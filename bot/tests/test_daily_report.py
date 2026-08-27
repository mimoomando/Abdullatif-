"""اختبارات سجل ما بعد إغلاق السوق."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from bot.daily_report import (
    MarketSnapshot,
    SetupRecord,
    build,
    detect_findings,
    split_for_telegram,
)
from bot.data import Candle
from bot.render import Zone, render_svg
from bot.reporting import TradeJournal, TradeRationale
from bot.verdicts import Accuracy

T0 = datetime(2026, 8, 27, 14, 0)
DAY = date(2026, 8, 27)


def snap(**kw) -> MarketSnapshot:
    base = dict(
        day=DAY, symbol="XAUUSD.m",
        open=4360.0, high=4392.0, low=4348.0, close=4381.0,
        structure={"H4": "bullish", "H1": "bullish", "M15": "bullish"},
    )
    base.update(kw)
    return MarketSnapshot(**base)


def rationale(tf="H1", direction="buy", entry=4365.2, stop=4361.0, fails=()) -> TradeRationale:
    r = TradeRationale("XAUUSD.m", direction, tf, "M5", T0)
    r.add("الهيكل صاعد", True, "قمم أعلى", "د9")
    for name in fails:
        r.add(name, False, "لم يتحقق", "د10")
    r.entry, r.stop = entry, stop
    r.targets = [entry + (entry - stop) * 2]
    return r


def journal(r, close_price, outcome, mfe_price=None, mae_price=None) -> TradeJournal:
    j = TradeJournal(rationale=r, opened_at=T0, entry=r.entry)
    for p in (mae_price, mfe_price):
        if p is not None:
            j.observe(T0 + timedelta(minutes=5), p)
    j.close(T0 + timedelta(minutes=40), close_price, outcome)
    return j


class TestSnapshot(unittest.TestCase):
    def test_range_and_net(self):
        s = snap()
        self.assertAlmostEqual(s.range_size, 44.0)
        self.assertAlmostEqual(s.net, 21.0)

    def test_structures_agree(self):
        self.assertTrue(snap().structures_agree)
        self.assertFalse(snap(structure={"H4": "bullish", "H1": "bearish"}).structures_agree)

    def test_undefined_does_not_break_agreement(self):
        s = snap(structure={"H4": "bullish", "H1": "undefined"})
        self.assertTrue(s.structures_agree)


class TestFindings(unittest.TestCase):
    def test_conflicting_structure_is_flagged(self):
        f = detect_findings(snap(structure={"H4": "bullish", "M15": "bearish"}), [])
        self.assertTrue(any("لا تتفق" in x.title for x in f))

    def test_stop_hit_after_reaching_profit(self):
        r = rationale()
        rec = SetupRecord(r, "taken", journal=journal(r, 4361.0, "sl", mfe_price=4372.0))
        f = detect_findings(snap(), [rec])
        hit = [x for x in f if "بعد بلوغ ربح" in x.title]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "high")

    def test_tight_stop_that_survived(self):
        r = rationale()
        rec = SetupRecord(r, "taken", journal=journal(r, 4373.6, "tp", mae_price=4361.3))
        f = detect_findings(snap(), [rec])
        self.assertTrue(any("الوقف ضيّق" in x.title for x in f))

    def test_blocked_winner_is_flagged(self):
        rec = SetupRecord(rationale("M15"), "blocked", hypothetical_r=2.4)
        f = detect_findings(snap(), [rec])
        self.assertTrue(any("محجوبة كانت رابحة" in x.title for x in f))

    def test_small_blocked_winner_not_flagged(self):
        rec = SetupRecord(rationale("M15"), "blocked", hypothetical_r=0.8)
        f = detect_findings(snap(), [rec])
        self.assertFalse(any("محجوبة" in x.title for x in f))

    def test_repeated_rejection_reason(self):
        recs = [
            SetupRecord(rationale(fails=("كسر بزخم",)), "rejected"),
            SetupRecord(rationale(fails=("كسر بزخم",)), "rejected"),
        ]
        f = detect_findings(snap(), recs)
        found = [x for x in f if "يرفض أكثر" in x.title]
        self.assertEqual(len(found), 1)
        self.assertIn("كسر بزخم", found[0].evidence)

    def test_single_rejection_not_flagged(self):
        recs = [SetupRecord(rationale(fails=("كسر بزخم",)), "rejected")]
        self.assertFalse(any("يرفض أكثر" in x.title for x in detect_findings(snap(), recs)))

    def test_sleeping_trade_is_flagged_with_its_gap(self):
        """
        ⭐ المستخدم اختار إبقاء الصفقة مفتوحة خلافًا لنصيحة المدرّب.
        شرط ذلك أن يُقاس الأثر — لا أن يُنسى.
        """
        r = rationale()
        j = journal(r, 4373.6, "tp")
        j.note_session_break(T0, 4368.0, T0 + timedelta(hours=8), 4364.0)
        f = detect_findings(snap(), [SetupRecord(r, "taken", journal=j)])
        hit = [x for x in f if "نامت عبر الإغلاق" in x.title]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "high")      # الفجوة ضدّها
        self.assertIn("-4.00", hit[0].evidence)

    def test_a_helpful_gap_is_only_informational(self):
        r = rationale()
        j = journal(r, 4373.6, "tp")
        j.note_session_break(T0, 4364.0, T0 + timedelta(hours=8), 4368.0)
        f = detect_findings(snap(), [SetupRecord(r, "taken", journal=j)])
        hit = [x for x in f if "نامت عبر الإغلاق" in x.title][0]
        self.assertEqual(hit.severity, "low")
        self.assertIn("0 تضرّرت", hit.evidence)

    def test_trade_that_never_slept_is_not_flagged(self):
        r = rationale()
        rec = SetupRecord(r, "taken", journal=journal(r, 4373.6, "tp"))
        self.assertFalse(any("نامت" in x.title for x in detect_findings(snap(), [rec])))

    def test_quiet_day_with_wide_range(self):
        self.assertTrue(any("لا إعدادات" in x.title for x in detect_findings(snap(), [])))


class TestReport(unittest.TestCase):
    def _report(self):
        r1 = rationale("H1")
        r2 = rationale("M15", entry=4370.0, stop=4366.0)
        return build(
            snap(),
            [
                SetupRecord(r1, "taken", journal=journal(r1, 4373.6, "tp")),
                SetupRecord(r2, "blocked", note="مركز مفتوح — حد المراكز = 1", hypothetical_r=2.1),
                SetupRecord(rationale(fails=("تحت بوابة الـ50%",)), "rejected"),
            ],
        )

    def test_totals(self):
        rep = self._report()
        self.assertEqual(len(rep.taken), 1)
        self.assertEqual(len(rep.closed), 1)
        self.assertEqual(rep.wins, 1)
        self.assertAlmostEqual(rep.total_r, 2.0)

    def test_per_timeframe_breakdown(self):
        rows = self._report().by_timeframe()
        self.assertIn("H1", rows)
        self.assertEqual(rows["H1"]["عدد"], 1)

    def test_render_contains_all_sections(self):
        out = self._report().render()
        for token in ("سجل", "الهيكل", "الإعدادات", "المغلقة", "يستحق النظر"):
            self.assertIn(token, out)

    def test_render_marks_each_disposition(self):
        out = self._report().render()
        self.assertIn("✅ نُفِّذت", out)
        self.assertIn("🔔 تنبيه", out)
        self.assertIn("⛔ مرفوضة", out)

    def test_render_states_the_rejection_reason(self):
        self.assertIn("تحت بوابة الـ50%", self._report().render())

    def test_render_warns_against_small_sample(self):
        self.assertIn("لا تُنتج قاعدة", self._report().render())

    def test_machine_block_is_valid_json(self):
        block = self._report().machine_block()
        payload = json.loads(block.split("\n", 1)[1].rsplit("\n", 2)[0])
        self.assertEqual(payload["symbol"], "XAUUSD.m")
        self.assertEqual(len(payload["setups"]), 3)
        self.assertEqual(payload["setups"][0]["disp"], "taken")

    def test_machine_block_carries_rejection_reasons(self):
        payload = json.loads(self._report().machine_block().split("\n", 1)[1].rsplit("\n", 2)[0])
        self.assertIn("تحت بوابة الـ50%", payload["setups"][2]["failed"])

    def test_empty_day_renders(self):
        out = build(snap(), []).render()
        self.assertIn("لا شيء", out)


class TestVerdictWiring(unittest.TestCase):
    """⭐ حلقة الحكم: السجل يسأل، والمستخدم يردّ، والردّ يعود إلى نفس السجل."""

    def _report(self):
        r1 = rationale("H1")
        return build(
            snap(),
            [
                SetupRecord(r1, "taken", journal=journal(r1, 4373.6, "tp")),
                SetupRecord(rationale("M15", fails=("كسر بزخم",)), "rejected", near_miss=True),
            ],
        )

    def test_report_asks_for_a_verdict(self):
        out = self._report().render()
        self.assertIn("بانتظار الحكم", out)
        self.assertIn("1 · 2", out)

    def test_no_prompt_when_there_is_nothing_to_judge(self):
        self.assertNotIn("بانتظار الحكم", build(snap(), []).render())

    def test_applying_a_reply_attaches_by_display_number(self):
        rep = self._report()
        self.assertEqual(rep.apply_verdicts("1 نعم\n2 لا الشكل ما كان مطابق"), 2)
        self.assertTrue(rep.setups[0].shape_ok)
        self.assertFalse(rep.setups[1].shape_ok)
        self.assertEqual(rep.setups[1].verdict.note, "الشكل ما كان مطابق")

    def test_out_of_range_number_is_ignored(self):
        rep = self._report()
        self.assertEqual(rep.apply_verdicts("9 نعم"), 0)
        self.assertEqual(len(rep.awaiting_verdict), 2)

    def test_prompt_only_lists_what_is_still_unjudged(self):
        rep = self._report()
        rep.apply_verdicts("1 نعم")
        out = rep.render()
        self.assertIn("الإعدادات: 2", out)
        self.assertIn("حكمك: ✅ الشكل مطابق", out)

    def test_prompt_disappears_once_all_are_judged(self):
        rep = self._report()
        rep.apply_verdicts("1 نعم\n2 نعم")
        self.assertNotIn("بانتظار الحكم", rep.render())

    def test_judged_carries_disposition_timeframe_and_near_miss(self):
        rep = self._report()
        rep.apply_verdicts("1 لا\n2 نعم")
        j = rep.judged()
        self.assertTrue(j[0].false_positive)      # نفّذ وشكل خاطئ
        self.assertTrue(j[1].false_negative)      # رفض وشكل صحيح
        self.assertTrue(j[1].near_miss)
        self.assertEqual(j[1].timeframe, "M15")

    def test_machine_block_carries_the_verdict(self):
        rep = self._report()
        rep.apply_verdicts("1 نعم")
        payload = json.loads(rep.machine_block().split("\n", 1)[1].rsplit("\n", 2)[0])
        self.assertEqual(payload["setups"][0]["shape_ok"], True)
        self.assertIsNone(payload["setups"][1]["shape_ok"])
        self.assertTrue(payload["setups"][1]["near_miss"])

    def test_cumulative_accuracy_is_rendered_when_supplied(self):
        rep = self._report()
        rep.apply_verdicts("1 لا\n2 نعم")
        acc = Accuracy()
        acc.add(rep.judged())
        rep.accuracy = acc
        out = rep.render()
        self.assertIn("دقة الشكل", out)
        self.assertIn("إيجابية كاذبة", out)

    def test_no_accuracy_section_without_judgements(self):
        rep = self._report()
        rep.accuracy = Accuracy()
        self.assertNotIn("دقة الشكل", rep.render())


def window(n=6):
    return [
        Candle(T0 + timedelta(minutes=5 * i), 4360.0 + i, 4364.0 + i, 4358.0 + i, 4362.0 + i)
        for i in range(n)
    ]


class TestJudgingPacket(unittest.TestCase):
    """
    ⭐ «حتى لو لم أعرف أين الخطأ… أرسل السجل إليك وأنت تحكم».

    الحزمة تحمل ما يلزم للحكم على الشكل، وتحجب خلاصات البوت عمدًا —
    لأن الحاكم لو رآها حكم بها لا بالشكل.
    """

    def _report(self):
        r1 = rationale("H1")
        return build(
            snap(),
            [
                SetupRecord(r1, "taken", journal=journal(r1, 4373.6, "tp"), window=window()),
                SetupRecord(
                    rationale("M15", fails=("كسر بزخم",)), "rejected",
                    near_miss=True, window=window(4),
                ),
            ],
        )

    def _payload(self, rep=None):
        text = (rep or self._report()).judging_packet()
        return json.loads(text.split("```json\n", 1)[1].rsplit("\n```", 1)[0])

    def test_packet_carries_raw_candles(self):
        p = self._payload()
        self.assertEqual(len(p["setups"][0]["candles"]), 6)
        self.assertEqual(len(p["setups"][0]["candles"][0]), 5)   # وقت + OHLC

    def test_packet_carries_the_levels_the_setup_was_built_on(self):
        lv = self._payload()["setups"][0]["levels"]
        self.assertAlmostEqual(lv["entry"], 4365.2)
        self.assertAlmostEqual(lv["stop"], 4361.0)
        self.assertTrue(lv["targets"])

    def test_packet_withholds_the_bots_conclusions(self):
        """⭐ الحجب شرط صحة القياس: بلا حجب يصادق الحاكم على البوت."""
        blob = json.dumps(self._payload(), ensure_ascii=False)
        for leak in ("كسر بزخم", "disp", "near_miss", "rejected", "taken"):
            with self.subTest(leak=leak):
                self.assertNotIn(leak, blob)

    def test_packet_withholds_the_outcome(self):
        """الرابحة قد يكون شكلها خاطئًا — والسؤال عن الشكل وحده."""
        p = self._payload()
        self.assertNotIn("r", p["setups"][0])
        self.assertNotIn("2.0", json.dumps(p["setups"][0]["levels"]))

    def test_packet_states_what_it_withheld(self):
        self.assertIn("سبب الرفض", self._payload()["withheld"])

    def test_packet_warns_about_setups_without_candles(self):
        rep = build(snap(), [SetupRecord(rationale("H1"), "taken")])
        text = rep.judging_packet()
        self.assertIn("إعدادات بلا شموع", text)
        self.assertIn("تصديقًا لا مراجعة", text)

    def test_no_warning_when_every_setup_has_candles(self):
        self.assertNotIn("إعدادات بلا شموع", self._report().judging_packet())

    def test_assistant_verdict_with_candles_counts_as_independent(self):
        rep = self._report()
        rep.apply_verdicts("1 لا\n2 نعم", by="assistant")
        j = rep.judged()
        self.assertTrue(all(x.by == "assistant" for x in j))
        self.assertTrue(all(x.independent for x in j))

    def test_assistant_verdict_without_candles_is_not_independent(self):
        rep = build(snap(), [SetupRecord(rationale("H1"), "taken")])
        rep.apply_verdicts("1 لا", by="assistant")
        self.assertFalse(rep.judged()[0].independent)

    def test_packet_fits_telegram_after_splitting(self):
        parts = split_for_telegram(self._report().judging_packet())
        self.assertTrue(all(len(p) <= 4200 for p in parts))


class TestCharts(unittest.TestCase):
    """
    ⭐ صورتان لكل إعداد ولكلٍّ غرض — والخلط بينهما يفسد القياس.

    المشروحة للدراسة: ترى أين رسم البوت مناطقه.
    العارية للحكم: ما إن يُرسم فوقها استنتاج البوت حتى يصير الناظر
    يقيّم استنتاجه لا شكل السوق.
    """

    def _record(self):
        return SetupRecord(
            rationale("H1"), "taken", window=window(),
            zones=[Zone(4366.0, 4362.0, "OB H1", "ob")],
        )

    def test_annotated_scene_carries_what_the_bot_drew(self):
        s = self._record().scene(setup_id=1)
        self.assertEqual(len(s.zones), 1)
        labels = " ".join(lv.label for lv in s.levels)
        self.assertIn("Entry", labels)
        self.assertIn("SL", labels)
        self.assertIn("TP1", labels)
        self.assertIn("#1", s.title)

    def test_chart_labels_survive_png_conversion(self):
        """
        ⭐ محوّلات SVG→PNG لا تصل العربية ولا تعكس اتجاهها، فتخرج «شراء»
        مقلوبة «ءارش». الصورة المقروءة خطأً أسوأ من صورة بلا تسمية.
        """
        s = self._record().scene(setup_id=1)
        text = s.title + " " + " ".join(lv.label for lv in s.levels)
        arabic = [ch for ch in text if "؀" <= ch <= "ۿ"]
        self.assertEqual(arabic, [], f"حرف عربي على الشارت: {text}")

    def test_plain_scene_carries_nothing_but_candles(self):
        s = self._record().scene(setup_id=1, plain=True)
        self.assertEqual(s.zones, [])
        self.assertEqual(s.levels, [])
        self.assertEqual(len(s.candles), 6)

    def test_plain_svg_leaks_no_conclusion(self):
        svg = render_svg(self._record().scene(setup_id=1, plain=True))
        for leak in ("OB", "Entry", "SL", "TP"):
            with self.subTest(leak=leak):
                self.assertNotIn(leak, svg)

    def test_annotated_svg_shows_the_zone(self):
        self.assertIn("OB H1", render_svg(self._record().scene()))

    def test_scene_without_candles_is_an_error(self):
        with self.assertRaises(ValueError):
            SetupRecord(rationale("H1"), "taken").scene()

    def test_write_charts_emits_both_kinds(self):
        rep = build(snap(), [self._record(), self._record()])
        with tempfile.TemporaryDirectory() as d:
            paths = rep.write_charts(d)
            self.assertEqual(len(paths["annotated"]), 2)
            self.assertEqual(len(paths["plain"]), 2)
            for p in paths["annotated"] + paths["plain"]:
                self.assertTrue(os.path.exists(p))

    def test_setups_without_candles_are_skipped_not_faked(self):
        rep = build(snap(), [SetupRecord(rationale("H1"), "taken")])
        with tempfile.TemporaryDirectory() as d:
            paths = rep.write_charts(d)
            self.assertEqual(paths, {"annotated": [], "plain": []})

    def test_chart_filenames_carry_day_and_setup_number(self):
        rep = build(snap(), [self._record()])
        with tempfile.TemporaryDirectory() as d:
            name = os.path.basename(rep.write_charts(d)["plain"][0])
            self.assertIn("20260827", name)
            self.assertIn("setup1", name)


class TestSplit(unittest.TestCase):
    def test_short_text_is_one_part(self):
        self.assertEqual(len(split_for_telegram("سطر واحد")), 1)

    def test_long_text_is_split_and_numbered(self):
        parts = split_for_telegram("\n".join(f"سطر رقم {i}" for i in range(400)), limit=500)
        self.assertGreater(len(parts), 1)
        self.assertIn("(1/", parts[0])
        self.assertTrue(all(len(p) <= 600 for p in parts))

    def test_lines_are_never_cut_mid_way(self):
        text = "\n".join(f"القيمة {i} = {i * 3.5}" for i in range(200))
        rejoined = "\n".join(p.split("\n\n(")[0] for p in split_for_telegram(text, limit=300))
        self.assertEqual(rejoined, text)

    def test_oversized_line_is_kept_whole(self):
        long_line = "x" * 700
        parts = split_for_telegram(long_line, limit=300)
        self.assertEqual(len(parts), 1)
        self.assertIn(long_line, parts[0])

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            split_for_telegram("x", limit=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
