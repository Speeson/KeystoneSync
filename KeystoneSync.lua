local ADDON_NAME, KeystoneSync = ...
local PREFIX = "[KeystoneSync]"
local KeystoneLootIntegration = KeystoneSync and KeystoneSync.KeystoneLootIntegration

-- Region hardcodeada. Cambiar a "us" si el servidor no es EU.
local REGION = "eu"
local MAX_LEVEL = 90
local SEASON_CAPTURE_DELAY_SECONDS = 20

local CURRENCIES = {
    { key = "adventurerMistcrest", id = 3442 },
    { key = "veteranMistcrest", id = 3443 },
    { key = "championMistcrest", id = 3444 },
    { key = "heroMistcrest", id = 3445 },
    { key = "mythMistcrest", id = 3446 },
    { key = "venomblightManaflux", id = 3465 },
    { key = "tidalSparkDust", id = 3509 },
    { key = "cofferKeyShards", id = 3310 },
    { key = "restoredCofferKey", id = 3028 },
    { key = "nebulousVoidcore", id = 3513, quantityId = 3418 },
}

local SPARK_OF_TIDES_ITEM_ID = 274476
local SPARK_OF_TIDES_ICON_FILE_ID = 7551419
local TIDAL_SPARK_DUST_CURRENCY_ID = 3509
local TROVEHUNTERS_BOUNTY_ITEM_ID = 274374
local TROVEHUNTERS_BOUNTY_QUEST_ID = 86371
local TROVEHUNTERS_BOUNTY_BUFF_SPELL_ID = 1293799
local pendingSeasonCaptureKey = nil
local GetCharacterKey

local function RefreshKeystoneLoot()
    if not KeystoneLootIntegration or type(KeystoneLootIntegration.RefreshCurrent) ~= "function" then
        return nil
    end

    local ok, snapshot = pcall(KeystoneLootIntegration.RefreshCurrent, KeystoneLootIntegration)
    if ok then
        return snapshot
    end
    return nil
end

local function StartKeystoneLootIntegration()
    if not KeystoneLootIntegration or type(KeystoneLootIntegration.Start) ~= "function" then
        return nil
    end

    local ok, snapshot = pcall(KeystoneLootIntegration.Start, KeystoneLootIntegration, GetCharacterKey)
    if ok then
        return snapshot
    end
    return nil
end

local function StopKeystoneLootIntegration()
    if not KeystoneLootIntegration or type(KeystoneLootIntegration.Stop) ~= "function" then
        return
    end

    pcall(KeystoneLootIntegration.Stop, KeystoneLootIntegration)
end

local function PrintKeystoneLootDiagnostic(snapshot)
    if not KeystoneLootIntegration or type(KeystoneLootIntegration.FormatDiagnostic) ~= "function" then
        return
    end

    local ok, message = pcall(KeystoneLootIntegration.FormatDiagnostic, KeystoneLootIntegration, snapshot)
    if ok and type(message) == "string" and message ~= "" then
        print(PREFIX .. " " .. message)
    end
end

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

GetCharacterKey = function()
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

    local lastBag = NUM_TOTAL_EQUIPPED_BAG_SLOTS or NUM_BAG_SLOTS or 0
    for bag = 0, lastBag do
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

    local lastBag = NUM_TOTAL_EQUIPPED_BAG_SLOTS or NUM_BAG_SLOTS or 0
    for bag = 0, lastBag do
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

local GetWeeklyResetKey
local GetWeeklyResetStart
local UtcTimestamp

local function GetCurrentKeystone(prev)
    local weeklyResetKey = GetWeeklyResetKey()
    local weeklyResetStart = GetWeeklyResetStart()
    local level = C_MythicPlus.GetOwnedKeystoneLevel()
    local challengeMapId = C_MythicPlus.GetOwnedKeystoneChallengeMapID()
    local mapId = C_MythicPlus.GetOwnedKeystoneMapID()

    if not level or not challengeMapId then
        local bagLevel, bagChallengeMapId = GetKeystoneFromBags()
        level = level or bagLevel
        challengeMapId = challengeMapId or bagChallengeMapId
    end

    local hasKeystone = (level ~= nil and level > 0)
    local previousSameWeek = prev
        and prev.hasKeystone
        and prev.keystoneLevel
        and (
            prev.keystoneWeeklyResetKey == weeklyResetKey
            or (not prev.keystoneWeeklyResetKey and prev.updatedAt and prev.updatedAt >= weeklyResetStart)
        )

    if not hasKeystone and previousSameWeek then
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
        weeklyResetKey = weeklyResetKey,
    }
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

local function CountPreyQuestSet(ids, questsCompleted)
    local count = 0
    local completed = {}

    for _, questID in ipairs(ids) do
        local isCompleted = C_QuestLog.IsQuestFlaggedCompleted(questID) == true
        questsCompleted[questID] = isCompleted
        if isCompleted then
            count = count + 1
            table.insert(completed, questID)
        end
    end

    return count, completed
end

local function PreyTotal(preyHunts)
    if not preyHunts then return 0 end
    return (preyHunts.normal and preyHunts.normal.count or 0)
        + (preyHunts.hard and preyHunts.hard.count or 0)
        + (preyHunts.nightmare and preyHunts.nightmare.count or 0)
end

GetWeeklyResetKey = function()
    return date("!%Y-%m-%d", GetWeeklyResetStart())
end

GetWeeklyResetStart = function()
    local now = time()
    local current = date("!*t", now)
    local daysSinceWednesday = (current.wday - 4) % 7
    local resetDay = date("!*t", now - (daysSinceWednesday * 86400))
    local resetAt = UtcTimestamp({
        year = resetDay.year,
        month = resetDay.month,
        day = resetDay.day,
        hour = 4,
        min = 0,
        sec = 0,
    })

    if now < resetAt then
        resetAt = resetAt - (7 * 86400)
    end

    return resetAt
end

UtcTimestamp = function(utcDate)
    local asLocal = time(utcDate)
    local localFields = date("*t", asLocal)
    local utcFields = date("!*t", asLocal)
    local offset = time(localFields) - time(utcFields)
    return asLocal + offset
end

local function GetTexturePath(fileDataID)
    if not fileDataID or not C_Texture or not C_Texture.GetFilenameFromFileDataID then return nil end

    local ok, path = pcall(C_Texture.GetFilenameFromFileDataID, fileDataID)
    if ok and path and path ~= "" then
        return path
    end

    return nil
end

local function GetCharacterItemCount(itemID)
    if not C_Item or type(C_Item.GetItemCount) ~= "function" then return 0 end

    local ok, rawCount = pcall(C_Item.GetItemCount, itemID, true, false, true, false)
    if ok and (not issecretvalue or not issecretvalue(rawCount)) and type(rawCount) == "number" then
        return rawCount
    end

    return 0
end

local function GetItemIconFileID(itemID, fallbackFileID)
    if C_Item and type(C_Item.GetItemIconByID) == "function" then
        local ok, rawIconFileID = pcall(C_Item.GetItemIconByID, itemID)
        if ok and (not issecretvalue or not issecretvalue(rawIconFileID)) and type(rawIconFileID) == "number" then
            return rawIconFileID
        end
    end

    return fallbackFileID
end

local function GetPreyHunts(prev)
    local normal = BuildRange(91095, 91124)
    local hard = {}
    local nightmare = {}
    local questsCompleted = {}
    local weekKey = GetWeeklyResetKey()

    AppendRange(hard, 91210, 91240, 2)
    AppendRange(hard, 91242, 91255)

    AppendRange(nightmare, 91211, 91241, 2)
    AppendRange(nightmare, 91256, 91269)
    table.insert(nightmare, 95021)
    table.insert(nightmare, 95022)
    table.insert(nightmare, 95023)
    table.insert(nightmare, 95024)

    local normalCount, normalCompleted = CountPreyQuestSet(normal, questsCompleted)
    local hardCount, hardCompleted = CountPreyQuestSet(hard, questsCompleted)
    local nightmareCount, nightmareCompleted = CountPreyQuestSet(nightmare, questsCompleted)

    local result = {
        weekKey = weekKey,
        questsCompleted = questsCompleted,
        normal = { count = normalCount, completedQuestIDs = normalCompleted },
        hard = { count = hardCount, completedQuestIDs = hardCompleted },
        nightmare = { count = nightmareCount, completedQuestIDs = nightmareCompleted },
    }

    -- WoW can occasionally return an empty quest-completion snapshot during login/logout.
    -- Preserve it only inside the same weekly reset window, otherwise reset-week zeroes must win.
    if PreyTotal(result) == 0
        and prev
        and prev.preyHunts
        and prev.preyHunts.weekKey == weekKey
        and PreyTotal(prev.preyHunts) > 0 then
        return prev.preyHunts
    end

    return result
end

local function GetCurrencyData(prev)
    local result = {}

    for _, currencyDef in ipairs(CURRENCIES) do
        local info = C_CurrencyInfo.GetCurrencyInfo(currencyDef.id)
        if info then
            local isComplete = false
            if currencyDef.key == "nebulousVoidcore" and info.maxQuantity and info.maxQuantity > 0 then
                isComplete = (info.totalEarned or info.quantity or 0) >= info.maxQuantity
            end

            local quantityInfo = info
            if currencyDef.quantityId then
                quantityInfo = C_CurrencyInfo.GetCurrencyInfo(currencyDef.quantityId) or info
            end

            result[currencyDef.key] = {
                id = currencyDef.id,
                name = info.name,
                quantity = quantityInfo.quantity or 0,
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

    local sparkDust = result.tidalSparkDust
    local sparkInventoryCount = CountItemInBags(SPARK_OF_TIDES_ITEM_ID)
    local sparkTotalCount = GetCharacterItemCount(SPARK_OF_TIDES_ITEM_ID)
    local sparkItemCount = math.max(sparkInventoryCount, sparkTotalCount)
    local sparkIconFileID = GetItemIconFileID(SPARK_OF_TIDES_ITEM_ID, SPARK_OF_TIDES_ICON_FILE_ID)

    result.sparksOfTides = {
        itemID = SPARK_OF_TIDES_ITEM_ID,
        currencyID = TIDAL_SPARK_DUST_CURRENCY_ID,
        quantity = sparkItemCount,
        itemQuantity = sparkItemCount,
        inventoryQuantity = sparkInventoryCount,
        totalItemQuantity = sparkTotalCount,
        dustQuantity = sparkDust and (sparkDust.quantity or sparkDust.trackedQuantity or sparkDust.totalEarned) or 0,
        dustMaxQuantity = sparkDust and sparkDust.maxQuantity or 0,
        dustTotalEarned = sparkDust and sparkDust.totalEarned or 0,
        dustTrackedQuantity = sparkDust and sparkDust.trackedQuantity or 0,
        iconFileID = sparkIconFileID,
        iconPath = GetTexturePath(sparkIconFileID),
    }

    local bagCount = 0
    local bagCountOK, rawBagCount = pcall(CountItemInBags, TROVEHUNTERS_BOUNTY_ITEM_ID)
    if bagCountOK and (not issecretvalue or not issecretvalue(rawBagCount)) and type(rawBagCount) == "number" then
        bagCount = rawBagCount
    end

    local hasBuff = false
    if C_UnitAuras and C_UnitAuras.GetPlayerAuraBySpellID then
        local auraOK, aura = pcall(C_UnitAuras.GetPlayerAuraBySpellID, TROVEHUNTERS_BOUNTY_BUFF_SPELL_ID)
        hasBuff = auraOK and aura ~= nil and (not issecretvalue or not issecretvalue(aura))
    end

    local questCompleted = false
    local questOK, questValue = pcall(C_QuestLog.IsQuestFlaggedCompleted, TROVEHUNTERS_BOUNTY_QUEST_ID)
    if questOK and (not issecretvalue or not issecretvalue(questValue)) then
        questCompleted = questValue == true
    end

    local weekKey = GetWeeklyResetKey()
    local previousBounty = prev and prev.currencies and prev.currencies.trovehuntersBounty
    if not questCompleted and previousBounty and previousBounty.weekKey == weekKey and previousBounty.questCompleted then
        questCompleted = true
    end

    local iconFileID = nil
    local iconOK, rawIconFileID = pcall(C_Item.GetItemIconByID, TROVEHUNTERS_BOUNTY_ITEM_ID)
    if iconOK and (not issecretvalue or not issecretvalue(rawIconFileID)) and type(rawIconFileID) == "number" then
        iconFileID = rawIconFileID
    end
    result.trovehuntersBounty = {
        itemID = TROVEHUNTERS_BOUNTY_ITEM_ID,
        bagCount = bagCount,
        hasBuff = hasBuff,
        questCompleted = questCompleted,
        iconFileID = iconFileID,
        iconPath = GetTexturePath(iconFileID),
        weekKey = weekKey,
    }

    return result
end

local function GetVaultData()
    local result = {
        weekKey = GetWeeklyResetKey(),
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

local function CountSeasonRuns(season)
    local count = 0
    if not season or not season.dungeons then return count end

    for _, dungeon in ipairs(season.dungeons) do
        if dungeon.level and dungeon.level > 0 then
            count = count + 1
        end
    end

    return count
end

local function SeasonSignature(season)
    if not season or not season.dungeons then return nil end

    local parts = {}
    for _, dungeon in ipairs(season.dungeons) do
        if dungeon.level and dungeon.level > 0 then
            local timed = dungeon.timed and "1" or "0"
            local duration = dungeon.bestTimedRun and dungeon.bestTimedRun.durationSec or 0
            table.insert(parts, table.concat({
                tostring(dungeon.challengeMapId or 0),
                tostring(dungeon.level or 0),
                timed,
                tostring(duration or 0),
            }, ":"))
        end
    end

    if #parts == 0 then return nil end
    table.sort(parts)
    return table.concat(parts, "|")
end

local function HasDuplicateSeasonSignature(currentKey, season)
    local signature = SeasonSignature(season)
    if not signature or not KeystoneSyncDB then return false end

    for key, data in pairs(KeystoneSyncDB) do
        if key ~= currentKey and data and SeasonSignature(data.mythicPlusSeason) == signature then
            return true
        end
    end

    return false
end

local function ShouldAcceptMythicPlusSeason(currentKey, prev, season)
    local newRuns = CountSeasonRuns(season)
    local prevRuns = CountSeasonRuns(prev and prev.mythicPlusSeason)

    if newRuns == 0 and prevRuns > 0 then
        if HasDuplicateSeasonSignature(currentKey, prev and prev.mythicPlusSeason) then
            return true
        end
        return false
    end

    if newRuns > 0 and HasDuplicateSeasonSignature(currentKey, season) then
        local previousSignature = SeasonSignature(prev and prev.mythicPlusSeason)
        if previousSignature and previousSignature == SeasonSignature(season) then
            return true
        end
        return false
    end

    return true
end

local function UpdateMythicPlusSeason(key, prev)
    local season = GetMythicPlusSeason()
    if ShouldAcceptMythicPlusSeason(key, prev, season) then
        KeystoneSyncDB[key].mythicPlusSeason = season
        KeystoneSyncDB[key].mythicPlusSeasonUpdatedAt = time()
    elseif prev and prev.mythicPlusSeason then
        KeystoneSyncDB[key].mythicPlusSeason = prev.mythicPlusSeason
        KeystoneSyncDB[key].mythicPlusSeasonUpdatedAt = prev.mythicPlusSeasonUpdatedAt
    end
end

local function GetItemLevel(prev)
    local avgItemLevel = GetAverageItemLevel()
    if avgItemLevel and avgItemLevel > 0 then
        return math.floor(avgItemLevel + 0.5)
    end
    return prev and prev.ilvl or nil
end

local function GetMoneyData(prev, reason)
    local copper = GetMoney() or 0
    if reason == "PLAYER_LOGOUT" and copper == 0 and prev and prev.money and prev.money.copper and prev.money.copper > 0 then
        return prev.money
    end
    return {
        copper = copper,
        gold = math.floor(copper / 10000),
        silver = math.floor((copper % 10000) / 100),
        copperOnly = copper % 100,
    }
end

local function SaveCharacterData(reason, updateSeason, refreshKeystoneLoot)
    if UnitLevel("player") < MAX_LEVEL then return end

    KeystoneSyncDB = KeystoneSyncDB or {}

    local character = UnitName("player")
    local realm = GetRealmName()
    local key = GetCharacterKey()
    local prev = KeystoneSyncDB and KeystoneSyncDB[key]
    local keystone = GetCurrentKeystone(prev)
    local ilvl = GetItemLevel(prev)

    KeystoneSyncDB[key] = KeystoneSyncDB[key] or {}
    KeystoneSyncDB[key].character = character
    KeystoneSyncDB[key].realm = realm
    KeystoneSyncDB[key].region = REGION
    KeystoneSyncDB[key].ilvl = ilvl
    KeystoneSyncDB[key].hasKeystone = keystone.hasKeystone
    KeystoneSyncDB[key].keystoneLevel = keystone.level
    KeystoneSyncDB[key].keystoneChallengeMapId = keystone.challengeMapId
    KeystoneSyncDB[key].keystoneMapId = keystone.mapId
    KeystoneSyncDB[key].keystoneDungeon = keystone.dungeonName
    KeystoneSyncDB[key].keystoneWeeklyResetKey = keystone.weeklyResetKey
    KeystoneSyncDB[key].vault = GetVaultData()
    KeystoneSyncDB[key].preyHunts = GetPreyHunts(prev)
    KeystoneSyncDB[key].currencies = GetCurrencyData(prev)
    KeystoneSyncDB[key].money = GetMoneyData(prev, reason)
    if updateSeason then
        UpdateMythicPlusSeason(key, prev)
    end
    KeystoneSyncDB[key].updatedAt = time()
    KeystoneSyncDB[key].updatedReason = reason

    if refreshKeystoneLoot ~= false then
        return RefreshKeystoneLoot()
    end
    return nil
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

local function ScheduleSeasonCapture()
    if not C_Timer or not C_Timer.After then return end

    local key = GetCharacterKey()
    pendingSeasonCaptureKey = key

    C_Timer.After(SEASON_CAPTURE_DELAY_SECONDS, function()
        if pendingSeasonCaptureKey == key and GetCharacterKey() == key and UnitLevel("player") >= MAX_LEVEL then
            SaveCharacterData("PLAYER_LOGIN_DELAYED_SEASON", true)
        end
    end)
end

frame:SetScript("OnEvent", function(self, event)
    if event == "PLAYER_LOGIN" then
        SaveCharacterData(event, false, false)
        StartKeystoneLootIntegration()
        ScheduleSeasonCapture()
    elseif event == "PLAYER_LOGOUT" then
        pendingSeasonCaptureKey = nil
        SaveCharacterData(event, false)
        StopKeystoneLootIntegration()
    elseif event == "CHALLENGE_MODE_COMPLETED" or event == "MYTHIC_PLUS_NEW_WEEKLY_RECORD" then
        SaveCharacterData(event, true)
    else
        SaveCharacterData(event, false)
    end
end)

SLASH_KEYSTONESYNC1 = "/ksync"
SlashCmdList["KEYSTONESYNC"] = function()
    local keystoneLootSnapshot = SaveCharacterData("MANUAL_COMMAND", true)
    PrintCurrentKeystone()
    PrintKeystoneLootDiagnostic(keystoneLootSnapshot)
end
