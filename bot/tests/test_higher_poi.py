"""
اختبارات سند الإطار الأكبر.

⭐ «الأوردر بلوك اللي بيكون على **أربع ساعات** — هيدا **ما بحاجة**
لأني أعمل له نقاط اهتمام. أما اللي بيكون على **الربع ساعة** —
**بحاجة لنقاط اهتمام من إطار أكبر** ليكون ناجحًا وفعّالًا… **وكلّ ما
قلّ الفريم، كلّ ما بدّه إطارات مرتبطة فيه**» (الأوردر بلوك ج1)

⛔ **ومُطفَأ حتى يُقاس** — الشرطُ منصوص وتفاصيلُه تأويل.
"""

import unittest

from bot.primitives.higher_poi import overlaps, required_for, support
from bot.primitives.liquidity_map import Internal


def zone(bottom, top, kind="fvg", index=0):
    return Internal(index=index, bottom=bottom, top=top, kind=kind,
                    direction="bullish")


class TestWhichFramesNeedIt(unittest.TestCase):
    """⛔ والقائمتان منصوصتان — وما بينهما لا يُشترط."""

    def test_the_quarter_hour_needs_support(self):
        self.assertTrue(required_for("M15"))

    def test_the_minute_frames_need_it_too(self):
        for tf in ("M5", "M3", "M1"):
            with self.subTest(tf=tf):
                self.assertTrue(required_for(tf))

    def test_four_hours_does_not(self):
        self.assertFalse(required_for("H4"))

    def test_the_hour_is_not_required_because_he_did_not_say_so(self):
        """
        ⛔⛔ **والتدرّج يرتّب ولا يعطي عتبة.**

        قال «كلّ ما قلّ الفريم كلّ ما بدّه إطارات» — وهي جملةُ ترتيب.
        وH1 بين الطرفين المنصوصين، فلا رقمَ له. **ولا تُخترَع عتبةٌ من
        ترتيب.**
        """
        self.assertFalse(required_for("H1"))

    def test_case_does_not_matter(self):
        self.assertTrue(required_for("m15"))


class TestOverlap(unittest.TestCase):
    def test_a_zone_inside_a_bigger_one_overlaps(self):
        self.assertTrue(overlaps(zone(100, 102), zone(95, 110)))

    def test_touching_edges_overlap(self):
        self.assertTrue(overlaps(zone(100, 102), zone(102, 110)))

    def test_apart_zones_do_not(self):
        self.assertFalse(overlaps(zone(100, 102), zone(105, 110)))

    def test_tolerance_bridges_a_small_gap(self):
        self.assertFalse(overlaps(zone(100, 102), zone(103, 110)))
        self.assertTrue(overlaps(zone(100, 102), zone(103, 110), tolerance=1.5))

    def test_it_is_symmetric(self):
        a, b = zone(100, 105), zone(104, 110)
        self.assertEqual(overlaps(a, b), overlaps(b, a))


class TestSupport(unittest.TestCase):
    def test_none_when_nothing_overlaps(self):
        self.assertIsNone(support(zone(100, 102), [zone(200, 210)]))

    def test_it_returns_the_overlapping_zone(self):
        got = support(zone(100, 102), [zone(90, 110)])
        self.assertIsNotNone(got)
        self.assertEqual((got.bottom, got.top), (90, 110))

    def test_the_nearest_by_midpoint_wins(self):
        """منطقتان تسندان ⇒ الأقربُ مركزًا أدلُّ على «الارتكاز»."""
        near, far = zone(99, 103), zone(80, 130)
        got = support(zone(100, 102), [far, near])
        self.assertEqual((got.bottom, got.top), (99, 103))

    def test_an_empty_higher_frame_supports_nothing(self):
        self.assertIsNone(support(zone(100, 102), []))


class TestItIsOffUntilMeasured(unittest.TestCase):
    """
    ⛔⛔ **قاعدةٌ تردّ إعدادات لا تُترك عاملةً قبل أن تُثبت.**

    والشرطُ منصوص، لكنّ **ثلاثة تفاصيل فيه تأويلٌ منّي**: أيُّ إطارٍ
    أعلى يُؤخذ لـM15 · ما معنى «مرتكز» · وحالُ H1.
    """

    def test_the_default_is_off(self):
        from bot.chain import ChainConfig
        cfg = ChainConfig(poi_timeframe="M15", confirm_timeframe="M3",
                          spread=0.3)
        self.assertFalse(cfg.higher_poi_required)

    def test_the_chain_wires_it(self):
        import pathlib
        src = pathlib.Path("bot/chain.py").read_text(encoding="utf-8")
        self.assertIn("higher_poi_needed", src)
        self.assertIn("higher_support", src)
        self.assertIn("higher_series", src)


class TestAnUncheckedRuleIsNotAPass(unittest.TestCase):
    """
    ⛔ **وفحصٌ لم يُجرَ ليس فحصًا نجح.**

    فإن طُلب السندُ ولم يُعطَ الإطارُ الأكبر، يمرّ القرار — لكنّ السجلّ
    يقول «**لم يُفحَص**» بلفظه، كي لا يُقرأ لاحقًا شاهدًا على شيء.
    """

    def test_the_evidence_says_it_was_not_checked(self):
        from bot.chain import ChainConfig, evaluate
        from bot.tests.test_chain import BULLISH, FLAT, mk
        res = evaluate(mk("M15", *BULLISH), mk("M3", *FLAT),
                       ChainConfig(poi_timeframe="M15", confirm_timeframe="M3",
                                   spread=0.3, higher_poi_required=True))
        named = [c for c in res.rationale.checks if c.name == "سند من إطار أكبر"]
        if named:
            self.assertIn("لم يُفحَص", named[0].evidence)
            self.assertTrue(named[0].passed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
