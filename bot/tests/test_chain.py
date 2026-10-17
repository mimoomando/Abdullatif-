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
    def test_the_default_measures_the_whole_wave(self):
        """
        ✅ **IM1 — قُلب الافتراضُ 2026-10-01** (قياسٌ + قرارُ المستخدم).

        وكان اسمُ هذا الاختبار `test_measures_last_low_to_last_high`
        ويثبّت **105→135** — وهو التذبذبُ الداخليّ. والموجةُ الكاملة
        **95→135**، ومنتصفُها **115** لا **120**.

        ⭐ **وفرقُ المنتصف خمسةُ دولارات** — وهو ما تُقاس عليه بوّابةُ
        الـ50%، فترفض شمعةً بـ[الدخول غالٍ] أو تقبلها.
        """
        s = mk("H1", *BULLISH)
        imp = active_impulse(find_swings(s), "bullish")
        self.assertIsNotNone(imp)
        self.assertEqual((imp.low, imp.high), (95, 135))
        self.assertEqual(imp.midpoint, 115)

    def test_the_old_span_is_still_reachable_by_name(self):
        """⚠️ ويبقى `last` مبلوغًا صراحةً — فـ`--rule impulse` يقارنهما."""
        s = mk("H1", *BULLISH)
        imp = active_impulse(find_swings(s), "bullish", "last")
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
        # ⛔ DR1 (10-17): الدالّةُ لا تعرف القرار ⇒ فتصف الفحوصَ وحدَها
        self.assertIn("رسب", out)
        self.assertEqual("rejected", res.disposition)   # ⬅ والقرارُ هنا

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


class TestTheRRCapDoesNotPunishATighterStop(unittest.TestCase):
    """
    ⛔⛔⛔ **العطبُ الذي قِيس 2026-09-26 — وأُثبت بالأرقام.**

    صفقةُ بيعٍ حقيقيّة (08-27 21:45): دخول 4613.07 · مخاطرة 10.37$ ·
    هدفٌ أعطى ‎+12.20$‎. ولمّا نجح التنقيحُ عليها وصغّر وقفَها،
    تجاوزت النسبةُ سقفَ 1:3 فصُفّيت الأهدافُ كلُّها ⇒ «لا هدف صالح»
    ⇒ **رُفض الإعدادُ كلُّه، ورُميت صفقةٌ رابحة**.

    والسعرُ لم يتحرّك. تحسّن الوقفُ وحده.
    """

    ENTRY = 4613.07
    TARGET = 4613.07 - 12.20        # بيع ⇒ الهدفُ تحت الدخول

    def _pool(self, risk, cap_risk=None):
        from bot.chain import _capped
        from bot.primitives.liquidity_map import External
        from bot.primitives.swings import Swing
        t = External(swing=Swing(0, datetime(2026, 8, 27, 21, 45),
                                 self.TARGET, "low"),
                     timeframe="M15", tier="major", strength="clean")
        return _capped(self.ENTRY, self.ENTRY + risk, [t], "bearish",
                       cap_risk=cap_risk)

    def test_the_wide_zone_stop_keeps_the_target(self):
        """1:1.18 — مقبولٌ بلا جدال."""
        self.assertEqual(len(self._pool(10.37)), 1)

    def test_the_defect_reproduces_without_the_fix(self):
        """⛔ نفسُ الهدف · وقفٌ أصغر ⇒ **يُصفّى**. وهذا هو العطب."""
        self.assertEqual(len(self._pool(4.00)), 0)

    def test_the_fix_keeps_it_when_the_cap_uses_the_zone_risk(self):
        """✅ السقفُ يُقاس على مخاطرة المنطقة ⇒ الهدفُ يبقى."""
        self.assertEqual(len(self._pool(4.00, cap_risk=10.37)), 1)

    def test_the_cap_still_excludes_a_genuinely_far_target(self):
        """⚠️ ولم يُلغَ السقف — هدفٌ بعيدٌ حقًّا ما زال يُستبعَد."""
        from bot.chain import _capped
        from bot.primitives.liquidity_map import External
        from bot.primitives.swings import Swing
        far = External(swing=Swing(0, datetime(2026, 8, 27, 21, 45),
                                   self.ENTRY - 40.0, "low"),
                       timeframe="M15", tier="major", strength="clean")
        self.assertEqual(
            _capped(self.ENTRY, self.ENTRY + 10.37, [far], "bearish",
                    cap_risk=10.37), [])

    def test_without_a_cap_risk_it_behaves_exactly_as_before(self):
        """⭐ **خُمولٌ مُثبَت** — وهذا حالُ الإعداد الحيّ اليوم."""
        for risk in (10.37, 4.00, 3.00):
            self.assertEqual(len(self._pool(risk)),
                             len(self._pool(risk, cap_risk=None)))

    def test_a_zero_or_negative_basis_falls_back_to_the_real_risk(self):
        self.assertEqual(len(self._pool(10.37, cap_risk=0.0)), 1)


class TestTheImpulseSpan(unittest.TestCase):
    """
    🔴🔴🔴 **IM1 — والكودُ كان يخالف نصًّا نملكه، لا ترجيحًا بين رأيَين.**

    فترويسةُ `active_impulse` نفسُها تنهى عن التذبذب الداخليّ، والسطرُ
    كان يأخذه. والنصّ (درس 18 ≈2:37): «التصحيح تبع هي الموجة، **من هي
    الموجة كاملة**».

    ⚠️ **ومع ذلك الافتراضُ لم يُقلب** — البوّابةُ تُسقط شمعةً بـ«الدخول
    غالٍ»، فتغييرُها يغيّر الصفقات. `--rule impulse` أوّلًا.
    """

    # موجةٌ صاعدةٌ 95 → 112، ثمّ تذبذبٌ داخليٌّ 106 → 109 في أعلاها
    WAVE = ((100, 101, 99, 100.5),
            (100.5, 101, 95, 96),          # 1 — القاعُ الحاكم 95
            (96, 110, 95.5, 109),          # 2 — اندفاع
            (109, 112, 108, 111),          # 3 — القمّة 112
            (111, 111.5, 106, 107),        # 4 — قاعٌ داخليّ 106
            (107, 109, 106.5, 108.5),      # 5 — قمّةٌ داخليّة
            (108.5, 108.8, 107, 107.5))

    def setUp(self):
        self.swings = find_swings(mk("M15", *self.WAVE))

    def test_the_default_is_the_whole_wave_now(self):
        """
        ⛔⛔ **أهمُّ اختبارٍ هنا: لا انقلابَ صامت.**

        وكان اسمُه `..._is_still_the_old_behaviour` ويثبّت `last` —
        ✅ **وقُلب 2026-10-01 بقياسٍ وبقرارِ المستخدم**، لا سهوًا:

            last        9 إعدادات · 2 هدف · 7 وقف   −22.40$
            governing   5 إعدادات · 1 هدف · 3 وقف   − 1.11$
            الفرق      −4 إعداد                    +21.29$

        ⭐ **والحارسُ أدّى دورَه**: سقط الطقمُ عند القلب، فلم يمرّ
        التغييرُ بلا إقرار. ⇒ **ويبقى قائمًا في الاتّجاه الآخر.**
        """
        from bot.chain import DEFAULT_SPAN
        self.assertEqual(DEFAULT_SPAN, "governing")
        self.assertEqual(active_impulse(self.swings, "bullish"),
                         active_impulse(self.swings, "bullish", "governing"))
        # ⛔ ولا يساوي القديمَ — وإلّا كان القلبُ بلا أثر
        self.assertNotEqual(active_impulse(self.swings, "bullish"),
                            active_impulse(self.swings, "bullish", "last"))

    def test_the_old_rule_measures_the_inner_swing(self):
        """⛔ 106→112 ومنتصفٌ 109.0 — **والموجةُ من 95**."""
        imp = active_impulse(self.swings, "bullish", "last")
        self.assertEqual((imp.low, imp.high), (106, 112))
        self.assertEqual(imp.midpoint, 109.0)

    def test_the_governing_rule_measures_the_whole_wave(self):
        """✅ 95→112 ومنتصفٌ 103.5 — **فرقُ 5.5$ في البوّابة**."""
        imp = active_impulse(self.swings, "bullish", "governing")
        self.assertEqual((imp.low, imp.high), (95, 112))
        self.assertEqual(imp.midpoint, 103.5)

    def test_the_old_rule_can_invert_the_two_ends_in_time(self):
        """
        ⛔⛔ **وهذا ليس ترجيحًا بين رأيَين**: القمّةُ فهرسُ 3 والقاعُ
        فهرسُ 4 ⇒ «موجةٌ» نهايتُها **قبل** بدايتها. **وكائنٌ كهذا ليس
        موجةً.** ويُثبَّت هنا كي لا يُقرأ الرقمُ الخارجُ منه على أنّه قياس.
        """
        lows = [s for s in self.swings if s.is_low]
        highs = [s for s in self.swings if s.is_high]
        self.assertLess(highs[-1].index, lows[-1].index)

    def test_the_governing_rule_keeps_the_ends_in_order(self):
        """✅ والوضعُ الجديد يشترط الترتيبَ الزمنيّ صراحةً."""
        imp = active_impulse(self.swings, "bullish", "governing")
        lo = next(s for s in self.swings if s.is_low and s.price == imp.low)
        hi = next(s for s in self.swings if s.is_high and s.price == imp.high)
        self.assertLess(lo.index, hi.index)

    def test_no_high_after_the_governing_low_gives_no_wave(self):
        """⛔ ولا تُخترع موجةٌ حين لا توجد — `None` لا تقديرٌ."""
        rows = ((100, 105, 99, 104),
                (104, 105, 103, 104),
                (104, 104.5, 95, 96))       # القاعُ الحاكم أخيرًا
        sw = find_swings(mk("M15", *rows))
        self.assertIsNone(active_impulse(sw, "bullish", "governing"))

    def test_bearish_mirrors_the_rule(self):
        rows = ((100, 101, 99, 100),
                (100, 112, 99.5, 111),      # القمّةُ الحاكمة 112
                (111, 111.5, 100, 101),
                (101, 102, 95, 96),         # الأدنى بعدها 95
                (96, 97, 95.5, 96.5))
        sw = find_swings(mk("M15", *rows))
        imp = active_impulse(sw, "bearish", "governing")
        self.assertEqual((imp.low, imp.high), (95, 112))

    def test_an_unknown_span_is_refused_loudly(self):
        with self.assertRaises(ValueError):
            active_impulse(self.swings, "bullish", "whole")

    def test_the_ledger_marks_it_derived_and_names_the_lesson(self):
        from bot import params as P
        # ✅ صار `SOURCE` يوم 10-01: القيمةُ نفسُها صارت ما ينصّ عليه
        #    الدرسُ، بعد أن كانت اشتقاقي.
        self.assertEqual(P.IMPULSE_SPAN_RULE.origin, "SOURCE")
        self.assertIn("lesson-18", P.IMPULSE_SPAN_RULE.lesson + P.IMPULSE_SPAN_RULE.note)


class TestOB3TheConsumedZoneSwitch(unittest.TestCase):
    """
    🔴 **OB3 — المنطقةُ المستهلَكة · بثّ 2026-10-03.**

    «صار له ماتيجيشن هون صار له بروبورشن هون **اجباري بده ينكسر**» ·
    «… اخر مرحله البروبولشن بلوك … **مش راح يكون بقى عننا دخول**»

    ⛔⛔ **وأوّلُ ما يثبّته هذا الطقم تصحيحٌ**: كان مكتوبًا في وثيقة
    المشروع [وعندنا الوحدةُ كاملةً **ولا تُستدعى**] — **و`trace_all`
    مستدعاةٌ في `read_frame` منذ بناء البثّ ٣، والميّتةُ تُسقط فعلًا.**
    ⇒ فالثغرةُ أضيقُ ممّا كُتب: **ما بلغ البروبلشن ولم يُكسَر بعدُ**.

    ⚠️ **ويُفحَص المُسقِطُ وحدَه**: تُحقَن دوراتٌ مصنوعة، فما يُقاس هنا
    هو **قرارُ الإسقاط** لا كشفُ المراحل — وذاك له طقمُه.
    """

    def _view(self, mode, cycles_spec):
        """
        يبني `FrameView` بدوراتٍ محقونة.

        و`cycles_spec` قائمةُ `(dead, propulsion, mitigation)` منطقيّة.
        """
        from unittest import mock
        from bot import chain as C
        from bot.primitives.ob_lifecycle import DerivedBlock, Lifecycle
        from bot.tests.test_ob_lifecycle import ob

        blocks = [ob(index=i) for i in (1, 2, 3)]

        def derived(parent, stage):
            return DerivedBlock(parent_index=parent, stage=stage, index=parent,
                                time=T0, direction="bullish",
                                top=102.0, bottom=98.0)

        cycles = []
        for b, (dead, prop, mit) in zip(blocks, cycles_spec):
            cycles.append(Lifecycle(
                parent=b,
                mitigation=derived(b.index, "mitigation") if mit else None,
                propulsion=derived(b.index, "propulsion") if prop else None,
                dead_at=99 if dead else None,
            ))

        series = mk("M15", *FLAT)
        cfg = ChainConfig("M15", "M3", 0.2, ob_consumed_entry=mode)
        with mock.patch.object(C, "update_states", return_value=blocks), \
             mock.patch.object(C, "trace_all", return_value=cycles):
            return C.read_frame(series, find_swings(series), "bullish", cfg)

    # ⬇️ ميّتة · بلغت البروبلشن ولم تمت · ملموسةٌ فقط
    SPEC = [(True, True, True), (False, True, True), (False, False, True)]

    def test_off_drops_only_the_dead_one(self):
        """✅ **وهذا هو السلوكُ القائم** — ويثبته الطقم لا الذاكرة."""
        view = self._view("off", self.SPEC)
        self.assertEqual([b.index for b in view.blocks], [2, 3])
        self.assertEqual(view.dead, 1)

    def test_propulsion_also_drops_the_spent_but_living_zone(self):
        """⭐ **وهذه هي الثغرةُ بعينها** — حيّةٌ ومستهلَكة."""
        view = self._view("propulsion", self.SPEC)
        self.assertEqual([b.index for b in view.blocks], [3])
        self.assertEqual(view.dead, 2)

    def test_mitigated_drops_everything_touched(self):
        view = self._view("mitigated", self.SPEC)
        self.assertEqual(view.blocks, [])
        self.assertEqual(view.dead, 3)

    def test_the_three_modes_are_ordered_by_strictness(self):
        """
        ⭐ **ولا يُفترض الترتيب — يُقاس**: كلُّ وضعٍ يُسقط ما يُسقطه
        الأرخى منه وزيادة. فلو انقلب الترتيبُ يومًا صاح هذا.
        """
        kept = {m: {b.index for b in self._view(m, self.SPEC).blocks}
                for m in ("off", "propulsion", "mitigated")}
        self.assertTrue(kept["mitigated"] <= kept["propulsion"] <= kept["off"])

    def test_the_dropped_reason_follows_the_mode(self):
        """
        ⛔ **وهو درسُ LB1**: كان سطرُ السجلّ يقول [منطقة **ميّتة**]
        مكتوبةً باليد — **وتصير كاذبةً بمجرّد قلب المفتاح**. ⇒ فالسببُ
        يُحمَل مع العرض.
        """
        self.assertEqual(self._view("off", self.SPEC).dropped_why, "ميّتة")
        self.assertIn("البروبلشن",
                      self._view("propulsion", self.SPEC).dropped_why)
        self.assertIn("ملموسة",
                      self._view("mitigated", self.SPEC).dropped_why)

    def test_an_unknown_mode_is_refused_not_ignored(self):
        """⚠️ **وقيمةٌ مجهولةٌ تصيح ولا تمرّ صامتةً** — عرفُ المشروع."""
        with self.assertRaises(ValueError):
            self._view("yes", self.SPEC)

    def test_the_live_default_is_off(self):
        """⛔ **ولم يُقلب شيء** — الوصلُ خلف مفتاحٍ مطفأ حتّى يُقاس."""
        self.assertEqual(ChainConfig("M15", "M3", 0.2).ob_consumed_entry, "off")


class TestBK1ReachesTheDecision(unittest.TestCase):
    """
    ⛔⛔ **BK1 — وأوّلُ ما يُفحَص أنّ المفتاحَ يبلغ موضعَه.**

    ⚠️ **وهذا هو صنفُ العطب الذي تكرّر في هذا المشروع أربع مرّات**:
    [بندٌ معلَنٌ لا يعمل، ويصمت عند تعطُّله]. فمفتاحٌ في `ChainConfig`
    لا يصل `update_states` **يقرأ القياسُ عمودَيه متطابقين فيُحكَم
    [لا أثر]** — والحقُّ أنّه لم يُجرَّب. ⇒ **فالوصلُ يُقاس لا يُفترض.**
    """

    def _spy(self, require):
        from unittest import mock
        from bot import chain as C
        series = mk("M15", *FLAT)
        cfg = ChainConfig("M15", "M3", 0.2, breaker_requires_gap=require)
        with mock.patch.object(C, "update_states",
                               side_effect=C.update_states) as spy:
            C.read_frame(series, find_swings(series), "bullish", cfg)
        return spy.call_args

    def test_the_switch_is_passed_through(self):
        for want in (False, True):
            with self.subTest(require=want):
                self.assertIs(self._spy(want).kwargs["require_break_gap"],
                              want)

    def test_the_gaps_are_passed_too(self):
        """
        ⛔⛔ **وشرطٌ بلا مادّته يرفض كلَّ شيءٍ بصمت** — فالفراغاتُ
        تُمرَّر **في الحالتين**، والمفتاحُ وحدَه هو ما يتغيّر.
        ⚠️ **والسلسلةُ هنا مسطَّحةٌ بلا فراغٍ واحد** ⇒ فهي تُثبّت أنّ
        القائمةَ الفارغةَ تمرّ ولا تصيح — وهو العطبُ الذي وقع في ساعته.
        """
        for want in (False, True):
            with self.subTest(require=want):
                passed = self._spy(want).kwargs["fvgs"]
                self.assertIsNotNone(passed)
                self.assertIsInstance(passed, list)

    def test_the_live_default_keeps_the_condition_off(self):
        """
        ⛔ **ولم يُقلب حرف** — والقيمةُ `False` **تخالف النصّ**، وهي
        إقرارٌ بأنّ القلب تغييرُ سلوكٍ لم يُقَس لا حكمٌ على القاعدة.
        """
        self.assertIs(ChainConfig("M15", "M3", 0.2).breaker_requires_gap,
                      False)

    def test_the_role_switch_is_passed_through(self):
        """
        ⛔⛔ **BK2 — والوصلُ يُقاس لا يُفترض**، كـBK1.

        ⚠️ **وكان هذا المُختبِرُ يفحص ثلاثةَ أوضاع** إلى 10-15، وثالثُها
        `flip_no_touch` **يحمل جوابين لسؤالين** ⇒ **فقُسِّم المفتاحُ
        محورين**، وصار القلبُ على `breaker_role` وحدَه ومسارُ الدخول
        على `breaker_entry`. ⭐ **وهو درسُ هذا المُختبِر نفسِه مطبَّقًا
        على المفتاح: مفتاحٌ واحدٌ لا يحمل سؤالين.**
        """
        from unittest import mock
        from bot import chain as C
        for role, want in (("off", False), ("flip", True)):
            with self.subTest(role=role):
                series = mk("M15", *FLAT)
                cfg = ChainConfig("M15", "M3", 0.2, breaker_role=role)
                with mock.patch.object(C, "update_states",
                                       side_effect=C.update_states) as spy:
                    C.read_frame(series, find_swings(series), "bullish", cfg)
                self.assertIs(spy.call_args.kwargs["flip_breaker"], want)

    def test_an_unknown_role_is_refused_not_ignored(self):
        """⚠️ **وقيمةٌ مجهولةٌ تصيح ولا تمرّ صامتةً** — عرفُ المشروع."""
        from bot import chain as C
        series = mk("M15", *FLAT)
        with self.assertRaises(ValueError):
            C.read_frame(series, find_swings(series), "bullish",
                         ChainConfig("M15", "M3", 0.2, breaker_role="yes"))

    def test_the_live_default_keeps_the_original_role(self):
        """⛔ **ولم يُقلب حرف** — والقيمةُ تخالف النصّ، وهي إقرار."""
        self.assertEqual(ChainConfig("M15", "M3", 0.2).breaker_role, "off")

    def test_bk3_the_entry_axis_reaches_the_gate(self):
        """
        ⛔⛔⛔ **BK3** — «فمجرد ما السعر يوصل له انا هون باخذ نموذج
        انعكاسي على الربع ساعه» · «ليه لازم ناخذ تاكيد انعكاس لحتى
        ما ناخذ ستوب» ⇒ **فالدخولُ عند البريكر ليس من مجرّد اللمس.**

        ⚠️ **ويُقرأ نصُّ `evaluate`** لأنّ الوضعَ يحذف مرشَّحًا لا
        يغيّر رقمًا ⇒ فلا يظهر في مخرَجٍ إلّا بسلسلةٍ فيها بريكرٌ
        بجهة الهيكل. **ووجودُ الشرط هو ما يُحرَس هنا.**
        """
        import inspect
        from bot import chain as C
        src = inspect.getsource(C.evaluate)
        self.assertIn('cfg.breaker_entry == "pattern"', src)
        self.assertIn('ob.state == "breaker"', src)

    def test_the_two_axes_are_independent(self):
        """
        ⭐⭐⭐ **وهذا جوهرُ القسمة**: محورُ الاتّجاه لا يمسّ مسارَ
        الدخول، ومحورُ المسار لا يمسّ الاتّجاه. **فالخلايا أربعٌ
        مبلوغةٌ كلُّها**، ولا خليّةَ تحمل جوابين مُقترنين.

        ⇒ **ويُقاس لا يُفترض**: القلبُ يُمرَّر من `breaker_role`
        وحدَه، **ولا يتغيّر بتغيُّر `breaker_entry`.**
        """
        from unittest import mock
        from bot import chain as C
        seen = {}
        for role in ("off", "flip"):
            for entry in ("touch", "pattern"):
                series = mk("M15", *FLAT)
                cfg = ChainConfig("M15", "M3", 0.2,
                                  breaker_role=role, breaker_entry=entry)
                with mock.patch.object(C, "update_states",
                                       side_effect=C.update_states) as spy:
                    C.read_frame(series, find_swings(series), "bullish", cfg)
                seen[(role, entry)] = spy.call_args.kwargs["flip_breaker"]
        self.assertEqual(seen, {("off", "touch"): False,
                                ("off", "pattern"): False,
                                ("flip", "touch"): True,
                                ("flip", "pattern"): True})

    def test_an_unknown_entry_mode_is_refused_not_ignored(self):
        """⚠️ **وقيمةٌ مجهولةٌ تصيح ولا تمرّ صامتةً** — عرفُ المشروع."""
        from bot import chain as C
        series = mk("M15", *FLAT)
        with self.assertRaises(ValueError):
            C.read_frame(series, find_swings(series), "bullish",
                         ChainConfig("M15", "M3", 0.2, breaker_entry="no"))

    def test_the_live_default_keeps_the_touch_path(self):
        """
        ⛔ **ولم يُقلب حرف** — و`touch` تخالف النصّ، وهي إقرارٌ بأنّ
        القلب تغييرُ سلوكٍ لم يُقَس.
        """
        self.assertEqual(ChainConfig("M15", "M3", 0.2).breaker_entry,
                         "touch")

    def test_the_prescribed_entry_path_exists_and_is_only_gated(self):
        """
        ⛔⛔⛔ **وهذا المُختبِرُ وُلد من خطأٍ في وثيقة المشروع.**

        كُتب 10-14: [والدَّينُ الحقيقيُّ الذي يكشفه BK3: مسارُ الدخول
        المنصوص **غيرُ مبنيٍّ أصلًا**]. **وهو مبنيّ** —
        `patterns.entry_plan` يدخل عند **إعادة اختبار فراغ كسر خطّ
        العنق** ويضع الوقفَ عند **طرف النموذج**، وهو النصُّ حرفًا:
        «عند هذا الفراغ كان في عندك نقطه دخول وين ستوبك ادنى هذا
        القاع».

        ⇒ **والذي يمنعه بوّابةٌ لا غياب**: `direct_touch_only`.
        ⭐ **وهو صنفُ [حكمٌ من غيابٍ بلا تتبُّع المسار] ثالثةً** —
        بعد MB1 (09-30) وOB3 (10-12). **فيُحرَس كي لا يُكتب رابعةً.**
        """
        from bot.primitives.patterns import entry_plan
        import inspect
        from bot import chain as C

        # ⬇️ المسارُ موجودٌ ويعمل — لا يُفترض وجودُه بل يُستدعى
        #    ⚠️ ويُفحَص **بالبادئة** لا بالسطر كاملًا: النداءُ صار
        #       متعدّدَ الأسطر يوم بُني CF1، **والشكلُ ليس الدعوى.**
        src = inspect.getsource(C.evaluate)
        self.assertIn("entry_plan(pat, cfg.stop_buffer", src)
        self.assertIn("elif cfg.direct_touch_only:", src)

        # ⬇️ والدخولُ من الفراغ والوقفُ من طرف النموذج — مقيسٌ
        made = inspect.signature(entry_plan)
        self.assertEqual(list(made.parameters)[:2], ["pattern", "spread"])
        self.assertIn("فراغ", inspect.getdoc(entry_plan) or "")

    def test_breaker_is_the_only_state_the_live_path_still_admits(self):
        """
        ⛔⛔⛔ **BK2 — ويُثبَّت هنا كي لا يُنسى**: السلسلةُ تُسقط
        `failed` و`mitigated` وتُمرّر `fresh` و`breaker`. ⇒ **فتشديدُ
        BK1 يعمل بتحويل بريكرٍ إلى `failed`** — وهو الطريقُ الوحيد.
        ⚠️ **ومن أضاف حالةً أو نقل البوّابةَ يُسقط هذا.**
        """
        import inspect
        from typing import get_args
        from bot import chain as C
        from bot.primitives.order_block import State
        self.assertEqual(set(get_args(State)),
                         {"fresh", "mitigated", "failed", "breaker"})
        src = inspect.getsource(C.evaluate)
        self.assertIn('ob.state in ("failed", "mitigated")', src)
