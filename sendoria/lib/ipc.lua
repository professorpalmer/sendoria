--[[
* Sendoria file handoff with the Discord bot.
* Format: bot/sendoria_bot/protocol.py. Text fields are raw Shift-JIS bytes.
* The reader of a file consumes it by renaming it first.
--]]

local Ipc = {}
Ipc.__index = Ipc
Ipc.PROTOCOL = 3
Ipc.BOT_TIMEOUT = 20

local function field(value)
    return (tostring(value or ''):gsub('[\t\r\n]', ' '))
end

function Ipc.split(line)
    local fields, start = {}, 1
    while true do
        local tab = line:find('\t', start, true)
        if not tab then
            fields[#fields + 1] = line:sub(start)
            return fields
        end
        fields[#fields + 1] = line:sub(start, tab - 1)
        start = tab + 1
    end
end

function Ipc.parse_inbox(data)
    local requests = {}
    for line in data:gmatch('[^\n]+') do
        local f = Ipc.split((line:gsub('\r$', '')))
        local epoch = tonumber(f[2])
        if #f == 5 and epoch then
            requests[#requests + 1] = { id = f[1], epoch = epoch, chat_type = f[3], target = f[4], text = f[5] }
        end
    end
    return requests
end

function Ipc.new(folder, char)
    return setmetatable({ folder = folder, char = char, buffer = {} }, Ipc)
end

function Ipc:path(ext)
    return self.folder .. 'sendoria_' .. self.char .. '.' .. ext
end

function Ipc:message(epoch, chat_type, sender, target, text)
    self.buffer[#self.buffer + 1] = table.concat(
        { 'M', epoch, field(chat_type), field(sender), field(target), field(text) }, '\t') .. '\n'
end

function Ipc:ack(epoch, id, status)
    self.buffer[#self.buffer + 1] = table.concat({ 'A', epoch, field(id), field(status) }, '\t') .. '\n'
end

-- Append buffered records in one write. Keep them if the file is busy.
function Ipc:flush()
    if #self.buffer == 0 then
        return true
    end
    local file = io.open(self:path('out'), 'ab')
    if not file then
        return false
    end
    file:write(table.concat(self.buffer))
    file:close()
    self.buffer = {}
    return true
end

function Ipc:heartbeat(epoch, version)
    local file = io.open(self:path('hb'), 'wb')
    if file then
        file:write(table.concat({ Ipc.PROTOCOL, epoch, version }, '\t') .. '\n')
        file:close()
    end
end

function Ipc:clear_heartbeat()
    os.remove(self:path('hb'))
end

function Ipc:take_inbox()
    local taken = self:path('in.taking')
    local file = io.open(taken, 'rb')
    if not file then
        -- Fails while the bot has the file open. Try again on the next poll.
        if not os.rename(self:path('in'), taken) then
            return {}
        end
        file = io.open(taken, 'rb')
        if not file then
            return {}
        end
    end
    local data = file:read('*a') or ''
    file:close()
    os.remove(taken)
    return Ipc.parse_inbox(data)
end

-- Returns nil when no bot heartbeat file exists.
function Ipc.bot_status(folder, now)
    local file = io.open(folder .. 'sendoria_bot.hb', 'rb')
    if not file then
        return nil
    end
    local f = Ipc.split(((file:read('*a') or ''):gsub('%s+$', '')))
    file:close()
    local protocol, epoch = tonumber(f[1]), tonumber(f[2])
    if not (protocol and epoch) then
        return nil
    end
    return { protocol = protocol, version = f[3] or '?', online = now - epoch <= Ipc.BOT_TIMEOUT }
end

function Ipc.request_stop(folder)
    local file = io.open(folder .. 'sendoria_bot.stop', 'wb')
    if not file then
        return false
    end
    file:write('stop\n')
    file:close()
    return true
end

return Ipc
