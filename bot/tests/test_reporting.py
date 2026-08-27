"""اختبارات طبقة الشرح — لماذا دخل، وماذا حدث."""

import unittest
from datetime import datetime, timedelta

from bot.reporting import TradeJournal, TradeRationale, full_report

T0 = datetime(2026, 8, 26, 14, 0)


def rationale(direction="buy") -> TradeRationale:
    r = TradeRationale(
        symbol="XAUUSD.m",
        direction=direction,
        poi_timeframe="H1",
        confirm_timeframe="M5",
        detected_at=T0,
    )
    r.add("الهيكل صاعد", True, "قمم أعلى 4380→4392 وقيعان أعلى 4351→4362", "الدرس 9")
    r.add("سيولة مسحوبة", True, "كُسح القاع 4351 ثم أُغلق فوقه عند 4358", "أشكال السيولة")
    r.add("فراغ سعري صاعد", True, "low[3]=4366.4 > high[1]=4364.1 ⇒ المنطقة 4364.1–4366.4", "الدرس 5")
    r.add("تحت بوابة الـ50%", True, "منتصف الموجة 4371.5 والفراغ عند 4365.2", "الدرس 14")
    r.add("نموذج انعكاسي على M5", True, "دبل بوتم 4362.1 و 4362.4 وكسر عنق 4368.0", "ترابط الفريمات")
    r.entry = 4365.2
    r.stop = 4361.0
    r.stop_reason = "أدنى قاع النموذج بقليل — وخارج تجمّع السيولة"
    r.targets = [4373.6, 4382.0]
    r.target_reason = "قمم سابقة — سيولة خارجية"
    return r


class TestRationale(unittest.TestCase):
    def test_accepted_when_all_checks_pass(self):
        r = rationale()
        self.assertTrue(r.accepted)
        self.assertEqual(r.failed_checks, [])

    def test_rejected_when_any_check_fails(self):
        r = rationale()
        r.add("الفراغ فوق الـ50%", False, "الفراغ 4380 والمنتصف 4371.5", "الدرس 14")
        self.assertFalse(r.accepted)
        self.assertEqual(len(r.failed_checks), 1)

    def test_risk_and_rr(self):
        r = rationale()
        self.assertAlmostEqual(r.risk, 4.2)
        self.assertAlmostEqual(r.rr_of(4373.6), 2.0)

    def test_render_includes_evidence_and_source(self):
        out = rationale().render()
        self.assertIn("low[3]=4366.4 > high[1]=4364.1", out)
        self.assertIn("الدرس 5", out)
        self.assertIn("يُنقل الوقف لنقطة الدخول", out)

    def test_rejected_render_states_failure(self):
        r = rationale()
        r.add("كسر بزخم", False, "شمعة واحدة فقط بلا فراغ", "ترابط الفريمات")
        out = r.render()
        self.assertIn("الإعداد مرفوض", out)
        self.assertIn("❌", out)

    def test_blocked_setup_is_notification_only(self):
        r = rationale()
        r.blocked_reason = "مركز مفتوح على H4 — حد المراكز = 1"
        self.assertIn("تنبيه فقط", r.render())


class TestJournal(unittest.TestCase):
    def make(self, direction="buy") -> TradeJournal:
        r = rationale(direction)
        return TradeJournal(rationale=r, opened_at=T0, entry=r.entry)

    def test_tracks_excursions(self):
        j = self.make()
        j.observe(T0 + timedelta(minutes=5), 4368.0)
        j.observe(T0 + timedelta(minutes=10), 4363.0)   # أسوأ
        j.observe(T0 + timedelta(minutes=15), 4374.0)   # أفضل
        self.assertAlmostEqual(j.mfe, 8.8)
        self.assertAlmostEqual(j.mae, 2.2)

    def test_result_and_r_multiple_on_win(self):
        j = self.make()
        j.observe(T0 + timedelta(minutes=20), 4373.6, "الهدف الأول")
        j.close(T0 + timedelta(minutes=25), 4373.6, "tp")
        self.assertAlmostEqual(j.result, 8.4)
        self.assertAlmostEqual(j.r_multiple, 2.0)
        self.assertEqual(j.duration_minutes, 25)

    def test_sell_direction_inverts_sign(self):
        j = self.make("sell")
        j.close(T0 + timedelta(minutes=30), 4360.0, "tp")
        self.assertAlmostEqual(j.result, 5.2)   # 4365.2 − 4360.0

    def test_open_trade_has_no_result(self):
        j = self.make()
        j.observe(T0 + timedelta(minutes=5), 4368.0)
        self.assertIsNone(j.result)
        self.assertIn("مفتوحة", j.render())

    def test_lesson_when_trade_reached_profit_then_stopped(self):
        """أهم ملاحظة: بلغت الهدف تقريبًا ثم ضُربت."""
        j = self.make()
        j.observe(T0 + timedelta(minutes=10), 4372.0)   # +6.8 = 1.6R
        j.close(T0 + timedelta(minutes=40), 4361.0, "sl")
        out = j.render()
        self.assertIn("قبل أن تُضرب", out)
        self.assertIn("الخروج كان متاحًا", out)

    def test_lesson_when_price_neared_stop_then_won(self):
        j = self.make()
        j.observe(T0 + timedelta(minutes=8), 4361.3)    # اقترب جدًا من 4361
        j.close(T0 + timedelta(minutes=50), 4373.6, "tp")
        self.assertIn("اقترب السعر من الوقف", j.render())

    def test_events_are_timestamped_in_order(self):
        j = self.make()
        j.observe(T0 + timedelta(minutes=5), 4367.0, "اختراق العنق")
        j.observe(T0 + timedelta(minutes=12), 4373.6, "الهدف الأول")
        j.close(T0 + timedelta(minutes=30), 4382.0, "tp")
        labels = [e.label for e in j.events]
        self.assertEqual(labels[:2], ["اختراق العنق", "الهدف الأول"])
        self.assertIn("إغلاق", labels[-1])


class TestFullReport(unittest.TestCase):
    def test_report_has_both_halves(self):
        j = TradeJournal(rationale=rationale(), opened_at=T0, entry=4365.2)
        j.observe(T0 + timedelta(minutes=10), 4373.6, "الهدف الأول", "نُقل الوقف لنقطة الدخول")
        j.close(T0 + timedelta(minutes=45), 4382.0, "tp")
        out = full_report(j)
        self.assertIn("سلسلة الفحص", out)      # لماذا دخل
        self.assertIn("سجل الصفقة", out)       # ماذا حدث
        self.assertIn("نُقل الوقف لنقطة الدخول", out)


class TestTargetLimit(unittest.TestCase):
    """درس ترابط الفريمات: «واحد على ثلاثة يكون ماكسيموم»."""

    def test_warns_on_target_beyond_max_rr(self):
        r = rationale()
        r.targets = [4373.6, 4382.0]        # 1:2 و 1:4
        out = r.render()
        self.assertIn("يتجاوز الحد 1:3", out)

    def test_no_warning_within_limit(self):
        r = rationale()
        r.targets = [4373.6, 4377.8]        # 1:2 و 1:3 بالضبط
        self.assertNotIn("يتجاوز الحد", r.render())

class TestSessionGap(unittest.TestCase):
    """
    ⭐ «ما تنيّم صفقة… ما بتعرف على شو بيفتح السوق» (وايكوف/د3).

    المستخدم اختار إبقاءها مفتوحة. فالفجوة تُقاس بدل أن يُجادَل فيها.
    """

    def _j(self, direction="buy"):
        r = TradeRationale("XAUUSD.m", direction, "H1", "M5", T0)
        r.entry, r.stop = 4365.0, 4360.0
        return TradeJournal(rationale=r, opened_at=T0, entry=4365.0)

    def test_a_trade_that_never_slept(self):
        j = self._j()
        self.assertFalse(j.slept)
        self.assertEqual(j.gap_effect, 0.0)

    def test_gap_against_a_buy_is_unfavourable(self):
        j = self._j("buy")
        g = j.note_session_break(T0, 4370.0, T0 + timedelta(hours=8), 4366.0)
        self.assertTrue(j.slept)
        self.assertFalse(g.favourable)
        self.assertAlmostEqual(g.gap, -4.0)
        self.assertAlmostEqual(j.gap_effect, -4.0)

    def test_gap_against_a_sell_is_upward(self):
        """الفجوة الصاعدة تضرّ البيع — الاتجاه يقرّر لا الإشارة."""
        j = self._j("sell")
        g = j.note_session_break(T0, 4360.0, T0 + timedelta(hours=8), 4364.0)
        self.assertFalse(g.favourable)
        self.assertAlmostEqual(j.gap_effect, -4.0)

    def test_favourable_gap_is_recorded_as_such(self):
        j = self._j("buy")
        g = j.note_session_break(T0, 4366.0, T0 + timedelta(hours=8), 4372.0)
        self.assertTrue(g.favourable)
        self.assertAlmostEqual(j.gap_effect, 6.0)

    def test_gap_counts_toward_mae(self):
        """الفجوة حركة سعر وقعت على المركز — لا تُخفى من الأقصى."""
        j = self._j("buy")
        j.observe(T0, 4366.0)
        j.note_session_break(T0, 4366.0, T0 + timedelta(hours=8), 4358.0)
        self.assertAlmostEqual(j.mae, 7.0)

    def test_multiple_nights_accumulate(self):
        j = self._j("buy")
        j.note_session_break(T0, 4370.0, T0 + timedelta(hours=8), 4366.0)
        j.note_session_break(T0 + timedelta(days=1), 4366.0,
                             T0 + timedelta(days=1, hours=8), 4369.0)
        self.assertEqual(len(j.session_gaps), 2)
        self.assertAlmostEqual(j.gap_effect, -1.0)

    def test_render_names_the_direction_of_harm(self):
        j = self._j("buy")
        g = j.note_session_break(T0, 4370.0, T0 + timedelta(hours=8), 4366.0)
        self.assertIn("نامت عبر الإغلاق", g.render())
        self.assertIn("ضدّها", g.render())

if __name__ == "__main__":
    unittest.main(verbosity=2)
