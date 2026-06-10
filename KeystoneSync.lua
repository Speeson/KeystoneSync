local ADDON_NAME = "KeystoneSync"
local PREFIX = "[KeystoneSync]"

-- Region hardcodeada. Cambiar a "us" si el servidor no es EU.
local REGION = "eu"
local MAX_LEVEL = 90

local CURRENCIES = {
    { key = "adventurerDawncrest", id = 3383 },
    { key = "veteranDawncrest", id = 3341 },
    { key = "championDawncrest", id = 3343 },
    { key = "heroDawncrest", id = 3345 },
    { key = "mythDawncrest", id = 3347 },
    { key = "dawnlightManaflux", id = 3378 },
    { key = "radiantSparkDust", id = 3212 },
    { key = "cofferKeyShards", id = 3310 },
    { key = "restoredCofferKey", id = 3028 },
    { key = "nebulousVoidcore", id = 3418 },
}

local SPARK_OF_RADIANCE_ITEM_ID = 232875
local RADIANT_SPARK_DUST_CURRENCY_ID = 3212

local frame = CreateFrame("Frame")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_LOGOUT")
frame:RegisterEvent("WEEKLY_REWARDS_UPDATE")
frame:RegisterEvent("CHALLENGE_MODE_MAPS_UPDATE")
frame:RegisterEvent("MYTHIC_PLUS_NEW_WEEKLY_RECORD")
frame:RegisterEvent("CURRENCY_DISPLAY_UPDATE")
frame:RegisterEvent("QUEST_LOG_UPDATE")
frame:RegisterEvent("BAG_UPDATE_DELAYED")
frame:RegisterEvent("CHALLENGE_MODE_COMPLETED")

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

local function CountItemInBags(itemID)
    local total = 0
    if not C_Container then return total end

    for bag = 0, NUM_BAG_SLOTS do
        local slots = C_Container.GetContainerNumSlots(bag) or 0
        for slot = 1, slots do
            local info = C_Container.GetContainerItemInfo(bag, slot)
            if info and info.itemID == itemID then
                total = total + (info.stackCount or 0)
            end
        end
    end

    return total
end

local function GetCurrentKeystone(prev)
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

    return {
        hasKeystone = hasKeystone,
        level = level,
        challengeMapId = challengeMapId,
        mapId = mapId,
        dungeonName = dungeonName,
    }
end

local function CountCompletedQuests(ids)
    local count = 0
    local completed = {}

    for _, questID in ipairs(ids) do
        if C_QuestLog.IsQuestFlaggedCompleted(questID) then
            count = count + 1
            table.insert(completed, questID)
        end
    end

    return count, completed
end

local function BuildRange(startId, endId, step)
    local ids = {}
    for questID = startId, endId, step or 1 do
        table.insert(ids, questID)
    end
    return ids
end

local function AppendRange(target, startId, endId, step)
    for questID = startId, endId, step or 1 do
        table.insert(target, questID)
    end
end

local function GetTexturePath(fileDataID)
    if not fileDataID or not C_Texture or not C_Texture.GetFilenameFromFileDataID then return nil end

    local ok, path = pcall(C_Texture.GetFilenameFromFileDataID, fileDataID)
    if ok and path and path ~= "" then
        return path
    end

    return nil
end

local function GetPreyHunts()
    local normal = BuildRange(91095, 91124)
    local hard = {}
    local nightmare = {}

    AppendRange(hard, 91210, 91240, 2)
    AppendRange(hard, 91242, 91255)

    AppendRange(nightmare, 91211, 91241, 2)
    AppendRange(nightmare, 91256, 91269)

    local normalCount, normalCompleted = CountCompletedQuests(normal)
    local hardCount, hardCompleted = CountCompletedQuests(hard)
    local nightmareCount, nightmareCompleted = CountCompletedQuests(nightmare)

    return {
        normal = { count = normalCount, completedQuestIDs = normalCompleted },
        hard = { count = hardCount, completedQuestIDs = hardCompleted },
        nightmare = { count = nightmareCount, completedQuestIDs = nightmareCompleted },
    }
end

local function GetCurrencyData()
    local result = {}

    for _, currencyDef in ipairs(CURRENCIES) do
        local info = C_CurrencyInfo.GetCurrencyInfo(currencyDef.id)
        if info then
            local isComplete = false
            if currencyDef.key == "nebulousVoidcore" and info.maxQuantity and info.maxQuantity > 0 then
                isComplete = (info.totalEarned or info.quantity or 0) >= info.maxQuantity
            end

            result[currencyDef.key] = {
                id = currencyDef.id,
                name = info.name,
                quantity = info.quantity or 0,
                maxQuantity = info.maxQuantity or 0,
                maxWeeklyQuantity = info.maxWeeklyQuantity or 0,
                totalEarned = info.totalEarned or 0,
                trackedQuantity = info.trackedQuantity or 0,
                quantityEarnedThisWeek = info.quantityEarnedThisWeek or 0,
                discovered = info.discovered == true,
                quality = info.quality,
                iconFileID = info.iconFileID,
                iconPath = GetTexturePath(info.iconFileID),
                isWeeklyComplete = isComplete,
                displayColor = isComplete and "red" or nil,
            }
        end
    end

    local sparkDust = result.radiantSparkDust
    local sparkInventoryCount = CountItemInBags(SPARK_OF_RADIANCE_ITEM_ID)
    local sparkTotalCount = C_Item.GetItemCount(SPARK_OF_RADIANCE_ITEM_ID, true) or 0
    local sparkItemCount = math.max(sparkInventoryCount, sparkTotalCount)

    result.sparksOfRadiance = {
        itemID = SPARK_OF_RADIANCE_ITEM_ID,
        currencyID = RADIANT_SPARK_DUST_CURRENCY_ID,
        quantity = sparkItemCount,
        itemQuantity = sparkItemCount,
        inventoryQuantity = sparkInventoryCount,
        totalItemQuantity = sparkTotalCount,
        dustQuantity = sparkDust and (sparkDust.quantity or sparkDust.trackedQuantity or sparkDust.totalEarned) or 0,
        dustMaxQuantity = sparkDust and sparkDust.maxQuantity or 0,
        dustTotalEarned = sparkDust and sparkDust.totalEarned or 0,
        dustTrackedQuantity = sparkDust and sparkDust.trackedQuantity or 0,
        iconFileID = C_Item.GetItemIconByID(SPARK_OF_RADIANCE_ITEM_ID),
        iconPath = GetTexturePath(C_Item.GetItemIconByID(SPARK_OF_RADIANCE_ITEM_ID)),
    }

    return result
end

local function GetVaultData()
    local result = {
        hasAvailableRewards = C_WeeklyRewards.HasAvailableRewards() == true,
        raid = { unlocked = 0, slots = {} },
        dungeons = { unlocked = 0, slots = {} },
        world = { unlocked = 0, slots = {} },
    }

    local typeMap = {
        [Enum.WeeklyRewardChestThresholdType.Raid] = "raid",
        [Enum.WeeklyRewardChestThresholdType.Activities] = "dungeons",
        [Enum.WeeklyRewardChestThresholdType.World] = "world",
    }

    local activities = C_WeeklyRewards.GetActivities()
    if not activities then return result end

    for _, activity in ipairs(activities) do
        local bucketName = typeMap[activity.type]
        if bucketName then
            local unlocked = activity.progress and activity.threshold and activity.progress >= activity.threshold
            local slot = {
                id = activity.id,
                index = activity.index,
                type = activity.type,
                level = activity.level,
                progress = activity.progress or 0,
                threshold = activity.threshold or 0,
                activityTierID = activity.activityTierID,
                unlocked = unlocked == true,
            }

            table.insert(result[bucketName].slots, slot)
            if unlocked then
                result[bucketName].unlocked = result[bucketName].unlocked + 1
            end
        end
    end

    local heroic, mythic, mythicPlus = C_WeeklyRewards.GetNumCompletedDungeonRuns()
    result.dungeons.completedRuns = {
        heroic = heroic or 0,
        mythic = mythic or 0,
        mythicPlus = mythicPlus or 0,
    }

    return result
end

local function GetTimedUpgradeLevel(durationSec, timeLimit)
    if not durationSec or not timeLimit or timeLimit <= 0 then return nil end
    if durationSec <= timeLimit * 0.6 then return 3 end
    if durationSec <= timeLimit * 0.8 then return 2 end
    if durationSec <= timeLimit then return 1 end
    return 0
end

local function CopyRunInfo(run)
    if not run then return nil end

    return {
        level = run.level or run.keystoneLevel,
        durationSec = run.durationSec or run.durationSeconds,
        mapScore = run.mapScore,
        completed = run.completed,
        finishedSuccess = run.finishedSuccess,
    }
end

local function CopyAffixScores(affixScores)
    local result = {}
    if not affixScores then return result end

    for _, affixScore in ipairs(affixScores) do
        table.insert(result, {
            name = affixScore.name,
            score = affixScore.score or 0,
            level = affixScore.level or 0,
            durationSec = affixScore.durationSec or 0,
            overTime = affixScore.overTime == true,
        })
    end

    return result
end

local function GetBestAffixScore(affixScores)
    local best = nil
    if not affixScores then return nil end

    for _, affixScore in ipairs(affixScores) do
        if not best or (affixScore.score or 0) > (best.score or 0) then
            best = affixScore
        end
    end

    return best
end

local function GetRunChallengeMapId(run)
    if not run then return nil end
    return run.challengeModeID or run.challengeMapID or run.mapChallengeModeID or run.challengeMapId or run.mapId
end

local function GetRunScore(run)
    if not run then return nil end
    return run.mapScore or run.score or run.bestRunScore or run.overallScore
end

local function GetMythicPlusSeason()
    local result = {
        rating = 0,
        dungeons = {},
    }

    local ratingSummary = C_PlayerInfo.GetPlayerMythicPlusRatingSummary("player")
    if ratingSummary and ratingSummary.currentSeasonScore then
        result.rating = ratingSummary.currentSeasonScore
    end

    local maps = C_ChallengeMode.GetMapTable()
    if not maps then return result end

    for _, challengeMapId in ipairs(maps) do
        local name, _, timeLimit, texture = C_ChallengeMode.GetMapUIInfo(challengeMapId)
        local bestTimedRun, bestNotTimedRun = C_MythicPlus.GetSeasonBestForMap(challengeMapId)
        local affixScores, bestOverAllScore = C_MythicPlus.GetSeasonBestAffixScoreInfoForMap(challengeMapId)
        local bestAffixScore = GetBestAffixScore(affixScores)
        local summaryRun = nil

        if ratingSummary and ratingSummary.runs then
            for _, run in ipairs(ratingSummary.runs) do
                if GetRunChallengeMapId(run) == challengeMapId then
                    summaryRun = run
                    break
                end
            end
        end

        local level = 0
        local timed = false
        local durationSec = nil
        local upgradeLevel = 0

        if bestAffixScore and bestAffixScore.level and bestAffixScore.level > 0 then
            level = bestAffixScore.level
            durationSec = bestAffixScore.durationSec
            timed = not bestAffixScore.overTime
            upgradeLevel = timed and GetTimedUpgradeLevel(durationSec, timeLimit) or 0
        elseif bestTimedRun then
            level = bestTimedRun.level or bestTimedRun.keystoneLevel or level
            durationSec = bestTimedRun.durationSec or bestTimedRun.durationSeconds
            timed = true
            upgradeLevel = GetTimedUpgradeLevel(durationSec, timeLimit) or 0
        elseif summaryRun then
            level = summaryRun.bestRunLevel or level
            timed = summaryRun.finishedSuccess == true
        elseif bestNotTimedRun then
            level = bestNotTimedRun.level or bestNotTimedRun.keystoneLevel or level
        end

        table.insert(result.dungeons, {
            challengeMapId = challengeMapId,
            name = name,
            texture = texture,
            texturePath = GetTexturePath(texture),
            timeLimit = timeLimit,
            level = level or 0,
            timed = timed,
            upgradeLevel = upgradeLevel,
            rating = (bestOverAllScore and bestOverAllScore > 0 and bestOverAllScore) or GetRunScore(summaryRun) or 0,
            bestOverAllScore = bestOverAllScore or 0,
            bestTimedRun = CopyRunInfo(bestTimedRun),
            bestNotTimedRun = CopyRunInfo(bestNotTimedRun),
            bestAffixScore = bestAffixScore and {
                name = bestAffixScore.name,
                score = bestAffixScore.score or 0,
                level = bestAffixScore.level or 0,
                durationSec = bestAffixScore.durationSec or 0,
                overTime = bestAffixScore.overTime == true,
            } or nil,
            affixScores = CopyAffixScores(affixScores),
        })
    end

    return result
end

local function GetItemLevelData()
    local avgItemLevel, avgItemLevelEquipped = GetAverageItemLevel()

    return {
        ilvl = avgItemLevel and math.floor(avgItemLevel + 0.5) or nil,
        equippedIlvl = avgItemLevelEquipped and math.floor(avgItemLevelEquipped + 0.5) or nil,
    }
end

local function SaveCharacterData(reason)
    if UnitLevel("player") < MAX_LEVEL then return end

    KeystoneSyncDB = KeystoneSyncDB or {}

    local character = UnitName("player")
    local realm = GetRealmName()
    local key = GetCharacterKey()
    local prev = KeystoneSyncDB and KeystoneSyncDB[key]
    local keystone = GetCurrentKeystone(prev)
    local itemLevel = GetItemLevelData()

    KeystoneSyncDB[key] = KeystoneSyncDB[key] or {}
    KeystoneSyncDB[key].character = character
    KeystoneSyncDB[key].realm = realm
    KeystoneSyncDB[key].region = REGION
    KeystoneSyncDB[key].ilvl = itemLevel.ilvl
    KeystoneSyncDB[key].equippedIlvl = itemLevel.equippedIlvl
    KeystoneSyncDB[key].hasKeystone = keystone.hasKeystone
    KeystoneSyncDB[key].keystoneLevel = keystone.level
    KeystoneSyncDB[key].keystoneChallengeMapId = keystone.challengeMapId
    KeystoneSyncDB[key].keystoneMapId = keystone.mapId
    KeystoneSyncDB[key].keystoneDungeon = keystone.dungeonName
    KeystoneSyncDB[key].vault = GetVaultData()
    KeystoneSyncDB[key].preyHunts = GetPreyHunts()
    KeystoneSyncDB[key].currencies = GetCurrencyData()
    KeystoneSyncDB[key].mythicPlusSeason = GetMythicPlusSeason()
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
    if event == "PLAYER_LOGOUT" or event == "PLAYER_LOGIN" then
        SaveCharacterData(event)
    else
        SaveCharacterData(event)
    end
end)

SLASH_KEYSTONESYNC1 = "/ksync"
SlashCmdList["KEYSTONESYNC"] = function()
    SaveCharacterData("MANUAL_COMMAND")
    PrintCurrentKeystone()
end
