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
    { key = "untaintedManaCrystals", id = 3356 },
    { key = "nebulousVoidcore", id = 3513, quantityId = 3418 },
}

local EQUIPMENT_SLOTS = {
    { id = 1, name = "Head" },
    { id = 2, name = "Neck" },
    { id = 3, name = "Shoulder" },
    { id = 15, name = "Back" },
    { id = 5, name = "Chest" },
    { id = 9, name = "Wrist" },
    { id = 10, name = "Hands" },
    { id = 6, name = "Waist" },
    { id = 7, name = "Legs" },
    { id = 8, name = "Feet" },
    { id = 11, name = "Finger1" },
    { id = 12, name = "Finger2" },
    { id = 13, name = "Trinket1" },
    { id = 14, name = "Trinket2" },
    { id = 16, name = "MainHand" },
    { id = 17, name = "OffHand" },
}

local OMNIUM_TRAIT_SYSTEM_ID = 48
local OMNIUM_FALLBACK_TREE_ID = 1186
local SNAPSHOT_REFRESH_DELAY_SECONDS = 0.4

local SPARK_OF_TIDES_ITEM_ID = 274476
local TIDAL_SPARK_DUST_CURRENCY_ID = 3509
local TROVEHUNTERS_BOUNTY_ITEM_ID = 274374
local TROVEHUNTERS_BOUNTY_QUEST_ID = 86371
local TROVEHUNTERS_BOUNTY_BUFF_SPELL_ID = 1293799
local pendingSeasonCaptureKey = nil
local snapshotRefreshPending = false
local personalBankAccessible = false
local GetCharacterKey

local function GenerateSavedVariablesInstanceId()
    local timestamp = type(time) == "function" and tonumber(time()) or 0
    local uptime = type(GetTime) == "function" and tonumber(GetTime()) or 0
    local entropy = string.gsub(tostring({}), "[^%w]", "")
    local randomA = math.random(100000, 999999)
    local randomB = math.random(100000, 999999)
    return string.format(
        "ksv1-%d-%d-%d-%d-%s",
        timestamp or 0,
        math.floor((uptime or 0) * 1000),
        randomA,
        randomB,
        entropy
    )
end

local function EnsureSavedVariablesInstanceId()
    if type(KeystoneSyncDB.savedVariablesInstanceId) ~= "string"
        or KeystoneSyncDB.savedVariablesInstanceId == "" then
        KeystoneSyncDB.savedVariablesInstanceId = GenerateSavedVariablesInstanceId()
    end
    return KeystoneSyncDB.savedVariablesInstanceId
end

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

local function PrintKeystoneLootFavoriteDiagnostics(snapshot)
    if not KeystoneLootIntegration or type(KeystoneLootIntegration.FormatFavoriteDiagnostics) ~= "function" then
        return
    end

    local ok, lines = pcall(KeystoneLootIntegration.FormatFavoriteDiagnostics, KeystoneLootIntegration, snapshot)
    if not ok or type(lines) ~= "table" then
        return
    end
    for _, line in ipairs(lines) do
        if type(line) == "string" and line ~= "" then
            print(PREFIX .. " " .. line)
        end
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
frame:RegisterEvent("BANKFRAME_OPENED")
frame:RegisterEvent("BANKFRAME_CLOSED")
frame:RegisterEvent("CHALLENGE_MODE_COMPLETED")
frame:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")
frame:RegisterEvent("UNIT_INVENTORY_CHANGED")
frame:RegisterEvent("TRAIT_CONFIG_LIST_UPDATED")
frame:RegisterEvent("TRAIT_CONFIG_UPDATED")
frame:RegisterEvent("ACTIVE_COMBAT_CONFIG_CHANGED")
frame:RegisterEvent("PLAYER_SPECIALIZATION_CHANGED")
frame:RegisterEvent("TRAIT_SUB_TREE_CHANGED")
frame:RegisterEvent("GET_ITEM_INFO_RECEIVED")

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

local SPARK_CARRIED_BAG_KEYS = {
    "Backpack",
    "Bag_1",
    "Bag_2",
    "Bag_3",
    "Bag_4",
    "ReagentBag",
}

local function CountItemInContainers(itemID, containerIDs)
    if not C_Container
        or type(C_Container.GetContainerNumSlots) ~= "function"
        or type(C_Container.GetContainerItemInfo) ~= "function"
        or type(containerIDs) ~= "table" then
        return nil
    end

    local ok, total = pcall(function()
        local count = 0
        for _, containerID in ipairs(containerIDs) do
            local slots = C_Container.GetContainerNumSlots(containerID)
            if type(slots) ~= "number" or (issecretvalue and issecretvalue(slots)) then
                error("container slots unavailable")
            end
            for slot = 1, slots do
                local info = C_Container.GetContainerItemInfo(containerID, slot)
                if info then
                    local foundItemID = info.itemID
                    local stackCount = info.stackCount
                    if issecretvalue and (issecretvalue(foundItemID) or issecretvalue(stackCount)) then
                        error("container item unavailable")
                    end
                    if foundItemID == itemID then
                        count = count + (type(stackCount) == "number" and stackCount or 0)
                    end
                end
            end
        end
        return count
    end)

    if not ok or type(total) ~= "number" then
        return nil
    end
    return math.max(0, total)
end

local function CountCarriedSparks()
    local bagIndex = Enum and Enum.BagIndex
    if type(bagIndex) ~= "table" then return nil end

    local carriedContainers = {}
    for _, key in ipairs(SPARK_CARRIED_BAG_KEYS) do
        local containerID = bagIndex[key]
        if type(containerID) ~= "number" then return nil end
        table.insert(carriedContainers, containerID)
    end

    return CountItemInContainers(SPARK_OF_TIDES_ITEM_ID, carriedContainers)
end

local function CountPersonalBankSparks()
    local bankType = Enum and Enum.BankType
    if not C_Bank
        or type(C_Bank.FetchPurchasedBankTabIDs) ~= "function"
        or type(bankType) ~= "table"
        or type(bankType.Character) ~= "number" then
        return nil
    end

    local ok, characterBankTabs = pcall(C_Bank.FetchPurchasedBankTabIDs, bankType.Character)
    if not ok or type(characterBankTabs) ~= "table" then
        return nil
    end
    return CountItemInContainers(SPARK_OF_TIDES_ITEM_ID, characterBankTabs)
end

local function GetSparkQuantities(prev, bankDataAuthoritative, preservePreviousSnapshot)
    local previousSpark = prev and prev.currencies and prev.currencies.sparksOfTides

    if preservePreviousSnapshot then
        local carriedQuantity = previousSpark
            and type(previousSpark.inventoryQuantity) == "number"
            and math.max(0, previousSpark.inventoryQuantity)
            or 0
        local bankQuantityKnown = previousSpark
            and previousSpark.bankQuantityKnown == true
            and type(previousSpark.bankQuantity) == "number"
            or false
        local bankQuantity = bankQuantityKnown
            and type(previousSpark.bankQuantity) == "number"
            and math.max(0, previousSpark.bankQuantity)
            or nil
        local itemQuantity = previousSpark
            and type(previousSpark.itemQuantity) == "number"
            and math.max(0, previousSpark.itemQuantity)
            or (carriedQuantity + (bankQuantity or 0))

        return {
            carriedQuantity = carriedQuantity,
            bankQuantity = bankQuantity,
            bankQuantityKnown = bankQuantityKnown,
            bankUpdatedAt = previousSpark and previousSpark.bankUpdatedAt or nil,
            itemQuantity = itemQuantity,
        }
    end

    local carriedQuantity = CountCarriedSparks()
    if type(carriedQuantity) ~= "number" then
        carriedQuantity = previousSpark
            and type(previousSpark.inventoryQuantity) == "number"
            and math.max(0, previousSpark.inventoryQuantity)
            or 0
    end
    local bankQuantity = nil
    local bankQuantityKnown = false
    local bankUpdatedAt = nil

    if bankDataAuthoritative then
        local currentBankQuantity = CountPersonalBankSparks()
        if type(currentBankQuantity) == "number" then
            bankQuantity = currentBankQuantity
            bankQuantityKnown = true
            bankUpdatedAt = time()
        end
    end

    if not bankQuantityKnown
        and previousSpark
        and previousSpark.bankQuantityKnown == true
        and type(previousSpark.bankQuantity) == "number" then
        bankQuantity = math.max(0, previousSpark.bankQuantity)
        bankQuantityKnown = true
        bankUpdatedAt = previousSpark.bankUpdatedAt
    end

    return {
        carriedQuantity = carriedQuantity,
        bankQuantity = bankQuantity,
        bankQuantityKnown = bankQuantityKnown,
        bankUpdatedAt = bankUpdatedAt,
        itemQuantity = carriedQuantity + (bankQuantity or 0),
    }
end

local function ParseTooltipMaximum(text)
    if type(text) ~= "string" or (issecretvalue and issecretvalue(text)) then return nil end
    text = text:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")
    local maximum
    for digits in text:gmatch("%d[%d%.,%s]*") do
        local normalized = digits:gsub("[^%d]", "")
        local value = tonumber(normalized)
        if value then maximum = value end
    end
    return maximum
end

local function GetCurrencyTooltipMaximum(currencyId)
    if not C_TooltipInfo or type(C_TooltipInfo.GetCurrencyByID) ~= "function" then return nil end
    local tooltipOK, tooltip = pcall(C_TooltipInfo.GetCurrencyByID, currencyId)
    if not tooltipOK or type(tooltip) ~= "table" or type(tooltip.lines) ~= "table" then return nil end
    local currencyTotalType = Enum and Enum.TooltipDataLineType and Enum.TooltipDataLineType.CurrencyTotal or 14
    for _, line in ipairs(tooltip.lines) do
        if type(line) == "table" and line.type == currencyTotalType then
            local maximum = ParseTooltipMaximum(line.rightText) or ParseTooltipMaximum(line.leftText)
            if maximum and maximum > 0 then return maximum end
        end
    end
    return nil
end

local function GetCurrencyData(prev, preserveSparkSnapshot)
    local result = {}

    for _, currencyDef in ipairs(CURRENCIES) do
        local info = C_CurrencyInfo.GetCurrencyInfo(currencyDef.id)
        if info then
            local quantityInfo = info
            if currencyDef.quantityId then
                quantityInfo = C_CurrencyInfo.GetCurrencyInfo(currencyDef.quantityId) or info
            end

            local quantity = quantityInfo.quantity or 0
            local maxQuantity = info.maxQuantity or 0
            local maxWeeklyQuantity = info.maxWeeklyQuantity or 0
            local totalEarned = info.totalEarned or 0
            local quantityEarnedThisWeek = info.quantityEarnedThisWeek or 0
            local useTotalEarnedForMaxQty = info.useTotalEarnedForMaxQty == true
            if useTotalEarnedForMaxQty and maxQuantity <= 0 then
                local tooltipMaximum = GetCurrencyTooltipMaximum(currencyDef.id)
                if tooltipMaximum and tooltipMaximum >= totalEarned then
                    maxQuantity = tooltipMaximum
                end
            end
            local isWeeklyMaxed = maxWeeklyQuantity > 0 and quantityEarnedThisWeek >= maxWeeklyQuantity
            local isSeasonMaxed = useTotalEarnedForMaxQty and maxQuantity > 0 and totalEarned >= maxQuantity
            local isTotalMaxed = not useTotalEarnedForMaxQty and maxQuantity > 0 and quantity >= maxQuantity
            local isMaxed = isWeeklyMaxed or isSeasonMaxed or isTotalMaxed

            result[currencyDef.key] = {
                id = currencyDef.id,
                name = info.name,
                quantity = quantity,
                maxQuantity = maxQuantity,
                maxWeeklyQuantity = maxWeeklyQuantity,
                totalEarned = totalEarned,
                trackedQuantity = info.trackedQuantity or 0,
                quantityEarnedThisWeek = quantityEarnedThisWeek,
                useTotalEarnedForMaxQty = useTotalEarnedForMaxQty,
                canEarnPerWeek = info.canEarnPerWeek == true,
                discovered = info.discovered == true,
                quality = info.quality,
                iconFileID = info.iconFileID,
                iconPath = GetTexturePath(info.iconFileID),
                isWeeklyMaxed = isWeeklyMaxed,
                isSeasonMaxed = isSeasonMaxed,
                isTotalMaxed = isTotalMaxed,
                isMaxed = isMaxed,
                isWeeklyComplete = isMaxed,
                displayColor = isMaxed and "red" or nil,
            }
        end
    end

    local sparkDust = result.tidalSparkDust
    local spark = GetSparkQuantities(prev, personalBankAccessible, preserveSparkSnapshot)

    result.sparksOfTides = {
        itemID = SPARK_OF_TIDES_ITEM_ID,
        currencyID = TIDAL_SPARK_DUST_CURRENCY_ID,
        quantity = spark.itemQuantity,
        itemQuantity = spark.itemQuantity,
        inventoryQuantity = spark.carriedQuantity,
        totalItemQuantity = spark.itemQuantity,
        bankQuantity = spark.bankQuantity,
        bankQuantityKnown = spark.bankQuantityKnown,
        bankUpdatedAt = spark.bankUpdatedAt,
        dustQuantity = sparkDust and (sparkDust.quantity or sparkDust.trackedQuantity or sparkDust.totalEarned) or 0,
        dustMaxQuantity = sparkDust and sparkDust.maxQuantity or 0,
        dustTotalEarned = sparkDust and sparkDust.totalEarned or 0,
        dustTrackedQuantity = sparkDust and sparkDust.trackedQuantity or 0,
        iconFileID = C_Item.GetItemIconByID(SPARK_OF_TIDES_ITEM_ID),
        iconPath = GetTexturePath(C_Item.GetItemIconByID(SPARK_OF_TIDES_ITEM_ID)),
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

local function SplitItemPayload(itemLink)
    if type(itemLink) ~= "string" then return nil end
    local payload = itemLink:match("|Hitem:([^|]+)|h") or itemLink:match("item:([^|]+)")
    if not payload then return nil end

    local fields = {}
    for value in (payload .. ":"):gmatch("(.-):") do
        table.insert(fields, value)
    end
    return fields
end

local function PositiveInteger(value)
    local number = tonumber(value)
    if not number or number <= 0 or number ~= math.floor(number) then return nil end
    return number
end

local function ParseItemVariant(itemLink)
    local fields = SplitItemPayload(itemLink)
    if not fields then return nil end

    local bonusIds = {}
    local numBonusIds = tonumber(fields[13]) or 0
    if numBonusIds < 0 or numBonusIds > 64 then numBonusIds = 0 end
    for index = 1, numBonusIds do
        local bonusId = PositiveInteger(fields[13 + index])
        if bonusId then table.insert(bonusIds, bonusId) end
    end

    return {
        itemId = PositiveInteger(fields[1]),
        enchantId = PositiveInteger(fields[2]),
        suffixId = tonumber(fields[7]),
        itemContext = tonumber(fields[12]),
        bonusIds = bonusIds,
    }
end

local function GetAtlasFileID(atlas)
    if type(atlas) ~= "string" or not C_Texture or type(C_Texture.GetAtlasInfo) ~= "function" then return nil end
    local atlasOK, atlasInfo = pcall(C_Texture.GetAtlasInfo, atlas)
    return atlasOK and type(atlasInfo) == "table" and PositiveInteger(atlasInfo.file) or nil
end

local function GetInventoryEnchantData(slotId)
    if not C_TooltipInfo or type(C_TooltipInfo.GetInventoryItem) ~= "function" then return nil end
    local tooltipOK, tooltip = pcall(C_TooltipInfo.GetInventoryItem, "player", slotId)
    if not tooltipOK or type(tooltip) ~= "table" or type(tooltip.lines) ~= "table" then return nil end
    local prefix = type(ENCHANTED_TOOLTIP_LINE) == "string" and ENCHANTED_TOOLTIP_LINE:match("^(.-)%%s") or nil
    if not prefix then return nil end
    for _, line in ipairs(tooltip.lines) do
        local text = type(line) == "table" and line.leftText or nil
        if text and issecretvalue and issecretvalue(text) then text = nil end
        if type(text) == "string" and text:find(prefix, 1, true) == 1 then
            text = text:sub(#prefix + 1)
            local atlas = text:match("|A:([^:]+):")
            local iconFileID = GetAtlasFileID(atlas)
            text = text:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", ""):gsub("|A.-|a", "")
            if text ~= "" then return { name = text, iconFileID = iconFileID } end
        end
    end
    return nil
end

local function GetEquipmentData(prev)
    if type(GetInventoryItemLink) ~= "function" or not C_Item or type(C_Item.GetItemInfo) ~= "function" then
        return prev and prev.equipment or nil
    end

    local items = {}
    local setCounts = {}
    for _, slot in ipairs(EQUIPMENT_SLOTS) do
        local linkOK, itemLink = pcall(GetInventoryItemLink, "player", slot.id)
        if linkOK and type(itemLink) == "string" and itemLink ~= "" then
            local variant = ParseItemVariant(itemLink)
            local infoOK, itemName, _, quality, itemLevel, _, _, _, _, _, iconFileID, _, _, _, _, _, setId =
                pcall(C_Item.GetItemInfo, itemLink)
            if infoOK and variant and variant.itemId then
                if type(C_Item.GetDetailedItemLevelInfo) == "function" then
                    local levelOK, detailedLevel = pcall(C_Item.GetDetailedItemLevelInfo, itemLink)
                    if levelOK and type(detailedLevel) == "number" then itemLevel = detailedLevel end
                end

                local gems = {}
                if type(C_Item.GetItemGem) == "function" then
                    for gemIndex = 1, 4 do
                        local gemOK, gemName, gemLink = pcall(C_Item.GetItemGem, itemLink, gemIndex)
                        if gemOK and type(gemLink) == "string" and gemLink ~= "" then
                            local gemVariant = ParseItemVariant(gemLink)
                            if gemVariant and gemVariant.itemId then
                                local gemIcon = nil
                                if type(C_Item.GetItemIconByID) == "function" then
                                    local iconOK, resolvedIcon = pcall(C_Item.GetItemIconByID, gemLink)
                                    if iconOK then gemIcon = resolvedIcon end
                                end
                                table.insert(gems, {
                                    itemId = gemVariant.itemId,
                                    itemLink = gemLink,
                                    name = gemName,
                                    iconFileID = gemIcon,
                                    iconPath = GetTexturePath(gemIcon),
                                })
                            end
                        end
                    end
                end

                local enchant = nil
                if variant.enchantId then
                    local enchantData = GetInventoryEnchantData(slot.id) or {}
                    enchant = {
                        enchantId = variant.enchantId,
                        name = enchantData.name,
                        iconFileID = enchantData.iconFileID,
                        iconPath = GetTexturePath(enchantData.iconFileID),
                    }
                end
                local upgrade = nil
                if type(C_Item.GetItemUpgradeInfo) == "function" then
                    local upgradeOK, upgradeInfo = pcall(C_Item.GetItemUpgradeInfo, itemLink)
                    if upgradeOK and type(upgradeInfo) == "table" then
                        upgrade = {
                            track = upgradeInfo.trackString,
                            currentLevel = upgradeInfo.currentLevel,
                            maxLevel = upgradeInfo.maxLevel,
                        }
                    end
                end

                table.insert(items, {
                    slotId = slot.id,
                    slotName = slot.name,
                    itemId = variant.itemId,
                    itemName = itemName,
                    itemLink = itemLink,
                    quality = quality,
                    itemLevel = itemLevel,
                    iconFileID = iconFileID,
                    iconPath = GetTexturePath(iconFileID),
                    setId = setId,
                    enchant = enchant,
                    gems = gems,
                    bonusIds = variant.bonusIds,
                    itemContext = variant.itemContext,
                    suffixId = variant.suffixId,
                    upgrade = upgrade,
                })

                if type(setId) == "number" and setId > 0 then
                    setCounts[setId] = (setCounts[setId] or 0) + 1
                end
            end
        end
    end

    if #items == 0 and prev and prev.equipment and type(prev.equipment.items) == "table" and #prev.equipment.items > 0 then
        return prev.equipment
    end

    local setPieces = {}
    for setId, count in pairs(setCounts) do
        table.insert(setPieces, { setId = setId, count = count })
    end
    table.sort(setPieces, function(left, right) return left.setId < right.setId end)
    return { averageItemLevel = GetAverageItemLevel(), setPieces = setPieces, items = items }
end

local function CurrentSpecialization()
    if not C_SpecializationInfo or type(C_SpecializationInfo.GetSpecialization) ~= "function"
        or type(C_SpecializationInfo.GetSpecializationInfo) ~= "function" then
        return nil, nil
    end
    local index = C_SpecializationInfo.GetSpecialization()
    if not index then return nil, nil end
    local specId, specName, _, specIconFileID = C_SpecializationInfo.GetSpecializationInfo(index)
    return specId, specName, PositiveInteger(specIconFileID)
end

local function SerializeTalentEntry(configId, nodeInfo, entryId)
    local entryInfo = C_Traits.GetEntryInfo(configId, entryId)
    if type(entryInfo) ~= "table" then return nil end
    local definition = entryInfo.definitionID and C_Traits.GetDefinitionInfo(entryInfo.definitionID) or nil
    local spellId = definition and definition.spellID or nil
    local spellInfo = spellId and C_Spell and C_Spell.GetSpellInfo and C_Spell.GetSpellInfo(spellId) or nil
    local selected = nodeInfo.activeEntry and nodeInfo.activeEntry.entryID == entryId or false
    local rank = selected and (nodeInfo.activeEntry.rank or nodeInfo.ranksPurchased or 0) or 0
    local description = definition and definition.overrideDescription or nil
    if not description and C_Traits.GetTraitDescription then
        local descriptionOK, value = pcall(C_Traits.GetTraitDescription, entryId, math.max(1, rank))
        if descriptionOK and type(value) == "string" and value ~= "" then description = value end
    end
    if not description and spellId and C_Spell and C_Spell.GetSpellDescription then
        local descriptionOK, value = pcall(C_Spell.GetSpellDescription, spellId)
        if descriptionOK then description = value end
    end

    return {
        entryId = entryId,
        definitionId = entryInfo.definitionID,
        spellId = spellId,
        overriddenSpellId = definition and definition.overriddenSpellID or nil,
        name = definition and definition.overrideName or (spellInfo and spellInfo.name or nil),
        description = description,
        subtext = definition and definition.overrideSubtext or nil,
        iconFileID = definition and definition.overrideIcon or (spellInfo and spellInfo.iconID or nil),
        iconPath = GetTexturePath(definition and definition.overrideIcon or (spellInfo and spellInfo.iconID or nil)),
        selected = selected,
        rank = rank,
        maxRanks = entryInfo.maxRanks,
        entryType = entryInfo.type,
        subTreeId = entryInfo.subTreeID,
    }
end

local function SerializeTalentNode(configId, nodeId)
    local nodeInfo = C_Traits.GetNodeInfo(configId, nodeId)
    if type(nodeInfo) ~= "table" or nodeInfo.isVisible == false or not PositiveInteger(nodeInfo.ID or nodeId) then return nil end
    local entries = {}
    for _, entryId in ipairs(nodeInfo.entryIDs or {}) do
        local entry = SerializeTalentEntry(configId, nodeInfo, entryId)
        if entry then table.insert(entries, entry) end
    end
    local edges = {}
    for _, edge in ipairs(nodeInfo.visibleEdges or {}) do
        if PositiveInteger(edge.targetNode) then
            table.insert(edges, {
                targetNodeId = edge.targetNode,
                type = edge.type,
                visualStyle = edge.visualStyle,
                active = edge.isActive == true,
            })
        end
    end
    local activeRank = nodeInfo.activeEntry and tonumber(nodeInfo.activeEntry.rank) or 0
    local ranksPurchased = math.max(tonumber(nodeInfo.ranksPurchased) or 0, activeRank or 0)
    return {
        nodeId = nodeInfo.ID or nodeId,
        posX = nodeInfo.posX,
        posY = nodeInfo.posY,
        nodeType = nodeInfo.type,
        ranksPurchased = ranksPurchased,
        maxRanks = nodeInfo.maxRanks or 0,
        activeEntryId = nodeInfo.activeEntry and nodeInfo.activeEntry.entryID or nil,
        entries = entries,
        visibleEdges = edges,
        subTreeId = nodeInfo.subTreeID,
        subTreeActive = nodeInfo.subTreeActive == true,
    }
end

local function FirstNodeCurrency(configId, nodeId)
    if type(C_Traits.GetNodeCost) ~= "function" then return nil end
    local costs = C_Traits.GetNodeCost(configId, nodeId)
    return type(costs) == "table" and costs[1] and (costs[1].ID or costs[1].traitCurrencyID) or nil
end

local function CollectCombatTalentSnapshot(prev)
    if not C_ClassTalents or type(C_ClassTalents.GetActiveConfigID) ~= "function" or not C_Traits then
        return prev and prev.talents or nil
    end
    local configId = C_ClassTalents.GetActiveConfigID()
    local configInfo = configId and C_Traits.GetConfigInfo(configId) or nil
    if not configId or type(configInfo) ~= "table" or type(configInfo.treeIDs) ~= "table" then
        return prev and prev.talents or nil
    end

    local specId, specName, specIconFileID = CurrentSpecialization()
    local className = type(UnitClass) == "function" and UnitClass("player") or nil
    local trees = {}
    local capturedNodes = 0
    for _, treeId in ipairs(configInfo.treeIDs) do
        local currencies = C_Traits.GetTreeCurrencyInfo and C_Traits.GetTreeCurrencyInfo(configId, treeId, true) or {}
        local classCurrencyId = currencies and currencies[1] and currencies[1].traitCurrencyID or nil
        local specCurrencyId = currencies and currencies[2] and currencies[2].traitCurrencyID or nil
        local buckets = {
            class = { treeId = treeId, type = "class", name = className, nodes = {} },
            spec = { treeId = treeId, type = "spec", name = specName, nodes = {} },
        }
        local heroBuckets = {}
        for _, nodeId in ipairs(C_Traits.GetTreeNodes(treeId) or {}) do
            local node = SerializeTalentNode(configId, nodeId)
            if node then
                local bucket = nil
                if node.subTreeId then
                    bucket = heroBuckets[node.subTreeId]
                    if not bucket then
                        local subTreeInfo = C_Traits.GetSubTreeInfo and C_Traits.GetSubTreeInfo(configId, node.subTreeId) or nil
                        local iconAtlas = subTreeInfo and subTreeInfo.iconElementID or nil
                        local heroIconFileID = GetAtlasFileID(iconAtlas)
                        bucket = {
                            treeId = treeId,
                            subTreeId = node.subTreeId,
                            type = "hero",
                            name = subTreeInfo and subTreeInfo.name or nil,
                            description = subTreeInfo and subTreeInfo.description or nil,
                            iconAtlas = iconAtlas,
                            iconFileID = heroIconFileID,
                            iconPath = GetTexturePath(heroIconFileID),
                            active = subTreeInfo and subTreeInfo.isActive == true or node.subTreeActive,
                            nodes = {},
                        }
                        heroBuckets[node.subTreeId] = bucket
                    end
                else
                    local currencyId = FirstNodeCurrency(configId, nodeId)
                    if currencyId and currencyId == classCurrencyId then bucket = buckets.class end
                    if currencyId and currencyId == specCurrencyId then bucket = buckets.spec end
                end
                if bucket then
                    table.insert(bucket.nodes, node)
                    capturedNodes = capturedNodes + 1
                end
            end
        end
        if #buckets.class.nodes > 0 then table.insert(trees, buckets.class) end
        local orderedHeroBuckets = {}
        for _, heroBucket in pairs(heroBuckets) do
            if #heroBucket.nodes > 0 then table.insert(orderedHeroBuckets, heroBucket) end
        end
        table.sort(orderedHeroBuckets, function(left, right)
            if left.active ~= right.active then return left.active == true end
            return (left.subTreeId or 0) < (right.subTreeId or 0)
        end)
        for _, heroBucket in ipairs(orderedHeroBuckets) do table.insert(trees, heroBucket) end
        if #buckets.spec.nodes > 0 then table.insert(trees, buckets.spec) end
    end

    if capturedNodes == 0 then return prev and prev.talents or nil end
    local importString = C_Traits.GenerateImportString and C_Traits.GenerateImportString(configId) or nil
    return {
        configId = configId,
        loadoutName = configInfo.name,
        importString = importString ~= "" and importString or nil,
        specId = specId,
        specName = specName,
        specIconFileID = specIconFileID,
        specIconPath = GetTexturePath(specIconFileID),
        class = className,
        className = className,
        characterLevel = UnitLevel("player"),
        trees = trees,
    }
end

local function CollectOmniumSnapshot(prev)
    if not C_Traits or type(C_Traits.GetConfigIDBySystemID) ~= "function" then
        return prev and prev.omniumFolio or nil
    end
    local configId = C_Traits.GetConfigIDBySystemID(OMNIUM_TRAIT_SYSTEM_ID)
    local configInfo = configId and C_Traits.GetConfigInfo(configId) or nil
    if not configId or type(configInfo) ~= "table" then return prev and prev.omniumFolio or nil end
    local treeIds = type(configInfo.treeIDs) == "table" and configInfo.treeIDs or {}
    if #treeIds == 0 and C_Traits.GetTreeNodes(OMNIUM_FALLBACK_TREE_ID) then treeIds = { OMNIUM_FALLBACK_TREE_ID } end

    local trees = {}
    local capturedNodes = 0
    for _, treeId in ipairs(treeIds) do
        local tree = { treeId = treeId, type = "omnium", name = configInfo.name, nodes = {} }
        for _, nodeId in ipairs(C_Traits.GetTreeNodes(treeId) or {}) do
            local node = SerializeTalentNode(configId, nodeId)
            if node then table.insert(tree.nodes, node); capturedNodes = capturedNodes + 1 end
        end
        if #tree.nodes > 0 then table.insert(trees, tree) end
    end
    if capturedNodes == 0 then return prev and prev.omniumFolio or nil end
    return { systemId = OMNIUM_TRAIT_SYSTEM_ID, configId = configId, treeIds = treeIds, trees = trees }
end

local function HasArrayValues(value)
    return type(value) == "table" and next(value) ~= nil
end

local function FindVaultSlot(slots, target)
    for _, slot in ipairs(slots or {}) do
        if (target.index ~= nil and slot.index == target.index)
            or (target.threshold ~= nil and slot.threshold == target.threshold) then
            return slot
        end
    end
    return nil
end

local function PreserveVaultDetails(result, previous)
    if type(previous) ~= "table" or previous.weekKey ~= result.weekKey then return result end

    for _, bucketName in ipairs({ "raid", "dungeons", "world" }) do
        local currentBucket = result[bucketName]
        local previousBucket = previous[bucketName]
        if type(currentBucket) == "table" and type(previousBucket) == "table"
            and not HasArrayValues(currentBucket.slots) and HasArrayValues(previousBucket.slots) then
            result[bucketName] = previousBucket
        end
        currentBucket = result[bucketName]
        if type(currentBucket) == "table" and type(previousBucket) == "table" then
            for _, slot in ipairs(currentBucket.slots or {}) do
                local previousSlot = FindVaultSlot(previousBucket.slots, slot)
                if previousSlot then
                    if not slot.rewardItemLevel and type(previousSlot.rewardItemLevel) == "number"
                        and previousSlot.rewardItemLevel > 0 then
                        slot.rewardItemLevel = previousSlot.rewardItemLevel
                    end
                    if not slot.rewardUpgradeTrack and type(previousSlot.rewardUpgradeTrack) == "string"
                        and previousSlot.rewardUpgradeTrack ~= "" then
                        slot.rewardUpgradeTrack = previousSlot.rewardUpgradeTrack
                    end
                end
            end
        end
    end

    if type(result.raid) == "table" and type(previous.raid) == "table" then
        for _, slot in ipairs(result.raid.slots or {}) do
            if not HasArrayValues(slot.encounters) then
                local previousSlot = FindVaultSlot(previous.raid.slots, slot)
                if previousSlot and HasArrayValues(previousSlot.encounters) then
                    slot.encounters = previousSlot.encounters
                end
            end
        end
    end

    if type(result.dungeons) == "table" and type(previous.dungeons) == "table"
        and not HasArrayValues(result.dungeons.topRuns) and HasArrayValues(previous.dungeons.topRuns) then
        result.dungeons.topRuns = previous.dungeons.topRuns
    end

    if type(result.world) == "table" and type(previous.world) == "table"
        and not HasArrayValues(result.world.tierProgress) and HasArrayValues(previous.world.tierProgress) then
        result.world.tierProgress = previous.world.tierProgress
    end

    return result
end

local function GetVaultData(prev, reason)
    local previousVault = prev and prev.vault or nil
    local result = {
        weekKey = GetWeeklyResetKey(),
        hasAvailableRewards = C_WeeklyRewards.HasAvailableRewards() == true,
        raid = { unlocked = 0, slots = {} },
        dungeons = { unlocked = 0, slots = {} },
        world = { unlocked = 0, slots = {} },
    }

    -- WoW tears these APIs down before PLAYER_LOGOUT. Gameplay changes have
    -- already emitted their own events, so retain the last complete snapshot.
    if reason == "PLAYER_LOGOUT" and previousVault and previousVault.weekKey == result.weekKey then
        return previousVault
    end

    local typeMap = {
        [Enum.WeeklyRewardChestThresholdType.Raid] = "raid",
        [Enum.WeeklyRewardChestThresholdType.Activities] = "dungeons",
        [Enum.WeeklyRewardChestThresholdType.World] = "world",
    }

    local activities = C_WeeklyRewards.GetActivities()
    if not activities then return PreserveVaultDetails(result, previousVault) end

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

            if unlocked and type(C_WeeklyRewards.GetExampleRewardItemHyperlinks) == "function" and C_Item then
                local rewardOK, currentRewardLink = pcall(
                    C_WeeklyRewards.GetExampleRewardItemHyperlinks,
                    activity.id
                )
                if rewardOK and currentRewardLink then
                    if type(C_Item.GetDetailedItemLevelInfo) == "function" then
                        local itemLevelOK, rewardItemLevel = pcall(
                            C_Item.GetDetailedItemLevelInfo,
                            currentRewardLink
                        )
                        if itemLevelOK and type(rewardItemLevel) == "number" and rewardItemLevel > 0 then
                            slot.rewardItemLevel = rewardItemLevel
                        end
                    end
                    if type(C_Item.GetItemUpgradeInfo) == "function" then
                        local upgradeOK, upgradeInfo = pcall(C_Item.GetItemUpgradeInfo, currentRewardLink)
                        if upgradeOK and type(upgradeInfo) == "table"
                            and type(upgradeInfo.trackString) == "string"
                            and upgradeInfo.trackString ~= "" then
                            slot.rewardUpgradeTrack = upgradeInfo.trackString
                        end
                    end
                end
            end

            if bucketName == "raid" and type(C_WeeklyRewards.GetActivityEncounterInfo) == "function" then
                local encountersOK, encounters = pcall(C_WeeklyRewards.GetActivityEncounterInfo, activity.type, activity.index)
                if encountersOK and type(encounters) == "table" then
                    slot.encounters = {}
                    for _, encounter in ipairs(encounters) do
                        local encounterName = nil
                        local instanceName = nil
                        if type(EJ_GetEncounterInfo) == "function" then
                            local encounterOK, name = pcall(EJ_GetEncounterInfo, encounter.encounterID)
                            if encounterOK then encounterName = name end
                        end
                        if type(EJ_GetInstanceInfo) == "function" then
                            local instanceOK, name = pcall(EJ_GetInstanceInfo, encounter.instanceID)
                            if instanceOK then instanceName = name end
                        end
                        table.insert(slot.encounters, {
                            encounterID = encounter.encounterID,
                            bestDifficulty = encounter.bestDifficulty or 0,
                            uiOrder = encounter.uiOrder,
                            instanceID = encounter.instanceID,
                            name = encounterName,
                            instanceName = instanceName,
                        })
                    end
                end
            end

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

    result.dungeons.topRuns = {}
    if C_MythicPlus and type(C_MythicPlus.GetRunHistory) == "function" then
        local historyOK, runHistory = pcall(C_MythicPlus.GetRunHistory, false, true)
        if historyOK and type(runHistory) == "table" then
            table.sort(runHistory, function(left, right)
                if (left.level or 0) == (right.level or 0) then
                    return (left.mapChallengeModeID or 0) < (right.mapChallengeModeID or 0)
                end
                return (left.level or 0) > (right.level or 0)
            end)
            for _, run in ipairs(runHistory) do
                local mapName = nil
                if C_ChallengeMode and type(C_ChallengeMode.GetMapUIInfo) == "function" then
                    local mapOK, name = pcall(C_ChallengeMode.GetMapUIInfo, run.mapChallengeModeID)
                    if mapOK then mapName = name end
                end
                table.insert(result.dungeons.topRuns, {
                    level = run.level or 0,
                    mapChallengeModeID = run.mapChallengeModeID,
                    name = mapName,
                })
            end
        end
    end

    result.world.tierProgress = {}
    if type(C_WeeklyRewards.GetSortedProgressForActivity) == "function" then
        local progressOK, tierProgress = pcall(
            C_WeeklyRewards.GetSortedProgressForActivity,
            Enum.WeeklyRewardChestThresholdType.World,
            true
        )
        if progressOK and type(tierProgress) == "table" then
            for _, progress in ipairs(tierProgress) do
                table.insert(result.world.tierProgress, {
                    activityTierID = progress.activityTierID,
                    difficulty = progress.difficulty or 0,
                    numPoints = progress.numPoints or 0,
                })
            end
        end
    end

    return PreserveVaultDetails(result, previousVault)
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

local function CaptureSnapshotSafely(collector, prev, field)
    local ok, snapshot = pcall(collector, prev)
    if ok and snapshot ~= nil then return snapshot end
    return prev and prev[field] or nil
end

local function SaveCharacterData(reason, updateSeason, refreshKeystoneLoot)
    KeystoneSyncDB = KeystoneSyncDB or {}
    EnsureSavedVariablesInstanceId()

    if UnitLevel("player") < MAX_LEVEL then return end

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
    KeystoneSyncDB[key].vault = GetVaultData(prev, reason)
    KeystoneSyncDB[key].preyHunts = GetPreyHunts(prev)
    KeystoneSyncDB[key].currencies = GetCurrencyData(prev, reason == "PLAYER_LOGOUT")
    KeystoneSyncDB[key].money = GetMoneyData(prev, reason)
    local shouldCaptureSnapshots = reason ~= "PLAYER_LOGOUT" and (
        reason == "PLAYER_LOGIN"
            or reason == "MANUAL_COMMAND"
            or reason == "SNAPSHOT_REFRESH"
            or not (prev and prev.equipment)
            or not (prev and prev.talents)
            or not (prev and prev.omniumFolio)
    )
    if shouldCaptureSnapshots then
        KeystoneSyncDB[key].equipment = CaptureSnapshotSafely(GetEquipmentData, prev, "equipment")
        KeystoneSyncDB[key].talents = CaptureSnapshotSafely(CollectCombatTalentSnapshot, prev, "talents")
        KeystoneSyncDB[key].omniumFolio = CaptureSnapshotSafely(CollectOmniumSnapshot, prev, "omniumFolio")
    end
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

local function ScheduleSnapshotRefresh()
    if snapshotRefreshPending or not C_Timer or type(C_Timer.After) ~= "function" then return end
    snapshotRefreshPending = true
    C_Timer.After(SNAPSHOT_REFRESH_DELAY_SECONDS, function()
        snapshotRefreshPending = false
        SaveCharacterData("SNAPSHOT_REFRESH", false, false)
    end)
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

frame:SetScript("OnEvent", function(self, event, ...)
    if event == "PLAYER_LOGIN" then
        personalBankAccessible = false
        SaveCharacterData(event, false, false)
        StartKeystoneLootIntegration()
        ScheduleSeasonCapture()
    elseif event == "PLAYER_LOGOUT" then
        pendingSeasonCaptureKey = nil
        personalBankAccessible = false
        -- Inventory APIs can already be torn down here. Preserve the last
        -- KeystoneLoot ownership snapshot captured by gameplay events.
        SaveCharacterData(event, false, false)
        StopKeystoneLootIntegration()
    elseif event == "BANKFRAME_OPENED" then
        personalBankAccessible = true
        SaveCharacterData(event, false)
    elseif event == "BANKFRAME_CLOSED" then
        personalBankAccessible = false
        SaveCharacterData(event, false)
    elseif event == "CHALLENGE_MODE_COMPLETED" or event == "MYTHIC_PLUS_NEW_WEEKLY_RECORD" then
        SaveCharacterData(event, true)
    elseif event == "PLAYER_EQUIPMENT_CHANGED"
        or (event == "UNIT_INVENTORY_CHANGED" and (...) == "player")
        or event == "TRAIT_CONFIG_LIST_UPDATED"
        or event == "TRAIT_CONFIG_UPDATED"
        or event == "ACTIVE_COMBAT_CONFIG_CHANGED"
        or event == "PLAYER_SPECIALIZATION_CHANGED"
        or event == "TRAIT_SUB_TREE_CHANGED" then
        ScheduleSnapshotRefresh()
    else
        SaveCharacterData(event, false)
    end
end)

SLASH_KEYSTONESYNC1 = "/ksync"
SlashCmdList["KEYSTONESYNC"] = function(message)
    local keystoneLootSnapshot = SaveCharacterData("MANUAL_COMMAND", true)
    local command = type(message) == "string" and string.lower(string.match(message, "^%s*(.-)%s*$")) or ""
    if command == "kl" or command == "keystoneloot" then
        PrintKeystoneLootFavoriteDiagnostics(keystoneLootSnapshot)
        return
    end
    PrintCurrentKeystone()
    PrintKeystoneLootDiagnostic(keystoneLootSnapshot)
end
