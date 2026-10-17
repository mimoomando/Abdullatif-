"""
حُرّاسُ نموذج الجارتلي — **ووصل درسُه 2026-10-17.**

⛔ **وهو غيرُ موصول**، والهارمونيك مُعطَّلٌ بقياس ⇒ **فلا رقمٌ منشورٌ
يتحرّك بهذا الملفّ.** والغرضُ ألّا تُنسى النسبُ، وألّا يُملأ المجهولُ
منها بالتخمين.
"""

import unittest
from datetime import datetime, timedelta

from bot.primitives.gartley import (B_RETRACE_FLOOR, B_RETRACE_RISKY_FLOOR,
                                    B_RETRACE_TOP_READINGS, BD_EXTENSION,
                                    BD_TOLERANCE, C_RETRACE, D_RETRACE,
                                    STOP_RETRACE, Gartley, active, build,
                                    find_patterns)
from bot.primitives.harmonic import PatternRejected
from bot.primitives.swings import Swing

T0 = datetime(2026, 10, 1)


def sw(index, price, kind):
    return Swing(index, T0 + timedelta(minutes=15 * index), price, kind)


#: جارتلي صاعدٌ مستوفٍ — B 0.600 · C 0.600 · BD 1.517
X, A, B, C = (sw(0, 100.0, "low"), sw(1, 200.0, "high"),
              sw(2, 140.0, "low"), sw(3, 176.0, "high"))


class TestTheRatiosAreTheOnesSpoken(unittest.TestCase):
    """⭐ كلُّ رقمٍ هنا منصوصٌ بلفظه — ويُثبَّت كي لا يُبدَّل بالذاكرة."""

    def test_the_spoken_numbers(self):
        self.assertEqual(0.586, B_RETRACE_FLOOR)
        self.assertEqual(0.52, B_RETRACE_RISKY_FLOOR)
        self.assertEqual((0.382, 0.886), C_RETRACE)
        self.assertEqual(0.786, D_RETRACE)
        self.assertEqual((1.130, 1.610), BD_EXTENSION)
        self.assertEqual(1.0, STOP_RETRACE)

    def test_the_bd_ceiling_has_no_tolerance_and_why(self):
        """
        ⭐⭐⭐ «1.610 **بالضبط** ممنوع تتغير … **لانه اذا صارت 618
        … صار عندك نموذج خفاش**» ⇒ **فالحدُّ فاصلٌ بين نموذجين**،
        وتوسيعُه يجعلهما يتداخلان.
        """
        from bot.primitives import bat
        self.assertEqual(0.0, BD_TOLERANCE)
        self.assertEqual(1.618, bat.BD_EXTENSION[0])
        self.assertLess(BD_EXTENSION[1], bat.BD_EXTENSION[0])

    def test_the_lesson_is_a_second_source_for_four_live_numbers(self):
        """
        ⭐⭐ **ولا واحدٌ منها احتاج تصحيحًا** — فُحصت قبل كتابة الجدول.
        """
        from bot.primitives import bat, butterfly, harmonic
        self.assertEqual(0.382, harmonic.MIN_RETRACE)
        self.assertEqual((0.382, 0.58), bat.B_RETRACE)
        self.assertEqual((1.618, 2.618), bat.BD_EXTENSION)
        self.assertEqual((0.75, 0.82), butterfly.AB_RETRACE)
        # «النسبه العليا هي 0.82 مسموح توصل ل 0.85» ⇒ 0.82 + 0.03
        self.assertAlmostEqual(0.85, butterfly.AB_RETRACE[1]
                               + butterfly.AB_TOLERANCE, places=9)


class TestTheCeilingIsAskedForNotGuessed(unittest.TestCase):
    """
    ⛔⛔⛔ **قيلت قراءتان في الدرس نفسِه** (0.646 · 0.664) ⇒
    **فلا تُختار إحداهما عن المستخدم** (القاعدة ①).
    """

    def test_both_readings_are_recorded(self):
        self.assertEqual((0.646, 0.664), B_RETRACE_TOP_READINGS)

    def test_a_build_without_a_ceiling_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            build(X, A, B, C, "M15")
        self.assertIn("0.646", str(cm.exception))
        self.assertIn("0.664", str(cm.exception))

    def test_a_third_value_is_refused_as_invention(self):
        with self.assertRaises(ValueError) as cm:
            build(X, A, B, C, "M15", b_top=0.65)
        self.assertIn("اختراع", str(cm.exception))

    def test_the_two_readings_genuinely_differ(self):
        """
        ⭐⭐⭐ **وبرهانُ أنّهما قراءتان** — ولولاه كان المقبضُ زينة.

        تصحيحُ B = 0.655: **يُقبل تحت 0.664 ويُرفض تحت 0.646.**
        """
        b, c = sw(2, 134.5, "low"), sw(3, 173.8, "high")
        ok = build(X, A, b, c, "M15", b_top=0.664)
        self.assertAlmostEqual(0.655, ok.b_retrace, places=3)
        with self.assertRaises(PatternRejected):
            build(X, A, b, c, "M15", b_top=0.646)

    def test_the_chosen_reading_is_carried_so_it_is_not_forgotten(self):
        self.assertEqual(0.664, build(X, A, B, C, "M15",
                                      b_top=0.664).b_top)

    def test_find_patterns_refuses_too_it_is_not_a_rejected_pattern(self):
        """⛔ **سقفٌ غيرُ مسمًّى عطبُ نداءٍ لا رفضُ نموذج** — فلا يُبتلَع."""
        from bot.data import Candle, Series
        bars = [Candle(T0 + timedelta(minutes=15 * i), 100, 201, 99, 150)
                for i in range(6)]
        with self.assertRaises(ValueError):
            find_patterns(Series("M15", bars), [X, A, B, C])


class TestTheRiskyExceptionIsOffAndNamed(unittest.TestCase):
    """
    ⚠️ «الاستثناء هي نسبه 0.586 ممكن تتاخذ على **0.52** ما في مشكله
    **ولكن بيبقى دائما في خطوره وخاصه مع جارتلي**» ⇒ **فالتحفُّظ
    يُحمَل مع النموذج** (عرفُ VL1: المرفوضُ لا يكون الافتراضَ صامتًا).
    """

    RISKY = (sw(2, 145.0, "low"), sw(3, 193.7, "high"))   # B = 0.550

    def test_off_by_default(self):
        with self.assertRaises(PatternRejected) as cm:
            build(X, A, *self.RISKY, timeframe="M15", b_top=0.646)
        self.assertIn("0.52", str(cm.exception))

    def test_asked_for_it_is_admitted_and_flagged(self):
        g = build(X, A, *self.RISKY, timeframe="M15", b_top=0.646,
                  allow_risky=True)
        self.assertTrue(g.risky)
        self.assertIn("بيبقى في خطوره", g.render())

    def test_below_the_exception_it_is_refused_even_when_asked(self):
        b, c = sw(2, 150.0, "low"), sw(3, 199.0, "high")      # B = 0.50
        with self.assertRaises(PatternRejected):
            build(X, A, b, c, "M15", b_top=0.646, allow_risky=True)

    def test_a_sound_pattern_is_not_flagged(self):
        self.assertFalse(build(X, A, B, C, "M15", b_top=0.646).risky)


class TestTheGeometry(unittest.TestCase):

    def setUp(self):
        self.g = build(X, A, B, C, "M15", b_top=0.646)

    def test_entry_is_0786_of_xa_from_a(self):
        self.assertAlmostEqual(121.4, self.g.entry, places=9)

    def test_the_stop_sits_on_x_itself(self):
        """«نقطه وقف الخساره هي **واحد على صفر عند الاكس**»."""
        self.assertAlmostEqual(X.price, self.g.stop, places=9)

    def test_a_low_x_is_a_buy(self):
        self.assertEqual("bullish", self.g.direction)
        self.assertEqual("bearish",
                         build(sw(0, 200.0, "high"), sw(1, 100.0, "low"),
                               sw(2, 160.0, "high"), sw(3, 124.0, "low"),
                               "M15", b_top=0.646).direction)

    def test_targets_run_from_a_to_d_not_from_c(self):
        """«تحقيق الاهداف هي **من نقطه A الى دي**»."""
        span = A.price - self.g.entry
        self.assertAlmostEqual(self.g.entry + span * 0.382,
                               self.g.targets()[0], places=9)

    def test_breaking_c_before_d_invalidates(self):
        from bot.data import Candle, Series
        bars = [Candle(T0 + timedelta(minutes=15 * i), 150, 151, 149, 150)
                for i in range(5)]
        # شمعةٌ تهبط دون B قبل بلوغ D=121.4 ⇒ كسرُ C في الشراء هو الصعودُ فوقه
        bars[4] = Candle(bars[4].time, 150, 180.0, 149, 179.0)
        s = Series("M15", bars)
        self.assertEqual([], active(s, [self.g]))

    def test_a_ratio_outside_its_range_is_refused_not_approximated(self):
        """«النسب بالهارمونيك مقدّسة — ما في مزح»."""
        with self.assertRaises(PatternRejected):
            build(X, A, sw(2, 120.0, "low"), sw(3, 160.0, "high"),
                  "M15", b_top=0.646)


class TestTheScanIsNotClaimedComplete(unittest.TestCase):
    """
    ⚠️ **عبارةُ [يمسح كلّ رباعيّة] صُحّحت ثلاثَ مرّات** في هذا المشروع
    (`harmonic` · `bat` · `butterfly`) ⇒ **فلا تُكتب رابعةً.**
    """

    def test_the_docstring_does_not_claim_a_complete_scan(self):
        self.assertNotIn("كلّ رباعية", find_patterns.__doc__ or "")
        self.assertIn("adjacent", find_patterns.__doc__ or "")


class TestTheFamiliesAreWiredAndOff(unittest.TestCase):
    """
    ⭐⭐⭐ **وُصلت `bat` و`butterfly` و`gartley` 2026-10-17** خلف
    `harmonic_families` — **وثلاثُ وحداتٍ خرجت من `UNWIRED` بنداءٍ
    واحد**، لا بثلاثة أبواب.

    ⛔ **ولا سلوكَ تغيّر**: الافتراضُ `("lightning",)`، **والهارمونيك
    كلُّه مطفأٌ بقياس.**
    """

    def _series(self):
        from bot.data import Candle, Series
        bars = [Candle(T0 + timedelta(minutes=15 * i), 150, 151, 149, 150)
                for i in range(6)]
        return Series("M15", bars)

    def test_the_live_default_is_lightning_alone(self):
        from bot.chain import ChainConfig
        from bot.primitives.harmonic_entry import DEFAULT_FAMILIES
        live = ChainConfig("M15", "M3", 0.25)
        self.assertEqual(("lightning",), DEFAULT_FAMILIES)
        self.assertEqual(("lightning",), live.harmonic_families)
        self.assertIsNone(live.harmonic_gartley_b_top)
        self.assertFalse(live.harmonic_enabled)      # ⬅ والبوّابةُ مطفأة

    def test_every_family_has_its_module(self):
        from bot.primitives.harmonic_entry import FAMILIES
        self.assertEqual(("lightning", "bat", "butterfly", "gartley"),
                         FAMILIES)

    def test_an_unknown_family_is_refused_not_skipped(self):
        """⛔ **وتخطّيها صامتةً يعطي عمودًا يبدو مقيسًا وليس كذلك.**"""
        from bot.primitives.harmonic_entry import candidates
        with self.assertRaises(ValueError) as cm:
            candidates(self._series(), [X, A, B, C], "bullish", 0.0, 999.0,
                       families=("خيال",))
        self.assertIn("خيال", str(cm.exception))

    def test_gartley_without_a_ceiling_is_refused_at_the_family_door(self):
        from bot.primitives.harmonic_entry import candidates
        with self.assertRaises(ValueError) as cm:
            candidates(self._series(), [X, A, B, C], "bullish", 0.0, 999.0,
                       families=("gartley",))
        self.assertIn("0.646", str(cm.exception))

    def test_the_chain_refuses_it_at_config_time_not_mid_scan(self):
        """⭐ **عطبُ إعدادٍ يُصاح به قبل التشغيل** — عرفُ LB1."""
        from bot.chain import ChainConfig, read_frame
        from bot.primitives.swings import find_swings
        s = self._series()
        sw = find_swings(s)
        for kw, needle in (
                (dict(harmonic_families=("خيال",)), "خيال"),
                (dict(harmonic_families=("lightning", "gartley")), "0.646")):
            with self.subTest(**kw):
                cfg = ChainConfig("M15", "M3", 0.25, **kw)
                with self.assertRaises(ValueError) as cm:
                    read_frame(s, sw, "bullish", cfg)
                self.assertIn(needle, str(cm.exception))

    def test_a_named_ceiling_passes(self):
        from bot.chain import ChainConfig, read_frame
        from bot.primitives.swings import find_swings
        s = self._series()
        cfg = ChainConfig("M15", "M3", 0.25,
                          harmonic_families=("lightning", "gartley"),
                          harmonic_gartley_b_top=0.664)
        read_frame(s, find_swings(s), "bullish", cfg)   # ⬅ لا يرفع

    def test_the_family_reaches_a_gartley_pattern(self):
        """
        ⭐⭐⭐ **وصلٌ يُبرهِن على نفسه**: النموذجُ المبنيُّ في هذا الملفّ
        **يخرج من `candidates`** حين تُطلَب عائلتُه — ولا يخرج حين لا
        تُطلَب. ⛔ **ولولا هذا لكان [الوصل] دعوًى.**
        """
        from bot.data import Candle, Series
        from bot.primitives.harmonic_entry import candidates
        bars = [Candle(T0 + timedelta(minutes=15 * i), 150, 151, 149, 150)
                for i in range(4)]
        s = Series("M15", bars)
        got = candidates(s, [X, A, B, C], "bullish", 100.0, 200.0,
                         families=("gartley",), gartley_b_top=0.646)
        self.assertEqual(1, len(got))
        self.assertAlmostEqual(121.4, got[0].entry, places=9)
        self.assertAlmostEqual(X.price, got[0].stop, places=9)
        # ⚠️ **والافتراضُ يجد برقًا سريعًا على النقاط نفسِها** (A·B·C)
        #   ⇒ **فالفحصُ على النوع لا على الفراغ**، وإلّا قال الحارسُ
        #   شيئًا غيرَ الذي بُني له.
        self.assertTrue(isinstance(got[0].pattern, Gartley))
        default = candidates(s, [X, A, B, C], "bullish", 100.0, 200.0)
        self.assertFalse(any(isinstance(h.pattern, Gartley)
                             for h in default))

    def test_the_rule_branch_exists_and_is_reachable(self):
        """⛔ **فرعٌ لا تذكره `choices` فرعٌ ميّت** — حارسٌ عامٌّ قائم."""
        with open("bot/backtest.py", encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('"harmonic-family"', src)
        self.assertIn('args.rule == "harmonic-family"', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
