"""File protocol between the Windower addon and the bot.

All files live in the addon folder. Each character has its own files, so
several game instances never write to the same file.

  sendoria_<Char>.out   addon -> bot, append only
      M <TAB> epoch <TAB> chat_type <TAB> sender <TAB> target <TAB> message
      A <TAB> epoch <TAB> request_id <TAB> status         (status: ok|stale|bad)
  sendoria_<Char>.in    bot -> addon, append only
      request_id <TAB> epoch <TAB> chat_type <TAB> target <TAB> message
  sendoria_<Char>.hb    addon heartbeat: protocol <TAB> epoch <TAB> addon_version
  sendoria_bot.hb       bot heartbeat:   protocol <TAB> epoch <TAB> bot_version
  sendoria_bot.stop     created by `//sn stop`

Lines end with LF. Text fields are raw cp932 bytes. Writers replace TAB,
CR and LF inside fields with a space. The reader of a file consumes it by
renaming it first, so a writer never appends to a file that is being read.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ffxi_text

PROTOCOL = 3

CHAT_TYPES = (
    "Tell", "Party", "Linkshell1", "Linkshell2",
    "Say", "Shout", "Yell", "Unity",
)


@dataclass(frozen=True)
class ChatRecord:
    epoch: int
    chat_type: str
    sender: str
    target: str
    message: str


@dataclass(frozen=True)
class AckRecord:
    epoch: int
    request_id: str
    status: str


@dataclass(frozen=True)
class Heartbeat:
    protocol: int
    epoch: int
    version: str


def _text(raw: bytes) -> str:
    return raw.decode("ascii", errors="replace").strip()


def parse_out_line(line: bytes) -> ChatRecord | AckRecord | None:
    """Parse one addon record. Return None for a malformed line."""
    fields = line.rstrip(b"\r\n").split(b"\t")
    try:
        if fields[0] == b"M" and len(fields) == 6:
            chat_type = _text(fields[2])
            if chat_type not in CHAT_TYPES:
                return None
            message = ffxi_text.decode(fields[5])
            if not message:
                return None
            return ChatRecord(
                epoch=int(fields[1]),
                chat_type=chat_type,
                sender=ffxi_text.decode(fields[3]),
                target=ffxi_text.decode(fields[4]),
                message=message,
            )
        if fields[0] == b"A" and len(fields) == 4:
            return AckRecord(int(fields[1]), _text(fields[2]), _text(fields[3]))
    except ValueError:
        return None
    return None


def _field(value: str) -> bytes:
    return ffxi_text.encode(value.replace("\t", " ").replace("\r", " ").replace("\n", " "))


def encode_in_line(request_id: str, epoch: int, chat_type: str, target: str, message: str) -> bytes:
    return b"\t".join([
        _field(request_id), str(epoch).encode(), _field(chat_type),
        _field(target), _field(message),
    ]) + b"\n"


def parse_heartbeat(raw: bytes) -> Heartbeat | None:
    fields = raw.strip().split(b"\t")
    if len(fields) != 3:
        return None
    try:
        return Heartbeat(int(fields[0]), int(fields[1]), _text(fields[2]))
    except ValueError:
        return None


def encode_heartbeat(epoch: int, version: str) -> bytes:
    return f"{PROTOCOL}\t{epoch}\t{version}\n".encode()
