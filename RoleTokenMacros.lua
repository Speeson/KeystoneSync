local _, KeystoneSync = ...
local Resolver = KeystoneSync.RoleTokenResolver
local Macros = {}
KeystoneSync.RoleTokenMacros = Macros

local PREFIX = "[KeystoneSync Roles] "
local MAX_BODY = 255
local COMMANDS = {
    ["/cast"] = true, ["/use"] = true, ["/castsequence"] = true,
    ["/target"] = true, ["/targetexact"] = true, ["/focus"] = true,
    ["/assist"] = true, ["/petattack"] = true, ["/startattack"] = true,
    ["/stopmacro"] = true, ["#showtooltip"] = true,
}
local pending = false
local scheduled = false
local warned = {}

local function say(message)
    print(PREFIX .. message)
end

local function warnOnce(key, message)
    if warned[key] then return end
    warned[key] = true
    say(message)
end

local function safeValue(value)
    if type(issecretvalue) == "function" then
        local ok, secret = pcall(issecretvalue, value)
        if not ok or secret then return nil end
    end
    return value
end

local function safeCall(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b, c = pcall(fn, ...)
    if not ok then return nil end
    return safeValue(a), safeValue(b), safeValue(c)
end

local function store()
    if type(KeystoneSyncDB) ~= "table" then return nil end
    local db = KeystoneSyncDB.roleTokens
    if type(db) ~= "table" then
        db = { schema = 1, enabled = true, account = {}, characters = {} }
        KeystoneSyncDB.roleTokens = db
    end
    if db.schema ~= nil and db.schema ~= 1 then
        warnOnce("schema", "La versión de datos de tokens de rol no es compatible; gestión suspendida.")
        return nil
    end
    if db.enabled == nil then db.enabled = true end
    if type(db.account) ~= "table" then db.account = {} end
    if type(db.characters) ~= "table" then db.characters = {} end
    db.schema = 1
    return db
end

local function characterBucket(db)
    local name = safeCall(UnitName, "player")
    local realm = safeCall(GetRealmName)
    if type(name) ~= "string" or type(realm) ~= "string" then return nil end
    local key = realm .. "-" .. name
    if type(db.characters[key]) ~= "table" then db.characters[key] = {} end
    return db.characters[key]
end

local function parseToken(word)
    local role, number = string.lower(word):match("^(%a+)(%d*)$")
    if role ~= "tank" and role ~= "healer" and role ~= "dps" then return nil end
    local slot = number == "" and 1 or tonumber(number)
    if not slot or slot < 1 or slot > 40 then return nil end
    return role .. slot
end

local function transform(body, units)
    if type(body) ~= "string" then return body, false end
    local found = false
    local function transformClause(clause)
        return (clause:gsub("([^%w_%-])@([%w_%-]+)", function(prefix, word)
            if prefix ~= "[" and prefix ~= "," and not prefix:match("%s") then
                return prefix .. "@" .. word
            end
            local key = parseToken(word)
            if not key then return prefix .. "@" .. word end
            found = true
            local unit = units and units[key]
            return prefix .. "@" .. (unit or word)
        end))
    end
    local function transformOption(option)
        local cursor, parts = 1, {}
        while true do
            local start = cursor
            while cursor <= #option and option:sub(cursor, cursor):match("%s") do
                cursor = cursor + 1
            end
            parts[#parts + 1] = option:sub(start, cursor - 1)
            if option:sub(cursor, cursor) ~= "[" then break end
            local close = option:find("]", cursor + 1, true)
            if not close then break end
            parts[#parts + 1] = transformClause(option:sub(cursor, close))
            cursor = close + 1
        end
        parts[#parts + 1] = option:sub(cursor)
        return table.concat(parts)
    end
    local result = body:gsub("[^\r\n]+", function(line)
        local lead, args = line:match("^(%s*[#/]%a+)(.*)$")
        if not lead or not COMMANDS[string.lower(lead:match("([/#]%a+)$"))] then return line end
        return lead .. (args:gsub("[^;]+", transformOption))
    end)
    return result, found
end

function Macros.Expand(body, units)
    local result = transform(body, units)
    return result
end

local function hasToken(body)
    local _, found = transform(body, nil)
    return found
end

local function otherManagerLoaded()
    local checker = C_AddOns and C_AddOns.IsAddOnLoaded or IsAddOnLoaded
    return safeCall(checker, "RoleTokens") == true
end

local function readMacros()
    local accountCount, charCount = safeCall(GetNumMacros)
    if type(accountCount) ~= "number" or type(charCount) ~= "number" then return nil end
    local accountMax = type(MAX_ACCOUNT_MACROS) == "number" and MAX_ACCOUNT_MACROS or 120
    local items = { account = {}, character = {} }
    local function add(index, scope)
        local name, icon, body = safeCall(GetMacroInfo, index)
        if type(name) ~= "string" or type(body) ~= "string" or icon == nil then return false end
        items[scope][index] = { index = index, name = name, icon = icon, body = body }
        return true
    end
    for index = 1, math.min(accountCount, accountMax) do
        if not add(index, "account") then return nil end
    end
    for offset = 1, math.min(charCount, 30) do
        if not add(accountMax + offset, "character") then return nil end
    end
    return items
end

local function uniqueBodyMatch(items, used, record)
    local match
    for index, item in pairs(items) do
        if not used[index] and item.body == record.lastBody
            and item.name == record.name and item.icon == record.icon then
            if match then return nil, true end
            match = item
        end
    end
    return match, false
end

local function reconcile(items, bucket)
    local active, used, preserved = {}, {}, {}
    local records = {}
    for index, record in pairs(bucket) do
        if type(index) == "number" and type(record) == "table"
            and type(record.template) == "string" and type(record.lastBody) == "string" then
            records[#records + 1] = { index = index, value = record }
        end
    end
    table.sort(records, function(a, b) return a.index < b.index end)

    for _, entry in ipairs(records) do
        local index, record = entry.index, entry.value
        local item = items[index]
        if item and not record.uncertain and not used[index] and item.body == record.lastBody
            and item.name == record.name and item.icon == record.icon then
            active[index] = record
            used[index] = true
        end
    end
    for _, entry in ipairs(records) do
        local index, record = entry.index, entry.value
        if record.uncertain then
            local sameSlot = items[index]
            if sameSlot and sameSlot.name == record.name and sameSlot.icon == record.icon
                and sameSlot.body ~= record.lastBody and hasToken(sameSlot.body) then
                record.template = sameSlot.body
                record.lastBody = sameSlot.body
                record.uncertain = nil
                active[index] = record
                used[index] = true
            else
                preserved[index] = record
                if sameSlot then used[index] = true end
            end
        elseif not active[index] then
            local item, ambiguous = uniqueBodyMatch(items, used, record)
            if ambiguous then
                warnOnce("ambiguous:" .. index, "Macros idénticas ambiguas; no se modificarán hasta resolverlas.")
                return nil
            elseif item then
                active[item.index] = record
                used[item.index] = true
                record.name, record.icon = item.name, item.icon
            else
                local sameSlot = items[index]
                if sameSlot and not used[index]
                    and sameSlot.name == record.name and sameSlot.icon == record.icon then
                    if hasToken(sameSlot.body) then
                        record.template = sameSlot.body
                        record.lastBody = sameSlot.body
                        active[index] = record
                        used[index] = true
                    else
                        -- A manual edit removed the token; stop managing it.
                        used[index] = true
                    end
                elseif sameSlot and not used[index] and sameSlot.body == record.lastBody then
                    -- A rename and a reused index cannot be distinguished by the API.
                    preserved[index] = record
                    used[index] = true
                    warnOnce("identity:" .. index, "La identidad de la macro '" .. record.name
                        .. "' es ambigua; queda intacta. Reintroduce el token manualmente para vincularla.")
                end
            end
        end
    end
    for index, item in pairs(items) do
        if not used[index] and hasToken(item.body) then
            active[index] = {
                name = item.name, icon = item.icon,
                template = item.body, lastBody = item.body,
            }
        end
    end
    for index in pairs(bucket) do bucket[index] = nil end
    for index, record in pairs(preserved) do bucket[index] = record end
    for index, record in pairs(active) do bucket[index] = record end
    return active
end

local function editBody(item, record, desired)
    if #desired > MAX_BODY then
        warnOnce("length:" .. item.index, "La macro '" .. item.name .. "' supera 255 bytes al expandirse; queda intacta.")
        return
    end
    if desired == item.body then return end
    local result = safeCall(EditMacro, item.index, nil, nil, desired)
    local _, _, actual = safeCall(GetMacroInfo, type(result) == "number" and result or item.index)
    if actual == desired then
        record.lastBody = desired
        record.uncertain = nil
        item.body = desired
    elseif type(result) == "number" then
        -- Do not treat an unexpected API result as a manual edit on the next scan.
        record.uncertain = true
        warnOnce("verify:" .. item.index, "No se pudo verificar la macro '" .. item.name .. "'. Revísala antes de usarla.")
    else
        warnOnce("edit:" .. item.index, "No se pudo editar la macro '" .. item.name .. "'; queda intacta.")
    end
end

local function sync(restore)
    local db = store()
    if not db then return end
    if safeCall(InCombatLockdown) ~= false then
        pending = true
        return
    end
    if otherManagerLoaded() then
        warnOnce("role-tokens", "RoleTokens está cargado; gestión de macros suspendida para evitar conflictos.")
        return
    end
    local items = readMacros()
    if not items then
        warnOnce("macro-api", "No se pudo leer la lista de macros; gestión suspendida.")
        return
    end
    local buckets = { account = db.account, character = characterBucket(db) }
    local units = restore or not db.enabled and {} or Resolver.Resolve()
    for scope, bucket in pairs(buckets) do
        if bucket then
            local active = reconcile(items[scope], bucket)
            if active then
                for index, record in pairs(active) do
                    local item = items[scope][index]
                    if item then
                        local desired = (restore or not db.enabled) and record.template
                            or Macros.Expand(record.template, units)
                        editBody(item, record, desired)
                    end
                end
            end
        end
    end
    pending = false
end

local function schedule()
    if scheduled then return end
    scheduled = true
    if C_Timer and type(C_Timer.After) == "function" then
        C_Timer.After(0, function()
            scheduled = false
            sync(false)
        end)
    else
        scheduled = false
        sync(false)
    end
end

local function status()
    local db = store()
    if not db then return end
    local count = 0
    local bucket = characterBucket(db)
    for _ in pairs(db.account) do count = count + 1 end
    if bucket then for _ in pairs(bucket) do count = count + 1 end end
    say((db.enabled and "Activado" or "Desactivado") .. "; grupo: " .. Resolver.GroupType()
        .. "; macros gestionadas: " .. count .. (pending and "; actualización pendiente de combate" or ""))
    if safeCall(InCombatLockdown) ~= false then return end
    local units = Resolver.Resolve()
    for _, role in ipairs({ "tank", "healer", "dps" }) do
        local entries = {}
        for slot = 1, 40 do
            local unit = units[role .. slot]
            if unit then
                local label = slot == 1 and ("@" .. role .. "=" .. unit .. " (@" .. role .. "1)")
                    or ("@" .. role .. slot .. "=" .. unit)
                entries[#entries + 1] = label
            end
        end
        say(#entries > 0 and table.concat(entries, ", ") or ("@" .. role .. ": sin candidato"))
    end
end

local frame = CreateFrame("Frame")
for _, event in ipairs({ "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD", "GROUP_ROSTER_UPDATE",
    "PLAYER_ROLES_ASSIGNED", "ROLE_CHANGED_INFORM", "PARTY_LEADER_CHANGED",
    "UPDATE_MACROS", "PLAYER_REGEN_ENABLED" }) do
    frame:RegisterEvent(event)
end
frame:SetScript("OnEvent", function(_, event)
    if event == "PLAYER_LOGIN" then store() end
    if event == "PLAYER_REGEN_ENABLED" then
        if pending then schedule() end
    else
        schedule()
    end
end)

SLASH_KSROLE1 = "/ksrole"
SlashCmdList["KSROLE"] = function(message)
    local command = type(message) == "string" and message:lower():match("^%s*(.-)%s*$") or ""
    local db = store()
    if not db then return end
    if command == "enable" then
        db.enabled = true
        say("Tokens de rol activados.")
        schedule()
    elseif command == "disable" or command == "restore" then
        db.enabled = false
        sync(true)
        say("Plantillas restauradas cuando sea seguro; tokens de rol desactivados.")
    elseif command == "refresh" then
        schedule()
    elseif command == "status" or command == "" then
        status()
    else
        say("Comandos: /ksrole enable, disable, status, refresh, restore")
    end
end
