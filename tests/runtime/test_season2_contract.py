import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LUA = (ROOT / "KeystoneSync.lua").read_text(encoding="utf-8")
TOC = (ROOT / "KeystoneSync.toc").read_text(encoding="utf-8")


class Season2ContractTests(unittest.TestCase):
    def test_interface_and_currency_contract(self):
        self.assertIn("## Interface: 120100", TOC)

        expected = {
            "adventurerMistcrest": 3442,
            "veteranMistcrest": 3443,
            "championMistcrest": 3444,
            "heroMistcrest": 3445,
            "mythMistcrest": 3446,
            "venomblightManaflux": 3465,
            "tidalSparkDust": 3509,
            "cofferKeyShards": 3310,
            "restoredCofferKey": 3028,
            "nebulousVoidcore": 3513,
        }
        actual = {
            key: int(currency_id)
            for key, currency_id in re.findall(
                r'\{ key = "([^"]+)", id = (\d+) \}', LUA
            )
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
            "3418",
        ):
            self.assertNotIn(stale_value, LUA)


if __name__ == "__main__":
    unittest.main()
