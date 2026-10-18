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


class TestABareVoidStillReachesNothing(unittest.TestCase):
    """
    ⛔⛔⛔ **IN1 — وُصف 2026-09-30، وأُغلق 2026-10-16 بالطريق ②.**

    ⚠️⚠️ **وهذه الاختباراتُ تبقى كما هي، وتُقرأ على وجهها الصحيح:**
    **سطرٌ يحمل `void` وحدَه ما زال لا يُبطل شيئًا** — وذلك
    **سلوكُ ما سُجّل قبل 10-16 بعينه**، فلا يتغيّر معناه بأثرٍ
    رجعيّ. **والذي صار يُبطل هو `voids`** (انظر الصنف التالي).

    ⭐ **ولو قُلب الاستثناءُ (الطريق ①) لانقلب معنى كلّ سطرٍ
    قديمٍ في الملفّ** — وهو الثمنُ الذي رجّح ②.
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


class TestTheVoidingMechanismNowReaches(unittest.TestCase):
    """
    ✅✅✅ **IN1 أُغلق 2026-10-16 بطلب المستخدم** [ابن كل شيء من غير
    ما ترجع لي] — **بالطريق ② المسجَّل في ترويسة `latest`.**

    **والطريقان كانا مكتوبين بثمنيهما**، و② اختير لأنّ ثمنَ ①
    كان موصوفًا سلفًا: [سطرُ `void` الشاردُ يمحو حكمًا حيًّا].
    ⇒ **فالسجلُّ هو الذي رجّح، لا ذوقي.**
    """

    def _live(self):
        return call(bias="bullish", quote="تحيّزي إيجابي")

    def _annul(self, day="2026-09-14", reason="سُجّل خطأً"):
        return call(bias="undefined", quote="(إبطال)",
                    void=reason, voids=day)

    # ── ⭐ والإبطالُ يصل ──

    def test_an_annulment_line_removes_the_day(self):
        """⭐⭐⭐ **وهذا هو ما لم يكن يعمل** — والمُبطَلُ كان يُحسب ويُصيب."""
        got = latest([self._live(), self._annul()])
        self.assertNotIn("2026-09-14", got)

    def test_and_the_annulled_day_is_no_longer_scored(self):
        card = score([self._live(), self._annul()],
                     {"2026-09-14": "bullish"}, "قاعدة", "H4")
        self.assertEqual(card.n, 0, "⇒ لم يعد يُحسب")
        self.assertEqual(card.hits, 0, "⇒ ولم يعد يُصيب")

    def test_the_order_does_not_matter(self):
        """
        ⭐ **ويعمل مهما كان ترتيبُ السطرين** — فالملفُّ إلحاقيٌّ
        والإبطالُ يأتي بعدَه عادةً، **ولا يُبنى على الترتيب.**
        """
        for pair in ((self._live(), self._annul()),
                     (self._annul(), self._live())):
            with self.subTest(order=[c.voids for c in pair]):
                self.assertNotIn("2026-09-14", latest(list(pair)))

    # ── ⛔ والشاردُ لا يمحو شيئًا — وهو ثمنُ ① الذي اجتُنب ──

    def test_a_stray_annulment_for_another_day_erases_nothing(self):
        """
        ⛔⛔⛔ **وهذا هو الفرقُ بين الطريقين بعينه.**

        فتحت ① كان **أيُّ** سطرِ `void` يمحو حكمَ يومه. وتحت ②
        **يسمّي السطرُ يومَه**، فسطرٌ على يومٍ آخرَ لا يمسّ هذا.
        """
        got = latest([self._live(), self._annul(day="2026-09-20")])
        self.assertIn("2026-09-14", got, "⇒ ولم يُمحَ على شاردٍ")
        self.assertTrue(got["2026-09-14"].live)

    def test_an_annulment_on_another_timeframe_does_not_cross_over(self):
        """⚠️ **والإبطالُ على إطاره** — فلا يعبر إلى إطارٍ آخر."""
        other = call(bias="undefined", quote="(إبطال)", tf="M15",
                     void="سببٌ", voids="2026-09-14")
        got = latest([self._live(), other], timeframe="H4")
        self.assertIn("2026-09-14", got)

    # ── ⛔ وسطرُ الإبطال ليس حكمًا ──

    def test_an_annulment_alone_is_not_a_verdict(self):
        """
        ⛔ **وإلّا صار الإبطالُ إثباتًا** — فسطرٌ يُبطل يومًا لا
        يصير هو حكمَ ذلك اليوم ولو كان وحدَه في الملفّ.
        """
        self.assertEqual(latest([self._annul()]), {})
        self.assertEqual(score([self._annul()], {"2026-09-14": "bullish"},
                               "قاعدة", "H4").n, 0)

    def test_nor_a_verdict_for_the_day_it_was_written_on(self):
        """
        ⛔⛔⛔ **وهذا الحارسُ كُشف نقصُه بالتجريب لا بالقراءة.**

        جُرّب نزعُ سطرِ [سطرُ إبطالٍ — لا حكم] **فصمت الطقم**:
        لأنّ المُختبِرَ أعلاه يُبطل **يومَه نفسَه**، فيمسكه حارسٌ
        ثانٍ (`c.day in voided`) ⇒ **فحارسان متراكبان، والأوّلُ
        غيرُ مقيس.**

        ⭐⭐ **والحالةُ الواقعيّةُ هي هذه**: «**إن تبيّن**» تعني
        بعدَه — **فالإبطالُ يُكتب يومَ انكشافِ الخطأ لا يومَ
        وقوعه**. وحينها يومُ السطر ≠ اليومُ المُبطَل، **ولو لم
        يُستثنَ لصار سطرُ الإبطال حكمَ يومِه** — حكمًا من [إبطال].
        """
        annul = call(day="2026-09-20", bias="undefined", quote="(إبطال)",
                     void="تبيّن بعد أسبوع", voids="2026-09-14")
        got = latest([self._live(), annul])
        self.assertNotIn("2026-09-14", got, "⇒ أُبطل")
        self.assertNotIn("2026-09-20", got,
                         "⛔ وسطرُ الإبطال صار حكمًا ليومِه!")
        self.assertEqual(
            score([self._live(), annul],
                  {"2026-09-14": "bullish", "2026-09-20": "undefined"},
                  "قاعدة", "H4").n, 0)

    # ── ⛔ ولا إبطالَ بلا سبب — وهو شرطُ الوحدة بنصِّه ──

    def test_an_annulment_without_a_reason_is_refused(self):
        """
        **وترويسةُ الوحدة تقول**: [فالصواب إبطالها صراحةً (`void`
        **مع سببه**)] ⇒ **فسطرٌ يُبطل ولا يقول لماذا مرفوض.**
        """
        with self.assertRaises(InvalidCall) as cm:
            validate(call(bias="undefined", quote="(إبطال)",
                          voids="2026-09-14"))
        self.assertIn("IN1", str(cm.exception))

    def test_a_malformed_day_is_refused_not_ignored(self):
        with self.assertRaises(InvalidCall):
            validate(call(bias="undefined", quote="(إبطال)",
                          void="سببٌ", voids="أمس"))

    # ── ⭐ والقديمُ لا يتغيّر معناه ──

    def test_a_line_written_before_the_field_existed_still_reads_the_same(self):
        """
        ⭐⭐⭐ **وهذا هو ما يجعل ② متوافقًا مع ما سُجّل**: سطرٌ قديمٌ
        لا يحمل `voids` ⇒ **لا يُبطل ولا يُزيح**، كما كان بالضبط.
        """
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                for bias, void in (("bullish", ""), ("bullish", "خطأ")):
                    fh.write(json.dumps(
                        {"day": "2026-09-14", "timeframe": "H4",
                         "bias": bias, "quote": "نصّ", "levels": {},
                         "void": void}, ensure_ascii=False) + "\n")
            got = latest(ins.load(path))
        self.assertIn("2026-09-14", got)
        self.assertTrue(got["2026-09-14"].live, "⇒ القديمُ كما كان")

    def test_the_field_survives_a_round_trip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.jsonl")
            ins.append(path, self._annul())
            back = ins.load(path)
        self.assertEqual(back[0].voids, "2026-09-14")
        self.assertIn("يُبطل يومَ 2026-09-14", back[0].render())

    def test_the_command_line_can_annul(self):
        """⭐ **وآليّةٌ لا يبلغها الأمرُ آليّةٌ ميّتة.**"""
        import contextlib
        import io
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "c.jsonl")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = ins.main(["--calls", path, "add",
                               "--day", "2026-10-16", "--tf", "M15",
                               "--bias", "undefined", "--quote", "(إبطال)",
                               "--void", "ترجمةٌ خاطئة",
                               "--voids", "2026-10-15"])
            self.assertEqual(rc, 0)
            self.assertIn("أُبطل يومُ", buf.getvalue())
            self.assertEqual(ins.load(path)[0].voids, "2026-10-15")


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


class TestTheWidenedListAndItsTwoGuards(unittest.TestCase):
    """
    ⛔⛔⛔ **وُسّعت القائمةُ 2026-10-09 — بقرار المستخدم.**

    وجرى قبلها أوّلُ فحصٍ أعمى (5 · 6 · 8 أكتوبر) فأعطى **1 من 3**،
    فقُرئ اليومان الساقطان للتشخيص. ⇒ **فالتوسيعُ مكتوبٌ وأنا أرى
    النصّ** — وهو الثمنُ المسجَّل في الوحدة نفسِها.

    ⭐⭐ **والإضافاتُ من مسحِ السجلّ لا من خيالي** — والمسحُ هو الذي
    كشف الفخّين المختبَرين أدناه، **قبل التوسيع لا بعده**.
    """

    @staticmethod
    def _doc(body):
        return "# ترويسةٌ لا تُقرأ\n\n```\n" + body + "\n```\n"

    # ── صيغةُ المفرد — والقائمةُ كانت تحمل الجمعَ وحدَه ──

    def test_the_singular_participle_is_read_like_the_plural(self):
        """«متوجه صعودا» — 10-05. والقائمةُ كانت تحمل [متوجهين] فقط."""
        got, ev, _ = ins.read_bias(self._doc(
            "ثبات اليوم انا بنظري فوق ال 140 هو متوجه صعودا"))
        self.assertEqual(got, "bullish")
        self.assertTrue(ev)

    def test_a_first_person_expectation_is_read(self):
        """«انا اتوقع انه هي نهايه الهبوط للذهب» — 10-05."""
        got, _, _ = ins.read_bias(self._doc(
            "وبعدين الصعود انا اتوقع انه هي نهايه الهبوط للذهب"))
        self.assertEqual(got, "bullish")

    # ── ⛔ فخُّ النفي — ولولا المسحُ لانقلب حكمٌ قائم ──

    def test_a_negated_stance_is_flipped_not_taken_at_face_value(self):
        """«ما بدنا نفكر بالصعود» — 10-06. **واللفظُ صاعدٌ والمعنى هابط.**"""
        got, ev, _ = ins.read_bias(self._doc(
            "حاليا ما بدنا نفكر بالصعود كثير انه نحن ناخذ صفقات شرائيه"))
        self.assertEqual(got, "bearish")
        self.assertIn("نفي", ev[0], "القلبُ يُعلَن في الدليل، ولا يُبتلَع")

    def test_the_other_direction_flips_too(self):
        """«ما هو متوجه للهبوط» — 09-25."""
        got, _, _ = ins.read_bias(self._doc(
            "ولكن بهدا ما بيعني انه سوقنا ما هو متوجه للهبوط"))
        self.assertEqual(got, "bullish")

    def test_a_far_off_negation_does_not_flip(self):
        """
        ⭐ **والأداةُ تلزمها الملاصقة** — فـ«مثل ما حكينا» ليست نفيًا
        للعبارة بعدها. وهو سببُ تضييقِ الشرط من نافذةٍ إلى كلمة.
        """
        got, _, _ = ins.read_bias(self._doc(
            "مثل ما حكينا امبارح على المستويات فنحن متوجهين صعود"))
        self.assertEqual(got, "bullish")

    def test_one_negated_match_does_not_poison_the_next(self):
        """
        ⛔⛔ **عطبٌ كُتب في ساعته وأُصلح**: كان القلبُ يُكتب على
        `bias` — **وهو متغيّرُ الحلقة** ⇒ فالمطابقةُ التاليةُ للعبارة
        نفسِها تخرج مقلوبةً بلا نفي.

        ⇒ وهنا موضعان لـ[متوجه للهبوط]: **الأوّلُ منفيٌّ والثاني لا**
        ⇒ فالصحيحُ تعارضٌ ⇒ [غير محدَّد]. **ولو سرى القلبُ لصار
        الاثنان صاعدين** ⇒ [صاعد] — وهو حكمٌ مخترَع.
        """
        got, ev, _ = ins.read_bias(self._doc(
            "ما هو متوجه للهبوط في عننا تصحيحات طفيفه وبعدها "
            "نحن هيكلنا هابط وبعده متوجه للهبوط ما في تشينج اوف كراكتر"))
        self.assertEqual(got, "undefined")
        self.assertEqual(len(ev), 2)
        self.assertEqual(sum("نفي" in e for e in ev), 1,
                         "واحدٌ يُقلب لا الاثنان")

    # ── ⛔ فخُّ الأداة — والمدرّب يحلّل أكثر من أداة في الفيديو ──

    def test_a_verdict_about_another_instrument_is_dropped_and_named(self):
        """
        ⛔⛔⛔ «فاتوقع هبوط **الدي اكس واي** بشكل عنيف جدا» — 10-05.

        **وهو هبوطُ الدولار لا الذهب، ومعناه صعودُ الذهب.** فلو حُسب
        لصار اليومُ هابطًا **على جملةٍ تقول عكسَه**.
        """
        got, ev, dropped = ins.read_bias(self._doc(
            "حسب الدايفرجنس فنحن متوجهين هبوط الدي اكس واي بشكل عنيف"))
        self.assertEqual(got, "undefined")
        self.assertFalse(ev)
        self.assertTrue(any("أداةٌ أخرى" in d for d in dropped),
                        "يُسقَط **ويُسمّى**، كالشرط سواءً")

    def test_the_same_phrase_about_gold_is_still_read(self):
        """⚠️ **والحارسُ لا يبتلع الحكمَ عن الذهب** — وإلّا أسكت الأداة."""
        got, _, _ = ins.read_bias(self._doc(
            "خلص نحن متوجهين هبوط ما يفكر انه هو يشتري من ه المناطق"))
        self.assertEqual(got, "bearish")

    # ── ⚠️ وما خسرناه بالتوسيع — يُثبَّت كي لا يُكتشف مرّتين ──

    def test_the_widening_costs_one_already_judged_day(self):
        """
        ⚠️⚠️ **و09-25 كان [صاعدًا] فصار [غير محدَّد].**

        والسببُ أنّ اليومَ يحمل **موقفين متضادّين** لم تكن القائمةُ
        الضيّقةُ ترى ثانيَهما: «فنحن متوجهين صعود» · و«نحن هيكلنا
        هابط وليس صاعد وبعده متوجه للهبوط».

        ⇒ **وليس عطبًا بالضرورة**: [غير محدَّد] أصدقُ من [صاعد] إن
        كان النصُّ يحمل الاثنين. ⚠️ **ولكنّه خسارةُ تغطيةٍ تُقال**،
        ولا تُدفن في فرق.
        """
        got, ev, _ = ins.read_bias(self._doc(
            "فنحن متوجهين صعود الى منطقه ما فوق ال 50% وبعدها "
            "نحن هيكلنا هابط وليس صاعد وبعده متوجه للهبوط"))
        self.assertEqual(got, "undefined")
        self.assertEqual(len(ev), 2, "الدليلان يُعرَضان معًا")

    def test_the_conditional_guard_still_outranks_the_new_forms(self):
        """⭐ **والشرطُ يُسقط المفردَ كما يُسقط الجمع** — ولا استثناء."""
        got, ev, dropped = ins.read_bias(self._doc(
            "في حال نزل واغلق تحت ال 300 فانا متوجه هبوط"))
        self.assertEqual(got, "undefined")
        self.assertFalse(ev)
        self.assertTrue(any("شرط" in d for d in dropped))


class TestTheSecondWideningAndItsPronounGuard(unittest.TestCase):
    """
    ⭐⭐⭐ **وُسّعت القائمةُ ثانيةً 2026-10-16 — بقرار المستخدم**
    [وسع القائمة]، بعد أن أعطى يومان أعميان **أربعَ صيغٍ جديدة**
    (10-14 · 10-15 ⇒ 2 من 4).

    ⚠️⚠️ **والثمنُ هو هو**: كُتبت الإضافاتُ وأنا أرى النصَّ الذي
    أسقطها ⇒ **فلا تُقرأ تغطيةُ 10-14 إنجازًا أعمى.**
    """

    @staticmethod
    def _doc(body):
        return "# ترويسةٌ كتابتي أنا — ولا تُقرأ\n\n```\n" + body + "\n```\n"

    # ── ⭐ حارسُ الضمير — وهو شرطُ الوحدة المكتوبُ في ترويستها ──

    def test_a_phrase_without_a_pronoun_needs_one_beside_it(self):
        """
        ⛔⛔ **و[بعده صاعد] وحدَها وصفٌ لا موقف.**

        10-15: «بالنسبه لي **انا** … الذهب **بعده صاعد**» ⇒ فتُحسب.
        """
        got, ev, _ = ins.read_bias(self._doc(
            "بالنسبه لي انا الذهب بعده صاعد بما انه ما ضرب قاع اتجاه"))
        self.assertEqual(got, "bullish")
        self.assertTrue(ev)

    def test_the_same_phrase_with_no_pronoun_is_dropped_and_named(self):
        """
        ⭐⭐⭐ **والوصفُ العاري يُسقَط ويُسمّى** — ولا يُبتلَع.

        ⚠️ **ولو مرّ لصار كلُّ وصفٍ حكمًا** — وهو عينُ ما تنهى عنه
        ترويسةُ الوحدة: [و«هبوط» و«صعود» وحدَهما لا تُحسبان].
        """
        got, ev, dropped = ins.read_bias(self._doc(
            "الذهب بعده صاعد على اطار اليومي وما ضرب قاع اتجاه من تحت"))
        self.assertEqual(got, "undefined")
        self.assertFalse(ev)
        self.assertTrue(any("ضمير متكلّم" in d for d in dropped),
                        "يُسقَط **ويُسمّى**، كالشرط والأداة سواءً")

    def test_the_pronoun_guard_touches_only_the_new_table(self):
        """
        ⚠️ **ولا يمسّ `STANCE` بحرف** — فالضميرُ فيها داخلُ اللفظ
        ([تحليلي] · [متوجهين] · [اشترينا])، **ولو سرى الحارسُ
        عليها لأسقط أحكامًا قائمة.**
        """
        self.assertTrue(set(ins.STANCE).isdisjoint(ins._SELF_REQUIRED))
        got, _, _ = ins.read_bias(self._doc("متوجهين هبوط ما يفكر انه يشتري"))
        self.assertEqual(got, "bearish", "بلا ضميرٍ قبلها — وتُحسب")

    # ── ⛔ و[ما] جزءٌ من العبارة بقصد — وإلّا قلبها حارسُ النفي ──

    def test_the_negator_inside_the_phrase_must_not_flip_it(self):
        """
        ⛔⛔⛔ «انا **ما زلت** عمشوف انه الذهب الى صعود» — 10-14.

        **و[ما] هنا من الفعل لا نفيٌ له.** فلو بدأت العبارةُ من
        «زلت» لصارت أداةُ النفي هي الكلمةَ السابقةَ مباشرةً ⇒
        **فقلبها الحارسُ وأعطى اليومَ هابطًا على جملةٍ تقول عكسَه.**
        """
        got, ev, _ = ins.read_bias(self._doc(
            "اهلا وسهلا فيكم انا ما زلت عمشوف انه الذهب الى صعود"))
        self.assertEqual(got, "bullish")
        self.assertFalse(any("نفي" in e for e in ev), "ولا قلبَ")

    # ── ⛔ وحارسُ الأداة كان يأكل عبارةً تسمّي الذهبَ بلفظها ──

    def test_the_instrument_guard_spares_a_phrase_that_names_gold(self):
        """
        ⛔⛔⛔ **عطبٌ كشفه التشغيل 2026-10-16، لا القراءة.**

        10-14: «انه **الذهب** الى صعود الدرجه الاولى عوائد
        **السندات** عم تنخفض» ⇒ **فالسندات سببٌ لا موضوع**، وكانت
        تُسقط العبارةَ ⇒ **فالإضافةُ ميّتةٌ يومَ وُلدت.**

        ⇒ **والحارسُ يسأل [أالحكمُ على الذهب؟]، وعبارةٌ تسمّيه
        تجيبه.** ⭐ **فهو تضييقٌ بسؤاله نفسِه لا استثناءٌ له.**
        """
        got, ev, dropped = ins.read_bias(self._doc(
            "انا ما زلت عمشوف انه الذهب الى صعود الدرجه الاولى "
            "عوائد السندات عم تنخفض"))
        self.assertEqual(got, "bullish")
        self.assertTrue(ev)
        self.assertFalse(dropped)

    def test_and_the_guard_still_bites_a_phrase_that_does_not(self):
        """⚠️ **والتضييقُ لا يفتح البابَ** — فعبارةٌ بلا «الذهب» تُسقَط."""
        _, _, dropped = ins.read_bias(self._doc(
            "حسب الدايفرجنس فنحن متوجهين هبوط الدي اكس واي بشكل عنيف"))
        self.assertTrue(any("أداةٌ أخرى" in d for d in dropped))

    # ── ⚠️ والكلفةُ تُقال لا تُدفَن ──

    def test_the_second_widening_costs_a_day_it_had_judged(self):
        """
        ⚠️⚠️ **و10-05 كان [صاعدًا] فصار [غير محدَّد]** — بـ«نحن
        الهيكل **عننا بعده هابط** بالنسبه للربع ساعه».

        ⇒ **وهو حدُّ 09-25 وقد وقع ثالثةً** — والفرقُ أنّ هذا
        **إطارٌ مصرَّح**: اليوميُّ صاعدٌ والربعُ هابط.
        **وللقاعدة لا مفهومَ إطارٍ أصلًا** ⇒ فـ[غير محدَّد] أصدقُ
        من ترجيحٍ لا سندَ له.
        """
        got, ev, _ = ins.read_bias(self._doc(
            "انا بنظري فوق ال 140 هو متوجه صعودا وبعدها "
            "نحن الهيكل عننا بعده هابط بالنسبه للربع ساعه"))
        self.assertEqual(got, "undefined")
        self.assertEqual(len(ev), 2, "الدليلان يُعرَضان معًا")

    def test_the_contradicting_phrase_was_not_withheld(self):
        """
        ⛔⛔⛔ **و[بايعين] مسجَّلةٌ وهي التي تُسقط 10-15.**

        ولو حُجبت لصار اليومُ [صاعدًا] — **وذلك تفصيلٌ على جوابٍ
        أعرفه**، وهو عينُ ما تحذّر منه ترويسةُ الوحدة.
        ⭐ **والأصدقُ: لا ربحَ على 10-15.**
        """
        self.assertIn(("bearish", "بايعين"), ins.STANCE_SELF)
        got, _, _ = ins.read_bias(self._doc(
            "بالنسبه لي انا الذهب بعده صاعد وبعدها "
            "نحن تقريبا هون بهي المنطقه بايعين ستوبنا اعلى المنطقه"))
        self.assertEqual(got, "undefined")

    # ── ⭐ وفُصل التحفُّظُ عن الإعفاء — وكانا مفتاحًا واحدًا ──

    def test_a_held_position_carries_the_reservation_without_the_exemption(self):
        """
        ⭐⭐ **و[بايعين] اسمُ فاعلٍ لا فعلٌ ماضٍ** ⇒ **فيحكمها الشرط**
        («اذا نزل لهون نحن بايعين» موقفٌ مشروطٌ حقًّا)، **ويبقى
        تحفُّظُ الصفقة السابقة عليها** (10-15: «اللي نحن **كنا
        بايعين**»).

        ⇒ **فهما سؤالان، ولا يحملهما مفتاحٌ واحد** — درسُ BK2/BK3.
        """
        self.assertIn("بايعين", ins.PRIOR_TRADE_RISK)
        self.assertNotIn("بايعين", ins.DONE_DEEDS)
        got, ev, dropped = ins.read_bias(self._doc(
            "نحن اذا نزل السعر لهون نحن بهي المنطقه بايعين"))
        self.assertEqual(got, "undefined")
        self.assertFalse(ev)
        self.assertTrue(any("شرط" in d for d in dropped))

    def test_an_order_already_placed_keeps_the_exemption(self):
        """
        ⭐ **و[علقنا] فعلٌ ماضٍ** ⇒ **فيُعفى من الشرط** كـ[اشترينا]،
        لأنّ الشرطَ في 10-14 على **الوقف** لا على التعليق:
        «علقنا اوام الشراء على 4130 ولكن … **اذا** في حال ضربنا
        ستوب على 4070».
        """
        self.assertIn("علقنا اوام الشراء", ins.DONE_DEEDS)
        got, _, _ = ins.read_bias(self._doc(
            "اذا في حال ضربنا ستوب فلهذا السبب نحن علقنا اوام الشراء على 4130"))
        self.assertEqual(got, "bullish")

    def test_the_transcription_typo_is_kept_beside_the_sound_form(self):
        """
        ⚠️ **و«اوام» تحريفُ «اوامر» في التفريغ** — والنصُّ خامٌّ لا
        يُصلَح ⇒ **فالصيغتان كلتاهما مسجَّلتان**، وإلّا ضاع الموضعُ
        الوحيدُ الذي في السجلّ.
        """
        phrases = [p for _, p in ins.STANCE]
        self.assertIn("علقنا اوام الشراء", phrases)
        self.assertIn("علقنا اوامر الشراء", phrases)

    # ── ⭐ والمقابلُ يُسجَّل ولو لم يرد — وإلّا كانت القائمةُ منحازة ──

    def test_the_frame_is_recorded_on_every_counted_stance(self):
        """⭐ **والحقلُ يُعرَض دائمًا** — ولو لم يُسمَّ، فـ[بلا إطار] حالةٌ."""
        _, ev, _ = ins.read_bias(self._doc("انا تحليلي هابط وليس صاعد"))
        self.assertTrue(all("الإطار:" in e for e in ev))

    def test_every_new_phrase_has_its_opposite(self):
        """
        ⭐⭐⭐ **وقائمةٌ تحمل جهةً دون أختها تنحاز بالبناء.**

        ⇒ فلكلّ عبارةٍ مقابلُها، **ولو لم يرد في السجلّ بعد** —
        وهو عرفُ توسيعِ 10-09 نفسُه.
        """
        for table in (ins.STANCE, ins.STANCE_SELF):
            got = {p for _, p in table}
            for word, mirror in (("صاعد", "هابط"), ("صعود", "هبوط"),
                                 ("الشراء", "البيع")):
                for phrase in list(got):
                    if word in phrase:
                        self.assertIn(phrase.replace(word, mirror), got,
                                      f"[{phrase}] بلا مقابل")


class TestTheFrameFieldOnTheStance(unittest.TestCase):
    """
    ⭐⭐⭐ **حقلُ الإطار — بطلب المستخدم 2026-10-16** [ابن حقل الاطار
    للموقف]. وبُني لأنّ التوسيعَ الثاني أعطى صفرًا صافيًا، **والسببُ
    المقيسُ موقفان على إطارين مصرَّحين** (10-05 · 10-15).

    ⛔⛔ **والنصُّ يسمّي الإطارَ ولا يقول كيف تُجمَع الأطر** ⇒
    **فالجمعُ مفتاحٌ، والقائمُ `off`.**
    """

    @staticmethod
    def _doc(body):
        return "# ترويسةٌ كتابتي أنا — ولا تُقرأ\n\n```\n" + body + "\n```\n"

    # ── ⭐ القائمُ لا يتغيّر بحرف ──

    def test_the_live_mode_does_not_decide_anything(self):
        """
        ⭐⭐⭐ **والوضعُ القائمُ `off`: الحقلُ يُسجَّل ويُعرَض ولا يقرّر.**

        ⇒ **فيومٌ يحمل موقفين على إطارين يبقى [غير محدَّد]** — وهو
        سلوكُ ما قبل الحقل بعينه. ✅ **ومقيسٌ على الخمسةَ عشرَ.**

        ╔══════════════════════════════════════════════════════════╗
        ║  ✅ **و`off` قرارُ المستخدم 2026-10-16** [Off خليه] —     ║
        ║  **بعد القياس لا قبله.** ⇒ **فهذا حارسُ انقلابٍ صامت**:   ║
        ║  من قلب الافتراضَ أسقط الطقمَ، فلا يمرّ بلا إقرار.         ║
        ║                                                          ║
        ║  ⚠️ **وليس منعًا للوضع الآخر**: `scoped` مبنيّةٌ ومبلوغةٌ  ║
        ║  من سطر الأمر، **والقرارُ أن لا تكون الافتراض.**          ║
        ╚══════════════════════════════════════════════════════════╝
        """
        self.assertEqual(ins.DEFAULT_FRAME_SCOPE, "off",
                         "⛔ قرارُ المستخدم 2026-10-16 — ولا يُقلب بلا قرار")
        got, ev, dropped = ins.read_bias(self._doc(
            "بالنسبه لي انا الذهب بعده صاعد على اليومي وبعدها "
            "نحن تقريبا هون بهي المنطقه بايعين"))
        self.assertEqual(got, "undefined")
        self.assertEqual(len(ev), 2)
        self.assertFalse([d for d in dropped if "إطارٌ آخر" in d],
                         "⛔ ولا يُسقِط شيئًا في الوضع القائم")

    def test_an_unknown_mode_is_refused_not_guessed(self):
        with self.assertRaises(ValueError):
            ins.read_bias(self._doc("انا تحليلي هابط"), scope="largest")

    # ── ⭐ والإطارُ يُقرأ من النصّ، ولا يُخمَّن ──

    def test_the_named_frame_is_read(self):
        got, ev, _ = ins.read_bias(self._doc(
            "بالنسبه لي انا الذهب بعده صاعد بما انه ما ضرب قاع على اليومي"))
        self.assertEqual(got, "bullish")
        self.assertIn("الإطار: D1", ev[0])

    def test_an_unnamed_frame_stays_empty_and_is_not_assumed(self):
        """
        ⛔ **ولا يُخمَّن إطارٌ لم يُسمَّ** — فالفراغُ حالةٌ معلنةٌ
        اسمُها [بلا إطار]، لا `M15` بالافتراض (القاعدة ①).
        """
        _, ev, _ = ins.read_bias(self._doc("انا تحليلي هابط وليس صاعد"))
        self.assertIn("الإطار: بلا إطار", ev[0])

    def test_the_assimilated_article_is_matched(self):
        """
        ⛔⛔⛔ **عطبٌ كشفه القياسُ قبل أن يُكتب سطرٌ واحد.**

        الموضعُ الذي بُني الحقلُ لأجله هو «بالنسبه **للربع ساعه**»
        (10-05) — **والتعريفُ مُدغَمٌ في اللام** («لل» = «ل» + «ال»)
        ⇒ **فـ`_word` لا تُطابقه، وكان الحقلُ سيُبنى ميّتًا على
        اليوم الذي بُني له.**
        """
        _, ev, _ = ins.read_bias(self._doc(
            "نحن الهيكل عننا بعده هابط بالنسبه للربع ساعه تغير كان صاعد"))
        self.assertIn("الإطار: M15", ev[0])

    def test_a_bare_hour_is_a_duration_not_a_frame(self):
        """
        ⛔ **و«ساعه» عاريةً مدّةٌ لا إطار**: «الاخبار ما بقي لها غير
        **ساعه**» (10-14). ⇒ **فيُشترَط التعريف.**
        """
        _, ev, _ = ins.read_bias(self._doc(
            "انا تحليلي هابط والاخبار ما بقي لها غير ساعه"))
        self.assertIn("الإطار: بلا إطار", ev[0])

    # ── ⭐ ووضعُ `scoped` — مِيكانيكا الأداة منقولةً إلى الأطر ──

    def test_a_stance_about_another_frame_is_dropped_and_named(self):
        """
        ⭐⭐⭐ **وهو `OTHER_INSTRUMENT` بعينه، نُقل من الأدوات إلى
        الأطر**: حكمٌ على اليوميّ ليس حكمًا على الربع ساعه.
        """
        got, ev, dropped = ins.read_bias(self._doc(
            "بالنسبه لي انا الذهب بعده صاعد على اليومي " + "و" * 70
            + " نحن تقريبا هون بهي المنطقه بايعين"),
            scope="scoped", frame="M15")
        self.assertEqual(got, "bearish", "والباقي [بايعين] بلا إطار")
        self.assertEqual(len(ev), 1)
        self.assertTrue(any("إطارٌ آخر: D1" in d for d in dropped),
                        "يُسقَط **ويُسمّى**، كالأداة سواءً")

    def test_a_frame_name_within_the_window_sticks_to_a_stance_not_its_own(self):
        """
        ⛔⛔⛔ **وهذا الحدُّ وقع في بناء المُختبِر نفسِه.**

        كُتبت الجملتان متجاورتين فأخذت **كلتاهما** الإطارَ `D1`،
        فأُسقطت الاثنتان ⇒ `undefined` بلا دليلٍ واحد — **ولم يكن
        [بايعين] عن اليوميّ بحرف.**

        ⇒ **فهو عطبُ النافذة مبرهَنًا بالقياس**، وهو نفسُ ما وقع
        على 09-25 في السجلّ الحقيقيّ: «واغلق فوقه **بخمس دقائق**
        فنحن متوجهين صعود» ⇒ **فوُسم الموقفُ `M5` وهو شرطُ
        الإغلاق لا إطارُ الحكم.**

        ⚠️ **ويُثبَّت كي لا يُقرأ الحقلُ أدقَّ مما هو.**
        """
        _, ev, dropped = ins.read_bias(self._doc(
            "بالنسبه لي انا الذهب بعده صاعد على اليومي وبعدها "
            "نحن تقريبا هون بهي المنطقه بايعين"),
            scope="scoped", frame="M15")
        self.assertFalse(ev, "الاثنتان أُسقطتا — والثانيةُ ليست عن اليوميّ")
        self.assertEqual(sum("إطارٌ آخر: D1" in d for d in dropped), 2)

    def test_the_same_frame_is_kept(self):
        """⚠️ **والحارسُ لا يُسقط إطارَه نفسَه** — وإلّا أسكت الوحدة."""
        got, _, dropped = ins.read_bias(self._doc(
            "بالنسبه لي انا الذهب بعده صاعد على اليومي"),
            scope="scoped", frame="D1")
        self.assertEqual(got, "bullish")
        self.assertFalse(dropped)

    def test_an_unscoped_stance_survives_every_question(self):
        """
        ⚠️ **وما لا يسمّي إطارًا يبقى محسوبًا** — فهو لا يناقض إطارًا
        بعينه، **ولا يُنسَب إليه بالافتراض.**
        """
        for frame in ("", "D1", "M15"):
            got, _, _ = ins.read_bias(self._doc("انا تحليلي هابط"),
                                      scope="scoped", frame=frame)
            self.assertEqual(got, "bearish", f"عند {frame!r}")

    # ── ⚠️ والنافذةُ اختيارٌ يُقال، لا رقمٌ طبيعيّ ──

    def test_the_window_is_a_choice_and_it_moves_the_label(self):
        """
        ⚠️⚠️ **وهو صنفُ [رقمٌ يقلبه اختيارُك]**: اسمُ إطارٍ بعيدٌ
        يُلصق بموقفٍ ليس له إن وُسّعت النافذة.

        ⇒ **فتُجرَّب على قيمتين**، وهو عرفُ المشروع بنصِّه.
        """
        doc = self._doc("انا تحليلي هابط " + "و" * 70 + " على اليومي")
        kept = ins.FRAME_WINDOW
        try:
            ins.FRAME_WINDOW = 30
            self.assertIn("بلا إطار", ins.read_bias(doc)[1][0])
            ins.FRAME_WINDOW = 200
            self.assertIn("الإطار: D1", ins.read_bias(doc)[1][0])
        finally:
            ins.FRAME_WINDOW = kept

    def test_the_nearest_name_wins(self):
        """
        ⭐ **وأقربُ اسمٍ هو المأخوذ** — ولا يُجمَع إطاران لموقف.

        ⚠️ **ويُقاس في الجهتين**: الأقربُ بعدَها ثمّ الأقربُ قبلَها،
        **فلا تُقرأ الأسبقيّةُ قاعدةً وهي مسافة.**
        """
        _, ev, _ = ins.read_bias(self._doc(
            "على اليومي " + "و" * 30 + " انا تحليلي هابط على الربع ساعه"))
        self.assertIn("الإطار: M15", ev[0], "والبعيدُ قبلَها لا يفوز")
        _, ev, _ = ins.read_bias(self._doc(
            "على الربع ساعه انا تحليلي هابط " + "و" * 30 + " على اليومي"))
        self.assertIn("الإطار: M15", ev[0], "والقريبُ قبلَها يفوز")

    # ── ⛔ ولا يُسجَّل حكمٌ أنتجه وضعٌ لا يحفظه الملفّ ──

    def test_writing_a_scoped_verdict_is_refused(self):
        """
        ⛔⛔⛔ **و`runs/instructor.jsonl` لا حقلَ فيه للوضع** ⇒ فحكمٌ
        مكتوبٌ بـ`scoped` **يصير بلا مصدر** بعد أسبوع.

        ⇒ **فيُرفض صريحًا**، وتوسيعُ صيغةِ الملفّ **قرارٌ منهجيٌّ**
        كـIN1 لا سطرٌ يُكتب في طريقه.
        """
        with tempfile.TemporaryDirectory() as tmp:
            calls = os.path.join(tmp, "instructor.jsonl")
            rc = ins.main(["--calls", calls, "infer",
                           "--scope", "scoped", "--write"])
            self.assertEqual(rc, 1)
            self.assertFalse(os.path.exists(calls), "ولا سطرَ كُتب")

    def test_the_mode_is_reachable_from_the_command_line(self):
        """
        ⭐ **وفرعٌ لا يبلغه الأمرُ فرعٌ ميّت** — وهو حارسُ
        `backtest.py` نفسُه، مطبَّقًا هنا.
        """
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ins.FRAME_SCOPE_MODES:
                rc = ins.main(["--calls", os.path.join(tmp, "x.jsonl"),
                               "infer", "--scope", mode, "--frame", "M15"])
                self.assertEqual(rc, 0, f"الوضعُ {mode} لا يبلغه الأمر")


class TestSC1MutualAbstentionIsCountedAsAgreement(unittest.TestCase):
    """
    ⛔⛔ **SC1 — كُشف 2026-10-18 في القراءة الأسبوعيّة.**

    `agrees = (got == call.bias)` و`BIAS` ثلاثٌ فيها `undefined`
    ⇒ **فيومٌ امتنع فيه الاثنان يُحسب إصابة.** ووقع في الرقم:
    `score --tf M15` أعطى `classify_trend` **2 من 10** وإحداهما
    `undefined` في العمودين.

    ⛔ **ولم يُغيَّر `hits`** — تغييرُ معنى [إصابة] يقلب كلَّ رقمٍ
    سجّله المشروع بأثرٍ رجعيّ (عرفُ IN1)، **و[أيُحسب الامتناعُ
    المتبادلُ اتّفاقًا؟] قرارٌ منهجيٌّ** لا عطبٌ يُصلَح.
    ⇒ **والذي صُنع أن يُقال مع الرقم** (درسُ VL1).
    """

    @staticmethod
    def _card():
        mute = Verdict(call(day="2026-10-15", bias="undefined"),
                       "undefined", True)
        said = Verdict(call(day="2026-10-14", bias="bullish"),
                       "bullish", True)
        miss = Verdict(call(day="2026-10-13", bias="bearish"),
                       "bullish", False)
        return Scorecard("classify_trend", [mute, said, miss])

    def test_the_count_itself_did_not_move(self):
        """⛔ فالبسطُ والمقامُ كما كانا — ولا رقمٌ قديمٌ يتغيّر معناه."""
        card = self._card()
        self.assertEqual((card.hits, card.n), (2, 3))

    def test_the_mutual_abstention_is_counted_apart(self):
        self.assertEqual(self._card().mutual_abstentions, 1)

    def test_a_one_sided_abstention_is_not_counted_as_mutual(self):
        """
        ⚠️ **وهو الفرقُ عن عمود 10-10**: [أحدُهما ممتنع] ليس
        [كلاهما ممتنع] — وذاك خطأٌ مسجَّلٌ، وهذا اتّفاقٌ في الامتناع.
        """
        one = Verdict(call(day="2026-10-12", bias="bullish"),
                      "undefined", False)
        card = Scorecard("x", [one])
        self.assertEqual(card.mutual_abstentions, 0)
        self.assertEqual((card.hits, card.n), (0, 1))

    def test_the_render_names_it_where_the_number_is_read(self):
        """
        ⭐⭐⭐ **درسُ VL1 بنصّه**: التحفّظُ في الترويسة لا يُقرأ مع
        الرقم ⇒ **فيُطبَع في السطر نفسِه ومع الحصيلة.**
        """
        text = self._card().render()
        self.assertIn("2/3", text)
        self.assertIn("SC1", text)
        self.assertIn("فالمُصرَّحُ 1/3", text)

        # ⛔⛔ **وحارسٌ صمت ساعةَ جُرِّب** — كان `assertIn` على النصّ
        # كلِّه، **وسطرُ الحصيلة يحمل العبارةَ نفسَها** ⇒ فنزعُ وسمِ
        # الصفّ يمرّ. ⭐ وهو [حارسٌ لا يسمّي ما يفحص] في موضعه
        # التاسع — وعطبُ `assertIn("0 ( 0.0%)")` بعينه (KZ1 · 10-17).
        # ⇒ **فيُسأل الصفُّ بعينه.**
        rows = [ln for ln in text.splitlines() if "2026-10-15" in ln]
        self.assertEqual(len(rows), 1, text)
        self.assertIn("⟨كلاهما ممتنع⟩", rows[0])

        other = [ln for ln in text.splitlines() if "2026-10-14" in ln]
        self.assertNotIn("ممتنع", other[0], "والمُصرَّحُ لا يُوسَم")

    def test_a_card_without_mutual_abstention_says_nothing_extra(self):
        """⚠️ **والمتكرّرُ يُعلَّم أن يُتجاهَل** (مبدأ KS1) ⇒ فلا سطرَ بلا داعٍ."""
        card = Scorecard("x", [Verdict(call(bias="bearish"), "bearish", True)])
        text = card.render()
        self.assertNotIn("SC1", text)
        self.assertNotIn("ممتنع", text)

    def test_a_voided_day_is_not_counted_as_a_mutual_abstention(self):
        """⛔ **والمُبطَلُ خارجَ العدّ كلِّه** — وهو عرفُ IN1."""
        dead = Verdict(call(day="2026-10-11", bias="undefined",
                            void="تبيّن أنّه خطأ", voids="2026-10-11"),
                       "undefined", True)
        card = Scorecard("x", [dead])
        self.assertEqual((card.hits, card.n, card.mutual_abstentions),
                         (0, 0, 0))
