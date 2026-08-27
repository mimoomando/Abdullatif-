"""
اختبارات حكم المستخدم على الشكل.

الغرض المعلَن: قياس النوع الثاني من الخطأ الذي سمّاه المدرّب —
«الحساب صح بس الشكل غير مطابق» — وهو ما **لا يراه الكود**.
"""

import unittest
from datetime import datetime

from bot.verdicts import (
    Accuracy,
    JudgedSetup,
    Verdict,
    parse_verdicts,
    prompt_for,
)

T0 = datetime(2026, 8, 27, 22, 0)


def js(sid, disp, tf="H1", shape=None, near=False) -> JudgedSetup:
    return JudgedSetup(sid, disp, tf, shape, near_miss=near)


class TestParse(unittest.TestCase):
    def test_simple_yes_and_no(self):
        v = parse_verdicts("1 نعم\n2 لا")
        self.assertEqual([x.setup_id for x in v], [1, 2])
        self.assertEqual([x.shape_ok for x in v], [True, False])

    def test_arabic_digits(self):
        v = parse_verdicts("١ نعم\n٢ لا")
        self.assertEqual([x.setup_id for x in v], [1, 2])

    def test_note_is_kept(self):
        v = parse_verdicts("3 لا الشكل ما كان مطابق")[0]
        self.assertFalse(v.shape_ok)
        self.assertEqual(v.note, "الشكل ما كان مطابق")

    def test_separators_are_tolerated(self):
        for line in ("1. نعم", "1) نعم", "1 - نعم", "1: نعم", "  1   نعم  "):
            with self.subTest(line=line):
                self.assertEqual(len(parse_verdicts(line)), 1)

    def test_unparseable_lines_are_ignored_not_fatal(self):
        """رفض ردّ كامل بسبب سطر واحد أسوأ من تجاهله."""
        v = parse_verdicts("مرحبا\n1 نعم\nكلام حر\n2 لا")
        self.assertEqual(len(v), 2)

    def test_unknown_answer_word_is_ignored(self):
        self.assertEqual(parse_verdicts("1 ربما"), [])

    def test_bare_number_is_ignored(self):
        self.assertEqual(parse_verdicts("1"), [])

    def test_first_answer_for_an_id_wins(self):
        v = parse_verdicts("1 نعم\n1 لا")
        self.assertEqual(len(v), 1)
        self.assertTrue(v[0].shape_ok)

    def test_timestamp_is_attached(self):
        self.assertEqual(parse_verdicts("1 نعم", at=T0)[0].at, T0)

    def test_english_answers(self):
        self.assertTrue(parse_verdicts("1 yes")[0].shape_ok)
        self.assertFalse(parse_verdicts("1 no")[0].shape_ok)

    def test_render_shows_the_mark(self):
        self.assertIn("✅", Verdict(1, True).render())
        self.assertIn("❌", Verdict(1, False, "ما كان مطابق").render())


class TestJudgedSetup(unittest.TestCase):
    def test_false_positive_is_acting_on_a_wrong_shape(self):
        """«الحساب صح بس الشكل غير مطابق» ⇒ الشروط فضفاضة."""
        self.assertTrue(js(1, "taken", shape=False).false_positive)
        self.assertTrue(js(1, "blocked", shape=False).false_positive)
        self.assertFalse(js(1, "rejected", shape=False).false_positive)

    def test_false_negative_is_rejecting_a_right_shape(self):
        """«الشكل صح بس الحساب غلط» ⇒ الشروط ضيقة."""
        self.assertTrue(js(1, "rejected", shape=True).false_negative)
        self.assertFalse(js(1, "taken", shape=True).false_negative)

    def test_unjudged_is_neither(self):
        s = js(1, "taken", shape=None)
        self.assertFalse(s.false_positive)
        self.assertFalse(s.false_negative)

    def test_blocked_counts_as_acted(self):
        """التنبيه تصرّف — البوت قال «هذه فرصة»، فيُحاسَب عليها."""
        self.assertTrue(js(1, "blocked").acted)
        self.assertFalse(js(1, "rejected").acted)


class TestAccuracy(unittest.TestCase):
    def _acc(self) -> Accuracy:
        a = Accuracy()
        a.add([
            js(1, "taken", "H1", shape=True),
            js(2, "taken", "H1", shape=False),          # إيجابية كاذبة
            js(3, "rejected", "M15", shape=True, near=True),   # سلبية كاذبة
            js(4, "rejected", "M15", shape=False),
            js(5, "blocked", "H4", shape=None),         # بلا حكم
        ])
        return a

    def test_only_judged_are_counted(self):
        self.assertEqual(len(self._acc().rated), 4)

    def test_both_error_types_are_counted(self):
        a = self._acc()
        self.assertEqual([j.setup_id for j in a.false_positives], [2])
        self.assertEqual([j.setup_id for j in a.false_negatives], [3])
        self.assertEqual([j.setup_id for j in a.correct], [1, 4])

    def test_rates(self):
        a = self._acc()
        self.assertAlmostEqual(a.rate("fp"), 0.25)
        self.assertAlmostEqual(a.rate("fn"), 0.25)

    def test_rate_is_none_without_a_sample(self):
        self.assertIsNone(Accuracy().rate("fp"))

    def test_by_timeframe_splits_the_errors(self):
        rows = self._acc().by_timeframe()
        self.assertEqual(rows["H1"]["إيجابية كاذبة"], 1)
        self.assertEqual(rows["M15"]["سلبية كاذبة"], 1)
        self.assertNotIn("H4", rows)      # بلا حكم ⇒ خارج القياس

    def test_near_miss_link_points_at_calibration(self):
        link = self._acc().near_miss_link()
        self.assertIn("1 من 1", link)
        self.assertIn("توسيع السماحية", link)

    def test_near_miss_link_when_none_were_near(self):
        a = Accuracy([js(1, "rejected", shape=True)])
        self.assertIn("ليست في العتبات وحدها", a.near_miss_link())

    def test_near_miss_link_is_none_without_false_negatives(self):
        self.assertIsNone(Accuracy([js(1, "taken", shape=True)]).near_miss_link())


class TestAccuracyRender(unittest.TestCase):
    def test_empty_says_so(self):
        self.assertIn("لا أحكام بعد", Accuracy().render())

    def test_render_names_both_error_types(self):
        out = TestAccuracy()._acc().render()
        self.assertIn("إيجابية كاذبة", out)
        self.assertIn("سلبية كاذبة", out)
        self.assertIn("الشروط فضفاضة", out)
        self.assertIn("الشروط ضيقة", out)

    def test_render_warns_while_the_sample_is_small(self):
        """⚠️ لا معايرة على عيّنة صغيرة — القاعدة نفسها في كل التقارير."""
        self.assertIn("لا تُتخذ قرارات معايرة بعد", TestAccuracy()._acc().render())

    def test_no_warning_once_the_sample_is_enough(self):
        a = Accuracy([js(i, "taken", shape=True) for i in range(6)])
        self.assertNotIn("لا تُتخذ قرارات معايرة", a.render(min_sample=5))

    def test_render_breaks_down_by_timeframe(self):
        out = TestAccuracy()._acc().render()
        self.assertIn("حسب الإطار", out)
        self.assertIn("M15", out)

    def test_single_timeframe_has_no_breakdown(self):
        a = Accuracy([js(1, "taken", "H1", shape=True)])
        self.assertNotIn("حسب الإطار", a.render())


class TestPrompt(unittest.TestCase):
    def test_empty_when_nothing_to_judge(self):
        self.assertEqual(prompt_for([]), "")

    def test_lists_the_ids_as_shown_in_the_report(self):
        out = prompt_for([2, 5])
        self.assertIn("2 · 5", out)
        self.assertIn("2 نعم", out)
        self.assertIn("5 لا", out)

    def test_single_id_still_shows_two_example_lines(self):
        out = prompt_for([3])
        self.assertIn("3 نعم", out)
        self.assertIn("4 لا", out)

    def test_asks_about_shape_not_outcome(self):
        out = prompt_for([1])
        self.assertIn("الشكل", out)
        self.assertIn("النتيجة يقيسها البوت", out)


class TestRoundTrip(unittest.TestCase):
    def test_the_reply_the_prompt_asks_for_parses(self):
        """ما يطلبه النصّ يجب أن يقرأه المحلّل — وإلا فالحلقة مكسورة."""
        prompt = prompt_for([1, 2])
        reply = "\n".join(
            line.strip() for line in prompt.splitlines()
            if line.strip().startswith(("1 ", "2 "))
        )
        v = parse_verdicts(reply)
        self.assertEqual([x.setup_id for x in v], [1, 2])
        self.assertEqual([x.shape_ok for x in v], [True, False])


if __name__ == "__main__":
    unittest.main(verbosity=2)
