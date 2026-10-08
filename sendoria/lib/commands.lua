--[[
* Sendoria //sn commands.
--]]

local Config = require('lib/config')

local Commands = {}

local function say(text)
    windower.add_to_chat(207, 'Sendoria: ' .. text)
end
Commands.say = say

local function on_off(word)
    if word == 'on' or word == 'true' or word == '1' then
        return true
    elseif word == 'off' or word == 'false' or word == '0' then
        return false
    end
    return nil
end

local function state(value)
    return value and 'ON' or 'off'
end

function Commands.help()
    say('Commands (//sn or //sendoria):')
    say('  status            relay, bot, and chat type state')
    say('  on | off          relay everything on or off')
    say('  <type> on|off     mute or unmute one type:')
    say('                    tell party ls1 ls2 say shout yell unity outgoing')
    say('  autostart on|off  start the bot with the addon')
    say('  start | stop      start or stop the Discord bot')
    say('  test [type]       send a test line to Discord (default: tell)')
    say('In Discord: type in a channel. Tells: /t Name text, /r text, or reply to a tell.')
end

function Commands.status(settings, ctx)
    say('Relay ' .. state(settings.enabled) .. ', character: ' .. (ctx.char() or 'not logged in'))
    local bot = ctx.bot_status()
    if not bot then
        say('Bot: not running')
    elseif not bot.online then
        say('Bot: not running (last seen version ' .. bot.version .. ')')
    elseif bot.protocol ~= ctx.protocol then
        say('Bot: version ' .. bot.version .. ' does not match this addon. Update both.')
    else
        say('Bot: online, version ' .. bot.version)
    end
    local types = {}
    for _, chat_type in ipairs({ 'Tell', 'Party', 'Linkshell1', 'Linkshell2', 'Say', 'Shout', 'Yell', 'Unity' }) do
        types[#types + 1] = chat_type .. ' ' .. state(settings[Config.type_settings[chat_type]])
    end
    say(table.concat(types, ', '))
    say('Own messages ' .. state(settings.monitor_outgoing) .. ', autostart ' .. state(settings.auto_start_bot))
end

function Commands.handle(settings, ctx, command, args)
    command = (command or ''):lower()
    local switch = on_off((args[1] or ''):lower())

    if command == '' or command == 'status' then
        Commands.status(settings, ctx)
    elseif command == 'help' then
        Commands.help()
    elseif command == 'on' or command == 'off' or command == 'toggle' or command == 'relay' then
        local value = on_off(command)
        if command == 'toggle' then
            value = not settings.enabled
        elseif command == 'relay' then
            value = switch
        end
        if value == nil then
            say('Usage: //sn on | off')
            return
        end
        settings.enabled = value
        Config.save(settings)
        say('Relay ' .. state(value))
    elseif Config.aliases[command] then
        if switch == nil then
            say('Usage: //sn ' .. command .. ' on|off')
            return
        end
        settings[Config.aliases[command]] = switch
        Config.save(settings)
        say(command .. ' ' .. state(switch))
    elseif command == 'autostart' then
        if switch ~= nil then
            settings.auto_start_bot = switch
            Config.save(settings)
        end
        say('Autostart ' .. state(settings.auto_start_bot))
    elseif command == 'start' then
        ctx.start_bot(true)
    elseif command == 'stop' then
        say(ctx.stop_bot() and 'Stop signal sent to the bot.' or 'Could not write the stop signal.')
    elseif command == 'test' then
        local setting = Config.aliases[(args[1] or 'tell'):lower()]
        local chat_type
        for t, s in pairs(Config.type_settings) do
            if s == setting then
                chat_type = t
            end
        end
        if not chat_type then
            say('Usage: //sn test [tell|party|ls1|ls2|say|shout|yell|unity]')
            return
        end
        say(ctx.test(chat_type) and ('Test line sent to the ' .. chat_type .. ' channel.') or 'Log in first.')
    else
        say('Unknown command. //sn help lists them.')
    end
end

return Commands
