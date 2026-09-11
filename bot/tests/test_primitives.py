"""
اختبارات البدائيات — كل اختبار يتحقق من تعريف منصوص عليه في درس.

التشغيل:  python3 -m unittest discover -s bot/tests -t .
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.guards import ExecutionBlocked, send_order
from bot.primitives.fvg import find_fvgs, group_adjacent, mark_mitigated
from bot.primitives.liquidity import find_sweeps
from bot.primitives.structure import (
    classify_trend,
    describe_trend,
    find_breaks,
    trend_at_close,
    trend_by_closes,
    validate_swings,
)
from bot.primitives.swings import find_swings

T0 = datetime(2026, 1, 1, 0, 0)


def mk(*ohlc_rows) -> Series:
    """يبني سلسلة من صفوف (open, high, low, close)."""
    candles = [
        Candle(T0 + timedelta(minutes=5 * i), o, h, l, c)
        for i, (o, h, l, c) in enumerate(ohlc_rows)
    ]
    return Series("M5", candles)


class TestSeries(unittest.TestCase):
    def test_rejects_inconsistent_ohlc(self):
        with self.assertRaises(ValueError):
            mk((10, 12, 11, 13))  # الإغلاق فوق الأعلى

    def test_body_and_wick_geometry(self):
        c = Candle(T0, open=10.0, high=14.0, low=8.0, close=12.0)
        self.assertTrue(c.bullish)
        self.assertEqual(c.body_top, 12.0)
        self.assertEqual(c.body_bottom, 10.0)
        self.assertEqual(c.upper_wick, 2.0)
        self.assertEqual(c.lower_wick, 2.0)


class TestSwings(unittest.TestCase):
    """الدرس 9: القمة أعلى من السابقة مباشرة واللاحقة مباشرة."""

    def test_detects_single_high_and_low(self):
        s = mk(
            (10, 11, 9, 10),
            (10, 15, 10, 14),   # قمة
            (14, 14, 12, 13),
            (13, 13, 5, 6),     # قاع
            (6, 9, 6, 8),
        )
        sw = find_swings(s, lookback=1)
        highs = [x for x in sw if x.is_high]
        lows = [x for x in sw if x.is_low]
        self.assertEqual([h.index for h in highs], [1])
        self.assertEqual([l.index for l in lows], [3])
        self.assertEqual(highs[0].price, 15)
        self.assertEqual(lows[0].price, 5)

    def test_wider_lookback_filters_noise(self):
        s = mk(
            (10, 11, 9, 10), (10, 12, 10, 11), (11, 20, 11, 19),
            (19, 19, 17, 18), (18, 18, 16, 17),
        )
        self.assertTrue(any(x.index == 2 for x in find_swings(s, lookback=2)))

    def test_rejects_zero_lookback(self):
        with self.assertRaises(ValueError):
            find_swings(mk((1, 2, 0, 1)), lookback=0)


class TestFVG(unittest.TestCase):
    """
    الدرس 5: ثلاث شموع، بالذيول.
    صاعد: بين high الشمعة 1 و low الشمعة 3.
    """

    def test_bullish_gap_uses_wicks(self):
        s = mk(
            (10, 100, 9, 99),      # الشمعة 1 — أعلاها 100
            (99, 130, 98, 128),    # اندفاع
            (128, 140, 105, 138),  # الشمعة 3 — أدناها 105
        )
        g = find_fvgs(s)
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0].direction, "bullish")
        self.assertEqual(g[0].bottom, 100)
        self.assertEqual(g[0].top, 105)
        self.assertEqual(g[0].midpoint, 102.5)

    def test_bearish_gap_uses_wicks(self):
        s = mk(
            (140, 145, 100, 105),
            (105, 106, 80, 82),
            (82, 95, 70, 75),      # أعلاها 95 < أدنى الشمعة 1 = 100
        )
        g = find_fvgs(s)
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0].direction, "bearish")
        self.assertEqual(g[0].bottom, 95)
        self.assertEqual(g[0].top, 100)

    def test_edge_follows_the_wick_not_the_body(self):
        """
        ⭐⭐⭐ C9 — مقيس من شاشة المدرّب (2026-08-31).

        الشمعة الثالثة لها **ذيل علويّ طويل**: قمتها 95 وأعلى جسمها 85.
        وحافة الصندوق على شارته وقفت عند **طرف الذيل** وابتعدت عن الجسم
        بنحو 70 بكسل في لقطتين مستقلّتين.

        فلو رُسم بالأجسام لكان الحدّ 85 والمنتصف 92.5 — وذلك يزيح
        **بوابة الـ50%** ومعها كل نقطة دخول.
        """
        s = mk(
            (140, 145, 100, 105),
            (105, 106, 80, 82),
            (82, 95, 70, 85),      # ذيل علويّ إلى 95 · أعلى الجسم 85
        )
        g = find_fvgs(s)[0]
        self.assertEqual(g.bottom, 95)          # الذيل ✅
        self.assertNotEqual(g.bottom, 85)       # الجسم ❌
        self.assertEqual(g.midpoint, 97.5)      # لا 92.5

    def test_a_candle_without_a_wick_bounds_the_gap_by_its_body(self):
        """
        «من الذيل إلى الجسم» — ليس خلطًا بين مرجعين.

        الطرف هو الحدّ: فحين لا ذيل، تكون حافة الجسم هي الطرف نفسه.
        هنا الشمعة الأولى إغلاقها = قاعها (بلا ذيل سفليّ).
        """
        s = mk(
            (140, 145, 100, 100),  # لا ذيل سفليّ: القاع = أسفل الجسم
            (99, 100, 80, 82),
            (82, 95, 70, 85),
        )
        g = find_fvgs(s)[0]
        self.assertEqual(g.top, 100)

    def test_no_gap_when_wicks_overlap(self):
        s = mk((10, 100, 9, 99), (99, 130, 98, 128), (128, 140, 95, 138))
        self.assertEqual(find_fvgs(s), [])

    def test_min_size_filter(self):
        s = mk((10, 100, 9, 99), (99, 130, 98, 128), (128, 140, 101, 138))
        self.assertEqual(len(find_fvgs(s, min_size=0.0)), 1)
        self.assertEqual(len(find_fvgs(s, min_size=5.0)), 0)

    def test_mitigation_flag(self):
        s = mk(
            (10, 100, 9, 99),
            (99, 130, 98, 128),
            (128, 140, 105, 138),
            (138, 139, 102, 103),   # عاد داخل الفراغ
        )
        self.assertTrue(mark_mitigated(s, find_fvgs(s))[0].mitigated)

    def test_grouping_depends_on_max_gap(self):
        """الفراغان هنا يفصلهما 25 نقطة — الدمج يتوقف على العتبة (§17)."""
        s = mk(
            (10, 100, 9, 99),      # الفراغ الأول : 100 → 105
            (99, 130, 98, 128),
            (128, 140, 105, 138),
            (138, 160, 137, 158),  # الفراغ الثاني: 130 → 137
        )
        gaps = find_fvgs(s)
        self.assertEqual([(g.bottom, g.top) for g in gaps], [(100, 105), (130, 137)])

        self.assertEqual(len(group_adjacent(gaps, max_gap=10.0)), 2)

        merged = group_adjacent(gaps, max_gap=30.0)
        self.assertEqual(len(merged), 1)
        bottom, top, mid = merged[0]
        self.assertEqual((bottom, top), (100, 137))
        self.assertEqual(mid, (bottom + top) / 2)


class TestStructure(unittest.TestCase):
    def test_classify_bullish(self):
        """قمم أعلى (20 → 25 → 30) وقيعان أعلى (8 → 9)."""
        s = mk(
            (10, 12, 9, 11),
            (11, 20, 10, 19),    # قمة 20
            (19, 19, 8, 13),     # قاع 8
            (13, 25, 12, 24),    # قمة 25
            (24, 24, 9, 10),     # قاع 9
            (10, 30, 10, 29),    # قمة 30
            (29, 29, 25, 26),
        )
        sw = find_swings(s)
        self.assertEqual([x.price for x in sw if x.is_high], [20, 25, 30])
        self.assertEqual([x.price for x in sw if x.is_low], [8, 9])
        self.assertEqual(classify_trend(sw), "bullish")

    def test_undefined_names_which_of_the_two_causes(self):
        """
        ⭐ في أسبوع الملاحظة رُفض **210 قرارًا (39%)** بدليلٍ واحد:
        «لا قمم/قيعان كافية للحكم» — وهو مستحيل بمئتَي شمعة. فالسبب
        الحقيقيّ كان الحالة الثانية، وقال المدرّب في اليوم نفسه:
        «صرنا عم نلعب بقلب **داينامك رينج**».
        """
        s = mk(
            (10, 12, 9, 11),
            (11, 30, 10, 29),    # قمة 30
            (29, 29, 8, 13),     # قاع 8
            (13, 25, 12, 24),    # قمة 25 — أدنى
            (24, 24, 5, 6),      # قاع 5 — أدنى
            (6, 40, 6, 39),      # قمة 40 — أعلى ⇒ تضارب
            (39, 39, 35, 36),
        )
        trend, why = describe_trend(find_swings(s))
        self.assertEqual(trend, "undefined")
        self.assertIn("متضارب", why)
        self.assertNotIn("كافية", why)

    def test_too_few_swings_says_how_few(self):
        trend, why = describe_trend([])
        self.assertEqual(trend, "undefined")
        self.assertIn("كافية", why)
        self.assertIn("0 قمة", why)

    def test_a_defined_trend_carries_no_excuse(self):
        s = mk(
            (10, 12, 9, 11), (11, 20, 10, 19), (19, 19, 8, 13),
            (13, 25, 12, 24), (24, 24, 9, 10), (10, 30, 10, 29),
            (29, 29, 25, 26),
        )
        self.assertEqual(describe_trend(find_swings(s)), ("bullish", ""))

    def test_the_two_functions_never_disagree(self):
        """`classify_trend` هي `describe_trend` بلا سببها — لا نسخةٌ ثانية."""
        for swings in ([], find_swings(mk((10, 12, 9, 11), (11, 20, 10, 19),
                                          (19, 19, 8, 13), (13, 25, 12, 24),
                                          (24, 24, 9, 10), (10, 30, 10, 29),
                                          (29, 29, 25, 26)))):
            self.assertEqual(classify_trend(swings), describe_trend(swings)[0])

    def test_one_close_beyond_is_not_a_break_when_two_are_required(self):
        """
        ⭐ «عنّا الأربع ساعات **ما أغلق تحت بشمعتين** فنحن هيكلنا هابط».
        فإغلاقٌ واحد خلف المستوى لا يكسره — والقاعدة قرارُ المستخدم:
        «اثنتان أقوى».
        """
        s = mk(
            (10, 11,  9, 10),
            (10, 20, 10, 19),     # قمة 20
            (19, 19, 15, 16),
            (16, 26, 15, 25),     # إغلاق واحد فوق 20
            (25, 25, 15, 17),     # ثم عاد تحته
        )
        sw = find_swings(s)
        self.assertEqual(trend_by_closes(s, sw, closes=2), [])
        self.assertTrue(trend_by_closes(s, sw, closes=1))

    def test_two_consecutive_closes_confirm_the_break(self):
        s = mk(
            (10, 11,  9, 10),
            (10, 20, 10, 19),     # قمة 20
            (19, 19, 15, 16),
            (16, 26, 15, 25),     # إغلاق 1 فوق
            (25, 28, 24, 27),     # إغلاق 2 فوق ⇒ تأكّد
        )
        line = trend_by_closes(s, find_swings(s), closes=2)
        self.assertEqual([t for _, t in line], ["bullish"])

    def test_the_streak_resets_it_does_not_accumulate(self):
        """⚠️ **التتابع شرط**: إغلاقان متفرّقان ليسا إغلاقين متتاليين."""
        s = mk(
            (10, 11,  9, 10),
            (10, 20, 10, 19),     # قمة 20
            (19, 19, 15, 16),
            (16, 26, 15, 25),     # فوق
            (25, 25, 15, 17),     # عاد تحت ⇒ صفر
            (17, 26, 16, 25),     # فوق مرّة أخرى — وهو الأول لا الثاني
        )
        self.assertEqual(trend_by_closes(s, find_swings(s), closes=2), [])

    def test_the_close_decides_not_the_body(self):
        """
        قال «**أغلق**» — وجسم الشمعة يشمل الافتتاح، فيكسر بما لم
        يُغلق عليه.
        """
        s = mk(
            (10, 11,  9, 10),
            (10, 20, 10, 19),     # قمة 20
            (19, 19, 15, 16),
            (25, 26, 15, 17),     # افتتح فوق 20 وأغلق تحتها
            (25, 26, 15, 17),
        )
        self.assertEqual(trend_by_closes(s, find_swings(s), closes=1), [])

    def test_it_returns_a_timeline_not_one_verdict(self):
        """ليُقارَن بتحيّز المدرّب **يومًا بيوم** لا بحصيلة آخر الأسبوع."""
        s = mk(
            (10, 11,  9, 10),
            (10, 20, 10, 19),     # قمة 20
            (19, 19,  5,  6),     # قاع 5
            (6, 26, 6, 25), (25, 28, 24, 27),      # صعد فوق القمة
            (27, 28,  4,  4), (4, 5, 3, 3),        # ثم تحت القاع
        )
        line = trend_by_closes(s, find_swings(s), closes=2)
        self.assertEqual([t for _, t in line], ["bullish", "bearish"])

    def test_trend_at_close_is_the_last_state(self):
        s = mk(
            (10, 11, 9, 10), (10, 20, 10, 19), (19, 19, 15, 16),
            (16, 26, 15, 25), (25, 28, 24, 27),
        )
        self.assertEqual(trend_at_close(s, find_swings(s), closes=2), "bullish")

    def test_nothing_broken_is_undefined_not_a_guess(self):
        s = mk(*[(10, 11, 9, 10)] * 6)
        self.assertEqual(trend_at_close(s, find_swings(s), closes=2), "undefined")

    def test_zero_closes_is_refused(self):
        with self.assertRaises(ValueError):
            trend_by_closes(mk((10, 11, 9, 10)), [], closes=0)

    def test_more_closes_never_gives_more_breaks(self):
        """اشتراطٌ أشدّ لا يُنتج كسورًا أكثر — وإلا فالعدّاد معطوب."""
        s = mk(
            (10, 11, 9, 10), (10, 20, 10, 19), (19, 19, 15, 16),
            (16, 26, 15, 25), (25, 28, 24, 27), (27, 29, 26, 28),
        )
        sw = find_swings(s)
        counts = [len(trend_by_closes(s, sw, closes=n)) for n in (1, 2, 3)]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_break_requires_body_not_wick(self):
        """الدرس 10: الكسر بالجسم لا بالذيل."""
        s = mk(
            (10, 11, 9, 10),
            (10, 20, 10, 19),     # قمة عند 20
            (19, 19, 15, 16),
            (16, 25, 15, 18),     # الذيل تجاوز 20 والجسم لم يتجاوز
        )
        sw = find_swings(s)
        self.assertEqual(find_breaks(s, sw, use_body=True), [])
        self.assertTrue(find_breaks(s, sw, use_body=False))

    def test_body_break_is_detected(self):
        s = mk(
            (10, 11, 9, 10), (10, 20, 10, 19), (19, 19, 15, 16), (16, 26, 15, 25),
        )
        b = find_breaks(s, find_swings(s), use_body=True)
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0].direction, "up")
        self.assertEqual(b[0].level, 20)

    def test_true_high_needs_governing_low_break(self):
        """
        المرحلة 2 الدرس 4: القمة لا تصبح حقيقية إلا إذا كسرت الحركة الهابطة
        التالية لها القاع الحاكم.
        """
        s = mk(
            (12, 13, 11, 12),
            (12, 12, 5, 6),       # قاع حاكم عند 5
            (6, 30, 6, 29),       # قمة عند 30
            (29, 29, 20, 21),
            (21, 22, 3, 4),       # الجسم أغلق عند 4 — كسر القاع الحاكم
        )
        validated = validate_swings(s, find_swings(s), use_body=True)
        self.assertTrue(any(v.swing.is_high and v.swing.price == 30 for v in validated))

    def test_corrective_high_is_not_validated(self):
        """القمة نفسها تبقى تصحيحية ما دام القاع الحاكم لم يُكسر."""
        s = mk(
            (12, 13, 11, 12),
            (12, 12, 5, 6),
            (6, 30, 6, 29),
            (29, 29, 20, 21),
            (21, 22, 15, 16),     # لم يصل إلى 5
        )
        validated = validate_swings(s, find_swings(s), use_body=True)
        self.assertFalse(any(v.swing.is_high and v.swing.price == 30 for v in validated))


class TestLiquidity(unittest.TestCase):
    def test_sweep_requires_reclaim(self):
        s = mk(
            (10, 11, 9, 10),
            (10, 20, 10, 19),     # قمة عند 20
            (19, 19, 15, 16),
            (16, 25, 15, 17),     # تجاوز 20 وأغلق تحتها ⇒ كسح
        )
        sweeps = find_sweeps(s, find_swings(s), max_bars_to_reclaim=2)
        self.assertEqual(len(sweeps), 1)
        self.assertEqual(sweeps[0].side, "buy_side")
        self.assertEqual(sweeps[0].level, 20)
        self.assertEqual(sweeps[0].extreme, 25)

    def test_clean_break_is_not_a_sweep(self):
        s = mk(
            (10, 11, 9, 10), (10, 20, 10, 19), (19, 19, 15, 16), (16, 25, 15, 24),
        )
        self.assertEqual(find_sweeps(s, find_swings(s), max_bars_to_reclaim=2), [])

    def test_min_penetration_filter(self):
        s = mk(
            (10, 11, 9, 10), (10, 20, 10, 19), (19, 19, 15, 16), (16, 20.5, 15, 17),
        )
        sw = find_swings(s)
        self.assertTrue(find_sweeps(s, sw, min_penetration=0.1))
        self.assertEqual(find_sweeps(s, sw, min_penetration=5.0), [])


class TestExecutionGuard(unittest.TestCase):
    """التنفيذ ممنوع حتى إذن صريح لاحق."""

    def test_send_order_is_blocked(self):
        with self.assertRaises(ExecutionBlocked):
            send_order("XAUUSD.m", "buy", 0.01)

    def test_block_message_explains_requirements(self):
        try:
            send_order()
        except ExecutionBlocked as e:
            self.assertIn("نفذ" if "نفذ" in str(e) else "التحليل", str(e))


if __name__ == "__main__":
    unittest.main(verbosity=2)
