<div align="center">
<img src="https://i.imgur.com/HTyEADB.png" width="400">
</div>

# Sendoria

Sendoria relays chat between Final Fantasy XI and Discord in both directions.
It has two parts: a Windower addon and a small Discord bot that runs on the same PC.

[Video setup guide](https://youtu.be/bHziEsnsxG4) (made for version 2. The steps are the same.)

## What it does

- Relays tells, party, linkshell 1 and 2, say, shout, yell, and unity to Discord channels that you choose.
- Shows Japanese text, auto-translate phrases, and element symbols correctly.
- Types what you write in Discord into the game. Japanese works in this direction too.
- Tells: reply to a relayed tell in Discord, or use `/r message` or `/t Name message`.
- Marks each Discord message with a reaction: queued, then sent or failed.
- Puts lines that arrive together into one Discord message, so busy chat is not lost to rate limits.
- Hides repeated identical yells and shouts (5 minutes by default).
- Works with several characters at the same time. A line that two of your characters see posts once.
- Starts with the addon and stops when the game closes (optional).

## Setup

### 1. Install

1. Download `Sendoria.zip` from the [latest release](https://github.com/professorpalmer/sendoria/releases/latest).
2. Extract it into `Windower/addons/`. You get `Windower/addons/sendoria/`.

To update, extract a new release over the old folder. Your `sendoria_config.txt` stays.

### 2. Create the Discord bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create an application.
2. Go to **Bot**. Turn on **Message Content Intent** under Privileged Gateway Intents.
3. Click **Reset Token** and copy the token.
4. Go to **OAuth2 > URL Generator**. Select `bot`, then these permissions:
   - View Channels
   - Send Messages
   - Read Message History
   - Add Reactions
5. Open the generated URL and add the bot to your server.

### 3. Configure

1. Start `SendoriaBot.exe` once. It creates `sendoria_config.txt` and stops.
2. In Discord, turn on Developer Mode: **Settings > Advanced > Developer Mode**.
3. Create a channel for each chat type you want, for example `#tells`, `#party`, `#linkshell`.
4. Right-click each channel, click **Copy Channel ID**, and paste the id into `sendoria_config.txt`:

   ```
   BOT_TOKEN=your token
   CHANNEL_Tell=123456789012345678
   CHANNEL_Party=123456789012345679
   ```

   Only chat types with a channel are relayed. The file lists the optional settings.

### 4. Run

In game:

```
//lua load sendoria
//sn autostart on
```

With autostart on, the addon starts the bot, and the bot stops itself about a minute after the last character logs out.
You can also run `SendoriaBot.exe` yourself. Use `//sn test` to send a test line to your tells channel.

## Use

Game to Discord: chat as usual.

Discord to game: type in a relay channel. The text goes to that channel's chat type.
Linkshell lines start with your Discord name, so the linkshell knows who wrote them.

| In Discord | In game |
| --- | --- |
| text in `#party` | `/p text` |
| reply to a relayed tell | `/tell <that player> text` |
| `/r text` | tell to the last player who sent you a tell |
| `/t Name text` | `/tell Name text` |
| `/p` `/l` `/l2` `/s` `/sh` `/y` `/u` + text | that chat type, from any relay channel |
| `!status` | the bot replies with the online characters |

Long messages are split into game-sized lines. Emoji that the game cannot show are removed.

## Addon commands

| Command | Effect |
| --- | --- |
| `//sn` or `//sn status` | Relay, bot, and chat type state |
| `//sn on` / `//sn off` | Turn the whole relay on or off |
| `//sn <type> on\|off` | Mute or unmute one type: `tell party ls1 ls2 say shout yell unity outgoing` |
| `//sn autostart on\|off` | Start the bot with the addon |
| `//sn start` / `//sn stop` | Start or stop the bot |
| `//sn test [type]` | Send a test line to Discord |
| `//sn help` | List the commands |

## Several characters

Each character writes its own files, so several game instances can share one addon folder and one bot.
Discord messages go to the character that logged in first. To choose one, set `SEND_AS=Name` in `sendoria_config.txt`.
A reply to a tell always comes from the character that got the tell.

## Troubleshooting

- `//sn status` shows if the bot is online and if its version matches the addon.
- The bot writes `sendoria_bot.log` in the addon folder. Read it first when something does not relay.
- "Discord refused the bot token": copy the token again.
- "Turn on Message Content Intent": see setup step 2.
- "bot lacks ... in #channel": give the bot the permissions from setup step 2 in that channel.
- Only people in `ALLOWED_USERS` can send to the game when that setting is used.

## Build from source

The bot is Python 3.11 or later with discord.py.

```
cd bot
pip install -r requirements.txt pytest pyinstaller
python -m pytest -q
python build.py
```

The tests run the real addon under LuaJIT (the Lua that Windower uses) when `luajit` is installed.
Tagged releases build the Windows executables and the release zip in GitHub Actions.
