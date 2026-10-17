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


def _rising(tf="M15"):
    """
    سلّمٌ صاعدٌ بقممٍ وقيعانٍ متناوبة — **وبعضُ قممه تُسحَب لاحقًا**،
    فيختلف `unswept` عن `all` حقًّا.
    """
    closes = [100, 103, 101, 106, 104, 109, 107, 112, 110, 115]
    return mk(*[(c, c + 1.0, c - 1.0, c) for c in closes], tf=tf)


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
        got = structural(self.s, self.swings, "unswept", upto=len(self.s))
        self.assertEqual([g.price for g in got], [14.0])

    def test_sweeper_keeps_only_the_one_that_took_the_earlier(self):
        got = structural(self.s, self.swings, "sweeper", upto=len(self.s))
        self.assertEqual([g.price for g in got], [14.0])

    def test_both_requires_the_two_conditions_together(self):
        got = structural(self.s, self.swings, "both", upto=len(self.s))
        self.assertEqual([g.price for g in got], [14.0])

    def test_the_readings_genuinely_differ(self):
        """
        ⭐ ولولا اختلافُهما لما كان للقياس معنًى.

        هنا 12 لم تُسحَب (لا شيء فوقها) لكنّها **لم تسحب** 14 قبلها.
        """
        s = mk((10, 14, 9, 11), (11, 11, 10, 10), (10, 12, 10, 11),
               (11, 11.5, 10, 11))
        swings = [sw(0, 14.0, "high"), sw(2, 12.0, "high")]
        self.assertEqual([g.price for g in
                          structural(s, swings, "unswept", upto=len(s))],
                         [14.0, 12.0])
        self.assertEqual(structural(s, swings, "sweeper", upto=len(s)), [])

    def test_empty_in_empty_out(self):
        for rule in ("all", "unswept", "sweeper", "both"):
            with self.subTest(rule=rule):
                self.assertEqual(
                    structural(mk((1, 2, 0, 1)), [], rule, upto=1), [])

    def test_output_stays_ordered_by_index(self):
        s = mk(*[(10, 11, 9, 10)] * 12)
        swings = [sw(i, 10.0 + i, "high") for i in (8, 2, 5)]
        got = structural(s, swings, "sweeper", upto=len(s))
        self.assertEqual([g.index for g in got], sorted(g.index for g in got))


class TestItDecidesNothingUntilAsked(unittest.TestCase):
    """
    ⛔⛔ **والقياسُ ردَّها، ويُقال بنصّه قبل أيّ وصل:**

    بُنيت ثم قِيست على أسبوع 09-14، فاستردّت 26 تصنيفًا من 50 —
    **وخسرت الدقّة**: على اليومين الوحيدَين القابلَين للمقارنة بأحكام
    المدرّب المسجَّلة قبل القياس، نزلت من **2/2** إلى **1/2**.

    ويومان عيّنةٌ لا تكفي لحكم — **ولا تكفي لتغيير الكود.**

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⭐⭐⭐ **ووُصلت 2026-10-17 — وهذا الحارسُ تغيّر سؤالُه.**       ║
    ║                                                              ║
    ║  كان يسأل: **[أيستوردها `chain`؟]** ⇒ ويمنع الاستيراد.       ║
    ║  **وذلك يمنع القياسَ الذي طلبه الردُّ نفسُه** — فنصُّه          ║
    ║  أعلاه يقول [**حتى يفصل أسبوعٌ أطول**]، ولا سبيلَ إلى          ║
    ║  أسبوعٍ أطول بلا فرعٍ في `--rule`.                            ║
    ║                                                              ║
    ║  ⇒ **فصار يسأل السؤالَ الأصحّ**: [أتقرّر شيئًا اليوم؟]         ║
    ║  والجواب لا — `ChainConfig().structure_swings == "all"`،      ║
    ║  **وفرعُ `all` يُرجع `find_swings` بلا مسٍّ**. ⇒ **فمن قلب      ║
    ║  الافتراضَ أسقط الطقم**، ومن وصلها بلا مفتاحٍ كذلك.            ║
    ╚══════════════════════════════════════════════════════════════╝
    """

    def test_the_live_default_is_every_fractal_swing(self):
        from bot.chain import DEFAULT_STRUCTURE_SWINGS, ChainConfig
        self.assertEqual("all", DEFAULT_STRUCTURE_SWINGS)
        self.assertEqual("all",
                         ChainConfig("M15", "M3", 0.25).structure_swings)

    def test_the_all_path_returns_the_fractal_swings_untouched(self):
        """⭐ **ومقيسٌ لا مقروء** — السلسلةُ نفسُها في الحالتين."""
        from bot.chain import ChainConfig, _structure_swings
        from bot.primitives.swings import find_swings
        series = _rising()
        cfg = ChainConfig("M15", "M3", 0.25)
        self.assertEqual(list(find_swings(series, cfg.swing_lookback,
                                          cfg.swing_plateau)),
                         _structure_swings(series, cfg))

    def test_a_filtered_reading_genuinely_drops_swings(self):
        """⛔ **ولو تطابقت القراءاتُ كان المفتاحُ زينة.**"""
        from bot.chain import ChainConfig, _structure_swings
        series = _rising()
        base = len(_structure_swings(series, ChainConfig("M15", "M3", 0.25)))
        thin = len(_structure_swings(
            series, ChainConfig("M15", "M3", 0.25,
                                structure_swings="unswept")))
        self.assertLess(thin, base)

    def test_an_unknown_reading_is_refused_at_config_time(self):
        from bot.chain import ChainConfig, read_frame
        from bot.primitives.swings import find_swings
        series = _rising()
        cfg = ChainConfig("M15", "M3", 0.25, structure_swings="خيال")
        with self.assertRaises(ValueError):
            read_frame(series, find_swings(series), "bullish", cfg)

    def test_the_filter_is_never_called_without_a_moment(self):
        """⛔ **فخُّ ST1** — الترشيحُ الزمنيُّ يلزمه زمن."""
        import inspect

        from bot import chain
        src = inspect.getsource(chain._structure_swings)
        self.assertIn("upto=now", src)
        self.assertNotIn("upto=None", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestTheDefaultReadsTheFuture(unittest.TestCase):
    """
    ⛔⛔⛔ **ST1 — وُصف 2026-09-30 ولم يُقلب.**

    `unswept` تعني [لم تُسحَب **حتى أين**؟] — والافتراضُ `upto=None`
    يمسح السلسلةَ كلَّها، فيبني الحكمَ على شموعٍ لم تقع بعدُ.

    ⚠️⚠️ **والخطرُ أنّ هذه الوحدة تنتظر قياسًا**: من يصلها بلا
    `upto` يحصل على أرقامٍ تبدو ممتازة **لأنّها رأت الغيب**.
    """

    ROWS = ((100, 105, 99, 104),
            (104, 106, 103, 105),
            (105, 108, 104, 107),      # ⬅ القمّة: 108
            (107, 108, 106, 107),      # ⬅ تلامسها ولا تتجاوزها
            (107, 120, 106, 119))      # ⬅ وهذه وحدَها تسحبها

    def _series(self):
        return Series("M15", [
            Candle(T0 + timedelta(minutes=15 * i), o, h, l, c)
            for i, (o, h, l, c) in enumerate(self.ROWS)])

    def _peak(self):
        return Swing(index=2, kind="high", price=108.0,
                     time=T0 + timedelta(minutes=30))

    def test_the_same_swing_flips_with_hindsight(self):
        """
        ⛔ **والحكمُ ينقلب بشمعةٍ لم تكن قد وقعت** — وهو العطبُ
        الموصوف، **ويبقى مُبرهَنًا بتمرير نهاية السلسلة صراحةً.**
        """
        s, peak = self._series(), self._peak()
        at_decision = structural(s, [peak], "unswept", upto=3)
        with_hindsight = structural(s, [peak], "unswept", upto=len(s))

        self.assertEqual([x.index for x in at_decision], [2])
        self.assertEqual(with_hindsight, [],
                         "⇒ الحكمُ انقلب بشمعةٍ لم تكن قد وقعت")

    def test_and_the_default_can_no_longer_read_the_future_at_all(self):
        """
        ✅✅✅ **ST1 أُغلق 2026-10-16**: الترشيحُ الزمنيُّ **يلزمه
        زمن** ⇒ **فـ`upto=None` تُرفض صريحًا** بدل أن تُجيب من الغيب.

        ⭐ **وصار الفخُّ مستحيلًا لا موصوفًا** — فمن يصلها غدًا
        **لا يستطيع** أن يحصل على أرقامٍ رأت الغيب.
        """
        s, peak = self._series(), self._peak()
        for rule in ("unswept", "sweeper", "both"):
            with self.subTest(rule=rule):
                with self.assertRaises(ValueError) as cm:
                    structural(s, [peak], rule)
                self.assertIn("ST1", str(cm.exception))

    def test_but_plain_exploration_is_untouched(self):
        """⚠️ **و`rule="all"` بلا `upto` باقيةٌ** — فلا ترشيحَ زمنيًّا فيها."""
        s, peak = self._series(), self._peak()
        self.assertEqual([x.index for x in structural(s, [peak], "all")], [2])

    def test_the_cut_off_is_what_makes_it_honest(self):
        """⭐ و`upto` هو الفرقُ — لا خيارًا للراحة."""
        s, peak = self._series(), self._peak()
        for cut in (3, 4):
            with self.subTest(upto=cut):
                self.assertEqual([x.index for x in
                                  structural(s, [peak], "unswept", upto=cut)],
                                 [2])
        self.assertEqual(structural(s, [peak], "unswept", upto=5), [])

    def test_the_trap_is_written_where_whoever_wires_it_will_read(self):
        self.assertIn("ST1", structural.__doc__)
        self.assertIn("يقرأ المستقبل", structural.__doc__)
