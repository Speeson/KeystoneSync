import unittest

from lua_harness import LuaAddonHarness, lua_to_python


CHARACTER_KEY = "Zul'jin-Spee"
SPARK_ITEM_ID = 274476


class SparkBankTrackingTests(unittest.TestCase):
    def make_runtime(self, containers=None, character_bank_tabs=None, previous_spark=None):
        harness = LuaAddonHarness()
        harness.install_keystonesync_wow_stubs()

        if character_bank_tabs is not None:
            tab_values = ", ".join(str(tab) for tab in character_bank_tabs)
            harness.execute(f"_test.characterBankTabs = {{ {tab_values} }}")

        for container, stacks in (containers or {}).items():
            harness.execute(f"_test.containerItems[{container}] = {{}}")
            for slot, (item_id, stack_count) in enumerate(stacks, start=1):
                harness.execute(
                    f"_test.containerItems[{container}][{slot}] = "
                    f"{{ itemID = {item_id}, stackCount = {stack_count} }}"
                )

        if previous_spark is not None:
            fields = []
            for key, value in previous_spark.items():
                if isinstance(value, bool):
                    encoded = "true" if value else "false"
                elif value is None:
                    encoded = "nil"
                else:
                    encoded = str(value)
                fields.append(f"{key} = {encoded}")
            harness.execute(
                "KeystoneSyncDB = {}; "
                f"KeystoneSyncDB[\"{CHARACTER_KEY}\"] = {{ currencies = {{ sparksOfTides = {{"
                + ", ".join(fields)
                + "} } }"
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

    def test_normal_equipped_bag_is_counted_as_carried(self):
        harness = self.make_runtime(containers={1: [(SPARK_ITEM_ID, 3)]})

        self.fire(harness, "PLAYER_LOGIN")

        spark = self.spark(harness)
        self.assertEqual(spark["inventoryQuantity"], 3)
        self.assertEqual(spark["itemQuantity"], 3)

    def test_backpack_is_counted_as_carried(self):
        harness = self.make_runtime(containers={0: [(SPARK_ITEM_ID, 2)]})

        self.fire(harness, "PLAYER_LOGIN")

        self.assertEqual(self.spark(harness)["inventoryQuantity"], 2)

    def test_equipped_reagent_bag_is_counted_as_carried(self):
        harness = self.make_runtime(containers={5: [(SPARK_ITEM_ID, 3)]})

        self.fire(harness, "PLAYER_LOGIN")

        spark = self.spark(harness)
        self.assertEqual(spark["inventoryQuantity"], 3)
        self.assertEqual(spark["itemQuantity"], 3)

    def test_mixed_carried_containers_are_summed(self):
        harness = self.make_runtime(
            containers={
                0: [(SPARK_ITEM_ID, 1)],
                1: [(999999, 8), (SPARK_ITEM_ID, 1)],
                5: [(SPARK_ITEM_ID, 2)],
            }
        )

        self.fire(harness, "PLAYER_LOGIN")

        self.assertEqual(self.spark(harness)["inventoryQuantity"], 4)

    def test_unknown_bank_state_keeps_live_carried_total(self):
        harness = self.make_runtime(containers={1: [(SPARK_ITEM_ID, 6)]})

        self.fire(harness, "PLAYER_LOGIN")

        spark = self.spark(harness)
        self.assertEqual(spark["itemQuantity"], 6)
        self.assertFalse(spark["bankQuantityKnown"])
        self.assertNotIn("bankQuantity", spark)

    def test_personal_character_bank_tabs_are_counted_independently(self):
        harness = self.make_runtime(
            containers={6: [(SPARK_ITEM_ID, 2)]},
            character_bank_tabs=[6],
        )

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["inventoryQuantity"], 0)
        self.assertEqual(spark["bankQuantity"], 2)
        self.assertEqual(spark["itemQuantity"], 2)
        self.assertTrue(spark["bankQuantityKnown"])
        self.assertEqual(spark["bankUpdatedAt"], 1780000000)

    def test_real_reproduction_three_carried_plus_two_banked_is_five(self):
        harness = self.make_runtime(
            containers={
                5: [(SPARK_ITEM_ID, 3)],
                6: [(SPARK_ITEM_ID, 2)],
            },
            character_bank_tabs=[6],
        )

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["inventoryQuantity"], 3)
        self.assertEqual(spark["bankQuantity"], 2)
        self.assertEqual(spark["itemQuantity"], 5)
        self.assertEqual(spark["quantity"], 5)
        self.assertEqual(spark["totalItemQuantity"], 5)

    def test_all_banked_sparks_keep_the_total(self):
        harness = self.make_runtime(
            containers={11: [(SPARK_ITEM_ID, 3)]},
            character_bank_tabs=[6, 11],
        )

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["inventoryQuantity"], 0)
        self.assertEqual(spark["bankQuantity"], 3)
        self.assertEqual(spark["itemQuantity"], 3)

    def test_account_bank_is_never_requested_or_counted(self):
        harness = self.make_runtime(
            containers={12: [(SPARK_ITEM_ID, 5)]},
            character_bank_tabs=[6],
        )

        self.fire(harness, "BANKFRAME_OPENED")

        spark = self.spark(harness)
        self.assertEqual(spark["bankQuantity"], 0)
        self.assertEqual(spark["itemQuantity"], 0)
        self.assertEqual(lua_to_python(harness.globals._test.requestedBankTypes), [0])

    def test_closed_bank_keeps_snapshot_but_refreshes_live_carried_count(self):
        harness = self.make_runtime(
            containers={1: [(SPARK_ITEM_ID, 1)], 6: [(SPARK_ITEM_ID, 2)]},
            character_bank_tabs=[6],
        )
        self.fire(harness, "BANKFRAME_OPENED")
        self.fire(harness, "BANKFRAME_CLOSED")
        harness.execute(
            f"_test.containerItems[1][1] = {{ itemID = {SPARK_ITEM_ID}, stackCount = 3 }}; "
            "_test.containerItems[6] = nil"
        )

        self.fire(harness, "BAG_UPDATE_DELAYED")

        spark = self.spark(harness)
        self.assertEqual(spark["inventoryQuantity"], 3)
        self.assertEqual(spark["bankQuantity"], 2)
        self.assertEqual(spark["itemQuantity"], 5)

    def test_bag_update_accepts_a_legitimate_live_zero(self):
        harness = self.make_runtime(containers={1: [(SPARK_ITEM_ID, 3)]})
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("_test.containerItems[1] = nil")

        self.fire(harness, "BAG_UPDATE_DELAYED")

        spark = self.spark(harness)
        self.assertEqual(spark["inventoryQuantity"], 0)
        self.assertEqual(spark["itemQuantity"], 0)

    def test_logout_preserves_last_trustworthy_spark_snapshot(self):
        harness = self.make_runtime(
            previous_spark={
                "quantity": 5,
                "itemQuantity": 5,
                "inventoryQuantity": 3,
                "totalItemQuantity": 5,
                "bankQuantity": 2,
                "bankQuantityKnown": True,
                "bankUpdatedAt": 1779990000,
            }
        )
        harness.execute("_test.containerAPIsAvailable = false")

        self.fire(harness, "PLAYER_LOGOUT")

        spark = self.spark(harness)
        self.assertEqual(spark["quantity"], 5)
        self.assertEqual(spark["itemQuantity"], 5)
        self.assertEqual(spark["inventoryQuantity"], 3)
        self.assertEqual(spark["totalItemQuantity"], 5)
        self.assertEqual(spark["bankQuantity"], 2)
        self.assertTrue(spark["bankQuantityKnown"])
        self.assertEqual(spark["bankUpdatedAt"], 1779990000)

    def test_spark_counting_does_not_use_aggregate_item_count(self):
        harness = self.make_runtime(containers={1: [(SPARK_ITEM_ID, 3)]})

        self.fire(harness, "PLAYER_LOGIN")

        self.assertEqual(lua_to_python(harness.globals._test.itemCountCalls), [])

    def test_logout_does_not_preserve_known_flag_without_a_bank_quantity(self):
        harness = self.make_runtime(
            previous_spark={
                "quantity": 3,
                "itemQuantity": 3,
                "inventoryQuantity": 3,
                "totalItemQuantity": 3,
                "bankQuantityKnown": True,
            }
        )

        self.fire(harness, "PLAYER_LOGOUT")

        spark = self.spark(harness)
        self.assertFalse(spark["bankQuantityKnown"])
        self.assertNotIn("bankQuantity", spark)

    def test_bank_open_refreshes_snapshot_while_bag_updates(self):
        harness = self.make_runtime(
            containers={1: [(SPARK_ITEM_ID, 3)], 6: [(SPARK_ITEM_ID, 2)]},
            character_bank_tabs=[6],
        )
        self.fire(harness, "BANKFRAME_OPENED")
        harness.execute(
            f"_test.containerItems[6][1] = {{ itemID = {SPARK_ITEM_ID}, stackCount = 4 }}"
        )

        self.fire(harness, "BAG_UPDATE_DELAYED")

        spark = self.spark(harness)
        self.assertEqual(spark["bankQuantity"], 4)
        self.assertEqual(spark["itemQuantity"], 7)

    def test_current_bank_events_are_registered(self):
        harness = self.make_runtime()
        events = lua_to_python(harness.globals._test.frames[1]["events"])

        self.assertTrue(events["BANKFRAME_OPENED"])
        self.assertTrue(events["BANKFRAME_CLOSED"])
        self.assertTrue(events["BAG_UPDATE_DELAYED"])
        self.assertNotIn("PLAYERREAGENTBANKSLOTS_CHANGED", events)


if __name__ == "__main__":
    unittest.main()
