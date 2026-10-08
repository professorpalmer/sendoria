# Sendoria 3.0.0

A rebuild of the relay core. Install from `Sendoria.zip` below. The addon and the bot must come from the same release.

## Fixed

- Japanese text from the game showed as broken characters in Discord ([#1](https://github.com/professorpalmer/sendoria/issues/1)). The bot now decodes FFXI's Shift-JIS text, auto-translate brackets, and color codes.
- Japanese text from Discord now reaches the game.
- Messages are no longer dropped. The old per-type cooldown discarded every line that came within a second of the one before it.
- Lines are no longer lost when the bot and the addon use the relay files at the same time.
- Outgoing tells now show who the tell was to.
- Game text can no longer ping `@everyone` or make Discord links.
- Discord text can no longer run Windower commands through `;`.
- Starting the addon on several characters no longer starts several bots.
- The bot no longer posts a backlog of old lines after a restart.

## New

- Reply to a relayed tell in Discord to answer it. `/r` and `/t Name` also work.
- Reactions show if a Discord message reached the game.
- Lines that arrive together go out as one Discord message.
- Repeated yell and shout filter (`REPEAT_FILTER_SECONDS`).
- Multibox support: per-character files, one bot, duplicate lines posted once, `SEND_AS`.
- Optional `CHANNEL_Default` for one channel with all types, and slash prefixes in any channel.
- `ALLOWED_USERS` to limit who can send to the game.
- `//sn test`, `//sn start`, `!status`, and a bot status line in `//sn status`.
- With autostart, the bot stops by itself after the game closes. No Task Manager.
- `sendoria_bot.log` in the addon folder.
- Every chat type relays by default. The channels in `sendoria_config.txt` choose what goes to Discord.

## Upgrade from 2.x

1. Extract the zip over your `sendoria` folder.
2. Keep your `sendoria_config.txt`. The format did not change.
3. Delete `chat_relay.txt`, `discord_responses.txt`, and `bot_position.txt` if they exist. Version 3 does not use them.
