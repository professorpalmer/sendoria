--[[
* Sendoria chat rules: packet parsing, game commands, echo and repeat guards.
* All text is raw Shift-JIS bytes. Shift-JIS trail bytes are 0x40 or higher,
* so the ASCII patterns below never match inside a Japanese character.
--]]

local Chat = {}

-- Chat mode in the 'chat message' event -> relay chat type.
Chat.incoming_modes = {
    [0] = 'Say', [1] = 'Shout', [3] = 'Tell', [4] = 'Party',
    [5] = 'Linkshell1', [26] = 'Yell', [27] = 'Linkshell2', [33] = 'Unity',
}

-- Mode byte of the outgoing speech packet 0x0B5 -> relay chat type.
Chat.outgoing_modes = {
    [0] = 'Say', [1] = 'Shout', [4] = 'Party', [5] = 'Linkshell1',
    [26] = 'Yell', [27] = 'Linkshell2', [33] = 'Unity',
}

Chat.commands = {
    Tell = '/tell', Party = '/p', Linkshell1 = '/l', Linkshell2 = '/l2',
    Say = '/say', Shout = '/sh', Yell = '/yell', Unity = '/unity',
}

local ECHO_SECONDS = 10
local REPEAT_SECONDS = 1

-- 0x0B5: mode at 0x04, text from 0x06. Returns chat_type, text or nil.
function Chat.parse_speech(data)
    local chat_type = Chat.outgoing_modes[data:byte(5)]
    if not chat_type then
        return nil
    end
    return chat_type, (data:sub(7):gsub('%z.*', ''))
end

-- 0x0B6: target name at 0x06 (15 bytes), text from 0x15.
function Chat.parse_tell(data)
    return (data:sub(7, 21):gsub('%z.*', '')), (data:sub(22):gsub('%z.*', ''))
end

-- Strip bytes that the game or Windower treat as syntax.
-- < > : <t> <me> <call> expansion. ; : Windower command separator. " : quoting.
function Chat.sanitize(text)
    return (text:gsub('[%z\1-\31<>;"]', ''):gsub('^%s+', ''):gsub('%s+$', ''))
end

-- Returns the Windower command, or nil and the refusal status.
function Chat.build_command(chat_type, target, text)
    local command = Chat.commands[chat_type]
    if not command then
        return nil, 'bad'
    end
    text = Chat.sanitize(text or '')
    if text == '' then
        return nil, 'bad'
    end
    if chat_type == 'Tell' then
        if not (target and target:match('^%a+$') and #target >= 3 and #target <= 15) then
            return nil, 'bad'
        end
        command = command .. ' ' .. target
    end
    return 'input ' .. command .. ' ' .. text, text
end

-- Messages this addon typed for Discord. The game shows them as our own
-- outgoing chat, and they must not go back to Discord.
Chat.echoes = {}

function Chat.mark_echo(chat_type, text, now)
    Chat.echoes[chat_type .. '\0' .. text] = now + ECHO_SECONDS
end

function Chat.take_echo(chat_type, text, now)
    local key = chat_type .. '\0' .. text
    local expires = Chat.echoes[key]
    for k, t in pairs(Chat.echoes) do
        if t < now then
            Chat.echoes[k] = nil
        end
    end
    if expires and expires >= now then
        Chat.echoes[key] = nil
        return true
    end
    return false
end

-- The client can report one outgoing packet more than once.
Chat.last_outgoing = { key = nil, time = 0 }

function Chat.is_repeat(key, now)
    local last = Chat.last_outgoing
    local repeated = last.key == key and now - last.time <= REPEAT_SECONDS
    last.key, last.time = key, now
    return repeated
end

return Chat
