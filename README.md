<div align="center">
<img src="https://i.imgur.com/HTyEADB.png" width="400">
</div>

# Sendoria - Discord Chat Relay

Chat between FFXI and Discord seamlessly!

📺 **[Watch the Video Setup Guide](https://youtu.be/bHziEsnsxG4)**

## Quick Setup

### 1. Install the Addon
- Copy `sendoria` folder to your Windower/addons folder.

### 2. Create Discord Server & Channels
- **Create a Discord server** (if you don't have one):
  - Click the + button in Discord → "Create My Own"
- **Create channels** for the chat types you want:
  - Right-click your server → Create Channel
  - Suggested channel names:
    - `#tells` - For private messages
    - `#party` - For party chat
    - `#linkshell-1` - For LS1 chat
    - `#linkshell-2` - For LS2 chat
    - `#say` - For local chat
    - `#shout` - For shouts
    - `#yell` - For yells
    - `#unity` - For unity chat

### 3. Set Up Discord Bot
- Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
- **Enable Message Content Intent**: Sidebar → Bot → Privileged Gateway Intents → Toggle ON "Message Content Intent"
- Make sure the bot is set to "Public Bot" in the Bot tab! *This will still only allow it to be in servers you invite it to.*
- Copy the bot token to `sendoria_config.txt`
- **Invite bot to your server**: Sidebar → OAuth2 → URL Generator → Select "bot" which will enable a drop down menu → Drop down menu → Select permissions: 
    - "Send Messages"
    - "Read Message History"
    - "Manage Messages"
    - "Add Reactions"

**Scroll down to "generated URL" → Copy URL and open it in a web browser. Invite the bot to your created server.**

### 4. Configure Channels (sendoria_config.txt)
- Enable Developer Options: Discord Settings → Advanced → Developer Mode
- Right-click each channel → Copy ID
- Add channel IDs to config file

### 5. Run the Bot
**Option A: Automatic (Recommended)**
- Enable autostart: `//send autostart on` in FFXI
- The bot will automatically start/stop with the addon

**Option B: Manual**
- Double-click `SendoriaBot.exe` (accept the Windows security warning)
- Keep it running for as long as you want to use the relay

### 6. Enable Relay in FFXI
Run these commands to start relaying:
- `//lua l sendoria` - Load the addon
- `//send autostart on` - Enable automatic bot management (recommended)
- `//send relay on` - Enable relay mode
- `//send tell on` - Enable tell relay
- `//send outgoing on` - Show your character's own sent messages (optional)
- `//send party on` - Enable party relay (optional)
- `//send ls1 on` - Enable linkshell relay (optional)

**Note**: With autostart enabled, the Discord bot will automatically start when you load the addon and stop when you unload it. You can still manually control the bot with `//send stop` or by running the executable directly.

## How to Use

**FFXI → Discord**: Just chat normally in game  
**Discord → FFXI**: Type in Discord channels  
**Tells**: `/tell PlayerName message` in Discord

## FFXI Commands
- `//send help` - Show commands
- `//send autostart on/off` - Enable/disable automatic bot start/stop
- `//send relay on/off` - Enable/disable relay mode
- `//send party on/off` - Enable/disable party chat relay
- `//send ls1 on/off` - Enable/disable linkshell relay
- `//send tell on/off` - Enable/disable tell relay
- `//send stop` - Manually stop the Discord bot
- `//send status` - Show current settings status

## Troubleshooting
- Make sure bot token is correct
- Check channel IDs are valid
- Verify relay is enabled: `//send relay on`
- Check specific chat types are enabled: `//send status`
- Bot needs Message Content Intent enabled in Discord Developer Portal
- **Autostart Issues**: 
  - Ensure `SendoriaBot.exe` or `SendoriaBot_Silent.exe` is in the addon folder
  - Check autostart status: `//send autostart` 
  - Try manual start if autostart fails: Double-click `SendoriaBot.exe`

---
Ready to go! Your chats now sync between FFXI and Discord. 🎮💬