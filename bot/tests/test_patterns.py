"""
اختبارات الأنماط الانعكاسية.

القاعدة الحاكمة: **الشكل وحده لا يكفي** — لا اعتماد إلا بالتفعيل.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.fvg import FVG, find_fvgs
from bot.primitives.patterns import (
    find_engulfing,
    activate,
    activated,
    entry_plan,
    find_all,
    find_doubles,
    find_head_shoulders,
    find_triples,
)
from bot.primitives.swings import Swing, find_swings

T0 = datetime(2026, 8, 27, 15, 0)


def sw(i, price, kind):
    return Swing(i, T0 + timedelta(minutes=5 * i), price, kind)


def mk(*rows) -> Series:
    return Series(
        "M5",
        [Candle(T0 + timedelta(minutes=5 * i), o, h, l, c) for i, (o, h, l, c) in enumerate(rows)],
    )


class TestDoubles(unittest.TestCase):
    def test_double_bottom(self):
        s = [sw(1, 100, "low"), sw(3, 120, "high"), sw(5, 101, "low")]
        p = find_doubles(s, tolerance=2)[0]
        self.assertEqual(p.kind, "double_bottom")
        self.assertEqual(p.direction, "bullish")
        self.assertEqual(p.neckline, 120)
        self.assertEqual(p.extreme, 100)

    def test_double_top(self):
        s = [sw(1, 120, "high"), sw(3, 100, "low"), sw(5, 119, "high")]
        p = find_doubles(s, tolerance=2)[0]
        self.assertEqual(p.kind, "double_top")
        self.assertEqual(p.direction, "bearish")
        self.assertEqual(p.neckline, 100)
        self.assertEqual(p.extreme, 120)

    def test_unequal_lows_rejected(self):
        s = [sw(1, 100, "low"), sw(3, 120, "high"), sw(5, 112, "low")]
        self.assertEqual(find_doubles(s, tolerance=2), [])

    def test_tolerance_controls_acceptance(self):
        s = [sw(1, 100, "low"), sw(3, 120, "high"), sw(5, 105, "low")]
        self.assertEqual(find_doubles(s, tolerance=2), [])
        self.assertEqual(len(find_doubles(s, tolerance=6)), 1)

    def test_no_intervening_pivot_rejected(self):
        s = [sw(1, 100, "low"), sw(5, 101, "low")]
        self.assertEqual(find_doubles(s, tolerance=2), [])

    def test_negative_tolerance_rejected(self):
        with self.assertRaises(ValueError):
            find_doubles([], tolerance=-1)


class TestTriples(unittest.TestCase):
    def test_triple_bottom(self):
        s = [
            sw(1, 100, "low"), sw(2, 118, "high"),
            sw(3, 101, "low"), sw(4, 120, "high"),
            sw(5, 99, "low"),
        ]
        p = find_triples(s, tolerance=3)[0]
        self.assertEqual(p.kind, "triple_bottom")
        self.assertEqual(len(p.pivots), 3)
        self.assertEqual(p.neckline, 120)      # الأصعب من النقطتين الفاصلتين

    def test_third_out_of_tolerance_rejected(self):
        s = [
            sw(1, 100, "low"), sw(2, 118, "high"),
            sw(3, 101, "low"), sw(4, 120, "high"),
            sw(5, 90, "low"),
        ]
        self.assertEqual(find_triples(s, tolerance=3), [])


class TestHeadShoulders(unittest.TestCase):
    def test_inverse_head_shoulders(self):
        s = [
            sw(1, 100, "low"), sw(2, 115, "high"),
            sw(3, 90, "low"),                      # الرأس أعمق
            sw(4, 116, "high"), sw(5, 101, "low"),
        ]
        p = find_head_shoulders(s, shoulder_tolerance=3)[0]
        self.assertEqual(p.kind, "inverse_head_shoulders")
        self.assertEqual(p.direction, "bullish")
        self.assertEqual(p.neckline, 116)
        self.assertEqual(p.extreme, 90)

    def test_head_shoulders_bearish(self):
        s = [
            sw(1, 120, "high"), sw(2, 105, "low"),
            sw(3, 130, "high"),
            sw(4, 104, "low"), sw(5, 121, "high"),
        ]
        p = find_head_shoulders(s, shoulder_tolerance=3)[0]
        self.assertEqual(p.kind, "head_shoulders")
        self.assertEqual(p.neckline, 104)

    def test_head_not_deeper_rejected(self):
        s = [
            sw(1, 100, "low"), sw(2, 115, "high"),
            sw(3, 105, "low"),                     # ليس أعمق
            sw(4, 116, "high"), sw(5, 101, "low"),
        ]
        self.assertEqual(find_head_shoulders(s, shoulder_tolerance=3), [])

    def test_uneven_shoulders_rejected(self):
        s = [
            sw(1, 100, "low"), sw(2, 115, "high"),
            sw(3, 90, "low"),
            sw(4, 116, "high"), sw(5, 110, "low"),
        ]
        self.assertEqual(find_head_shoulders(s, shoulder_tolerance=3), [])


# قاعدة مشتركة: دبل بتم بقاعين عند 100 و101 وقمة فاصلة 110
#   فهارس السوينغ: 1 (قاع 100) · 3 (قمة 110) · 5 (قاع 101)
BASE = (
    (105, 107, 104, 106),
    (106, 107, 100, 102),   # 1 — قاع 100
    (102, 108, 101, 107),
    (107, 110, 106, 109),   # 3 — قمة 110 (خط العنق)
    (109, 109, 103, 104),
    (104, 106, 101, 105),   # 5 — قاع 101
    (105, 108, 104, 107),
)


def series_with(*tail) -> Series:
    return mk(*(BASE + tail))


class TestActivation(unittest.TestCase):
    """«الشكل وحده لا يكفي» — لا اعتماد إلا بكسر خط العنق."""

    def _pattern(self, s: Series):
        return find_doubles(find_swings(s), tolerance=2)[0]

    def test_base_series_yields_the_double_bottom(self):
        s = series_with()
        p = self._pattern(s)
        self.assertEqual(p.kind, "double_bottom")
        self.assertEqual((p.extreme, p.neckline), (100, 110))

    def test_shape_alone_is_only_forming(self):
        s = series_with((107, 109, 106, 108), (108, 109, 106, 107))
        p = activate(s, [self._pattern(s)], find_fvgs(s), require_fvg=False)[0]
        self.assertEqual(p.state, "forming")
        self.assertFalse(p.activated)

    def test_body_break_with_fvg_activates(self):
        s = series_with(
            (107, 112, 106, 111),      # 7 — كسر 110 بالجسم
            (111, 118, 109, 117),      # 8 — فراغ: low 109 > high[6] 108
        )
        p = activate(s, [self._pattern(s)], find_fvgs(s))[0]
        self.assertEqual(p.state, "activated")
        self.assertEqual(p.break_index, 7)
        self.assertIsNotNone(p.fvg)

    def test_wick_break_does_not_activate(self):
        """الكسر بالجسم لا بالذيل — الدرس 10."""
        s = series_with(
            (105, 115, 104, 108),      # الذيل تجاوز 110 والجسم لم يتجاوز
            (108, 112, 107, 109),
        )
        p = activate(s, [self._pattern(s)], find_fvgs(s), require_fvg=False)[0]
        self.assertEqual(p.state, "forming")

    def test_break_without_fvg_is_not_enough(self):
        """«ما كمّل الشروط» — الكسر بلا فراغ لا يفعّل."""
        s = series_with(
            (107, 112, 106, 111),
            (111, 114, 107, 112),      # لا فراغ: low 107 < high[6] 108
        )
        gaps = find_fvgs(s)
        self.assertEqual([g for g in gaps if g.direction == "bullish" and g.index >= 7], [])
        strict = activate(s, [self._pattern(s)], gaps, require_fvg=True)[0]
        loose = activate(s, [self._pattern(s)], gaps, require_fvg=False)[0]
        self.assertEqual(strict.state, "forming")
        self.assertEqual(loose.state, "activated")

    def test_breaking_the_extreme_invalidates(self):
        s = series_with(
            (105, 106, 97, 98),        # الجسم أغلق تحت 100
            (98, 112, 97, 111),
        )
        p = activate(s, [self._pattern(s)], find_fvgs(s), require_fvg=False)[0]
        self.assertEqual(p.state, "invalidated")

    def test_activated_filter(self):
        s = series_with((107, 112, 106, 111), (111, 118, 109, 117))
        self.assertEqual(len(activated(activate(s, [self._pattern(s)], find_fvgs(s)))), 1)


class TestEntryPlan(unittest.TestCase):
    def _activated(self):
        s = series_with((107, 112, 106, 111), (111, 118, 109, 117))
        p = find_doubles(find_swings(s), tolerance=2)[0]
        return activate(s, [p], find_fvgs(s))[0]

    def test_entry_is_the_break_fvg_not_the_break(self):
        plan = entry_plan(self._activated(), spread=0.5)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.entry, plan.pattern.fvg.top)
        self.assertIn("إعادة اختباره", plan.reason)

    def test_stop_is_pattern_extreme_minus_spread(self):
        plan = entry_plan(self._activated(), spread=0.5)
        self.assertAlmostEqual(plan.stop, 100 - 0.5)

    def test_targets_follow_rr(self):
        plan = entry_plan(self._activated(), spread=0.5)
        self.assertAlmostEqual(plan.target_for(2), plan.entry + plan.risk * 2)
        self.assertAlmostEqual(plan.target_for(3), plan.entry + plan.risk * 3)

    def test_no_plan_before_activation(self):
        s = series_with()
        p = find_doubles(find_swings(s), tolerance=2)[0]
        self.assertIsNone(entry_plan(p, spread=0.5))

    def test_negative_spread_rejected(self):
        with self.assertRaises(ValueError):
            self._activated().stop_for(-1)


class TestFindAll(unittest.TestCase):
    def test_collects_every_kind(self):
        s = [
            sw(1, 100, "low"), sw(2, 118, "high"),
            sw(3, 101, "low"), sw(4, 120, "high"),
            sw(5, 99, "low"),
        ]
        kinds = {p.kind for p in find_all(s, tolerance=3)}
        self.assertIn("double_bottom", kinds)
        self.assertIn("triple_bottom", kinds)


class TestEngulfing(unittest.TestCase):
    """
    ⭐ البثّ المباشر ٢ — أضافها بلفظه إلى النماذج الانعكاسية:

        «بس طلع من منطقته — إعادة اختبار، **شمعة ابتلاعية** —
         في عندك دخول، استهداف»
    """

    def _s(self, *rows):
        return Series("M15", [
            Candle(datetime(2026, 8, 30, 9, 0) + timedelta(minutes=15 * i), o, h, l, c)
            for i, (o, h, l, c) in enumerate(rows)
        ])

    def test_bullish_engulfing(self):
        s = self._s((105, 106, 100, 101), (100, 108, 99, 107))
        e = find_engulfing(s)
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0].direction, "bullish")

    def test_bearish_engulfing(self):
        s = self._s((100, 106, 99, 105), (106, 107, 97, 98))
        self.assertEqual(find_engulfing(s)[0].direction, "bearish")

    def test_body_not_range_decides(self):
        """
        ⭐ مقتضى تفريقه بين السيولتين: الجسم أوامر حقيقية، والذيل
        سيولة ستوبات. فالابتلاع الذي يعني شيئًا هو ابتلاع الأجسام.

        هنا المدى يبتلع والجسم لا — فلا ابتلاع.
        """
        s = self._s((105, 106, 100, 101), (102, 120, 90, 104))
        self.assertEqual(find_engulfing(s), [])

    def test_same_colour_is_not_engulfing(self):
        s = self._s((100, 106, 99, 105), (99, 110, 98, 109))
        self.assertEqual(find_engulfing(s), [])

    def test_doji_neither_engulfs_nor_is_engulfed(self):
        """نسبة بلا مقام — الشمعة بلا جسم تُتخطّى."""
        s = self._s((100, 106, 99, 100), (99, 110, 98, 109))
        self.assertEqual(find_engulfing(s), [])

    def test_min_ratio_filters_marginal_engulfings(self):
        """🔴 EN1 — لم يذكر نسبة؛ المقبض مكشوف."""
        s = self._s((105, 106, 100, 101), (101, 107, 100, 106))
        self.assertTrue(find_engulfing(s, min_ratio=1.0))
        self.assertEqual(find_engulfing(s, min_ratio=2.0), [])

    def test_direction_filter(self):
        s = self._s((105, 106, 100, 101), (100, 108, 99, 107))
        self.assertTrue(find_engulfing(s, direction="bullish"))
        self.assertEqual(find_engulfing(s, direction="bearish"), [])

    def test_stop_reference_is_the_engulfed_body_edge(self):
        s = self._s((105, 106, 100, 101), (100, 108, 99, 107))
        self.assertAlmostEqual(find_engulfing(s)[0].stop_reference, 101.0)

    def test_ratio_below_one_rejected(self):
        with self.assertRaises(ValueError):
            find_engulfing(self._s((100, 101, 99, 100)), min_ratio=0.5)

    def test_render(self):
        s = self._s((105, 106, 100, 101), (100, 108, 99, 107))
        self.assertIn("ابتلاعية", find_engulfing(s)[0].render())


if __name__ == "__main__":
    unittest.main(verbosity=2)
