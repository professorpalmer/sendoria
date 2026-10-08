"""Discord side of the relay."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field

import discord

from . import __version__, protocol
from .config import Settings
from .core import GameCommand, Post, Rejection, Relay
from .ipc import Folder
from .protocol import AckRecord, ChatRecord

log = logging.getLogger("sendoria")

POLL_SECONDS = 0.25
HEARTBEAT_SECONDS = 5
ACK_TIMEOUT = 45
# Discord allows 2000 characters per message.
BATCH_CHARS = 1900
# With --auto, exit when no character is online for this long.
AUTO_EXIT_SECONDS = 60

QUEUED, SENT, FAILED = "⏳", "✅", "❌"


@dataclass
class Pending:
    message: discord.Message
    waiting: set[str]
    deadline: float
    failed: bool = False


@dataclass
class ChannelSender:
    posts: deque[Post] = field(default_factory=deque)
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None


class SendoriaBot(discord.Client):
    def __init__(self, settings: Settings, folder: Folder, auto_exit: bool) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.settings = settings
        self.folder = folder
        self.relay = Relay(settings)
        self.auto_exit = auto_exit
        self.senders: dict[int, ChannelSender] = {}
        self.tell_posts: OrderedDict[int, tuple[str, str]] = OrderedDict()
        self.pending: dict[str, Pending] = {}
        self.online: dict[str, float] = {}  # character -> first seen
        self.last_online = time.time()
        self.request_seq = 0

    async def setup_hook(self) -> None:
        self.pump_task = asyncio.create_task(self._pump())

    async def on_ready(self) -> None:
        log.info("connected to Discord as %s", self.user)
        for chat_type, channel_id in self.settings.routes.items():
            channel = await self._channel(channel_id)
            if channel is None:
                log.error("%s: channel %s not found or not visible to the bot", chat_type, channel_id)
                continue
            perms = channel.permissions_for(channel.guild.me)
            missing = [p for p in ("view_channel", "send_messages", "add_reactions", "read_message_history")
                       if not getattr(perms, p)]
            if missing:
                log.error("%s: bot lacks %s in #%s", chat_type, ", ".join(missing), channel.name)
            else:
                log.info("%s -> #%s", chat_type, channel.name)
        await self._update_presence()

    async def _channel(self, channel_id: int) -> discord.TextChannel | None:
        channel = self.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)
            except discord.HTTPException:
                return None
        return channel if isinstance(channel, (discord.TextChannel, discord.Thread)) else None

    # Game -> Discord

    async def _pump(self) -> None:
        await self.wait_until_ready()
        next_beat = 0.0
        while not self.is_closed():
            now = time.time()
            try:
                if now >= next_beat:
                    self.folder.write_bot_heartbeat(int(now), __version__)
                    await self._refresh_online(int(now))
                    next_beat = now + HEARTBEAT_SECONDS
                for char in list(self.online):
                    for record in self.folder.take_outbox(char, int(now)):
                        await self._handle_record(char, record, int(now))
                await self._expire_pending(now)
                if self.folder.stop_requested():
                    log.info("stop requested from the game")
                    break
                if self.auto_exit and not self.online and now - self.last_online > AUTO_EXIT_SECONDS:
                    log.info("no character online for %ds, exiting", AUTO_EXIT_SECONDS)
                    break
            except Exception:
                log.exception("relay loop error")
            await asyncio.sleep(POLL_SECONDS)
        await self.close()

    async def _refresh_online(self, now: int) -> None:
        current = self.folder.characters(now)
        changed = set(current) != set(self.online)
        for name, beat in current.items():
            if name not in self.online:
                log.info("%s is online (addon %s)", name, beat.version)
                if beat.protocol != protocol.PROTOCOL:
                    log.error("%s runs addon protocol %d, bot needs %d. Update both from the same release.",
                              name, beat.protocol, protocol.PROTOCOL)
                self.online[name] = time.time()
        for name in list(self.online):
            if name not in current:
                log.info("%s is offline", name)
                # Drain what it wrote before it stopped.
                for record in self.folder.take_outbox(name, now):
                    await self._handle_record(name, record, now)
                del self.online[name]
        if self.online:
            self.last_online = time.time()
        if changed:
            await self._update_presence()

    async def _update_presence(self) -> None:
        if self.online:
            names = ", ".join(self._online_order())
            activity = discord.Activity(type=discord.ActivityType.watching, name=f"Vana'diel: {names}")
            await self.change_presence(status=discord.Status.online, activity=activity)
        else:
            await self.change_presence(status=discord.Status.idle,
                                       activity=discord.Game("waiting for FFXI"))

    def _online_order(self) -> list[str]:
        return sorted(self.online, key=self.online.__getitem__)

    async def _handle_record(self, char: str, record: ChatRecord | AckRecord, now: int) -> None:
        if isinstance(record, AckRecord):
            await self._ack(record)
            return
        post = self.relay.post_for(char, record, len(self.online), now)
        if post is None:
            return
        sender = self.senders.get(post.channel_id)
        if sender is None:
            sender = self.senders[post.channel_id] = ChannelSender()
            sender.task = asyncio.create_task(self._drain(post.channel_id, sender))
        sender.posts.append(post)
        sender.ready.set()

    async def _drain(self, channel_id: int, sender: ChannelSender) -> None:
        """Send queued posts. Lines that arrive during a send go out together."""
        while True:
            if not sender.posts:
                sender.ready.clear()
                await sender.ready.wait()
            batch = [sender.posts.popleft()]
            size = len(batch[0].text)
            while sender.posts and size + 1 + len(sender.posts[0].text) <= BATCH_CHARS:
                size += 1 + len(sender.posts[0].text)
                batch.append(sender.posts.popleft())
            channel = await self._channel(channel_id)
            if channel is None:
                continue
            text = "\n".join(p.text for p in batch)[:2000]
            try:
                sent = await channel.send(text)
            except discord.HTTPException as exc:
                log.error("send to #%s failed: %s", channel, exc)
                continue
            peers = {(p.peer, p.char) for p in batch}
            if len(peers) == 1 and batch[0].peer:
                self.tell_posts[sent.id] = batch[0].peer, batch[0].char
                while len(self.tell_posts) > 1000:
                    self.tell_posts.popitem(last=False)

    # Discord -> game

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.webhook_id is not None:
            return
        content = message.content.strip()
        if content.lower() == "!status" and message.channel.id in self.settings.channel_types:
            await message.reply(self._status_text(), mention_author=False)
            return

        reply_to = None
        if message.reference and message.reference.message_id:
            reply_to = self.tell_posts.get(message.reference.message_id)
        command = self.relay.command_for(
            message.channel.id, message.author.id, message.author.display_name,
            message.clean_content, reply_to,
        )
        if command is None:
            return
        if isinstance(command, Rejection):
            await self._reject(message, command.reason)
            return
        await self._send_to_game(message, command)

    async def _send_to_game(self, message: discord.Message, command: GameCommand) -> None:
        char = self.relay.pick_character(self._online_order(), command.char)
        if char is None:
            who = command.char or self.settings.send_as
            await self._reject(message, f"{who} is not online." if who else "No FFXI character is online.")
            return
        now = int(time.time())
        ids = set()
        lines = []
        for text in command.lines:
            self.request_seq += 1
            request_id = f"{message.id}.{self.request_seq}"
            ids.add(request_id)
            lines.append(protocol.encode_in_line(request_id, now, command.chat_type, command.target, text))
        try:
            self.folder.give_inbox(char, lines)
        except OSError as exc:
            await self._reject(message, f"Could not hand the message to the game: {exc}")
            return
        self.relay.expect_echo(char, command, now)
        pending = Pending(message, ids, time.time() + ACK_TIMEOUT)
        for request_id in ids:
            self.pending[request_id] = pending
        await self._react(message, QUEUED)
        if command.truncated:
            await message.reply(f"Only the first {len(command.lines)} game lines were sent.",
                                mention_author=False, delete_after=15)

    async def _ack(self, ack: AckRecord) -> None:
        pending = self.pending.pop(ack.request_id, None)
        if pending is None:
            return
        pending.waiting.discard(ack.request_id)
        if ack.status != "ok":
            pending.failed = True
            log.warning("game refused request %s: %s", ack.request_id, ack.status)
        if not pending.waiting:
            await self._settle(pending.message, not pending.failed)

    async def _expire_pending(self, now: float) -> None:
        expired = {id(p): p for p in self.pending.values() if p.deadline < now}
        for pending in expired.values():
            for request_id in pending.waiting:
                self.pending.pop(request_id, None)
            await self._settle(pending.message, False)

    async def _settle(self, message: discord.Message, ok: bool) -> None:
        try:
            await message.remove_reaction(QUEUED, self.user)  # type: ignore[arg-type]
        except discord.HTTPException:
            pass
        await self._react(message, SENT if ok else FAILED)

    async def _react(self, message: discord.Message, emoji: str) -> None:
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException as exc:
            log.warning("cannot add reaction: %s", exc)

    async def _reject(self, message: discord.Message, reason: str) -> None:
        await self._react(message, FAILED)
        try:
            await message.reply(reason, mention_author=False, delete_after=20)
        except discord.HTTPException:
            pass

    def _status_text(self) -> str:
        chars = ", ".join(self._online_order()) or "none"
        target = self.relay.pick_character(self._online_order()) or "nobody"
        return (f"Sendoria {__version__}\n"
                f"Characters online: {chars}\n"
                f"Discord messages go to: {target}")
