from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sendoria_bot import config, core, ffxi_text, protocol
from sendoria_bot.config import Settings
from sendoria_bot.core import GameCommand, Rejection, Relay
from sendoria_bot.ipc import Folder
from sendoria_bot.protocol import AckRecord, ChatRecord

ADDON = Path(__file__).resolve().parents[2] / "sendoria"
DRIVER = Path(__file__).with_name("lua_driver.lua")
LUAJIT = shutil.which("luajit")
CLOCK = 1700000000  # driver start time

JP_YELL = "ソーティ ボス 募集中 5/6"


def sjis(text: str) -> bytes:
    return text.encode("cp932")


def settings(**routes: int) -> Settings:
    return Settings(token="t", routes=routes or {"Tell": 1, "Party": 2, "Linkshell1": 3, "Yell": 4})


# ffxi_text

def test_decode_japanese_that_utf8_dropped():
    raw = sjis(JP_YELL)
    assert raw.decode("utf-8", errors="ignore") != JP_YELL  # the issue #1 bug
    assert ffxi_text.decode(raw) == JP_YELL


def test_decode_ffxi_controls_and_glyphs():
    raw = (b"\x1e\x02Sortie " + b"\xef\x27" + b"Boss" + b"\xef\x28" + b"\x1e\x01 "
           + sjis("茨") + b" \xef\x1f" + b"\x07next")
    assert sjis("茨") == b"\x88\xef"  # 0xEF as a trail byte must not be a glyph
    assert ffxi_text.decode(raw) == "Sortie {Boss} 茨 (Fire)\nnext"


def test_decode_half_width_katakana_and_raw_auto_translate():
    assert ffxi_text.decode(b"\xb1\xb2 \xfd\x02\x02\x10\x01\xfd ok") == "ｱｲ {?} ok"


def test_to_game_text_makes_syntax_inert_and_drops_emoji():
    out = ffxi_text.to_game_text('hi <t>; "x" \U0001F600 <:pog:123> “q”  ')
    assert out == "hi ＜t＞； ”x” :pog: ”q”"
    assert not set("<>;") & set(out)
    ffxi_text.encode(out)


def test_split_for_game_respects_bytes_and_characters():
    text = "あ" * 120 + " tail"
    pieces = ffxi_text.split_for_game(text, 100)
    assert all(len(ffxi_text.encode(p)) <= 100 for p in pieces)
    assert "".join(pieces).replace(" ", "") == text.replace(" ", "")


# config

def test_config_parses_legacy_file_and_ignores_placeholders():
    s = config.parse("BOT_TOKEN=abc\nCHANNEL_Tell=11\nCHANNEL_Party=YOUR_PARTY_CHANNEL_ID\n"
                     "CHANNEL_ls2=11\nALLOWED_USERS=5, 6\nSEND_AS=zodiarchy\n")
    assert s.routes == {"Tell": 11, "Linkshell2": 11}
    assert s.channel_types[11] == ("Tell", "Linkshell2")
    assert s.allowed_users == {5, 6} and s.send_as == "Zodiarchy"


def test_config_requires_token():
    with pytest.raises(config.ConfigError):
        config.parse("BOT_TOKEN=YOUR_BOT_TOKEN_HERE\nCHANNEL_Tell=1\n")


# core: game -> Discord

def rec(chat_type="Party", sender="Bob", target="", message="hi", epoch=CLOCK):
    return ChatRecord(epoch, chat_type, sender, target, message)


def test_post_escapes_markdown_and_routes():
    post = Relay(settings()).post_for("Zod", rec(message="**x** [l](http://e)"), 1, CLOCK)
    assert post.channel_id == 2
    assert post.text == "**Bob**: \\*\\*x\\*\\* \\[l\\]\\(http://e\\)"


def test_multibox_duplicate_and_yell_repeat_filter():
    relay = Relay(settings())
    assert relay.post_for("A", rec(), 2, CLOCK)
    assert relay.post_for("B", rec(), 2, CLOCK + 1) is None
    assert relay.post_for("A", rec(), 2, CLOCK + 60)
    yell = rec("Yell", message="LFG")
    assert relay.post_for("A", yell, 1, CLOCK)
    assert relay.post_for("A", yell, 1, CLOCK + 200) is None
    assert relay.post_for("A", yell, 1, CLOCK + 400)


def test_tell_posts_carry_peer_and_direction():
    relay = Relay(settings())
    incoming = relay.post_for("Zod", rec("Tell", "Bob"), 2, CLOCK)
    assert incoming.text == "**Bob** → Zod: hi" and incoming.peer == "Bob"
    assert relay.last_tell == ("Bob", "Zod")
    outgoing = relay.post_for("Zod", rec("Tell", "Zod", "Amy"), 1, CLOCK)
    assert outgoing.text == "**Zod → Amy**: hi" and outgoing.peer == "Amy"


def test_default_channel_tags_type():
    relay = Relay(settings(Default=9))
    assert relay.post_for("Z", rec("Say"), 1, CLOCK).text == "`Say` **Bob**: hi"


# core: Discord -> game

def test_command_in_typed_channel_tags_linkshell_name():
    cmd = Relay(settings()).command_for(3, 1, "Cary", "こんにちは <t>", None)
    assert cmd == GameCommand("Linkshell1", "", ("[Cary]: こんにちは ＜t＞",), False)


def test_command_prefixes_reply_and_tells():
    relay = Relay(settings())
    assert relay.command_for(2, 1, "C", "/l2 yo", None).chat_type == "Linkshell2"
    assert relay.command_for(1, 1, "C", "/t bob hey there", None) == GameCommand("Tell", "Bob", ("hey there",), False)
    assert isinstance(relay.command_for(1, 1, "C", "hey", None), Rejection)
    assert isinstance(relay.command_for(1, 1, "C", "/r hey", None), Rejection)
    relay.last_tell = ("Bob", "Alt")
    assert relay.command_for(1, 1, "C", "/r hey", None) == GameCommand("Tell", "Bob", ("hey",), False, "Alt")
    assert relay.command_for(1, 1, "C", "sure", ("Amy", "Zod")) == GameCommand("Tell", "Amy", ("sure",), False, "Zod")
    assert isinstance(relay.command_for(1, 1, "C", "/t b@d x", None), Rejection)
    assert relay.command_for(99, 1, "C", "x", None) is None


def test_command_splits_long_text_and_respects_allowed_users():
    relay = Relay(settings())
    cmd = relay.command_for(2, 1, "C", "word " * 200, None)
    assert len(cmd.lines) == core.MAX_GAME_LINES and cmd.truncated
    locked = Relay(Settings(token="t", routes={"Party": 2}, allowed_users=frozenset({7})))
    assert isinstance(locked.command_for(2, 1, "C", "x", None), Rejection)
    assert isinstance(locked.command_for(2, 7, "C", "x", None), GameCommand)


def test_typed_line_seen_by_other_character_is_not_posted_back():
    relay = Relay(settings())
    cmd = relay.command_for(3, 1, "Cary", "hi all", None)
    relay.expect_echo("Zod", cmd, CLOCK)
    echo = rec("Linkshell1", "Zod", message="[Cary]: hi all")
    assert relay.post_for("Alt", echo, 2, CLOCK + 5) is None
    assert relay.post_for("Alt", rec("Linkshell1", "Zod", message="later"), 2, CLOCK + 5)


def test_pick_character():
    relay = Relay(settings())
    assert relay.pick_character(["A", "B"]) == "A"
    assert relay.pick_character(["A", "B"], "B") == "B"
    assert relay.pick_character(["A"], "B") is None
    assert relay.pick_character([]) is None


# ipc

def test_folder_take_outbox_skips_stale_and_partial(tmp_path):
    folder = Folder(tmp_path)
    (tmp_path / "sendoria_Zod.out").write_bytes(
        b"M\t%d\tParty\tBob\t\t" % CLOCK + sjis("やあ") + b"\n"
        b"M\t%d\tParty\tOld\t\told\n" % (CLOCK - 500) + b"garbage\n"
        b"A\t%d\t5.1\tok" % CLOCK)
    records = folder.take_outbox("Zod", CLOCK)
    assert records == [rec(message="やあ"), AckRecord(CLOCK, "5.1", "ok")]
    assert folder.take_outbox("Zod", CLOCK) == []


def test_folder_characters_reads_fresh_heartbeats(tmp_path):
    (tmp_path / "sendoria_Zod.hb").write_bytes(b"3\t%d\t3.0.0\n" % CLOCK)
    (tmp_path / "sendoria_Old.hb").write_bytes(b"3\t%d\t3.0.0\n" % (CLOCK - 100))
    (tmp_path / "sendoria_bot.hb").write_bytes(b"3\t%d\t3.0.0\n" % CLOCK)
    assert list(Folder(tmp_path).characters(CLOCK)) == ["Zod"]


# end to end through the real addon

def run_addon(folder: Path, script: str) -> list[str]:
    path = folder / "script.txt"
    path.write_text(script)
    result = subprocess.run([LUAJIT, str(DRIVER), str(folder) + "/", str(path)],
                            cwd=ADDON, capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


@pytest.mark.skipif(LUAJIT is None, reason="luajit not installed")
def test_end_to_end_japanese_both_ways(tmp_path):
    relay = Relay(settings())
    folder = Folder(tmp_path)

    # Game -> Discord: Japanese yell, auto-translate, own party line, outgoing tell.
    out = run_addon(tmp_path, "\n".join([
        "login Zodiarchy",
        f"chat 26 Anjou {sjis(JP_YELL).hex()}",
        f"chat 4 Bob {(b'need ' + b'\xef\x27Cure IV\xef\x28').hex()}",
        f"speech 4 {sjis('了解').hex()}",
        f"tell Amy {sjis('ありがとう').hex()}",
        "ticks 25",
    ]))
    assert out == []
    online = folder.characters(CLOCK + 6)
    assert list(online) == ["Zodiarchy"] and online["Zodiarchy"].protocol == protocol.PROTOCOL
    posts = [relay.post_for("Zodiarchy", r, 1, CLOCK) for r in folder.take_outbox("Zodiarchy", CLOCK + 6)]
    assert [(p.channel_id, p.text) for p in posts] == [
        (4, f"**Anjou**: {JP_YELL}"),
        (2, "**Bob**: need {Cure IV}"),
        (2, "**Zodiarchy**: 了解"),
        (1, "**Zodiarchy → Amy**: ありがとう"),
    ]

    # Discord -> game: Japanese reply to a tell, then the ack comes back.
    cmd = relay.command_for(1, 1, "Cary", "またね!", ("Amy", "Zodiarchy"))
    assert isinstance(cmd, GameCommand)
    folder.give_inbox("Zodiarchy", [protocol.encode_in_line("9.1", CLOCK, cmd.chat_type, cmd.target, cmd.lines[0])])
    out = run_addon(tmp_path, "login Zodiarchy\nticks 12\n" + f"tell Amy {sjis('またね!').hex()}\nticks 4\n")
    sends = [bytes.fromhex(line[5:]) for line in out if line.startswith("SEND ")]
    assert sends == [b"input /tell Amy " + sjis("またね!")]
    assert not (tmp_path / "sendoria_Zodiarchy.in").exists()
    # The ack arrives, and the game echo of the typed tell is not relayed back.
    assert folder.take_outbox("Zodiarchy", CLOCK + 5) == [AckRecord(CLOCK, "9.1", "ok")]


@pytest.mark.skipif(LUAJIT is None, reason="luajit not installed")
def test_end_to_end_refuses_stale_and_bad_requests(tmp_path):
    folder = Folder(tmp_path)
    folder.give_inbox("Zod", [
        protocol.encode_in_line("1.1", CLOCK - 300, "Party", "", "old"),
        protocol.encode_in_line("1.2", CLOCK, "Tell", "x y", "bad target"),
        protocol.encode_in_line("1.3", CLOCK, "Party", "", "ok;now"),
    ])
    out = run_addon(tmp_path, "login Zod\nticks 12\n")
    assert [bytes.fromhex(l[5:]) for l in out if l.startswith("SEND ")] == [b"input /p oknow"]
    acks = folder.take_outbox("Zod", CLOCK)
    assert [(a.request_id, a.status) for a in acks] == [("1.1", "stale"), ("1.2", "bad"), ("1.3", "ok")]


@pytest.mark.skipif(LUAJIT is None, reason="luajit not installed")
def test_end_to_end_mute_switch_and_test_command(tmp_path):
    out = run_addon(tmp_path, "login Zod\ncmd yell off\nchat 26 Anjou 6869\ncmd test party\nticks 2\n")
    assert "CHAT Sendoria: yell off" in out
    records = Folder(tmp_path).take_outbox("Zod", CLOCK)
    assert [(r.chat_type, r.sender, r.message) for r in records] == [("Party", "Zod", "Sendoria test line")]
