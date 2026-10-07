import unittest

from lua_harness import LuaAddonHarness, lua_to_python


CHARACTER_KEY = "Zul'jin-Spee"
ORIN_QUEST_IDS = (98016, 98015, 98012)


class OrinVoidcoreTests(unittest.TestCase):
    def make_runtime(self):
        harness = LuaAddonHarness()
        harness.install_keystonesync_wow_stubs()
        harness.execute("""
            _test.weekKey = "2026-10-07"
            _test.completedQuests = {}
            _test.questCalls = {}
            local originalDate = date
            date = function(format, value)
                if format == "!%Y-%m-%d" then return _test.weekKey end
                return originalDate(format, value)
            end
            C_CurrencyInfo.GetCurrencyInfo = function(id)
                if id == 3513 or id == 3418 then
                    return { name = "Nebulous Voidcore", quantity = 1, maxQuantity = 0 }
                end
                return nil
            end
            C_QuestLog.IsQuestFlaggedCompleted = function(id)
                table.insert(_test.questCalls, id)
                return _test.completedQuests[id] == true
            end
        """)
        harness.load_addon_file("KeystoneSync.lua")
        return harness

    def snapshot(self, harness):
        frame = harness.globals._test.frames[1]
        frame["OnEvent"](frame, "PLAYER_LOGIN")
        return lua_to_python(harness.globals.KeystoneSyncDB[CHARACTER_KEY]["currencies"]["nebulousVoidcore"])

    def test_each_orin_option_completes_the_weekly_card(self):
        for quest_id in ORIN_QUEST_IDS:
            with self.subTest(quest_id=quest_id):
                harness = self.make_runtime()
                harness.execute(f"_test.completedQuests[{quest_id}] = true")
                core = self.snapshot(harness)
                self.assertTrue(core["questCompleted"])
                self.assertTrue(core["isWeeklyComplete"])
                self.assertEqual(core["displayColor"], "red")
                self.assertEqual(core["weekKey"], "2026-10-07")

    def test_decimus_quest_is_ignored_and_completion_resets_next_week(self):
        harness = self.make_runtime()
        harness.execute("_test.completedQuests[95279] = true")
        core = self.snapshot(harness)
        self.assertFalse(core["questCompleted"])
        calls = lua_to_python(harness.globals._test.questCalls)
        self.assertEqual([quest_id for quest_id in calls if quest_id in ORIN_QUEST_IDS], list(ORIN_QUEST_IDS))
        self.assertNotIn(95279, calls)

        harness.execute("_test.completedQuests[98016] = true")
        self.assertTrue(self.snapshot(harness)["questCompleted"])
        harness.execute("_test.completedQuests[98016] = false")
        self.assertTrue(self.snapshot(harness)["questCompleted"])
        harness.execute('_test.weekKey = "2026-10-14"')
        self.assertFalse(self.snapshot(harness)["questCompleted"])


if __name__ == "__main__":
    unittest.main()
