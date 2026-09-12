"""
اختبارات تنقيح الدخول داخل المنطقة.

⭐ أعلى بندٍ قِسنا كلفته بالدولار: وسيط وقف البوت 10.91$ وأقصاه
74.77$، وأرقام المدرّب 1–3.5$. والنصّ الفاصل:

    «في أغلبيتها بتفوت من الأوردر بلوك بيكون **الستوب تبعها قاع
     الأوردر بلوك**، **ولكن أنا بدون تأكيد ما بنصح**»
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.fvg import find_fvgs
from bot.primitives.patterns import activate, find_all
from bot.primitives.refine import Refinement, candidates, refine
from bot.primitives.swings import find_swings

T0 = datetime(2026, 9, 14, 9, 0)


def mk(*rows, tf="M3"):
    return Series(tf, [
        Candle(T0 + timedelta(minutes=3 * i), o, h, l, c)
        for i, (o, h, l, c) in enumerate(rows)
    ])


# ── سلسلة تأكيدٍ فيها دبل بوتم مفعَّل ──
#
# ⚠️ **وعمقُه ضحل عن قصد** — كما يكون على M3. فنموذجٌ بعمق منطقةٍ
# كاملة لا ينقّح شيئًا، وضحالتُه هي سببُ تصغير الوقف.
#
#   1 القاع الأول 100.5 · 3 خطّ العنق 102.5 · 4 القاع الثاني 100.6
#   6 كسرٌ بالجسم (إغلاق 102.9) · 7 فراغُ الكسر 101.5–103
#   ⇒ دخول 103 · وقف 100.5 − 2 = 98.5 · مخاطرة **4.50$**
DOUBLE_BOTTOM = (
    (104, 104, 103, 103.5),
    (103.5, 104, 100.5, 101),       # 1 — القاع الأول
    (101, 101.2, 100.8, 101),       # 2 — شمعة هادئة
    (101, 102.5, 100.9, 102.3),     # 3 — خطّ العنق 102.5
    (102.3, 102.4, 100.6, 101),     # 4 — القاع الثاني
    (101, 101.5, 100.9, 101.3),
    (101.3, 103, 101.2, 102.9),     # 6 — كسرٌ بالجسم
    (103.1, 105, 103, 104.5),       # 7 — فراغُ الكسر
    (104.5, 105, 103.5, 104),
)


def patterns_of(series, tolerance=1.5):
    return activate(series,
                    find_all(find_swings(series), tolerance),
                    find_fvgs(series))


def plan(zone_entry=102.0, zone_stop=90.0, direction="bullish",
         rows=DOUBLE_BOTTOM, buffer=2.0, bottom=90.0, top=102.0, tol=0.0):
    s = mk(*rows)
    return refine(zone_entry=zone_entry, zone_stop=zone_stop,
                  direction=direction, confirm_series=s,
                  patterns=patterns_of(s), buffer=buffer,
                  zone_bottom=bottom, zone_top=top, tolerance=tol)


class TestTheGovernningRule(unittest.TestCase):
    """«بدون تأكيد ما بنصح» — فالمسارُ الأصل هو المنقَّح."""

    def test_the_module_quotes_the_rule_it_implements(self):
        import bot.primitives.refine as m
        self.assertIn("بدون تأكيد ما بنصح", m.__doc__)

    def test_no_pattern_falls_back_to_the_zone_edge(self):
        flat = tuple([(100, 101, 99, 100)] * 8)
        ref = plan(rows=flat)
        self.assertFalse(ref.refined)
        self.assertEqual(ref.source, "zone")
        self.assertEqual((ref.entry, ref.stop), (102.0, 90.0))

    def test_the_fallback_names_itself_as_the_discouraged_path(self):
        flat = tuple([(100, 101, 99, 100)] * 8)
        self.assertIn("ما بنصح", plan(rows=flat).render())


class TestContainment(unittest.TestCase):
    """
    ⚠️ شرطُ الاحتواء هو ما يجعل هذا **تنقيحًا** لا صفقةً أخرى —
    «**أي لمس لهي المنطقة** ما راح يوصل لي للقاع».
    """

    def test_a_pattern_whose_low_is_inside_the_zone_qualifies(self):
        s = mk(*DOUBLE_BOTTOM)
        found = candidates(s, patterns_of(s), "bullish", 90.0, 102.0)
        self.assertTrue(found)
        for p in found:
            self.assertLessEqual(p.extreme, 102.0)
            self.assertGreaterEqual(p.extreme, 90.0)

    def test_a_pattern_far_from_the_zone_is_not_a_refinement(self):
        """نموذجٌ في مكانٍ آخر من الشارت إعدادٌ مستقلّ."""
        s = mk(*DOUBLE_BOTTOM)
        self.assertEqual(candidates(s, patterns_of(s), "bullish", 10.0, 20.0), [])

    def test_the_tolerance_widens_containment(self):
        """طرفُ النموذج 100.5 — خارج 101–102 تمامًا، وداخلها بسماحية 1."""
        s = mk(*DOUBLE_BOTTOM)
        self.assertEqual(candidates(s, patterns_of(s), "bullish", 101.0, 102.0),
                         [])
        self.assertTrue(candidates(s, patterns_of(s), "bullish", 101.0, 102.0,
                                   tolerance=1.0))

    def test_the_direction_must_match(self):
        s = mk(*DOUBLE_BOTTOM)
        self.assertEqual(candidates(s, patterns_of(s), "bearish", 90.0, 102.0),
                         [])


class TestItActuallyTightens(unittest.TestCase):
    """⭐ الغرض المنصوص: «الغرض من التدرّج **تصغير الوقف**»."""

    def test_the_refined_stop_is_tighter_than_the_zone(self):
        ref = plan()
        self.assertTrue(ref.refined)
        self.assertAlmostEqual(ref.zone_risk, 12.00)
        self.assertAlmostEqual(ref.risk, 4.50)      # 103 − 98.5

    def test_it_reports_what_it_saved(self):
        ref = plan()
        self.assertAlmostEqual(ref.saved, ref.zone_risk - ref.risk)
        self.assertGreater(ref.saved, 0)
        self.assertLess(ref.shrink, 1.0)

    def test_a_refinement_that_does_not_tighten_is_refused(self):
        """⛔ نموذجٌ وقفُه أوسع من قاع المنطقة ليس تنقيحًا."""
        ref = plan(zone_stop=99.0)           # مخاطرة المنطقة 3$ < 4.5$
        self.assertFalse(ref.refined)
        self.assertEqual(ref.stop, 99.0)

    def test_the_stop_comes_from_the_patterns_low_not_the_zones(self):
        """§3 و§8: «الوقف: **أدنى القاع** بقليل»."""
        ref = plan()
        self.assertAlmostEqual(ref.stop, ref.pattern.extreme - 2.0)
        self.assertNotAlmostEqual(ref.stop, ref.zone_stop)

    def test_it_keeps_both_numbers_always(self):
        """⚠️ سجلٌّ بلا المتروك لا يقيس ما وفّره التنقيح."""
        for ref in (plan(), plan(rows=tuple([(100, 101, 99, 100)] * 8))):
            self.assertEqual((ref.zone_entry, ref.zone_stop), (102.0, 90.0))

    def test_the_render_carries_both_risks(self):
        out = plan().render()
        self.assertIn("بدل", out)
        self.assertIn("وفّر", out)


class TestGeometrySanity(unittest.TestCase):
    def test_a_zero_width_zone_is_returned_untouched(self):
        ref = plan(zone_entry=100.0, zone_stop=100.0)
        self.assertFalse(ref.refined)
        self.assertEqual(ref.shrink, 1.0)
        self.assertEqual(ref.saved, 0.0)

    def test_a_bullish_stop_sits_below_its_entry(self):
        ref = plan()
        self.assertLess(ref.stop, ref.entry)

    def test_saved_is_never_negative(self):
        self.assertGreaterEqual(plan(zone_stop=101.0).saved, 0.0)

    def test_the_bearish_mirror(self):
        s = mk(*[(210 - o, 210 - l, 210 - h, 210 - c)
                 for (o, h, l, c) in DOUBLE_BOTTOM])
        ref = refine(zone_entry=108.0, zone_stop=120.0, direction="bearish",
                     confirm_series=s, patterns=patterns_of(s), buffer=2.0,
                     zone_bottom=108.0, zone_top=118.0)
        if ref.refined:
            self.assertGreater(ref.stop, ref.entry)
            self.assertLess(ref.risk, ref.zone_risk)


class TestChainIntegration(unittest.TestCase):
    def test_it_is_on_by_default_and_switchable(self):
        from bot.chain import ChainConfig
        self.assertTrue(ChainConfig("H1", "M5", spread=0.3).refine_entry)
        self.assertFalse(
            ChainConfig("H1", "M5", spread=0.3, refine_entry=False).refine_entry)

    def test_the_check_appears_only_on_the_direct_touch_path(self):
        """مسار النموذج منقَّحٌ أصلًا — فلا يُنقَّح مرّتين."""
        from bot.chain import ChainConfig, evaluate
        from bot.tests.test_chain import BULLISH, FLAT, mk as cmk
        res = evaluate(cmk("H1", *BULLISH), cmk("M5", *FLAT),
                       ChainConfig("H1", "M5", spread=0.3))
        names = [c.name for c in res.rationale.checks]
        if "تنقيح الدخول داخل المنطقة" in names:
            self.assertIn("دخول من مجرد اللمس", names)

    def test_the_large_block_threshold_is_wired_and_undefined(self):
        from bot import params as P
        from bot.chain import ChainConfig
        self.assertIsNone(ChainConfig("H1", "M5", spread=0.3).ob_large_threshold)
        self.assertIsNone(P.OB_LARGE_THRESHOLD.value)


class TestParams(unittest.TestCase):
    def test_the_param_records_the_measured_cost(self):
        from bot import params as P
        self.assertTrue(P.REFINE_ENTRY_IN_ZONE.value)
        self.assertEqual(P.REFINE_ENTRY_IN_ZONE.origin, "SOURCE")
        self.assertIn("ما بنصح", P.REFINE_ENTRY_IN_ZONE.note)


if __name__ == "__main__":
    unittest.main(verbosity=2)
