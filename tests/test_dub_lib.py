import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/cartoon-pipeline"))
import dub_lib


class NormTokensTests(unittest.TestCase):
    def test_hyphenated_number_words_match_digit_compounds(self):
        # script says "twenty-one day", whisper hears "21-day"
        self.assertEqual(
            dub_lib.norm_tokens("their twenty-one day window"),
            dub_lib.norm_tokens("their 21-day window"),
        )

    def test_plain_digits_match_number_words(self):
        self.assertEqual(dub_lib.norm_tokens("fifty"), dub_lib.norm_tokens("50"))
        self.assertEqual(dub_lib.norm_tokens("three"), dub_lib.norm_tokens("3"))

    def test_years_stay_digits_on_both_sides(self):
        self.assertEqual(dub_lib.norm_tokens("before 2005."), ["before", "2005"])

    def test_punctuation_and_case_are_stripped(self):
        self.assertEqual(dub_lib.norm_tokens('He said: "DENIED!"'), ["he", "said", "denied"])


if __name__ == "__main__":
    unittest.main()
