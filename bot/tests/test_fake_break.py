"""
اختبارات الكسر الوهمي مقابل الحقيقي — وايكوف/د3.

كل اختبار هنا يتحقق من جملة منصوصة، لا من اجتهاد.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.fake_break import (
    BreakAttempt,
    crossing_rule,
    find_break_attempts,
    plan_from_fake_break,
)

T0 = datetime(2026, 8, 27, 9, 0)
LEVEL = 100.0


def mk(*rows) -> Series:
    return Series(
        "H1",
        [Candle(T0 + timedelta(hours=i), o, h, l, c) for i, (o, h, l, c) in enumerate(rows)],
    )


class TestNoBreakWithoutClose(unittest.TestCase):
    """«هل أغلقت شموع أعلى المنطقة؟ لا» ⇒ لم يحدث كسر أصلًا."""

    def test_wick_above_the_level_is_not_a_break(self):
        s = mk(
            (98, 99, 97, 98),
            (98, 104, 97, 99),      # الذيل فوق 100 والإغلاق تحته
            (99, 100, 97, 98),
        )
        self.assertEqual(find_break_attempts(s, LEVEL, "up"), [])

    def test_close_exactly_at_the_level_is_not_beyond_it(self):
        s = mk((98, 101, 97, 100), (100, 101, 99, 100))
        self.assertEqual(find_break_attempts(s, LEVEL, "up"), [])

    def test_close_above_is_a_break(self):
        s = mk((98, 103, 97, 102), (102, 103, 101, 102))
        self.assertEqual(len(find_break_attempts(s, LEVEL, "up")), 1)


class TestFakeBreak(unittest.TestCase):
    """
    ⭐ «أما لأنه كسر وهمي — هي تصعّدت وأغلقت فوق».

    أي: أُعيد اختبار المستوى فأُغلق **عائدًا** إلى الجهة الأصلية.
    """

    ROWS = (
        (96, 98, 95, 97),
        (97, 103, 96, 102),      # 1 — كسر صعودًا بالإغلاق
        (102, 103, 99, 101),     # 2 — لمس المستوى وأغلق فوقه
        (101, 102, 96, 97),      # 3 — أغلق عائدًا تحت 100 ⇒ وهمي
        (97, 98, 94, 95),
    )

    def test_close_back_inside_makes_it_fake(self):
        a = find_break_attempts(mk(*self.ROWS), LEVEL, "up")
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0].state, "fake")
        self.assertEqual(a[0].index, 1)

    def test_the_closing_candle_is_recorded(self):
        a = find_break_attempts(mk(*self.ROWS), LEVEL, "up")[0]
        self.assertEqual(a.resolved_at, 3)
        self.assertIn("أغلق عائدًا", a.detail)

    def test_a_close_back_beats_an_earlier_looking_confirmation(self):
        """
        ⭐ الإغلاق العائد ينقض الكسر مهما بدا قويًا.

        الشمعة 2 لمست المستوى وأغلقت فوقه — ولو حُسم عندها لصار «حقيقيًا».
        لكن الحسم ليس أول إشارة، بل ما استقرّ عليه الإغلاق.
        """
        a = find_break_attempts(mk(*self.ROWS), LEVEL, "up", retest_window=1)[0]
        self.assertEqual(a.state, "real")       # نافذة ضيّقة ⇒ حُسم مبكرًا
        b = find_break_attempts(mk(*self.ROWS), LEVEL, "up", retest_window=5)[0]
        self.assertEqual(b.state, "fake")       # نافذة كافية ⇒ الحقيقة ظهرت


class TestRealBreak(unittest.TestCase):
    """«نزل، أغلق، تست، أغلق ⇒ صار توجّهه هابط»."""

    ROWS = (
        (104, 105, 103, 104),
        (104, 105, 96, 97),      # 1 — كسر هبوطًا بالإغلاق
        (97, 100, 96, 98),       # 2 — عاد للمستوى وأغلق تحته ⇒ حقيقي
        (98, 99, 93, 94),
    )

    def test_retest_that_holds_makes_it_real(self):
        a = find_break_attempts(mk(*self.ROWS), LEVEL, "down")
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0].state, "real")
        self.assertEqual(a[0].resolved_at, 2)

    def test_detail_quotes_the_rule(self):
        a = find_break_attempts(mk(*self.ROWS), LEVEL, "down")[0]
        self.assertIn("عاد للمستوى وأغلق خارجه", a.detail)


class TestPending(unittest.TestCase):
    """ما لم يُحسم لا يُصنَّف — ولا يُخمَّن."""

    def test_no_retest_within_the_window_stays_pending(self):
        s = mk(
            (96, 98, 95, 97),
            (97, 106, 96, 105),     # كسر
            (105, 107, 104, 106),   # ابتعد ولم يعد
            (106, 108, 105, 107),
        )
        a = find_break_attempts(s, LEVEL, "up", retest_window=2)[0]
        self.assertEqual(a.state, "pending")
        self.assertIsNone(a.resolved_at)
        self.assertIn("لم يُعِد اختبار", a.detail)

    def test_touched_but_unresolved_says_so(self):
        s = mk(
            (96, 98, 95, 97),
            (97, 103, 96, 102),
            (102, 103, 99, 101),    # لمس وأغلق فوق — لكن النافذة تنتهي
        )
        a = find_break_attempts(s, LEVEL, "up", retest_window=1)[0]
        self.assertEqual(a.state, "real")


class TestSpring(unittest.TestCase):
    """«منطقة سبرينغ… اللي بيحدث فيها الكسر الوهمي» — الهبوطي وحده."""

    def test_downward_fake_break_is_a_spring(self):
        s = mk(
            (104, 105, 103, 104),
            (104, 105, 96, 97),      # كسر هبوطًا
            (97, 104, 96, 103),      # أغلق عائدًا فوق ⇒ وهمي
            (103, 106, 102, 105),
        )
        a = find_break_attempts(s, LEVEL, "down")[0]
        self.assertEqual(a.state, "fake")
        self.assertTrue(a.is_spring)
        self.assertIn("سبرينغ", a.render())

    def test_upward_fake_break_is_not_named_spring(self):
        """لم يُسمِّ نظيره الصاعد في هذا الدرس — فلا يُسمَّى هنا."""
        s = mk(
            (96, 98, 95, 97),
            (97, 103, 96, 102),
            (102, 103, 96, 97),
        )
        a = find_break_attempts(s, LEVEL, "up")[0]
        self.assertEqual(a.state, "fake")
        self.assertFalse(a.is_spring)


class TestSequencing(unittest.TestCase):
    def test_a_new_attempt_only_starts_after_the_previous_resolves(self):
        """الكسر وإعادة اختباره حدث واحد لا حدثان."""
        s = mk(
            (96, 98, 95, 97),
            (97, 103, 96, 102),      # 1 — كسر
            (102, 103, 96, 97),      # 2 — أغلق عائدًا ⇒ وهمي، حُسم هنا
            (97, 104, 96, 103),      # 3 — كسر جديد
            (103, 104, 96, 97),      # 4 — وهمي ثانٍ
        )
        a = find_break_attempts(s, LEVEL, "up")
        self.assertEqual([x.index for x in a], [1, 3])
        self.assertTrue(all(x.state == "fake" for x in a))

    def test_attempts_are_in_order(self):
        s = mk(*[(97, 103, 96, 102), (102, 103, 96, 97)] * 3)
        a = find_break_attempts(s, LEVEL, "up")
        self.assertEqual([x.index for x in a], sorted(x.index for x in a))


class TestGuards(unittest.TestCase):
    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            find_break_attempts(mk((97, 103, 96, 102)), LEVEL, "up", retest_window=0)

    def test_negative_tolerance_rejected(self):
        with self.assertRaises(ValueError):
            find_break_attempts(mk((97, 103, 96, 102)), LEVEL, "up", level_tolerance=-1)

    def test_bad_direction_rejected(self):
        with self.assertRaises(ValueError):
            find_break_attempts(mk((97, 103, 96, 102)), LEVEL, "sideways")

    def test_tolerance_suppresses_a_marginal_break(self):
        """FB2 — «أغلقت عند المستوى»: السماحية مقبض مكشوف لا رقم منه."""
        s = mk((99, 101, 98, 100.4), (100, 101, 99, 100.2))
        self.assertEqual(find_break_attempts(s, LEVEL, "up", level_tolerance=1.0), [])
        self.assertTrue(find_break_attempts(s, LEVEL, "up", level_tolerance=0.0))


class TestNeverDecides(unittest.TestCase):
    """
    ⭐ «أنا ما بدي أعطيك إياها كصفقة، أنا بدي أعطيك إياها كسلوك سعر».

    التأكيد الرابع — والوحدة يجب ألا تحمل دخولًا ولا وقفًا ولا هدفًا.
    """

    def test_attempt_carries_no_trade_fields(self):
        a = BreakAttempt(0, T0, LEVEL, "up", 102.0, "fake")
        for field in ("entry", "stop", "target", "targets", "direction_to_trade"):
            self.assertFalse(hasattr(a, field), field)


class TestCrossingRule(unittest.TestCase):
    """«ما تجاوزها السعر بده يرتد · تجاوز السعر بده يرتكز عليه ويكفّي»."""

    def test_failed_cross_bounces(self):
        self.assertIn("ارتداد", crossing_rule(False))

    def test_successful_cross_becomes_support(self):
        self.assertIn("ارتكازًا", crossing_rule(True))


class TestPlanFromFakeBreak(unittest.TestCase):
    """
    ⭐⭐ أول صفقة كاملة في سلسلة وايكوف — د4.

        «مجرد الخروج والإغلاق من الكسر الوهمي كان في صفقة سيل،
         الستوب عند أعلى قمة بالكسر الوهمي،
         والهدف عند القيعان — هي أول قاع تستهدفه»
    """

    ROWS = (
        (96, 98, 95, 97),
        (97, 108, 96, 102),      # 1 — كسر صعودًا · القمة 108
        (102, 110, 100, 104),    # 2 — قمة أعلى 110 داخل الكسر الوهمي
        (104, 105, 96, 97),      # 3 — إغلاق عائد ⇒ وهمي · الدخول 97
    )
    LOWS = (92.0, 88.0, 80.0)

    def _plan(self, **kw):
        s = mk(*self.ROWS)
        a = find_break_attempts(s, LEVEL, "up")[0]
        return plan_from_fake_break(s, a, self.LOWS, **kw)

    def test_direction_is_opposite_the_break(self):
        self.assertEqual(self._plan().direction, "sell")

    def test_entry_is_the_close_of_the_returning_candle(self):
        p = self._plan()
        self.assertAlmostEqual(p.entry, 97.0)
        self.assertEqual(p.entry_index, 3)

    def test_stop_is_the_extreme_of_the_fake_break_not_the_level(self):
        """⭐ «الستوب عند أعلى قمة بالكسر الوهمي» — لا عند المستوى."""
        p = self._plan()
        self.assertAlmostEqual(p.stop, 110.0)
        self.assertNotAlmostEqual(p.stop, LEVEL)

    def test_targets_are_prior_lows_nearest_first(self):
        """«هي أول قاع تستهدفه» ثم الأبعد."""
        self.assertEqual(self._plan().targets, [92.0, 88.0, 80.0])

    def test_targets_beyond_entry_only(self):
        s = mk(*self.ROWS)
        a = find_break_attempts(s, LEVEL, "up")[0]
        p = plan_from_fake_break(s, a, (92.0, 120.0))
        self.assertEqual(p.targets, [92.0])

    def test_max_targets_is_respected(self):
        self.assertEqual(len(self._plan(max_targets=2).targets), 2)

    def test_risk_and_rr(self):
        p = self._plan()
        self.assertAlmostEqual(p.risk, 13.0)          # 110 − 97
        self.assertAlmostEqual(p.rr_of(84.0), 1.0)

    def test_no_plan_without_a_target(self):
        """لا صفقة بلا هدف."""
        s = mk(*self.ROWS)
        a = find_break_attempts(s, LEVEL, "up")[0]
        self.assertIsNone(plan_from_fake_break(s, a, ()))

    def test_no_plan_for_a_real_break(self):
        rows = (
            (104, 105, 103, 104),
            (104, 105, 96, 97),
            (97, 100, 96, 98),       # حقيقي
        )
        s = mk(*rows)
        a = find_break_attempts(s, LEVEL, "down")[0]
        self.assertEqual(a.state, "real")
        self.assertIsNone(plan_from_fake_break(s, a, (110.0,)))

    def test_buy_side_mirrors(self):
        rows = (
            (104, 105, 103, 104),
            (104, 105, 90, 96),      # كسر هبوطًا · القاع 90
            (96, 104, 88, 103),      # قاع أدنى 88 · إغلاق عائد ⇒ وهمي
        )
        s = mk(*rows)
        a = find_break_attempts(s, LEVEL, "down")[0]
        p = plan_from_fake_break(s, a, (108.0, 115.0))
        self.assertEqual(p.direction, "buy")
        self.assertAlmostEqual(p.stop, 88.0)
        self.assertEqual(p.targets, [108.0, 115.0])

    def test_render_states_the_rule(self):
        self.assertIn("كسر وهمي", self._plan().render())


class TestTargetBeforeKeyZone(unittest.TestCase):
    """
    ⭐ «ما بحط هدفي بعد منها، ممكن يرتد — أنا بحطه قبل منها» (د4 ≈16:13).
    """

    def _plan(self, **kw):
        s = mk(*TestPlanFromFakeBreak.ROWS)
        a = find_break_attempts(s, LEVEL, "up")[0]
        return plan_from_fake_break(s, a, (92.0, 80.0), **kw)

    def test_target_behind_a_key_zone_is_pulled_in_front_of_it(self):
        p = self._plan(key_zones=(85.0,))
        self.assertIn(85.0, p.targets)
        self.assertNotIn(80.0, p.targets)

    def test_buffer_places_it_short_of_the_zone(self):
        """🔴 V4 — لم يحدّد كم «قبلها»؛ الهامش مقبض مكشوف."""
        p = self._plan(key_zones=(85.0,), key_zone_buffer=1.5)
        self.assertIn(86.5, p.targets)

    def test_targets_clear_of_key_zones_are_untouched(self):
        p = self._plan(key_zones=(60.0,))
        self.assertEqual(p.targets, [92.0, 80.0])

    def test_duplicates_collapse(self):
        """هدفان خلف المنطقة نفسها يصيران واحدًا."""
        s = mk(*TestPlanFromFakeBreak.ROWS)
        a = find_break_attempts(s, LEVEL, "up")[0]
        p = plan_from_fake_break(s, a, (84.0, 80.0), key_zones=(85.0,))
        self.assertEqual(p.targets, [85.0])

    def test_no_plan_when_the_buffer_pushes_the_target_past_the_entry(self):
        """
        منطقة مفتاحية قرب الدخول + هامش يتجاوزه ⇒ لا مسافة للهدف أصلًا.
        فلا صفقة — والبديل (هدف خلف الدخول) عبث.
        """
        s = mk(*TestPlanFromFakeBreak.ROWS)
        a = find_break_attempts(s, LEVEL, "up")[0]
        self.assertIsNone(
            plan_from_fake_break(s, a, (92.0,), key_zones=(96.5,), key_zone_buffer=1.0)
        )

    def test_negative_buffer_rejected(self):
        with self.assertRaises(ValueError):
            self._plan(key_zones=(85.0,), key_zone_buffer=-1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
