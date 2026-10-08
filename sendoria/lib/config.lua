--[[
* Sendoria settings. Windower stores them in data/settings.xml.
* Every chat type relays by default. The bot config decides which types
* have a Discord channel, so these switches are only for muting.
--]]

local config = require('config')

local Config = {}

Config.defaults = {
    enabled = true,
    auto_start_bot = false,
    monitor_tells = true,
    monitor_party = true,
    monitor_linkshell1 = true,
    monitor_linkshell2 = true,
    monitor_say = true,
    monitor_shout = true,
    monitor_yell = true,
    monitor_unity = true,
    monitor_outgoing = true,
}

-- Relay chat type -> setting
Config.type_settings = {
    Tell = 'monitor_tells', Party = 'monitor_party',
    Linkshell1 = 'monitor_linkshell1', Linkshell2 = 'monitor_linkshell2',
    Say = 'monitor_say', Shout = 'monitor_shout', Yell = 'monitor_yell', Unity = 'monitor_unity',
}

-- Command word -> setting
Config.aliases = {
    tell = 'monitor_tells', tells = 'monitor_tells', t = 'monitor_tells',
    party = 'monitor_party', p = 'monitor_party',
    linkshell = 'monitor_linkshell1', linkshell1 = 'monitor_linkshell1', ls = 'monitor_linkshell1',
    ls1 = 'monitor_linkshell1', l = 'monitor_linkshell1',
    linkshell2 = 'monitor_linkshell2', ls2 = 'monitor_linkshell2', l2 = 'monitor_linkshell2',
    say = 'monitor_say', s = 'monitor_say',
    shout = 'monitor_shout', sh = 'monitor_shout',
    yell = 'monitor_yell', y = 'monitor_yell',
    unity = 'monitor_unity', u = 'monitor_unity',
    outgoing = 'monitor_outgoing', own = 'monitor_outgoing',
}

function Config.load()
    return config.load(Config.defaults)
end

function Config.save(settings)
    config.save(settings)
end

function Config.relays(settings, chat_type)
    local key = Config.type_settings[chat_type]
    return settings.enabled and key ~= nil and settings[key]
end

return Config
