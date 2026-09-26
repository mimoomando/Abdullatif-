"""
اختبارُ تدقيق الاقتباسات.

⛔ **الغرضُ عمليّ لا تجميليّ**: إن أُضيف غدًا معاملٌ `SOURCE` باقتباسٍ
لا أصلَ له في نصوص المدرّب — **يسقط الطقم**. فالقاعدة ① تصير
مفروضةً بالكود لا موصى بها في التوثيق.

⚠️ ولا يثبت هذا صحّةَ فهمي للنصّ — يثبت أنّ العبارة قيلت فقط.
"""

import unittest

from bot.quotes import Corpus, check, render, suspect


class TestTheMatcherIsCalibrated(unittest.TestCase):
    """
    ⭐ **الأداةُ تُختبر على حالاتٍ معروفةِ الجواب قبل أن تُصدَّق.**

    فمحاولتان سابقتان أعطتا «92 اقتباسًا غير موجود» — رقمٌ كاذبٌ
    كلُّه، سببُه مطابقةُ الحروف على تفريغٍ بلا إعراب.
    """

    @classmethod
    def setUpClass(cls):
        cls.corpus = Corpus.load()

    def test_the_corpus_actually_loaded(self):
        self.assertGreater(len(self.corpus.words), 50_000)

    def test_a_quote_i_verified_by_hand_scores_high(self):
        """تحقّقتُ منها بعيني في `live-01` — فإن رسبت فالأداةُ معطوبة."""
        q = ("الماكسيموم ماكسيموم ماكسيموم 50%؟ بس ما يغلق — "
             "هي مش غالق فوق الـ50%")
        self.assertGreaterEqual(self.corpus.coverage(q), 0.80)

    def test_a_second_hand_verified_quote_scores_high(self):
        q = ("عندي نقطة بيع من هون، بس ستوبي بعيد 25 دولار، "
             "هدف الأول أقلّ من واحد على واحد")
        self.assertGreaterEqual(self.corpus.coverage(q), 0.80)

    def test_an_invented_quote_scores_low(self):
        """⛔ لو مرّت هذه، لما دلّت الأداةُ على شيء."""
        q = ("المدرّب قال إنّ الوقف يوضع عند مئتين وخمسين دولارًا "
             "فوق القمة دائمًا في كلّ الفريمات")
        self.assertLess(self.corpus.coverage(q), 0.55)

    def test_a_second_invented_quote_scores_low(self):
        q = ("القاعدة الذهبية أن تدخل يوم الخميس فقط وتخرج قبل "
             "الجمعة بساعتين على الأكثر")
        self.assertLess(self.corpus.coverage(q), 0.55)

    def test_contiguous_matching_rescues_a_short_true_quote(self):
        self.assertTrue(self.corpus.contiguous("سحب سيوله"))

    def test_contiguous_matching_refuses_a_short_false_one(self):
        self.assertFalse(self.corpus.contiguous("الوقف مئتان وخمسون"))


class TestNoInventedQuoteEntersParams(unittest.TestCase):
    """
    ⛔⛔ **الحارس.** أيُّ اقتباسٍ طويلٍ جديدٍ لا أصلَ له يُسقط الطقم.
    """

    # الأربعةُ المعروفة — **وكلُّها من دروسٍ لم يصل تفريغُها**، فهي
    # غيرُ قابلةٍ للفحص لا مكذَّبة. وتُسمّى هنا صراحةً كي لا تُخفى،
    # وتُحذف من القائمة حين يصل نصُّ درسها.
    # ⭐ واثنان خرجا منها 2026-09-26 بعد أن رُبطا بنصٍّ نملكه:
    #   `CONTINUATION_REQUIRES_RETEST` · `CONTINUATION_INVALIDATING_RETRACE`
    # والباقيان **من تحليلات المدرّب اليوميّة** — وهي غيرُ الدروس،
    # ولم تصل إلّا لأسبوع 09-21…25. (شخّصه المستخدم بنفسه.)
    UNVERIFIABLE = {
        "MODEL_FAILURES_BEFORE_STOPPING",   # تحليل 7/9 — تحليلٌ يوميّ لم يصل
        "NEWS_FILTER",                      # تحليلا 7/9 و10/9 — لم يصلا
    }

    @classmethod
    def setUpClass(cls):
        cls.results = check()

    def test_something_was_actually_checked(self):
        self.assertGreater(len(self.results), 80)

    def test_no_long_quote_is_unaccounted_for(self):
        rogue = {c.param for c in suspect(self.results)} - self.UNVERIFIABLE
        self.assertEqual(
            rogue, set(),
            "اقتباسٌ منسوبٌ للمدرّب لا أصلَ له في نصوصه: %s" % sorted(rogue))

    def test_the_allowlist_does_not_rot(self):
        """⚠️ واسمٌ في القائمة صار قابلًا للفحص **يُحذف منها**."""
        still = {c.param for c in suspect(self.results)}
        stale = self.UNVERIFIABLE - still
        self.assertEqual(
            stale, set(),
            "صار قابلًا للفحص — يُحذف من القائمة: %s" % sorted(stale))

    def test_most_testable_quotes_are_found(self):
        testable = [c for c in self.results if c.testable]
        found = [c for c in testable if c.found]
        self.assertGreaterEqual(len(found) / max(len(testable), 1), 0.90)

    def test_user_decisions_are_excluded(self):
        """قرارُ المستخدم ليس كلامَ المدرّب — فغيابُه صواب."""
        self.assertTrue(all(c.origin != "USER" for c in self.results))

    def test_the_report_states_what_it_cannot_prove(self):
        self.assertIn("لا أنّ ما بُني عليها صحيح", render(self.results))


if __name__ == "__main__":
    unittest.main(verbosity=2)
