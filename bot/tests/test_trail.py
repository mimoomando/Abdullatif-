"""
اختبارات نقل الوقف مع الأهداف.

⭐ الخطوة الأولى **منصوصة** (الأوردر بلوك ج3): «بس ضرب الهدف الأوّل،
بدك تأمّن… بترفع الستوب لوز **لفوق دخولك بدولار**، مشان إذا صار
انعكاس قوي انت **بتطلع صفر**».

⭐ وما بعدها **قرار المستخدم** (2026-09-20): «عند وصول أوّل تي بي
ينقل الوقف إلى الدخول، وعند الوصول إلى ثاني تي بي ينقل الوقف إلى
أوّل تي بي — وهكذا». ثم قال «**ابنها مثل ما قال المدرّب**» ⇒
فالأولى بالدولار.
"""

import unittest
from datetime import datetime, timedelta

from bot.replay import Bar, Setup, walk, walk_managed
from bot.trail import BREAK_EVEN_PLUS, ladder, never_looser, stop_after

T0 = datetime(2026, 9, 14, 4, 0)
TARGETS = (110.0, 120.0, 130.0, 140.0)


def bar(i, o, h, l, c):
    return Bar(T0 + timedelta(minutes=15 * i), o, h, l, c)


def setup(direction="buy", entry=100.0, stop=95.0, targets=TARGETS):
    return Setup("M15", direction, entry, stop, targets[0], T0.isoformat(),
                 1, tuple(targets))


class TestTheSpokenFirstStep(unittest.TestCase):
    """
    ⚠️⚠️ **والدولارُ ليس نقطةَ تعادل — هو فوقها.**

    وعلّتُه في قوله نفسِه: «بتطلع **صفر**». فالتعادل الحرفيّ يخرجك
    بخسارة السبريد، والدولار يغطّيها فتخرج صفرًا فعلًا.
    """

    def test_the_dollar_is_the_recorded_one(self):
        self.assertEqual(BREAK_EVEN_PLUS, 1.00)

    def test_after_the_first_target_the_stop_is_entry_plus_a_dollar(self):
        self.assertAlmostEqual(
            stop_after(100.0, 95.0, TARGETS, 1, "buy"), 101.0)

    def test_it_is_above_break_even_not_at_it(self):
        s = stop_after(100.0, 95.0, TARGETS, 1, "buy")
        self.assertGreater(s, 100.0, "الوقفُ عند الدخول يخرجك بخسارة السبريد")

    def test_selling_mirrors_it(self):
        self.assertAlmostEqual(
            stop_after(100.0, 105.0, (90.0, 80.0), 1, "sell"), 99.0)

    def test_nothing_moves_before_the_first_target(self):
        """«**بس ضرب الهدف الأوّل**، بدك تأمّن» — فلا تأمين قبله."""
        self.assertEqual(stop_after(100.0, 95.0, TARGETS, 0, "buy"), 95.0)


class TestTheUsersLadder(unittest.TestCase):
    """«وعند الوصول إلى ثاني تي بي ينقل الوقف إلى أوّل تي بي — وهكذا»."""

    def test_after_the_second_the_stop_sits_on_the_first(self):
        self.assertEqual(stop_after(100.0, 95.0, TARGETS, 2, "buy"), 110.0)

    def test_after_the_third_it_sits_on_the_second(self):
        self.assertEqual(stop_after(100.0, 95.0, TARGETS, 3, "buy"), 120.0)

    def test_after_the_fourth_it_sits_on_the_third(self):
        self.assertEqual(stop_after(100.0, 95.0, TARGETS, 4, "buy"), 130.0)

    def test_the_dollar_is_not_added_to_the_later_rungs(self):
        """
        ⛔ علّةُ الدولار تغطيةُ السبريد عند **التعادل**. وعند الهدف
        الأوّل صار الربحُ المحجوز يغطّيه — فلا يُكرَّر.
        """
        self.assertEqual(stop_after(100.0, 95.0, TARGETS, 2, "buy"), 110.0)

    def test_the_whole_ladder_reads_at_a_glance(self):
        steps = ladder(100.0, 95.0, TARGETS, "buy")
        self.assertEqual([s.stop for s in steps], [101.0, 110.0, 120.0, 130.0])
        self.assertIn("+ 1$", steps[0].render())


class TestTheStopNeverLoosens(unittest.TestCase):
    """⛔ ووقفٌ يتراجع ليس تأمينًا — هو نقضُه."""

    def test_a_buy_stop_only_rises(self):
        self.assertEqual(never_looser("buy", 110.0, 105.0), 110.0)
        self.assertEqual(never_looser("buy", 110.0, 115.0), 115.0)

    def test_a_sell_stop_only_falls(self):
        self.assertEqual(never_looser("sell", 90.0, 95.0), 90.0)
        self.assertEqual(never_looser("sell", 90.0, 85.0), 85.0)

    def test_a_target_nearer_than_entry_cannot_loosen_it(self):
        """هدفٌ أقربُ من الدخول ممكنٌ في سيولةٍ مزدحمة — ولا يُرخي الوقف."""
        odd = (110.0, 101.5)           # الثاني أقرب من الأوّل
        steps = ladder(100.0, 95.0, odd, "buy")
        self.assertGreaterEqual(steps[1].stop, steps[0].stop)


class TestWalkingWithItOnRealBars(unittest.TestCase):
    def test_a_price_that_never_reaches_entry_is_unfilled(self):
        bars = [bar(1, 105, 106.0, 104.0, 105)]      # لم يلمس 100
        self.assertEqual(walk_managed(bars, setup()).outcome, "unfilled")

    def test_it_stops_at_the_original_before_any_target(self):
        bars = [bar(1, 100, 100.5, 94.0, 95.0)]
        r = walk_managed(bars, setup())
        self.assertEqual(r.outcome, "stop")
        self.assertAlmostEqual(r.pnl, -5.0)

    def test_hitting_one_target_then_reversing_exits_a_dollar_up(self):
        """
        ⭐⭐ **وهذا هو البند كلُّه.**

        بلا تأمين: الصفقةُ تعود إلى 95 فتخسر **5$**.
        وبه: تخرج عند 101 فتربح **1$**. الفرق **6$** على صفقةٍ واحدة.
        """
        bars = [bar(1, 100, 101.0, 99.5, 100.5),      # الدخول وحده
                bar(2, 100, 111.0, 102.0, 110.0),     # بلغ الهدف الأوّل
                bar(3, 110, 110.0, 94.0, 95.0)]       # ثم انعكس عميقًا
        r = walk_managed(bars, setup())
        self.assertEqual(r.outcome, "tp1")
        self.assertAlmostEqual(r.pnl, 1.0)

        plain = walk(bars, setup())
        self.assertAlmostEqual(plain.pnl, 10.0)       # `walk` يخرج عند الهدف

    def test_two_targets_then_a_reversal_locks_the_first(self):
        bars = [bar(1, 100, 101.0, 99.5, 100.5),      # الدخول وحده
                bar(2, 100, 111.0, 102.0, 110.0),     # الهدف الأوّل ⇒ وقف 101
                bar(3, 110, 121.0, 109.0, 120.0),     # الثاني   ⇒ وقف 110
                bar(4, 120, 120.0, 100.0, 101.0)]     # انعكاسٌ عميق
        r = walk_managed(bars, setup())
        self.assertEqual(r.outcome, "tp2")
        self.assertAlmostEqual(r.pnl, 10.0)           # خرج عند 110

    def test_all_four_targets_pay_the_last(self):
        bars = [bar(1, 100, 101.0, 99.5, 100.5),          # الدخول
                bar(2, 100, 141.0, 130.5, 140.0)]         # اجتاحها كلَّها
        r = walk_managed(bars, setup())
        self.assertEqual(r.outcome, "tp4")
        self.assertAlmostEqual(r.pnl, 40.0)

    def test_one_bar_may_carry_two_targets_and_the_stop_between_them(self):
        """
        ⚠️⚠️ **ومسارُ السعر داخل الشمعة مجهول.**

        شمعةٌ قمّتُها عند الهدف الثاني (120) وقاعُها تحت الوقف المنقول
        (101) — لا يُعرف أيُّهما أوّلًا. فتُقرأ **عند الوقف المنقول**.

        ⛔ وبلا فحصٍ متكرّرٍ داخل الشمعة كان الوقفُ المنقول يُتجاوَز
        صامتًا، فيُحسب ربحًا لم يقع.
        """
        bars = [bar(1, 100, 121.0, 99.5, 120.0)]
        r = walk_managed(bars, setup())
        self.assertEqual(r.outcome, "tp1")
        self.assertAlmostEqual(r.pnl, 1.0)

    def test_the_stop_wins_when_both_are_hit_in_one_bar(self):
        """⚠️ التشاؤم مقصود — فالرقم الخارج أدنى من الواقع لا أعلى."""
        bars = [bar(1, 100, 111.0, 99.5, 110.0),
                bar(2, 110, 121.0, 100.9, 101.0)]     # الثاني والوقف معًا
        r = walk_managed(bars, setup())
        self.assertEqual(r.outcome, "tp1")
        self.assertAlmostEqual(r.pnl, 1.0)

    def test_selling_mirrors_the_whole_thing(self):
        s = setup("sell", 100.0, 105.0, (90.0, 80.0))
        bars = [bar(1, 100, 100.5, 89.0, 90.0),       # الهدف الأوّل
                bar(2, 90, 106.0, 90.0, 105.0)]       # انعكاس
        r = walk_managed(bars, s)
        self.assertEqual(r.outcome, "tp1")
        self.assertAlmostEqual(r.pnl, 1.0)

    def test_a_setup_with_one_target_still_works(self):
        s = setup(targets=(110.0,))
        bars = [bar(1, 100, 111.0, 99.5, 110.0)]
        r = walk_managed(bars, s)
        self.assertEqual(r.outcome, "tp1")
        self.assertAlmostEqual(r.pnl, 10.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
