"""
اختبارات اختبار الخطّ — «هيدا مش دبل بتم».

⭐ الحالة التي أراني إيّاها (البثّ ٣ ≈20:05): نموذجٌ يبدو دبل بوتم على
الشموع، فلمّا قُلب الشارت إلى **خطّ** صار «**قاعًا واحدًا**» — لأن
القاع الثاني كان **ذيلًا** لا إغلاقًا.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.line_chart import check, rejected, survivors
from bot.primitives.patterns import find_all
from bot.primitives.swings import find_swings

T0 = datetime(2026, 9, 14, 9, 0)


def mk(*rows, tf="M15"):
    return Series(tf, [
        Candle(T0 + timedelta(minutes=15 * i), o, h, l, c)
        for i, (o, h, l, c) in enumerate(rows)
    ])


# ── حالته بالضبط: قاعان متساويان **بالذيول** وغير متساويين بالإغلاق ──
#
#   الشمعة 1: أدنى 100.0  · إغلاق 104.0
#   الشمعة 3: أدنى 100.2  · إغلاق 100.5     ⬅ أدنى بكثير على الخطّ
#
# على الشموع: 100.0 و100.2 ⇒ دبل بوتم بسماحية 1.5
# على الخطّ : 104.0 و100.5 ⇒ فارق 3.5 — «هيدا مش دبل بتم»
WICK_ONLY = (
    (106, 106, 105, 105.5),
    (105.5, 105.6, 100.0, 104.0),   # 1 — القاع الأول: ذيلٌ طويل · إغلاق 104
    (104, 106, 103.5, 105.5),       # 2 — القمّة الفاصلة
    (105.5, 105.7, 100.2, 100.5),   # 3 — القاع الثاني: إغلاق 100.5
    (100.5, 103, 100.4, 102.5),
    (102.5, 104, 102, 103.5),
)

# ── ونموذجٌ سليم: القاعان متساويان بالذيل **وبالإغلاق** ──
REAL = (
    (106, 106, 105, 105.5),
    (105.5, 105.6, 100.0, 100.3),   # 1 — قاع 100.0 · إغلاق 100.3
    (100.3, 106, 100.2, 105.5),     # 2 — قمّة
    (105.5, 105.7, 100.1, 100.4),   # 3 — قاع 100.1 · إغلاق 100.4
    (100.4, 103, 100.3, 102.5),
    (102.5, 104, 102, 103.5),
)


def patterns(rows, tol=1.5):
    s = mk(*rows)
    return s, find_all(find_swings(s), tol)


class TestTheCaseHeShowedMe(unittest.TestCase):
    """
    ⭐ «بروح على الربع ساعة… أنا هون **ما عندي دبل بوتم**… **هيدا مش
    دبل بتم** — شوفوا ع الشموع، **هيدا قاع واحد**»
    """

    def test_the_candles_do_show_a_double_bottom(self):
        """⚠️ الاختبار بلا هذا لا معنى له: لا بدّ أن يراه الكود أوّلًا."""
        _, found = patterns(WICK_ONLY)
        self.assertTrue(any(p.kind == "double_bottom" for p in found))

    def test_the_line_refuses_it(self):
        s, found = patterns(WICK_ONLY)
        dbl = [p for p in found if p.kind == "double_bottom"][0]
        r = check(s, dbl, 1.5)
        self.assertFalse(r.ok)

    def test_the_reason_names_the_closes(self):
        s, found = patterns(WICK_ONLY)
        dbl = [p for p in found if p.kind == "double_bottom"][0]
        self.assertIn("الإغلاق", check(s, dbl, 1.5).reason)

    def test_a_genuine_double_bottom_survives(self):
        s, found = patterns(REAL)
        dbl = [p for p in found if p.kind == "double_bottom"]
        self.assertTrue(dbl)
        self.assertTrue(check(s, dbl[0], 1.5).ok)

    def test_survivors_keeps_the_real_and_drops_the_wick_made(self):
        s1, f1 = patterns(WICK_ONLY)
        s2, f2 = patterns(REAL)
        self.assertEqual(
            [p for p in survivors(s1, f1, 1.5) if p.kind == "double_bottom"], [])
        self.assertTrue(
            [p for p in survivors(s2, f2, 1.5) if p.kind == "double_bottom"])


class TestItIsAVetoNotAReplacement(unittest.TestCase):
    """
    ⛔ قرار المستخدم 2026-09-12: **(أ) اعتراض**.

    فالنموذج يُكتشَف بالذيول كما هو — والمناطق تُرسم بالذيول وذلك
    **مقيسٌ من شاشته** (C9) — ثم يُعرَض على الخطّ.
    """

    def test_detection_still_runs_on_wicks(self):
        import bot.primitives.line_chart as m
        with open(m.__file__, encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("def find_", src)       # لا كشفَ هنا
        self.assertIn("اعتراضٌ لا استبدال", src)

    def test_it_only_ever_removes_never_adds(self):
        s, found = patterns(WICK_ONLY)
        kept = survivors(s, found, 1.5)
        self.assertLessEqual(len(kept), len(found))
        for p in kept:
            self.assertIn(p, found)

    def test_the_veto_is_switchable_in_the_chain(self):
        from bot.chain import ChainConfig
        self.assertTrue(ChainConfig("H1", "M5", spread=0.3).line_chart_veto)
        self.assertFalse(
            ChainConfig("H1", "M5", spread=0.3,
                        line_chart_veto=False).line_chart_veto)


class TestTheTwoConditions(unittest.TestCase):
    def test_a_pivot_that_stops_being_a_pivot_is_refused(self):
        """«هيدا **قاع واحد**» — طرفٌ لم يبقَ طرفًا."""
        # الإغلاقات تنزل بانتظام: 105.5 · 104 · 103 · 102 · 101
        # فالشمعة 1 قاعٌ بالذيل، ولا قاعَ لها على الخطّ.
        rows = (
            (106, 106, 105, 105.5),
            (105.5, 105.6, 100.0, 104.0),
            (104, 106, 102.9, 103.0),
            (103, 105.7, 100.2, 102.0),
            (102, 103, 100.4, 101.0),
            (101, 104, 100.9, 103.5),
        )
        s, found = patterns(rows)
        dbl = [x for x in found if x.kind == "double_bottom"]
        self.assertTrue(dbl)
        for p in dbl:
            r = check(s, p, 1.5)
            self.assertFalse(r.ok)
            self.assertIn("قاع واحد", r.reason)

    def test_equal_closes_within_tolerance_pass(self):
        s, found = patterns(REAL)
        for p in [x for x in found if x.kind == "double_bottom"]:
            self.assertTrue(check(s, p, 1.5).ok)

    def test_a_tighter_tolerance_refuses_more(self):
        s, found = patterns(REAL)
        dbl = [p for p in found if p.kind == "double_bottom"][0]
        self.assertTrue(check(s, dbl, 1.5).ok)
        self.assertFalse(check(s, dbl, 0.01).ok)


class TestBearishMirror(unittest.TestCase):
    def test_a_wick_made_double_top_is_refused(self):
        rows = tuple((210 - o, 210 - l, 210 - h, 210 - c)
                     for (o, h, l, c) in WICK_ONLY)
        s, found = patterns(rows)
        tops = [p for p in found if p.kind == "double_top"]
        self.assertTrue(tops)
        for p in tops:
            self.assertFalse(check(s, p, 1.5).ok)


class TestReporting(unittest.TestCase):
    """
    ⚠️ العدد نفسه إشارة: إن رُدّ كلُّ شيء فالسماحية واسعة، وإن لم
    يُرَدّ شيءٌ قطّ فالاختبار لا يعمل.
    """

    def test_rejected_returns_the_pattern_with_its_reason(self):
        s, found = patterns(WICK_ONLY)
        out = rejected(s, found, 1.5)
        self.assertTrue(out)
        for p, why in out:
            self.assertTrue(why.strip())

    def test_nothing_rejected_when_all_are_genuine(self):
        s, found = patterns(REAL)
        self.assertEqual(
            [x for x in rejected(s, found, 1.5) if x[0].kind == "double_bottom"],
            [])


class TestEdges(unittest.TestCase):
    def test_an_empty_pattern_list_is_fine(self):
        self.assertEqual(survivors(mk((1, 2, 0, 1)), [], 1.5), [])

    def test_a_pivot_at_the_series_edge_cannot_be_confirmed(self):
        """طرفٌ على حافّة السلسلة لا جارَ له — فلا يُثبَت أنه طرف."""
        s, found = patterns(REAL)
        if found:
            tiny = Series("M15", list(s)[:2])
            self.assertFalse(check(tiny, found[0], 1.5).ok)

    def test_the_check_is_falsy_when_it_fails(self):
        s, found = patterns(WICK_ONLY)
        dbl = [p for p in found if p.kind == "double_bottom"][0]
        self.assertFalse(bool(check(s, dbl, 1.5)))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestThePlateauReachesTheVeto(unittest.TestCase):
    """
    ⚠️⚠️ **موضعُ SW1 الثاني — ووصلُه شرطٌ لصحّة قياس SW1 نفسِه.**

    فلو بقي الفيتو صارمًا وحده، لزاد المفتاحُ السوينجات **وأكل الفيتو
    الزيادة** ⇒ فيُقرأ «لا أثر» والعلّةُ في الفيتو لا في القاعدة.
    **وهو صنفُ الخطأ الذي وقع اليوم مرّتين**: عطبٌ واحدٌ في موضعين ولم
    يُربَط بينهما.
    """

    # إغلاقان متساويان متجاوران عند 1 و2
    CLOSES = [105.0, 100.0, 100.0, 104.0, 99.0]

    def test_strict_drops_both_equal_closes(self):
        from bot.primitives.line_chart import _is_local
        self.assertFalse(_is_local(self.CLOSES, 1, True, 1, "strict"))
        self.assertFalse(_is_local(self.CLOSES, 2, True, 1, "strict"))

    def test_first_keeps_the_earlier_one_only(self):
        from bot.primitives.line_chart import _is_local
        self.assertTrue(_is_local(self.CLOSES, 1, True, 1, "first"))
        self.assertFalse(_is_local(self.CLOSES, 2, True, 1, "first"))

    def test_the_default_is_still_strict(self):
        """⛔⛔ لا انقلابَ صامت — هنا أيضًا."""
        from bot.primitives.line_chart import DEFAULT_PLATEAU, _is_local
        self.assertEqual(DEFAULT_PLATEAU, "strict")
        self.assertEqual(_is_local(self.CLOSES, 1, True),
                         _is_local(self.CLOSES, 1, True, 1, "strict"))

    def test_highs_mirror_the_rule(self):
        from bot.primitives.line_chart import _is_local
        highs = [95.0, 100.0, 100.0, 96.0, 101.0]
        self.assertFalse(_is_local(highs, 1, False, 1, "strict"))
        self.assertTrue(_is_local(highs, 1, False, 1, "first"))

    def test_the_chain_passes_its_switch_down(self):
        """⭐ وإلّا كان الوصلُ في الوحدة ولم يبلغ السلسلة."""
        import inspect
        from bot import chain
        src = inspect.getsource(chain._patterns_on_line)
        self.assertIn("cfg.swing_plateau", src)
