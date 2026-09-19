"""
اختبارات قفل النسخة الواحدة.

⛔ **والعطب الذي بُني له وقع فعلًا (2026-09-19):** حدّث المستخدم
الكود وشغّل البوت في نافذةٍ جديدة، و**القديمة ما زالت تعمل** — فصار
مسجّلان يُلحقان في `runs/decisions.jsonl` معًا، وأحدُهما يشغّل الكود
**قبل** إصلاح جدول الامتدادات.

وهو انتبه وسأل. ولا يصحّ أن يعتمد الأمرُ على انتباهه.
"""

import os
import pathlib
import tempfile
import unittest

from bot.lock import AlreadyRunning, SingleInstance


class TestOnlyOneMayHoldIt(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "runs", "runner.lock")

    def tearDown(self):
        for g in getattr(self, "_open", []):
            g.release()

    def _guard(self):
        g = SingleInstance(self.path)
        self._open = getattr(self, "_open", []) + [g]
        return g

    def test_the_first_one_takes_it(self):
        self._guard().acquire("first")
        self.assertTrue(os.path.exists(self.path))

    def test_the_second_one_is_refused(self):
        self._guard().acquire("first")
        with self.assertRaises(AlreadyRunning):
            self._guard().acquire("second")

    def test_the_refusal_carries_who_holds_it(self):
        """
        ⭐ ورسالةٌ بلا «متى بدأت الأخرى» لا تدلّ على أيّ نافذةٍ يُغلق.
        """
        self._guard().acquire("pid 4242 since 2026-09-19 22:10")
        with self.assertRaises(AlreadyRunning) as caught:
            self._guard().acquire("second")
        self.assertIn("4242", str(caught.exception))

    def test_releasing_hands_it_over(self):
        first = self._guard()
        first.acquire("first")
        first.release()
        self._guard().acquire("second")          # لا يرفع

    def test_release_is_safe_to_call_twice(self):
        g = self._guard()
        g.acquire("first")
        g.release()
        g.release()                               # ولا ينفجر

    def test_it_works_as_a_context_manager(self):
        with self._guard() as g:
            g.acquire("inside")
            with self.assertRaises(AlreadyRunning):
                self._guard().acquire("outside")
        self._guard().acquire("after")            # أُطلق عند الخروج

    def test_a_leftover_file_does_not_block_anyone(self):
        """
        ⭐⭐ **وهذا ما يفرّق قفلَ النظام عن ملفّ الـPID.**

        انقطاعُ الكهرباء يترك الملفّ ولا يترك عمليّة. فملفُّ الـPID
        يمنع التشغيل بلا سبب — والمستخدمُ يحذفه يدويًّا أو يستسلم.
        وقفلُ النظام يُطلَق مع موت العمليّة، فالملفُّ الباقي لا يعني
        شيئًا.
        """
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        pathlib.Path(self.path).write_text("#pid 999 since يومٍ مضى",
                                           encoding="utf-8")
        self._guard().acquire("fresh")            # لا يرفع

    def test_the_note_survives_a_takeover(self):
        first = self._guard()
        first.acquire("first")
        first.release()
        second = self._guard()
        second.acquire("second")
        self.assertEqual(second.note(), "second")


class TestTheRunnerActuallyUsesIt(unittest.TestCase):
    """⛔ قفلٌ مبنيٌّ غير موصولٍ لا يحرس شيئًا."""

    def test_runner_locks_before_it_records(self):
        src = pathlib.Path("bot/runner.py").read_text(encoding="utf-8")
        self.assertIn("SingleInstance", src)
        self.assertIn("AlreadyRunning", src)

    def test_the_refusal_opens_with_a_pure_ascii_line(self):
        """نافذة cmd تقلب العربيّة — والرسالةُ الحاسمة لا تعتمد عليها."""
        src = pathlib.Path("bot/runner.py").read_text(encoding="utf-8")
        line = "[!!] ANOTHER BOT IS ALREADY RUNNING"
        self.assertIn(line, src)
        self.assertTrue(line.isascii())


if __name__ == "__main__":
    unittest.main(verbosity=2)
