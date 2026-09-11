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
    rebuild,
    render,
    replay,
    setups_from,
    stop_demand,
    tally,
    walk,
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
        s = Setup("M15", "buy", 100.0, 95.0, 110.0, "لا وقت", 1)
        self.assertEqual(walk([bar(1, 100, 111, 99, 110)], s).outcome, "unfilled")


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
