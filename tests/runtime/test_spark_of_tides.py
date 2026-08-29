import unittest

from lua_harness import LuaAddonHarness, lua_to_python


class SparkOfTidesRuntimeTests(unittest.TestCase):
    def make_runtime(self):
        harness = LuaAddonHarness()
        harness.install_keystonesync_wow_stubs()
        harness.load_addon_file("KeystoneSync.lua")
        return harness

    @staticmethod
    def save(harness):
        frame = harness.globals._test.frames[1]
        frame["OnEvent"](frame, "PLAYER_LOGIN")
        return lua_to_python(
            harness.globals.KeystoneSyncDB["Zul'jin-Spee"]["currencies"]["sparksOfTides"]
        )

    def test_normal_bag_sparks_are_counted(self):
        harness = self.make_runtime()
        harness.execute(
            """
            C_Container.GetContainerNumSlots = function(bag)
                if bag == 2 then return 1 end
                return 0
            end
            C_Container.GetContainerItemInfo = function(bag, slot)
                if bag == 2 and slot == 1 then
                    return { itemID = 274476, stackCount = 2 }
                end
                return nil
            end
            """
        )

        sparks = self.save(harness)

        self.assertEqual(sparks["inventoryQuantity"], 2)
        self.assertEqual(sparks["quantity"], 2)
        self.assertEqual(sparks["itemQuantity"], 2)

    def test_equipped_reagent_bag_sparks_are_counted(self):
        harness = self.make_runtime()
        harness.execute(
            """
            NUM_TOTAL_EQUIPPED_BAG_SLOTS = 5
            C_Container.GetContainerNumSlots = function(bag)
                if bag == 5 then return 1 end
                return 0
            end
            C_Container.GetContainerItemInfo = function(bag, slot)
                if bag == 5 and slot == 1 then
                    return { itemID = 274476, stackCount = 3 }
                end
                return nil
            end
            """
        )

        sparks = self.save(harness)

        self.assertEqual(sparks["inventoryQuantity"], 3)
        self.assertEqual(sparks["quantity"], 3)
        self.assertEqual(sparks["itemQuantity"], 3)

    def test_personal_reagent_bank_is_included_with_exact_item_count_semantics(self):
        harness = self.make_runtime()
        harness.execute(
            """
            _test.itemCountArgs = nil
            C_Item.GetItemCount = function(itemInfo, includeBank, includeUses, includeReagentBank, includeAccountBank)
                _test.itemCountArgs = {
                    itemInfo,
                    includeBank,
                    includeUses,
                    includeReagentBank,
                    includeAccountBank,
                }
                if includeBank == true and includeUses == false
                    and includeReagentBank == true and includeAccountBank == false then
                    return 4
                end
                return 0
            end
            """
        )

        sparks = self.save(harness)

        self.assertEqual(sparks["quantity"], 4)
        self.assertEqual(sparks["itemQuantity"], 4)
        self.assertEqual(
            lua_to_python(harness.globals._test.itemCountArgs),
            [274476, True, False, True, False],
        )

    def test_warband_bank_quantity_is_excluded(self):
        harness = self.make_runtime()
        harness.execute(
            """
            C_Item.GetItemCount = function(itemInfo, includeBank, includeUses, includeReagentBank, includeAccountBank)
                if includeAccountBank ~= false then return 9 end
                return 4
            end
            """
        )

        sparks = self.save(harness)

        self.assertEqual(sparks["quantity"], 4)
        self.assertEqual(sparks["itemQuantity"], 4)
        self.assertEqual(sparks["totalItemQuantity"], 4)

    def test_icon_uses_deterministic_fallback_when_api_is_unavailable(self):
        harness = self.make_runtime()
        harness.execute("C_Item.GetItemIconByID = nil")

        sparks = self.save(harness)

        self.assertEqual(sparks["iconFileID"], 7551419)


if __name__ == "__main__":
    unittest.main()
