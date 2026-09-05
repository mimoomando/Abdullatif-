"""
اختبارات التعلّم من الأخطاء.

⛔ الحدّ المحوريّ: **لا يُغيَّر معامل SOURCE أبدًا** — تلك قواعد المدرّب.
والتعلّم محصور في الفراغات التي تركها المصدر (`UNDEFINED`)، ويقترح
ولا يطبّق.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle
from bot.learning import (
    KNOB_FOR,
    Lesson,
    Mistake,
    RiskLedger,
    diagnose,
    lessons,
    render_lessons,
)
from bot.reporting import TradeJournal, TradeRationale
from bot import params as P

T0 = datetime(2026, 9, 5, 10, 0)


def rationale(direction="buy", entry=100.0, stop=98.0, targets=(106.0,)):
    r = TradeRationale(
        symbol="XAUUSD.m", direction=direction,
        poi_timeframe="M15", confirm_timeframe="M3", detected_at=T0,
    )
    r.entry, r.stop, r.targets = entry, stop, list(targets)
    return r


def journal(direction="buy", entry=100.0, stop=98.0, targets=(106.0,)):
    return TradeJournal(
        rationale=rationale(direction, entry, stop, targets),
        opened_at=T0, entry=entry,
    )


def candles(*prices, start=T0):
    return [
        Candle(start + timedelta(minutes=3 * i), p, p + 1, p - 1, p)
        for i, p in enumerate(prices)
    ]


class TestDiagnose(unittest.TestCase):
    def test_an_open_trade_is_not_diagnosed(self):
        self.assertEqual(diagnose(journal()), [])

    def test_a_plain_loss_is_not_a_mistake(self):
        """
        ⭐ الخسارة وحدها ليست خطأً. منهجٌ سليم يخسر، وتسميةُ كل خسارة
        خطأً تُفسد التعلّم من أصله.
        """
        j = journal()
        j.observe(T0, 103.0)                 # تحرّكت لصالحك ثم عادت
        j.close(T0 + timedelta(minutes=30), 98.0, "sl")
        self.assertEqual(diagnose(j), [])

    def test_entry_wrong_when_it_never_moved_your_way(self):
        j = journal()
        j.observe(T0, 99.0)
        j.close(T0 + timedelta(minutes=30), 98.0, "sl")
        kinds = [m.kind for m in diagnose(j)]
        self.assertIn("entry_wrong", kinds)

    def test_stop_too_tight_needs_what_happened_after(self):
        """
        بلا رؤية ما بعد الإغلاق، «ضُرب الوقف» و«الوقف ضيّق» لا يفترقان.
        """
        j = journal()
        j.observe(T0, 101.0)
        j.close(T0 + timedelta(minutes=30), 98.0, "sl")

        self.assertNotIn("stop_too_tight", [m.kind for m in diagnose(j)])

        after = candles(99.0, 102.0, 107.0)          # بلغ الهدف 106
        self.assertIn("stop_too_tight", [m.kind for m in diagnose(j, after)])

    def test_stop_too_tight_not_raised_if_the_target_never_came(self):
        j = journal()
        j.observe(T0, 101.0)
        j.close(T0 + timedelta(minutes=30), 98.0, "sl")
        after = candles(97.0, 96.0, 95.0)
        self.assertNotIn("stop_too_tight", [m.kind for m in diagnose(j, after)])

    def test_sell_side_after_window(self):
        j = journal(direction="sell", entry=100.0, stop=102.0, targets=(94.0,))
        j.observe(T0, 99.0)
        j.close(T0 + timedelta(minutes=30), 102.0, "sl")
        after = candles(101.0, 98.0, 93.0)
        self.assertIn("stop_too_tight", [m.kind for m in diagnose(j, after)])

    def test_gave_back_when_the_target_was_reached_in_passing(self):
        j = journal()
        j.observe(T0, 107.0)                 # تجاوز الهدف 106 مرورًا
        j.close(T0 + timedelta(minutes=30), 99.0, "manual")
        kinds = [m.kind for m in diagnose(j)]
        self.assertIn("gave_back", kinds)

    def test_gave_back_not_raised_when_it_closed_on_target(self):
        j = journal()
        j.observe(T0, 107.0)
        j.close(T0 + timedelta(minutes=30), 106.0, "tp")
        self.assertNotIn("gave_back", [m.kind for m in diagnose(j)])

    def test_sleeping_that_helped_is_not_a_mistake(self):
        j = journal()
        j.note_session_break(T0, 100.0, T0 + timedelta(hours=8), 104.0)
        j.close(T0 + timedelta(hours=9), 106.0, "tp")
        self.assertNotIn("slept_and_harmed", [m.kind for m in diagnose(j)])

    def test_sleeping_that_harmed_is(self):
        j = journal()
        j.note_session_break(T0, 100.0, T0 + timedelta(hours=8), 96.0)
        j.close(T0 + timedelta(hours=9), 98.0, "sl")
        self.assertIn("slept_and_harmed", [m.kind for m in diagnose(j)])

    def test_mistake_renders_its_evidence(self):
        m = Mistake("entry_wrong", "دليل")
        self.assertIn("دليل", m.render())
        self.assertIn("دخول خاطئ", m.render())


class TestSourceIsLocked(unittest.TestCase):
    """⛔ أهمّ اختبار في الملفّ: قواعد المدرّب لا تُضبط من البيانات."""

    def test_a_source_knob_is_flagged_locked_not_proposed(self):
        diag = [[Mistake("slept_and_harmed", "x")] for _ in range(5)]
        got = lessons(diag)
        self.assertEqual(len(got), 1)
        lesson = got[0]
        if lesson.origin == "SOURCE":
            self.assertTrue(lesson.locked)
            self.assertIn("تعارض", lesson.render())
            self.assertNotIn("يقترح مراجعة", lesson.render())

    def test_locked_lessons_never_say_they_propose_a_change(self):
        for kind, knob in KNOB_FOR.items():
            p = P.registry().get(knob)
            with self.subTest(kind=kind):
                self.assertIsNotNone(p, f"{knob} غير موجود في params")
                l = Lesson(kind, 5, 10, knob, p.origin)
                if l.locked:
                    self.assertIn("🔒", l.render())
                else:
                    self.assertIn("اقتراح لا تطبيق", l.render())

    def test_every_mistake_maps_to_a_real_parameter(self):
        reg = P.registry()
        for kind, knob in KNOB_FOR.items():
            with self.subTest(kind=kind):
                self.assertIn(knob, reg)

    def test_the_footer_states_nothing_is_auto_applied(self):
        diag = [[Mistake("entry_wrong", "x")] for _ in range(4)]
        out = render_lessons(lessons(diag))
        self.assertIn("لا يُغيَّر أي معامل تلقائيًّا", out)


class TestLessons(unittest.TestCase):
    def test_a_single_occurrence_is_not_a_lesson(self):
        diag = [[Mistake("entry_wrong", "x")], [], []]
        self.assertEqual(lessons(diag), [])

    def test_repetition_makes_a_lesson(self):
        diag = [[Mistake("entry_wrong", "x")] for _ in range(3)]
        got = lessons(diag)
        self.assertEqual(got[0].kind, "entry_wrong")
        self.assertEqual(got[0].count, 3)
        self.assertAlmostEqual(got[0].share, 1.0)

    def test_duplicates_within_one_trade_count_once(self):
        diag = [[Mistake("entry_wrong", "a"), Mistake("entry_wrong", "b")]] * 3
        self.assertEqual(lessons(diag)[0].count, 3)

    def test_sorted_by_frequency(self):
        diag = ([[Mistake("entry_wrong", "x")]] * 5
                + [[Mistake("gave_back", "y")]] * 3)
        got = lessons(diag)
        self.assertEqual(got[0].kind, "entry_wrong")
        self.assertGreater(got[0].count, got[1].count)

    def test_min_count_below_two_rejected(self):
        with self.assertRaises(ValueError):
            lessons([], min_count=1)

    def test_empty_renders_a_reassurance_not_a_blank(self):
        out = render_lessons([])
        self.assertIn("المنهج السليم يخسر", out)


class TestRiskLedger(unittest.TestCase):
    """قرار المستخدم: **لا حدّ — يسجّل ولا يوقِف.**"""

    def _closed(self, day, result, entry=100.0):
        j = journal()
        at = datetime(2026, 9, day, 12, 0)
        j.close(at, entry + result, "tp" if result > 0 else "sl")
        return j

    def _ledger(self, *specs):
        return RiskLedger(journals=[self._closed(d, r) for d, r in specs])

    def test_empty_ledger_renders(self):
        self.assertIn("لا صفقات مغلقة", RiskLedger().render())

    def test_open_trades_are_excluded(self):
        led = RiskLedger(journals=[journal()])
        self.assertEqual(led.closed(), [])

    def test_net_uses_one_dollar_per_unit(self):
        led = self._ledger((1, -2.0), (1, 6.0))
        self.assertAlmostEqual(led.net(), 4.0)

    def test_streaks(self):
        led = self._ledger((1, -2.0), (1, -2.0), (1, 5.0), (1, -2.0), (1, -2.0), (1, -2.0))
        self.assertEqual(led.streaks(), [2, 3])
        self.assertEqual(led.longest_streak, 3)
        self.assertEqual(led.current_streak, 3)

    def test_current_streak_zero_after_a_win(self):
        led = self._ledger((1, -2.0), (1, 5.0))
        self.assertEqual(led.current_streak, 0)

    def test_by_day_and_worst_day(self):
        led = self._ledger((1, -2.0), (1, -3.0), (2, 4.0))
        self.assertAlmostEqual(led.by_day()[datetime(2026, 9, 1).date()], -5.0)
        self.assertEqual(led.worst_day()[1], -5.0)

    def test_streak_limit_counterfactual_positive_when_useful(self):
        """ثلاث خسائر ثم رابعة — حدُّ 3 كان سيوفّر الرابعة."""
        led = self._ledger((1, -2.0), (1, -2.0), (1, -2.0), (1, -5.0))
        self.assertAlmostEqual(led.saved_by_streak_limit(3), 5.0)

    def test_streak_limit_counterfactual_negative_when_costly(self):
        """لو جاء ربحٌ بعد السلسلة، الحدّ كان سيحرمك إياه."""
        led = self._ledger((1, -2.0), (1, -2.0), (1, 9.0))
        self.assertAlmostEqual(led.saved_by_streak_limit(2), -9.0)

    def test_the_limit_resets_each_day(self):
        """مفتاح التوقّف يُعاد ضبطه كل صباح — فلا تعبر السلسلة اليوم."""
        led = self._ledger((1, -2.0), (1, -2.0),
                           (2, -2.0), (2, -2.0), (2, -9.0))
        # لو عبرت السلسلة اليوم لتخطّى صفقات اليوم الثاني كلَّها (13$)
        self.assertAlmostEqual(led.saved_by_streak_limit(2), 9.0)

    def test_daily_cap_counterfactual(self):
        led = self._ledger((1, -6.0), (1, -6.0), (1, -20.0))
        self.assertAlmostEqual(led.saved_by_daily_cap(10.0), 20.0)

    def test_daily_cap_not_reached_saves_nothing(self):
        led = self._ledger((1, -2.0), (1, -3.0))
        self.assertAlmostEqual(led.saved_by_daily_cap(50.0), 0.0)

    def test_invalid_thresholds_rejected(self):
        led = self._ledger((1, -2.0))
        with self.assertRaises(ValueError):
            led.saved_by_streak_limit(0)
        with self.assertRaises(ValueError):
            led.saved_by_daily_cap(0)

    def test_render_shows_what_each_limit_would_have_saved(self):
        out = self._ledger((1, -2.0), (1, -2.0), (1, -5.0)).render()
        self.assertIn("يسجّل ولا يوقِف", out)
        self.assertIn("ماذا كان سيوفّر", out)
        self.assertIn("أطول سلسلة خسائر", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
