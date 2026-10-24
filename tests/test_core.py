import datetime as dt
import unittest

from history_briefed.config import load_config
from history_briefed.episode import build_spec, load_all
from history_briefed.schedule import slots


class Core(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    def test_slots_are_mon_wed_fri_at_four(self):
        for s in slots(self.cfg, 12):
            self.assertIn(s.weekday(), (0, 2, 4))
            self.assertEqual((s.hour, s.minute), (16, 0))

    def test_slots_strictly_increasing(self):
        s = slots(self.cfg, 20)
        self.assertTrue(all(a < b for a, b in zip(s, s[1:])))

    def test_dst_keeps_local_time(self):
        self.cfg["schedule"]["start_date"] = "2027-03-29"  # across Sydney's April DST end
        s = slots(self.cfg, 6)
        self.assertTrue(all(x.hour == 16 for x in s))
        self.assertNotEqual(s[0].utcoffset(), s[-1].utcoffset())

    def test_episodes_valid_and_end_with_fixed_outro(self):
        for ep in load_all():
            spec = build_spec(self.cfg, ep)
            self.assertEqual(spec[-1]["narration"], self.cfg["outro"]["brand_line"])
            self.assertEqual(spec[-1]["visuals"][0]["kind"], "outro")
            self.assertEqual(spec[-2]["narration"], self.cfg["outro"]["subscribe_line"])

    def test_estimated_length_over_twenty_seconds(self):
        wps = self.cfg["tts"]["words_per_second_fallback"]
        for ep in load_all():
            n = sum(len(s["narration"].split()) for s in build_spec(self.cfg, ep))
            self.assertGreaterEqual(n / wps, self.cfg["video"]["min_seconds"])


if __name__ == "__main__":
    unittest.main()
