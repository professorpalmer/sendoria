--[[
* Runs the real addon under LuaJIT with a minimal Windower stub.
* Usage (cwd = the sendoria addon folder):
*   luajit driver.lua <folder/> <script>
* Script lines:
*   login <Name>
*   chat <mode> <sender> <hex text>
*   speech <mode> <hex text>        outgoing 0x0B5
*   tell <target> <hex text>        outgoing 0x0B6
*   ticks <n>
*   cmd <word> [args...]
* Prints "SEND <hex command>" for each windower.send_command and
* "CHAT <text>" for each windower.add_to_chat.
--]]

local folder, script_path = arg[1], arg[2]

local function unhex(s)
    return (s:gsub('%x%x', function(h) return string.char(tonumber(h, 16)) end))
end

local function hex(s)
    return (s:gsub('.', function(c) return string.format('%02X', c:byte()) end))
end

_addon = {}
local events, scheduled, player = {}, {}, nil
local clock = 1700000000

os.time = function() return math.floor(clock) end

windower = {
    addon_path = folder,
    register_event = function(name, fn) events[name] = fn end,
    add_to_chat = function(_, text) print('CHAT ' .. text) end,
    send_command = function(command) print('SEND ' .. hex(command)) end,
    convert_auto_trans = function(text) return text end,
    ffxi = {
        get_info = function() return { logged_in = player ~= nil } end,
        get_player = function() return player and { name = player } or nil end,
    },
}

coroutine.schedule = function(fn, delay)
    scheduled[#scheduled + 1] = fn
end

package.preload['config'] = function()
    return {
        load = function(defaults)
            local t = {}
            for k, v in pairs(defaults) do t[k] = v end
            return t
        end,
        save = function() end,
    }
end

dofile('sendoria.lua')

local function run_ticks(n)
    for _ = 1, n do
        clock = clock + 0.25
        local due = scheduled
        scheduled = {}
        for _, fn in ipairs(due) do fn() end
    end
end

local function packet(id, body)
    return string.char(id % 256, 0, 0, 0) .. body
end

for line in io.lines(script_path) do
    local words = {}
    for w in line:gmatch('%S+') do words[#words + 1] = w end
    local op = words[1]
    if op == 'login' then
        player = words[2]
        events['login'](words[2])
    elseif op == 'chat' then
        events['chat message'](unhex(words[4] or ''), words[3], tonumber(words[2]), false)
    elseif op == 'speech' then
        local body = string.char(tonumber(words[2]), 0) .. unhex(words[3]) .. '\0'
        local data = packet(0xB5, body)
        events['outgoing chunk'](0x0B5, data, data, false, false)
    elseif op == 'tell' then
        local name = words[2] .. string.rep('\0', 15 - #words[2])
        local data = packet(0xB6, string.char(0, 0) .. name .. unhex(words[3]) .. '\0')
        events['outgoing chunk'](0x0B6, data, data, false, false)
    elseif op == 'ticks' then
        run_ticks(tonumber(words[2]))
    elseif op == 'cmd' then
        events['addon command'](words[2], select(3, unpack(words)))
    end
end
