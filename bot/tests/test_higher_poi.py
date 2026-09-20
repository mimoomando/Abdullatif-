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


# هيكلٌ هابط — **مرآةُ `BULLISH`** في `test_chain` بانعكاسٍ حول 230:
#   (o, h, l, c) ⇒ (230−o, 230−l, 230−h, 230−c)
# فقممُه أدنى (135 ⇒ 125) وقيعانُه أدنى (118 ⇒ 108 ⇒ 95).
#
# ⚠️ وأوّلُ ما كتبتُه كان هبوطًا **مستقيمًا**، فلم تتشكّل فيه قمّةٌ
#    واحدة — `find_swings` تطلب شمعةً أعلى من جارتيها. فالمرآةُ
#    أسلمُ من الارتجال.
BEARISH = (
    (130, 132, 128, 129),
    (129, 130, 118, 119),    # 1 — قاع 118
    (120, 135, 120, 133),    # 2 — قمة 135
    (124, 124, 112, 113),
    (113, 118, 108, 109),    # 4 — قاع 108
    (110, 125, 110, 123),    # 5 — قمة 125  (أدنى من 135)
    (120, 120, 102, 103),
    (103, 110,  95,  96),    # 7 — قاع 95   (أدنى من 108)
    (100, 106, 100, 104),
)


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


class TestItIsOnBecauseItCostNothing(unittest.TestCase):
    """
    ✅ **قِيس على 09-14…18 من شموع المنصّة:**

        بلا سند   7 إعدادات   −17.49$
        مع السند  7 إعدادات   −17.49$   ⇒ **+0.00$**

    ⛔ **وصفرٌ في الحصيلة لا يعني قاعدةً خاملة** — فُحص ذلك ولم يُفترَض:
    الشرطُ **يردّ 54% من المناطق** (55 من 102). فكلُّ ما كان سيردّه
    كانت بوّابةٌ لاحقة تردّه أصلًا في هذا الأسبوع.

    ⇒ مرشِّحٌ منصوصٌ لا يكلّف شيئًا — وهو ميزانُ `max_stop = 20$` نفسُه.

    🔶 **ولم يُثبت نفعًا، إنّما نفى ضررًا.**
    """

    def test_the_default_is_on(self):
        from bot.chain import ChainConfig
        cfg = ChainConfig(poi_timeframe="M15", confirm_timeframe="M3",
                          spread=0.3)
        self.assertTrue(cfg.higher_poi_required)

    def test_it_can_be_switched_off_in_one_line(self):
        """🔶 وهو أوّلُ ما يُطفأ إن ساء أسبوع — فثلاثةُ تفاصيلَ فيه تأويل."""
        from bot.chain import ChainConfig
        cfg = ChainConfig(poi_timeframe="M15", confirm_timeframe="M3",
                          spread=0.3, higher_poi_required=False)
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



class TestHigherTrendAgreement(unittest.TestCase):
    """
    ⭐⭐⭐ «إذا انت فايت **عكس الترند** رح يضربك».

    🔴 **وأسبوع 09-14 يقوله بالأرقام**، بمقارنة اتّجاه كلّ صفقةٍ بحكم
    المدرّب المسجَّل لذلك اليوم:

        09-14  قال هابط · اشترى البوت ×2   **−25.82$**
        09-15  قال صاعد · اشترى البوت ×3   **+29.76$**
        09-16  قال صاعد · باع البوت   ×2   **−21.43$**

    ⇒ وافقه فربح · خالفه مرّتين فخسر −47.25$.

    ⚠️ **والبوت لا يقرأ فيديوهاته.** فالمبنيُّ ليس «وافِق المدرّب» بل
    «وافِق قراءتك أنت للإطار الأعلى» — **وهي فرضيّةٌ أخرى تُقاس.**

    ⛔ ومُطفَأ: ثلاثةُ أيّامٍ لا تُشغّل قاعدة.
    """

    def _cfg(self, **kw):
        from bot.chain import ChainConfig
        return ChainConfig(poi_timeframe="M15", confirm_timeframe="M3",
                           spread=0.3, **kw)

    def test_the_default_is_off(self):
        self.assertFalse(self._cfg().require_higher_trend)

    def test_an_opposing_higher_trend_rejects(self):
        from bot.chain import evaluate
        from bot.tests.test_chain import BULLISH, FLAT, mk
        res = evaluate(mk("M15", *BULLISH), mk("M3", *FLAT),
                       self._cfg(require_higher_trend=True),
                       higher_series=mk("H1", *BEARISH))
        self.assertEqual(res.disposition, "rejected")
        self.assertIn("الإطار الأعلى يخالف", res.note)

    def test_an_agreeing_higher_trend_passes_the_gate(self):
        from bot.chain import evaluate
        from bot.tests.test_chain import BULLISH, FLAT, mk
        res = evaluate(mk("M15", *BULLISH), mk("M3", *FLAT),
                       self._cfg(require_higher_trend=True),
                       higher_series=mk("H1", *BULLISH))
        self.assertNotIn("الإطار الأعلى يخالف", res.note)

    def test_an_undefined_higher_trend_is_not_a_disagreement(self):
        """⚠️ **من لا ترند له لا يُذهب عكسَه** — فالعرضيّ يمرّ ويُسمّى."""
        from bot.chain import evaluate
        from bot.tests.test_chain import BULLISH, FLAT, mk
        res = evaluate(mk("M15", *BULLISH), mk("M3", *FLAT),
                       self._cfg(require_higher_trend=True),
                       higher_series=mk("H1", *FLAT))
        self.assertNotIn("الإطار الأعلى يخالف", res.note)

    def test_without_a_higher_series_nothing_changes(self):
        from bot.chain import evaluate
        from bot.tests.test_chain import BULLISH, FLAT, mk
        a = evaluate(mk("M15", *BULLISH), mk("M3", *FLAT), self._cfg())
        b = evaluate(mk("M15", *BULLISH), mk("M3", *FLAT),
                     self._cfg(require_higher_trend=True))
        self.assertEqual(a.disposition, b.disposition)

    def test_it_is_the_cheapest_gate_so_it_runs_early(self):
        """
        ⭐ سوينجاتٌ وحكمُ اتّجاه، بلا فراغاتٍ ولا أوردر بلوك. فتُوضع
        **قبل** بناء نقاط الاهتمام، فيسقط المخالفُ قبل أيّ حساب.
        """
        import pathlib
        src = pathlib.Path("bot/chain.py").read_text(encoding="utf-8")
        self.assertLess(src.index("الإطار الأعلى لا يخالف"),
                        src.index("# ── ٢. نقطة اهتمام مع الاتجاه ──"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
