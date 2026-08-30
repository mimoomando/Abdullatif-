"""
اختبارات الأنماط الاستمرارية — الدرس 8.

⭐ الشرط الفاصل: **عمق التصحيح**. 38% سليم · 50% على الأطر الكبيرة ·
61.8% **باطل** — «ما بقى نموذج استمراري، صار انعكاس».
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.continuation import (
    INVALIDATING_RETRACE,
    MAX_RETRACE,
    Consolidation,
    PatternInvalid,
    build,
    find_breakout,
    measure_retrace,
)
from bot.primitives.fibonacci import Impulse

T0 = datetime(2026, 8, 30, 9, 0)


def mk(tf, *rows) -> Series:
    return Series(
        tf,
        [Candle(T0 + timedelta(minutes=15 * i), o, h, l, c)
         for i, (o, h, l, c) in enumerate(rows)],
    )


def rising_flag(rest_low: float, tf: str = "M15") -> Series:
    """
    اندفاع صاعد 100 → 200 بالأجسام، ثم راحة تنزل إلى `rest_low`.

    فهارس: 0 بداية الاندفاع · 2 نهايته · 4 نهاية الراحة.
    """
    return mk(
        tf,
        (100, 152, 99, 150),
        (150, 182, 149, 180),
        (180, 202, 179, 200),
        (198, 199, rest_low, rest_low + 1),
        (rest_low + 1, rest_low + 3, rest_low, rest_low + 2),
        (rest_low + 2, 210, rest_low + 1, 208),
        (208, 212, 199, 210),
    )


class TestRetraceDepth(unittest.TestCase):
    def test_shallow_pullback_is_clean(self):
        """التصحيح 20% ⇒ سليم على أي إطار."""
        p = build(rising_flag(180.0), 0, 2, 4)
        self.assertAlmostEqual(p.retrace, 0.2)
        self.assertEqual(p.grade, "clean")
        self.assertTrue(p.valid)

    def test_618_is_refused_not_downgraded(self):
        """«ما بقى نموذج استمراري» — رفض صريح لا كائن ضعيف."""
        with self.assertRaises(PatternInvalid):
            build(rising_flag(138.0), 0, 2, 4)      # تصحيح 62%

    def test_deeper_than_618_also_refused(self):
        with self.assertRaises(PatternInvalid):
            build(rising_flag(120.0), 0, 2, 4)

    def test_45_percent_is_tolerated_on_a_higher_timeframe(self):
        p = build(rising_flag(155.0, tf="H4"), 0, 2, 4)
        self.assertAlmostEqual(p.retrace, 0.45)
        self.assertEqual(p.grade, "tolerated")
        self.assertTrue(p.valid)

    def test_the_same_45_percent_is_unstated_on_m15(self):
        """
        النصّ يسمح بالـ50 **بالفريمات الكبيرة**. فعلى M15 هو ليس مقبولًا
        ولا باطلًا — **غير منصوص** (CP1)، ولا يُعامَل معاملة السليم.
        """
        p = build(rising_flag(155.0, tf="M15"), 0, 2, 4)
        self.assertEqual(p.grade, "unstated")
        self.assertFalse(p.valid)

    def test_boundary_382_is_still_clean(self):
        p = build(rising_flag(200 - 38.2), 0, 2, 4)
        self.assertAlmostEqual(p.retrace, MAX_RETRACE, places=6)
        self.assertEqual(p.grade, "clean")

    def test_measure_retrace_bearish(self):
        imp = Impulse(low=100.0, high=200.0, direction="bearish")
        rest = Consolidation(start=3, end=4, high=130.0, low=105.0)
        self.assertAlmostEqual(measure_retrace(imp, rest, "bearish"), 0.30)

    def test_zero_size_impulse_rejected(self):
        with self.assertRaises(ValueError):
            Impulse(low=100.0, high=100.0, direction="bullish")


class TestGeometry(unittest.TestCase):
    def test_impulse_is_measured_on_bodies(self):
        """الاندفاع بالأجسام — والذيول تتجاوزه ولا تدخل في القياس."""
        p = build(rising_flag(180.0), 0, 2, 4)
        self.assertEqual(p.impulse.low, 100.0)      # افتتاح أول شمعة
        self.assertEqual(p.impulse.high, 200.0)     # إغلاق آخرها
        self.assertEqual(p.price_range, 100.0)

    def test_consolidation_bounds_are_wicks(self):
        """«حدود العلم بترسمها على ذيول الشموع» — عكس ترند لاين الهيكل."""
        p = build(rising_flag(180.0), 0, 2, 4)
        self.assertEqual(p.consolidation.low, 180.0)
        self.assertEqual(p.breakout_level, p.consolidation.high)

    def test_target_copies_the_range_from_the_break(self):
        """«بنسخه وبحطه عند نقطة الكسر»."""
        p = build(rising_flag(180.0), 0, 2, 4)
        self.assertAlmostEqual(p.target(205.0), 305.0)

    def test_target_defaults_to_the_pattern_boundary(self):
        p = build(rising_flag(180.0), 0, 2, 4)
        self.assertAlmostEqual(p.target(), p.breakout_level + 100.0)

    def test_bearish_target_goes_down(self):
        s = mk(
            "M15",
            (200, 201, 148, 150),
            (150, 151, 98, 100),
            (100, 122, 99, 120),
            (120, 121, 105, 110),
            (110, 111, 95, 96),
            (96, 97, 80, 85),
        )
        p = build(s, 0, 1, 3)
        self.assertEqual(p.direction, "bearish")
        self.assertLess(p.target(), p.breakout_level)

    def test_direction_read_from_the_leg(self):
        self.assertEqual(build(rising_flag(180.0), 0, 2, 4).direction, "bullish")

    def test_pennant_shape_is_carried(self):
        p = build(rising_flag(180.0), 0, 2, 4, shape="pennant")
        self.assertEqual(p.shape, "pennant")
        self.assertIn("مثلث", p.render())

    def test_indices_must_ascend(self):
        s = rising_flag(180.0)
        for a, b, c in ((2, 1, 4), (0, 2, 2), (0, 2, 99)):
            with self.subTest(idx=(a, b, c)):
                with self.assertRaises(ValueError):
                    build(s, a, b, c)


class TestBreakout(unittest.TestCase):
    """«بستنى كسر حدّ العلم، وبيفضّل يرجع يعمل ريتست»."""

    def _pattern(self):
        return build(rising_flag(180.0), 0, 2, 4)

    def test_break_then_retest_confirms(self):
        s = mk(
            "M15",
            (100, 152, 99, 150), (150, 182, 149, 180), (180, 202, 179, 200),
            (198, 199, 180, 181), (181, 183, 180, 182),      # راحة · الحدّ 199
            (182, 206, 181, 205),                            # كسر بالجسم
            (205, 206, 199, 204),                            # ريتست
        )
        p = build(s, 0, 2, 4)
        b = find_breakout(s, p, retest_tolerance=0.5)
        self.assertEqual(b.break_index, 5)
        self.assertEqual(b.retest_index, 6)
        self.assertTrue(b.confirmed)
        self.assertEqual(b.entry, 205.0)

    def test_break_without_retest_is_not_confirmed(self):
        """CP3 — الريتست مُلزم في الكود وإن كان «مفضَّلًا» في النصّ."""
        s = mk(
            "M15",
            (100, 152, 99, 150), (150, 182, 149, 180), (180, 202, 179, 200),
            (198, 199, 180, 181), (181, 183, 180, 182),
            (182, 206, 181, 205),
            (205, 240, 204, 238),                            # هرب بلا عودة
        )
        p = build(s, 0, 2, 4)
        b = find_breakout(s, p, retest_tolerance=0.5)
        self.assertIsNone(b.retest_index)
        self.assertFalse(b.confirmed)
        self.assertIsNone(b.entry)

    def test_a_wick_through_the_line_is_not_a_break(self):
        """الحدّ يُرسم بالذيول ويُكسر بالأجسام — «الكسر بالجسم»."""
        s = mk(
            "M15",
            (100, 152, 99, 150), (150, 182, 149, 180), (180, 202, 179, 200),
            (198, 199, 180, 181), (181, 183, 180, 182),
            (182, 205, 181, 190),                            # ذيل فوق 199 فقط
        )
        p = build(s, 0, 2, 4)
        self.assertIsNone(find_breakout(s, p, retest_tolerance=0.5))

    def test_close_back_inside_ends_the_search_for_a_retest(self):
        s = mk(
            "M15",
            (100, 152, 99, 150), (150, 182, 149, 180), (180, 202, 179, 200),
            (198, 199, 180, 181), (181, 183, 180, 182),
            (182, 206, 181, 205),
            (205, 206, 185, 187),                            # أغلق داخل الراحة
            (187, 200, 186, 199),                            # عودة متأخرة لا تُحتسب
        )
        p = build(s, 0, 2, 4)
        b = find_breakout(s, p, retest_tolerance=0.5)
        self.assertFalse(b.confirmed)

    def test_no_break_returns_none(self):
        s = rising_flag(180.0)
        p = build(s, 0, 2, 4)
        self.assertIsNotNone(p)                      # الشمعة 5 تكسر فعلًا
        flat = mk(
            "M15",
            (100, 152, 99, 150), (150, 182, 149, 180), (180, 202, 179, 200),
            (198, 199, 180, 181), (181, 183, 180, 182),
            (182, 190, 181, 185), (185, 191, 184, 188),
        )
        self.assertIsNone(find_breakout(flat, build(flat, 0, 2, 4), 0.5))

    def test_negative_tolerance_rejected(self):
        s = rising_flag(180.0)
        with self.assertRaises(ValueError):
            find_breakout(s, build(s, 0, 2, 4), retest_tolerance=-1)

    def test_breakout_target_uses_the_actual_break_price(self):
        s = mk(
            "M15",
            (100, 152, 99, 150), (150, 182, 149, 180), (180, 202, 179, 200),
            (198, 199, 180, 181), (181, 183, 180, 182),
            (182, 206, 181, 205), (205, 206, 199, 204),
        )
        p = build(s, 0, 2, 4)
        b = find_breakout(s, p, retest_tolerance=0.5)
        self.assertAlmostEqual(b.target, 205.0 + 100.0)


class TestConstants(unittest.TestCase):
    def test_thresholds_match_the_lesson(self):
        self.assertAlmostEqual(MAX_RETRACE, 0.382)
        self.assertAlmostEqual(INVALIDATING_RETRACE, 0.618)


if __name__ == "__main__":
    unittest.main(verbosity=2)
