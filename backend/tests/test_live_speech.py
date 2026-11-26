from unittest import TestCase
from unittest.mock import patch

from backend.services.live_speech import normalize_speech


class LiveSpeechTests(TestCase):
    def test_english_ordinals_and_years(self):
        self.assertEqual(normalize_speech("5th 1st 2nd 3rd 12th", "en-in"),
                         "fifth first second third twelfth")
        self.assertEqual(normalize_speech("2025–26, 150, 1200", "en-in"),
                         "two thousand twenty-five to two thousand twenty-six, one hundred fifty, one thousand two hundred")

    def test_credits_fractions_currency_and_identifier(self):
        self.assertEqual(normalize_speech("3.5, 75%, 4–6 credits; CSE-502", "en-in"),
                         "three point five, seventy-five percent, four to six credits; C S E five zero two")
        self.assertEqual(normalize_speech("₹1200, 3/4, 12/02/2026", "en-in"),
                         "one thousand two hundred Indian rupees, three over four, twelve February two thousand twenty-six")

    def test_indic_and_gender(self):
        with patch.dict("os.environ", {"TAVUS_AVATAR_GENDER": "feminine"}):
            self.assertEqual(normalize_speech("मैं समझ गया। 3.5", "hi"),
                             "मैं समझ गई। तीन दशमलव पाँच")
        with patch.dict("os.environ", {"TAVUS_AVATAR_GENDER": "masculine"}):
            self.assertEqual(normalize_speech("હું સમજી ગઈ. ૩.૫", "mixed"),
                             "હું સમજી ગયો. ત્રણ દશાંશ પાંચ")
