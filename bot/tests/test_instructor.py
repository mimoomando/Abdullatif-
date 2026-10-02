"""
اختبارات تسجيل أحكام المدرّب.

⛔ الشرط الحاكم لهذه الوحدة: **لا تُعدَّل مقولةٌ بعد رؤية نتيجتها.**
وكل اختبار هنا يحرس بابًا من أبواب ذلك.
"""

import json
import os
import pathlib
import tempfile
import unittest

from bot import instructor as ins

from bot.instructor import (
    Call,
    InvalidCall,
    Scorecard,
    Verdict,
    append,
    compare,
    latest,
    load,
    score,
    validate,
)


def call(day="2026-09-14", tf="H4", bias="bearish", quote="هيكلنا هابط", **kw):
    return Call(day=day, timeframe=tf, bias=bias, quote=quote, **kw)


class TestValidation(unittest.TestCase):
    """⛔ الحكم الناقص يُرفض **وقت تسجيله** لا وقت استعماله."""

    def test_a_call_without_a_quote_is_refused(self):
        """بلا نصٍّ لا يمكنك مراجعة ترجمتي — وهي بيت الداء."""
        with self.assertRaises(InvalidCall):
            validate(call(quote="   "))

    def test_a_bias_outside_the_three_is_refused(self):
        with self.assertRaises(InvalidCall):
            validate(call(bias="صاعد نوعًا ما"))

    def test_a_bad_date_is_refused(self):
        with self.assertRaises(InvalidCall):
            validate(call(day="الاثنين"))

    def test_a_call_without_a_timeframe_is_refused(self):
        with self.assertRaises(InvalidCall):
            validate(call(tf=""))

    def test_a_complete_call_passes_and_comes_back_unchanged(self):
        c = call()
        self.assertIs(validate(c), c)


class TestAppendOnly(unittest.TestCase):
    """الإلحاق وحده يضمن أن ما سُجّل الاثنين لا يتغيّر الجمعة."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "calls", "instructor.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_it_writes_and_reads_back(self):
        append(self.path, call())
        got = load(self.path)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].bias, "bearish")
        self.assertEqual(got[0].quote, "هيكلنا هابط")

    def test_an_invalid_call_never_reaches_the_file(self):
        with self.assertRaises(InvalidCall):
            append(self.path, call(quote=""))
        self.assertEqual(load(self.path), [])

    def test_a_second_call_does_not_erase_the_first(self):
        append(self.path, call(day="2026-09-14"))
        append(self.path, call(day="2026-09-15", bias="bullish"))
        self.assertEqual([c.day for c in load(self.path)],
                         ["2026-09-14", "2026-09-15"])

    def test_levels_survive_the_round_trip(self):
        append(self.path, call(levels={"flip_above": 4510.0}))
        self.assertEqual(load(self.path)[0].levels, {"flip_above": 4510.0})

    def test_a_truncated_line_does_not_lose_the_week(self):
        append(self.path, call())
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write('{"day": "2026-09-1')
        self.assertEqual(len(load(self.path)), 1)

    def test_a_missing_file_is_empty_not_an_error(self):
        self.assertEqual(load("/لا/يوجد.jsonl"), [])


class TestVoiding(unittest.TestCase):
    """
    ⭐ إن تبيّن أن التسجيل خطأ فالصواب **إبطاله صراحةً** لا إعادة
    صياغته: الإبطال يُعَدّ ويظهر، والصياغة الجديدة تختفي.
    """

    def test_a_voided_call_is_not_scored(self):
        c = call(void="التبس عليّ إطار الساعة بالأربع ساعات")
        card = score([c], {"2026-09-14": "bearish"}, "قاعدة", "H4")
        self.assertEqual(card.n, 0)
        self.assertEqual(card.hits, 0)

    def test_a_voided_call_still_shows_in_the_report(self):
        """⚠️ الإبطال الصامت أسوأ من الخطأ — فهو يُطبَع بسببه."""
        c = call(void="سببٌ ما")
        out = score([c], {"2026-09-14": "bearish"}, "قاعدة", "H4").render()
        self.assertIn("مُبطَل", out)
        self.assertIn("سببٌ ما", out)

    def test_a_void_does_not_displace_a_live_call_for_that_day(self):
        live = call(bias="bearish")
        dead = call(bias="bullish", void="أُبطل")
        self.assertEqual(latest([live, dead])["2026-09-14"].bias, "bearish")

    def test_the_later_live_call_of_a_day_wins(self):
        """قد يتكلّم عن الإطار نفسه مرّتين في اليوم."""
        a = call(bias="bearish", quote="أوّل الجلسة")
        b = call(bias="bullish", quote="بعد فتح نيويورك")
        self.assertEqual(latest([a, b])["2026-09-14"].bias, "bullish")


class TestScoring(unittest.TestCase):
    def test_agreement_and_disagreement_are_counted(self):
        calls = [call(day="2026-09-14", bias="bearish"),
                 call(day="2026-09-15", bias="bullish")]
        card = score(calls, {"2026-09-14": "bearish", "2026-09-15": "bearish"},
                     "إغلاقان", "H4")
        self.assertEqual((card.hits, card.n), (1, 2))

    def test_a_day_without_a_measurement_is_dropped_not_failed(self):
        """
        ⚠️ السلسلة قد تبدأ بعد اليوم أو تنقطع — وذلك **عيب التغطية**
        لا عيب القاعدة. (وقد وقع: الاثنين خرج `undefined` في كل
        القواعد لأن سلسلة الأسبوع تبدأ عنده.)
        """
        calls = [call(day="2026-09-14"), call(day="2026-09-15")]
        card = score(calls, {"2026-09-15": "bearish"}, "قاعدة", "H4")
        self.assertEqual(card.n, 1)

    def test_only_the_timeframe_asked_for_is_compared(self):
        calls = [call(tf="H4", bias="bearish"), call(tf="H1", bias="bullish")]
        self.assertEqual(latest(calls, timeframe="H4")["2026-09-14"].bias,
                         "bearish")

    def test_a_call_about_another_timeframe_is_never_scored(self):
        """
        ⭐ **الخطأ الذي وقع فعلًا** في أوّل تشغيلٍ لهذه الوحدة: حكم
        الجمعة كان عن **إطار الساعة** («على إطار الساعة عملنا ماركت
        ستراكتشر شفت») فقِستُه على هيكل **الأربع ساعات** وسجّلتُه
        خطأً — وهو ليس خطأً أصلًا.
        """
        h1 = call(tf="H1", bias="bullish",
                  quote="على إطار الساعة عملنا ماركت ستراكتشر شفت")
        card = score([h1], {"2026-09-14": "bearish"}, "قاعدة", "H4")
        self.assertEqual(card.n, 0)

    def test_the_same_day_on_two_frames_is_scored_on_each_alone(self):
        calls = [call(tf="H4", bias="bearish"), call(tf="H1", bias="bullish")]
        m = {"2026-09-14": "bearish"}
        self.assertEqual(score(calls, m, "ق", "H4").hits, 1)
        self.assertEqual(score(calls, m, "ق", "H1").hits, 0)


class TestCompareRefusesToOverreach(unittest.TestCase):
    """
    ⭐⭐ هذا هو الدرس المستفاد من أسبوع 09-07…11 مكتوبًا كودًا.

    تقاربت القواعد (1/5 · 1/5 · 2/5) فلم يترجّح شيء — وكان الصواب أن
    يُقال «لا حكم»، لا أن يُختار الأعلى.
    """

    def _cards(self, *scores):
        out = []
        for i, s in enumerate(scores):
            card = Scorecard(f"قاعدة {i}")
            for j in range(5):
                c = call(day=f"2026-09-1{j}")
                card.verdicts.append(Verdict(c, "bearish", j < s))
            out.append(card)
        return out

    def test_a_narrow_lead_is_declared_no_verdict(self):
        out = compare(self._cards(2, 1), min_gap=2)
        self.assertIn("لا حكم", out)
        self.assertNotIn("يسبق", out)

    def test_a_clear_lead_is_declared(self):
        out = compare(self._cards(5, 1), min_gap=2)
        self.assertIn("يسبق", out)
        self.assertNotIn("لا حكم", out)

    def test_a_tie_is_no_verdict(self):
        self.assertIn("لا حكم", compare(self._cards(3, 3), min_gap=2))

    def test_the_weeks_actual_numbers_would_have_been_refused(self):
        """⭐ 1/5 · 1/5 · 2/5 — بالضبط ما وقع، والعتبة ترفضه."""
        self.assertIn("لا حكم", compare(self._cards(1, 1, 2), min_gap=2))

    def test_no_measurements_at_all_says_so(self):
        self.assertIn("لا قياس", compare([Scorecard("قاعدة")]))

    def test_one_rule_alone_is_not_a_comparison(self):
        self.assertIn("لا مقارنة", compare(self._cards(4)))

    def test_every_rule_is_printed_even_the_losers(self):
        """⚠️ لا تُطوى القاعدة الخاسرة — فطيُّها يخفي ضيق الفارق."""
        out = compare(self._cards(5, 1), min_gap=2)
        self.assertIn("قاعدة 0", out)
        self.assertIn("قاعدة 1", out)


class TestRender(unittest.TestCase):
    def test_the_quote_is_always_shown(self):
        """نصُّه هو ما يسمح لك بمراجعة ترجمتي — فلا يُطوى."""
        self.assertIn("هيكلنا هابط", call().render())

    def test_levels_are_shown_when_present(self):
        self.assertIn("4510", call(levels={"flip_above": 4510.0}).render())


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestTheVoidingMechanismDoesNotReach(unittest.TestCase):
    """
    ⛔⛔⛔ **IN1 — وُصف 2026-09-30 · ولم يُختَر فيه.**

    الترويسة: [وإن تبيّن أن تسجيلها خطأ فالصواب **إبطالها صراحةً**].
    والملفُّ إلحاقيٌّ ⇒ فالإبطالُ سطرٌ جديدٌ يحمل `void`.
    **و`latest` يتخطّاه** لأنّ الحكمَ الحيَّ سبقه.

    ⚠️⚠️ **وليس سهوًا**: السلوكُ مثبَّتٌ في
    `test_a_void_does_not_displace_a_live_call_for_that_day` أعلاه.
    ⇒ فهما **نيّتان معلنتان تتصادمان**، والقرارُ منهجيٌّ للمستخدم.
    """

    def _pair(self):
        live = call(bias="bullish", quote="تحيّزي إيجابي")
        void = call(bias="bullish", quote="تحيّزي إيجابي",
                    void="سُجّل خطأً — وصف الصعود تصحيحًا")
        return live, void

    def test_appending_a_void_does_not_void_the_day(self):
        live, void = self._pair()
        got = latest([live, void])["2026-09-14"]
        self.assertTrue(got.live, "⇒ الإبطالُ لم يصل")
        self.assertEqual(got.void, "")

    def test_and_so_the_voided_call_is_still_counted(self):
        live, void = self._pair()
        card = score([live, void], {"2026-09-14": "bullish"}, "قاعدة", "H4")
        self.assertEqual(card.n, 1)
        self.assertEqual(card.hits, 1, "⇒ حكمٌ أُبطل وما زال يُصيب")

    def test_voiding_works_only_when_it_was_there_from_the_start(self):
        """
        ⇒ أي **إلّا في الحالة التي لا يُحتاج فيها إليه**: و[إن تبيّن]
        تعني بعدَ التسجيل لا معه.
        """
        _, void = self._pair()
        self.assertEqual(score([void], {"2026-09-14": "bullish"},
                               "قاعدة", "H4").n, 0)

    def test_the_collision_is_written_where_it_lives(self):
        self.assertIn("IN1", latest.__doc__)
        self.assertIn("نيّتان معلنتان تتصادمان", latest.__doc__)


class TestTheWiringReadsTheLiveLog(unittest.TestCase):
    """
    ⭐⭐⭐ **وُصلت الوحدةُ 2026-10-02** — وهذه اختباراتُ الوصل نفسِه.

    وكانت أوّلَ سطرٍ في `UNWIRED`: مبنيّةٌ ومختبَرةٌ **ولا يبلغها
    مدخلُ تشغيل**. ⇒ فصار لها `__main__`، وصارت تقرأ
    `runs/decisions.jsonl`.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.log = os.path.join(self.dir, "decisions.jsonl")

    def _write(self, rows):
        with open(self.log, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    @staticmethod
    def _row(day, tf="M15", closes="bullish", passed=True, ev="bullish — قمّة"):
        return {"poi_tf": tf, "candle_time": f"{day}T05:00:00",
                "structure_closes": closes,
                "checks": [{"name": "الهيكل محدد", "passed": passed,
                            "evidence": ev}]}

    def test_it_reads_the_clean_field(self):
        self._write([self._row("2026-09-30")])
        got, cov = ins.measured_from_log(self.log, "M15", "closes")
        self.assertEqual(got, {"2026-09-30": "bullish"})
        self.assertEqual(cov.unreadable, 0)

    def test_another_timeframe_is_ignored(self):
        """⚠️ وحكمٌ على إطارٍ لا يُقاس على إطارٍ آخر — وهو خطأٌ وقع."""
        self._write([self._row("2026-09-30", tf="H1", closes="bearish")])
        got, _ = ins.measured_from_log(self.log, "M15", "closes")
        self.assertEqual(got, {})

    def test_the_last_candle_of_the_day_wins(self):
        """
        ⭐ **وهذا اختياري أنا ويُقال**: المدرّبُ يحكم على اليوم كلِّه،
        والسجلُّ فيه عشراتُ الشموع. **واختيارُ الأولى يعطي رقمًا آخر.**
        """
        rows = [self._row("2026-09-30", closes="bearish")]
        rows.append({**self._row("2026-09-30", closes="bullish"),
                     "candle_time": "2026-09-30T23:45:00"})
        self._write(rows)
        got, _ = ins.measured_from_log(self.log, "M15", "closes")
        self.assertEqual(got["2026-09-30"], "bullish")

    def test_an_unparsable_evidence_is_counted_not_swallowed(self):
        """
        ⛔⛔ **وهذا بندُ المشروع**: [اجعلها تكتب سطرًا حين لا تعمل].

        فهيكلُ `classify_trend` **انتزاعٌ من نصٍّ حرّ** لا حقلٌ نظيف.
        ⇒ والعجزُ **يُعَدّ**، ولا يُقرأ [هيكلًا غيرَ محدَّد] — وهما
        شيئان: عجزُ قراءةٍ عندي · وحكمُ البوت.
        """
        self._write([self._row("2026-09-30", ev="??? غيرُ مفهوم")])
        got, cov = ins.measured_from_log(self.log, "M15", "swings")
        self.assertEqual(got, {})
        self.assertEqual(cov.unreadable, 1)

    def test_a_failed_structure_check_is_the_bots_own_verdict(self):
        """⚠️ و`passed=False` ليس عجزًا — بل البوتُ يقول [غير محدَّد]."""
        self._write([self._row("2026-09-30", passed=False, ev="لا قمم كافية")])
        got, cov = ins.measured_from_log(self.log, "M15", "swings")
        self.assertEqual(got, {"2026-09-30": "undefined"})
        self.assertEqual(cov.unreadable, 0)

    def test_a_missing_log_is_empty_not_a_crash(self):
        got, cov = ins.measured_from_log(os.path.join(self.dir, "ghost"),
                                         "M15", "closes")
        self.assertEqual((got, cov.days), ({}, 0))


class TestTheEntryPointProvesItself(unittest.TestCase):
    """⛔ ومدخلُ التشغيل يلزمه `__main__` — وإلّا فهو اسمٌ بلا برهان."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.calls = os.path.join(self.dir, "instructor.jsonl")

    def test_it_has_a_main(self):
        src = pathlib.Path("bot/instructor.py").read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":', src)

    def test_add_writes_and_rejects(self):
        ok = ins.main(["--calls", self.calls, "add", "--day", "2026-09-30",
                       "--tf", "M15", "--bias", "bullish",
                       "--quote", "اشترينا اليوم الصبح على 4182"])
        self.assertEqual(ok, 0)
        self.assertEqual(len(ins.load(self.calls)), 1)
        # ⛔ وحكمٌ بلا نصّ يُرفض — ولا يُكتب
        bad = ins.main(["--calls", self.calls, "add", "--day", "2026-09-30",
                        "--tf", "M15", "--bias", "bullish", "--quote", "  "])
        self.assertEqual(bad, 1)
        self.assertEqual(len(ins.load(self.calls)), 1)

    def test_a_broken_level_is_refused_not_guessed(self):
        for bad in ("entry", "entry=غير-رقم"):
            with self.subTest(level=bad):
                rc = ins.main(["--calls", self.calls, "add",
                               "--day", "2026-09-30", "--tf", "M15",
                               "--bias", "bullish", "--quote", "نصّ",
                               "--level", bad])
                self.assertEqual(rc, 1)

    def test_scoring_with_no_calls_says_so_and_fails(self):
        """⚠️ ولا يُطبع صفرٌ من صفر كأنّه قياس."""
        rc = ins.main(["--calls", self.calls, "score"])
        self.assertEqual(rc, 1)

    def test_the_void_path_shouts_that_IN1_is_open(self):
        """
        ⛔⛔ **IN1 صار مبلوغًا بالوصل** — والإبطالُ ما زال لا يعمل.

        ⇒ فيُصاح به **في اللحظة التي يعضّ فيها**، لا في ترويسةٍ لا
        تُقرأ. وهو بندُ المشروع: [اجعلها تكتب سطرًا حين لا تعمل].
        """
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ins.main(["--calls", self.calls, "add", "--day", "2026-09-30",
                      "--tf", "M15", "--bias", "bullish", "--quote", "نصّ",
                      "--void", "ترجمةٌ خاطئة"])
        self.assertIn("IN1", buf.getvalue())


class TestTheBiasIsReadByARuleNotByMyJudgement(unittest.TestCase):
    """
    ⭐⭐⭐ **بطلب المستخدم 2026-10-02**: [انا لا اريد ان اقول لك شيء
    — اريدك ان تستنتج من السجل].

    ⚠️ وترويسةُ الوحدة تحذّر من الترجمة — **والخشيةُ هناك ليست من
    الآليّة بل من أن أُترجم بعد أن أرى النتيجة**. وقاعدةٌ مكتوبةٌ
    تُطبَّق على كلّ يومٍ سواءً **لا ترى نتيجةً أصلًا**.
    """

    @staticmethod
    def _doc(body):
        return "# ترويسةٌ كتابتي أنا — ولا تُقرأ\n\n```\n" + body + "\n```\n"

    def test_a_plain_stance_is_read(self):
        got, ev, _ = ins.read_bias(self._doc("انا تحليلي هابط وليس صاعد"))
        self.assertEqual(got, "bearish")
        self.assertTrue(ev)

    def test_a_substring_inside_another_word_is_not_a_match(self):
        """
        ⛔⛔⛔ **عطبٌ وقع فعلًا — 2026-10-02.**

        البحثُ بالنصّ الجزئيّ التقط [بعنا] **داخل** «الارتداد
        **تبعنا** من بريكر بلوك» ⇒ فصار تحليلُ 09-07 **هابطًا على
        دليلٍ ليس من كلامه**.

        ⭐ **ولولا أنّ الدليل يُطبع لمرّ** — فالأدلّةُ تُعرَض لا تُبتلَع.
        """
        got, ev, _ = ins.read_bias(
            self._doc("وهون نحن الارتداد تبعنا من بريكر بلوك"))
        self.assertEqual(got, "undefined")
        self.assertEqual(ev, [])

    def test_the_waw_prefix_is_still_the_same_word(self):
        """⚠️ «**و**بعنا» عطفٌ لا جزءٌ من الفعل — فتُقبل."""
        got, _, _ = ins.read_bias(self._doc("طلعنا معه وبعنا من مناطق ال 29"))
        self.assertEqual(got, "bearish")

    def test_a_stance_inside_a_condition_does_not_count(self):
        """
        ⛔⛔ **الفخُّ الأكبر**: «**في حال** غير هيكل برجع بحترم الهبوط»
        شرطٌ لا حكم. ⇒ ويُسقَط **ويُسمّى**، لا يُبتلَع.
        """
        got, ev, dropped = ins.read_bias(self._doc(
            "فانا بحترم الصعود وبصعد معه في حال غير هيكل برجع بحترم الهبوط"))
        self.assertEqual(got, "bullish")
        self.assertEqual(len(dropped), 1)
        self.assertIn("شرط", dropped[0])

    def test_a_deed_already_done_is_not_voided_by_a_nearby_condition(self):
        """
        ⭐ «**اذا** انت منك مشتري من تحت · نحن امبارح **اشترينا**» —
        والشرطُ على جملةٍ أخرى، **وهو اشترى فعلًا**.
        """
        got, ev, _ = ins.read_bias(self._doc(
            "اذا انت منك مشتري من تحت نحن امبارح اشترينا على 4140"))
        self.assertEqual(got, "bullish")
        self.assertIn("قد يكون سردَ صفقةٍ سابقة", ev[0])

    def test_a_timestamp_line_must_not_cut_a_phrase_in_half(self):
        """
        ⛔⛔ **عطبٌ ثانٍ وقع**: «فانا بحترم» ⏎ [2:01 دقيقتان وثانية] ⏎
        «الصعود» ⇒ فعبارةُ [بحترم الصعود] **لا تُطابَق أبدًا**.
        """
        got, _, _ = ins.read_bias(self._doc(
            "فانا بحترم\n2:01 دقيقتان وثانية\nالصعود وبصعد معه"))
        self.assertEqual(got, "bullish")

    def test_two_opposite_stances_give_undefined_not_a_guess(self):
        """⛔ ولا يُرجَّح: [غير محدَّد] **حالةٌ لا عجز**."""
        got, _, _ = ins.read_bias(
            self._doc("انا تحليلي هابط … ونحن مكملين صعود"))
        self.assertEqual(got, "undefined")

    def test_only_the_fenced_block_is_read(self):
        """⭐ **فالترويسةُ كتابتي أنا** — وعرفُ `bot.quotes` نفسُه."""
        doc = "# وأنا أقول انا تحليلي هابط\n\n```\nلا عبارةَ موقفٍ هنا\n```\n"
        got, ev, _ = ins.read_bias(doc)
        self.assertEqual((got, ev), ("undefined", []))

    def test_plain_direction_words_are_not_a_stance(self):
        """
        ⚠️ **و«هبوط» و«صعود» وحدَهما لا تُحسبان** — فالمدرّبُ يصف حركةَ
        السوق في كلّ جملة، **ووصفُ الحركة ليس حكمًا**.
        """
        got, _, _ = ins.read_bias(self._doc(
            "صار في عننا هبوط كثير قوي وعنيف وبعدها صعود"))
        self.assertEqual(got, "undefined")
