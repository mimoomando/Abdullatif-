"""
اختبارات الأوردر بلوك — كل اختبار يتحقق من شرط منصوص عليه.

الثلاثية (د10 · م2/د3): كسح سيولة + كسر بالجسم + فراغ سعري.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.fvg import find_fvgs
from bot.primitives.liquidity import find_sweeps
from bot.primitives.order_block import (
    find_order_blocks,
    fresh_blocks,
    qualifies_for_direct_touch,
    stop_buffer,
    update_states,
)
from bot.primitives.swings import find_swings

T0 = datetime(2026, 8, 27, 10, 0)


def mk(*rows) -> Series:
    return Series(
        "M5",
        [
            Candle(T0 + timedelta(minutes=5 * i), o, h, l, c)
            for i, (o, h, l, c) in enumerate(rows)
        ],
    )


# سيناريو صاعد صالح:
#   قمة حاكمة 25 · قاع 10 · كسح إلى 8 مع استعادة · اندفاع يكسر 25 بالجسم · فراغ
VALID = (
    (19, 20, 18, 19),
    (19, 25, 19, 24),    # 1 — قمة حاكمة 25
    (22, 22, 10, 12),    # 2 — قاع 10
    (12, 15, 12, 13),
    (11, 14, 8, 12),     # 4 — كسح إلى 8 ثم إغلاق 12 فوق 10 · شمعة رفض
    (12, 16, 11, 15),
    (15, 30, 15, 29),    # 6 — كسر 25 بالجسم (29)
    (29, 32, 18, 31),    # 7 — فراغ
)


def build(*extra):
    s = mk(*(VALID + extra))
    sw = find_swings(s)
    return s, find_order_blocks(s, sw, find_sweeps(s, sw, max_bars_to_reclaim=3), find_fvgs(s))


class TestThreePartStack(unittest.TestCase):
    def test_valid_bullish_order_block(self):
        s, obs = build()
        self.assertEqual(len(obs), 1)
        ob = obs[0]
        self.assertEqual(ob.direction, "bullish")
        self.assertEqual(ob.index, 4)
        self.assertEqual((ob.bottom, ob.top), (8, 14))     # المدى الكامل — م2/د4
        self.assertEqual(ob.governing_level, 25)
        self.assertEqual(ob.sweep.level, 10)
        self.assertTrue(ob.is_rejection_block)

    def test_zone_is_full_range_not_body(self):
        """م2/د4: «marks the defining OB candle by its complete high-to-low range»."""
        _, obs = build()
        c = mk(*VALID)[obs[0].index]
        self.assertEqual(obs[0].bottom, c.low)
        self.assertEqual(obs[0].top, c.high)
        self.assertNotEqual(obs[0].bottom, c.body_bottom)

    def test_no_sweep_no_order_block(self):
        """بلا كسح تسقط الثلاثية."""
        rows = list(VALID)
        rows[4] = (11, 14, 11, 12)          # لا يخترق القاع 10
        s = mk(*rows)
        sw = find_swings(s)
        obs = find_order_blocks(s, sw, find_sweeps(s, sw, max_bars_to_reclaim=3), find_fvgs(s))
        self.assertEqual(obs, [])

    def test_wick_break_is_not_enough(self):
        """د10: «The structural break must be by candle body, not wick»."""
        rows = list(VALID)
        rows[6] = (15, 30, 15, 20)          # الذيل تجاوز 25 والجسم لم يتجاوز
        rows[7] = (20, 24, 18, 23)
        s = mk(*rows)
        sw = find_swings(s)
        obs = find_order_blocks(s, sw, find_sweeps(s, sw, max_bars_to_reclaim=3), find_fvgs(s))
        self.assertEqual(obs, [])

    def test_no_fvg_no_order_block(self):
        """الشرط الثالث: «ومشكّل فراغات سعرية»."""
        rows = list(VALID)
        rows[6] = (15, 26, 13, 26)          # يكسر بالجسم لكن بلا فراغ
        rows[7] = (26, 27, 15, 26)
        s = mk(*rows)
        sw = find_swings(s)
        gaps = find_fvgs(s)
        # لا فجوة **صاعدة** في نافذة الاندفاع — الفجوة الهابطة الموجودة سابقة له
        self.assertEqual([g for g in gaps if g.direction == "bullish" and g.index >= 4], [])
        obs = find_order_blocks(s, sw, find_sweeps(s, sw, max_bars_to_reclaim=3), gaps)
        self.assertEqual(obs, [])

    def test_break_must_be_of_governing_point(self):
        """كسر نقطة أدنى من القمة الحاكمة لا يكفي."""
        rows = list(VALID)
        rows[6] = (15, 24, 15, 23)          # 23 < 25
        rows[7] = (23, 24, 18, 23)
        s = mk(*rows)
        sw = find_swings(s)
        obs = find_order_blocks(s, sw, find_sweeps(s, sw, max_bars_to_reclaim=3), find_fvgs(s))
        self.assertEqual(obs, [])


class TestStop(unittest.TestCase):
    """م2/د3: «أدنى قاع الأوردر بلوك بقليل مشان السبريد»."""

    def test_stop_below_low_by_buffer(self):
        _, obs = build()
        self.assertAlmostEqual(obs[0].stop_for(0.35), 8 - 0.35)

    def test_zero_buffer_is_the_low_itself(self):
        _, obs = build()
        self.assertEqual(obs[0].stop_for(0.0), 8)

    def test_negative_buffer_rejected(self):
        _, obs = build()
        with self.assertRaises(ValueError):
            obs[0].stop_for(-1)


class TestStopBuffer(unittest.TestCase):
    """
    ⭐ T2 — «أدنى القاع بقليل» = كم؟

    المصدر أعطى **السبب**: «مشان السبريد» (م2/د3).
    والمستخدم أعطى **المقدار**: «درجتان» (2026-08-27).
    فالمقدار يحكم، والسبريد أرضية دنيا.
    """

    def test_the_settled_answer_is_two_dollars(self):
        """
        ⭐ «درجتان» + «الدولار كاملًا» ⇒ 2.00 دولار.

        مثال أكّده المستخدم بنفسه: قاع 4365.00 ⇒ الوقف 4363.00.
        """
        self.assertAlmostEqual(stop_buffer(0.30, degrees=2, degree_value=1.0), 2.00)
        self.assertAlmostEqual(4365.00 - stop_buffer(0.30, 2, 1.0), 4363.00)

    def test_degrees_win_when_they_exceed_the_spread(self):
        self.assertAlmostEqual(stop_buffer(0.30, degrees=2, degree_value=1.0), 2.0)

    def test_spread_is_the_floor_when_degrees_are_smaller(self):
        """هامش أضيق من السبريد يُضرب بلا حركة سعر — وذلك ينقض سببه."""
        self.assertAlmostEqual(stop_buffer(0.50, degrees=2, degree_value=0.01), 0.50)

    def test_unknown_degree_value_falls_back_to_spread(self):
        """⚠️ الارتداد صريح: ما دامت الوحدة معلّقة لا يُخترع رقم."""
        self.assertAlmostEqual(stop_buffer(0.40, degrees=2, degree_value=None), 0.40)

    def test_no_degrees_at_all_is_the_original_source_rule(self):
        self.assertAlmostEqual(stop_buffer(0.40), 0.40)

    def test_the_unit_changes_the_answer_a_hundredfold(self):
        """⭐ لماذا لا تُخمَّن الوحدة: الفارق ليس تفصيلًا."""
        cent = stop_buffer(0.0, degrees=2, degree_value=0.01)
        dollar = stop_buffer(0.0, degrees=2, degree_value=1.0)
        self.assertAlmostEqual(dollar / cent, 100.0)

    def test_negative_inputs_rejected(self):
        with self.assertRaises(ValueError):
            stop_buffer(-1)
        with self.assertRaises(ValueError):
            stop_buffer(0.3, degrees=-2, degree_value=1.0)
        with self.assertRaises(ValueError):
            stop_buffer(0.3, degrees=2, degree_value=0.0)


class TestStates(unittest.TestCase):
    def test_fresh_when_never_revisited(self):
        s, obs = build((31, 40, 30, 39), (39, 45, 38, 44))
        self.assertEqual(update_states(s, obs)[0].state, "fresh")

    def test_mitigated_on_return(self):
        s, obs = build((31, 33, 13, 20))          # عاد ولامس المنطقة 8–14
        self.assertEqual(update_states(s, obs)[0].state, "mitigated")

    def test_failed_when_body_closes_through(self):
        s, obs = build((31, 33, 12, 20), (20, 21, 5, 6))   # الجسم أغلق تحت 8
        self.assertEqual(update_states(s, obs)[0].state, "failed")

    def test_breaker_after_failure_and_return(self):
        s, obs = build((31, 33, 12, 20), (20, 21, 5, 6), (6, 13, 6, 12))
        self.assertEqual(update_states(s, obs)[0].state, "breaker")

    def test_fresh_filter(self):
        s, obs = build((31, 40, 30, 39))
        self.assertEqual(len(fresh_blocks(update_states(s, obs))), 1)


class TestDirectTouch(unittest.TestCase):
    """م2/د3 — «نقطة الدخول بتكون عنّا عند مجرد اللمس»."""

    def setUp(self):
        s, obs = build((31, 40, 30, 39))
        self.ob = update_states(s, obs)[0]

    def _fvg(self, bottom, top, direction="bullish"):
        from bot.primitives.fvg import FVG
        return FVG(0, T0, direction, top, bottom)

    def test_eligible_when_supported_by_higher_frame_fvg(self):
        r = qualifies_for_direct_touch(self.ob, [self._fvg(7, 15)])
        self.assertTrue(r.eligible)
        self.assertTrue(any("مسنودة" in x for x in r.reasons))

    def test_not_eligible_without_higher_frame_support(self):
        r = qualifies_for_direct_touch(self.ob, [self._fvg(100, 110)])
        self.assertFalse(r.eligible)
        self.assertTrue(any("القاعدة العامة" in x for x in r.reasons))

    def test_opposite_direction_fvg_does_not_support(self):
        r = qualifies_for_direct_touch(self.ob, [self._fvg(7, 15, "bearish")])
        self.assertFalse(r.eligible)

    def test_containment_stricter_than_overlap(self):
        """D1 غير محسوم — الفارق مكشوف كمعامل."""
        partial = [self._fvg(12, 20)]                       # يتقاطع ولا يحتوي
        self.assertTrue(qualifies_for_direct_touch(self.ob, partial).eligible)
        self.assertFalse(
            qualifies_for_direct_touch(self.ob, partial, require_containment=True).eligible
        )

    def test_expensive_entry_rejected(self):
        """C3 — بوابة الـ50%."""
        cheap = qualifies_for_direct_touch(self.ob, [self._fvg(7, 15)], impulse_midpoint=20)
        self.assertTrue(cheap.eligible)
        dear = qualifies_for_direct_touch(self.ob, [self._fvg(7, 15)], impulse_midpoint=10)
        self.assertFalse(dear.eligible)
        self.assertTrue(any("غالٍ" in x for x in dear.reasons))

    def test_failed_block_never_eligible(self):
        s, obs = build((31, 33, 12, 20), (20, 21, 5, 6))
        failed = update_states(s, obs)[0]
        r = qualifies_for_direct_touch(failed, [self._fvg(7, 15)])
        self.assertFalse(r.eligible)
        self.assertTrue(any("فاشلة" in x for x in r.reasons))

    def test_reasons_always_cite_the_stack(self):
        r = qualifies_for_direct_touch(self.ob, [self._fvg(7, 15)])
        self.assertTrue(any("الثلاثية مستوفاة" in x for x in r.reasons))


if __name__ == "__main__":
    unittest.main(verbosity=2)
