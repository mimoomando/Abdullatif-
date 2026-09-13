"""
اختبارات حلقة التشغيل.

⛔ الحدّ الأول: **لا أمر يُرسَل.** وضع الورق يسجّل ما كان سيفعله.
⚠️ والثاني: **المتانة** — أسبوعٌ يسقط في ليلته الثالثة لا يعطي أسبوعًا.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.runner import (
    DEFAULT_PAIRS,
    OffsetProbe,
    Recorder,
    RunConfig,
    package,
    render_package,
    run_once,
)

T0 = datetime(2026, 9, 5, 9, 0)


# دقائقُ كل إطار — كي تختلف أوقاتُ الشموع بين إطار نقطة الاهتمام
# وإطار التأكيد، كما تختلف في الواقع. وبلا هذا يصير الإطاران شمعةً
# واحدة، فلا يُختبَر شيءٌ يخصّ ترابطهما.
STEP_MINUTES = {"M3": 3, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}


def series(tf, n=40, base=100.0):
    step = STEP_MINUTES.get(tf, 15)
    return Series(tf, [
        Candle(T0 + timedelta(minutes=step * i),
               base + i, base + i + 2, base + i - 2, base + i + 1)
        for i in range(n)
    ], symbol="XAUUSD.m")


class FakeBridge:
    """جسر زائف — يقرأ فقط، تمامًا كالحقيقي."""

    def __init__(self, spread=0.30, fail_on=(), spread_fails=False,
                 offset=3.0, offset_fails=False):
        self.spread_value = spread
        self.fail_on = set(fail_on)
        self.spread_fails = spread_fails
        self.offset_value = offset
        self.offset_fails = offset_fails
        self.offset_calls = 0
        self.fetched = []

    def measure_server_offset(self):
        self.offset_calls += 1
        if self.offset_fails:
            from bot.mt5_bridge import StaleTick
            raise StaleTick("السوق مغلق")
        return self.offset_value

    def spread(self):
        if self.spread_fails:
            raise RuntimeError("لا تِكّة")
        return self.spread_value

    def fetch(self, tf, count):
        self.fetched.append(tf)
        if tf in self.fail_on:
            raise RuntimeError(f"عطب {tf}")
        return series(tf)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = RunConfig(out_dir=self.tmp.name, save_charts=False)
        self.rec = Recorder(self.cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        with open(self.cfg.journal_path, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh]


class TestNoOrders(unittest.TestCase):
    """⛔ أهمّ اختبار: الوحدة لا تعرف كيف تأمر."""

    def test_the_module_calls_no_execution_function(self):
        import bot.runner as m
        with open(m.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("order_send", "order_check", "positions_close", "send_order("):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, src)

    def test_execution_stays_blocked(self):
        from bot import guards
        self.assertFalse(guards.EXECUTION_ENABLED)


class TestSetupRepetition(Base):
    """
    ⭐ **أكبر بندٍ منفرد في خسارة أسبوع الملاحظة** — ومقيسٌ عليه:

        20 إعدادًا متمايزًا   ⇒  −10.21$
        60 قرارًا كما سُجّلت  ⇒  −316.26$

    نفس الأوردر بلوك، ما زال `fresh`، فيُعلَن في كل شمعة جديدة —
    أحدها **تسع مرّات**. وعلى حساب حقيقيّ: فتح الصفقة نفسها كل ربع
    ساعة.
    """

    def rec_row(self, **kw):
        row = dict(poi_tf="M15", candle_time="2026-09-10T20:30:00",
                   direction="buy", entry=4369.16, stop=4359.16,
                   disposition="taken")
        row.update(kw)
        return row

    def test_the_same_setup_is_recognised_across_candles(self):
        first = self.rec_row()
        self.rec.write(first)
        later = self.rec_row(candle_time="2026-09-10T20:45:00")
        self.assertEqual(self.rec.announced_at(later), "2026-09-10T20:30:00")

    def test_a_different_stop_is_a_different_setup(self):
        self.rec.write(self.rec_row())
        self.assertIsNone(self.rec.announced_at(self.rec_row(stop=4360.00)))

    def test_a_different_direction_is_a_different_setup(self):
        self.rec.write(self.rec_row())
        self.assertIsNone(self.rec.announced_at(self.rec_row(direction="sell")))

    def test_cents_below_the_second_decimal_do_not_split_a_setup(self):
        """الأوردر بلوك الواحد يعطي الرقم نفسه — والزغب العشري لا يفرّقه."""
        self.rec.write(self.rec_row())
        self.assertIsNotNone(self.rec.announced_at(self.rec_row(entry=4369.1601)))

    def test_a_rejected_record_never_claims_a_setup(self):
        """المرفوضات تُسجَّل كلها — الفحص الراسب المعدود هو ما يضبط المعاملات."""
        self.rec.write(self.rec_row(disposition="rejected"))
        self.assertIsNone(self.rec.announced_at(self.rec_row()))

    def test_a_record_without_an_entry_has_no_setup_key(self):
        self.assertIsNone(Recorder.setup_key(dict(poi_tf="M15", entry=None, stop=None)))

    def test_it_survives_a_restart(self):
        """السجلّ على القرص هو الذاكرة — لا متغيّر في الذاكرة الحيّة."""
        self.rec.write(self.rec_row())
        fresh = Recorder(self.cfg)
        self.assertIsNotNone(fresh.announced_at(self.rec_row(
            candle_time="2026-09-10T21:00:00")))

    def test_the_repeat_is_recorded_not_silenced(self):
        """
        يبقى معدودًا — فلا يضيع من التحليل — لكنه `blocked` لا `taken`،
        فلا يُقرأ تنبيهًا جديدًا.
        """
        self.rec.write(self.rec_row())
        row = self.rec_row(candle_time="2026-09-10T20:45:00")
        first = self.rec.announced_at(row)
        row["disposition"], row["repeat_of"] = "blocked", first
        self.rec.write(row)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["repeat_of"], "2026-09-10T20:30:00")

    def test_a_blocked_repeat_does_not_become_the_new_first(self):
        self.rec.write(self.rec_row())
        self.rec.write(self.rec_row(candle_time="2026-09-10T20:45:00",
                                    disposition="blocked"))
        self.assertEqual(self.rec.announced_at(self.rec_row()),
                         "2026-09-10T20:30:00")


class TestRecordedNotYetRuling(Base):
    """
    ⭐ هيكل المدرّب بقاعدته هو — «ما أغلق تحت بشمعتين» — يُسجَّل في كل
    قرار إلى جانب الهيكل الحاكم.

    ⚠️ **ولا يحكم بعد**: أسبوع 09-07…11 لم يستطع الترجيح (30 شمعة H4
    وتحوّلان اثنان)، فيُسجَّل الرقمان معًا ليحكم الأسبوع القادم
    بمئتَي شمعة.
    """

    def test_every_decision_carries_the_closes_structure(self):
        run_once(FakeBridge(), self.cfg, self.rec)
        for r in self.rows():
            self.assertIn("structure_closes", r)
            self.assertIn(r["structure_closes"],
                          ("bullish", "bearish", "undefined", None))

    def test_it_does_not_decide_the_direction(self):
        """الحقل مرصدٌ لا حاكم — والاتجاه يبقى من `classify_trend`."""
        run_once(FakeBridge(), self.cfg, self.rec)
        import bot.chain as m
        with open(m.__file__, encoding="utf-8") as fh:
            self.assertNotIn("trend_at_close", fh.read())

    def test_the_user_chose_two_closes(self):
        from bot import params as P
        self.assertEqual(P.STRUCTURE_BREAK_CLOSES.value, 2)
        self.assertEqual(P.STRUCTURE_BREAK_CLOSES.origin, "USER")

    def test_every_decision_carries_the_confirm_frame_candle(self):
        """
        ⭐ أسبوع 09-07…11 لم يحفظ إلّا شمعة إطار نقطة الاهتمام، فتعذّر
        قياسُ **تنقيح الدخول** عليه: التنقيح يقع على الإطار المقابل،
        وذلك الإطار غائبٌ عن السجل. فلمّا شُغّلت السلسلة عليه اضطُرّ
        M15 أن يكون إطارَ تأكيد نفسه ⇒ صفرُ تنقيحات — لا لأن القاعدة
        عاطلة بل **لأن البيانات لا تحملها**.
        """
        run_once(FakeBridge(), self.cfg, self.rec)
        for r in self.rows():
            self.assertIn("confirm_candle", r)
            c = r["confirm_candle"]
            self.assertIsNotNone(c)
            for k in ("o", "h", "l", "c", "t"):
                self.assertIn(k, c)

    def test_the_confirm_candle_is_not_the_poi_candle(self):
        """وإلّا لم يُضف السطرُ شيئًا."""
        run_once(FakeBridge(), self.cfg, self.rec)
        pairs = {r["poi_tf"]: r for r in self.rows()}
        for tf, r in pairs.items():
            if r["confirm_tf"] != tf:
                self.assertNotEqual(r["confirm_candle"]["t"], r["candle_time"])

    def test_the_watch_loop_announces_the_offset_once(self):
        """
        ⚠️ كانت تُسجَّل في كل قرار **ولا تُعرَض قطّ** — فقلتُ للمستخدم
        «سيظهر سطر UTC+3» وهو لا يظهر. والانتظارُ لسطرٍ لا يأتي يُقرأ
        عطبًا.
        """
        import bot.runner as m
        with open(m.__file__, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("توقيت الخادم UTC", src)
        self.assertIn("announced", src)

    def test_a_broken_series_records_none_instead_of_crashing(self):
        """تسجيلٌ لا حكم — فعطبه لا يُسقط قرارًا."""
        from bot.runner import _closes_trend
        self.assertIsNone(_closes_trend(None))


class TestRunOnce(Base):
    def test_one_record_per_pair(self):
        n = run_once(FakeBridge(), self.cfg, self.rec)
        self.assertEqual(n, len(DEFAULT_PAIRS))
        self.assertEqual(len(self.rows()), len(DEFAULT_PAIRS))

    def test_a_record_carries_the_full_check_chain(self):
        """سلسلة الفحص هي الجواب على «لماذا لا يجد إعدادات؟»."""
        run_once(FakeBridge(), self.cfg, self.rec)
        r = self.rows()[0]
        self.assertIn("checks", r)
        self.assertTrue(all({"name", "passed", "evidence", "source"} <= set(c)
                            for c in r["checks"]))

    def test_record_carries_disposition_and_spread(self):
        run_once(FakeBridge(spread=0.42), self.cfg, self.rec)
        r = self.rows()[0]
        self.assertIn(r["disposition"], ("accepted", "rejected", "blocked"))
        self.assertAlmostEqual(r["spread"], 0.42)

    def test_the_same_candle_is_not_logged_twice(self):
        """التمريرة تتكرّر كل دقيقة والشمعة نفسها تبقى آخر مغلقة."""
        b = FakeBridge()
        self.assertEqual(run_once(b, self.cfg, self.rec), len(DEFAULT_PAIRS))
        self.assertEqual(run_once(b, self.cfg, self.rec), 0)
        self.assertEqual(len(self.rows()), len(DEFAULT_PAIRS))

    def test_dedupe_survives_a_restart(self):
        """السجل يُقرأ عند الإقلاع — فإعادة التشغيل لا تُكرّر."""
        run_once(FakeBridge(), self.cfg, self.rec)
        fresh = Recorder(self.cfg)
        self.assertEqual(run_once(FakeBridge(), self.cfg, fresh), 0)


class TestRobustness(Base):
    """أسبوعٌ يسقط في ليلته الثالثة لا يعطي أسبوعًا."""

    def test_one_broken_timeframe_does_not_sink_the_rest(self):
        broken = next(iter(DEFAULT_PAIRS))
        n = run_once(FakeBridge(fail_on=[broken]), self.cfg, self.rec)
        self.assertEqual(n, len(DEFAULT_PAIRS) - 1)
        self.assertTrue(os.path.exists(self.cfg.errors_path))

    def test_a_failing_spread_does_not_stop_the_pass(self):
        n = run_once(FakeBridge(spread_fails=True), self.cfg, self.rec)
        self.assertEqual(n, len(DEFAULT_PAIRS))
        self.assertAlmostEqual(self.rows()[0]["spread"], 0.0)

    def test_errors_are_recorded_with_their_place(self):
        run_once(FakeBridge(spread_fails=True), self.cfg, self.rec)
        with open(self.cfg.errors_path, encoding="utf-8") as fh:
            err = json.loads(fh.readline())
        self.assertEqual(err["where"], "spread")
        self.assertIn("error", err)

    def test_a_truncated_line_does_not_destroy_the_journal(self):
        """انقطاعُ كتابةٍ يُتلف سطرًا — لا أسبوعًا."""
        run_once(FakeBridge(), self.cfg, self.rec)
        with open(self.cfg.journal_path, "a", encoding="utf-8") as fh:
            fh.write('{"poi_tf": "H4", "candle_ti')      # سطر مبتور
        pkg = package(self.tmp.name)
        self.assertEqual(pkg["decisions"], len(DEFAULT_PAIRS))
        self.assertEqual(pkg["broken_lines"], 1)

    def test_recorder_reads_a_journal_with_a_bad_line(self):
        with open(self.cfg.journal_path, "w", encoding="utf-8") as fh:
            fh.write("ليس جيسون\n")
        self.assertEqual(Recorder(self.cfg).count(), 0)


class TestCharts(Base):
    def test_charts_are_saved_when_asked(self):
        cfg = RunConfig(out_dir=self.tmp.name, save_charts=True)
        run_once(FakeBridge(), cfg, Recorder(cfg))
        self.assertTrue(os.listdir(cfg.charts_dir))

    def test_the_saved_chart_is_plain(self):
        """
        ⭐ عارٍ عمدًا: ما إن يُرسَم فوقه استنتاجُ البوت حتى يصير الناظر
        يقيّم استنتاج البوت لا شكل السوق.
        """
        cfg = RunConfig(out_dir=self.tmp.name, save_charts=True)
        run_once(FakeBridge(), cfg, Recorder(cfg))
        name = os.listdir(cfg.charts_dir)[0]
        with open(os.path.join(cfg.charts_dir, name), encoding="utf-8") as fh:
            svg = fh.read()
        self.assertIn("<svg", svg)
        for drawn in ("Entry", "SL", "TP1", "OB", "FVG"):
            self.assertNotIn(drawn, svg)


class TestDossiers(unittest.TestCase):
    """
    ⭐ طلب المستخدم: «أريد لكل صفقة سجلًّا خاصًّا — لماذا فتحها، وما
    توافقت، والتاريخ، وكل شيء».
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = RunConfig(out_dir=self.tmp.name, save_charts=False,
                             dossier_max_failed=9)
        self.rec = Recorder(self.cfg)
        run_once(FakeBridge(spread=0.31), self.cfg, self.rec)

    def tearDown(self):
        self.tmp.cleanup()

    def _files(self):
        return [f for f in sorted(os.listdir(self.cfg.dossiers_dir))
                if not f.startswith("000")]

    def _text(self):
        with open(os.path.join(self.cfg.dossiers_dir, self._files()[0]),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_one_file_per_decision(self):
        self.assertEqual(len(self._files()), len(DEFAULT_PAIRS))

    def test_the_file_says_why(self):
        """كل شرط بدليله **ومصدر درسه** — لا حكمًا مجرّدًا."""
        t = self._text()
        self.assertIn("سلسلة الفحص", t)
        self.assertIn("الدليل", t)
        self.assertIn("المصدر", t)

    def test_the_file_carries_the_date_and_frames(self):
        t = self._text()
        self.assertIn("وقت الشمعة", t)
        self.assertIn("الأطر", t)
        self.assertIn("2026-09-05", t)

    def test_the_file_carries_the_market_context(self):
        t = self._text()
        self.assertIn("الشمعة المغلقة", t)
        self.assertIn("السبريد وقتها", t)
        self.assertIn("0.31", t)

    def test_it_counts_what_matched(self):
        self.assertIn("وافق", self._text())

    def test_it_leaves_room_for_the_outcome(self):
        """النتيجة لا تُعرف ساعةَ القرار — فيُترك لها موضع."""
        t = self._text()
        self.assertIn("تُملأ بعد الإغلاق", t)
        self.assertIn("حكمك على الشكل", t)

    def test_the_index_lists_them(self):
        with open(self.cfg.index_path, encoding="utf-8") as fh:
            idx = fh.read()
        self.assertEqual(len(idx.strip().splitlines()), len(DEFAULT_PAIRS))
        for f in self._files():
            self.assertIn(f, idx)

    def test_the_journal_points_at_the_file(self):
        with open(self.cfg.journal_path, encoding="utf-8") as fh:
            rows = [json.loads(l) for l in fh]
        self.assertTrue(all(r["dossier"] for r in rows))

    def test_noisy_rejects_are_filtered_out(self):
        """
        بلا حدٍّ تصير الملفّات مئات لا تُقرأ. والافتراضي يُبقي المقبولة
        وما رسب بفحصٍ واحد — وتلك أنفع ما في الأسبوع.
        """
        with tempfile.TemporaryDirectory() as d:
            cfg = RunConfig(out_dir=d, save_charts=False, dossier_max_failed=0)
            run_once(FakeBridge(), cfg, Recorder(cfg))
            files = [f for f in os.listdir(cfg.dossiers_dir)
                     if not f.startswith("000")]
            self.assertEqual(files, [])

    def test_dossiers_can_be_switched_off(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = RunConfig(out_dir=d, save_charts=False, save_dossiers=False)
            run_once(FakeBridge(), cfg, Recorder(cfg))
            self.assertFalse(os.path.isdir(cfg.dossiers_dir))

    def test_package_counts_them(self):
        self.assertEqual(package(self.tmp.name)["dossiers"], len(DEFAULT_PAIRS))


class TestServerOffset(Base):
    """
    ⭐ قيس على جهاز المستخدم: **UTC+3** (2026-09-05، بعد فتح السوق).

    الأوقات كلها بوقت الخادم — وهو الصواب: قواعد المدرّب عن تسلسل
    الشموع، وما في الملفّ يطابق ما في MT5. لكن أسبوعًا من الطوابع
    **بلا منطقة زمنية مرفقة** لا يُعرف منه أيّ شمعة وقعت في أيّ جلسة.
    """

    def test_the_offset_rides_along_with_every_decision(self):
        run_once(FakeBridge(offset=3.0), self.cfg, self.rec, OffsetProbe())
        self.assertTrue(all(r["server_utc_offset"] == 3.0 for r in self.rows()))

    def test_it_is_measured_once_not_every_pass(self):
        b, probe = FakeBridge(), OffsetProbe()
        run_once(b, self.cfg, self.rec, probe)
        run_once(b, self.cfg, self.rec, probe)
        self.assertEqual(b.offset_calls, 1)

    def test_a_closed_market_does_not_stop_recording(self):
        """السوق مغلق ⇒ لا إزاحة — والتسجيل يمضي."""
        n = run_once(FakeBridge(offset_fails=True), self.cfg, self.rec, OffsetProbe())
        self.assertEqual(n, len(DEFAULT_PAIRS))
        self.assertTrue(all(r["server_utc_offset"] is None for r in self.rows()))

    def test_it_keeps_retrying_until_the_market_opens(self):
        b, probe = FakeBridge(offset_fails=True), OffsetProbe()
        run_once(b, self.cfg, self.rec, probe)          # تفشل ⇒ تتباطأ
        b.offset_fails = False
        for _ in range(4):                              # تمريراتٌ تستنفد المهلة
            run_once(b, self.cfg, self.rec, probe)
        self.assertEqual(probe.value, 3.0)

    def test_it_backs_off_instead_of_retrying_every_pass(self):
        """
        ⭐ سوقٌ مغلق كتب **3632 خطأً** في أسبوع الملاحظة، أغلبها من
        هنا: محاولةٌ في كل تمريرة ونصُّ الخطأ واحد. فالتباطؤ يُبقي
        الخطأ الحقيقيّ ظاهرًا بدل أن يغرق بين آلاف النسخ.
        """
        b, probe = FakeBridge(offset_fails=True), OffsetProbe()
        for _ in range(40):
            run_once(b, self.cfg, self.rec, probe)
        self.assertLess(b.offset_calls, 10)             # لا أربعون
        self.assertGreater(b.offset_calls, 2)           # ولا يستسلم

    def test_the_backoff_is_bounded(self):
        b, probe = FakeBridge(offset_fails=True), OffsetProbe()
        for _ in range(500):
            run_once(b, self.cfg, self.rec, probe)
        self.assertLessEqual(probe._backoff, OffsetProbe.MAX_BACKOFF)

    def test_without_a_probe_nothing_breaks(self):
        run_once(FakeBridge(), self.cfg, self.rec)
        self.assertTrue(all(r["server_utc_offset"] is None for r in self.rows()))

    def test_the_package_states_the_timezone(self):
        run_once(FakeBridge(offset=3.0), self.cfg, self.rec, OffsetProbe())
        pkg = package(self.tmp.name)
        self.assertEqual(pkg["server_utc_offset"], 3.0)
        self.assertIn("UTC+3", render_package(pkg))

    def test_the_package_says_so_when_it_was_never_measured(self):
        run_once(FakeBridge(offset_fails=True), self.cfg, self.rec, OffsetProbe())
        self.assertIn("لم يُقَس", render_package(package(self.tmp.name)))


class TestPackage(Base):
    def test_empty_directory_packages_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            pkg = package(d)
            self.assertEqual(pkg["decisions"], 0)
            self.assertIn("حصاد التشغيل", render_package(pkg))

    def test_package_counts_failed_checks(self):
        """⭐ الفحص الراسب هو ما يضبط العتبة — فيُعدّ لا يُلخَّص."""
        run_once(FakeBridge(), self.cfg, self.rec)
        pkg = package(self.tmp.name)
        self.assertIsInstance(pkg["failed_checks"], dict)
        self.assertEqual(sum(pkg["by_timeframe"].values()), pkg["decisions"])

    def test_package_reports_the_spread_range(self):
        run_once(FakeBridge(spread=0.5), self.cfg, self.rec)
        self.assertAlmostEqual(package(self.tmp.name)["spread"]["avg"], 0.5)

    def test_render_names_what_to_send(self):
        run_once(FakeBridge(), self.cfg, self.rec)
        out = render_package(package(self.tmp.name))
        self.assertIn("decisions.jsonl", out)
        self.assertIn("الفحوص الراسبة", out)


class TestConfig(unittest.TestCase):
    def test_active_pairs_follow_the_lesson_table(self):
        from bot import params as P
        for poi, confirm in DEFAULT_PAIRS.items():
            with self.subTest(poi=poi):
                self.assertEqual(P.TIMEFRAME_PAIRS.value[poi], confirm)
                self.assertIn(poi, P.ACTIVE_POI_TIMEFRAMES.value)

    def test_paths_sit_under_out_dir(self):
        cfg = RunConfig(out_dir="X")
        for p in (cfg.journal_path, cfg.errors_path, cfg.charts_dir):
            self.assertTrue(p.startswith("X"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
