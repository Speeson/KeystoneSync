local ADDON_NAME = "KeystoneSync"
local PREFIX = "[KeystoneSync]"

-- Region hardcodeada. Cambiar a "us" si el servidor no es EU.
local REGION = "eu"
local MAX_LEVEL = 90

local frame = CreateFrame("Frame")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_LOGOUT")
frame:RegisterEvent("CHALLENGE_MODE_COMPLETED")
frame:RegisterEvent("BAG_UPDATE_DELAYED")

local function GetCharacterKey()
    local character = UnitName("player")
    local realm = GetRealmName()
    return realm .. "-" .. character
end

local function SaveCurrentKeystone(reason)
    if UnitLevel("player") < MAX_LEVEL then return end

    KeystoneSyncDB = KeystoneSyncDB or {}

    local character = UnitName("player")
    local realm = GetRealmName()
    local key = GetCharacterKey()

    local level = C_MythicPlus.GetOwnedKeystoneLevel()
    local challengeMapId = C_MythicPlus.GetOwnedKeystoneChallengeMapID()
    local mapId = C_MythicPlus.GetOwnedKeystoneMapID()
    local hasKeystone = (level ~= nil and level > 0)

    local dungeonName = nil
    if challengeMapId then
        local name = C_ChallengeMode.GetMapUIInfo(challengeMapId)
        if name and name ~= "" then
            dungeonName = name
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
        C_Timer.After(5, function()
            SaveCurrentKeystone("PLAYER_LOGIN_5S")
        end)

    elseif event == "BAG_UPDATE_DELAYED" then
        -- Detecta cuando WoW coloca una piedra nueva en el bag (ej: reset semanal)
        -- Solo guarda si el nivel o la mazmorra cambió respecto a lo guardado
        local key = GetCharacterKey()
        local saved = KeystoneSyncDB and KeystoneSyncDB[key]
        local currentLevel = C_MythicPlus.GetOwnedKeystoneLevel()
        local currentMapId = C_MythicPlus.GetOwnedKeystoneChallengeMapID()
        local savedLevel = saved and saved.keystoneLevel
        local savedMapId = saved and saved.keystoneChallengeMapId
        if currentLevel ~= savedLevel or currentMapId ~= savedMapId then
            SaveCurrentKeystone("BAG_UPDATE")
        end

    elseif event == "CHALLENGE_MODE_COMPLETED" then
        C_Timer.After(5, function()
            SaveCurrentKeystone("CHALLENGE_MODE_COMPLETED_5S")
        end)
        C_Timer.After(10, function()
            SaveCurrentKeystone("CHALLENGE_MODE_COMPLETED_10S")
        end)
        C_Timer.After(20, function()
            SaveCurrentKeystone("CHALLENGE_MODE_COMPLETED_20S")
        end)
    end
end)

SLASH_KEYSTONESYNC1 = "/ksync"
SlashCmdList["KEYSTONESYNC"] = function()
    SaveCurrentKeystone("MANUAL_COMMAND")
    PrintCurrentKeystone()
end
