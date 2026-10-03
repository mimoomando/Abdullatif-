"""
اختبارات إعادة التشغيل.

⛔ الحدّ الأول كما في الحلقة: **لا أمر يُرسَل** — يُقرأ ملفٌّ ويُحسَب.
⚠️ والثاني خاصٌّ بهذه الوحدة: **التشاؤم مقصود**. إعادةُ تشغيلٍ تجمّل
النتيجة أسوأ من لا شيء، لأنها تُثبِّت معاملًا على ربحٍ لم يقع.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from bot.replay import (
    GAP_MINUTES,
    Bar,
    Setup,
    coverage,
    net,
    read_journal,
    realized_pnl,
    rebuild,
    render,
    replay,
    setups_from,
    stop_demand,
    survival,
    tally,
    walk,
    walk_managed,
)

T0 = datetime(2026, 9, 7, 4, 0)


def bar(i, o, h, l, c):
    return Bar(T0 + timedelta(minutes=15 * i), o, h, l, c)


def row(i, **kw):
    d = dict(poi_tf="M15", candle_time=(T0 + timedelta(minutes=15 * i)).isoformat(),
             candle=dict(o=100.0, h=102.0, l=98.0, c=101.0),
             disposition="rejected", direction="buy",
             entry=None, stop=None, targets=[])
    d.update(kw)
    return d


def taken(i, entry=100.0, stop=95.0, target=110.0, **kw):
    return row(i, disposition="taken", entry=entry, stop=stop, targets=[target], **kw)


def setup(entry=100.0, stop=95.0, target=110.0, direction="buy", n=1, at=0):
    return Setup("M15", direction, entry, stop, target,
                 (T0 + timedelta(minutes=15 * at)).isoformat(), n)


class TestDailyRealizedPnl(unittest.TestCase):
    """
    ⛔ **مصدرُ حدّ الخسارة اليوميّ** (المستخدم 2026-09-20: «100$»).

    وفي وضع الورق لا مراكزَ حقيقيّة تُقرأ — فالمصدر قراراتُ البوت
    نفسِها مصحَّحةً على مسار السعر الذي يحمله السجلّ.
    """

    def test_a_day_with_nothing_is_zero(self):
        self.assertEqual(realized_pnl([], T0.date()), 0.0)

    def test_a_loser_is_negative(self):
        rows = [taken(0, entry=100.0, stop=95.0, target=110.0),
                row(1, candle=dict(o=100.0, h=100.5, l=94.0, c=95.0))]
        self.assertLess(realized_pnl(rows, T0.date()), 0.0)

    def test_a_winner_is_positive(self):
        """⚠️ والإشارة تُفحص — فحدٌّ يقرأ الربحَ خسارةً يوقف يومًا رابحًا."""
        rows = [taken(0, entry=100.0, stop=95.0, target=110.0),
                row(1, candle=dict(o=100.0, h=111.0, l=99.5, c=110.5))]
        self.assertGreater(realized_pnl(rows, T0.date()), 0.0)

    def test_an_unresolved_setup_counts_as_nothing(self):
        """
        ⛔⛔ **وما زال مفتوحًا لا يُحسب.** فالحدُّ يقيس ما وقع لا ما قد
        يقع — وإلّا أوقف اليومَ إعدادٌ لم يُحسَم، فينقلب رابحًا بعد ساعة.
        """
        rows = [taken(0, entry=100.0, stop=95.0, target=110.0),
                row(1, candle=dict(o=100.0, h=100.6, l=99.4, c=100.0))]
        self.assertEqual(realized_pnl(rows, T0.date()), 0.0)

    def test_another_day_is_not_counted(self):
        """العدّاد يصفّر عند تدوير اليوم — وإلّا تراكم الحدُّ أبدًا."""
        rows = [taken(0, entry=100.0, stop=95.0, target=110.0),
                row(1, candle=dict(o=100.0, h=100.5, l=94.0, c=95.0))]
        self.assertEqual(realized_pnl(rows, (T0 + timedelta(days=1)).date()), 0.0)

    def test_it_reads_the_candle_date_not_the_writing_time(self):
        rows = [taken(0, logged_at="2099-01-01T00:00:00"),
                row(1, candle=dict(o=100.0, h=100.5, l=94.0, c=95.0))]
        self.assertLess(realized_pnl(rows, T0.date()), 0.0)


class TestNoOrders(unittest.TestCase):
    def test_the_module_calls_no_execution_function(self):
        import bot.replay as m
        with open(m.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("order_send", "order_check", "positions_close", "send_order("):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, src)


class TestRebuild(unittest.TestCase):
    """⭐ المسار يأتي من السجلّ نفسه — كلُّ قرارٍ يحمل شمعته."""

    def test_it_reads_the_price_path_out_of_the_decisions(self):
        bars = rebuild([row(0), row(1), row(2)], "M15")
        self.assertEqual(len(bars), 3)
        self.assertEqual(bars[0].time, T0)

    def test_the_same_candle_seen_twice_is_one_candle(self):
        """القرار يتكرّر على الشمعة نفسها — وهي شمعةٌ واحدة لا اثنتان."""
        self.assertEqual(len(rebuild([row(0), row(0), row(0)], "M15")), 1)

    def test_other_timeframes_are_not_mixed_in(self):
        self.assertEqual(len(rebuild([row(0), row(1, poi_tf="H1")], "M15")), 1)

    def test_it_comes_back_sorted(self):
        bars = rebuild([row(2), row(0), row(1)], "M15")
        self.assertEqual([b.time for b in bars], sorted(b.time for b in bars))

    def test_a_malformed_candle_is_skipped_not_fatal(self):
        bad = row(1); bad["candle"] = {"o": 1.0}
        self.assertEqual(len(rebuild([row(0), bad], "M15")), 1)

    def test_a_malformed_time_is_skipped_not_fatal(self):
        self.assertEqual(len(rebuild([row(0), row(1, candle_time="لا وقت")], "M15")), 1)


class TestCoverage(unittest.TestCase):
    """⚠️ لا تُقرأ نتيجةٌ فوق مسارٍ مثقوب — فالثقوب تُعدّ وتُعلَن."""

    def test_the_weekend_shows_up_as_a_gap(self):
        bars = [bar(0, 100, 102, 98, 101),
                Bar(T0 + timedelta(days=2), 100, 102, 98, 101)]
        cov = coverage(bars, "M15")
        self.assertEqual(len(cov.gaps), 1)
        self.assertEqual(cov.gaps[0][2], 2 * 24 * 60)

    def test_a_continuous_run_has_no_gaps(self):
        cov = coverage([bar(i, 100, 102, 98, 101) for i in range(8)], "M15")
        self.assertEqual(cov.gaps, [])
        self.assertEqual(cov.bars, 8)

    def test_an_empty_series_says_so_instead_of_crashing(self):
        self.assertIn("لا شموع", coverage([], "M15").render())

    def test_the_threshold_is_the_stated_one(self):
        bars = [bar(0, 100, 102, 98, 101),
                Bar(T0 + timedelta(minutes=GAP_MINUTES + 1), 100, 102, 98, 101)]
        self.assertEqual(len(coverage(bars, "M15").gaps), 1)
        bars = [bar(0, 100, 102, 98, 101),
                Bar(T0 + timedelta(minutes=GAP_MINUTES), 100, 102, 98, 101)]
        self.assertEqual(coverage(bars, "M15").gaps, [])


class TestDistinctSetups(unittest.TestCase):
    """
    ⭐ ستّون قرارًا مقبولًا في أسبوع الملاحظة كانت **عشرين إعدادًا**.
    والخلط بينهما يضاعف الحصيلة واحدًا وثلاثين ضعفًا.
    """

    def test_the_same_setup_across_candles_is_one_setup(self):
        s = setups_from([taken(0), taken(1), taken(2)])
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0].announcements, 3)

    def test_a_different_stop_is_a_different_setup(self):
        self.assertEqual(len(setups_from([taken(0), taken(1, stop=94.0)])), 2)

    def test_rejected_decisions_are_not_setups(self):
        self.assertEqual(setups_from([row(0), row(1)]), [])

    def test_a_setup_without_a_target_is_skipped(self):
        bare = row(0, disposition="taken", entry=100.0, stop=95.0, targets=[])
        self.assertEqual(setups_from([bare]), [])

    def test_first_seen_is_the_first_not_the_last(self):
        self.assertEqual(setups_from([taken(0), taken(5)])[0].first_seen,
                         T0.isoformat())

    def test_order_follows_the_journal(self):
        s = setups_from([taken(0, entry=100.0), taken(1, entry=200.0, stop=190.0)])
        self.assertEqual([x.entry for x in s], [100.0, 200.0])


class TestWalk(unittest.TestCase):
    def test_it_starts_after_the_decision_candle_not_on_it(self):
        """
        ⭐ القرار يُتَّخذ على الشمعة **المغلقة** — فلا أمر قبل إغلاقها.
        واحتساب الشمعة نفسها يقرأ حركةً سبقت الأمر.
        """
        bars = [bar(0, 100, 120, 100, 110)]      # شمعة القرار وحدها تبلغ الهدف
        self.assertEqual(walk(bars, setup(at=0)).outcome, "unfilled")

    def test_target_first_is_a_win(self):
        bars = [bar(0, 100, 101, 99, 100),
                bar(1, 100, 100, 99, 100),       # امتلأ
                bar(2, 100, 111, 99, 110)]       # بلغ 110
        self.assertEqual(walk(bars, setup()).outcome, "tp1")

    def test_stop_first_is_a_loss(self):
        bars = [bar(0, 100, 101, 99, 100),
                bar(1, 100, 100, 99, 100),
                bar(2, 100, 101, 94, 95)]
        self.assertEqual(walk(bars, setup()).outcome, "stop")

    def test_a_stopped_trade_records_the_adverse_move_that_stopped_it(self):
        """
        ⛔⛔ **ومقيسٌ على سجلّ المستخدم 10-03**: صفقتان ضُربتا وقفًا
        على **شمعة ملئهما** أرجعتا `mae = 0.00` — **وذلك مستحيلٌ
        بتعريفه**، فضربُ الوقف يلزمه ارتدادٌ ≥ المخاطرة.

        والعلّةُ أنّ تحديثَ `mae` كان **بعد** المخارج، فيضمّه فرعُ
        `tp1` وحدَه ⇒ **فالحقلُ يعني شيئين بحسب النتيجة**.
        """
        bars = [bar(0, 100, 101, 99, 100),
                bar(1, 100, 100, 94, 95)]        # يملأ ويَضرب في شمعةٍ واحدة
        r = walk(bars, setup())
        self.assertEqual(r.outcome, "stop")
        self.assertGreaterEqual(r.mae, 5.0)      # ⬅ المخاطرة، لا صفرًا

    def test_both_walkers_agree_on_the_adverse_field(self):
        """
        ⭐ **وهو حارسُ [أين الموضعُ الثاني؟]**: الماشيتان تحسبان
        الحقلَ نفسَه، **فلا تختلفان فيه** — وقد اختلفتا إلى 10-03.
        """
        from bot.replay import walk_managed
        bars = [bar(0, 100, 101, 99, 100),
                bar(1, 100, 100, 94, 95)]
        s = setup()
        self.assertAlmostEqual(walk(bars, s).mae,
                               walk_managed(bars, s).mae, places=6)

    def test_both_inside_one_candle_is_named_not_guessed(self):
        """
        ⚠️ شمعةٌ بلغت الوقفَ والهدفَ معًا لا تُخمَّن — تُسمّى `ambiguous`
        وتُحسب **خسارة**. فالرقم الخارج أسوأ من الواقع لا أفضل منه.
        """
        bars = [bar(0, 100, 101, 99, 100),
                bar(1, 100, 100, 99, 100),
                bar(2, 100, 115, 90, 100)]
        r = walk(bars, setup())
        self.assertEqual(r.outcome, "ambiguous")
        self.assertLess(r.pnl, 0)

    def test_an_unreached_entry_never_becomes_a_trade(self):
        bars = [bar(i, 200, 202, 198, 201) for i in range(1, 6)]
        self.assertEqual(walk(bars, setup()).outcome, "unfilled")

    def test_an_unresolved_setup_stays_open_and_costs_nothing(self):
        bars = [bar(1, 100, 100, 99, 100), bar(2, 100, 102, 99, 101)]
        r = walk(bars, setup())
        self.assertEqual(r.outcome, "open")
        self.assertEqual(r.pnl, 0.0)

    def test_a_sell_mirrors_a_buy(self):
        s = setup(entry=100.0, stop=105.0, target=90.0, direction="sell")
        bars = [bar(1, 100, 100, 99, 100), bar(2, 100, 101, 89, 90)]
        self.assertEqual(walk(bars, s).outcome, "tp1")

    def test_mae_records_what_the_winner_actually_needed(self):
        """⭐ هذا هو الرقم الذي يضبط سقف الوقف — لا المخاطرة المعلَنة."""
        bars = [bar(1, 100, 100, 97, 98),        # امتلأ وارتدّ 3
                bar(2, 100, 111, 99, 110)]
        r = walk(bars, setup())
        self.assertEqual(r.outcome, "tp1")
        self.assertAlmostEqual(r.mae, 3.0)
        self.assertLess(r.mae, r.setup.risk)     # احتاج أقلّ ممّا أُعطي

    def test_a_bad_timestamp_does_not_crash_the_walk(self):
        """
        ⛔⛔ **RW2 — وكان يُرجع `unfilled`. صُحّح 2026-09-27.**

        فـ«لم تُملأ» **حكمٌ على السوق**، و«وقتٌ لا يُقرأ» **عطبُ
        بيانات**. وخلطُهما يضيف صفوفًا وهميّةً إلى عدّ الإعدادات
        **ويُخفي العطب** — والشاهدُ أنّ هذه الشمعةَ **تبلغ الهدف**،
        فلو كان الوقتُ مقروءًا لكانت `tp1` لا `unfilled`.
        """
        s = Setup("M15", "buy", 100.0, 95.0, 110.0, "لا وقت", 1)
        self.assertEqual(
            walk([bar(1, 100, 111, 99, 110)], s).outcome, "unreadable")


class TestTightenVsRefuse(unittest.TestCase):
    """
    ⭐ الفرق جوهريّ: الرفض يفقدك الصفقة، والشدّ يُبقيها بمخاطرةٍ أقلّ.
    ولذلك يشدّ `max_stop` ولا يطرح.
    """

    def test_the_cap_tightens_the_stop_it_does_not_drop_the_setup(self):
        bars = [bar(1, 100, 100, 99, 100), bar(2, 100, 111, 99, 110)]
        r = walk(bars, setup(stop=70.0), max_stop=5.0)
        self.assertEqual(r.outcome, "tp1")
        self.assertAlmostEqual(r.setup.risk, 5.0)

    def test_a_cap_below_what_the_winner_needed_turns_it_into_a_loss(self):
        """⚠️ وهذا ما رصده الأسبوع: التشديد إلى 12$ قلب −10.21$ إلى −109.85$."""
        bars = [bar(1, 100, 100, 96, 97), bar(2, 100, 111, 99, 110)]
        self.assertEqual(walk(bars, setup()).outcome, "tp1")
        self.assertEqual(walk(bars, setup(), max_stop=2.0).outcome, "stop")

    def test_a_cap_above_the_stop_changes_nothing(self):
        bars = [bar(1, 100, 100, 99, 100), bar(2, 100, 111, 99, 110)]
        a, b = walk(bars, setup()), walk(bars, setup(), max_stop=999.0)
        self.assertEqual((a.outcome, a.setup.risk), (b.outcome, b.setup.risk))


class TestAccounting(unittest.TestCase):
    """بلوت 0.01 على الذهب: دولارٌ لكل دولار حركة — قرار المستخدم."""

    def _both(self):
        bars = [bar(1, 100, 100, 99, 100), bar(2, 100, 111, 90, 110)]
        win = walk([bar(1, 100, 100, 99, 100), bar(2, 100, 111, 99, 110)], setup())
        loss = walk([bar(1, 100, 100, 99, 100), bar(2, 100, 101, 94, 95)],
                    setup(n=4))
        return win, loss, bars

    def test_a_win_pays_its_reward_and_a_loss_costs_its_risk(self):
        win, loss, _ = self._both()
        self.assertAlmostEqual(win.pnl, 10.0)
        self.assertAlmostEqual(loss.pnl, -5.0)

    def test_the_weighted_total_is_the_cost_of_repetition(self):
        win, loss, _ = self._both()
        self.assertAlmostEqual(net([win, loss]), 5.0)
        self.assertAlmostEqual(net([win, loss], weighted=True), 10.0 - 4 * 5.0)

    def test_tally_counts_every_outcome(self):
        win, loss, _ = self._both()
        self.assertEqual(tally([win, loss]), {"tp1": 1, "stop": 1})

    def test_stop_demand_ranks_the_hungriest_winner_first(self):
        a = walk([bar(1, 100, 100, 98, 99), bar(2, 100, 111, 99, 110)], setup())
        b = walk([bar(1, 100, 100, 96, 97), bar(2, 100, 111, 99, 110)], setup())
        self.assertEqual([round(x[1], 2) for x in stop_demand([a, b])], [4.0, 2.0])

    def test_stop_demand_ignores_losers(self):
        _, loss, _ = self._both()
        self.assertEqual(stop_demand([loss]), [])


class TestRender(unittest.TestCase):
    def test_it_always_states_its_own_limits(self):
        """⚠️ نتيجةٌ بلا حدودها تُقرأ أقوى ممّا هي."""
        out = render(replay([taken(0), row(1), row(2)]))
        self.assertIn("عيّنة", out)
        self.assertIn("ملتبس", out)

    def test_the_repetition_line_appears_only_when_it_costs(self):
        """الهدف 101.5 تبلغه قمّة 102 في الشمعة التالية ⇒ نتيجةٌ محسومة."""
        hit = lambda i: taken(i, target=101.5)                # noqa: E731
        once = render(replay([hit(0), row(1), row(2)]))
        many = render(replay([hit(0), hit(1), hit(2), row(3)]))
        self.assertNotIn("كلفة التكرار", once)
        self.assertIn("كلفة التكرار", many)


class TestJournalReading(unittest.TestCase):
    def test_a_truncated_last_line_does_not_lose_the_week(self):
        """انقطاعُ الكهرباء يُتلف سطرًا — لا أسبوعًا."""
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "j.jsonl")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(row(0)) + "\n")
                fh.write(json.dumps(row(1)) + "\n")
                fh.write('{"poi_tf": "M15", "candle_ti')
            self.assertEqual(len(read_journal(p)), 2)

    def test_a_missing_file_is_empty_not_an_error(self):
        self.assertEqual(read_journal("/لا/يوجد.jsonl"), [])


class TestReplayEndToEnd(unittest.TestCase):
    def test_an_empty_journal_replays_to_nothing(self):
        self.assertEqual(replay([]), [])

    def test_every_setup_gets_exactly_one_result(self):
        rows = [taken(0), taken(1), taken(2, entry=200.0, stop=190.0), row(3)]
        self.assertEqual(len(replay(rows)), len(setups_from(rows)))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestSurvival(unittest.TestCase):
    """
    ⭐⭐⭐ **ما كان سيحدث لو لم يكن للإعداد وقفٌ إطلاقًا؟**

    وهو ما يفصل بين احتمالين يبدوان واحدًا في السجلّ:
      • بلغ الهدفَ بعد ضربِ وقفه ⇒ الاتّجاه صحيح **والوقف ضيّق**
      • لم يبلغه                 ⇒ **الإعداد خطأ**، والوقف بريء
    """

    def test_a_trade_that_reaches_after_being_stopped_says_so(self):
        bars = [bar(1, 100, 100.5, 94.0, 95.0),    # ضُرب وقفُه عند 95
                bar(2, 95, 111.0, 95.0, 110.0)]    # ثم بلغ الهدف 110
        s = survival(bars, setup(entry=100.0, stop=95.0, target=110.0))
        self.assertTrue(s.reached)
        self.assertAlmostEqual(s.needed, 6.0)      # لزمه 6$ لا 5$

    def test_a_trade_that_never_reaches_says_so(self):
        bars = [bar(1, 100, 100.5, 94.0, 95.0),
                bar(2, 95, 99.0, 90.0, 92.0)]
        s = survival(bars, setup(entry=100.0, stop=95.0, target=110.0))
        self.assertFalse(s.reached)

    def test_the_horizon_bounds_the_wait(self):
        """
        ⚠️ **وبلا سقفٍ يصير السؤال «هل يُبلَغ يومًا ما»** — وكلُّ سعرٍ
        يُبلَغ إن انتظرتَ كفاية. فالسقف شرطُ معنًى لا تحسينُ أداء.
        """
        bars = [bar(1, 100, 100.5, 99.5, 100.0)] * 1
        bars += [bar(i, 100, 100.5, 99.5, 100.0) for i in range(2, 20)]
        bars.append(bar(40, 100, 120.0, 100, 119.0))
        s = survival(bars, setup(entry=100.0, stop=95.0, target=110.0),
                     horizon=5)
        self.assertFalse(s.reached)
        self.assertTrue(survival(bars, setup(), horizon=100).reached)

    def test_an_unfilled_setup_is_marked(self):
        bars = [bar(1, 200, 201, 199, 200)]
        s = survival(bars, setup(entry=100.0, stop=95.0, target=110.0))
        self.assertFalse(s.filled)
        self.assertFalse(s.reached)

    def test_selling_mirrors(self):
        bars = [bar(1, 100, 106.0, 99.5, 105.0),   # ضُرب وقفُه عند 105
                bar(2, 105, 105.0, 89.0, 90.0)]    # ثم بلغ الهدف 90
        s = survival(bars, setup(entry=100.0, stop=105.0, target=90.0,
                                 direction="sell"))
        self.assertTrue(s.reached)
        self.assertAlmostEqual(s.needed, 6.0)


class TestTheFillBarIsNotCountedOptimistically(unittest.TestCase):
    """
    ⛔⛔⛔ **RW1 — انحيازٌ متفائلٌ كان يخالف عهدَ الأداة المعلَن:**
    «الرقمُ الخارج **أسوأُ** من الواقع لا أفضلُ منه».

    فعلى شمعةِ الملء كان المكسبُ يُقاس **بمدى الشمعة كلِّه**، وفيه ما
    سبق لمسَ الدخول.

    ⚠️ **وأثرُه على أرقامٍ منشورة**: كلُّ رقمٍ في `CLAUDE.md` خرج من
    هاتين الدالّتين.
    """

    T = datetime(2026, 9, 14, 10, 0)

    def _s(self, direction="buy", entry=4300.0, stop=4295.0, target=4310.0,
           targets=()):
        return Setup(timeframe="M15", direction=direction, entry=entry,
                     stop=stop, target=target,
                     first_seen=self.T.isoformat(), targets=targets)

    def _bars(self, *rows):
        out = [Bar(self.T, 4300, 4300, 4300, 4300)]
        for i, (o, h, l, c) in enumerate(rows, start=1):
            out.append(Bar(self.T + timedelta(minutes=15 * i), o, h, l, c))
        return out

    def test_a_high_that_preceded_the_fill_is_not_a_target(self):
        """
        ⛔ **الحالةُ بعينها**: شمعةٌ **افتتحت 4311** فوق دخولِ 4300،
        فقمّتُها 4312 **سبقت** نزولَها إلى 4300 فملأت. وكانت تُرجع
        `tp1 +10$` — **ومكسبُها لم يقع بعد الدخول أصلًا**.
        """
        r = walk(self._bars((4311, 4312, 4300, 4305)), self._s())
        self.assertNotEqual(r.outcome, "tp1")

    def test_a_fill_bar_that_truly_closes_beyond_the_target_still_counts(self):
        """✅ ولا يُبخَس حقٌّ: الإغلاقُ مرتَّبٌ بعد الملء يقينًا."""
        r = walk(self._bars((4301, 4312, 4300, 4311)), self._s())
        self.assertEqual(r.outcome, "tp1")

    def test_the_stop_is_still_hit_by_the_wick_on_the_fill_bar(self):
        """
        ⚠️ **وعدمُ التناظر مقصودٌ ومعلَن**: الخسارةُ بالمدى والمكسبُ
        بالإغلاق — لأنّ احتسابَ الخسارة **تشاؤمٌ**، وهو العهد.
        """
        r = walk(self._bars((4300, 4301, 4294, 4299)), self._s())
        self.assertEqual(r.outcome, "stop")

    def test_a_later_bar_reaches_the_target_normally(self):
        """⭐ ولا يمسّ الإصلاحُ إلّا شمعةَ الملء وحدها."""
        r = walk(self._bars((4300, 4302, 4299, 4301),
                            (4301, 4312, 4301, 4311)), self._s())
        self.assertEqual(r.outcome, "tp1")

    def test_a_sell_mirrors_the_rule(self):
        r = walk(self._bars((4289, 4300, 4288, 4295)),
                 self._s("sell", 4300.0, 4305.0, 4290.0))
        self.assertNotEqual(r.outcome, "tp1")

    def test_walk_managed_has_the_same_guard(self):
        """
        ⚠️ **وهو الموضعُ الثاني — وأثقل**: بلوغُ هدفٍ **يحرّك الوقف**،
        فهدفٌ كاذبٌ على شمعة الملء يُزيح الوقفَ ويتراكم الخطأ.
        """
        s = self._s(targets=(4310.0, 4320.0))
        r = walk_managed(self._bars((4321, 4322, 4300, 4302)), s)
        self.assertEqual(r.outcome, "open")

    def test_walk_managed_still_credits_a_real_close(self):
        s = self._s(targets=(4310.0, 4320.0))
        r = walk_managed(self._bars((4301, 4322, 4300, 4321)), s)
        self.assertTrue(r.outcome.startswith("tp"))


class TestWhyTheBotRejects(unittest.TestCase):
    """
    ⭐⭐⭐ **بُني 2026-10-02** — طلب المستخدم [اريد ان يقرا الاتجاه
    افضل]، **والقياسُ قبل التغيير**.

    و[الهيكل غير محدَّد] **حالتان لا واحدة**، وعلاجُهما مختلفٌ تمامًا:
      ① «لا قمم/قيعان كافية»      ⇒ عطبُ قراءة — **يُصلَح**
      ② [هيكل متضارب — نطاق عرضيّ] ⇒ **لا يُحكَم عليه جملةً**

    ⛔⛔ **وصُحّحت الأداةُ في اليوم نفسِه** — أوّلُ تشغيلٍ على سجلّ
    المستخدم أعطى ① = **صفر** و② = **كلَّها**، فكانت القراءةُ
    الظاهرة [الرفضُ صائبٌ كلُّه]. **و② ثلاثُ حالات**، لأنّ
    `describe_trend` تبنيها من **ثلاثِ** كلمات: `أعلى` · `أدنى` ·
    **`مساوية`** — والثالثةُ **ليست سوقًا عرضيًّا**.
    ⇒ **فاللمُّ كان يُخفي حالةً.**

    ⛔⛔⛔ **وصُحّح ثانيةً في اليوم نفسِه — وكان الوسمُ يَعِد بما لا
    يملك.** كُتب أنّ الطرفَ المساوي **هو هضبةُ SW1**، فيُقرأ صفرُه
    جوابًا عنها. **وذلك باطل**: `find_swings` تحت `strict` تقارن
    صارمةً يمينًا ⇒ **فالقمّتان المتساويتان المتجاورتان تسقطان معًا**
    ولا تبلغان `describe_trend` أصلًا. ⇒ **فالصفرُ مضمونٌ بالبناء
    لا مقيس** — وهو **عينُ المفتاح الذي يُقاس**.
    ⇒ وما يلتقطه الوسمُ فعلًا: **سوينجان غيرُ متجاورَين متساويان**.
    ⭐ **والدرسُ: يُسأل عن الوسم الجديد — ماذا يلتقط فعلًا، لا ماذا
    سمّيتُه؟**
    """

    def _log(self, rows):
        import json
        import tempfile
        p = tempfile.mktemp(suffix=".jsonl")
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return p

    @staticmethod
    def _row(evidence, passed=False, tf="M15", disp="rejected"):
        return {"poi_tf": tf, "disposition": disp,
                "checks": [{"name": "الهيكل محدد", "passed": passed,
                            "evidence": evidence}]}

    def test_it_separates_the_two_kinds_of_undefined(self):
        """⭐ **وهذا هو غرضُ الأداة كلِّه** — فالعلاجان مختلفان."""
        from bot.replay import why_rejected
        p = self._log([self._row("لا قمم/قيعان كافية للحكم — 0 قمة")] * 3
                      + [self._row("هيكل متضارب — قمة أعلى ⇒ نطاق عرضيّ")] * 7)
        out = why_rejected(p, "M15")
        self.assertIn("لا قمم/قيعان كافية", out)
        self.assertIn("نطاق عرضيّ", out)
        self.assertIn("3", out)
        self.assertIn("7", out)

    def test_it_says_which_one_may_be_fixed(self):
        """⛔ **ولا يُقرأ العددان سواءً** — وإلّا فُهم أنّ كليهما عطب."""
        from bot.replay import why_rejected
        p = self._log([self._row("هيكل متضارب ⇒ نطاق عرضيّ")])
        self.assertIn("والأوّلُ وحده يُصلَح", why_rejected(p, "M15"))

    def test_only_the_first_failing_check_is_counted(self):
        """
        ⚠️ **وما بعد الراسب الأوّل لم يُفحَص أصلًا** — فعدُّه يضخّم
        أسبابًا لم تمنع شيئًا.
        """
        from bot.replay import why_rejected
        p = self._log([{"poi_tf": "M15", "disposition": "rejected", "checks": [
            {"name": "الهيكل محدد", "passed": False, "evidence": "نطاق عرضيّ"},
            {"name": "فحصٌ تالٍ", "passed": False, "evidence": "—"}]}])
        out = why_rejected(p, "M15")
        self.assertIn("الهيكل محدد", out)
        self.assertNotIn("فحصٌ تالٍ", out)

    def test_another_timeframe_is_excluded(self):
        from bot.replay import why_rejected
        p = self._log([self._row("نطاق عرضيّ", tf="H1")])
        self.assertIn("لا صفوفَ على M15", why_rejected(p, "M15"))

    def test_an_empty_log_says_so(self):
        from bot.replay import why_rejected
        self.assertIn("فارغ", why_rejected(self._log([]), "M15"))

    # ── ⛔⛔ وتفصيلُ ② — والطرفُ المساوي ليس سوقًا عرضيًّا ──────────

    def test_an_equal_high_is_named_apart_from_a_range(self):
        """
        ⭐⭐ **وهذا ما كان اللمُّ يُخفيه**: صفٌّ دليلُه `قمة مساوية`
        يُقرأ في السلّة الواحدة [سوقٌ عرضيٌّ ⇒ الرفضُ صائب] — **وهو
        طرفٌ مساوٍ لا نطاق**.
        ⚠️ **ولا يُقرأ منه حكمٌ على SW1** — انظر ترويسةَ الطقم.
        """
        from bot.replay import why_rejected
        p = self._log([self._row(
            "هيكل متضارب — قمة مساوية وقاع أعلى ⇒ نطاق عرضيّ لا اتجاه "
            "(110→110 · 100→101)")])
        out = why_rejected(p, "M15")
        self.assertIn("قمّتان متساويتان", out)
        self.assertIn("طرفاه متساويان", out)

    def test_a_true_range_is_not_called_an_equal_edge(self):
        """⚠️ **والعكسُ يُفحَص** — وإلّا سُمّي كلُّ رفضٍ عطبًا."""
        from bot.replay import why_rejected
        p = self._log([self._row(
            "هيكل متضارب — قمة أعلى وقاع أدنى ⇒ نطاق عرضيّ لا اتجاه "
            "(110→112 · 100→98)")])
        out = why_rejected(p, "M15")
        self.assertIn("نطاقٌ متوسّع", out)
        self.assertNotIn("متساويتان", out)      # ⬅ لا صفَّ طرفٍ مساوٍ

    def test_the_two_shapes_are_counted_apart(self):
        """⚠️ **والعددان يُفصلان** — ولا يُقرأ منهما حكمٌ على SW1."""
        from bot.replay import why_rejected
        p = self._log(
            [self._row("هيكل متضارب — قمة مساوية وقاع أعلى ⇒ نطاق عرضيّ")] * 2
            + [self._row("هيكل متضارب — قمة أعلى وقاع أدنى ⇒ نطاق عرضيّ")] * 8)
        out = why_rejected(p, "M15")
        self.assertIn("قمّتان متساويتان", out)
        self.assertIn("نطاقٌ متوسّع", out)
        self.assertIn("2 صفًّا", out)

    def test_an_unreadable_evidence_is_named_not_bucketed(self):
        """
        ⚠️ **وما لا يُقرأ يُسمّى** — ولا يُلحَق بأقرب سلّة. فالسجلُّ
        لا يحمل السوينجات، فلا سبيلَ إلى إعادة الحساب.
        """
        from bot.replay import why_rejected
        p = self._log([self._row("هيكل متضارب ⇒ نطاق عرضيّ")])
        self.assertIn("دليلٌ لا يُقرأ", why_rejected(p, "M15"))

    def test_the_shape_split_matches_describe_trend_wording(self):
        """
        ⛔⛔ **وهذا هو الحارس**: `_range_shape` تقرأ **نصًّا** يبنيه
        `describe_trend`. ⇒ فلو تغيّرت صيغتُه لصمتت الأداةُ عن
        الطرف المساوي — **وهو صنفُ [بندٌ معلَنٌ لا يعمل، ويصمت]**.
        ⇒ فيُبنى الدليلُ من الدالّة نفسِها لا من نصٍّ مكتوبٍ باليد.
        """
        from datetime import datetime, timezone

        from bot.primitives.structure import describe_trend
        from bot.primitives.swings import Swing
        from bot.replay import _range_shape

        def sw(i, price, kind):
            return Swing(index=i, price=price, kind=kind,
                         time=datetime(2026, 10, 2, tzinfo=timezone.utc))

        trend, ev = describe_trend([
            sw(0, 110.0, "high"), sw(1, 100.0, "low"),
            sw(2, 110.0, "high"), sw(3, 101.0, "low")])
        self.assertEqual(trend, "undefined")
        self.assertIn("قمّتان متساويتان", _range_shape(ev))
