local _, KeystoneSync = ...

KeystoneSync.KeystoneLootIntegration = {}

local Integration = KeystoneSync.KeystoneLootIntegration
local SUPPORTED_API_VERSION = 2
local FAVORITES_DEBOUNCE_SECONDS = 0.1
local PREVIEW_CAPTURE_MAX_AGE_SECONDS = 30
local CALLBACK_OWNER = {}
local ITEM_QUALITY_TYPES = {
    [0] = "POOR",
    [1] = "COMMON",
    [2] = "UNCOMMON",
    [3] = "RARE",
    [4] = "EPIC",
    [5] = "LEGENDARY",
    [6] = "ARTIFACT",
    [7] = "HEIRLOOM",
}
local EXPECTED_API_METHODS = {
    "GetVersion",
    "IsReady",
    "GetCurrentCharacterKey",
    "GetFavorites",
    "GetItemSource",
    "GetSourceInfo",
    "GetItemInfo",
    "RegisterCallback",
    "UnregisterCallback",
}

local function SafeCall(object, methodName, ...)
    if type(object) ~= "table" or type(object[methodName]) ~= "function" then
        return false
    end

    return pcall(object[methodName], object, ...)
end

local function IsKeystoneLootInstalled(api)
    if type(api) == "table" then
        return true
    end

    if not C_AddOns or type(C_AddOns.GetAddOnInfo) ~= "function" then
        return false
    end

    local ok, name = pcall(C_AddOns.GetAddOnInfo, "KeystoneLoot")
    return ok and name ~= nil
end

local function HasExpectedApi(api)
    if type(api) ~= "table" then
        return false
    end

    for _, methodName in ipairs(EXPECTED_API_METHODS) do
        if type(api[methodName]) ~= "function" then
            return false
        end
    end
    return true
end

local function CopyList(values)
    if type(values) ~= "table" then
        return nil
    end

    local result = {}
    for _, value in ipairs(values) do
        table.insert(result, value)
    end
    return result
end

local function IsInteger(value)
    return type(value) == "number" and value == math.floor(value)
end

local function NormalizeBonusIds(values)
    if type(values) ~= "table" then
        return nil
    end

    local result = {}
    for _, rawValue in ipairs(values) do
        local value = tonumber(rawValue)
        if not IsInteger(value) or value < 0 then
            return nil
        end
        table.insert(result, value)
    end
    return result
end

local function VariantKey(bonusIds)
    if type(bonusIds) ~= "table" or #bonusIds == 0 then
        return "base"
    end

    local normalized = CopyList(bonusIds)
    table.sort(normalized)
    local parts = {}
    for _, bonusId in ipairs(normalized) do
        table.insert(parts, tostring(bonusId))
    end
    return "bonus:" .. table.concat(parts, ",")
end

local function SplitItemPayload(payload)
    local fields = {}
    local startIndex = 1
    for index = 1, #payload do
        if string.sub(payload, index, index) == ":" then
            table.insert(fields, string.sub(payload, startIndex, index - 1))
            startIndex = index + 1
        end
    end
    table.insert(fields, string.sub(payload, startIndex))
    return fields
end

local function ParseExactItemLink(itemLink, expectedItemId, expectedSpecId)
    if type(itemLink) ~= "string" then
        return nil
    end

    local payload = string.match(itemLink, "|Hitem:([^|]+)|h") or string.match(itemLink, "^item:(.*)$")
    if not payload then
        return nil
    end

    local fields = SplitItemPayload(payload)
    local itemId = tonumber(fields[1])
    local linkLevel = tonumber(fields[9])
    local specId = tonumber(fields[10])
    local modifiersMask = fields[11] == "" and 0 or tonumber(fields[11])
    local itemContext = fields[12] == "" and 0 or tonumber(fields[12])
    local numBonusIds = tonumber(fields[13])
    if not IsInteger(itemId) or itemId <= 0
        or (expectedItemId and itemId ~= expectedItemId)
        or not IsInteger(linkLevel) or linkLevel < 0
        or not IsInteger(specId) or specId < 0
        or (expectedSpecId and specId ~= expectedSpecId)
        or not IsInteger(modifiersMask) or modifiersMask < 0
        or not IsInteger(itemContext) or itemContext < 0
        or not IsInteger(numBonusIds) or numBonusIds <= 0 or numBonusIds > 64
        or #fields < 13 + numBonusIds then
        return nil
    end

    local bonusIds = {}
    for index = 1, numBonusIds do
        local bonusId = tonumber(fields[13 + index])
        if not IsInteger(bonusId) or bonusId <= 0 then
            return nil
        end
        table.insert(bonusIds, bonusId)
    end

    return {
        itemId = itemId,
        linkLevel = linkLevel,
        specId = specId,
        modifiersMask = modifiersMask,
        itemContext = itemContext,
        numBonusIds = numBonusIds,
        bonusIds = bonusIds,
        itemLink = itemLink,
    }
end

local function CurrentClock()
    if type(GetTime) == "function" then
        local ok, value = pcall(GetTime)
        if ok and type(value) == "number" then
            return value
        end
    end
    return type(time) == "function" and time() or 0
end

local function CaptureKey(characterKey, sourceId, specId, itemId)
    return table.concat({ tostring(characterKey), tostring(sourceId), tostring(specId), tostring(itemId) }, "|")
end

local function ReadSelectedContext()
    local charDB = type(KeystoneLootCharDB) == "table" and KeystoneLootCharDB or nil
    local filters = charDB and type(charDB.filters) == "table" and charDB.filters or nil
    local ui = charDB and type(charDB.ui) == "table" and charDB.ui or nil
    local selectedTab = ui and ui.selectedTab or nil
    local context = {
        selectedContext = selectedTab == "dungeons" and "dungeon"
            or selectedTab == "raids" and "raid"
            or selectedTab,
        selectedSpecId = filters and tonumber(filters.specId) or nil,
        selectedClassId = filters and tonumber(filters.classId) or nil,
        selectedSlotId = filters and tonumber(filters.slotId) or nil,
    }

    if selectedTab == "dungeons" and filters and type(filters.dungeon) == "table" then
        context.selectedTrack = filters.dungeon.track
        context.selectedRank = tonumber(filters.dungeon.rank)
    elseif selectedTab == "raids" and filters and type(filters.raid) == "table" then
        context.selectedDifficulty = filters.raid.difficulty
        context.selectedRank = tonumber(filters.raid.rank)
    end
    return context
end

local function CopyFields(target, source)
    for key, value in pairs(source) do
        target[key] = value
    end
end

local function PreviewContextMatches(left, right)
    if type(left) ~= "table" or type(right) ~= "table" then
        return false
    end
    for _, key in ipairs({
        "selectedContext", "selectedTrack", "selectedDifficulty", "selectedRank", "selectedSpecId",
    }) do
        if left[key] ~= right[key] then
            return false
        end
    end
    return true
end

-- Explicit Favorite bonus IDs already identify a real variant. This builder is never
-- called for a base Favorite, because base item metadata is not exact Favorite metadata.
local function BuildFavoriteItemLink(itemId, specId, bonusIds)
    local playerLevel = type(UnitLevel) == "function" and tonumber(UnitLevel("player")) or 0
    local ids = type(bonusIds) == "table" and bonusIds or {}
    return string.format(
        "item:%d:%s:::%d:%d:::%d:%s",
        itemId,
        "::::",
        playerLevel or 0,
        specId,
        #ids,
        table.concat(ids, ":")
    )
end

local function ReadVariantMetadata(itemLink)
    if type(C_Item) ~= "table" then
        return nil, nil
    end

    local itemLevel = nil
    if type(C_Item.GetDetailedItemLevelInfo) == "function" then
        local ok, value = pcall(C_Item.GetDetailedItemLevelInfo, itemLink)
        value = ok and tonumber(value) or nil
        if value and IsInteger(value) and value > 0 then
            itemLevel = value
        end
    end

    local qualityType = nil
    if type(C_Item.GetItemInfo) == "function" then
        local result = { pcall(C_Item.GetItemInfo, itemLink) }
        if result[1] then
            qualityType = ITEM_QUALITY_TYPES[tonumber(result[4])]
        end
    end
    return itemLevel, qualityType
end

local function NormalizeFavorite(integration, api, entry, characterKey)
    if type(entry) ~= "table" then
        return nil
    end

    local itemId = tonumber(entry.itemId)
    local specId = tonumber(entry.specId)
    local tier = tonumber(entry.tier)
    local sourceId = entry.sourceId
    if type(sourceId) == "number" then
        sourceId = tonumber(sourceId)
    elseif type(sourceId) ~= "string" then
        sourceId = nil
    end

    if not itemId or not specId or not tier or sourceId == nil then
        return nil
    end

    local sourceType = nil
    local sourceOK, sourceInfo = SafeCall(api, "GetSourceInfo", sourceId)
    if sourceOK and type(sourceInfo) == "table" and type(sourceInfo.type) == "string" then
        sourceType = sourceInfo.type
    end

    local slotId = nil
    local icon = nil
    local itemOK, itemInfo = SafeCall(api, "GetItemInfo", itemId)
    if itemOK and type(itemInfo) == "table" then
        slotId = tonumber(itemInfo.slotId)
        icon = tonumber(itemInfo.icon)
    end

    local bonusIds = NormalizeBonusIds(entry.bonusIds)
    if type(bonusIds) == "table" and #bonusIds == 0 then
        bonusIds = nil
    end
    local capturedVariant = nil
    if not bonusIds and type(integration.GetCapturedVariant) == "function" then
        capturedVariant = integration:GetCapturedVariant(characterKey, sourceId, specId, itemId)
        if capturedVariant then
            bonusIds = NormalizeBonusIds(capturedVariant.bonusIds)
            if type(bonusIds) ~= "table" or #bonusIds == 0 then
                bonusIds = nil
                capturedVariant = nil
            end
        end
    end
    local variantKey = VariantKey(bonusIds)
    local favorite = {
        sourceId = sourceId,
        sourceType = sourceType,
        specId = specId,
        itemId = itemId,
        tier = tier,
        slotId = slotId,
        icon = icon,
        bonusIds = bonusIds,
        gems = CopyList(entry.gems),
        enchant = tonumber(entry.enchant),
        variantKey = variantKey,
    }

    if capturedVariant then
        if capturedVariant.metadataComplete ~= true and type(integration.ResolveCapturedVariant) == "function" then
            integration:ResolveCapturedVariant(api, capturedVariant)
        end
        favorite.itemLevel = capturedVariant.itemLevel
        favorite.qualityType = capturedVariant.qualityType
        return favorite
    end

    -- A normal KeystoneLoot UI Favorite usually has no bonus IDs. Resolving the bare
    -- item ID here would produce sparse base metadata (for example ilvl 28 / RARE),
    -- which must never be labeled as the exact selected Favorite variant.
    if not bonusIds then
        return favorite
    end

    local cacheKey = tostring(itemId) .. "\0" .. tostring(specId) .. "\0" .. variantKey
    local metadata = integration.variantMetadata and integration.variantMetadata[cacheKey]
    if metadata then
        favorite.itemLevel = metadata.itemLevel
        favorite.qualityType = metadata.qualityType
        if metadata.complete or metadata.pending then
            return favorite
        end
    end

    local itemLink = BuildFavoriteItemLink(itemId, specId, bonusIds)
    local itemLevel, qualityType = ReadVariantMetadata(itemLink)
    if itemLevel and qualityType then
        integration.variantMetadata[cacheKey] = {
            complete = true,
            itemLevel = itemLevel,
            qualityType = qualityType,
        }
        favorite.itemLevel = itemLevel
        favorite.qualityType = qualityType
        return favorite
    end

    if not metadata and type(Item) == "table" and type(Item.CreateFromItemLink) == "function" then
        integration.variantMetadata[cacheKey] = {
            pending = true,
            itemLevel = itemLevel,
            qualityType = qualityType,
        }
        favorite.itemLevel = itemLevel
        favorite.qualityType = qualityType
        local generation = integration.generation
        local keystoneSyncKey = integration:GetKeystoneSyncKey()
        local ok, item = pcall(Item.CreateFromItemLink, itemLink)
        if ok and type(item) == "table" and type(item.ContinueOnItemLoad) == "function" then
            local callbackOK = pcall(item.ContinueOnItemLoad, item, function()
                if not integration.active or integration.generation ~= generation then
                    return
                end
                if integration:GetKeystoneSyncKey() ~= keystoneSyncKey then
                    return
                end
                if integration:GetKeystoneLootCharacterKey(api) ~= characterKey then
                    return
                end
                local resolvedLevel, resolvedQuality = ReadVariantMetadata(itemLink)
                integration.variantMetadata[cacheKey] = {
                    complete = true,
                    itemLevel = resolvedLevel,
                    qualityType = resolvedQuality,
                }
                integration:RefreshCurrent()
            end)
            if not callbackOK then
                integration.variantMetadata[cacheKey] = {
                    complete = true, itemLevel = itemLevel, qualityType = qualityType,
                }
            end
        else
            integration.variantMetadata[cacheKey] = {
                complete = true, itemLevel = itemLevel, qualityType = qualityType,
            }
        end
    elseif not metadata then
        integration.variantMetadata[cacheKey] = {
            complete = true, itemLevel = itemLevel, qualityType = qualityType,
        }
        favorite.itemLevel = itemLevel
        favorite.qualityType = qualityType
    end

    return favorite
end

local function NormalizeVoidcore()
    local result = {
        checked = false,
        usedItems = {},
    }

    if type(KeystoneLootCharDB) ~= "table" then
        return result
    end

    result.checked = KeystoneLootCharDB.voidcoreChecked == true
    if type(KeystoneLootCharDB.voidcore) ~= "table" then
        return result
    end

    for rawItemId, used in pairs(KeystoneLootCharDB.voidcore) do
        local itemId = tonumber(rawItemId)
        if used == true and itemId and itemId > 0 then
            table.insert(result.usedItems, itemId)
        end
    end
    table.sort(result.usedItems)
    return result
end

function Integration:WriteCurrent(snapshot)
    if type(self.getKeystoneSyncKey) ~= "function" then
        return nil
    end

    local keyOK, key = pcall(self.getKeystoneSyncKey)
    if not keyOK or type(key) ~= "string" or key == "" then
        return nil
    end
    if type(KeystoneSyncDB) ~= "table" or type(KeystoneSyncDB[key]) ~= "table" then
        return nil
    end

    KeystoneSyncDB[key].keystoneLoot = snapshot
    self.lastSnapshot = snapshot
    return snapshot
end

function Integration:GetKeystoneSyncKey()
    if type(self.getKeystoneSyncKey) ~= "function" then
        return nil
    end

    local ok, key = pcall(self.getKeystoneSyncKey)
    if ok and type(key) == "string" and key ~= "" then
        return key
    end
    return nil
end

function Integration:GetKeystoneLootCharacterKey(api)
    local ok, key = SafeCall(api, "GetCurrentCharacterKey")
    if ok and type(key) == "string" and key ~= "" then
        return key
    end
    return nil
end

function Integration:GetCaptureStore(create)
    local keystoneSyncKey = self:GetKeystoneSyncKey()
    local record = keystoneSyncKey and type(KeystoneSyncDB) == "table" and KeystoneSyncDB[keystoneSyncKey] or nil
    if type(record) ~= "table" then
        return nil
    end
    if type(record.keystoneLootFavoriteCaptures) ~= "table" then
        if not create then
            return nil
        end
        record.keystoneLootFavoriteCaptures = {}
    end
    return record.keystoneLootFavoriteCaptures
end

function Integration:GetCapturedVariant(characterKey, sourceId, specId, itemId)
    local store = self:GetCaptureStore(false)
    local capture = store and store[CaptureKey(characterKey, sourceId, specId, itemId)] or nil
    if type(capture) ~= "table" or capture.characterKey ~= characterKey
        or capture.sourceId ~= sourceId or tonumber(capture.specId) ~= specId
        or tonumber(capture.itemId) ~= itemId then
        return nil
    end
    local bonusIds = NormalizeBonusIds(capture.bonusIds)
    if type(bonusIds) ~= "table" or #bonusIds == 0 then
        return nil
    end
    return capture
end

function Integration:RememberTooltipPreview(tooltip)
    if not self.active or type(tooltip) ~= "table" or tooltip.KeystoneLootOwned ~= true
        or type(tooltip.GetItem) ~= "function" then
        return
    end
    local result = { pcall(tooltip.GetItem, tooltip) }
    local itemLink = result[1] and result[3] or nil
    local parsed = ParseExactItemLink(itemLink)
    if not parsed then
        return
    end
    self.recentPreview = {
        itemId = parsed.itemId,
        specId = parsed.specId,
        itemLink = itemLink,
        seenAt = CurrentClock(),
        context = ReadSelectedContext(),
    }
end

function Integration:RegisterTooltipCapture()
    if self.tooltipHookRegistered then
        return
    end
    if type(TooltipDataProcessor) ~= "table" or type(TooltipDataProcessor.AddTooltipPostCall) ~= "function"
        or type(Enum) ~= "table" or type(Enum.TooltipDataType) ~= "table"
        or Enum.TooltipDataType.Item == nil then
        return
    end

    local integration = self
    local ok = pcall(TooltipDataProcessor.AddTooltipPostCall, Enum.TooltipDataType.Item, function(tooltip)
        integration:RememberTooltipPreview(tooltip)
    end)
    if ok then
        self.tooltipHookRegistered = true
    end
end

function Integration:PersistCapturedVariant(api, characterKey, itemId, specId)
    if not self.active or self:GetKeystoneLootCharacterKey(api) ~= characterKey then
        return
    end
    local preview = self.recentPreview
    local age = preview and CurrentClock() - preview.seenAt or nil
    if not preview then
        return
    end
    if type(age) ~= "number" or age < 0 or age > PREVIEW_CAPTURE_MAX_AGE_SECONDS
        or preview.itemId ~= itemId then
        self.recentPreview = nil
        return
    end
    if preview.specId ~= specId then
        return
    end

    self.recentPreview = nil
    local sourceOK, sourceId = SafeCall(api, "GetItemSource", itemId)
    if not sourceOK or (type(sourceId) ~= "number" and type(sourceId) ~= "string") then
        return
    end
    local context = ReadSelectedContext()
    if not PreviewContextMatches(preview.context, context) then
        return
    end
    local parsed = ParseExactItemLink(preview.itemLink, itemId, specId)
    if not parsed then
        return
    end

    local store = self:GetCaptureStore(true)
    if not store then
        return
    end
    local captureKey = CaptureKey(characterKey, sourceId, specId, itemId)
    local capture = {
        characterKey = characterKey,
        sourceId = sourceId,
        specId = specId,
        itemId = itemId,
        bonusIds = CopyList(parsed.bonusIds),
        variantKey = VariantKey(parsed.bonusIds),
        itemString = parsed.itemLink,
        linkLevel = parsed.linkLevel,
        modifiersMask = parsed.modifiersMask,
        itemContext = parsed.itemContext,
        numBonusIds = parsed.numBonusIds,
        capturedAt = type(time) == "function" and time() or 0,
        metadataSource = "captured_variant",
    }
    CopyFields(capture, context)

    capture.metadataComplete = false
    store[captureKey] = capture
    self:ResolveCapturedVariant(api, capture)
end

function Integration:ResolveCapturedVariant(api, capture)
    if type(capture) ~= "table" or capture.metadataComplete == true or type(capture.itemString) ~= "string" then
        return
    end
    local captureKey = CaptureKey(capture.characterKey, capture.sourceId, capture.specId, capture.itemId)
    self.captureResolutionPending = self.captureResolutionPending or {}
    if self.captureResolutionPending[captureKey] then
        return
    end

    local itemLevel, qualityType = ReadVariantMetadata(capture.itemString)
    capture.itemLevel = itemLevel
    capture.qualityType = qualityType
    if itemLevel ~= nil and qualityType ~= nil then
        capture.metadataComplete = true
        return
    end
    if type(Item) ~= "table" or type(Item.CreateFromItemLink) ~= "function" then
        capture.metadataComplete = true
        return
    end

    local generation = self.generation
    local keystoneSyncKey = self:GetKeystoneSyncKey()
    self.captureResolutionPending[captureKey] = true
    local ok, item = pcall(Item.CreateFromItemLink, capture.itemString)
    if not ok or type(item) ~= "table" or type(item.ContinueOnItemLoad) ~= "function" then
        self.captureResolutionPending[captureKey] = nil
        capture.metadataComplete = true
        return
    end
    local callbackOK = pcall(item.ContinueOnItemLoad, item, function()
        self.captureResolutionPending[captureKey] = nil
        if not self.active or self.generation ~= generation
            or self:GetKeystoneSyncKey() ~= keystoneSyncKey
            or self:GetKeystoneLootCharacterKey(api) ~= capture.characterKey then
            return
        end
        local currentStore = self:GetCaptureStore(false)
        local current = currentStore and currentStore[captureKey] or nil
        if current ~= capture then
            return
        end
        local resolvedLevel, resolvedQuality = ReadVariantMetadata(capture.itemString)
        current.itemLevel = resolvedLevel
        current.qualityType = resolvedQuality
        current.metadataComplete = true
        self:RefreshCurrent()
    end)
    if not callbackOK then
        self.captureResolutionPending[captureKey] = nil
        capture.metadataComplete = true
    end
end

function Integration:RemoveCapturedVariants(characterKey, itemId, specId)
    local store = self:GetCaptureStore(false)
    if not store then
        return
    end
    for key, capture in pairs(store) do
        if type(capture) == "table" and capture.characterKey == characterKey
            and tonumber(capture.itemId) == itemId
            and (specId == 0 or tonumber(capture.specId) == specId) then
            store[key] = nil
        end
    end
end

function Integration:ClearCapturedVariants(characterKey)
    local store = self:GetCaptureStore(false)
    if not store then
        return
    end
    for key, capture in pairs(store) do
        if type(capture) == "table" and capture.characterKey == characterKey then
            store[key] = nil
        end
    end
end

function Integration:ScheduleRefresh(eventCharacterKey)
    if not self.active or self.refreshPending then
        return
    end
    if not C_Timer or type(C_Timer.After) ~= "function" then
        return
    end

    local api = self.callbackApi
    local keystoneLootKey = self:GetKeystoneLootCharacterKey(api)
    if not keystoneLootKey or eventCharacterKey ~= keystoneLootKey then
        return
    end

    local keystoneSyncKey = self:GetKeystoneSyncKey()
    if not keystoneSyncKey then
        return
    end

    local generation = self.generation
    self.refreshPending = true
    self.pendingGeneration = generation
    C_Timer.After(FAVORITES_DEBOUNCE_SECONDS, function()
        if self.pendingGeneration == generation then
            self.refreshPending = false
            self.pendingGeneration = nil
        end
        if not self.active or self.generation ~= generation then
            return
        end
        if self:GetKeystoneSyncKey() ~= keystoneSyncKey then
            return
        end
        if self:GetKeystoneLootCharacterKey(api) ~= keystoneLootKey then
            return
        end

        self:RefreshCurrent()
    end)
end

function Integration:Start(getKeystoneSyncKey)
    if self.active then
        self:Stop()
    end

    self.getKeystoneSyncKey = getKeystoneSyncKey
    self.generation = (self.generation or 0) + 1
    self.active = true
    self.refreshPending = false
    self.pendingGeneration = nil
    self.variantMetadata = {}
    self.captureResolutionPending = {}
    self.recentPreview = nil
    self:RegisterTooltipCapture()

    local api = KeystoneLootAPI
    self.callbackApi = type(api) == "table" and api or nil

    local readyDelivered = false
    local versionOK, apiVersion = SafeCall(api, "GetVersion")
    local canRegister = versionOK
        and tonumber(apiVersion) == SUPPORTED_API_VERSION
        and HasExpectedApi(api)

    if canRegister then
        local generation = self.generation
        self.readyCallback = function()
            if not self.active or self.generation ~= generation then
                return
            end
            readyDelivered = true
            self:RefreshCurrent()
        end
        self.favoritesChangedCallback = function(_, characterKey)
            if not self.active or self.generation ~= generation then
                return
            end
            self:ScheduleRefresh(characterKey)
        end
        self.favoriteAddedCallback = function(_, characterKey, itemId, specId)
            if not self.active or self.generation ~= generation then
                return
            end
            itemId = tonumber(itemId)
            specId = tonumber(specId)
            if type(characterKey) ~= "string" or not IsInteger(itemId) or itemId <= 0
                or not IsInteger(specId) or specId <= 0 then
                return
            end
            self:PersistCapturedVariant(api, characterKey, itemId, specId)
        end
        self.favoriteRemovedCallback = function(_, characterKey, itemId, specId)
            if not self.active or self.generation ~= generation then
                return
            end
            itemId = tonumber(itemId)
            specId = tonumber(specId)
            if type(characterKey) ~= "string" or not IsInteger(itemId) or itemId <= 0
                or not IsInteger(specId) or specId < 0 then
                return
            end
            self:RemoveCapturedVariants(characterKey, itemId, specId)
        end
        self.favoritesImportedCallback = function(_, characterKey)
            if not self.active or self.generation ~= generation or type(characterKey) ~= "string" then
                return
            end
            self:ClearCapturedVariants(characterKey)
        end

        SafeCall(api, "RegisterCallback", "READY", self.readyCallback, CALLBACK_OWNER)
        SafeCall(api, "RegisterCallback", "FAVORITE_ADDED", self.favoriteAddedCallback, CALLBACK_OWNER)
        SafeCall(api, "RegisterCallback", "FAVORITE_REMOVED", self.favoriteRemovedCallback, CALLBACK_OWNER)
        SafeCall(api, "RegisterCallback", "FAVORITES_IMPORTED", self.favoritesImportedCallback, CALLBACK_OWNER)
        SafeCall(api, "RegisterCallback", "FAVORITES_CHANGED", self.favoritesChangedCallback, CALLBACK_OWNER)
    end

    if readyDelivered then
        return self.lastSnapshot
    end
    return self:RefreshCurrent()
end

function Integration:RefreshCurrent()
    local api = KeystoneLootAPI
    local installed = IsKeystoneLootInstalled(api)
    if type(api) ~= "table" then
        return self:WriteCurrent({
            state = installed and "installed_not_ready" or "not_installed",
            installed = installed,
            supported = false,
            favorites = {},
        })
    end

    local versionOK, apiVersion, addonVersion = SafeCall(api, "GetVersion")
    apiVersion = versionOK and tonumber(apiVersion) or nil
    addonVersion = versionOK and addonVersion or nil
    if apiVersion ~= SUPPORTED_API_VERSION then
        return self:WriteCurrent({
            state = "unsupported_api",
            installed = true,
            supported = false,
            apiVersion = apiVersion,
            addonVersion = addonVersion,
            favorites = {},
        })
    end

    if not HasExpectedApi(api) then
        return self:WriteCurrent({
            state = "unsupported_api",
            installed = true,
            supported = false,
            apiVersion = apiVersion,
            addonVersion = addonVersion,
            favorites = {},
        })
    end

    local readyOK, ready = SafeCall(api, "IsReady")
    if not readyOK or ready ~= true then
        return self:WriteCurrent({
            state = "installed_not_ready",
            installed = true,
            supported = false,
            apiVersion = apiVersion,
            addonVersion = addonVersion,
            favorites = {},
        })
    end

    local characterOK, characterKey = SafeCall(api, "GetCurrentCharacterKey")
    if not characterOK or type(characterKey) ~= "string" or characterKey == "" then
        return self:WriteCurrent({
            state = "installed_not_ready",
            installed = true,
            supported = false,
            apiVersion = apiVersion,
            addonVersion = addonVersion,
            favorites = {},
        })
    end

    local favoritesOK, rawFavorites = SafeCall(api, "GetFavorites", characterKey)
    if not favoritesOK or type(rawFavorites) ~= "table" then
        return self:WriteCurrent({
            state = "installed_not_ready",
            installed = true,
            supported = false,
            apiVersion = apiVersion,
            addonVersion = addonVersion,
            characterKey = characterKey,
            favorites = {},
        })
    end

    local favorites = {}
    for _, entry in ipairs(rawFavorites) do
        local favorite = NormalizeFavorite(self, api, entry, characterKey)
        if favorite then
            table.insert(favorites, favorite)
        end
    end

    return self:WriteCurrent({
        state = "supported",
        installed = true,
        supported = true,
        apiVersion = apiVersion,
        addonVersion = addonVersion,
        characterKey = characterKey,
        updatedAt = time(),
        favorites = favorites,
        voidcore = NormalizeVoidcore(),
    })
end

function Integration:Stop()
    local api = self.callbackApi
    self.generation = (self.generation or 0) + 1
    self.active = false
    self.refreshPending = false
    self.pendingGeneration = nil

    if type(api) == "table" and type(api.UnregisterCallback) == "function" then
        SafeCall(api, "UnregisterCallback", "READY", CALLBACK_OWNER)
        SafeCall(api, "UnregisterCallback", "FAVORITE_ADDED", CALLBACK_OWNER)
        SafeCall(api, "UnregisterCallback", "FAVORITE_REMOVED", CALLBACK_OWNER)
        SafeCall(api, "UnregisterCallback", "FAVORITES_IMPORTED", CALLBACK_OWNER)
        SafeCall(api, "UnregisterCallback", "FAVORITES_CHANGED", CALLBACK_OWNER)
    end

    self.callbackApi = nil
    self.readyCallback = nil
    self.favoriteAddedCallback = nil
    self.favoriteRemovedCallback = nil
    self.favoritesImportedCallback = nil
    self.favoritesChangedCallback = nil
    self.recentPreview = nil
    self.captureResolutionPending = {}
end

function Integration:FormatDiagnostic(snapshot)
    if type(snapshot) ~= "table" or snapshot.state == "not_installed" then
        return "KeystoneLoot no detectado."
    end
    if snapshot.state == "installed_not_ready" then
        return "KeystoneLoot detectado, pero todavía no está listo."
    end
    if snapshot.state == "unsupported_api" then
        local version = snapshot.apiVersion and ("v" .. tostring(snapshot.apiVersion)) or "desconocida"
        return "KeystoneLoot detectado, pero la API " .. version .. " no es compatible."
    end
    if snapshot.state == "supported" then
        local count = type(snapshot.favorites) == "table" and #snapshot.favorites or 0
        local favoriteLabel = count == 1 and " favorito." or " favoritos."
        return "KeystoneLoot: detectado, API v" .. tostring(snapshot.apiVersion) .. ", " .. count .. favoriteLabel
    end

    return "KeystoneLoot no detectado."
end

local function DiagnosticValue(value)
    if value == nil or value == "" then
        return "unavailable"
    end
    return tostring(value)
end

local function DiagnosticList(values)
    if type(values) ~= "table" or #values == 0 then
        return "[]"
    end
    local parts = {}
    for _, value in ipairs(values) do
        table.insert(parts, tostring(value))
    end
    return "[" .. table.concat(parts, ",") .. "]"
end

function Integration:FormatFavoriteDiagnostics(snapshot)
    local lines = { "KeystoneSync KeystoneLoot diagnostic" }
    if type(snapshot) ~= "table" or snapshot.state ~= "supported" or type(snapshot.favorites) ~= "table" then
        table.insert(lines, "favorites: unavailable")
        return lines
    end
    if #snapshot.favorites == 0 then
        table.insert(lines, "favorites: 0")
        return lines
    end

    local characterKey = snapshot.characterKey
    for _, favorite in ipairs(snapshot.favorites) do
        local capture = self:GetCapturedVariant(
            characterKey, favorite.sourceId, tonumber(favorite.specId), tonumber(favorite.itemId)
        )
        local metadataSource = capture and "captured_variant"
            or (type(favorite.bonusIds) == "table" and #favorite.bonusIds > 0 and "favorite_bonus_ids")
            or "legacy/no-capture"
        table.insert(lines, table.concat({
            "itemId=" .. DiagnosticValue(favorite.itemId),
            "sourceId=" .. DiagnosticValue(favorite.sourceId),
            "specId=" .. DiagnosticValue(favorite.specId),
            "favoriteBonusIds=" .. DiagnosticList(favorite.bonusIds),
            "selectedContext=" .. DiagnosticValue(capture and capture.selectedContext),
            "selectedTrack=" .. DiagnosticValue(capture and (capture.selectedTrack or capture.selectedDifficulty)),
            "selectedRank=" .. DiagnosticValue(capture and capture.selectedRank),
            "variantKey=" .. DiagnosticValue(favorite.variantKey),
            "itemLevel=" .. DiagnosticValue(favorite.itemLevel),
            "qualityTypeExact=" .. DiagnosticValue(favorite.qualityType),
            "metadataSource=" .. metadataSource,
        }, " "))
    end
    return lines
end
