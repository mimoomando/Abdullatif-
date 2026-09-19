"""
اختبارات نموذج الفراشة — الهارمونيك ٣.

⭐ **وأهمّها ليست من عندي**: الدرس نفسه مسحٌ حيٌّ على الذهب والعملات
والبيتكوين، **قَبِل فيه نسبًا ورَفَض أخرى بصوته**. فتُثبَّت تلك
الحالات كما نطق بها — هي الحكمُ، لا اختيارُ أوساطٍ مريحة.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.butterfly import (
    AB_RETRACE,
    AB_TOLERANCE,
    BC_RETRACE,
    CD_EXTENSION,
    D_EXTENSION,
    STOP_EXTENSION,
    active,
    build,
    find_patterns,
)
from bot.primitives.harmonic import PatternRejected
from bot.primitives.swings import Swing

T0 = datetime(2026, 9, 18, 10, 0)

X, A = 200.0, 100.0          # X قمة · A قاع ⇒ D فوق X ⇒ بيع
LEG = X - A


def sw(index, price, kind):
    return Swing(index, T0 + timedelta(minutes=3 * index), price, kind)


def mk(*rows, tf="H4"):
    return Series(tf, [Candle(T0 + timedelta(minutes=240 * i), o, h, l, c)
                       for i, (o, h, l, c) in enumerate(rows)], symbol="XAUUSD")


def quad(ab: float, bc: float, x_price=X, a_price=A):
    """رباعيّةٌ بنسبتَي A→B و B→C المطلوبتين. C محسوبة، و D تتبع."""
    leg = x_price - a_price
    b_price = a_price + leg * ab
    c_price = b_price - (b_price - a_price) * bc
    xk, ak = ("high", "low") if leg > 0 else ("low", "high")
    return (sw(0, x_price, xk), sw(2, a_price, ak),
            sw(4, b_price, xk), sw(6, c_price, ak))


class TestTheLessonsOwnVerdicts(unittest.TestCase):
    """⭐ ما قَبِله ورَفَضه المدرّب في مسح الدرس — حرفًا بحرف."""

    def _ab(self, ratio, bc=0.55):
        return build(*quad(ratio, bc), "H4")

    def test_069_is_refused_as_he_refused_it(self):
        """«تصحيح الموجة B هو 0.69… أقلّ نسبة هي 0.75 — فهذا مرفوض»."""
        with self.assertRaises(PatternRejected):
            self._ab(0.69)

    def test_066_is_refused_as_he_refused_it(self):
        """«عنّا X A B **66** — لا، ما بيمشي الحال»."""
        with self.assertRaises(PatternRejected):
            self._ab(0.66)

    def test_073_passes_because_he_said_it_does(self):
        """
        ⭐ «فنسبة **73** هي نسبة محقّقة بنموذج الفراشة، ما في أي مشكلة».

        وهي **دون** الحدّ المنصوص 0.75 — فلولا سماحيتُه لسقطت.
        """
        self.assertAlmostEqual(self._ab(0.73).ab_retrace, 0.73, places=3)

    def test_076_and_078_and_079_and_081_all_pass(self):
        """أربع نسبٍ قبِلها في المسح: «76 ماشي الحال» · «78 ضمن الشروط» · «79» · «81»."""
        for r in (0.76, 0.78, 0.79, 0.81):
            with self.subTest(ab=r):
                self.assertAlmostEqual(self._ab(r).ab_retrace, r, places=3)

    def test_bc_055_and_065_and_057_and_087_all_pass(self):
        """«0.55 ضمن الرينج» · «65 ضمن الشروط» · «57» · «87 — 86 أعلى شيء»."""
        for r in (0.55, 0.65, 0.57, 0.87):
            with self.subTest(bc=r):
                self.assertAlmostEqual(self._ab(0.78, r).bc_retrace, r, places=3)


class TestBoundaries(unittest.TestCase):
    """النسب مقدّسة — فالحدّ نفسه يمرّ، وما وراءه يسقط."""

    def test_the_stated_bounds_themselves_pass(self):
        for r in AB_RETRACE:
            with self.subTest(ab=r):
                build(*quad(r, 0.5), "H4")
        # ⚠️ لكلّ حدٍّ من B→C نسبةُ A→B التي تُبقي C→D داخل نطاقه —
        # انظر `test_the_three_ratios_are_coupled` أدناه.
        for r, ab in ((BC_RETRACE[0], 0.80), (BC_RETRACE[1], 0.78)):
            with self.subTest(bc=r):
                build(*quad(ab, r), "H4")

    def test_the_three_ratios_are_coupled_not_independent(self):
        """
        ⭐ **ليست ثلاثةَ شروطٍ منفصلة** — بل شرطان يقيّدان الثالث.

        لأنّ D محسوبةٌ من X→A، يصير امتداد C→D دالّةً في الاثنين:

            C→D = (1.270 − ab·(1−bc)) / (ab·bc)

        ⇒ فـ**تصحيحٌ ضحلٌ في B→C يدفع C→D فوق 2.618**. مثالًا:
        ab = 0.78 مع bc = 0.382 يعطي **2.645** — يُرفَض، ولو أنّ كلّ
        نسبةٍ منهما داخل نطاقها.

        وهذا ما يفسّر ندرةَ النموذج التي نصّ عليها، ولا يُخفَّف بحجّة
        أنّ «النسبتين سليمتان».
        """
        with self.assertRaises(PatternRejected):
            build(*quad(0.78, BC_RETRACE[0]), "H4")
        # وبرفع A→B قليلًا يعود النموذج صالحًا بالنسبة نفسها
        self.assertAlmostEqual(
            build(*quad(0.80, BC_RETRACE[0]), "H4").bc_retrace,
            BC_RETRACE[0], places=3)

    def test_the_tolerated_floor_passes_and_below_it_fails(self):
        floor = AB_RETRACE[0] - AB_TOLERANCE
        build(*quad(floor, 0.5), "H4")
        with self.assertRaises(PatternRejected):
            build(*quad(floor - 0.005, 0.5), "H4")

    def test_the_upper_bound_is_not_widened_by_the_tolerance(self):
        """
        🔴 **BF1 مثبَّت**: السماحية على الأدنى وحده.

        أثبت 0.73 (أدنى من 0.75) ورفض 0.69، ولم يعرض حالةً واحدة فوق
        0.82 في الدرس كلّه. فلا يُوسَّع السقف بلا نصّ — ولو تبيّن
        خلافه، هذا الاختبار هو ما يسقط أوّلًا.
        """
        with self.assertRaises(PatternRejected):
            build(*quad(AB_RETRACE[1] + 0.02, 0.5), "H4")

    def test_bc_above_0886_is_refused(self):
        with self.assertRaises(PatternRejected):
            build(*quad(0.78, 0.90), "H4")


class TestGeometry(unittest.TestCase):
    """⭐ الفارق عن الخفاش: D **خلف X** لا دونها."""

    P = build(*quad(0.78, 0.55), "H4")

    def test_entry_is_the_1270_projection(self):
        self.assertAlmostEqual(self.P.entry, A + LEG * D_EXTENSION, places=6)

    def test_entry_lies_beyond_x_not_short_of_it(self):
        self.assertGreater(self.P.entry, X)

    def test_stop_is_1414_and_further_than_entry(self):
        self.assertAlmostEqual(self.P.stop, A + LEG * STOP_EXTENSION, places=6)
        self.assertGreater(self.P.stop, self.P.entry)

    def test_direction_follows_x(self):
        self.assertEqual(self.P.direction, "bearish")          # X قمة
        low = build(*quad(0.78, 0.55, x_price=A, a_price=X), "H4")
        self.assertEqual(low.direction, "bullish")            # X قاع
        self.assertLess(low.entry, A)                          # D تحت X

    def test_targets_run_from_a_to_d(self):
        span = A - self.P.entry
        self.assertAlmostEqual(self.P.targets()[0], self.P.entry + span * 0.382, places=6)
        for t in self.P.targets():
            self.assertLess(t, self.P.entry)                   # بيع ⇒ الأهداف تحت

    def test_prz_is_b_to_a(self):
        lo, hi = self.P.prz()
        self.assertAlmostEqual(lo, A, places=6)
        self.assertAlmostEqual(hi, self.P.b.price, places=6)

    def test_cd_extension_is_inside_its_band(self):
        self.assertGreaterEqual(self.P.cd_extension, CD_EXTENSION[0] - 0.01)
        self.assertLessEqual(self.P.cd_extension, CD_EXTENSION[1] + 0.01)


class TestInvalidation(unittest.TestCase):
    """«بيفشل النموذج بحال **تغيّر موقع C**»."""

    P = build(*quad(0.78, 0.55), "H4")

    def _broke_c(self):
        c = self.P.c.price
        return mk(*[(c + 5, c + 6, c + 4, c + 5)] * 9,
                  (c + 5, c + 6, c - 5, c - 4))          # المؤشّر 9

    def test_breaking_c_before_reaching_d_invalidates(self):
        self.assertEqual(self.P.invalidated_by(self._broke_c()), 9)

    def test_reaching_d_first_leaves_it_valid(self):
        d, c = self.P.entry, self.P.c.price
        s = mk(*[(d - 20, d - 19, d - 21, d - 20)] * 9,
               (d - 20, d + 1, d - 21, d),                # بلغ D
               (d, d + 1, c - 5, c - 4))                  # ثم كسر C — لا يُبطل
        self.assertIsNone(self.P.invalidated_by(s))

    def test_active_filters_the_invalidated(self):
        self.assertEqual(active(self._broke_c(), [self.P]), [])


class TestFindPatterns(unittest.TestCase):
    def test_a_valid_quad_is_found(self):
        s = mk(*[(150, 151, 149, 150)] * 9)
        self.assertEqual(len(find_patterns(s, list(quad(0.78, 0.55)))), 1)

    def test_rarity_is_not_a_failure(self):
        """⚠️ «رح تشوفني إني **بدوّر كثير** لحتى للنموذج» — الصفر نتيجةٌ سليمة."""
        s = mk(*[(150, 151, 149, 150)] * 9)
        self.assertEqual(find_patterns(s, list(quad(0.50, 0.55))), [])

    def test_no_swings_no_patterns(self):
        self.assertEqual(find_patterns(mk((1, 2, 0, 1)), []), [])


class TestItIsNotTheBat(unittest.TestCase):
    """⛔ أسهل خلط: النموذجان XABCD وأرقامُهما مختلفة كلّها."""

    def test_the_two_modules_disagree_on_every_number(self):
        from bot.primitives import bat
        self.assertNotEqual(bat.D_RETRACE, D_EXTENSION)          # 0.886 ≠ 1.270
        self.assertNotEqual(bat.STOP_RETRACE, STOP_EXTENSION)    # 1.130 ≠ 1.414
        self.assertNotEqual(bat.B_RETRACE, AB_RETRACE)
        self.assertNotEqual(bat.C_RETRACE, BC_RETRACE)

    def test_the_bat_entry_stays_short_of_x_and_the_butterfly_passes_it(self):
        from bot.primitives import bat
        bat_entry = A + LEG * bat.D_RETRACE
        self.assertLess(bat_entry, X)
        self.assertGreater(build(*quad(0.78, 0.55), "H4").entry, X)


if __name__ == "__main__":
    unittest.main(verbosity=2)
