"""
اختبارات إعادة تشغيل السلسلة على تاريخٍ حقيقيّ.

⛔ **ولماذا وُجد هذا الملفّ؟** لأنّ `replay.py` يصحّح نتيجة قراراتٍ
اتُّخذت ولا يعيد اتّخاذها — فقاعدةٌ جديدة في `chain.py` لا يظهر أثرها
فيه. وأسوأ: السجلّ يحمل **8.6% فقط** من شموع إطار التأكيد، فقاعدةٌ
تعمل عليه لا تُقاس على تسعة أعشارِ فراغ.
"""

import unittest
from datetime import datetime, timedelta

from bot.backtest import (_upto, confirm_bars_needed, coverage_gap,
                          decisions, render)


class TestConfirmBarsMustCoverThePoiRange(unittest.TestCase):
    """
    ⛔⛔ **ثلثُ نافذة القياس كان بلا شمعةِ تأكيدٍ واحدة** (كُشف 09-25).

        --poi-bars 1500 شمعة M15  ⇒  17.9 يومَ تداول
        --confirm-bars 5000 M3    ⇒  12.0 يومَ تداول
        ⇒ ستّةُ أيّامٍ يُرجع فيها `_upto` **سلسلةً فارغة**.

    فيبدو التنقيحُ فاشلًا وهو لم يُسأل، ويُرفض المسارُ الانعكاسيّ دائمًا.
    """

    def test_the_count_is_derived_not_written(self):
        self.assertEqual(confirm_bars_needed("M15", "M3", 1500), 8250)

    def test_the_old_default_was_short_by_a_third(self):
        need = confirm_bars_needed("M15", "M3", 1500)
        self.assertGreater(need, 5000)
        self.assertGreater((need - 5000) / need, 0.30)

    def test_other_pairs_scale_too(self):
        self.assertEqual(confirm_bars_needed("H1", "M5", 1000), 13200)
        self.assertEqual(confirm_bars_needed("H4", "M30", 500), 4400)

    def test_an_unknown_frame_falls_back_instead_of_guessing(self):
        self.assertEqual(confirm_bars_needed("???", "M3", 700), 700)
        self.assertEqual(confirm_bars_needed("M3", "M15", 700), 700)   # مقلوب

    def test_a_gap_is_shouted_not_swallowed(self):
        poi = series("M15", 15, 40)
        late = Series("M3", [Candle(T0 + timedelta(hours=6) + timedelta(minutes=3 * i),
                                    100, 100.5, 99.5, 100) for i in range(20)],
                      symbol="XAUUSD")
        msg = coverage_gap(poi, late)
        self.assertIsNotNone(msg)
        self.assertIn("6h", msg)
        self.assertTrue(msg.splitlines()[0].isascii())

    def test_full_coverage_says_nothing(self):
        poi = series("M15", 15, 40)
        conf = series("M3", 3, 400)
        self.assertIsNone(coverage_gap(poi, conf))

    def test_an_empty_series_is_named_not_passed_over(self):
        self.assertIn("EMPTY", coverage_gap(series("M15", 15, 10),
                                            Series("M3", [], symbol="XAUUSD")))
from bot.data import Candle, Series
from bot.replay import Result, Setup

T0 = datetime(2026, 9, 14, 0, 0)


def series(tf: str, step: int, n: int) -> Series:
    return Series(tf, [Candle(T0 + timedelta(minutes=step * i),
                              100, 100.5, 99.5, 100) for i in range(n)],
                  symbol="XAUUSD")


def result(name, outcome, pnl):
    s = Setup("M15", "buy", 100.0, 95.0, 110.0, T0.isoformat(), 1)
    r = Result(s, outcome)
    return r


class TestNoOrders(unittest.TestCase):
    def test_the_module_calls_no_execution_function(self):
        import bot.backtest as m
        with open(m.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("order_send", "order_check", "positions_close", "send_order("):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, src)


class TestItNeverReadsTheFuture(unittest.TestCase):
    """
    ⭐⭐⭐ **وهذا الفرق بين قياسٍ وبين خداعِ النفس.**

    لو أُعطيت السلسلةُ شمعةً لم تُغلق بعد — أو شموعَ تأكيدٍ لاحقةً
    للحظة القرار — لخرج الرقمُ مبهرًا وكاذبًا.
    """

    def test_confirm_bars_are_cut_at_the_decision_moment(self):
        conf = series("M3", 3, 20)
        cut = _upto(conf, T0 + timedelta(minutes=15))
        self.assertEqual(len(cut), 6)                    # 0,3,6,9,12,15
        self.assertLessEqual(cut[-1].time, T0 + timedelta(minutes=15))

    def test_a_moment_before_the_first_bar_yields_nothing(self):
        conf = series("M3", 3, 20)
        self.assertEqual(len(_upto(conf, T0 - timedelta(minutes=1))), 0)

    def test_the_whole_series_passes_when_the_moment_is_later(self):
        conf = series("M3", 3, 20)
        self.assertEqual(len(_upto(conf, T0 + timedelta(days=9))), 20)

    def test_the_window_never_exceeds_the_current_bar(self):
        """
        السلسلة تُعطى `poi[:i+1]` — فآخرُ شمعةٍ فيها هي شمعةُ القرار،
        ولا شمعةَ بعدها. ويُتحقَّق منه بمراقبة ما يصل إلى `evaluate`.
        """
        import bot.backtest as m
        poi, conf = series("M15", 15, 12), series("M3", 3, 60)
        seen = []
        original = m.evaluate

        def spy(p, c, cfg, *a, **k):
            seen.append((len(p), p[-1].time, c[-1].time if len(c) else None))
            return original(p, c, cfg, *a, **k)

        m.evaluate = spy
        try:
            decisions(poi, conf, "M15", "M3", spread=0.3)
        finally:
            m.evaluate = original

        self.assertEqual(len(seen), 12)
        for n, poi_last, conf_last in seen:
            self.assertLessEqual(conf_last, poi_last,
                                 "شمعةُ تأكيدٍ بعد لحظة القرار — قراءةُ مستقبل")

    def test_the_window_is_bounded(self):
        import bot.backtest as m
        poi, conf = series("M15", 15, 30), series("M3", 3, 150)
        sizes = []
        original = m.evaluate
        m.evaluate = lambda p, c, cfg, *a, **k: (sizes.append(len(p)),
                                                 original(p, c, cfg, *a, **k))[1]
        try:
            decisions(poi, conf, "M15", "M3", spread=0.3, window=5)
        finally:
            m.evaluate = original
        self.assertLessEqual(max(sizes), 5)


class TestRange(unittest.TestCase):
    def test_since_and_until_bound_the_walk(self):
        import bot.backtest as m
        poi, conf = series("M15", 15, 40), series("M3", 3, 200)
        seen = []
        original = m.evaluate
        m.evaluate = lambda p, c, cfg, *a, **k: (seen.append(p[-1].time),
                                                 original(p, c, cfg, *a, **k))[1]
        try:
            decisions(poi, conf, "M15", "M3", spread=0.3,
                      since=T0 + timedelta(minutes=60),
                      until=T0 + timedelta(minutes=120))
        finally:
            m.evaluate = original
        self.assertTrue(all(T0 + timedelta(minutes=60) <= t
                            <= T0 + timedelta(minutes=120) for t in seen))
        self.assertEqual(len(seen), 5)       # 60,75,90,105,120


class TestRender(unittest.TestCase):
    def test_no_difference_is_said_plainly(self):
        """⭐ «لا أثر» رقمٌ كباقي الأرقام — ولا يُخفى."""
        runs = [("بلا هارمونيك", [], []), ("مع الهارمونيك", [], [])]
        self.assertIn("لا أثر", render(runs))

    def test_the_limits_are_printed_with_the_number_not_after_it(self):
        runs = [("أ", [], []), ("ب", [], [])]
        self.assertIn("الملتبس يُحسب خسارة", render(runs))


if __name__ == "__main__":
    unittest.main(verbosity=2)
