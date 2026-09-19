"""
اختبارات نموذج الخفاش — الهارمونيك ٢.

⛔ «**النسب بالهارمونيك مقدّسة — ما في مزح**». رفض المدرّب نموذجًا
لأن C جاءت 0.996 بدل 0.99، فتُثبَّت هنا **حدود النطاقات** لا أوساطها.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.bat import (
    BD_EXTENSION,
    B_RETRACE,
    C_RETRACE,
    D_RETRACE,
    STOP_RETRACE,
    active,
    build,
    find_patterns,
)
from bot.primitives.harmonic import PatternRejected
from bot.primitives.swings import Swing

T0 = datetime(2026, 9, 11, 10, 0)

X, A = 200.0, 100.0          # X قمة · A قاع ⇒ بيع (شكل M)
LEG = X - A


def sw(index, price, kind):
    return Swing(index, T0 + timedelta(minutes=3 * index), price, kind)


def mk(*rows, tf="M3"):
    return Series(tf, [
        Candle(T0 + timedelta(minutes=3 * i), o, h, l, c)
        for i, (o, h, l, c) in enumerate(rows)
    ])


def bat(b_ratio=0.50, c_ratio=0.70):
    """يبني خفاشًا من نسبتين — والباقي محسوب."""
    b = A + LEG * b_ratio
    c = b + (A - b) * c_ratio
    return build(sw(0, X, "high"), sw(2, A, "low"),
                 sw(4, b, "high"), sw(6, c, "low"), "M3")


class TestRatios(unittest.TestCase):
    """أربعة شروط، كلها مُلزمة."""

    def test_b_band_boundaries_pass(self):
        """
        ⚠️ كل حدٍّ مع C موافقة له — الشروط الأربعة **يقيّد بعضها
        بعضًا**، فلا تُختبَر نسبةٌ بمعزل عن أخواتها.
        """
        for br, cr in ((0.382, 0.90), (0.45, 0.80), (0.58, 0.60)):
            with self.subTest(b=br):
                self.assertAlmostEqual(bat(br, cr).b_retrace, br, places=6)

    def test_b_below_382_is_refused(self):
        with self.assertRaises(PatternRejected):
            bat(b_ratio=0.30)

    def test_b_above_58_is_refused(self):
        """«إذا طلعت فوق 58 يُلغى»."""
        with self.assertRaises(PatternRejected):
            bat(b_ratio=0.62)

    def test_c_band_boundaries_pass(self):
        for br, cr in ((0.58, 0.382), (0.50, 0.50), (0.50, 0.90), (0.382, 0.99)):
            with self.subTest(c=cr):
                self.assertAlmostEqual(bat(br, cr).c_retrace, cr, places=6)

    def test_the_four_conditions_constrain_each_other(self):
        """
        ⭐ B سليمة و C سليمة **ولا نموذج**: امتداد B→D يخرج عن نطاقه.

        وهذا ليس عيبًا بل دقّة النموذج — أربع نسب تتقاطع، ولذلك
        «وين ما برمت باليوم ممكن يعطيك أربع خمس نماذج» لا مئة.
        """
        p = bat(0.58, 0.60)                     # تمرّ
        self.assertAlmostEqual(p.b_retrace, 0.58, places=6)
        with self.assertRaises(PatternRejected):
            bat(0.382, 0.70)                    # B و C سليمتان · BD = 2.885

    def test_c_below_382_is_refused(self):
        with self.assertRaises(PatternRejected):
            bat(c_ratio=0.30)

    def test_the_996_example_he_refused(self):
        """
        ⭐ رفضه بنفسه: «هي أعلى من 0.99 — لازم الماكس تبعها أكثر شيء
        0.99». جزءٌ من المئة يُسقط النموذج.
        """
        with self.assertRaises(PatternRejected):
            bat(c_ratio=0.996)

    def test_bd_extension_out_of_range_is_refused(self):
        """تصحيح C ضحل جدًّا ⇒ امتداد B→D يتجاوز 2.618."""
        with self.assertRaises(PatternRejected):
            bat(c_ratio=0.40)

    def test_every_accepted_pattern_satisfies_all_four(self):
        p = bat()
        self.assertTrue(B_RETRACE[0] <= p.b_retrace <= B_RETRACE[1])
        self.assertTrue(C_RETRACE[0] <= p.c_retrace <= C_RETRACE[1])
        self.assertTrue(BD_EXTENSION[0] - 0.02 <= p.bd_extension <= BD_EXTENSION[1] + 0.02)

    def test_constants_match_the_lesson(self):
        self.assertEqual(B_RETRACE, (0.382, 0.58))
        self.assertEqual(C_RETRACE, (0.382, 0.99))
        self.assertAlmostEqual(D_RETRACE, 0.886)
        self.assertAlmostEqual(STOP_RETRACE, 1.130)


class TestGeometry(unittest.TestCase):
    def test_entry_is_886_of_xa(self):
        """«نقطة الدخول عنّا 0.886 — لا بتزيد ولا بتنقص»."""
        self.assertAlmostEqual(bat().entry, A + LEG * 0.886)

    def test_stop_sits_beyond_x_not_beyond_d(self):
        p = bat()
        self.assertAlmostEqual(p.stop, A + LEG * 1.130)
        self.assertGreater(p.stop, X)            # خلف X

    def test_direction_follows_x(self):
        self.assertEqual(bat().direction, "bearish")

    def test_stop_is_on_the_losing_side(self):
        p = bat()
        self.assertGreater(p.stop, p.entry)      # بيع ⇒ الوقف فوق
        self.assertAlmostEqual(p.risk, abs(p.stop - p.entry))

    def test_bullish_mirror(self):
        """X قاع ⇒ شراء (شكل W)."""
        x, a = 100.0, 200.0
        leg = x - a
        b = a + leg * 0.5
        c = b + (a - b) * 0.7
        p = build(sw(0, x, "low"), sw(2, a, "high"),
                  sw(4, b, "low"), sw(6, c, "high"), "M3")
        self.assertEqual(p.direction, "bullish")
        self.assertLess(p.stop, p.entry)
        self.assertTrue(all(t > p.entry for t in p.targets()))


class TestTargets(unittest.TestCase):
    """
    ⭐ **من A إلى D** — لا من C. وهذا أسهل ما يُخلَط بالبرق السريع.
    """

    def test_targets_are_measured_from_a(self):
        p = bat()
        span = A - p.entry
        for r, t in zip((0.382, 0.5, 0.618), p.targets()):
            self.assertAlmostEqual(t, p.entry + span * r)

    def test_targets_from_a_are_wider_than_from_c(self):
        """A أبعد من C ⇒ أهداف أوسع. والسريعة «مسموحة لا مفضَّلة»."""
        p = bat()
        for main, fast in zip(p.targets(), p.fast_targets()):
            self.assertGreater(abs(main - p.entry), abs(fast - p.entry))

    def test_targets_lie_between_entry_and_a(self):
        p = bat()
        for t in p.targets():
            self.assertLess(t, p.entry)
            self.assertGreater(t, A)

    def test_fast_target_is_opt_in(self):
        p = bat()
        self.assertEqual(len(p.targets()), 3)
        self.assertEqual(len(p.targets(include_fast=True)), 4)


class TestThePublishedCards(unittest.TestCase):
    """
    ⭐ **ثلاث بطاقاتٍ من وصف درس الخفاش** (2026-09-20).

    وهي كبطاقات البرق السريع: «نسب الأهداف» و«منطقة PRZ» **متطابقتان
    حرفًا بحرف** مع نظيرتيهما — فالنسبتان مشتركتان بين النموذجين،
    وهو ما يفعله الكود أصلًا (`bat.py` يستوردهما ولا يعرّفهما).

    والثالثة «جدول نسب نموذج BAT» تؤكّد النسب الخمس.
    """

    def test_the_bat_card_confirms_all_five_numbers(self):
        """
        من البطاقة نصًّا:

            تصحيح B من الضلع X–A      0.382 – 0.58
            تصحيح C من الضلع A–B      0.382 – 0.99
            امتداد D من الضلع B–C     1.618 – 2.618
            امتداد D من X · الدخول    0.886
            امتداد D من X · SL        1.130
        """
        self.assertEqual(B_RETRACE, (0.382, 0.58))
        self.assertEqual(C_RETRACE, (0.382, 0.99))
        self.assertEqual(BD_EXTENSION, (1.618, 2.618))
        self.assertAlmostEqual(D_RETRACE, 0.886)
        self.assertAlmostEqual(STOP_RETRACE, 1.130)

    def test_the_card_gives_no_tolerance_so_d1_stays_open(self):
        """
        ⚠️ **ولا سماحيةَ في البطاقة.** تقول «0.886» مجرّدةً.

        فـ🔴 **D1 يبقى مفتوحًا**، و`D_TOLERANCE` يبقى **مقبضَنا نحن**
        لا رقمَه — كما هو موسومٌ أصلًا. وهذا الاختبار يمنع أن يُنسَب
        إليه يومًا.
        """
        import pathlib
        src = pathlib.Path("bot/primitives/bat.py").read_text(encoding="utf-8")
        block = src.split("D_TOLERANCE")[0][-400:]
        self.assertIn("D1", block,
                      "D_TOLERANCE لم يعد موسومًا بأنه مقبضُنا لا رقمُه")


class TestPRZ(unittest.TestCase):
    """«الـPRZ بيتاخذ من B إلى A» — سياقٌ لا مَدخَل."""

    def test_prz_is_the_127_to_1618_band_of_the_b_to_a_leg(self):
        """
        ⭐ **كان المدى الخام B→A، فصار نطاقًا محسوبًا** (2026-09-20).

        بطاقتُه المنشورة «منطقة PRZ» لقطةٌ لإعدادات أداة الفيبوناتشي
        عنده، والمؤشَّر فيها أربعةٌ لا غير: **0 · 1 · 1.27 · 1.618**.
        وقولُه يعطي المرساتين: «الـPRZ بيتاخذ **من B إلى A**».

        🔶 والقراءة مرجَّحة لا منصوصة — **H3 ضُيِّق لا أُغلق.**
        """
        from bot.primitives.harmonic import prz_from
        p = bat()
        self.assertEqual(p.prz(), prz_from(A, p.b.price))

    def test_the_raw_b_to_a_range_is_no_longer_what_prz_returns(self):
        """⛔ ولو عاد المدى الخام صامتًا، هذا أوّل ما يكشفه."""
        p = bat()
        raw = (min(p.b.price, A), max(p.b.price, A))
        self.assertNotEqual(p.prz(), raw)

    def test_entering_at_prz_would_widen_the_stop(self):
        """
        ⭐ تحذيره بعدد: «تفوت على 4416 وستوبك على 4440 — **كارثي**».
        فالدخول من PRZ يوسّع المخاطرة عن الدخول من D.
        """
        p = bat()
        lo, hi = p.prz()
        risk_from_prz = abs(p.stop - hi)
        self.assertGreater(risk_from_prz, p.risk)


class TestInvalidation(unittest.TestCase):
    """«بيفشل النموذج لما بيتغيّر عندي القاع تبع C»."""

    def _p(self):
        return bat()

    def test_breaking_c_before_d_invalidates(self):
        p = self._p()
        s = mk(*[(120, 121, 119, 120)] * 7,
               (120, 121, 110, 112))          # 7 — نزل تحت C=115
        self.assertEqual(p.invalidated_by(s), 7)

    def test_reaching_d_first_keeps_it_valid(self):
        p = self._p()
        s = mk(*[(120, 121, 119, 120)] * 7,
               (120, 190, 119, 189),          # 7 — بلغ D=188.6
               (189, 190, 100, 105))          # 8 — كسر C بعدها: لا يُبطل
        self.assertIsNone(p.invalidated_by(s))

    def test_a_quiet_series_is_neither(self):
        p = self._p()
        self.assertIsNone(p.invalidated_by(mk(*[(120, 125, 118, 121)] * 8)))

    def test_active_filters_the_invalidated(self):
        p = self._p()
        s = mk(*[(120, 121, 119, 120)] * 7, (120, 121, 110, 112))
        self.assertEqual(active(s, [p]), [])


class TestBuildValidation(unittest.TestCase):
    def test_points_must_alternate(self):
        with self.assertRaises(ValueError):
            build(sw(0, X, "high"), sw(2, A, "low"),
                  sw(4, 150.0, "low"), sw(6, 115.0, "low"), "M3")

    def test_points_must_be_in_order(self):
        with self.assertRaises(ValueError):
            build(sw(6, X, "high"), sw(2, A, "low"),
                  sw(4, 150.0, "high"), sw(8, 115.0, "low"), "M3")

    def test_zero_length_leg_rejected(self):
        with self.assertRaises(ValueError):
            build(sw(0, 100.0, "high"), sw(2, 100.0, "low"),
                  sw(4, 100.0, "high"), sw(6, 100.0, "low"), "M3")


class TestScan(unittest.TestCase):
    def test_scan_returns_only_valid_patterns(self):
        s = mk(*[(120, 121, 119, 120)] * 8)
        for p in find_patterns(s, []):
            self.assertTrue(B_RETRACE[0] <= p.b_retrace <= B_RETRACE[1])

    def test_scan_with_no_swings(self):
        self.assertEqual(find_patterns(mk((1, 2, 0, 1)), []), [])


class TestRender(unittest.TestCase):
    def test_render_carries_the_ratios(self):
        r = bat().render()
        self.assertIn("خفاش", r)
        self.assertIn("بيع", r)
        self.assertIn("دخول 188.6", r)
        self.assertIn("وقف 213", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
