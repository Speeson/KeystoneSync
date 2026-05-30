local ADDON_NAME = "KeystoneSync"
local PREFIX = "[KeystoneSync]"

-- Region hardcodeada. Cambiar a "us" si el servidor no es EU.
local REGION = "eu"
local MAX_LEVEL = 90

local frame = CreateFrame("Frame")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_LOGOUT")

local function GetCharacterKey()
    local character = UnitName("player")
    local realm = GetRealmName()
    return realm .. "-" .. character
end

local function ParseKeystoneLink(link)
    if not link then return nil, nil end

    local challengeMapId, level = link:match("Hkeystone:%d+:(%d+):(%d+)")
    if challengeMapId and level then
        return tonumber(level), tonumber(challengeMapId)
    end

    local itemString = link:match("Hitem:([^|]+)")
    if not itemString then return nil, nil end

    local fields = {}
    for value in itemString:gmatch("([^:]+)") do
        table.insert(fields, value)
    end

    local itemId = tonumber(fields[1])
    if itemId ~= 180653 and itemId ~= 138019 then return nil, nil end

    for i = 2, #fields - 1 do
        local modifierType = tonumber(fields[i])
        if modifierType == 17 then
            challengeMapId = tonumber(fields[i + 1])
        elseif modifierType == 18 then
            level = tonumber(fields[i + 1])
        end
    end

    return level, challengeMapId
end

local function GetKeystoneFromBags()
    if not C_Container then return nil, nil end

    for bag = 0, NUM_BAG_SLOTS do
        local slots = C_Container.GetContainerNumSlots(bag) or 0
        for slot = 1, slots do
            local link = C_Container.GetContainerItemLink(bag, slot)
            local level, challengeMapId = ParseKeystoneLink(link)
            if level or challengeMapId then
                return level, challengeMapId
            end
        end
    end

    return nil, nil
end

local function SaveCurrentKeystone(reason)
    if UnitLevel("player") < MAX_LEVEL then return end

    KeystoneSyncDB = KeystoneSyncDB or {}

    local character = UnitName("player")
    local realm = GetRealmName()
    local key = GetCharacterKey()
    local prev = KeystoneSyncDB and KeystoneSyncDB[key]

    local level = C_MythicPlus.GetOwnedKeystoneLevel()
    local challengeMapId = C_MythicPlus.GetOwnedKeystoneChallengeMapID()
    local mapId = C_MythicPlus.GetOwnedKeystoneMapID()

    if not level or not challengeMapId then
        local bagLevel, bagChallengeMapId = GetKeystoneFromBags()
        level = level or bagLevel
        challengeMapId = challengeMapId or bagChallengeMapId
    end

    local hasKeystone = (level ~= nil and level > 0)

    if not hasKeystone and prev and prev.hasKeystone and prev.keystoneLevel then
        level = prev.keystoneLevel
        challengeMapId = prev.keystoneChallengeMapId
        mapId = prev.keystoneMapId
        hasKeystone = true
    end

    local dungeonName = nil
    if challengeMapId then
        local name, resolvedMapId = C_ChallengeMode.GetMapUIInfo(challengeMapId)
        mapId = mapId or resolvedMapId
        if name and name ~= "" then
            dungeonName = name
        else
            -- GetMapUIInfo no disponible aun (datos no cargados en login)
            -- Si ya teniamos el nombre guardado para esta misma mazmorra, conservarlo
            if prev and prev.keystoneChallengeMapId == challengeMapId and prev.keystoneDungeon then
                dungeonName = prev.keystoneDungeon
            end
        end
    end

    KeystoneSyncDB[key] = KeystoneSyncDB[key] or {}
    KeystoneSyncDB[key].character = character
    KeystoneSyncDB[key].realm = realm
    KeystoneSyncDB[key].region = REGION
    KeystoneSyncDB[key].hasKeystone = hasKeystone
    KeystoneSyncDB[key].keystoneLevel = level
    KeystoneSyncDB[key].keystoneChallengeMapId = challengeMapId
    KeystoneSyncDB[key].keystoneMapId = mapId
    KeystoneSyncDB[key].keystoneDungeon = dungeonName
    KeystoneSyncDB[key].updatedAt = time()
    KeystoneSyncDB[key].updatedReason = reason
end

local function PrintCurrentKeystone()
    local key = GetCharacterKey()
    if not KeystoneSyncDB or not KeystoneSyncDB[key] then
        print(PREFIX .. " No hay datos guardados para este personaje.")
        return
    end

    local data = KeystoneSyncDB[key]
    if data.hasKeystone and data.keystoneLevel and data.keystoneLevel > 0 then
        local mapLabel = data.keystoneDungeon or (data.keystoneChallengeMapId and ("ID " .. data.keystoneChallengeMapId) or "mazmorra desconocida")
        print(PREFIX .. " Piedra actual guardada: " .. mapLabel .. " +" .. data.keystoneLevel)
    else
        print(PREFIX .. " No se ha detectado ninguna piedra actual para este personaje.")
    end
end

frame:SetScript("OnEvent", function(self, event)
    if event == "PLAYER_LOGOUT" then
        SaveCurrentKeystone("PLAYER_LOGOUT")
    elseif event == "PLAYER_LOGIN" then
        SaveCurrentKeystone("PLAYER_LOGIN")
    end
end)

SLASH_KEYSTONESYNC1 = "/ksync"
SlashCmdList["KEYSTONESYNC"] = function()
    SaveCurrentKeystone("MANUAL_COMMAND")
    PrintCurrentKeystone()
end
