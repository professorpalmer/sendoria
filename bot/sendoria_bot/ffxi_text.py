"""Convert between FFXI chat bytes and Unicode text.

FFXI chat is Shift-JIS (Windows code page 932) with game-specific control
sequences mixed in. Decoding the bytes as UTF-8 drops every Japanese
character, which is the bug in GitHub issue #1.
"""

from __future__ import annotations

import re
import unicodedata

CODEC = "cp932"

# 0xEF xx is never a cp932 lead byte. FFXI uses it for its own glyphs.
_EF_GLYPHS = {
    0x1F: "(Fire)",
    0x20: "(Ice)",
    0x21: "(Wind)",
    0x22: "(Earth)",
    0x23: "(Lightning)",
    0x24: "(Water)",
    0x25: "(Light)",
    0x26: "(Dark)",
    0x27: "{",  # auto-translate open
    0x28: "}",  # auto-translate close
}

# One control byte followed by one argument byte (text color, prompts).
_TWO_BYTE_CONTROLS = {0x1E, 0x1F, 0x7F}
_AUTO_TRANSLATE = 0xFD
_LINE_BREAK = 0x07


def _is_lead_byte(b: int) -> bool:
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC


def decode(raw: bytes) -> str:
    """Decode FFXI chat bytes to readable Unicode text."""
    out: list[str] = []
    plain = bytearray()

    def flush() -> None:
        if plain:
            out.append(plain.decode(CODEC, errors="replace"))
            plain.clear()

    i, n = 0, len(raw)
    while i < n:
        b = raw[i]
        if b == 0xEF and i + 1 < n:
            flush()
            out.append(_EF_GLYPHS.get(raw[i + 1], ""))
            i += 2
        elif b == _AUTO_TRANSLATE:
            # Raw auto-translate block: FD xx xx xx xx FD. The addon expands
            # these before it writes, so this is only a fallback.
            flush()
            end = raw.find(bytes([_AUTO_TRANSLATE]), i + 1, i + 7)
            out.append("{?}")
            i = end + 1 if end != -1 else n
        elif _is_lead_byte(b):
            plain += raw[i:i + 2]
            i += 2
        elif b in _TWO_BYTE_CONTROLS:
            i += 2
        elif b == _LINE_BREAK:
            plain += b"\n"
            i += 1
        elif b < 0x20:
            i += 1
        else:
            plain.append(b)
            i += 1
    flush()
    return "".join(out).strip()


_PUNCTUATION = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
})

# Characters the game or Windower treat as syntax. Map them to the
# full-width forms, which look the same to a reader and are inert.
_INERT = str.maketrans({
    "<": "＜",   # <t>, <me>, <call> expansion
    ">": "＞",
    ";": "；",   # Windower command separator
    '"': "”",   # Windower argument quoting
})

_CUSTOM_EMOJI = re.compile(r"<a?:(\w+):\d+>")
_WHITESPACE = re.compile(r"\s+")


def to_game_text(text: str) -> str:
    """Normalize Discord text to the subset that is safe to type in game.

    Characters that cp932 cannot encode (most emoji) are dropped.
    """
    text = _CUSTOM_EMOJI.sub(r":\1:", text)
    text = unicodedata.normalize("NFC", text).translate(_PUNCTUATION)
    text = _WHITESPACE.sub(" ", text).strip().translate(_INERT)
    kept = []
    for ch in text:
        try:
            ch.encode(CODEC)
        except UnicodeEncodeError:
            continue
        kept.append(ch)
    return _WHITESPACE.sub(" ", "".join(kept)).strip()


def encode(text: str) -> bytes:
    """Encode text that already passed through to_game_text."""
    return text.encode(CODEC)


def split_for_game(text: str, limit: int) -> list[str]:
    """Split text into pieces of at most `limit` cp932 bytes.

    Splits on whitespace when it can, and never inside a character.
    """
    pieces: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}" if current else word
        if len(encode(candidate)) <= limit:
            current = candidate
            continue
        if current:
            pieces.append(current)
            current = ""
        while len(encode(word)) > limit:
            cut = len(word)
            while len(encode(word[:cut])) > limit:
                cut -= 1
            pieces.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        pieces.append(current)
    return pieces
