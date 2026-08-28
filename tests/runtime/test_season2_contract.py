import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LUA = (ROOT / "KeystoneSync.lua").read_text(encoding="utf-8")
TOC = (ROOT / "KeystoneSync.toc").read_text(encoding="utf-8")

CURRENCY_DEF_RE = re.compile(
    r'\{ key = "([^"]+)", id = (\d+)(?:, quantityId = (\d+))? \}'
)


def parse_currency_defs(lua: str) -> dict[str, dict]:
    defs = {}
    for key, currency_id, quantity_id in CURRENCY_DEF_RE.findall(lua):
        defs[key] = {
            "key": key,
            "id": int(currency_id),
            "quantityId": int(quantity_id) if quantity_id else None,
        }
    return defs


def simulate_currency(defn: dict, display_info: dict, quantity_info: dict) -> dict:
    """Mirror the GetCurrencyData() currency loop for a single definition.

    display_info is the C_CurrencyInfo result for `id` (e.g. 3513).
    quantity_info is the C_CurrencyInfo result for `quantityId` (e.g. 3418),
    or display_info when no quantityId exists.
    """
    is_complete = False
    if defn["key"] == "nebulousVoidcore" and display_info.get("maxQuantity", 0) > 0:
        is_complete = (
            display_info.get("totalEarned") or display_info.get("quantity") or 0
        ) >= display_info["maxQuantity"]

    source = quantity_info if defn["quantityId"] is not None else display_info

    return {
        "id": defn["id"],
        "name": display_info["name"],
        "quantity": source.get("quantity") or 0,
        "maxQuantity": display_info.get("maxQuantity") or 0,
        "maxWeeklyQuantity": display_info.get("maxWeeklyQuantity") or 0,
        "totalEarned": display_info.get("totalEarned") or 0,
        "trackedQuantity": display_info.get("trackedQuantity") or 0,
        "quantityEarnedThisWeek": display_info.get("quantityEarnedThisWeek") or 0,
        "discovered": display_info.get("discovered") is True,
        "quality": display_info.get("quality"),
        "iconFileID": display_info.get("iconFileID"),
        "isWeeklyComplete": is_complete,
    }


class Season2ContractTests(unittest.TestCase):
    def test_interface_and_currency_contract(self):
        self.assertIn("## Interface: 120100", TOC)

        expected = {
            "adventurerMistcrest": {"id": 3442, "quantityId": None},
            "veteranMistcrest": {"id": 3443, "quantityId": None},
            "championMistcrest": {"id": 3444, "quantityId": None},
            "heroMistcrest": {"id": 3445, "quantityId": None},
            "mythMistcrest": {"id": 3446, "quantityId": None},
            "venomblightManaflux": {"id": 3465, "quantityId": None},
            "tidalSparkDust": {"id": 3509, "quantityId": None},
            "cofferKeyShards": {"id": 3310, "quantityId": None},
            "restoredCofferKey": {"id": 3028, "quantityId": None},
            "nebulousVoidcore": {"id": 3513, "quantityId": 3418},
        }
        actual = {
            key: {"id": defn["id"], "quantityId": defn["quantityId"]}
            for key, defn in parse_currency_defs(LUA).items()
        }
        self.assertEqual(actual, expected)

        self.assertIn("local SPARK_OF_TIDES_ITEM_ID = 274476", LUA)
        self.assertIn("local TIDAL_SPARK_DUST_CURRENCY_ID = 3509", LUA)
        self.assertIn("result.sparksOfTides = {", LUA)

    def test_prey_and_trovehunter_contract(self):
        for quest_id in (95021, 95022, 95023, 95024):
            self.assertIn(f"table.insert(nightmare, {quest_id})", LUA)

        self.assertIn("local TROVEHUNTERS_BOUNTY_ITEM_ID = 274374", LUA)
        self.assertIn("local TROVEHUNTERS_BOUNTY_QUEST_ID = 86371", LUA)
        self.assertIn("local TROVEHUNTERS_BOUNTY_BUFF_SPELL_ID = 1293799", LUA)
        self.assertIn("pcall(CountItemInBags, TROVEHUNTERS_BOUNTY_ITEM_ID)", LUA)
        self.assertIn("local weekKey = GetWeeklyResetKey()", LUA)
        self.assertIn("previousBounty.weekKey == weekKey", LUA)
        self.assertIn("previousBounty.questCompleted", LUA)
        self.assertIn("result.trovehuntersBounty = {", LUA)
        for field in (
            "itemID",
            "bagCount",
            "hasBuff",
            "questCompleted",
            "iconFileID",
            "iconPath",
            "weekKey",
        ):
            self.assertRegex(LUA, rf"\n\s+{field} = ")

    def test_mythic_plus_pool_remains_dynamic(self):
        self.assertIn("C_ChallengeMode.GetMapTable()", LUA)
        self.assertNotRegex(LUA, r"challengeMapId\s*==\s*\d+")

    def test_active_runtime_has_no_season_1_contract(self):
        for stale_value in (
            "Dawncrest",
            "dawnlightManaflux",
            "radiantSparkDust",
            "sparksOfRadiance",
            "SPARK_OF_RADIANCE",
            "RADIANT_SPARK_DUST",
        ):
            self.assertNotIn(stale_value, LUA)

        self.assertNotIn('{ key = "nebulousVoidcore", id = 3418', LUA)

    def test_3418_is_used_only_as_quantity_source(self):
        self.assertRegex(LUA, r"quantityId = 3418")
        self.assertRegex(LUA, r"currencyDef\.quantityId")
        self.assertRegex(LUA, r"quantity = quantityInfo\.quantity or 0,")
        self.assertRegex(LUA, r"iconFileID = info\.iconFileID,")
        self.assertRegex(LUA, r"iconPath = GetTexturePath\(info\.iconFileID\),")
        self.assertRegex(LUA, r"id = currencyDef\.id,")

        defs = parse_currency_defs(LUA)
        self.assertEqual(defs["nebulousVoidcore"]["id"], 3513)
        self.assertEqual(defs["nebulousVoidcore"]["quantityId"], 3418)
        for key, defn in defs.items():
            if key != "nebulousVoidcore":
                self.assertIsNone(defn["quantityId"])

    def test_nebulous_voidcore_quantity_and_icon_two_source_contract(self):
        defs = parse_currency_defs(LUA)
        voidcore = defs["nebulousVoidcore"]
        self.assertEqual(voidcore["id"], 3513)
        self.assertEqual(voidcore["quantityId"], 3418)

        season2_icon = 123456

        def case(quantity_3418, quantity_3513):
            display = {
                "name": "Nebulous Voidcore",
                "quantity": quantity_3513,
                "maxQuantity": 0,
                "totalEarned": quantity_3513,
                "trackedQuantity": quantity_3513,
                "iconFileID": season2_icon,
            }
            quantity = {"quantity": quantity_3418, "iconFileID": 999888}
            return simulate_currency(voidcore, display, quantity)

        case_a = case(quantity_3418=0, quantity_3513=7)
        self.assertEqual(case_a["id"], 3513)
        self.assertEqual(case_a["quantity"], 0)
        self.assertEqual(case_a["iconFileID"], season2_icon)

        case_b = case(quantity_3418=1, quantity_3513=2)
        self.assertEqual(case_b["id"], 3513)
        self.assertEqual(case_b["quantity"], 1)
        self.assertEqual(case_b["iconFileID"], season2_icon)

    def test_other_season_2_currencies_keep_own_quantity_source(self):
        defs = parse_currency_defs(LUA)
        myth = defs["mythMistcrest"]
        self.assertEqual(myth["id"], 3446)
        self.assertIsNone(myth["quantityId"])

        result = simulate_currency(
            myth,
            {"name": "Myth Mistcrest", "quantity": 9, "iconFileID": 111},
            {"quantity": 99, "iconFileID": 222},
        )
        self.assertEqual(result["id"], 3446)
        self.assertEqual(result["quantity"], 9)
        self.assertEqual(result["iconFileID"], 111)


if __name__ == "__main__":
    unittest.main()
