"""Read sendoria_config.txt (KEY=VALUE lines, # comments)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .protocol import CHAT_TYPES

log = logging.getLogger("sendoria")

CONFIG_NAME = "sendoria_config.txt"
EXAMPLE_NAME = "sendoria_config.example.txt"
DEFAULT_ROUTE = "Default"

_TYPE_NAMES = {t.lower(): t for t in CHAT_TYPES + (DEFAULT_ROUTE,)}
_TYPE_NAMES.update({"tells": "Tell", "ls": "Linkshell1", "ls1": "Linkshell1", "ls2": "Linkshell2"})


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    token: str
    # chat type (or "Default") -> Discord channel id
    routes: dict[str, int]
    send_as: str = ""
    allowed_users: frozenset[int] = frozenset()
    repeat_filter_seconds: int = 300
    channel_types: dict[int, tuple[str, ...]] = field(init=False)

    def __post_init__(self) -> None:
        by_channel: dict[int, list[str]] = {}
        for chat_type, channel_id in self.routes.items():
            by_channel.setdefault(channel_id, []).append(chat_type)
        object.__setattr__(self, "channel_types", {k: tuple(v) for k, v in by_channel.items()})

    def channel_for(self, chat_type: str) -> int | None:
        return self.routes.get(chat_type) or self.routes.get(DEFAULT_ROUTE)


def parse(text: str) -> Settings:
    values: dict[str, str] = {}
    routes: dict[str, int] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            log.warning("config line %d ignored (no '='): %s", number, line)
            continue
        key, value = key.strip(), value.strip()
        if key.upper().startswith("CHANNEL_"):
            chat_type = _TYPE_NAMES.get(key[8:].lower())
            if chat_type is None:
                log.warning("config line %d: unknown chat type %r", number, key[8:])
            elif value.isdigit():
                routes[chat_type] = int(value)
            elif value and not value.upper().startswith("YOUR_"):
                log.warning("config line %d: %s is not a channel id", number, key)
            continue
        values[key.upper()] = value

    token = values.get("BOT_TOKEN", "")
    if not token or token.upper().startswith("YOUR_"):
        raise ConfigError("BOT_TOKEN is not set in sendoria_config.txt")
    if not routes:
        raise ConfigError("no CHANNEL_ lines with a channel id in sendoria_config.txt")

    allowed = values.get("ALLOWED_USERS", "")
    try:
        allowed_users = frozenset(int(x) for x in allowed.replace(",", " ").split())
        repeat = int(values.get("REPEAT_FILTER_SECONDS", "300") or 0)
    except ValueError as exc:
        raise ConfigError(f"bad number in sendoria_config.txt: {exc}") from exc

    return Settings(
        token=token,
        routes=routes,
        send_as=values.get("SEND_AS", "").strip().capitalize(),
        allowed_users=allowed_users,
        repeat_filter_seconds=max(repeat, 0),
    )


def load(folder: Path) -> Settings:
    path = folder / CONFIG_NAME
    if not path.exists():
        example = folder / EXAMPLE_NAME
        if example.exists():
            path.write_bytes(example.read_bytes())
            raise ConfigError(f"created {path}. Add your bot token and channel ids, then start the bot again.")
        raise ConfigError(f"{path} not found")
    return parse(path.read_text(encoding="utf-8-sig"))
