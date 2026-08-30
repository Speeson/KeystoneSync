local _, KeystoneSync = ...

KeystoneSync.KeystoneLootIntegration = {}

local Integration = KeystoneSync.KeystoneLootIntegration
local SUPPORTED_API_VERSION = 2
local FAVORITES_DEBOUNCE_SECONDS = 0.1
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

-- KeystoneLoot's own link builder uses this exact item-string layout. We keep only
-- the Favorite's stored bonus IDs instead of adding the UI's current upgrade filters.
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

        SafeCall(api, "RegisterCallback", "READY", self.readyCallback, CALLBACK_OWNER)
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
        SafeCall(api, "UnregisterCallback", "FAVORITES_CHANGED", CALLBACK_OWNER)
    end

    self.callbackApi = nil
    self.readyCallback = nil
    self.favoritesChangedCallback = nil
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
