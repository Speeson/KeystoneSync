import unittest

from lua_harness import LuaAddonHarness, lua_to_python


CHARACTER_KEY = "Zul'jin-Spee"
BOUNTY_ITEM_ID = 274374


class TrovehunterLogoutTests(unittest.TestCase):
    def make_runtime(self, has_map=True):
        harness = LuaAddonHarness()
        harness.install_keystonesync_wow_stubs()
        harness.execute("C_QuestLog.IsQuestFlaggedCompleted = function() return true end")
        if has_map:
            harness.execute(
                f"_test.containerItems[1] = {{ {{ itemID = {BOUNTY_ITEM_ID}, stackCount = 1 }} }}"
            )
        harness.load_addon_file("KeystoneSync.lua")
        return harness

    @staticmethod
    def fire(harness, event):
        frame = harness.globals._test.frames[1]
        frame["OnEvent"](frame, event)

    @staticmethod
    def bounty(harness):
        return lua_to_python(
            harness.globals.KeystoneSyncDB[CHARACTER_KEY]["currencies"]["trovehuntersBounty"]
        )

    def test_logout_keeps_last_in_game_map_count_when_bags_are_unavailable(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        self.assertEqual(self.bounty(harness)["bagCount"], 1)

        harness.execute("_test.containerAPIsAvailable = false")
        self.fire(harness, "PLAYER_LOGOUT")

        self.assertEqual(self.bounty(harness)["bagCount"], 1)

    def test_unreadable_bags_during_gameplay_do_not_erase_last_map_count(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("_test.containerAPIsAvailable = false")

        self.fire(harness, "BAG_UPDATE_DELAYED")

        self.assertEqual(self.bounty(harness)["bagCount"], 1)

    def test_real_map_removal_during_gameplay_records_zero(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("_test.containerItems[1] = nil")

        self.fire(harness, "BAG_UPDATE_DELAYED")

        self.assertEqual(self.bounty(harness)["bagCount"], 0)

    def test_logout_keeps_active_aura_when_aura_api_is_unavailable(self):
        harness = self.make_runtime(has_map=False)
        harness.execute(
            "C_UnitAuras = { GetPlayerAuraBySpellID = function() return { spellId = 1293799 } end }"
        )
        self.fire(harness, "PLAYER_LOGIN")
        self.assertTrue(self.bounty(harness)["hasBuff"])
        harness.execute("C_UnitAuras = nil")

        self.fire(harness, "PLAYER_LOGOUT")

        self.assertTrue(self.bounty(harness)["hasBuff"])

    def test_first_unreadable_logout_does_not_publish_a_false_zero(self):
        harness = self.make_runtime()
        harness.execute("_test.containerAPIsAvailable = false")

        self.fire(harness, "PLAYER_LOGOUT")

        bounty = self.bounty(harness)
        self.assertNotIn("bagCount", bounty)
        self.assertNotIn("hasBuff", bounty)


if __name__ == "__main__":
    unittest.main()
