"""
اختبارات «الأدوات» — فيبوناتشي، الارتكاز، الترند لاين، القناة.

الغرض المزدوج لهذه الاختبارات: التحقق من الصحة، **وإثبات أن كل أداة رسم
في المنصة ليست إلا حسابًا**. لا استيراد لأي منصة في أي سطر هنا.

اختبارات الارتكاز تستعمل الأرقام الموثّقة حرفيًا في المصدر
(المرحلة 2 الدرس 4)، فهي تحقّق مقابل قيم منصوص عليها لا مقابل توقعي أنا.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.fibonacci import EXTENSION_LEVELS, SOURCE_LEVELS, Impulse, measure
from bot.primitives.pivot import pivot_from_values, pivot_point, position
from bot.primitives.swings import find_swings
from bot.primitives.trendline import build, build_channel

T0 = datetime(2026, 1, 1)


def mk(*rows) -> Series:
    return Series(
        "M5",
        [
            Candle(T0 + timedelta(minutes=5 * i), o, h, l, c)
            for i, (o, h, l, c) in enumerate(rows)
        ],
    )


class TestPivotAgainstSourceValues(unittest.TestCase):
    """المرحلة 2 الدرس 4 — Pivot = (High + Low + Close) / 3."""

    def test_daily_matches_documented_value(self):
        p = pivot_from_values(4396.84, 4310.84, 4376.28, "daily")
        self.assertAlmostEqual(p.value, 4361.32, places=2)

    def test_weekly_matches_documented_value(self):
        p = pivot_from_values(4449.33, 4310.84, 4376.28, "weekly")
        self.assertAlmostEqual(p.value, 4378.8166666, places=5)

    def test_from_candle(self):
        c = Candle(T0, open=4350.0, high=4396.84, low=4310.84, close=4376.28)
        self.assertAlmostEqual(pivot_point(c).value, 4361.32, places=2)

    def test_position_relative_to_pivot(self):
        p = pivot_from_values(4396.84, 4310.84, 4376.28)
        self.assertEqual(position(4400.0, p), "above")
        self.assertEqual(position(4300.0, p), "below")
        self.assertEqual(position(p.value, p), "at")


class TestFibonacci(unittest.TestCase):
    """الدرس 6 — من القاع إلى القمة في الموجة الصاعدة."""

    def test_bullish_retracement_arithmetic(self):
        imp = measure(low=4300.0, high=4400.0, direction="bullish")
        self.assertEqual(imp.size, 100.0)
        self.assertEqual(imp.midpoint, 4350.0)
        self.assertAlmostEqual(imp.retracement(0.5), 4350.0)
        self.assertAlmostEqual(imp.retracement(0.618), 4338.2)
        self.assertAlmostEqual(imp.retracement(0.786), 4321.4)

    def test_bearish_retracement_mirrors(self):
        imp = measure(low=4300.0, high=4400.0, direction="bearish")
        self.assertAlmostEqual(imp.retracement(0.5), 4350.0)
        self.assertAlmostEqual(imp.retracement(0.618), 4361.8)

    def test_source_levels_are_the_three_used(self):
        self.assertEqual(SOURCE_LEVELS, [0.5, 0.618, 0.786])
        imp = measure(4300.0, 4400.0, "bullish")
        self.assertEqual(sorted(imp.levels().keys()), [0.5, 0.618, 0.786])

    def test_extension_targets(self):
        imp = measure(4300.0, 4400.0, "bullish")
        ext = imp.extensions()
        self.assertEqual(sorted(ext.keys()), sorted(EXTENSION_LEVELS))
        self.assertAlmostEqual(ext[1.0], 4400.0)
        self.assertAlmostEqual(ext[1.618], 4461.8)

    def test_premium_discount_gate(self):
        """الدرس 14 — الشراء فوق الـ50% غالٍ."""
        imp = measure(4300.0, 4400.0, "bullish")
        self.assertEqual(imp.value_of(4380.0), "premium")
        self.assertEqual(imp.value_of(4320.0), "discount")
        self.assertEqual(imp.value_of(4350.0), "midpoint")
        self.assertTrue(imp.is_expensive(4380.0, "bullish"))
        self.assertFalse(imp.is_expensive(4320.0, "bullish"))

    def test_golden_zone_between_618_and_786(self):
        lo, hi = measure(4300.0, 4400.0, "bullish").golden_zone()
        self.assertAlmostEqual(lo, 4321.4)
        self.assertAlmostEqual(hi, 4338.2)

    def test_rejects_inverted_impulse(self):
        with self.assertRaises(ValueError):
            measure(low=4400.0, high=4300.0, direction="bullish")


def sample() -> Series:
    """قاعان (5 ثم 7) وقمة بينهما (20) — الحد الأدنى لبناء ترند لاين وقناة."""
    return mk(
        (10, 12, 9, 11),
        (11, 13, 5, 12),     # قاع 5   · أدنى الجسم 11
        (12, 20, 10, 19),    # قمة 20
        (19, 19, 7, 8),      # قاع 7   · أدنى الجسم 8
        (10, 15, 8, 14),
    )


class TestTrendLine(unittest.TestCase):
    def test_line_is_two_points_and_arithmetic(self):
        s = sample()
        lows = [x for x in find_swings(s) if x.is_low]
        self.assertEqual([x.price for x in lows], [5, 7])

        line = build(s, lows, anchor="wick")
        self.assertIsNotNone(line)
        self.assertEqual(line.side, "support")
        self.assertEqual(line.slope, 1.0)        # (7 − 5) / (3 − 1)
        self.assertEqual(line.price_at(5), 9.0)  # امتداد للمستقبل — Ray

    def test_anchor_choice_changes_the_line(self):
        """التعارض C1 مكشوف كمعامل، لا مخفيًا في الكود."""
        s = sample()
        lows = [x for x in find_swings(s) if x.is_low]

        by_wick = build(s, lows, anchor="wick")
        by_body = build(s, lows, anchor="body")

        self.assertEqual((by_wick.y1, by_wick.y2), (5.0, 7.0))    # الذيول
        self.assertEqual((by_body.y1, by_body.y2), (11.0, 8.0))   # أدنى الأجسام
        self.assertGreater(by_wick.slope, 0)                       # صاعد
        self.assertLess(by_body.slope, 0)                          # هابط — خط مختلف تمامًا

    def test_break_detected_by_body(self):
        s = mk(
            (10, 12, 9, 11), (11, 13, 5, 12), (12, 20, 10, 19),
            (19, 19, 7, 8), (10, 15, 8, 14),
            (14, 15, 2, 3),                       # الجسم نزل إلى 3 والخط عند 9
        )
        lows = [x for x in find_swings(s) if x.is_low]
        line = build(s, lows, anchor="wick")
        self.assertEqual(line.price_at(5), 9.0)
        self.assertEqual(line.broken_at(s, use_body=True), 5)

    def test_requires_two_pivots(self):
        s = mk((10, 12, 9, 11), (11, 13, 5, 12), (12, 14, 6, 13))
        lows = [x for x in find_swings(s) if x.is_low]
        self.assertEqual(len(lows), 1)
        self.assertIsNone(build(s, lows))

    def test_rejects_mixed_pivot_kinds(self):
        s = sample()
        with self.assertRaises(ValueError):
            build(s, find_swings(s))


class TestChannel(unittest.TestCase):
    def test_parallel_channel_has_constant_width(self):
        s = sample()
        sw = find_swings(s)
        lows = [x for x in sw if x.is_low]
        high = next(x for x in sw if x.is_high)

        ch = build_channel(s, lows, high, anchor="wick")
        self.assertIsNotNone(ch)

        widths = [ch.upper_at(i) - ch.lower_at(i) for i in (1, 3, 5, 10)]
        for w in widths:
            self.assertAlmostEqual(w, widths[0])   # التوازي محفوظ ولو في المستقبل
        for i in (1, 3, 5):
            self.assertAlmostEqual(ch.mid_at(i), (ch.upper_at(i) + ch.lower_at(i)) / 2)

    def test_contains(self):
        s = sample()
        sw = find_swings(s)
        ch = build_channel(
            s, [x for x in sw if x.is_low], next(x for x in sw if x.is_high), "wick"
        )
        self.assertTrue(ch.contains(2, ch.mid_at(2)))
        self.assertFalse(ch.contains(2, ch.upper_at(2) + 1.0))


class TestNoPlatformDependency(unittest.TestCase):
    """برهان مباشر: أدوات الرسم حساب، ولا تستورد أي منصة."""

    def test_tools_import_no_platform_library(self):
        import bot.primitives.fibonacci as fib
        import bot.primitives.pivot as piv
        import bot.primitives.trendline as tl

        forbidden = ("import metatrader5", "import mt5", "tvdatafeed", "selenium", "playwright")
        for mod in (fib, piv, tl):
            with open(mod.__file__, encoding="utf-8") as fh:
                src = fh.read().lower()
            for token in forbidden:
                self.assertNotIn(token, src, f"{mod.__name__} يستورد {token}")

    def test_fib_levels_need_only_two_numbers(self):
        """قمة وقاع فقط — لا منصة ولا أداة رسم."""
        levels = measure(4300.0, 4400.0, "bullish").levels()
        self.assertEqual(len(levels), 3)
        self.assertTrue(all(4300.0 <= v <= 4400.0 for v in levels.values()))


class TestGateByClose(unittest.TestCase):
    """
    ⭐ البثّ المباشر: «الماكسيموم ماكسيموم ماكسيموم 50%؟
    **بس ما يغلق** — هي مش غالق فوق الـ50%»

    ⇒ الذيل فوق المنتصف مقبول · والإغلاق فوقه مرفوض.
    """

    IMP = Impulse(low=100.0, high=200.0, direction="bullish")   # المنتصف 150

    def _c(self, high, close):
        return Candle(datetime(2026, 8, 27, 9, 0), 140.0, high, 130.0, close)

    def test_wick_above_the_midpoint_is_accepted(self):
        """⭐ هذا هو جوهر التصحيح: اللمس لا يُسقط الإعداد."""
        self.assertFalse(self.IMP.closed_beyond_midpoint(self._c(170.0, 145.0), "bullish"))

    def test_close_above_the_midpoint_is_rejected(self):
        self.assertTrue(self.IMP.closed_beyond_midpoint(self._c(170.0, 160.0), "bullish"))

    def test_close_exactly_at_the_midpoint_is_accepted(self):
        """«ما يغلق فوق» — عند المنتصف ليس فوقه."""
        self.assertFalse(self.IMP.closed_beyond_midpoint(self._c(160.0, 150.0), "bullish"))

    def test_bearish_impulse_mirrors(self):
        imp = Impulse(low=100.0, high=200.0, direction="bearish")
        low_wick = Candle(datetime(2026, 8, 27, 9, 0), 160.0, 170.0, 130.0, 155.0)
        self.assertFalse(imp.closed_beyond_midpoint(low_wick, "bearish"))
        closed_below = Candle(datetime(2026, 8, 27, 9, 0), 160.0, 170.0, 130.0, 140.0)
        self.assertTrue(imp.closed_beyond_midpoint(closed_below, "bearish"))

    def test_it_differs_from_the_level_test(self):
        """البرهان أن التصحيح غيّر سلوكًا فعليًا لا صياغةً."""
        c = self._c(170.0, 145.0)
        self.assertTrue(self.IMP.is_expensive(c.high, "bullish"))       # بالذيل: غالٍ
        self.assertFalse(self.IMP.closed_beyond_midpoint(c, "bullish"))  # بالإغلاق: مقبول


if __name__ == "__main__":
    unittest.main(verbosity=2)
