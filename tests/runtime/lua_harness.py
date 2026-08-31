from __future__ import annotations

from pathlib import Path

from lupa import LuaRuntime, lua_type


ROOT = Path(__file__).resolve().parents[2]


BOOTSTRAP = r"""
_test = {
    addonInstalled = false,
    now = 1780000000,
    frames = {},
    timers = {},
    prints = {},
    tooltipCallbacks = {},
}

Enum = {
    TooltipDataType = {
        Item = 0,
    },
}

TooltipDataProcessor = {
    AddTooltipPostCall = function(dataType, callback)
        _test.tooltipCallbacks[dataType] = callback
    end,
}

function CreateFrame()
    local frame = { events = {} }
    function frame:RegisterEvent(event)
        self.events[event] = true
    end
    function frame:SetScript(scriptType, callback)
        self[scriptType] = callback
    end
    table.insert(_test.frames, frame)
    return frame
end

C_AddOns = {
    GetAddOnInfo = function(name)
        if name == "KeystoneLoot" and _test.addonInstalled then
            return "KeystoneLoot", "KeystoneLoot", "", true
        end
        return nil
    end,
}

C_Timer = {
    After = function(delay, callback)
        table.insert(_test.timers, { delay = delay, callback = callback })
    end,
}

function time()
    return _test.now
end

function print(...)
    local values = {}
    for index = 1, select("#", ...) do
        values[index] = tostring(select(index, ...))
    end
    table.insert(_test.prints, table.concat(values, " "))
end
"""


def lua_to_python(value):
    if lua_type(value) != "table":
        return value

    keys = list(value.keys())
    numeric_keys = sorted(key for key in keys if isinstance(key, (int, float)))
    if len(numeric_keys) == len(keys) and numeric_keys == list(range(1, len(keys) + 1)):
        return [lua_to_python(value[index]) for index in range(1, len(keys) + 1)]

    return {key: lua_to_python(value[key]) for key in keys}


class LuaAddonHarness:
    def __init__(self) -> None:
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(BOOTSTRAP)
        self.namespace = self.lua.table()

    @property
    def globals(self):
        return self.lua.globals()

    def load_addon_file(self, filename: str):
        source = (ROOT / filename).read_text(encoding="utf-8")
        self.lua.execute(source, "KeystoneSync", self.namespace)
        return self.namespace

    def execute(self, source: str):
        return self.lua.execute(source)

    def evaluate(self, source: str):
        return self.lua.eval(source)

    def run_timers(self) -> None:
        self.lua.execute(
            """
            local timers = _test.timers
            _test.timers = {}
            for _, timer in ipairs(timers) do
                timer.callback()
            end
            """
        )

    def timer_count(self) -> int:
        return int(self.lua.eval("#_test.timers"))

    def stored_keystone_loot(self, key: str):
        value = self.globals.KeystoneSyncDB[key]["keystoneLoot"]
        return lua_to_python(value)

    def install_keystonesync_wow_stubs(self) -> None:
        self.lua.execute(
            r"""
            NUM_BAG_SLOTS = 4
            SlashCmdList = {}
            Enum = {
                WeeklyRewardChestThresholdType = {
                    Raid = 1,
                    Activities = 2,
                    World = 3,
                },
            }

            function UnitLevel() return 90 end
            function UnitName() return "Spee" end
            function GetRealmName() return "Zul'jin" end
            function GetAverageItemLevel() return 700 end
            function GetMoney() return 12345 end
            function time() return _test.now end
            function date(format)
                if format == "!%Y-%m-%d" then return "2026-08-26" end
                return { year = 2026, month = 8, day = 26, wday = 4, hour = 4, min = 0, sec = 0 }
            end

            C_MythicPlus = {
                GetOwnedKeystoneLevel = function() return nil end,
                GetOwnedKeystoneChallengeMapID = function() return nil end,
                GetOwnedKeystoneMapID = function() return nil end,
                GetSeasonBestForMap = function() return nil, nil end,
                GetSeasonBestAffixScoreInfoForMap = function() return {}, 0 end,
            }
            C_Container = {
                GetContainerNumSlots = function() return 0 end,
                GetContainerItemLink = function() return nil end,
                GetContainerItemInfo = function() return nil end,
            }
            C_ChallengeMode = {
                GetMapUIInfo = function() return nil end,
                GetMapTable = function() return {} end,
            }
            C_WeeklyRewards = {
                HasAvailableRewards = function() return false end,
                GetActivities = function() return {} end,
                GetNumCompletedDungeonRuns = function() return 0, 0, 0 end,
            }
            C_QuestLog = { IsQuestFlaggedCompleted = function() return false end }
            C_CurrencyInfo = { GetCurrencyInfo = function() return nil end }
            C_Item = {
                GetItemCount = function() return 0 end,
                GetItemIconByID = function() return nil end,
            }
            C_PlayerInfo = { GetPlayerMythicPlusRatingSummary = function() return nil end }
            C_Texture = { GetFilenameFromFileDataID = function() return nil end }
            C_UnitAuras = nil
            """
        )

    def install_integration_spy(self) -> None:
        self.lua.execute(
            r"""
            _test.integrationCalls = {}
            _test.integrationSnapshot = {
                state = "supported",
                installed = true,
                supported = true,
                favorites = {},
            }

            local function Record(call)
                table.insert(_test.integrationCalls, call)
            end

            _test.integrationSpy = {
                Start = function(self, keyProvider)
                    Record("start")
                    _test.recordExistsAtStart = KeystoneSyncDB[keyProvider()] ~= nil
                    return _test.integrationSnapshot
                end,
                RefreshCurrent = function(self)
                    Record("refresh")
                    if _test.throwIntegration then error("integration failure") end
                    local record = KeystoneSyncDB["Zul'jin-Spee"]
                    _test.reasonAtRefresh = record and record.updatedReason or nil
                    record.keystoneLoot = _test.integrationSnapshot
                    return record.keystoneLoot
                end,
                Stop = function(self)
                    Record("stop")
                end,
                FormatDiagnostic = function(self, snapshot)
                    Record("diagnostic")
                    _test.diagnosticState = snapshot and snapshot.state or nil
                    return "KeystoneLoot diagnostic"
                end,
                FormatFavoriteDiagnostics = function(self, snapshot)
                    Record("favorite-diagnostic")
                    _test.diagnosticState = snapshot and snapshot.state or nil
                    return { "KeystoneSync KeystoneLoot diagnostic", "metadataSource=legacy/no-capture" }
                end,
            }
            """
        )
        self.namespace["KeystoneLootIntegration"] = self.globals._test.integrationSpy
