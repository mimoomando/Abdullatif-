"""
اختبارات تسجيل أحكام المدرّب.

⛔ الشرط الحاكم لهذه الوحدة: **لا تُعدَّل مقولةٌ بعد رؤية نتيجتها.**
وكل اختبار هنا يحرس بابًا من أبواب ذلك.
"""

import json
import os
import tempfile
import unittest

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
