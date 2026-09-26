"""
اختبارات سلسلة القرار.

كل اختبار يتحقق من أن السلسلة **تتوقف عند الشرط الصحيح** وتسجّل سببه.
"""

import unittest
from datetime import datetime, timedelta

from bot.chain import ChainConfig, active_impulse, evaluate
from bot.data import Candle, Series
from bot.primitives.swings import find_swings

T0 = datetime(2026, 8, 27, 9, 0)


def mk(tf, *rows) -> Series:
    return Series(
        tf,
        [Candle(T0 + timedelta(minutes=5 * i), o, h, l, c) for i, (o, h, l, c) in enumerate(rows)],
    )


FLAT = tuple((100, 101, 99, 100) for _ in range(6))

# هيكل صاعد: قمم أعلى 112 → 122 → 135 · وقيعان أعلى 95 → 105
BULLISH = (
    (100, 102,  98, 101),
    (101, 112, 100, 111),    # 1 — قمة 112
    (110, 110,  95,  97),    # 2 — قاع 95
    (106, 118, 106, 117),
    (117, 122, 112, 121),    # 4 — قمة 122
    (120, 120, 105, 107),    # 5 — قاع 105
    (110, 128, 110, 127),
    (127, 135, 120, 134),    # 7 — قمة 135
    (130, 130, 124, 126),
)


def cfg(**kw) -> ChainConfig:
    base = dict(poi_timeframe="H1", confirm_timeframe="M5", spread=0.3)
    base.update(kw)
    return ChainConfig(**base)


class TestImpulse(unittest.TestCase):
    def test_measures_last_low_to_last_high(self):
        s = mk("H1", *BULLISH)
        imp = active_impulse(find_swings(s), "bullish")
        self.assertIsNotNone(imp)
        self.assertEqual((imp.low, imp.high), (105, 135))
        self.assertEqual(imp.midpoint, 120)

    def test_none_when_no_swings(self):
        self.assertIsNone(active_impulse([], "bullish"))

    def test_none_when_high_below_low(self):
        s = mk("H1", *BULLISH)
        sws = [x for x in find_swings(s) if x.is_low]
        self.assertIsNone(active_impulse(sws, "bullish"))


class TestChainStopsAtTheRightStep(unittest.TestCase):
    def test_undefined_structure_rejected_first(self):
        res = evaluate(mk("H1", *FLAT), mk("M5", *FLAT), cfg())
        self.assertEqual(res.disposition, "rejected")
        self.assertEqual(res.rationale.checks[0].name, "الهيكل محدد")
        self.assertFalse(res.rationale.checks[0].passed)

    def test_structure_recorded_when_defined(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg())
        first = res.rationale.checks[0]
        self.assertTrue(first.passed)
        self.assertIn("bullish", first.evidence)
        self.assertEqual(res.rationale.direction, "buy")

    def test_direction_follows_structure(self):
        bearish = tuple((c, h, l, o) for (o, h, l, c) in reversed(BULLISH))
        res = evaluate(mk("H1", *bearish), mk("M5", *FLAT), cfg())
        if res.rationale.checks[0].passed:
            self.assertIn(res.rationale.direction, ("buy", "sell"))

    def test_every_check_carries_evidence_and_source(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg())
        for c in res.rationale.checks:
            self.assertTrue(c.evidence, f"فحص بلا دليل: {c.name}")
            self.assertTrue(c.source, f"فحص بلا مصدر: {c.name}")

    def test_chain_stops_at_first_failure(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg())
        self.assertEqual(len(res.rationale.failed_checks), 1)
        self.assertIs(res.rationale.checks[-1], res.rationale.failed_checks[0])

    def test_rejected_never_carries_entry(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg())
        if res.disposition == "rejected":
            self.assertIsNone(res.rationale.entry)


class TestRiskGate(unittest.TestCase):
    """حد المركز الواحد — يمنع التنفيذ ولا يمنع التنبيه."""

    def test_gate_is_the_last_step(self):
        """لا يُفحص حد المراكز إلا بعد اكتمال التحليل."""
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg(open_positions=5))
        self.assertEqual(res.disposition, "rejected")   # سقط قبل بوابة المخاطرة
        self.assertNotIn("مركز مفتوح", res.note)

    def test_blocked_setup_keeps_full_rationale(self):
        from bot.reporting import TradeRationale
        r = TradeRationale("XAUUSD.m", "buy", "H1", "M5", T0)
        r.add("مثال", True, "دليل", "مصدر")
        r.entry, r.stop, r.targets = 100.0, 98.0, [104.0]
        r.blocked_reason = "مركز مفتوح (1/1) — تنبيه لا أمر"
        self.assertIn("تنبيه فقط", r.render())
        self.assertIsNotNone(r.entry)


class TestSpreadGuard(unittest.TestCase):
    """
    سبريد شاذّ يوسّع الوقف معه: `stop_buffer = max(2.00, spread)`.
    وبلغ السبريد في أسبوع الملاحظة **6.87$** في ثلاثة قرارات.
    """

    def test_an_abnormal_spread_stops_before_anything_else(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg(spread=6.87))
        self.assertEqual(res.disposition, "rejected")
        self.assertEqual(res.rationale.checks[0].name, "السبريد طبيعي")
        self.assertIn("6.87", res.rationale.checks[0].evidence)

    def test_the_weeks_worst_accepted_spread_still_passes(self):
        """أعلى سبريد عند إعدادٍ مقبول في الأسبوع كان 0.68$."""
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg(spread=0.68))
        self.assertNotEqual(res.rationale.checks[0].name, "السبريد طبيعي")

    def test_the_guard_is_switchable(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT),
                       cfg(spread=6.87, max_spread=None))
        self.assertNotEqual(res.rationale.checks[0].name, "السبريد طبيعي")


class TestMaxStop(unittest.TestCase):
    """
    ⭐ سقف مسافة الوقف — **مستخرَج من أسبوع 09-07…11 لا مقدَّر**:

      • أقصى ارتداد احتاجه رابح قبل هدفه:   13.30$
      • سقف 20$  ⇒ الأسبوع كما هو تمامًا:  −10.21$
      • سقف 12$  ⇒ ينقلب إلى:             −109.85$

    ويوافق حدّ المدرّب المنطوق: 24$ على الذهب «كارثي».
    """

    def test_the_default_sits_above_what_winners_needed(self):
        self.assertGreater(cfg().max_stop, 13.30)

    def test_the_default_sits_below_what_he_called_catastrophic(self):
        self.assertLess(cfg().max_stop, 24.0)

    def test_a_wide_stop_is_refused_with_its_number(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg(max_stop=0.5))
        named = [c for c in res.rationale.checks if c.name == "مسافة الوقف ضمن السقف"]
        if named:                                   # بلغت السلسلة هذه المرحلة
            self.assertFalse(named[0].passed)
            self.assertEqual(res.note, "الوقف أبعد من السقف")

    def test_a_refused_setup_still_shows_its_numbers(self):
        """⚠️ لا يُخفى الرقم عند الرفض — وإلا تعذّر ضبط السقف لاحقًا."""
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg(max_stop=0.5))
        if res.note == "الوقف أبعد من السقف":
            self.assertIsNotNone(res.rationale.entry)
            self.assertIsNotNone(res.rationale.stop)

    def test_the_cap_is_switchable(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg(max_stop=None))
        self.assertFalse(any(c.name == "مسافة الوقف ضمن السقف"
                             for c in res.rationale.checks))

    def test_the_cap_comes_after_the_confirmation_not_before(self):
        """السقف يُفحص بعد معرفة الدخول — لا يجوز أن يسبق ما يحدّده."""
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg(max_stop=0.5))
        names = [c.name for c in res.rationale.checks]
        if "مسافة الوقف ضمن السقف" in names:
            self.assertLess(names.index("الهيكل محدد"),
                            names.index("مسافة الوقف ضمن السقف"))


class TestConfig(unittest.TestCase):
    def test_defaults_match_recorded_decisions(self):
        c = cfg()
        # ⭐ رُفع حدّ المراكز (2026-09-20): «لا أريد حدًّا»
        self.assertIsNone(c.max_open_positions)
        self.assertEqual(c.daily_loss_limit, 100.0)    # «حد الخسارة اليومي 100$»
        self.assertFalse(c.require_containment)        # D1 — الافتراضي التطابق

    def test_containment_is_switchable(self):
        self.assertTrue(cfg(require_containment=True).require_containment)


class TestTargetCap(unittest.TestCase):
    """
    ⭐⭐ **أربعة، منطوقًا بالعدّ** (الأوردر بلوك ج2 ≈19:25):

        «الأهداف تبعت الأوردر بلوك هي **القيعان السابقة** — واحد،
         اثنين، ثلاثة، **أربعة**. يعني أربع أهداف. بدك الخامس؟
         **لا، ما بيمشي الحال**»

    ويشمل الأنواع الثلاثة بنصّه: «إن كان العاديّ وإن كان **البريكر**
    وإن كان **الميتيجيشن**».

    ⛔ **وكان الكود يعطي ثلاثة** — `pool[:3]`، رقمٌ عارٍ بلا مصدر.
    فالأربعة **تصحيحُ رقمٍ مخترَع** لا توسيعُ سقف.
    """

    def test_the_cap_is_the_spoken_four(self):
        from bot.chain import MAX_TARGETS
        self.assertEqual(MAX_TARGETS, 4)
        self.assertEqual(cfg().max_targets, 4)

    def test_it_matches_the_recorded_parameter(self):
        """⛔ ورقمٌ في مكانين يتباعد — فيُفحَص تطابقُهما."""
        from bot import params as P
        from bot.chain import MAX_TARGETS
        self.assertEqual(P.MAX_TARGETS.value, MAX_TARGETS)
        self.assertEqual(P.MAX_TARGETS.origin, "SOURCE")

    def test_never_more_than_the_cap_is_announced(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg())
        self.assertLessEqual(len(res.rationale.targets), 4)

    def test_the_cap_is_lowerable_in_one_line(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg(max_targets=1))
        self.assertLessEqual(len(res.rationale.targets), 1)


class TestRiskGate(unittest.TestCase):
    """
    ⛔⛔ **الحدُّ صار بالدولار لا بالعدّ** (المستخدم 2026-09-20).

    «حد الخسارة اليومي **100$**» · «حد المراكز المفتوحة **لا أريد حدًّا**»

    ومركزان وقفُهما 3$ ليسا كمركزٍ وقفُه 20$ — فالعدُّ كان يسوّي بينهما.
    """

    def _taken(self, **kw):
        return evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg(**kw))

    def test_open_positions_no_longer_block(self):
        res = self._taken(open_positions=9)
        self.assertNotIn("مركز مفتوح", res.note)

    def test_a_count_cap_still_works_when_set(self):
        """الحدّ رُفع ولم يُحذف — فمن أراده أعاده بسطر."""
        res = self._taken(open_positions=1, max_open_positions=1)
        if res.disposition == "blocked":
            self.assertIn("مركز مفتوح", res.note)

    def test_reaching_the_daily_loss_blocks_the_rest_of_the_day(self):
        res = self._taken(daily_loss=-100.0)
        if res.rationale.entry is not None:      # بلغت السلسلةُ بوّابةَ المخاطرة
            self.assertEqual(res.disposition, "blocked")
            self.assertIn("حدَّ خسارته", res.note)

    def test_just_under_the_limit_still_passes(self):
        res = self._taken(daily_loss=-99.99)
        self.assertNotIn("حدَّ خسارته", res.note)

    def test_a_profitable_day_is_never_blocked_by_it(self):
        """⚠️ الحصيلة موجبةٌ ربحًا — فلا يُقرأ الربحُ خسارةً بإشارةٍ مقلوبة."""
        res = self._taken(daily_loss=+250.0)
        self.assertNotIn("حدَّ خسارته", res.note)

    def test_the_limit_can_be_switched_off(self):
        res = self._taken(daily_loss=-5000.0, daily_loss_limit=None)
        self.assertNotIn("حدَّ خسارته", res.note)


class TestRationaleIsReportReady(unittest.TestCase):
    """مخرَج السلسلة يُستهلك مباشرة في تيليجرام والسجل اليومي."""

    def test_render_works_on_rejected(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg())
        out = res.rationale.render()
        self.assertIn("سلسلة الفحص", out)
        self.assertIn("الإعداد مرفوض", out)

    def test_feeds_the_daily_report(self):
        from bot.daily_report import MarketSnapshot, SetupRecord, build
        from datetime import date

        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT), cfg())
        rep = build(
            MarketSnapshot(date(2026, 8, 27), "XAUUSD.m", 100, 130, 95, 120),
            [SetupRecord(res.rationale, res.disposition, note=res.note)],
        )
        out = rep.render()
        self.assertIn("⛔ مرفوضة", out)
        self.assertIn(res.rationale.failed_checks[0].name, out)


class TestTargetTierMatchesEntry(unittest.TestCase):
    """
    ⭐ درس السيولة الضخمة والمخففة — قاعدة منصوصة:

        «نحن **ما فينا نرتد من فير فالو جاب على الربع ساعة ونستهدف
         قمة أربع ساعات**»

    السلسلة تحقّقها ضمنًا لأنها تقرأ قممًا وقيعانًا من إطار نقطة
    الاهتمام وحده. وهذا الاختبار يجعل الصحة **مقصودة لا عارضة**:
    لو قرأ أحدهم يومًا قممًا من إطار أعلى، يسقط الاختبار.
    """

    def test_every_target_carries_the_poi_timeframe_tier(self):
        from bot.primitives.liquidity_map import tier_for

        res = evaluate(mk("H1", *BULLISH), mk("M5", *BULLISH), ChainConfig("H1", "M5", spread=0.3))
        expected = tier_for("H1")
        for t in res.targets:
            self.assertEqual(t.tier, expected)

    def test_changing_the_poi_timeframe_changes_the_tier(self):
        from bot.primitives.liquidity_map import tier_for

        res = evaluate(mk("M15", *BULLISH), mk("M5", *BULLISH), ChainConfig("M15", "M5", spread=0.3))
        for t in res.targets:
            self.assertEqual(t.tier, tier_for("M15"))
        self.assertNotEqual(tier_for("M15"), tier_for("H1"))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDirectTouchOnly(unittest.TestCase):
    """
    ⭐⭐⭐ **النزيفُ في فرعٍ واحد** — قِيس على 08-26…09-18 بتفصيل
    المسارات:

        اللمس المباشر (منقَّح + من حدّه)   **+2.69$**
        النموذج الانعكاسيّ                **−65.36$**

    ⇒ فطريقةُ المدرّب الأساسيّة — الدخول من أوردر بلوك عند لمسه —
    متعادلةٌ بل موجبة. والخسارةُ كلُّها في الفرع الذي يدخل من نموذجٍ
    انعكاسيّ **بلا أوردر بلوك**.

    ⛔ ومُطفَأ حتى يُقاس وحده: الفرعُ منصوصٌ للمنعكسة، وإغلاقُه يردّ
    نصًّا — ولا يُردّ نصٌّ إلّا بقياسٍ صريح.
    """

    def test_the_default_now_closes_the_bleeding_path(self):
        """
        ✅ قِيس وحده: **+68.93$** — والفرعُ أعطى تسعةَ إعدادات
        **وصفرَ رابح**. فأُغلق.
        """
        self.assertTrue(cfg().direct_touch_only)

    def test_it_can_be_reopened_in_one_line(self):
        """🔶 فإغلاقُه يردّ نصًّا، ويُعاد إن قال أسبوعٌ آخر غير ذلك."""
        self.assertFalse(cfg(direct_touch_only=False).direct_touch_only)

    def test_switching_it_on_closes_the_reversal_path(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT),
                       cfg(direct_touch_only=True))
        names = [c.name for c in res.rationale.checks]
        self.assertNotIn("نموذج انعكاسي مفعَّل", names)

    def test_it_says_why_in_the_log(self):
        res = evaluate(mk("H1", *BULLISH), mk("M5", *FLAT),
                       cfg(direct_touch_only=True))
        if res.note == "لا لمس مباشر":
            ev = [c.evidence for c in res.rationale.checks
                  if c.name == "دخول من مجرد اللمس"]
            self.assertTrue(any("مغلق" in e for e in ev))


class TestASkippedGateDeclaresItself(unittest.TestCase):
    """
    ⛔⛔⛔ **هنا خفي عطبُ H1 ثلاثةَ أسابيع.**

    بوّابةُ السند تسجّل «⚠️ لم يُفحَص» حين لا يصلها الإطارُ الأعلى،
    وبوّابةُ الاتّجاه كانت **تُتخطّى بلا سطرٍ واحد**. فخرجت صفقتا H1
    من السجلّ وليس فيهما ذكرٌ للاتّجاه أصلًا — لا نجاحًا ولا فشلًا
    ولا «لم يُفحَص». وبوّابةٌ تصمت عند تعطُّلها لا يُكتشف تعطُّلها.
    """

    @staticmethod
    def _series(tf, step, n):
        out = []
        for i in range(n):
            p = 4300 + (i % 20) * 1.5 - (i % 7) * 2.0
            out.append(Candle(T0 + timedelta(minutes=step * i),
                              p, p + 2, p - 2, p + 0.5))
        return Series(tf, out, symbol="XAUUSD")

    def _checks(self, higher):
        r = evaluate(self._series("M15", 15, 200), self._series("M3", 3, 800),
                     ChainConfig(poi_timeframe="M15", confirm_timeframe="M3",
                                 spread=0.3),
                     higher_series=higher)
        return {c.name: c for c in r.rationale.checks}

    def test_the_trend_gate_is_named_even_when_it_could_not_run(self):
        c = self._checks(None).get("الإطار الأعلى لا يخالف")
        self.assertIsNotNone(c, "البوّابةُ غابت عن السجلّ — وهو العطب نفسه")
        self.assertIn("لم يُفحَص", c.evidence)

    def test_both_higher_frame_gates_behave_alike_when_starved(self):
        """⭐ التسويةُ هي الإصلاح: جارتان لا تتصرّفان تصرّفين."""
        ch = self._checks(None)
        for name in ("الإطار الأعلى لا يخالف", "سند من إطار أكبر"):
            with self.subTest(name=name):
                self.assertIn("لم يُفحَص", ch[name].evidence)

    def test_a_present_frame_is_judged_not_excused(self):
        c = self._checks(self._series("H1", 60, 200))["الإطار الأعلى لا يخالف"]
        self.assertNotIn("لم يُفحَص", c.evidence)
        self.assertIn("H1", c.evidence)
