"""
اختبارات تتبُّع الإعداد حتّى نهايته.

⭐ **والسؤالُ الذي بُنيت له الوحدة:** كم بقي السعرُ خلف الوقف قبل أن
يعود؟ — لا «أبُلغ الهدفُ يومًا ما»، فذاك يُبلَغ دائمًا إن انتظرت.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from bot.data import Candle
from bot.followup import (POST_MINUTES, Tracker, Watch, advance, measures,
                          ready, window)
from bot.replay import Bar

T0 = datetime(2026, 9, 28, 10, 0)


def candles(*rows, start=T0, step=1):
    """شموعُ الدقيقة بنوع `data.Candle` — وهو ما يعطيه الجسرُ حيًّا."""
    return [Candle(start + timedelta(minutes=step * i), o, h, l, c)
            for i, (o, h, l, c) in enumerate(rows)]


def bars(*rows, start=T0, step=1):
    """وبنوع `replay.Bar` — وهو ما يُبنى من السجلّ في التحليل."""
    return [Bar(start + timedelta(minutes=step * i), o, h, l, c)
            for i, (o, h, l, c) in enumerate(rows)]


def buy_watch(**kw):
    base = dict(key="k1", timeframe="M15", direction="buy",
                entry=100.0, stop=98.0, targets=(104.0,),
                announced=T0.isoformat())
    base.update(kw)
    return Watch(**base)


class TestItWalksToTheEnd(unittest.TestCase):
    def test_it_fills_then_stops(self):
        w = advance(buy_watch(), candles(
            (101, 101, 101, 101),      # قبل — لا لمس
            (100, 100.5, 99.8, 100),   # اللمس ⇒ الملء
            (100, 100, 97.5, 98),      # الوقف
        ))
        self.assertEqual(w.outcome, "stop")
        self.assertIsNotNone(w.filled)

    def test_it_fills_then_reaches_the_target(self):
        w = advance(buy_watch(), candles(
            (100, 100.2, 99.9, 100),
            (100, 104.5, 100, 104.2),
        ))
        self.assertEqual(w.outcome, "tp1")

    def test_it_never_reads_a_bar_before_the_setup_was_announced(self):
        """⛔ الأمرُ لا يوجد قبل إغلاق شمعته."""
        early = candles((100, 110, 90, 100), start=T0 - timedelta(minutes=30))
        self.assertIsNone(advance(buy_watch(), early).outcome)

    def test_an_unfilled_setup_expires_rather_than_lingering(self):
        far = candles((120, 121, 119, 120),
                      start=T0 + timedelta(minutes=25 * 60))
        self.assertEqual(advance(buy_watch(), far).outcome, "expired")

    def test_the_stop_wins_a_tie_inside_one_minute(self):
        """⛔ التشاؤم مقصود — كعُرف `replay`."""
        w = advance(buy_watch(), candles((100, 104.5, 97.5, 100),
                                         start=T0 + timedelta(minutes=1)))
        self.assertEqual(w.outcome, "stop")

    def test_a_resolved_watch_is_not_walked_again(self):
        done = buy_watch(resolved=T0.isoformat(), outcome="stop")
        self.assertIs(advance(done, candles((1, 999, 0, 1))), done)


class TestBothCandleTypes(unittest.TestCase):
    """
    ⛔ `data.Candle` حقولُها `.high/.low` و`replay.Bar` حقولُها `.h/.l`.
    وكادت الوحدةُ تُبنى على أحدهما فتنهار مع الآخر حيًّا.
    """

    ROWS = ((100, 100.2, 99.9, 100), (100, 100, 97.5, 98))

    def test_the_live_candle_type_works(self):
        self.assertEqual(advance(buy_watch(), candles(*self.ROWS)).outcome,
                         "stop")

    def test_the_analysis_bar_type_works_identically(self):
        self.assertEqual(advance(buy_watch(), bars(*self.ROWS)).outcome,
                         "stop")


class TestTheNumberTheModuleExistsFor(unittest.TestCase):
    """
    ⭐⭐⭐ `minutes_beyond_stop` — بديلُ الأفق المختار.

    صغيرٌ ⇒ كسحُ سيولة، **وموضعُ الدخول خطأ**.
    كبيرٌ ⇒ **الاتّجاهُ خطأ**. وعلاجُهما مختلف.
    """

    def _stopped(self, *after_rows):
        rows = ((100, 100.2, 99.9, 100), (100, 100, 97.5, 98)) + after_rows
        w = advance(buy_watch(), candles(*rows))
        return w, measures(w, candles(*rows))

    def test_a_sweep_that_reverses_in_three_minutes_reads_small(self):
        """⚠️ والقمّةُ تبقى **دون** الوقف 98 — فلمسُه عودةٌ لا بقاء."""
        w, m = self._stopped(
            (97.8, 97.90, 97.5, 97.8),   # +1 دقيقة — تحت الوقف
            (97.8, 97.95, 97.6, 97.9),   # +2 — ما زال
            (97.9, 98.60, 97.9, 98.5),   # +3 — عاد إلى الوقف
        )
        self.assertEqual(w.outcome, "stop")
        self.assertEqual(m["minutes_beyond_stop"], 3)

    def test_a_real_move_that_never_comes_back_reads_none(self):
        w, m = self._stopped(*[(97, 97.4, 96.5, 97)] * 30)
        self.assertIsNone(m["minutes_beyond_stop"])

    def test_none_means_not_within_the_window_not_never(self):
        """⚠️ والفرقُ يُذكر مع الرقم ولا يُطوى."""
        import bot.followup as mod
        self.assertIn("لم يعد ضمن النافذة المسجَّلة",
                      mod.measures.__doc__)

    def test_it_measures_how_far_past_the_stop_price_went(self):
        _, m = self._stopped((97, 97.2, 96.0, 97))
        self.assertAlmostEqual(m["max_excursion_in_window"], 2.0, places=2)
        self.assertAlmostEqual(m["max_excursion_before_return"], 2.0, places=2)

    def test_the_depth_read_with_the_minutes_stops_at_the_return(self):
        """
        ⛔⛔ **FU1 — وكان الرقمان يُقاسان على نافذتين مختلفتين.**

        فـ`minutes_beyond_stop` يتوقّف عند أوّل عودة، والعمقُ كان
        يُجمَع على النافذة كلِّها. فلو عاد السعرُ سريعًا **ثمّ** هوى،
        خرج الزوجُ «عاد في دقائق · بعمقٍ سحيق» — **وهو كذب**.

        ⭐ **والزوجُ هو جوابُ السؤال المركزيّ**: عمقٌ كبير + عودةٌ
        سريعة = كسحُ سيولة ⇒ موضعُ الدخول خطأ. وعمقٌ صغير + عودةٌ
        سريعة = **ضجيجٌ عند المستوى**، لا خبرَ فيه.
        """
        # وقفُ الشراء 98. تنزل إلى 97.5 (عمق 0.5) ثمّ **تعود** إلى 98،
        # ثمّ تهوي إلى 90 (عمق 8) بعد العودة.
        _, m = self._stopped(
            (97.8, 97.9, 97.5, 97.8),      # عمقٌ 0.5 قبل العودة
            (97.9, 98.2, 97.9, 98.1),      # ← العودة إلى الوقف
            (98.0, 98.0, 90.0, 90.5),      # هُويٌّ **بعد** العودة
        )
        self.assertIsNotNone(m["minutes_beyond_stop"])
        self.assertAlmostEqual(m["max_excursion_before_return"], 0.5, places=2)
        self.assertAlmostEqual(m["max_excursion_in_window"], 8.0, places=2)

    def test_no_return_makes_both_depths_the_window_depth(self):
        """
        ⚠️ **وإن لم يعد ضمن النافذة** فالعمقُ «حتّى العودة» هو عمقُ
        النافذة كلِّها — **ولا يُترك `None`** فيُقرأ «لا عمق».
        """
        _, m = self._stopped((97, 97.2, 96.0, 96.5),
                             (96.5, 96.6, 95.0, 95.2))
        self.assertIsNone(m["minutes_beyond_stop"])
        self.assertEqual(m["max_excursion_before_return"],
                         m["max_excursion_in_window"])

    def test_it_times_the_target_reached_after_the_stop(self):
        w, m = self._stopped(
            (98, 98.5, 97.9, 98.4),
            (98, 104.6, 98, 104.5),
        )
        self.assertEqual(m["minutes_to_target_after_stop"], 2)

    def test_a_winner_carries_no_beyond_stop_number(self):
        rows = ((100, 100.2, 99.9, 100), (100, 104.5, 100, 104.2))
        w = advance(buy_watch(), candles(*rows))
        self.assertEqual(w.outcome, "tp1")
        self.assertIsNone(measures(w, candles(*rows))["minutes_beyond_stop"])

    def test_the_sell_side_mirrors(self):
        w = buy_watch(direction="sell", entry=100.0, stop=102.0,
                      targets=(96.0,))
        rows = ((100, 100.1, 99.8, 100),       # +0 — تُتخطّى (لحظةُ الإعلان)
                (100, 102.5, 100, 102),        # +1 — الملء ثمّ الوقف
                (102.2, 102.4, 102.1, 102.3),  # +2 — فوق الوقف بعد
                (102.1, 102.2, 101.5, 101.6))  # +3 — عاد إلى الوقف
        w = advance(w, candles(*rows))
        self.assertEqual(w.outcome, "stop")
        self.assertEqual(measures(w, candles(*rows))["minutes_beyond_stop"], 2)


class TestTheWindow(unittest.TestCase):
    def test_it_reaches_back_before_the_setup_and_after_its_end(self):
        rows = candles((100, 100.2, 99.9, 100), (100, 100, 97.5, 98),
                       start=T0)
        pre = candles((99, 99, 99, 99), start=T0 - timedelta(minutes=30))
        w = advance(buy_watch(), rows)
        out = window(w, pre + rows, pre=60, post=120)
        self.assertEqual(len(out), 3)
        self.assertIn("t", out[0])

    def test_it_is_not_ready_until_the_post_window_elapsed(self):
        w = buy_watch(resolved=T0.isoformat(), outcome="stop")
        self.assertFalse(ready(w, T0 + timedelta(minutes=POST_MINUTES - 1)))
        self.assertTrue(ready(w, T0 + timedelta(minutes=POST_MINUTES)))


class TestTheTrackerSurvivesRestarts(unittest.TestCase):
    def _tracker(self, d):
        return Tracker(state_path=os.path.join(d, "watches.json"),
                       out_path=os.path.join(d, "followups.jsonl"))

    def test_a_noted_setup_round_trips_through_disk(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._tracker(d)
            t.note("k1", "M15", "buy", 100.0, 98.0, [104.0], T0.isoformat())
            t.save()
            again = self._tracker(d).load()
            self.assertIn("k1", again.watches)
            self.assertEqual(again.watches["k1"].targets, (104.0,))

    def test_the_same_setup_is_not_noted_twice(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._tracker(d)
            for _ in range(3):
                t.note("k1", "M15", "buy", 100.0, 98.0, [104.0],
                       T0.isoformat())
            self.assertEqual(len(t.watches), 1)

    def test_a_corrupt_state_file_does_not_raise(self):
        """⛔ زينةُ تشخيصٍ لا شرطُ تشغيل."""
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "watches.json")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("{ليس جيسون")
            self.assertEqual(
                Tracker(state_path=p, out_path=os.path.join(d, "o")).load()
                .watches, {})

    def test_tick_never_raises_on_nonsense_bars(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._tracker(d)
            t.note("k1", "M15", "buy", 100.0, 98.0, [104.0], T0.isoformat())
            self.assertEqual(t.tick([object(), None], T0), [])

    def test_a_finished_watch_is_written_and_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            t = self._tracker(d)
            t.note("k1", "M15", "buy", 100.0, 98.0, [104.0], T0.isoformat())
            rows = candles((100, 100.2, 99.9, 100), (100, 100, 97.5, 98))
            done = t.tick(rows, T0 + timedelta(minutes=POST_MINUTES + 5))
            self.assertEqual(len(done), 1)
            self.assertEqual(done[0]["outcome"], "stop")
            self.assertNotIn("k1", t.watches)
            self.assertEqual(t.write(done), 1)
            with open(t.out_path, encoding="utf-8") as fh:
                rec = json.loads(fh.readline())
            self.assertIn("measures", rec)
            self.assertIn("m1", rec)


class TestItCannotTrade(unittest.TestCase):
    """⛔ القاعدةُ ② — لا تنفيذ، مسدودٌ في الكود لا في التوثيق."""

    @staticmethod
    def _source() -> str:
        import inspect

        import bot.followup as mod
        return inspect.getsource(mod)       # لا يعتمد على مجلّد التشغيل

    def test_the_module_sends_no_orders(self):
        src = self._source()
        for forbidden in ("order_send", "order_check", "positions_get"):
            self.assertNotIn(forbidden, src)

    def test_it_does_not_import_the_bridge(self):
        """نقيّةٌ من MT5 — تأخذ الشموع ولا تجلبها، فتُختبر بلا منصّة."""
        src = self._source()
        self.assertNotIn("mt5_bridge", src)
        self.assertNotIn("MetaTrader5", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
