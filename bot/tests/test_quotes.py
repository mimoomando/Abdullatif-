"""
اختبارُ تدقيق الاقتباسات.

⛔ **الغرضُ عمليّ لا تجميليّ**: إن أُضيف غدًا معاملٌ `SOURCE` باقتباسٍ
لا أصلَ له في نصوص المدرّب — **يسقط الطقم**. فالقاعدة ① تصير
مفروضةً بالكود لا موصى بها في التوثيق.

⚠️ ولا يثبت هذا صحّةَ فهمي للنصّ — يثبت أنّ العبارة قيلت فقط.
"""

import unittest

from bot.quotes import Corpus, check, check_code, render, suspect


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


class TestTheCorpusReadsWhatItClaims(unittest.TestCase):
    """
    ⛔⛔ **حارسا عطبَي 2026-09-27** — وكلاهما «بندٌ يصمت عند تعطُّله».
    """

    @classmethod
    def setUpClass(cls):
        cls.corpus = Corpus.load()

    def test_the_daily_analyses_folder_is_actually_read(self):
        """
        ⛔ كان `os.listdir` يهمل `analyses/` كلَّه صامتًا — **وفيه
        تحاليلُ الذهب اليوميّة**، وهي مصدرٌ مستقلٌّ كالدروس. فكانت
        الأداةُ تقول «لم يُوجد» عن نصٍّ لم تفتحه.
        """
        nested = [f for f in self.corpus.files if "/" in f]
        self.assertGreaterEqual(len(nested), 6, "لم تُقرأ التحاليلُ اليوميّة")

    def test_a_sentence_only_in_a_daily_analysis_is_found(self):
        """فحصٌ موجَّه: عبارةٌ لا وجودَ لها إلّا في تحليل 7/9."""
        self.assertGreaterEqual(
            self.corpus.coverage(
                "ونحن بوقت الاخبار ما بنتداول بنوقف اي شيء"), 0.80)

    def test_my_own_commentary_is_not_part_of_the_corpus(self):
        """
        ⭐ **وإلّا صدّقت الأداةُ نفسَها.** فترويسةُ كلّ ملفٍّ كتابتي،
        ولو حرّفتُ اقتباسًا ونقلتُ التحريفَ إليها لوجدته «في النصّ».

        والمثالُ واقعٌ لا مفترَض: «الهيكل غير محدَّد» — وهو **سببُ
        رفضٍ من الكود** لا كلامُ المدرّب — كان يُطابَق متّصلًا،
        وموضعُه الوحيد سطرٌ من كتابتي في `lesson-33`.
        """
        self.assertFalse(self.corpus.contiguous("الهيكل غير محدد"))

    def test_an_english_quote_is_checkable_at_all(self):
        """
        ⛔ **عطبٌ رابع — كُشف 2026-09-27.** كان `_KEEP` يمحو الحروفَ
        اللاتينيّة، **فيصير كلُّ اقتباسٍ إنجليزيّ صفرَ كلمات ⇒ «أقصرُ
        من أن يُفحَص» ⇒ يمرّ صامتًا**. وهي أكثرُ من عشرين، ومنها
        حاملةٌ لقرار: سندُ `structure_break = "body"`.
        """
        self.assertTrue(self.corpus.contiguous(
            "The structural break must be by candle body, not wick"))

    def test_an_invented_english_quote_still_fails(self):
        """⛔ ولو مرّت هذه، لما دلّت الإضافةُ على شيء."""
        self.assertLess(self.corpus.coverage(
            "The stop loss is always placed two hundred fifty dollars "
            "above the high in every timeframe"), 0.55)

    def test_the_report_states_the_weaker_limit_of_english_quotes(self):
        """
        ⚠️ **والإنجليزيّةُ تُطابَق على الملفّ الجامع** — وهو وثيقةٌ
        **مشتقّة** لا تفريغُ كلام. فالحدُّ أضعف، **ويُقال في التقرير**.
        """
        self.assertIn("وثيقةٌ **مشتقّة**", render(check_code(self.corpus)))

    def test_every_source_file_keeps_the_fence_convention(self):
        """
        ⚠️ **وملفٌّ بلا سياجٍ يُقرأ كلُّه** — فلو أُضيف تفريغٌ جديدٌ بلا
        سياج لعادت ترويستُه إلى السجلّ بلا إشعار. فالعرفُ يُفحص.
        """
        import os

        from bot.quotes import raw_only

        loose = []
        for root, _d, names in os.walk("knowledge/source"):
            for name in names:
                if not name.endswith(".md"):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                if raw_only(text) == text:
                    loose.append(path)
        self.assertEqual(loose, [], "ملفٌّ بلا سياج ``` — ترويستُه ستُقرأ")


class TestNoInventedQuoteEntersParams(unittest.TestCase):
    """
    ⛔⛔ **الحارس.** أيُّ اقتباسٍ طويلٍ جديدٍ لا أصلَ له يُسقط الطقم.
    """

    # ⛔ كانت أربعةً، ثمّ اثنين — **وصارت فارغةً 2026-09-27.**
    #
    #   09-26  خرج `CONTINUATION_REQUIRES_RETEST` و
    #          `CONTINUATION_INVALIDATING_RETRACE` — رُبطا بنصٍّ نملكه
    #          (وفي أحدهما **زيادةٌ منّي** كشفها التدقيق).
    #   09-27  خرج `MODEL_FAILURES_BEFORE_STOPPING` (73%) و
    #          `NEWS_FILTER` (100% · مرّتين) — **وصل تحليلا 7/9 و10/9**
    #          بعد أن شخّص المستخدم غيابَهما بنفسه.
    #
    # ⭐ **فلم يبقَ اقتباسٌ منسوبٌ للمدرّب بلا أصلٍ في نصّه.** وأيُّ
    # اسمٍ يُضاف هنا لاحقًا يلزمه سببٌ مكتوب: أيُّ درسٍ لم يصل.
    UNVERIFIABLE: set = set()

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


class TestNoInventedQuoteEntersTheCode(unittest.TestCase):
    """
    ⛔⛔⛔ **والحارسُ الثاني — أهمُّ من الأوّل.**

    فالأوّل يقرأ الدفتر، **وقد ثبت أنّ ذلك لا يكفي**: صُحّحت ثلاثةُ
    اقتباساتٍ محرَّفةٍ في `params.py` يوم 2026-09-26، **وبقيت
    محرَّفةً في `primitives/continuation.py` يومًا كاملًا** —
    وأحدُها في **رسالةِ خطأٍ يطبعها البوت للمستخدم**.

    ⇒ فالتصحيحُ الناقص أخطرُ من غيابه: يُغلق البابَ في الدفتر
    ويُبقيه مفتوحًا في الكود، **ويقول إنّه أُغلق**.
    """

    @classmethod
    def setUpClass(cls):
        cls.results = check_code()

    def test_something_was_actually_checked(self):
        self.assertGreater(len(self.results), 300)

    def test_no_long_quote_in_the_code_is_unaccounted_for(self):
        """
        ⚠️ **وما ليس كلامَه يُكتب بين [ ] لا بين «»** — إقرارًا صريحًا،
        لا تهرُّبًا. فقرارُ المستخدم وصياغتي والرقمُ المقيس كلُّها
        معقوفة.
        """
        rogue = sorted({(c.param, c.quote[:60]) for c in suspect(self.results)})
        self.assertEqual(
            rogue, [],
            "اقتباسٌ في الكود منسوبٌ للمدرّب لا أصلَ له: %s" % rogue)

    def test_the_corrupted_continuation_quote_is_gone(self):
        """
        ⛔ **فحصٌ موجَّه على العطب بعينه.** «صار انعكاس» **لم يقلها
        المدرّب** — أضفتُها أنا، وكانت في ستّة مواضع من
        `continuation.py` ومنها رسالةُ الخطأ.
        """
        with open("bot/primitives/continuation.py", encoding="utf-8") as fh:
            text = fh.read()
        for phrase in ("«ما بقى نموذج استمراري، صار انعكاس»",
                       "«بقيسه من",
                       "«بيفضّل يرجع يعمل ريتست»"):
            self.assertNotIn(phrase, text, f"عاد الاقتباسُ المحرَّف: {phrase}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
