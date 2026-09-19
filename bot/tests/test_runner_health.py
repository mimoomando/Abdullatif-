"""
حارسا الصحّة — وكلاهما بُني بعد عطبٍ وقع لا احتياطًا.

⛔ في أسبوع 09-14 سقطت منصّة MT5 ليلة الثلاثاء. فـ:
   · صمتت الحلقة ثلاثة أيّام، والنافذة بقيت حيّةَ المظهر
   · وانتفخ errors.jsonl إلى 13.3 ميغابايت من نسخٍ متطابقة
     مقابل 0.3 ميغابايت من القرارات
"""

import json
import os
import tempfile
import unittest

from bot.runner import Heartbeat, Recorder, RunConfig


class TestHeartbeatSpeaksWhenSilent(unittest.TestCase):
    """الصمتُ نفسه يُطبع — وسطرٌ يتغيّر هو وحده ما يثبت الحياة."""

    def test_a_working_pass_says_nothing(self):
        h = Heartbeat()
        self.assertIsNone(h.beat(3))
        self.assertIsNone(h.beat(1))

    def test_it_stays_quiet_below_the_threshold(self):
        h = Heartbeat(alarm_after=3)
        self.assertIsNone(h.beat(0))
        self.assertIsNone(h.beat(0))

    def test_it_alarms_on_the_threshold_pass(self):
        h = Heartbeat(alarm_after=3)
        h.beat(0); h.beat(0)
        msg = h.beat(0)
        self.assertIsNotNone(msg)
        self.assertIn("MetaTrader", msg)

    def test_it_keeps_alarming_every_pass_not_once(self):
        """
        ⭐ جوهرُ الإصلاح: إنذارٌ **يتكرّر**.

        فإنذارٌ مرّةً واحدة يصعد في الشاشة ويختفي، وتعود النافذة
        ساكنةً — وهي الحالة نفسها التي كلّفتنا ثلاثة أيّام.
        """
        h = Heartbeat(alarm_after=2)
        h.beat(0)
        msgs = [h.beat(0) for _ in range(5)]
        self.assertTrue(all(m for m in msgs), "الإنذار سكت قبل أن يعود التسجيل")
        self.assertIn("6 تمريرة", msgs[-1])       # والعدّاد يتزايد

    def test_recovery_is_announced_once_then_silence_returns(self):
        h = Heartbeat(alarm_after=2)
        h.beat(0); h.beat(0)
        back = h.beat(2)
        self.assertIn("عاد التسجيل", back)
        self.assertIsNone(h.beat(2))

    def test_a_single_good_pass_resets_the_counter(self):
        h = Heartbeat(alarm_after=3)
        h.beat(0); h.beat(0); h.beat(1)
        self.assertIsNone(h.beat(0))
        self.assertIsNone(h.beat(0))


class TestErrorLogFoldsRepeats(unittest.TestCase):
    """المتطابق المتتالي يُكتب مرّةً، ثم يُعَدّ."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.rec = Recorder(RunConfig(out_dir=self.dir, save_charts=False,
                                      save_dossiers=False))

    def _rows(self):
        p = self.rec.cfg.errors_path
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_the_first_one_carries_its_trace(self):
        self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertIn("trace", rows[0])

    def test_identical_repeats_are_muted(self):
        for _ in range(50):
            self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        self.assertEqual(len(self._rows()), 1, "المكرَّر كُتب مرّةً بعد أخرى")

    def test_one_counting_line_lands_every_hundred(self):
        for _ in range(201):
            self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        rows = self._rows()
        self.assertEqual([r.get("repeats") for r in rows], [None, 100, 200])
        self.assertNotIn("trace", rows[1])        # سطرُ عدٍّ لا تتبُّع

    def test_a_different_error_is_never_folded_behind_an_old_one(self):
        """⛔ ولا يُطوى عطبٌ جديد خلف قديم — وإلّا لأخفى الحارسُ ما جاء له."""
        for _ in range(50):
            self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        self.rec.write_error("pair:H1", ValueError("رمزٌ غير معروف"))
        rows = self._rows()
        self.assertEqual(len(rows), 2)
        self.assertIn("trace", rows[-1])

    def test_rotating_pairs_are_each_folded_on_their_own(self):
        """
        ⭐⭐ **الحالة التي أسقطت أوّل صياغةٍ لهذا الإصلاح.**

        الأزواج تتناوب، فمقارنةُ الخطأ بسابقه وحده لا تطوي شيئًا.
        والعدّ يجب أن يكون **لكل بصمةٍ على حدة**.
        """
        for i in range(300):
            self.rec.write_error(f"pair:{['H4', 'H1', 'M15'][i % 3]}",
                                 RuntimeError("IPC send failed"))
        rows = self._rows()
        self.assertEqual(sum(1 for r in rows if "trace" in r), 3)
        self.assertEqual(len(rows), 3, "التناوبُ أفلت من الطيّ")

    def test_the_same_text_from_a_different_place_is_not_folded(self):
        for _ in range(20):
            self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        self.rec.write_error("pair:M15", RuntimeError("IPC send failed"))
        self.assertEqual(len(self._rows()), 2)

    def test_the_week_that_caused_this_would_have_stayed_small(self):
        """
        ⭐ القياس: 13.3 ميغابايت صارت كم؟

        ثلاثة أزواج × تمريرةٍ كل دقيقة × ثلاثة أيّام ≈ 12,960 خطأ.
        """
        for i in range(12960):
            self.rec.write_error(f"pair:{['H4','H1','M15'][i % 3]}",
                                 RuntimeError("IPC send failed"))
        size = os.path.getsize(self.rec.cfg.errors_path)
        self.assertLess(size, 200_000, f"الملفّ ما زال ضخمًا: {size} بايت")


if __name__ == "__main__":
    unittest.main(verbosity=2)
