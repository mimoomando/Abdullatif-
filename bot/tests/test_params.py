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


class TestTheLedgerMatchesTheLiveConfig(unittest.TestCase):
    """
    ⛔⛔ **الدفترُ والقيمُ المشغَّلة في موضعين — وهذا خطرُ انحرافٍ بذاته.**

    `params.py` دفترُ مصادر، و`ChainConfig` يحمل ما يعمل به البوت
    فعلًا. فلو تغيّر أحدُهما وحده، **لقال التوثيقُ رقمًا واشتغل
    البوتُ بآخر** — والقاعدةُ ① تصير زينة.

    ⇒ وهذا الاختبار يجعل ذلك **مستحيلًا** لا مكتشَفًا.
    """

    # اسمُ الحقل الحيّ  ⇔  اسمُ المعامل في الدفتر
    PAIRS = {
        "swing_lookback": "SWING_LOOKBACK",
        "swing_plateau": "SWING_PLATEAU_MODE",
        "refine_pick": "REFINE_PICK_RULE",
        "impulse_span": "IMPULSE_SPAN_RULE",
        "protected_not_target": "PROTECTED_NOT_TARGET",
        "thinning_proximity": "THINNING_PROXIMITY_POINTS",
        "pattern_tolerance": "PATTERN_EQUALITY_TOLERANCE",
        "degree_value": "DEGREE_VALUE",
        "gate_by_close": "GATE_BY_CLOSE",
        "line_chart_veto": "LINE_CHART_VETO",
        "ob_large_threshold": "OB_LARGE_THRESHOLD",
        "bpr_enabled": "BPR_ENABLED",
        "max_targets": "MAX_TARGETS",
        "max_stop": "MAX_STOP_DOLLARS",
        "max_spread": "MAX_SPREAD_DOLLARS",
        "daily_loss_limit": "DAILY_LOSS_LIMIT_DOLLARS",
        "inversion_enabled": "INVERSION_FVG_ENABLED",
        # ⭐ الستّةُ التي نُقلت إلى الدفتر 2026-09-26
        "direct_touch_only": "DIRECT_TOUCH_ONLY",
        "harmonic_enabled": "HARMONIC_ENABLED",
        "require_higher_trend": "REQUIRE_HIGHER_TREND",
        "higher_poi_required": "HIGHER_POI_REQUIRED",
        "refine_entry": "REFINE_ENTRY",
    }

    @classmethod
    def setUpClass(cls):
        from bot.chain import ChainConfig
        cls.cfg = ChainConfig("M15", "M3", spread=0.3)

    def test_every_pair_agrees(self):
        from bot import params as P
        for field, name in self.PAIRS.items():
            with self.subTest(field=field):
                self.assertEqual(
                    getattr(self.cfg, field), getattr(P, name).value,
                    f"انحراف: ChainConfig.{field} \u2260 params.{name}")

    def test_the_bare_constant_is_ledgered_and_agrees(self):
        """⛔ `MAX_TARGET_RR` كان رقمًا عاريًا خارج الدفتر."""
        from bot import params as P
        from bot.chain import MAX_TARGET_RR
        self.assertEqual(MAX_TARGET_RR, P.MAX_TARGET_RR.value)

    def test_the_break_gap_window_agrees_with_the_ledger(self):
        """
        ⛔ **PA1** — كانت `i - 1 <= g.index <= i + 2` رقمًا عاريًا داخل
        `patterns.activate`: يقرّر تفعيلَ النموذج بلا اسمٍ ولا سطرٍ في
        الدفتر. وكُشف 2026-09-27، فسُمّي وسُجّل.
        """
        from bot import params as P
        from bot.primitives.patterns import BREAK_GAP_AFTER, BREAK_GAP_BEFORE
        self.assertEqual((BREAK_GAP_BEFORE, BREAK_GAP_AFTER),
                         P.PATTERN_BREAK_GAP_WINDOW.value)

    def test_the_same_constant_is_not_allowed_to_drift_between_files(self):
        """⛔ ومكتوبٌ في موضعين — `chain.py` و`reporting.py`."""
        from bot.chain import MAX_TARGET_RR as a
        from bot.reporting import MAX_TARGET_RR as b
        self.assertEqual(a, b)

    def test_the_decision_switches_all_carry_a_source(self):
        """فمفتاحٌ يقرّر فتحَ صفقةٍ بلا وسمٍ يخالف القاعدة ①."""
        from bot import params as P
        for name in ("DIRECT_TOUCH_ONLY", "HARMONIC_ENABLED",
                     "REQUIRE_HIGHER_TREND", "HIGHER_POI_REQUIRED",
                     "REFINE_ENTRY", "MAX_TARGET_RR"):
            with self.subTest(param=name):
                self.assertIn(getattr(P, name).origin,
                              ("SOURCE", "USER", "MEASURED", "DERIVED"))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestNoNumberIsWrittenTwiceAndAllowedToDrift(unittest.TestCase):
    """
    ⛔⛔ **رقمٌ مكتوبٌ في موضعين يتباعد بصمت** — وقد وقع فعلًا في هذا
    المشروع (`MAX_TARGET_RR` في `chain.py` و`reporting.py`)، فحُرس.

    ⭐ **وهذا يوسّع الحرسَ إلى تسعةِ أرقامٍ أخرى** كُشفت 2026-09-27
    بمسحٍ آليّ: ثوابتُ `bat.py` و`continuation.py` لها سطورٌ في الدفتر
    **بأسماءٍ مختلفة**، فلا يربطها شيء.

    ⚠️ **ووحدةٌ غيرُ موصولةٍ لا تُعفى**: يومَ تُوصَل يكون الرقمُ قد
    تباعد، **والوصلُ حينها يُشغّل رقمًا لا أحد يعرف من أين جاء**.
    """

    @staticmethod
    def _same(a, b) -> bool:
        """قائمةٌ وصفٌّ متساويان إن تساوت عناصرُهما — فالنوعُ ليس المعنى."""
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            return tuple(a) == tuple(b)
        return a == b

    def test_the_bat_ratios_agree_with_the_module(self):
        from bot import params as P
        from bot.primitives import bat
        r = P.BAT_RATIOS.value
        for key, const in (("B_of_XA", "B_RETRACE"),
                           ("C_of_AB", "C_RETRACE"),
                           ("D_of_XA", "D_RETRACE"),
                           ("BD_of_BC", "BD_EXTENSION"),
                           ("stop_of_XA", "STOP_RETRACE")):
            with self.subTest(ratio=key):
                self.assertTrue(
                    self._same(r[key], getattr(bat, const)),
                    f"انحراف: BAT_RATIOS[{key!r}] ≠ bat.{const}")

    def test_the_continuation_numbers_agree_with_the_module(self):
        from bot import params as P
        from bot.primitives import continuation as c
        for name, const in (("CONTINUATION_MAX_RETRACE", "MAX_RETRACE"),
                            ("CONTINUATION_INVALIDATING_RETRACE",
                             "INVALIDATING_RETRACE"),
                            ("CONTINUATION_HIGHER_TIMEFRAMES",
                             "HIGHER_TIMEFRAMES")):
            with self.subTest(param=name):
                self.assertTrue(
                    self._same(getattr(P, name).value, getattr(c, const)),
                    f"انحراف: params.{name} ≠ continuation.{const}")

    def test_the_unstated_band_is_derived_from_the_two_thresholds(self):
        """
        ⭐ **وهذا أدقُّ من مقارنةٍ**: النطاقُ **مشتقٌّ** من الحدَّين، فلو
        تغيّر أحدُهما وبقي النطاقُ لكان الدفترُ يصف نطاقًا لا وجودَ له.
        """
        from bot import params as P
        from bot.primitives import continuation as c
        self.assertEqual(P.CONTINUATION_UNSTATED_BAND.value,
                         (c.MAX_RETRACE_HIGHER_TF, c.INVALIDATING_RETRACE))

    def test_the_two_new_defaults_agree_with_their_modules(self):
        """ومفاتيحُ اليوم: `DEFAULT_PLATEAU` · `DEFAULT_PICK` · `DEFAULT_SPAN`."""
        from bot import params as P
        from bot.chain import DEFAULT_SPAN
        from bot.primitives.refine import DEFAULT_PICK
        from bot.primitives.swings import DEFAULT_PLATEAU
        self.assertEqual(P.SWING_PLATEAU_MODE.value, DEFAULT_PLATEAU)
        self.assertEqual(P.REFINE_PICK_RULE.value, DEFAULT_PICK)
        self.assertEqual(P.IMPULSE_SPAN_RULE.value, DEFAULT_SPAN)

    def test_the_line_chart_default_follows_swings(self):
        """⚠️ وموضعُ SW1 الثاني — فلو تباعد الافتراضان تلوّث القياس."""
        from bot.primitives.line_chart import DEFAULT_PLATEAU as line
        from bot.primitives.swings import DEFAULT_PLATEAU as sw
        self.assertEqual(line, sw)


class TestTheLedgerSaysHowFarItsOwnClaimReaches(unittest.TestCase):
    """
    ⚠️ **PR1 · 2026-09-29.** `undefined_report` كان يطبع «⛔ ومنها N
    **لا يشغّلها كود**» — وN مأخوذٌ من `NOT_RUNNING`، **وهي قائمةٌ
    باليد لا يُفحَص اكتمالُها**.

    ⇒ فصار العددُ **أدنى حدٍّ لا حصرًا**، ويقول ذلك بنفسه.
    """

    def test_the_report_declares_the_count_is_a_floor(self):
        out = P.undefined_report()
        self.assertIn("على الأقلّ", out)
        self.assertIn("أدنى حدٍّ لا حصر", out)

    def test_every_idle_param_still_names_a_reason(self):
        for name, why in P.not_running().items():
            with self.subTest(param=name):
                self.assertIn(name, P.registry())
                self.assertTrue(why.strip())
