"""
اختبارات مفتاح الإيقاف.

⭐ «ضع ملفًّا اسمه STOP ⇒ يتوقّف · احذفه ⇒ يعود» — قرار المستخدم
(2026-09-20)، بُني بطلبه: «ابنِ مفتاح الإيقاف».
"""

import os
import pathlib
import tempfile
import unittest

from bot import killswitch as ks


class TestItSeesTheFile(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def _put(self, name, text=""):
        pathlib.Path(self.dir, name).write_text(text, encoding="utf-8")

    def test_nothing_means_running(self):
        self.assertFalse(ks.active(self.dir))
        self.assertIsNone(ks.path(self.dir))

    def test_a_bare_STOP_stops_it(self):
        self._put("STOP")
        self.assertTrue(ks.active(self.dir))

    def test_windows_silently_appends_txt_and_it_still_stops(self):
        """
        ⭐⭐ **وهذا ليس تسامحًا زائدًا.**

        ويندوز يخفي الامتدادات، والمفكّرةُ تُلحق `.txt` صامتةً. فمن
        أنشأ «STOP» بالمفكّرة يظنّه `STOP` وهو `STOP.txt`.

        ⛔ **ومفتاحُ إيقافٍ يفشل صامتًا لأنّ النظام أضاف ثلاثة أحرف
        أسوأ من عدمه** — لأنّ صاحبه يظنّ نفسه محميًّا.
        """
        self._put("STOP.txt")
        self.assertTrue(ks.active(self.dir))

    def test_lowercase_works_too(self):
        self._put("stop")
        self.assertTrue(ks.active(self.dir))

    def test_deleting_it_resumes(self):
        self._put("STOP")
        os.remove(os.path.join(self.dir, "STOP"))
        self.assertFalse(ks.active(self.dir))

    def test_an_unrelated_file_does_not_stop_it(self):
        self._put("STOPWATCH.md")
        self._put("notes.txt")
        self.assertFalse(ks.active(self.dir))


class TestItCarriesTheReason(unittest.TestCase):
    """⭐ من أوقفه الخميس وعاد الاثنين لا يذكر لماذا."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_the_note_inside_is_read(self):
        pathlib.Path(self.dir, "STOP").write_text("أخبار الفائدة",
                                                  encoding="utf-8")
        self.assertEqual(ks.reason(self.dir), "أخبار الفائدة")
        self.assertIn("أخبار الفائدة", ks.banner(self.dir))

    def test_an_empty_file_is_fine(self):
        pathlib.Path(self.dir, "STOP").write_text("", encoding="utf-8")
        self.assertEqual(ks.reason(self.dir), "")
        self.assertIn("KILL SWITCH IS ON", ks.banner(self.dir))

    def test_no_file_no_reason(self):
        self.assertEqual(ks.reason(self.dir), "")


class TestTheBannerIsReadable(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        pathlib.Path(self.dir, "STOP").write_text("", encoding="utf-8")

    def test_the_first_line_is_pure_ascii(self):
        """نافذة cmd تقلب العربيّة — والسطرُ الحاسم لا يعتمد عليها."""
        first = ks.banner(self.dir).splitlines()[0]
        self.assertTrue(first.isascii(), first)

    def test_it_says_how_to_resume(self):
        self.assertIn("delete the file", ks.banner(self.dir))

    def test_the_cleared_message_is_ascii_first(self):
        self.assertTrue(ks.CLEARED.splitlines()[0].isascii())


class TestTheRunnerHonoursIt(unittest.TestCase):
    """⛔ مفتاحٌ مبنيٌّ غير موصول لا يوقف شيئًا."""

    def setUp(self):
        self.src = pathlib.Path("bot/runner.py").read_text(encoding="utf-8")

    def test_the_runner_checks_it(self):
        self.assertIn("killswitch", self.src)

    def test_it_does_not_trip_the_silence_alarm(self):
        """
        ⚠️⚠️ **أخطرُ تفاعلٍ في هذا البند.**

        التمريرة المتوقّفة تُرجع صفرًا، وثلاثةُ أصفار توقظ إنذار «البوت
        صامت». فيصرخ الحارسُ من إيقافٍ **طلبه المستخدم**.

        وإنذارٌ كاذب مرّةً يُعلَّم صاحبُه أن يتجاهله — فيُهدر الحارس
        كلُّه، وهو الحارس الذي بُني بعد فقدان ثلاثة أيّام.

        ⇒ فالحلقة تعمل `continue` قبل `heart.beat` لا بعدها.
        """
        i = self.src.index("killswitch.active()")
        j = self.src.index("heart.beat", i)
        between = self.src[i:j]
        self.assertIn("continue", between,
                      "الإيقاف يمرّ على الحارس فيوقظ إنذارًا كاذبًا")


if __name__ == "__main__":
    unittest.main(verbosity=2)
