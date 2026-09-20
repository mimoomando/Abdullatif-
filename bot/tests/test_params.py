"""
اختبارات سجلّ المعاملات.

⭐ **لماذا يُختبَر ملفُّ ثوابت؟** لأن `params.py` ليس ثوابت: هو
**دفتر النسب** — كل رقمٍ فيه يحمل مصدره، وعليه يقوم شرطُ المشروع:
«لا قاعدة بلا مصدر». وعطبٌ صامتٌ فيه لا يُسقط اختبارًا ولا يرفع
استثناءً — يضيع سطرًا فحسب.

وقد وقع ذلك فعلًا: عُرِّف `NEWS_FILTER` مرّتين، فطمس الثاني الأولَ
في `registry()` وضاع قرارُ المستخدم بلا أثر.
"""

import re
import unittest

from bot import params as P


class TestNoSilentOverwrite(unittest.TestCase):
    def test_no_parameter_is_defined_twice(self):
        """
        ⛔ الاسم المكرَّر يطمس سابقه صامتًا — ولا شيء يشكو.

        يُقرأ **نصّ الملفّ** لا `registry()`: فالسجلّ يرى الأخير وحده،
        وهو بالضبط ما يخفي العطب.
        """
        with open(P.__file__, encoding="utf-8") as fh:
            names = re.findall(r"^([A-Z][A-Z0-9_]*) = Param\(", fh.read(), re.M)
        dupes = {n for n in names if names.count(n) > 1}
        self.assertEqual(dupes, set(), f"معاملات مكرَّرة: {sorted(dupes)}")

    def test_the_registry_sees_every_definition(self):
        with open(P.__file__, encoding="utf-8") as fh:
            names = re.findall(r"^([A-Z][A-Z0-9_]*) = Param\(", fh.read(), re.M)
        self.assertEqual(len(names), len(P.registry()))


class TestEveryParamCarriesItsSource(unittest.TestCase):
    def test_origins_are_from_the_five_known(self):
        for name, p in P.registry().items():
            with self.subTest(name=name):
                self.assertIn(p.origin,
                              ("SOURCE", "USER", "MEASURED", "DERIVED", "UNDEFINED"))

    def test_measured_params_say_they_are_read_not_heard(self):
        """
        ⭐ `MEASURED` مصدرٌ دون `SOURCE` — رقمٌ قُرئ من شاشته لا من فمه.

        فلا يجوز أن يمرّ بلا تنبيهٍ على أنه لا يُبنى عليه قرار: مثالٌ
        واحد يثبت أنه استعمل الرقم، لا أنه قاعدةٌ عنده.
        """
        found = P.by_origin("MEASURED")
        self.assertTrue(found, "لا معامل مقيس — احذف الصنف أو استعمله")
        for name, p in found.items():
            with self.subTest(name=name):
                self.assertIn("🎥", p.lesson, f"{name}: المرجع لا يسمّي الفيديو")
                self.assertTrue(
                    "⛔" in p.note or "⚠️" in p.note,
                    f"{name}: معاملٌ مقيسٌ بلا تحذيرٍ من البناء عليه")

    def test_none_is_left_without_a_reference(self):
        for name, p in P.registry().items():
            with self.subTest(name=name):
                self.assertTrue(p.lesson.strip(), f"{name} بلا مرجع")

    def test_derived_and_undefined_explain_themselves(self):
        """المشتقّ والمعلَّق هما ما يحتاج تبريرًا — لا المنقول عن الدرس."""
        for name, p in P.registry().items():
            if p.origin in ("DERIVED", "UNDEFINED"):
                with self.subTest(name=name):
                    self.assertTrue(p.note.strip(), f"{name} بلا تعليل")


class TestTheWeeksMeasurements(unittest.TestCase):
    """
    ⭐ المعاملات المستخرَجة من أسبوع 09-07…11 — وقيمتها هي **القياس**،
    فإن تغيّرت بلا قياسٍ جديد فقد انقطعت صلتها بما تدّعيه.
    """

    def test_the_stop_cap_matches_the_chain(self):
        from bot.chain import ChainConfig
        c = ChainConfig("H1", "M5", spread=0.3)
        self.assertEqual(c.max_stop, P.MAX_STOP_DOLLARS.value)
        self.assertEqual(c.max_spread, P.MAX_SPREAD_DOLLARS.value)

    def test_the_stop_cap_sits_between_the_two_measured_bounds(self):
        """فوق 13.30$ التي احتاجها الرابحون · ودون 24$ التي سمّاها كارثية."""
        self.assertGreater(P.MAX_STOP_DOLLARS.value, 13.30)
        self.assertLess(P.MAX_STOP_DOLLARS.value, 24.0)

    def test_the_bias_gate_stayed_shut_because_the_data_refused_it(self):
        """
        🔴 اقتُرحت ثم نُقضت: الموافق لـ H4 خسر (1/6) والمخالف ربح (3/0).
        """
        self.assertFalse(P.H4_BIAS_GATE.value)
        self.assertIn("نقضتها البيانات", P.H4_BIAS_GATE.note)

    def test_the_rr_filter_was_refused_as_overfitting(self):
        """⛔ 1.00 ⇒ +7.38$ و1.25 ⇒ −40.38$ — رقمٌ معلَّق بصفقةٍ واحدة."""
        self.assertIsNone(P.MIN_RISK_REWARD.value)
        self.assertEqual(P.MIN_RISK_REWARD.origin, "UNDEFINED")

    def test_the_repetition_fix_is_on(self):
        """عطبٌ ميكانيكيّ لا قاعدة تداوليّة — ولذلك يُثبَّت بلا استئذان."""
        self.assertTrue(P.ANNOUNCE_SETUP_ONCE.value)


class TestSourceStaysAboveEverything(unittest.TestCase):
    """⛔ الشرط الحاكم: البوت لا يخترع قاعدة، والمصدر لا يُضبَط بالبيانات."""

    def test_a_derived_param_never_claims_a_lesson_it_has_no_text_for(self):
        for name, p in P.by_origin("DERIVED").items():
            with self.subTest(name=name):
                self.assertNotEqual(p.lesson, "-")

    def test_the_instructors_own_bound_is_still_recorded(self):
        self.assertIn("24", P.MAX_STOP_DOLLARS.note)


class TestFibTargetsAreRecorded(unittest.TestCase):
    """
    ⭐ «أوّل واحد **100%** هو الممتاز، الثاني من بعد منه **138**،
    **161** و**184**» (الأنماط الاستمراريّة ≈23:46).

    وأحال إليها في الأوردر بلوك ج3: «الأهداف عن طريق فيبوناتشي —
    وعطيت النسب». ⇒ فالأربعةُ في `MAX_TARGETS` **أربعُ نسبٍ بأعيانها**،
    لا سقفٌ اعتباطيّ.
    """

    def test_the_four_ratios_are_source(self):
        self.assertEqual(P.FIB_EXTENSION_TARGETS.origin, "SOURCE")
        self.assertEqual(len(P.FIB_EXTENSION_TARGETS.value), 4)
        self.assertEqual(P.FIB_EXTENSION_TARGETS.value[0], 1.00)

    def test_they_agree_with_the_built_extension_levels(self):
        """⛔ ورقمٌ في مكانين يتباعد — فيُفحَص تطابقُهما."""
        from bot.primitives.fibonacci import EXTENSION_LEVELS
        self.assertEqual(len(EXTENSION_LEVELS), len(P.FIB_EXTENSION_TARGETS.value))
        self.assertEqual(EXTENSION_LEVELS[0], 1.0)
        self.assertEqual(EXTENSION_LEVELS[-1], 1.84)

    def test_the_target_count_matches_the_ratio_count(self):
        self.assertEqual(P.MAX_TARGETS.value, len(P.FIB_EXTENSION_TARGETS.value))

    def test_the_first_target_at_the_break_is_recorded(self):
        self.assertEqual(P.FIRST_TARGET_AT_THE_BREAK.origin, "SOURCE")
        self.assertTrue(P.FIRST_TARGET_AT_THE_BREAK.value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
