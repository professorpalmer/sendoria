--[[
* Sendoria - two-way chat relay between FFXI and Discord.
* Author: Palmer (Zodiarchy @ Asura)
*
* The addon writes chat to sendoria_<Character>.out and types what the
* Discord bot puts in sendoria_<Character>.in. See lib/ipc.lua.
--]]

_addon.name     = 'Sendoria'
_addon.author   = 'Palmer (Zodiarchy @ Asura)'
_addon.version  = '3.0.0'
_addon.desc     = 'Two-way chat relay between FFXI and Discord.'
_addon.commands = { 'sendoria', 'sn' }

local Config = require('lib/config')
local Chat = require('lib/chat')
local Ipc = require('lib/ipc')
local Commands = require('lib/commands')

local settings = Config.load()
local folder = windower.addon_path

local TICK = 0.25              -- seconds per loop tick
local SEND_GAP_TICKS = 5       -- spacing between lines typed for Discord
local INBOX_TICKS = 2
local HEARTBEAT_TICKS = 20
local STALE_SECONDS = 60       -- Discord lines older than this are not typed
local BOT_GRACE_TICKS = 120    -- warn once if no bot after this long

local ipc = nil                -- Ipc for the logged-in character
local send_queue = {}
local tick = 0
local last_send_tick = -SEND_GAP_TICKS
local bot_warned = false
local start_bot

local function current_name()
    local info = windower.ffxi.get_info()
    if not (info and info.logged_in) then
        return nil
    end
    local player = windower.ffxi.get_player()
    return player and player.name or nil
end

local function switch_character(name)
    if ipc and ipc.char == name then
        return
    end
    if ipc then
        ipc:flush()
        ipc:clear_heartbeat()
    end
    ipc = name and Ipc.new(folder, name) or nil
    send_queue = {}
    if ipc then
        ipc:heartbeat(os.time(), _addon.version)
        if settings.auto_start_bot then
            -- On every login: an autostarted bot exits while nobody is logged in.
            coroutine.schedule(function() start_bot(false) end, 2)
        end
    end
end

local function relay(chat_type, sender, target, text)
    if ipc and Config.relays(settings, chat_type) then
        ipc:message(os.time(), chat_type, sender, target, windower.convert_auto_trans(text) or text)
    end
end

--[[ Game -> Discord ]]

windower.register_event('chat message', function(message, sender, mode)
    local chat_type = Chat.incoming_modes[mode]
    if not chat_type or not ipc or sender == ipc.char then
        return
    end
    relay(chat_type, sender, '', message)
end)

windower.register_event('outgoing chunk', function(id, original, modified, injected, blocked)
    if blocked or not ipc or not settings.monitor_outgoing then
        return
    end
    local chat_type, target, text
    if id == 0x0B5 then
        chat_type, text = Chat.parse_speech(modified)
        target = ''
    elseif id == 0x0B6 then
        chat_type = 'Tell'
        target, text = Chat.parse_tell(modified)
    end
    if not chat_type or text == '' then
        return
    end
    local now = os.time()
    if Chat.is_repeat(chat_type .. '\0' .. target .. '\0' .. text, now) or Chat.take_echo(chat_type, text, now) then
        return
    end
    relay(chat_type, ipc.char, target, text)
end)

--[[ Discord -> game ]]

local function read_inbox()
    local now = os.time()
    for _, request in ipairs(ipc:take_inbox()) do
        if now - request.epoch > STALE_SECONDS then
            ipc:ack(now, request.id, 'stale')
        else
            local command, text = Chat.build_command(request.chat_type, request.target, request.text)
            if command then
                send_queue[#send_queue + 1] = { id = request.id, chat_type = request.chat_type, command = command, text = text }
            else
                ipc:ack(now, request.id, text)
            end
        end
    end
end

local function send_next()
    local item = table.remove(send_queue, 1)
    local now = os.time()
    Chat.mark_echo(item.chat_type, item.text, now)
    windower.send_command(item.command)
    ipc:ack(now, item.id, 'ok')
    last_send_tick = tick
end

--[[ Bot process ]]

local function bot_status()
    return Ipc.bot_status(folder, os.time())
end

function start_bot(verbose)
    local status = bot_status()
    if status and status.online then
        if verbose then
            Commands.say('The bot is already running.')
        end
        return
    end
    for _, exe in ipairs({ 'SendoriaBot_Silent.exe', 'SendoriaBot.exe' }) do
        local file = io.open(folder .. exe, 'rb')
        if file then
            file:close()
            -- --auto: the bot exits on its own when no character is online.
            os.execute('cd /d "' .. folder .. '" && start "" "' .. folder .. exe .. '" --auto')
            Commands.say('Starting the Discord bot.')
            return
        end
    end
    Commands.say('SendoriaBot.exe is not in ' .. folder .. '. Get it from the release zip.')
end

local function check_bot()
    if bot_warned or tick < BOT_GRACE_TICKS then
        return
    end
    local status = bot_status()
    if not (status and status.online) then
        bot_warned = true
        Commands.say('The Discord bot is not running. Use //sn start, or //sn autostart on.')
    elseif status.protocol ~= Ipc.PROTOCOL then
        bot_warned = true
        Commands.say('Bot version ' .. status.version .. ' does not match addon ' .. _addon.version .. '. Update both.')
    end
end

--[[ Main loop ]]

local function loop()
    tick = tick + 1
    if tick % HEARTBEAT_TICKS == 0 then
        switch_character(current_name())
        if ipc then
            ipc:heartbeat(os.time(), _addon.version)
            check_bot()
        end
    end
    if ipc then
        if tick % INBOX_TICKS == 0 then
            read_inbox()
        end
        if #send_queue > 0 and tick - last_send_tick >= SEND_GAP_TICKS then
            send_next()
        end
        ipc:flush()
    end
    coroutine.schedule(loop, TICK)
end

windower.register_event('login', function(name)
    switch_character(name)
end)

windower.register_event('logout', function()
    switch_character(nil)
end)

windower.register_event('unload', function()
    switch_character(nil)
end)

windower.register_event('addon command', function(command, ...)
    Commands.handle(settings, {
        protocol = Ipc.PROTOCOL,
        char = function() return ipc and ipc.char end,
        bot_status = bot_status,
        start_bot = start_bot,
        stop_bot = function() return Ipc.request_stop(folder) end,
        test = function(chat_type)
            if not ipc then
                return false
            end
            local target = chat_type == 'Tell' and ipc.char or ''
            ipc:message(os.time(), chat_type, ipc.char, target, 'Sendoria test line')
            return true
        end,
    }, command, { ... })
end)

switch_character(current_name())
coroutine.schedule(loop, TICK)
