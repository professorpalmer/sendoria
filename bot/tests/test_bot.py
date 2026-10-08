from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from sendoria_bot import bot as bot_module
from sendoria_bot.bot import FAILED, QUEUED, SENT, SendoriaBot
from sendoria_bot.config import Settings
from sendoria_bot.ipc import Folder
from sendoria_bot.protocol import AckRecord, ChatRecord


class FakeChannel:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, text: str) -> SimpleNamespace:
        self.sent.append(text)
        await asyncio.sleep(0)
        return SimpleNamespace(id=1000 + len(self.sent))


class FakeMessage:
    def __init__(self, channel_id: int, content: str, reply_to: int | None = None) -> None:
        self.id = 55
        self.channel = SimpleNamespace(id=channel_id)
        self.author = SimpleNamespace(id=1, bot=False, display_name="Cary")
        self.webhook_id = None
        self.content = self.clean_content = content
        self.reference = SimpleNamespace(message_id=reply_to) if reply_to else None
        self.reactions: list[str] = []
        self.replies: list[str] = []

    async def add_reaction(self, emoji: str) -> None:
        self.reactions.append(emoji)

    async def remove_reaction(self, emoji: str, _user: object) -> None:
        self.reactions.remove(emoji)

    async def reply(self, text: str, **_: object) -> None:
        self.replies.append(text)


def make_bot(tmp_path) -> tuple[SendoriaBot, dict[int, FakeChannel]]:
    settings = Settings(token="t", routes={"Tell": 1, "Party": 2})
    client = SendoriaBot(settings, Folder(tmp_path), auto_exit=False)
    channels = {1: FakeChannel(), 2: FakeChannel()}

    async def channel(channel_id: int) -> FakeChannel:
        return channels[channel_id]

    client._channel = channel  # type: ignore[method-assign]
    return client, channels


def test_lines_batch_per_channel_and_tells_map_to_peer(tmp_path):
    async def scenario() -> None:
        client, channels = make_bot(tmp_path)
        client.online = {"Zod": time.time()}
        now = int(time.time())
        for i in range(30):
            await client._handle_record("Zod", ChatRecord(now, "Party", "Bob", "", f"line {i}"), now)
        await client._handle_record("Zod", ChatRecord(now, "Tell", "Amy", "", "psst"), now)
        await asyncio.sleep(0.05)
        party = channels[2].sent
        assert len(party) == 1  # 30 lines that arrive together: one Discord message
        assert party[0].count("\n") == 29
        assert channels[1].sent == ["**Amy**: psst"]
        assert client.tell_posts[1001] == ("Amy", "Zod")

    asyncio.run(scenario())


def test_discord_reply_goes_to_game_and_ack_settles(tmp_path):
    async def scenario() -> None:
        client, _ = make_bot(tmp_path)
        client.online = {"Zod": time.time()}
        client.tell_posts[1001] = ("Amy", "Zod")
        message = FakeMessage(1, "on my way", reply_to=1001)
        await client.on_message(message)
        assert message.reactions == [QUEUED]
        inbox = (tmp_path / "sendoria_Zod.in").read_bytes()
        assert inbox.endswith(b"\tTell\tAmy\ton my way\n")
        request_id = inbox.split(b"\t")[0].decode()
        await client._ack(AckRecord(0, request_id, "ok"))
        assert message.reactions == [SENT]

    asyncio.run(scenario())


def test_rejections_and_timeout(tmp_path, monkeypatch):
    async def scenario() -> None:
        client, _ = make_bot(tmp_path)
        offline = FakeMessage(2, "hello")
        await client.on_message(offline)
        assert offline.reactions == [FAILED] and offline.replies == ["No FFXI character is online."]

        client.online = {"Zod": time.time()}
        monkeypatch.setattr(bot_module, "ACK_TIMEOUT", -1)
        lost = FakeMessage(2, "hello")
        await client.on_message(lost)
        await client._expire_pending(time.time())
        assert lost.reactions == [FAILED] and not client.pending

    asyncio.run(scenario())
