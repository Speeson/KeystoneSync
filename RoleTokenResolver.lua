local _, KeystoneSync = ...
local Resolver = {}
KeystoneSync.RoleTokenResolver = Resolver

local ROLE_KEYS = { TANK = "tank", HEALER = "healer", DAMAGER = "dps" }

local function safeCall(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, value = pcall(fn, ...)
    if not ok then return nil end
    if type(issecretvalue) == "function" then
        local checked, secret = pcall(issecretvalue, value)
        if not checked or secret then return nil end
    end
    return value
end

function Resolver.GroupType()
    if safeCall(IsInRaid) == true then return "raid" end
    if safeCall(IsInGroup) == true then return "party" end
    return "solo"
end

function Resolver.Resolve()
    local result = {}
    local kind = Resolver.GroupType()
    if kind == "solo" then return result end

    local count = kind == "raid" and safeCall(GetNumGroupMembers) or safeCall(GetNumSubgroupMembers)
    if type(count) ~= "number" then return result end
    count = math.max(0, math.min(count, kind == "raid" and 40 or 4))

    local lists = { tank = {}, healer = {}, dps = {} }
    local mainTanks = {}
    for index = 1, count do
        local unit = kind .. index
        if safeCall(UnitExists, unit) == true and safeCall(UnitIsUnit, unit, "player") == false then
            local role = ROLE_KEYS[safeCall(UnitGroupRolesAssigned, unit)]
            if role then
                if kind == "raid" and role == "tank" and safeCall(GetPartyAssignment, "MAINTANK", unit) == true then
                    mainTanks[#mainTanks + 1] = unit
                else
                    local list = lists[role]
                    list[#list + 1] = unit
                end
            end
        end
    end

    if #mainTanks > 0 then
        local ordered = {}
        for _, unit in ipairs(mainTanks) do ordered[#ordered + 1] = unit end
        for _, unit in ipairs(lists.tank) do ordered[#ordered + 1] = unit end
        lists.tank = ordered
    end
    for role, list in pairs(lists) do
        for slot, unit in ipairs(list) do
            result[role .. slot] = unit
        end
    end
    return result
end
