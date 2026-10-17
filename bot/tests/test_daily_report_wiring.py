"""
حُرّاسُ وصلِ `daily_report` من السجلّ المكتوب — **2026-10-17.**

╔══════════════════════════════════════════════════════════════════╗
║  ⭐⭐⭐ **ولمَ ملفٌّ ثانٍ؟** لأنّ `test_daily_report.py` يفحص         ║
║  **الوحدةَ** (اللقطة · التناقضات · العرض · الحكم)، وهذه تفحص      ║
║  **الطريقَ إليها**: السجلُّ ⇒ تقرير. وهما سؤالان.                   ║
║                                                                  ║
║  ⛔ **وكلُّ حارسٍ هنا سلوكيٌّ لا نصّيّ** — فمن نزع البندَ وبقي       ║
║  السطرُ أسقط الطقم. **وهو درسُ TM1 (10-16): حارسٌ يقرأ نصَّ         ║
║  `evaluate` صمت حين نُزع `return` منه.**                          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import os
import tempfile
import unittest
from datetime import date

from bot import daily_report as dr
from bot import replay
from bot.reporting import TradeRationale
from datetime import datetime


def _row(**kw):
    """صفُّ قرارٍ كما يكتبه `runner` — بأقلّ ما يلزم، والباقي يُمرَّر."""
    row = dict(
        v=1, symbol="XAUUSD", poi_tf="M15", confirm_tf="M3",
        candle_time="2026-10-09T10:00:00",
        candle={"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5},
        spread=0.25, disposition="rejected", note="",
        direction="buy", entry=None, stop=None, stop_reason="",
        targets=[], target_reason="", blocked_reason="",
        checks=[], structure_closes="bullish",
    )
    row.update(kw)
    return row


def _check(name, passed=True, evidence="", source=""):
    return dict(name=name, passed=passed, evidence=evidence, source=source)


def _log(rows):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


# ─────────────────────────── المدخل يُبرهِن على نفسه ───────────────────────────


class TestTheEntryPointRuns(unittest.TestCase):
    """⭐ 635 سطرًا **لم تُنفَّذ قطّ** — فالحارسُ الأوّل أنّها تُنفَّذ."""

    def test_main_returns_zero_on_a_real_log(self):
        path = _log([
            _row(candle_time="2026-10-09T10:00:00",
                 checks=[_check("الهيكل محدد", False, "range")]),
            _row(candle_time="2026-10-09T10:15:00", disposition="taken",
                 entry=100.2, stop=99.0, targets=[102.0, 103.0],
                 candle={"o": 100.0, "h": 103.5, "l": 99.5, "c": 103.0},
                 checks=[_check("الهيكل محدد", True, "bullish — آخر قمة 1")]),
        ])
        try:
            self.assertEqual(0, dr.main(["--day", "2026-10-09",
                                         "--log", path]))
        finally:
            os.unlink(path)

    def test_a_missing_log_is_refused_not_silently_empty(self):
        self.assertEqual(1, dr.main(["--day", "2026-10-09",
                                     "--log", "لا-وجود-له.jsonl"]))

    def test_a_bad_date_is_refused(self):
        self.assertEqual(1, dr.main(["--day", "2026-13-99"]))


# ─────────────────────────── موضعُ التمايز واحد ───────────────────────────


class TestOnePlaceForDistinctness(unittest.TestCase):
    """
    ⛔ **`setups_from` قشرةٌ على `setups_with_rows`** — ومن كتب
    تمايزًا ثانيًا في `daily_report` **أسقط الطقم**.
    """

    def test_setups_from_delegates(self):
        rows = [
            _row(disposition="taken", entry=100.0, stop=99.0,
                 targets=[102.0], candle_time="2026-10-09T10:00:00"),
            _row(disposition="taken", entry=100.0, stop=99.0,
                 targets=[102.0], candle_time="2026-10-09T10:15:00"),
        ]
        plain = replay.setups_from(rows)
        paired = replay.setups_with_rows(rows)
        self.assertEqual(1, len(plain))            # ⬅ متمايزٌ واحد
        self.assertEqual([s for s in plain], [s for s, _ in paired])
        self.assertEqual(2, plain[0].announcements)

    def test_the_default_disposition_is_taken_so_old_callers_are_untouched(self):
        rows = [_row(disposition="blocked", entry=100.0, stop=99.0,
                     targets=[102.0])]
        self.assertEqual([], replay.setups_from(rows))
        self.assertEqual(1, len(replay.setups_with_rows(rows, "blocked")))

    def test_daily_report_uses_setup_key_not_its_own(self):
        """⭐ `Setup.key()` موجودةٌ — فلا يُكتب مفتاحٌ ثانٍ بجوارها."""
        import inspect
        src = inspect.getsource(dr)
        self.assertNotIn("def _key(", src)
        self.assertIn(".key() in taken_keys", src)


# ─────────────────────────── DR1 ───────────────────────────


class TestDR1TheDossierDoesNotCallATakenTradeRejected(unittest.TestCase):
    """
    ⛔⛔⛔ **14 من 16 صفقةً أُخذت وملفُّها يقول [إعداد مرفوض]** —
    لأنّ `accepted` تعني [وافق كلَّ شرط]، **والتنقيحُ فحصٌ غيرُ قاتل.**
    """

    def _rationale(self):
        r = TradeRationale(symbol="XAUUSD", direction="buy",
                           poi_timeframe="M15", confirm_timeframe="M3",
                           detected_at=datetime(2026, 10, 9, 10, 0),
                           entry=100.0, stop=99.0, targets=[102.0])
        r.add("الهيكل محدد", True, "bullish", "د")
        r.add("تنقيح الدخول داخل المنطقة", False,
              "من حدّ المنطقة · «بدون تأكيد ما بنصح»", "د")
        return r

    def test_the_case_is_real_a_taken_trade_fails_a_check(self):
        self.assertFalse(self._rationale().accepted)

    def test_an_empty_head_prints_no_verdict_word(self):
        out = self._rationale().render(head="")
        self.assertNotIn("إعداد مرفوض", out)
        self.assertNotIn("صفقة مقترحة", out)
        self.assertIn("شراء XAUUSD", out)

    def test_the_default_head_describes_the_checks_not_a_decision(self):
        out = self._rationale().render()
        self.assertNotIn("إعداد مرفوض", out)
        self.assertIn("رسب فيه 1 فحصًا", out)
        self.assertIn("والقرارُ ليس هنا", out)

    def test_a_caller_may_still_name_the_head(self):
        self.assertIn("صفقة أُعلنت",
                      self._rationale().render(head="صفقة أُعلنت"))

    def test_the_runner_dossier_never_calls_a_taken_trade_rejected(self):
        """⭐⭐⭐ **سلوكيٌّ عبر `runner` نفسِه** — لا قراءةَ نصِّ ملفّ."""
        from bot.data import Candle, Series
        from bot.runner import dossier_text

        class _R:
            disposition = "taken"
            note = ""

            def __init__(self, rationale):
                self.rationale = rationale

        bars = [Candle(datetime(2026, 10, 9, 10, 0), 100, 101, 99, 100.5)]
        text = dossier_text(_R(self._rationale()), "M15", "M3",
                            Series("M15", bars), 0.25, None)
        self.assertNotIn("إعداد مرفوض", text)


# ─────────────────────────── فخُّ المحجوب المكرَّر ───────────────────────────


class TestTheBlockedDuplicateIsNotAMissedChance(unittest.TestCase):
    """
    ⛔⛔⛔ **24 من 24 محجوبًا في السجلّ هو الإعدادُ المأخوذُ نفسُه.**
    فلو حُسب لها [ماذا كان سيحدث] أعلن التقريرُ 24 فرصةً رابحةً
    محجوبة — **وهي الصفقاتُ التي أخذها البوت.**
    """

    def _rows(self):
        base = dict(entry=100.0, stop=99.0, targets=[102.0],
                    checks=[_check("الهيكل محدد", True, "bullish — قمة")])
        return [
            _row(disposition="taken", candle_time="2026-10-09T10:00:00",
                 candle={"o": 100.0, "h": 103.0, "l": 99.5, "c": 102.5},
                 **base),
            _row(disposition="blocked", candle_time="2026-10-09T10:15:00",
                 blocked_reason="الإعداد نفسه أُعلن — تكرارٌ لا تنبيه",
                 candle={"o": 102.0, "h": 103.0, "l": 101.0, "c": 102.5},
                 **base),
        ]

    def test_the_duplicate_is_dropped_and_counted(self):
        rows = self._rows()
        read = dr.LogRead()
        recs = dr.records_of(rows, rows, "M15", read)
        self.assertEqual(1, read.blocked_duplicate)
        self.assertEqual(0, read.blocked_fresh)
        self.assertEqual(["taken"], [r.disposition for r in recs])

    def test_it_is_shouted_not_swallowed(self):
        rows = self._rows()
        read = dr.LogRead()
        dr.records_of(rows, rows, "M15", read)
        self.assertTrue(any("تكرارُ إعلان" in s for s in read.shouts()))

    def test_no_missed_chance_finding_is_raised_for_it(self):
        path = _log(self._rows())
        try:
            report, _ = dr.from_log(path, date(2026, 10, 9), "M15")
        finally:
            os.unlink(path)
        self.assertNotIn("فرصة محجوبة كانت رابحة",
                         [f.title for f in report.findings])

    def test_a_blocked_setup_with_no_twin_still_gets_its_number(self):
        """⚠️ **والفرعُ حيٌّ ينتظر حالتَه** — فالصفرُ مقيسٌ لا مبنيّ."""
        rows = [
            _row(disposition="blocked", candle_time="2026-10-09T10:00:00",
                 entry=100.0, stop=99.0, targets=[102.0],
                 blocked_reason="حدُّ المركز الواحد",
                 checks=[_check("الهيكل محدد", True, "bullish — قمة")]),
            _row(disposition="rejected", candle_time="2026-10-09T10:15:00",
                 candle={"o": 100.0, "h": 103.0, "l": 99.5, "c": 102.5}),
        ]
        read = dr.LogRead()
        recs = dr.records_of(rows, rows, "M15", read)
        self.assertEqual(1, read.blocked_fresh)
        self.assertEqual(0, read.blocked_duplicate)
        blocked = [r for r in recs if r.disposition == "blocked"]
        self.assertEqual(1, len(blocked))
        self.assertIsNotNone(blocked[0].hypothetical_r)


# ─────────────────────────── العجزُ يُصاح به ───────────────────────────


class TestTheGapsAreShouted(unittest.TestCase):
    """⭐ عرفُ المشروع: [اجعلها تكتب سطرًا حين لا تعمل]."""

    def test_a_day_with_no_bars_says_so(self):
        read = dr.LogRead()
        snap = dr.snapshot_of([], date(2026, 10, 9), "M15", "closes", read)
        self.assertEqual(0, snap.range_size)
        self.assertTrue(any("لا شمعةَ واحدةٌ" in s for s in read.shouts()))

    def test_a_recording_gap_is_named(self):
        rows = [_row(candle_time="2026-10-09T10:00:00"),
                _row(candle_time="2026-10-09T18:00:00")]
        read = dr.LogRead()
        dr.snapshot_of(rows, date(2026, 10, 9), "M15", "closes", read)
        self.assertTrue(any("فجوةُ تسجيل" in s for s in read.shouts()))

    def test_an_unreadable_structure_is_counted_not_read_as_undefined(self):
        """⚠️ **عجزُ قراءةٍ عندي، لا [هيكلًا غيرَ محدَّد]** — حدُّ `instructor`."""
        rows = [_row(checks=[_check("الهيكل محدد", True, "لا-وسمَ-هنا")])]
        read = dr.LogRead()
        snap = dr.snapshot_of(rows, date(2026, 10, 9), "M15", "swings", read)
        self.assertEqual({}, snap.structure)
        self.assertEqual(1, read.unreadable_structure)
        self.assertTrue(any("عجزُ قراءةٍ عندي" in s for s in read.shouts()))

    def test_the_structure_reader_is_borrowed_not_rewritten(self):
        """⛔ **موضعٌ واحدٌ للانتزاع** — و`instructor` هو صاحبُه."""
        from bot.instructor import trend_from_checks
        import inspect
        self.assertIn("trend_from_checks", inspect.getsource(dr.snapshot_of))
        self.assertEqual("bullish",
                         trend_from_checks([_check("الهيكل محدد", True,
                                                   "bullish — آخر قمة 1")]))

    def test_an_unknown_structure_field_is_refused(self):
        with self.assertRaises(ValueError):
            dr.snapshot_of([], date(2026, 10, 9), "M15", "خيال")


# ─────────────────────────── النافذةُ تُطلَب صريحًا ───────────────────────────


class TestTheCandleWindowIsAskedFor(unittest.TestCase):
    """
    ⚠️⚠️ **`saw_candles` يُشتقُّ من وجود النافذة** — وهو ما يجعل حكمَ
    المساعد **مراجعةً مستقلّة**. فمن ملأها بلا صورةٍ جعل التصديقَ
    يُحسب مراجعة.
    """

    def _rows(self):
        return [_row(disposition="taken", candle_time="2026-10-09T10:00:00",
                     entry=100.0, stop=99.0, targets=[102.0],
                     checks=[_check("الهيكل محدد", True, "bullish — قمة")]),
                _row(candle_time="2026-10-09T10:15:00",
                     candle={"o": 100.0, "h": 103.0, "l": 99.5, "c": 102.5})]

    def test_off_by_default(self):
        rows = self._rows()
        recs = dr.records_of(rows, rows, "M15", dr.LogRead())
        self.assertEqual([], recs[0].window)
        self.assertFalse(dr.build(
            dr.snapshot_of(rows, date(2026, 10, 9), "M15"),
            recs).judged()[0].saw_candles)

    def test_asked_for_it_arrives(self):
        rows = self._rows()
        recs = dr.records_of(rows, rows, "M15", dr.LogRead(), window=3)
        self.assertTrue(recs[0].window)


if __name__ == "__main__":
    unittest.main(verbosity=2)
