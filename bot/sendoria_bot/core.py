"""Relay rules with no I/O: game records to Discord posts, Discord text to game commands."""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import ffxi_text
from .config import DEFAULT_ROUTE, Settings
from .protocol import ChatRecord

# Text bytes per game line, after the command (/l, /tell Name, ...).
GAME_LINE_BYTES = 100
MAX_GAME_LINES = 4
# Window in which two characters that see the same line produce one post.
MULTIBOX_WINDOW = 10
REPEAT_FILTERED = ("Yell", "Shout")
# How long a line typed for Discord can take to show in game.
ECHO_SECONDS = 30

_NAME = re.compile(r"^[A-Za-z]{3,15}$")
_MARKDOWN = re.compile(r"([\\*_~`|>#\[\]()-])")

PREFIXES = {
    "/p": "Party", "/party": "Party",
    "/l": "Linkshell1", "/linkshell": "Linkshell1", "/l1": "Linkshell1",
    "/l2": "Linkshell2", "/linkshell2": "Linkshell2",
    "/s": "Say", "/say": "Say",
    "/sh": "Shout", "/shout": "Shout",
    "/y": "Yell", "/yell": "Yell",
    "/u": "Unity", "/unity": "Unity",
    "/t": "Tell", "/tell": "Tell",
    "/r": "Reply", "/reply": "Reply",
}
NAME_TAGGED = ("Linkshell1", "Linkshell2")


def escape(text: str) -> str:
    return _MARKDOWN.sub(r"\\\1", text)


@dataclass(frozen=True)
class Post:
    channel_id: int
    text: str
    # For tells: the other player and the character in the conversation.
    peer: str = ""
    char: str = ""


@dataclass(frozen=True)
class GameCommand:
    chat_type: str
    target: str
    lines: tuple[str, ...]
    truncated: bool
    # Character that must send it, when the conversation fixes one.
    char: str = ""


@dataclass(frozen=True)
class Rejection:
    reason: str


class Relay:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._seen: dict[tuple[str, str, str], int] = {}
        # Lines typed for Discord that another of our characters can see.
        self._expected: dict[tuple[str, str, str], int] = {}
        self.last_tell: tuple[str, str] | None = None  # (peer, char)

    # Game -> Discord

    def _duplicate(self, rec: ChatRecord, now: int) -> bool:
        if rec.chat_type == "Tell":
            return False
        key = (rec.chat_type, rec.sender, rec.message)
        if self._expected.pop(key, 0) >= now:
            return True
        window = MULTIBOX_WINDOW
        if rec.chat_type in REPEAT_FILTERED:
            window = max(window, self.settings.repeat_filter_seconds)
        last = self._seen.get(key)
        if last is not None and now - last < window:
            return True
        self._seen[key] = now
        if len(self._seen) > 4096:
            horizon = now - max(MULTIBOX_WINDOW, self.settings.repeat_filter_seconds)
            self._seen = {k: t for k, t in self._seen.items() if t >= horizon}
        return False

    def post_for(self, char: str, rec: ChatRecord, characters_online: int, now: int) -> Post | None:
        channel_id = self.settings.channel_for(rec.chat_type)
        if channel_id is None or self._duplicate(rec, now):
            return None

        types = self.settings.channel_types.get(channel_id, ())
        tag = f"`{rec.chat_type}` " if len(types) > 1 or DEFAULT_ROUTE in types else ""
        body = escape(rec.message)

        if rec.chat_type != "Tell":
            return Post(channel_id, f"{tag}**{escape(rec.sender)}**: {body}")

        outgoing = bool(rec.target) or rec.sender == char
        peer = rec.target if outgoing else rec.sender
        if outgoing:
            head = f"**{escape(char)} → {escape(peer)}**"
        else:
            self.last_tell = (peer, char)
            head = f"**{escape(peer)}**"
            if characters_online > 1:
                head += f" → {escape(char)}"
        return Post(channel_id, f"{tag}{head}: {body}", peer=peer, char=char)

    # Discord -> game

    def command_for(
        self,
        channel_id: int,
        author_id: int,
        author_name: str,
        content: str,
        reply_to: tuple[str, str] | None,
    ) -> GameCommand | Rejection | None:
        """Turn a Discord message into a game command.

        reply_to is (peer, char) when the message is a Discord reply to a
        relayed tell. Returns None when the message is not for the game.
        """
        types = self.settings.channel_types.get(channel_id)
        if not types:
            return None
        if self.settings.allowed_users and author_id not in self.settings.allowed_users:
            return Rejection("You are not in ALLOWED_USERS for this relay.")

        text = content.strip()
        chat_type, target, char = "", "", ""
        word, _, rest = text.partition(" ")
        prefix = PREFIXES.get(word.lower())

        if prefix == "Tell":
            target, _, text = rest.strip().partition(" ")
        elif prefix == "Reply":
            if self.last_tell is None:
                return Rejection("No tell to reply to yet.")
            chat_type, (target, char), text = "Tell", self.last_tell, rest
        elif prefix:
            chat_type, text = prefix, rest
        elif reply_to is not None:
            chat_type, (target, char) = "Tell", reply_to
        elif len(types) == 1 and types[0] not in ("Tell", DEFAULT_ROUTE):
            chat_type = types[0]
        elif types == ("Tell",):
            return Rejection("Use `/t Name message`, `/r message`, or reply to a tell.")
        else:
            return Rejection("Start with /p, /l, /l2, /s, /sh, /y, /u, /t Name, or /r.")

        if prefix == "Tell":
            chat_type = "Tell"
        if chat_type == "Tell":
            if not _NAME.match(target):
                return Rejection(f"`{target or '?'}` is not a character name.")
            target = target.capitalize()

        text = ffxi_text.to_game_text(text)
        if not text:
            return Rejection("Nothing left to send after removing characters the game cannot show.")

        lead = ""
        if chat_type in NAME_TAGGED:
            name = ffxi_text.to_game_text(author_name) or "Discord"
            lead = f"[{name}]: "
        budget = GAME_LINE_BYTES - len(ffxi_text.encode(lead))
        pieces = ffxi_text.split_for_game(text, max(budget, 20))
        truncated = len(pieces) > MAX_GAME_LINES
        lines = tuple(lead + p for p in pieces[:MAX_GAME_LINES])
        return GameCommand(chat_type, target, lines, truncated, char)

    def expect_echo(self, char: str, command: GameCommand, now: int) -> None:
        """The game shows a typed line to the other characters too. Do not post it back."""
        if command.chat_type == "Tell":
            return
        self._expected = {k: t for k, t in self._expected.items() if t >= now}
        for line in command.lines:
            self._expected[(command.chat_type, char, line)] = now + ECHO_SECONDS

    def pick_character(self, online: list[str], wanted: str = "") -> str | None:
        """online is ordered by first heartbeat, oldest first."""
        for name in (wanted, self.settings.send_as):
            if name:
                return name if name in online else None
        return online[0] if online else None
