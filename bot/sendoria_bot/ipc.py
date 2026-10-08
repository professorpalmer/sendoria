"""File handoff with the addon. See protocol.py for the format."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from . import protocol
from .protocol import AckRecord, ChatRecord, Heartbeat

log = logging.getLogger("sendoria")

PREFIX = "sendoria_"
BOT_NAME = "bot"
# A character whose heartbeat is older than this is offline.
HEARTBEAT_TIMEOUT = 20
# Records older than this are dropped (backlog from when the bot was down).
STALE_SECONDS = 120

_CHAR_FILE = re.compile(rf"^{PREFIX}([A-Za-z]{{3,15}})\.hb$")


class Folder:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _file(self, name: str, ext: str) -> Path:
        return self.path / f"{PREFIX}{name}.{ext}"

    def characters(self, now: int) -> dict[str, Heartbeat]:
        """Characters with a fresh heartbeat."""
        found: dict[str, Heartbeat] = {}
        for entry in self.path.iterdir():
            match = _CHAR_FILE.match(entry.name)
            if not match or match.group(1) == BOT_NAME:
                continue
            try:
                beat = protocol.parse_heartbeat(entry.read_bytes())
            except OSError:
                continue
            if beat and now - beat.epoch <= HEARTBEAT_TIMEOUT:
                found[match.group(1)] = beat
        return found

    def take_outbox(self, char: str, now: int) -> list[ChatRecord | AckRecord]:
        """Consume everything the addon wrote for this character."""
        source = self._file(char, "out")
        taken = self._file(char, "out.taking")
        if not taken.exists():
            try:
                os.replace(source, taken)
            except FileNotFoundError:
                return []
            except PermissionError:
                # The addon has the file open. Take it on the next poll.
                return []
        try:
            data = taken.read_bytes()
        except OSError as exc:
            log.warning("cannot read %s: %s", taken.name, exc)
            return []
        taken.unlink(missing_ok=True)

        records: list[ChatRecord | AckRecord] = []
        for line in data.split(b"\n"):
            if not line.strip():
                continue
            record = protocol.parse_out_line(line)
            if record is None:
                log.debug("skipped malformed line from %s: %r", char, line[:80])
            elif now - record.epoch <= STALE_SECONDS:
                records.append(record)
        return records

    def give_inbox(self, char: str, lines: list[bytes]) -> None:
        with open(self._file(char, "in"), "ab") as handle:
            handle.write(b"".join(lines))

    def write_bot_heartbeat(self, now: int, version: str) -> None:
        target = self._file(BOT_NAME, "hb")
        temp = target.with_suffix(".hb.tmp")
        temp.write_bytes(protocol.encode_heartbeat(now, version))
        try:
            os.replace(temp, target)
        except PermissionError:
            # The addon is reading it. The next beat replaces it.
            temp.unlink(missing_ok=True)

    def clear_bot_heartbeat(self) -> None:
        self._file(BOT_NAME, "hb").unlink(missing_ok=True)

    def stop_requested(self) -> bool:
        stop = self._file(BOT_NAME, "stop")
        if stop.exists():
            stop.unlink(missing_ok=True)
            return True
        return False
