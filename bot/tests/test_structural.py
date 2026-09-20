"""
اختبارات القمم والقيعان الحقيقيّة.

⚠️ **والوحدة مبنيّةٌ وغيرُ موصولة بقرار** — قِيست فلم يسندها القياس.
انظر `knowledge/analyses/2026-09-20-structural-swings.md`.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.structural import (
    structural,
    swept_at,
    swept_before,
)
from bot.primitives.swings import Swing, find_swings

T0 = datetime(2026, 9, 20, 10, 0)


def mk(*rows, tf="M15"):
    return Series(tf, [Candle(T0 + timedelta(minutes=15 * i), o, h, l, c)
                       for i, (o, h, l, c) in enumerate(rows)], symbol="XAUUSD")


def sw(i, price, kind):
    return Swing(i, T0 + timedelta(minutes=15 * i), price, kind)


class TestSweptAt(unittest.TestCase):
    """«سحبت سيولتها» — تجاوزٌ بالطرف لا بالإغلاق (C1)."""

    def test_a_high_taken_out_later_reports_the_bar(self):
        s = mk((10, 12, 9, 11), (11, 11, 10, 10), (10, 13, 10, 12))
        self.assertEqual(swept_at(s, sw(0, 12.0, "high")), 2)

    def test_a_high_never_exceeded_is_unswept(self):
        s = mk((10, 12, 9, 11), (11, 11, 10, 10), (10, 11.9, 10, 11))
        self.assertIsNone(swept_at(s, sw(0, 12.0, "high")))

    def test_touching_exactly_is_not_a_sweep(self):
        """المساواة ليست تجاوزًا — والحدّ هو ما ينزلق."""
        s = mk((10, 12, 9, 11), (11, 12, 10, 11))
        self.assertIsNone(swept_at(s, sw(0, 12.0, "high")))

    def test_a_low_taken_out_reports_the_bar(self):
        s = mk((10, 11, 8, 9), (9, 10, 9, 10), (10, 10, 7, 8))
        self.assertEqual(swept_at(s, sw(0, 8.0, "low")), 2)

    def test_bars_before_the_swing_are_never_counted(self):
        """السحب لاحقٌ دائمًا — وشمعةٌ سابقة لا تسحب شيئًا."""
        s = mk((10, 20, 9, 11), (11, 12, 10, 11))
        self.assertIsNone(swept_at(s, sw(1, 12.0, "high")))

    def test_upto_bounds_the_search(self):
        s = mk((10, 12, 9, 11), (11, 11, 10, 10), (10, 13, 10, 12))
        self.assertIsNone(swept_at(s, sw(0, 12.0, "high"), upto=2))


class TestSweptBefore(unittest.TestCase):
    """«ما في قمّة حقيقيّة إلّا ما تكون **ساحبة سيولة ما قبل**»."""

    def test_a_higher_high_than_the_previous_one_sweeps_it(self):
        swings = [sw(0, 10.0, "high"), sw(4, 12.0, "high")]
        self.assertTrue(swept_before(swings[1], swings))

    def test_a_lower_high_does_not(self):
        swings = [sw(0, 12.0, "high"), sw(4, 10.0, "high")]
        self.assertFalse(swept_before(swings[1], swings))

    def test_the_first_of_its_kind_sweeps_nothing(self):
        swings = [sw(0, 10.0, "high")]
        self.assertFalse(swept_before(swings[0], swings))

    def test_lows_mirror(self):
        swings = [sw(0, 10.0, "low"), sw(4, 8.0, "low")]
        self.assertTrue(swept_before(swings[1], swings))
        self.assertFalse(swept_before(swings[0], swings))

    def test_the_other_kind_is_ignored(self):
        """قمّةٌ لا تُقارَن بقاع — ولو كان أقرب."""
        swings = [sw(0, 10.0, "high"), sw(2, 5.0, "low"), sw(4, 12.0, "high")]
        self.assertTrue(swept_before(swings[2], swings))

    def test_it_compares_with_the_latest_of_its_kind_not_the_extreme(self):
        """
        ⚠️ «ساحبة ما **قبلها**» — فالمقارنة مع الأخيرة، لا مع أعلى ما مضى.

        وهنا 11 تتجاوز آخر قمّةٍ (9) ولا تتجاوز أعلى ما مضى (12).
        """
        swings = [sw(0, 12.0, "high"), sw(4, 9.0, "high"), sw(8, 11.0, "high")]
        self.assertTrue(swept_before(swings[2], swings))


class TestStructural(unittest.TestCase):
    def setUp(self):
        # قمّتان: الأولى تُسحَب لاحقًا، والثانية لا
        self.s = mk((10, 12, 9, 11), (11, 11, 10, 10),
                    (10, 14, 10, 13), (13, 13, 12, 12))
        self.swings = [sw(0, 12.0, "high"), sw(2, 14.0, "high")]

    def test_all_returns_everything_untouched(self):
        """`all` هو السلوك القائم — وخطُّ الأساس في أيّ قياس."""
        self.assertEqual(len(structural(self.s, self.swings, "all")), 2)

    def test_unswept_keeps_only_the_one_not_taken_out(self):
        got = structural(self.s, self.swings, "unswept")
        self.assertEqual([g.price for g in got], [14.0])

    def test_sweeper_keeps_only_the_one_that_took_the_earlier(self):
        got = structural(self.s, self.swings, "sweeper")
        self.assertEqual([g.price for g in got], [14.0])

    def test_both_requires_the_two_conditions_together(self):
        got = structural(self.s, self.swings, "both")
        self.assertEqual([g.price for g in got], [14.0])

    def test_the_readings_genuinely_differ(self):
        """
        ⭐ ولولا اختلافُهما لما كان للقياس معنًى.

        هنا 12 لم تُسحَب (لا شيء فوقها) لكنّها **لم تسحب** 14 قبلها.
        """
        s = mk((10, 14, 9, 11), (11, 11, 10, 10), (10, 12, 10, 11),
               (11, 11.5, 10, 11))
        swings = [sw(0, 14.0, "high"), sw(2, 12.0, "high")]
        self.assertEqual([g.price for g in structural(s, swings, "unswept")],
                         [14.0, 12.0])
        self.assertEqual(structural(s, swings, "sweeper"), [])

    def test_empty_in_empty_out(self):
        for rule in ("all", "unswept", "sweeper", "both"):
            with self.subTest(rule=rule):
                self.assertEqual(structural(mk((1, 2, 0, 1)), [], rule), [])

    def test_output_stays_ordered_by_index(self):
        s = mk(*[(10, 11, 9, 10)] * 12)
        swings = [sw(i, 10.0 + i, "high") for i in (8, 2, 5)]
        got = structural(s, swings, "sweeper")
        self.assertEqual([g.index for g in got], sorted(g.index for g in got))


class TestItIsNotWiredIntoAnyDecision(unittest.TestCase):
    """
    ⛔⛔ **والوحدة معزولةٌ عمدًا.**

    بُنيت ثم قِيست على أسبوع 09-14، فاستردّت 26 تصنيفًا من 50 —
    **وخسرت الدقّة**: على اليومين الوحيدَين القابلَين للمقارنة بأحكام
    المدرّب المسجَّلة قبل القياس، نزلت من **2/2** إلى **1/2**.

    ويومان عيّنةٌ لا تكفي لحكم — **ولا تكفي لتغيير الكود.** فتبقى
    مبنيّةً غير موصولة حتى يفصل أسبوعٌ أطول.
    """

    def test_no_decision_module_imports_it(self):
        """
        ⚠️ ويُفحَص **الاستيراد** لا مجرّد ذكر الاسم.

        كان الفحص يردّ أيّ ظهورٍ للكلمة، فسقط حين ذُكرت `structural.py`
        في **تعليقٍ** يشرح أنّ الهارمونيك نال حكمَها نفسه. وحارسٌ يردّ
        التوثيق يُغري بحذفه — فضُيِّق ليمنع ما يضرّ وحده.
        """
        import pathlib
        import re
        pattern = re.compile(r"^\s*(from\s+\S*structural|import\s+\S*structural"
                             r"|from\s+\S+\s+import\s+[^\n]*\bstructural\b)",
                             re.MULTILINE)
        for name in ("chain.py", "runner.py"):
            src = (pathlib.Path("bot") / name).read_text(encoding="utf-8")
            with self.subTest(module=name):
                self.assertIsNone(pattern.search(src),
                                  f"{name} صار يستورد وحدةً لم يسندها القياس")


if __name__ == "__main__":
    unittest.main(verbosity=2)
