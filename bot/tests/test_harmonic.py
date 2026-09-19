"""
اختبارات نموذج البرق السريع — مدرسة الهارمونيك.

⭐ الجدول هو قلب النموذج، وقد تحقّق من اثني عشر مثالًا في الدرس والبثّ.
فتُثبَّت هنا **حدود النطاقات** لا الوسط: الحدّ هو ما ينزلق.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.harmonic import (
    EXTENSION_TABLE,
    MIN_RETRACE,
    FastLightning,
    PatternRejected,
    active,
    build,
    extension_for,
    find_patterns,
    measure_retrace,
)
from bot.primitives.swings import Swing, find_swings

T0 = datetime(2026, 9, 5, 10, 0)


def sw(index, price, kind) -> Swing:
    return Swing(index, T0 + timedelta(minutes=3 * index), price, kind)


def mk(tf, *rows) -> Series:
    return Series(
        tf,
        [Candle(T0 + timedelta(minutes=3 * i), o, h, l, c)
         for i, (o, h, l, c) in enumerate(rows)],
    )


class TestTable(unittest.TestCase):
    """«من 0.382 لـ0.48 امتداد 2.24، من 0.49 الى 0.59 امتداد 2.00…»"""

    def test_every_band_boundary(self):
        cases = [
            (0.382, 2.24), (0.44, 2.24), (0.48, 2.24),
            (0.49, 2.00), (0.53, 2.00), (0.59, 2.00),
            (0.60, 1.618), (0.65, 1.618), (0.68, 1.618),
            (0.69, 1.41), (0.73, 1.41), (0.76, 1.41),
            (0.77, 1.270), (0.81, 1.270), (0.86, 1.270),
            (0.87, 1.130), (0.89, 1.130), (0.90, 1.130),
        ]
        for retrace, expected in cases:
            with self.subTest(retrace=retrace):
                self.assertEqual(extension_for(retrace), expected)

    def test_the_twelve_worked_examples_from_the_lesson(self):
        """كل مثال ذكره بنسبته وامتداده — لا واحد يخالف."""
        stated = {
            0.59: 2.00, 0.51: 2.00, 0.50: 2.00, 0.53: 2.00,
            0.74: 1.41, 0.73: 1.41, 0.71: 1.41, 0.69: 1.41,
            0.65: 1.618, 0.68: 1.618,
            0.47: 2.24,
        }
        for retrace, expected in stated.items():
            with self.subTest(retrace=retrace):
                self.assertEqual(extension_for(retrace), expected)

    def test_the_card_beats_a_spoken_example_that_contradicts_it(self):
        """
        🔴 **H8 — تعارضٌ بين لسانه وبطاقته، والبطاقة رُجِّحت.**

        في الدرس مثالٌ منطوق: **0.85 ⇒ 1.13**. وفي بطاقته المنشورة
        الصفُّ الخامس **0.77 – 0.86 ⇒ 1.270**.

        ⇒ ورُجِّحت البطاقة لسببين معدودَين لا مزاج:

        ١. **أحد عشر مثالًا من اثني عشر** في الدرس نفسه يوافقان
           البطاقة حرفًا بحرف. والمخالف **واحد**.
        ٢. وهو يحيل إليها بنفسه بديلًا عن السماع: «**ما تعذّب حالك
           إنك تاخذ سكرين شوت**… عليك تروح على صندوق الوصف».

        ⛔ **والتعارض مسجَّلٌ لا مطويّ.** وهذا الاختبار هو موضعه في
        الكود: إن وصل ما يرجّح المنطوق، فهو أوّل ما يسقط.
        """
        self.assertEqual(extension_for(0.85), 1.270)      # البطاقة
        self.assertNotEqual(extension_for(0.85), 1.13)    # المنطوق

    def test_the_card_stop_column_is_taken_verbatim(self):
        """عمود SL في البطاقة — لا مشتقًّا من السلّم."""
        from bot.primitives.harmonic import STOP_LADDER
        self.assertEqual(STOP_LADDER, {
            1.130: 1.270, 1.270: 1.410, 1.410: 1.618,
            1.618: 2.000, 2.000: 2.240, 2.240: 2.618,
        })

    def test_1270_is_a_rung_at_all(self):
        """⛔ كانت غائبةً من السلّم كلِّه، فكان وقفُ الدخول من 1.130 خطأً."""
        from bot.primitives.harmonic import LADDER
        self.assertIn(1.270, LADDER)

    def test_above_the_last_band_is_still_refused(self):
        """والبطاقة تنتهي عند 0.90 — وما فوقها لم يُعطَ، فلا يُخمَّن."""
        for r in (0.905, 0.95, 0.99):
            with self.subTest(retrace=r):
                with self.assertRaises(PatternRejected):
                    extension_for(r)

    def test_below_382_is_refused(self):
        """«أقل نسبة مسموح يصحح فيها هي 0.382» — ورفض مثالًا عند 35%."""
        for r in (0.35, 0.20, 0.381):
            with self.subTest(retrace=r):
                with self.assertRaises(PatternRejected):
                    extension_for(r)

    def test_above_the_table_is_refused_not_guessed(self):
        """فوق آخر نطاق: الجدول الكامل لم يصل (H1) ⇒ لا يُخمَّن امتداد."""
        with self.assertRaises(PatternRejected):
            extension_for(0.95)

    def test_the_published_target_card_matches_the_code(self):
        """
        ⭐ **البطاقة الثالثة** — أوّل روابط وصف الدرس، «نسب الأهداف».

        وهي كأختها لقطةٌ لإعدادات الأداة. والمؤشَّر فيها خمسة:

            ✅ 0   ✅ 0.382   ✅ 0.5   ✅ 0.618   ✅ 1

        الطرفان أسودان (مرساتان)، والثلاثة الوسطى **برتقاليّة** —
        وهو لونُ ما يتصرّف عليه، كنسب OTE على شارته الحيّ.

        ✅ فطابقت `TARGET_RATIOS` بلا تغيير. **وهذه أوّل بطاقةٍ
        تؤكّد الكود بدل أن تنقضه** — والاثنتان قبلها أسقطتا صفًّا
        وبدّلتا مدًى خامًا.
        """
        from bot.primitives.harmonic import TARGET_RATIOS
        self.assertEqual(TARGET_RATIOS, (0.382, 0.5, 0.618))

    def test_the_fast_target_is_absent_from_the_card_as_it_should_be(self):
        """
        ⚠️ و**0.236 غير مؤشَّرة** في البطاقة — ويوافق ذلك قولَه:
        «بدك هدف سريع **حطّ** الـ0.236». فهي إضافةٌ لا أصل.

        ولذلك هي `include_fast=False` افتراضًا في `targets()`.
        """
        from bot.primitives.harmonic import FAST_TARGET_RATIO, TARGET_RATIOS
        self.assertAlmostEqual(FAST_TARGET_RATIO, 0.236)
        self.assertNotIn(FAST_TARGET_RATIO, TARGET_RATIOS)

    def test_min_retrace_matches_the_lesson(self):
        self.assertAlmostEqual(MIN_RETRACE, 0.382)

    def test_table_bands_ascend(self):
        tops = [t for t, _ in EXTENSION_TABLE]
        self.assertEqual(tops, sorted(tops))


class TestGeometry(unittest.TestCase):
    """A قمة · B قاع · C قمة ⇒ D تحت ⇒ شراء."""

    def _buy(self):
        # A=200 · B=100 · C=150 ⇒ تصحيح 50% ⇒ امتداد 2.00
        return build(sw(0, 200.0, "high"), sw(5, 100.0, "low"),
                     sw(10, 150.0, "high"), "M15")

    def test_retrace_is_measured_on_the_ab_leg(self):
        p = self._buy()
        self.assertAlmostEqual(p.retrace, 0.5)
        self.assertEqual(p.extension, 2.00)

    def test_direction_is_the_trade_not_the_first_leg(self):
        self.assertEqual(self._buy().direction, "bullish")

    def test_entry_projects_the_bc_leg_from_c(self):
        """D = C − (C−B) × الامتداد = 150 − 50×2 = 50."""
        self.assertAlmostEqual(self._buy().entry, 50.0)

    def test_stop_is_the_next_rung(self):
        """2.00 ⇒ 2.24 ⇒ 150 − 50×2.24 = 38."""
        self.assertAlmostEqual(self._buy().stop, 38.0)

    def test_targets_are_measured_from_c_to_entry_not_to_stop(self):
        """
        ⚠️ «التارجت من الـC إلى **نقطة الدخول**» — نبّه عليها صراحةً.

        المدى C→D = 100. فالأهداف فوق الدخول (50) بـ38.2 · 50 · 61.8.
        ولو قيست إلى الوقف (112) لتضخّمت كلها.
        """
        t = self._buy().targets()
        self.assertAlmostEqual(t[0], 88.2)
        self.assertAlmostEqual(t[1], 100.0)
        self.assertAlmostEqual(t[2], 111.8)

    def test_fast_target_is_opt_in(self):
        p = self._buy()
        self.assertEqual(len(p.targets()), 3)
        fast = p.targets(include_fast=True)
        self.assertEqual(len(fast), 4)
        self.assertAlmostEqual(fast[0], 73.6)      # 0.236

    def test_targets_lie_between_entry_and_c(self):
        p = self._buy()
        for t in p.targets(include_fast=True):
            self.assertGreater(t, p.entry)
            self.assertLess(t, p.c.price)

    def test_sell_side_mirrors(self):
        # A=100 · B=200 · C=150 ⇒ تصحيح 50% ⇒ امتداد 2.00 ⇒ D=250
        p = build(sw(0, 100.0, "low"), sw(5, 200.0, "high"),
                  sw(10, 150.0, "low"), "M15")
        self.assertEqual(p.direction, "bearish")
        self.assertAlmostEqual(p.entry, 250.0)
        self.assertAlmostEqual(p.stop, 262.0)
        self.assertTrue(all(t < p.entry for t in p.targets()))

    def test_stop_is_farther_than_entry(self):
        p = self._buy()
        self.assertLess(p.stop, p.entry)
        self.assertAlmostEqual(p.stop_distance(), 12.0)


class TestHardStop(unittest.TestCase):
    """
    ⭐ قرار المستخدم 2026-09-05: «نعم 2.618، وضع وقفًا صلبًا خلفه».

        الدخول      ← الدرجة من الجدول
        وقف الإغلاق ← الدرجة التالية     (قاعدة المدرّب)
        الوقف الصلب ← الدرجة التي تليها  (شبكة الأمان)
    """

    def _at(self, c_price):
        return build(sw(0, 200.0, "high"), sw(5, 100.0, "low"),
                     sw(10, c_price, "high"), "M15")

    def test_2618_closes_h2(self):
        """كان الدخول عند 2.24 بلا وقف؛ صار وقفه 2.618."""
        p = self._at(147.0)                     # تصحيح 47% ⇒ 2.24
        self.assertEqual(p.extension, 2.24)
        self.assertAlmostEqual(p.stop, 147 - 47 * 2.618)
        self.assertIsNotNone(p.stop)

    def test_the_ladder_is_two_rungs(self):
        p = self._at(150.0)                     # تصحيح 50% ⇒ 2.00
        self.assertAlmostEqual(p.stop, 150 - 50 * 2.24)        # 38
        self.assertAlmostEqual(p.hard_stop, 150 - 50 * 2.618)  # 19.1

    def test_hard_stop_is_farther_than_the_close_stop(self):
        for c in (147.0, 150.0, 165.0, 173.0):
            with self.subTest(c=c):
                p = self._at(c)
                if p.hard_stop is None:
                    continue
                self.assertLess(p.hard_stop, p.stop)
                self.assertLess(p.stop, p.entry)

    def test_hard_stop_tolerates_wicks_the_close_stop_is_meant_to_ignore(self):
        """
        وقف الإغلاق موضوعٌ ليحتمل الذيول. فلو كانت الشبكة قريبةً منه
        لضربها الذيلُ نفسه وأبطلت القاعدة. الدرجة التالية أوسع بمراحل.
        """
        p = self._at(150.0)
        close_risk = abs(p.stop - p.entry)          # 50×0.24 = 12
        hard_risk = p.risk()                        # 50×0.618 = 30.9
        self.assertGreater(hard_risk, close_risk * 2)

    def test_the_224_entry_has_no_net_and_is_refused(self):
        """
        🔴 H5 — سلّم المدرّب ينتهي عند 2.618، فالدخول من 2.24 بلا
        درجة بعد وقفه. لا تُخترَع: يُعرَض النموذج ولا يُتداول.
        """
        p = self._at(147.0)
        self.assertIsNone(p.hard_stop)
        self.assertFalse(p.protected)
        self.assertIsNone(p.risk())
        self.assertIn("لا تُؤخذ", p.render())

    def test_every_other_band_is_protected(self):
        for c, ext in ((150.0, 2.00), (165.0, 1.618), (173.0, 1.41)):
            with self.subTest(extension=ext):
                p = self._at(c)
                self.assertEqual(p.extension, ext)
                self.assertTrue(p.protected)

    def test_sell_side_net_sits_above(self):
        p = build(sw(0, 100.0, "low"), sw(5, 200.0, "high"),
                  sw(10, 150.0, "low"), "M15")
        self.assertGreater(p.hard_stop, p.stop)
        self.assertGreater(p.stop, p.entry)


class TestBuildValidation(unittest.TestCase):
    def test_points_must_alternate(self):
        with self.assertRaises(ValueError):
            build(sw(0, 200.0, "high"), sw(5, 150.0, "high"),
                  sw(10, 100.0, "low"), "M15")

    def test_points_must_be_in_time_order(self):
        with self.assertRaises(ValueError):
            build(sw(10, 200.0, "high"), sw(5, 100.0, "low"),
                  sw(12, 150.0, "high"), "M15")

    def test_zero_length_ab_leg_rejected(self):
        with self.assertRaises(ValueError):
            measure_retrace(sw(0, 100.0, "high"), sw(5, 100.0, "low"),
                            sw(10, 100.0, "high"))

    def test_a_shallow_retrace_yields_no_pattern(self):
        """«أعطاك تصحيح 35 — ما في نموذج»."""
        with self.assertRaises(PatternRejected):
            build(sw(0, 200.0, "high"), sw(5, 100.0, "low"),
                  sw(10, 135.0, "high"), "M15")


class TestInvalidation(unittest.TestCase):
    """«قبل ما يوصل لمنطقة الارتداد طلع كسر الـC — نموذج يُلغى»."""

    P = FastLightning(
        a=sw(0, 200.0, "high"), b=sw(2, 100.0, "low"), c=sw(4, 150.0, "high"),
        retrace=0.5, extension=2.00, timeframe="M15",
    )   # دخول 50 · وقف 38

    def _series(self, *rows):
        return mk("M15", *rows)

    def test_breaking_c_before_reaching_d_invalidates(self):
        s = self._series(
            *[(150, 151, 149, 150)] * 5,
            (150, 155, 149, 154),          # 5 — تجاوز C=150
        )
        self.assertEqual(self.P.invalidated_by(s), 5)

    def test_reaching_d_first_leaves_it_valid(self):
        s = self._series(
            *[(150, 150, 149, 149)] * 5,
            (149, 149, 45, 48),            # 5 — بلغ D=50
            (48, 160, 47, 158),            # 6 — كسر C بعدها: لا يُبطل
        )
        self.assertIsNone(self.P.invalidated_by(s))

    def test_a_quiet_series_is_neither(self):
        s = self._series(*[(140, 145, 135, 140)] * 6)
        self.assertIsNone(self.P.invalidated_by(s))

    def test_active_filters_out_the_invalidated(self):
        s = self._series(
            *[(150, 151, 149, 150)] * 5,
            (150, 155, 149, 154),
        )
        self.assertEqual(active(s, [self.P]), [])


class TestScan(unittest.TestCase):
    def test_swing_definition_matches_the_lesson(self):
        """«الشمعة أعلى من اللي قبلها واللي بعدها» — تعريف الدرس 9 نفسه."""
        s = mk("M15", (10, 12, 9, 11), (11, 20, 10, 19), (15, 16, 8, 9))
        self.assertTrue(any(x.kind == "high" and x.index == 1 for x in find_swings(s)))

    def test_scan_builds_only_what_the_table_accepts(self):
        s = mk(
            "M15",
            (200, 200, 195, 196),
            (196, 205, 195, 200),     # 1 — قمة 205
            (199, 199, 100, 105),
            (105, 106, 95, 100),      # 3 — قاع 95
            (100, 150, 99, 148),
            (148, 160, 147, 150),     # 5 — قمة 160
            (150, 151, 120, 125),
        )
        got = find_patterns(s, find_swings(s))
        self.assertTrue(all(0.382 <= p.retrace <= 0.85 for p in got))

    def test_scan_on_an_empty_swing_list(self):
        self.assertEqual(find_patterns(mk("M15", (1, 2, 0, 1)), []), [])

    def test_limit_keeps_the_latest(self):
        s = mk("M15", *[(100, 101, 99, 100)] * 3)
        self.assertEqual(find_patterns(s, [], limit=2), [])


class TestRender(unittest.TestCase):
    def test_render_carries_the_numbers(self):
        p = build(sw(0, 200.0, "high"), sw(5, 100.0, "low"),
                  sw(10, 150.0, "high"), "M15")
        r = p.render()
        self.assertIn("شراء", r)
        self.assertIn("دخول 50", r)
        self.assertIn("وقف إغلاق 38", r)
        self.assertIn("وقف صلب 19.1", r)


class TestLiveTrade20260916(unittest.TestCase):
    """
    ⭐⭐⭐ صفقةٌ حقيقيّة، بأرقامٍ مقروءةٍ من شاشة المدرّب نفسها.

    أرسل المستخدم (2026-09-16) لقطاتِ شاشةٍ لفيديو «ثلاث صفقات
    متناغمة»، وفيها أداةُ الفيبوناتشي مرسومةٌ على البرق السريع:

        0     ── 4,314.112      ⬅ المرساة العليا
        0.382 ── 4,303.220
        1     ── 4,285.600      ⬅ المعلَّمة C على الشارت
        ملصق التصحيح 0.479 · وملصق 2.613 حيث انتهى السعر

    وهذا أغلق **H7**: كان الشريط المفرَّغ يقول «الاهداف من سي الى
    **اي**»، والدرس يقول «إلى **نقطة الدخول**». و A على الشارت
    ≈ 4,271 — **تحت C وخارج المرسم**. فـ«اي» زلّةُ تفريغ.

    ⛔ ولا يُبنى هذا الاختبار على قراءتي للصورة وحدها: مرساه الأرقام
    الثلاثة المطبوعة على الشاشة، وهي تتقاطع — فلو أخطأتُ في واحد
    لسقط التطابق.
    """

    # الهندسة المعاد بناؤها من المرساتين + ملصق التصحيح 0.479
    C = 4285.600
    ENTRY = 4314.112          # = C + 2.24 × ضلع B→C
    LEG_BC = (ENTRY - C) / 2.24

    def _pattern(self):
        b_price = self.C + self.LEG_BC
        a_price = b_price - self.LEG_BC / 0.479
        return FastLightning(
            a=sw(0, a_price, "low"), b=sw(4, b_price, "high"),
            c=sw(8, self.C, "low"),
            retrace=0.479, extension=2.24, timeframe="M5",
        )

    def test_retrace_0479_lands_on_the_224_row(self):
        """«سي كانت 47 فهي امتدادها 224» — و0.479 تحت الحدّ 0.48."""
        self.assertEqual(extension_for(0.479), 2.24)

    def test_entry_reproduces_his_fibonacci_anchor(self):
        self.assertAlmostEqual(self._pattern().entry, self.ENTRY, places=3)

    def test_first_target_matches_his_screen_to_the_millipoint(self):
        """0.382 على شاشته = 4,303.220 — والكود يعطيها بالضبط."""
        self.assertAlmostEqual(self._pattern().targets()[0], 4303.220, places=3)

    def test_all_three_target_ratios_are_the_ones_he_drew(self):
        got = self._pattern().targets()
        self.assertEqual(len(got), 3)
        for value, seen in zip(got, (4303.220, 4299.856, 4296.492)):
            self.assertAlmostEqual(value, seen, places=3)

    def test_targets_are_measured_to_the_entry_not_to_a(self):
        """
        ⭐ جوهر H7: لو قِيست إلى A لخرجت الأهداف من نطاقه كلّيًّا.

        فـ A تحت C، والقياس إليها يصعد بالأهداف فوق الدخول — أي في
        الجهة الخاسرة.
        """
        p = self._pattern()
        self.assertLess(p.a.price, p.c.price)
        for t in p.targets():
            self.assertLess(t, p.entry)
            self.assertGreater(t, p.c.price)

    def test_his_close_stop_sits_just_above_where_price_stopped(self):
        """
        😳 ملصق الشارت **2.613** ووقفُ الإغلاق **2.618**.

        فالصفقة الرابحة بأهدافها الثلاثة مرّت على مسافة خمسةِ أجزاء
        من الألف من وقفها — وبلا شبكة أمان خلفه (**H5**).
        """
        p = self._pattern()
        self.assertFalse(p.protected)              # الدخول من 2.24
        high_reached = self.C + 2.613 * self.LEG_BC
        self.assertLess(high_reached, p.stop)
        self.assertLess(p.stop - high_reached, 0.10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
