import unittest

from lua_harness import LuaAddonHarness, lua_to_python


CHARACTER_KEY = "Zul'jin-Spee"


class SparkBankTrackingTests(unittest.TestCase):
    def make_runtime(self, carried=0, character_owned=0, previous_spark=None):
        harness = LuaAddonHarness()
        harness.install_keystonesync_wow_stubs()
        harness.execute(
            f"_test.sparkCarriedCount = {carried}; "
            f"_test.sparkCharacterOwnedCount = {character_owned}"
        )
        if previous_spark is not None:
            bank_quantity = previous_spark.get("bankQuantity", 0)
            known = "true" if previous_spark.get("bankQuantityKnown") else "false"
            updated_at = previous_spark.get("bankUpdatedAt")
            updated_at_lua = str(updated_at) if updated_at is not None else "nil"
            harness.execute(
                "KeystoneSyncDB = {}; "
                f"KeystoneSyncDB[\"{CHARACTER_KEY}\"] = {{ currencies = {{ sparksOfTides = {{"
                f"bankQuantity = {bank_quantity}, bankQuantityKnown = {known}, "
                f"bankUpdatedAt = {updated_at_lua}"
                "} } }"
            )
        harness.load_addon_file("KeystoneSync.lua")
        return harness

    @staticmethod
    def fire(harness, event):
        frame = harness.globals._test.frames[1]
        frame["OnEvent"](frame, event)

    @staticmethod
    def spark(harness):
        return lua_to_python(
            harness.globals.KeystoneSyncDB[CHARACTER_KEY]["currencies"]["sparksOfTides"]
        )

    def test_unknown_bank_state_keeps_carried_total_without_inventing_known_zero(self):
        harness = self.make_runtime(carried=6, character_owned=6)

        self.fire(harness, "PLAYER_LOGIN")

        spark = self.spark(harness)
        self.assertEqual(spark["inventoryQuantity"], 6)
        self.assertEqual(spark["itemQuantity"], 6)
        self.assertEqual(spark["totalItemQuantity"], 6)
        self.assertFalse(spark["bankQuantityKnown"])
        self.assertNotIn("bankQuantity", spark)

    def test_bank_open_captures_mixed_carried_and_personal_bank_total(self):
        harness = self.make_runtime(carried=3, character_owned=6)
        self.fire(harness, "PLAYER_LOGIN")

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["quantity"], 6)
        self.assertEqual(spark["itemQuantity"], 6)
        self.assertEqual(spark["inventoryQuantity"], 3)
        self.assertEqual(spark["totalItemQuantity"], 6)
        self.assertEqual(spark["bankQuantity"], 3)
        self.assertTrue(spark["bankQuantityKnown"])
        self.assertEqual(spark["bankUpdatedAt"], 1780000000)

    def test_bags_only_keeps_carried_total_and_authoritative_zero_bank(self):
        harness = self.make_runtime(carried=6, character_owned=6)

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["itemQuantity"], 6)
        self.assertEqual(spark["inventoryQuantity"], 6)
        self.assertEqual(spark["bankQuantity"], 0)
        self.assertTrue(spark["bankQuantityKnown"])

    def test_reagent_bank_only_is_counted_as_character_personal_bank(self):
        harness = self.make_runtime(carried=0, character_owned=1)

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["itemQuantity"], 1)
        self.assertEqual(spark["bankQuantity"], 1)

    def test_normal_personal_bank_only_is_counted(self):
        harness = self.make_runtime(carried=0, character_owned=2)

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["itemQuantity"], 2)
        self.assertEqual(spark["bankQuantity"], 2)

    def test_all_banked_sparks_keep_the_total(self):
        harness = self.make_runtime(carried=0, character_owned=3)

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["itemQuantity"], 3)
        self.assertEqual(spark["inventoryQuantity"], 0)
        self.assertEqual(spark["bankQuantity"], 3)

    def test_account_bank_only_never_leaks_into_character_total(self):
        harness = self.make_runtime(carried=0, character_owned=0)

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["itemQuantity"], 0)
        self.assertEqual(spark["bankQuantity"], 0)
        calls = lua_to_python(harness.globals._test.itemCountCalls)
        self.assertTrue(calls)
        self.assertTrue(all(call[4] is False for call in calls))

    def test_item_count_calls_use_every_explicit_storage_argument(self):
        harness = self.make_runtime(carried=3, character_owned=6)

        self.fire(harness, "BANKFRAME_OPENED")

        calls = lua_to_python(harness.globals._test.itemCountCalls)
        self.assertIn([274476, False, False, False, False], calls)
        self.assertIn([274476, True, False, True, False], calls)

    def test_login_preserves_last_trustworthy_character_bank_snapshot(self):
        harness = self.make_runtime(
            carried=2,
            character_owned=2,
            previous_spark={
                "bankQuantity": 3,
                "bankQuantityKnown": True,
                "bankUpdatedAt": 1779990000,
            },
        )

        self.fire(harness, "PLAYER_LOGIN")

        spark = self.spark(harness)
        self.assertEqual(spark["itemQuantity"], 5)
        self.assertEqual(spark["bankQuantity"], 3)
        self.assertTrue(spark["bankQuantityKnown"])
        self.assertEqual(spark["bankUpdatedAt"], 1779990000)

    def test_bag_update_refreshes_snapshot_only_while_bank_is_open(self):
        harness = self.make_runtime(carried=3, character_owned=6)
        self.fire(harness, "BANKFRAME_OPENED")
        harness.execute("_test.sparkCarriedCount = 4; _test.sparkCharacterOwnedCount = 8")

        self.fire(harness, "BAG_UPDATE_DELAYED")

        spark = self.spark(harness)
        self.assertEqual(spark["itemQuantity"], 8)
        self.assertEqual(spark["bankQuantity"], 4)

    def test_bank_close_does_not_take_a_fresh_authoritative_read(self):
        harness = self.make_runtime(carried=3, character_owned=6)
        self.fire(harness, "BANKFRAME_OPENED")
        harness.execute("_test.sparkCarriedCount = 3; _test.sparkCharacterOwnedCount = 99")

        self.fire(harness, "BANKFRAME_CLOSED")

        spark = self.spark(harness)
        self.assertEqual(spark["itemQuantity"], 6)
        self.assertEqual(spark["bankQuantity"], 3)

    def test_current_bank_events_are_registered_without_removed_reagent_event(self):
        harness = self.make_runtime()
        events = lua_to_python(harness.globals._test.frames[1]["events"])

        self.assertTrue(events["BANKFRAME_OPENED"])
        self.assertTrue(events["BANKFRAME_CLOSED"])
        self.assertTrue(events["BAG_UPDATE_DELAYED"])
        self.assertNotIn("PLAYERREAGENTBANKSLOTS_CHANGED", events)


if __name__ == "__main__":
    unittest.main()
