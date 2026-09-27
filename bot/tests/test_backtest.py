"""
اختبارات إعادة تشغيل السلسلة على تاريخٍ حقيقيّ.

⛔ **ولماذا وُجد هذا الملفّ؟** لأنّ `replay.py` يصحّح نتيجة قراراتٍ
اتُّخذت ولا يعيد اتّخاذها — فقاعدةٌ جديدة في `chain.py` لا يظهر أثرها
فيه. وأسوأ: السجلّ يحمل **8.6% فقط** من شموع إطار التأكيد، فقاعدةٌ
تعمل عليه لا تُقاس على تسعة أعشارِ فراغ.
"""

import unittest
from datetime import datetime, timedelta

from bot.backtest import (_upto, confirm_bars_needed, coverage_gap,
                          decisions, range_gap, render)


class TestTheAskedRangeMustExist(unittest.TestCase):
    """
    ⛔ **العطبُ نفسُه في ثوبٍ ثانٍ — وكُشف قبل التشغيل لا بعده.**

    `--from 2026-08-26` مع `--poi-bars 1500`، وأقدمُ شمعةٍ مجلوبةٍ
    `09-02` ⇒ سبعةُ أيّامٍ **غيرُ موجودةٍ أصلًا**. و`decisions()`
    يتخطّاها صامتًا، فيخرج الرقمُ باسم مدًى لم يُقَس.
    """

    def test_a_missing_head_is_shouted(self):
        poi = series("M15", 15, 40)                     # يبدأ عند T0
        msg = range_gap(poi, T0 - timedelta(days=7))
        self.assertIsNotNone(msg)
        self.assertIn("7 DAYS MISSING", msg)
        self.assertTrue(msg.splitlines()[0].isascii())

    def test_a_covered_range_says_nothing(self):
        poi = series("M15", 15, 40)
        self.assertIsNone(range_gap(poi, T0 - timedelta(hours=0)))
        self.assertIsNone(range_gap(poi, None))

    def test_a_tail_that_stops_short_is_named_too(self):
        poi = series("M15", 15, 4)                      # ينتهي بعد 45 دقيقة
        msg = range_gap(poi, None, T0 + timedelta(days=3))
        self.assertIn("before", msg)

    def test_an_empty_series_is_named(self):
        self.assertIn("EMPTY", range_gap(Series("M15", [], symbol="XAUUSD"), T0))


class TestConfirmBarsMustCoverThePoiRange(unittest.TestCase):
    """
    ⛔⛔ **ثلثُ نافذة القياس كان بلا شمعةِ تأكيدٍ واحدة** (كُشف 09-25).

        --poi-bars 1500 شمعة M15  ⇒  17.9 يومَ تداول
        --confirm-bars 5000 M3    ⇒  12.0 يومَ تداول
        ⇒ ستّةُ أيّامٍ يُرجع فيها `_upto` **سلسلةً فارغة**.

    فيبدو التنقيحُ فاشلًا وهو لم يُسأل، ويُرفض المسارُ الانعكاسيّ دائمًا.
    """

    def test_the_count_is_derived_not_written(self):
        self.assertEqual(confirm_bars_needed("M15", "M3", 1500), 8250)

    def test_the_old_default_was_short_by_a_third(self):
        need = confirm_bars_needed("M15", "M3", 1500)
        self.assertGreater(need, 5000)
        self.assertGreater((need - 5000) / need, 0.30)

    def test_other_pairs_scale_too(self):
        self.assertEqual(confirm_bars_needed("H1", "M5", 1000), 13200)
        self.assertEqual(confirm_bars_needed("H4", "M30", 500), 4400)

    def test_an_unknown_frame_falls_back_instead_of_guessing(self):
        self.assertEqual(confirm_bars_needed("???", "M3", 700), 700)
        self.assertEqual(confirm_bars_needed("M3", "M15", 700), 700)   # مقلوب

    def test_a_gap_is_shouted_not_swallowed(self):
        poi = series("M15", 15, 40)
        late = Series("M3", [Candle(T0 + timedelta(hours=6) + timedelta(minutes=3 * i),
                                    100, 100.5, 99.5, 100) for i in range(20)],
                      symbol="XAUUSD")
        msg = coverage_gap(poi, late)
        self.assertIsNotNone(msg)
        self.assertIn("6h", msg)
        self.assertTrue(msg.splitlines()[0].isascii())

    def test_full_coverage_says_nothing(self):
        poi = series("M15", 15, 40)
        conf = series("M3", 3, 400)
        self.assertIsNone(coverage_gap(poi, conf))

    def test_an_empty_series_is_named_not_passed_over(self):
        self.assertIn("EMPTY", coverage_gap(series("M15", 15, 10),
                                            Series("M3", [], symbol="XAUUSD")))
from bot.data import Candle, Series
from bot.replay import Result, Setup

T0 = datetime(2026, 9, 14, 0, 0)


def series(tf: str, step: int, n: int) -> Series:
    return Series(tf, [Candle(T0 + timedelta(minutes=step * i),
                              100, 100.5, 99.5, 100) for i in range(n)],
                  symbol="XAUUSD")


def result(name, outcome, pnl):
    s = Setup("M15", "buy", 100.0, 95.0, 110.0, T0.isoformat(), 1)
    r = Result(s, outcome)
    return r


class TestNoOrders(unittest.TestCase):
    def test_the_module_calls_no_execution_function(self):
        import bot.backtest as m
        with open(m.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("order_send", "order_check", "positions_close", "send_order("):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, src)


class TestItNeverReadsTheFuture(unittest.TestCase):
    """
    ⭐⭐⭐ **وهذا الفرق بين قياسٍ وبين خداعِ النفس.**

    لو أُعطيت السلسلةُ شمعةً لم تُغلق بعد — أو شموعَ تأكيدٍ لاحقةً
    للحظة القرار — لخرج الرقمُ مبهرًا وكاذبًا.
    """

    def test_confirm_bars_are_cut_at_the_decision_moment(self):
        conf = series("M3", 3, 20)
        cut = _upto(conf, T0 + timedelta(minutes=15))
        self.assertEqual(len(cut), 6)                    # 0,3,6,9,12,15
        self.assertLessEqual(cut[-1].time, T0 + timedelta(minutes=15))

    def test_a_moment_before_the_first_bar_yields_nothing(self):
        conf = series("M3", 3, 20)
        self.assertEqual(len(_upto(conf, T0 - timedelta(minutes=1))), 0)

    def test_the_whole_series_passes_when_the_moment_is_later(self):
        conf = series("M3", 3, 20)
        self.assertEqual(len(_upto(conf, T0 + timedelta(days=9))), 20)

    def test_the_window_never_exceeds_the_current_bar(self):
        """
        السلسلة تُعطى `poi[:i+1]` — فآخرُ شمعةٍ فيها هي شمعةُ القرار،
        ولا شمعةَ بعدها. ويُتحقَّق منه بمراقبة ما يصل إلى `evaluate`.
        """
        import bot.backtest as m
        poi, conf = series("M15", 15, 12), series("M3", 3, 60)
        seen = []
        original = m.evaluate

        def spy(p, c, cfg, *a, **k):
            seen.append((len(p), p[-1].time, c[-1].time if len(c) else None))
            return original(p, c, cfg, *a, **k)

        m.evaluate = spy
        try:
            decisions(poi, conf, "M15", "M3", spread=0.3)
        finally:
            m.evaluate = original

        self.assertEqual(len(seen), 12)
        for n, poi_last, conf_last in seen:
            self.assertLessEqual(conf_last, poi_last,
                                 "شمعةُ تأكيدٍ بعد لحظة القرار — قراءةُ مستقبل")

    def test_the_window_is_bounded(self):
        import bot.backtest as m
        poi, conf = series("M15", 15, 30), series("M3", 3, 150)
        sizes = []
        original = m.evaluate
        m.evaluate = lambda p, c, cfg, *a, **k: (sizes.append(len(p)),
                                                 original(p, c, cfg, *a, **k))[1]
        try:
            decisions(poi, conf, "M15", "M3", spread=0.3, window=5)
        finally:
            m.evaluate = original
        self.assertLessEqual(max(sizes), 5)


class TestRange(unittest.TestCase):
    def test_since_and_until_bound_the_walk(self):
        import bot.backtest as m
        poi, conf = series("M15", 15, 40), series("M3", 3, 200)
        seen = []
        original = m.evaluate
        m.evaluate = lambda p, c, cfg, *a, **k: (seen.append(p[-1].time),
                                                 original(p, c, cfg, *a, **k))[1]
        try:
            decisions(poi, conf, "M15", "M3", spread=0.3,
                      since=T0 + timedelta(minutes=60),
                      until=T0 + timedelta(minutes=120))
        finally:
            m.evaluate = original
        self.assertTrue(all(T0 + timedelta(minutes=60) <= t
                            <= T0 + timedelta(minutes=120) for t in seen))
        self.assertEqual(len(seen), 5)       # 60,75,90,105,120


class TestRender(unittest.TestCase):
    def test_no_difference_is_said_plainly(self):
        """⭐ «لا أثر» رقمٌ كباقي الأرقام — ولا يُخفى."""
        runs = [("بلا هارمونيك", [], []), ("مع الهارمونيك", [], [])]
        self.assertIn("لا أثر", render(runs))

    def test_the_limits_are_printed_with_the_number_not_after_it(self):
        runs = [("أ", [], []), ("ب", [], [])]
        self.assertIn("الملتبس يُحسب خسارة", render(runs))


class TestTheRefineFloorRuleIsReallyWired(unittest.TestCase):
    """
    ⛔ صنفُ العطب الذي تكرّر أربع مرّات: **بندٌ معلَنٌ لا يعمل.**

    فقياسٌ يُذكر في تعليقٍ ولا وجود له في `--rule` وعدٌ كاذب. وهذه
    الاختباراتُ تمنع ذلك على `refine-floor` بعينه.
    """

    def test_the_rule_is_an_accepted_choice(self):
        import argparse
        import bot.backtest as m
        seen = {}
        original = argparse.ArgumentParser.add_argument

        def spy(self, *a, **kw):
            if a and a[0] == "--rule":
                seen["choices"] = kw.get("choices", ())
            return original(self, *a, **kw)

        argparse.ArgumentParser.add_argument = spy
        try:
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    m.main(["--help"])
                except SystemExit:
                    pass
        finally:
            argparse.ArgumentParser.add_argument = original
        self.assertIn("refine-floor", seen.get("choices", ()))

    def test_the_override_key_is_a_real_config_field(self):
        """فمفتاحٌ مخطئٌ يرفع TypeError — لا يُبلع بصمت."""
        from bot.chain import ChainConfig
        cfg = ChainConfig("M15", "M3", spread=0.3, refine_floor_to_stop=True)
        self.assertTrue(cfg.refine_floor_to_stop)

    def test_an_unknown_override_would_be_caught_not_swallowed(self):
        from bot.chain import ChainConfig
        with self.assertRaises(TypeError):
            ChainConfig("M15", "M3", spread=0.3, refine_floor_to_stopp=True)

    def test_it_is_off_in_the_default_config(self):
        """⛔ «قِس قبل أن تغيّر» — فلا يُشغَّل قبل أن يُقاس."""
        from bot.chain import ChainConfig
        self.assertFalse(ChainConfig("M15", "M3", spread=0.3)
                         .refine_floor_to_stop)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestTheOutputSurvivesBeingSavedToAFile(unittest.TestCase):
    """
    ⛔⛔ **قياسٌ لا يُحفظ في ملفّ قياسٌ ناقص** — وقع 2026-09-26.

    على ويندوز يسقط الترميز إلى `cp1252` عند `> out.txt`، فينهار
    أوّلُ سطرٍ فيه `⛔` أو حرفٌ عربيّ — **قبل جلب شمعةٍ واحدة**.

    ⚠️ ولا ينهار على الشاشة. فهو «يصمت حتّى يُحتاج».
    """

    BANNER = "⛔ قياسٌ على التاريخ — ولا أوامر تُرسل."

    def _cp1252_stdout(self):
        import io
        return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="")

    def test_the_defect_reproduces_on_a_cp1252_stream(self):
        """فلولا الإصلاح لانهار السطرُ الأوّل."""
        stream = self._cp1252_stdout()
        with self.assertRaises(UnicodeEncodeError):
            stream.write(self.BANNER)

    def test_utf8_console_rescues_that_same_stream(self):
        import sys
        from bot.replay import utf8_console
        stream = self._cp1252_stdout()
        original = sys.stdout
        sys.stdout = stream
        try:
            utf8_console()
            sys.stdout.write(self.BANNER)        # ⇐ لا يرفع
        finally:
            sys.stdout = original
        self.assertEqual(stream.encoding, "utf-8")

    def test_it_never_raises_on_a_stream_that_cannot_be_reconfigured(self):
        """⛔ ولا يُسقط القياسَ مجرًى لا يقبل الضبط."""
        import sys
        from bot.replay import utf8_console
        original = sys.stdout
        sys.stdout = object()                    # بلا reconfigure
        try:
            utf8_console()                       # ⇐ يبتلع بهدوء
        finally:
            sys.stdout = original

    def test_both_entry_points_call_it_before_printing(self):
        import inspect
        import bot.backtest as b
        import bot.replay as r
        for mod in (b, r):
            src = inspect.getsource(mod.main)
            self.assertIn("utf8_console()", src)


class TestTheComparisonTableDoesNotMislead(unittest.TestCase):
    """
    ⛔⛔ **عطبان في أداةِ القياس صُحّحا 2026-09-27** — وكلاهما يضلّل
    القارئ في الأداة **التي تخرج منها كلُّ نتيجةٍ في هذا المشروع**.
    """

    @staticmethod
    def _res(outcome):
        from bot.replay import Result, Setup
        s = Setup(timeframe="M15", direction="buy", entry=4300.0,
                  stop=4295.0, target=4310.0,
                  first_seen="2026-09-14T10:00")
        return Result(setup=s, outcome=outcome)

    def setUp(self):
        self.a = [self._res("tp1"), self._res("stop"), self._res("unfilled")]
        self.b = [self._res("tp1"), self._res("tp1")]
        self.c = [self._res("stop"), self._res("open")]

    def test_three_variants_still_get_a_difference_line(self):
        """
        ⛔ **كان `if len(runs) == 2` فقط.** و`refine-pick` ثلاثُ صيغ
        و`refine` أربع ⇒ فتُطبع الأرقامُ **بلا سطرِ فرق**، ويُترك
        القارئُ يحسب بعينه — **وهو موضعُ الخطأ بعينه**.
        """
        from bot.backtest import render
        out = render([("القائم", self.a, []), ("ب١", self.b, []),
                      ("ب٢", self.c, [])])
        self.assertIn("والفروقُ مقيسةٌ على «القائم»", out)
        self.assertIn("ب١", out)
        self.assertIn("ب٢", out)

    def test_the_baseline_is_the_first_variant(self):
        """⭐ والأولى هي «القائم» في كلّ صيغةٍ بنيتُها — فالفرقُ عليها."""
        from bot.backtest import render
        out = render([("القائم", self.a, []), ("ب", self.b, [])])
        self.assertIn("+15.00$", out)          # 20 − 5

    def test_unfilled_and_open_are_visible(self):
        """
        ⛔ **`Outcome` خمسُ قيمٍ والجدولُ كان يُظهر ثلاثًا** ⇒ لا تجمع
        الأعمدةُ عددَ الإعدادات ولا يعرف القارئُ لماذا. و«لم تُملأ»
        **واقعةٌ في السجلّ** (أسبوع 09-21: تسعٌ إحداها لم تُملأ).
        """
        from bot.backtest import render
        out = render([("القائم", self.a, [])])
        self.assertIn("لم تُملأ", out)
        self.assertIn("معلَّق", out)

    def test_the_columns_now_add_up_to_the_setup_count(self):
        """⭐ وهذا هو الفحصُ الذي يمنع عودةَ العطب: مجموعٌ يُطابق."""
        from bot.replay import tally
        t = tally(self.a)
        shown = sum(t.get(k, 0) for k in
                    ("tp1", "stop", "ambiguous", "unfilled", "open"))
        self.assertEqual(shown, len(self.a))

    def test_no_effect_is_stated_explicitly(self):
        from bot.backtest import render
        out = render([("القائم", self.a, []), ("ب", list(self.a), [])])
        self.assertIn("لا أثر", out)

    def test_every_new_rule_has_a_variant_block(self):
        """
        ⭐ **وحارسٌ للمفاتيح الأربعة الجديدة**: قاعدةٌ في `choices` بلا
        صيغٍ تسقط إلى الهارمونيك صامتةً — **فيُقاس غيرُ المطلوب**.
        """
        import inspect

        from bot import backtest
        src = inspect.getsource(backtest.main)
        for rule in ("swings", "refine-pick", "impulse", "protected"):
            with self.subTest(rule=rule):
                self.assertIn(f'args.rule == "{rule}"', src)


class TestADataDefectIsNotAMarketVerdict(unittest.TestCase):
    """
    ⛔⛔ **RW2 — «وقتٌ لا يُقرأ» كان يُرجَع `unfilled`. صُحّح 2026-09-27.**

    و«لم تُملأ» **حكمٌ على السوق**: بلغ الإعلانُ ولم يبلغ السعرُ
    الدخول. **و«وقتٌ لا يُقرأ» عطبُ بياناتٍ** — فخلطُهما يضيف صفوفًا
    وهميّةً إلى عدّ الإعدادات **ويُخفي العطب**.
    """

    def test_an_unreadable_timestamp_is_not_called_unfilled(self):
        from bot.replay import Setup, walk
        s = Setup(timeframe="M15", direction="buy", entry=4300.0,
                  stop=4295.0, target=4310.0, first_seen="ليس وقتًا")
        self.assertEqual(walk([], s).outcome, "unreadable")

    def test_walk_managed_agrees(self):
        from bot.replay import Setup, walk_managed
        s = Setup(timeframe="M15", direction="buy", entry=4300.0,
                  stop=4295.0, target=4310.0, first_seen="-")
        self.assertEqual(walk_managed([], s).outcome, "unreadable")

    def test_the_report_shouts_when_any_row_is_unreadable(self):
        """⭐ **ويصيح** — فعطبُ بياناتٍ صامتٌ يُقرأ نتيجةً."""
        from bot.backtest import render
        from bot.replay import Result, Setup
        s = Setup(timeframe="M15", direction="buy", entry=4300.0,
                  stop=4295.0, target=4310.0,
                  first_seen="2026-09-14T10:00")
        out = render([("القائم", [Result(setup=s, outcome="unreadable")], [])])
        self.assertIn("غيرُ مقروء", out)
        self.assertIn("عطبُ بياناتٍ لا حكمُ سوق", out)

    def test_a_clean_run_says_nothing_about_it(self):
        """⚠️ ولا يُصاح بلا سبب — وإنذارٌ كاذبٌ مرّةً يُعلَّم أن يُتجاهَل."""
        from bot.backtest import render
        from bot.replay import Result, Setup
        s = Setup(timeframe="M15", direction="buy", entry=4300.0,
                  stop=4295.0, target=4310.0,
                  first_seen="2026-09-14T10:00")
        out = render([("القائم", [Result(setup=s, outcome="tp1")], [])])
        self.assertNotIn("غيرُ مقروء", out)
