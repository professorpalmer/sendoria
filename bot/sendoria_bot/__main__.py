"""Start the bot: python -m sendoria_bot [--dir ADDON_FOLDER] [--auto]."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import IO

import discord

from . import __version__, config
from .bot import SendoriaBot
from .ipc import Folder

log = logging.getLogger("sendoria")


def _default_folder() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def _setup_logging(folder: Path) -> None:
    handlers: list[logging.Handler] = [logging.handlers.RotatingFileHandler(
        folder / "sendoria_bot.log", maxBytes=1_000_000, backupCount=1, encoding="utf-8")]
    if sys.stdout is not None:  # None in the windowless build
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


def _single_instance(folder: Path) -> IO[bytes] | None:
    """Hold an exclusive lock for the life of the process. None if another bot has it."""
    handle = open(folder / "sendoria_bot.lock", "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="SendoriaBot", description="FFXI <-> Discord chat relay")
    parser.add_argument("--dir", type=Path, default=None, help="Sendoria addon folder")
    parser.add_argument("--auto", action="store_true",
                        help="exit when no character is online (used by autostart)")
    args = parser.parse_args(argv)

    folder = (args.dir or _default_folder()).resolve()
    _setup_logging(folder)
    log.info("Sendoria bot %s in %s", __version__, folder)

    lock = _single_instance(folder)
    if lock is None:
        log.info("another Sendoria bot is already running for this folder")
        return 0

    try:
        settings = config.load(folder)
    except config.ConfigError as exc:
        log.error("%s", exc)
        return 1

    bot = SendoriaBot(settings, Folder(folder), auto_exit=args.auto)
    try:
        bot.run(settings.token, log_handler=None)
    except discord.LoginFailure:
        log.error("Discord refused the bot token. Copy it again from the Developer Portal.")
        return 1
    except discord.PrivilegedIntentsRequired:
        log.error("Turn on Message Content Intent: Developer Portal > Bot > Privileged Gateway Intents.")
        return 1
    finally:
        Folder(folder).clear_bot_heartbeat()
        lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
