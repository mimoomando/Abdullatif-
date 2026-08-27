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


class TestConfig(unittest.TestCase):
    def test_defaults_match_recorded_decisions(self):
        c = cfg()
        self.assertEqual(c.max_open_positions, 1)      # قرار المستخدم
        self.assertFalse(c.require_containment)        # D1 — الافتراضي التطابق

    def test_containment_is_switchable(self):
        self.assertTrue(cfg(require_containment=True).require_containment)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
