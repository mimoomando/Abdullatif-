"""
جردُ الوحدات غير الموصولة — **بالاستيراد الفعليّ، لا بالذاكرة.**

╔══════════════════════════════════════════════════════════════════╗
║  ⛔⛔⛔ **لماذا وُجد — خطأٌ في `CLAUDE.md` كُشف 2026-09-27.**        ║
║                                                                  ║
║  كان مكتوبًا: «وحداتٌ مبنيّةٌ غيرُ موصولة — **جُردت آليًّا**        ║
║  2026-09-26» ومعه **ثلاثُ** وحدات. **والعددُ الحقيقيّ 12** —      ║
║  تسعٌ منها في `bot/primitives/`، أي أنّ الجردَ السابق لم ينزل      ║
║  إلى المجلّد الفرعيّ أصلًا. (وهو **العطبُ نفسُه** الذي وقع في       ║
║  `bot/quotes.py` يومَها: `os.listdir` لا `os.walk`.)              ║
║                                                                  ║
║  ومن الاثنتي عشرة **سبعٌ لم تكن موثَّقةً بحرفٍ واحد**:              ║
║  `continuation` · `fake_break` · `key_zones` · `trendline` ·      ║
║  `volume` · `bat` · `butterfly`.                                 ║
║                                                                  ║
║  ⇒ **والجردُ يُعاد بمقارنة المستوردين، لا بالذاكرة** — كما تقول    ║
║  `CLAUDE.md` نفسُها. فصار اختبارًا: أيُّ وحدةٍ تُفصل عن السلسلة     ║
║  بعد اليوم **تُسقط الطقم** حتى تُسجَّل هنا صراحةً.                 ║
╚══════════════════════════════════════════════════════════════════╝

⚠️ **وهذا لا يقول إنّ الموصولةَ تعمل** — يقول إنّ غيرَ الموصولة
معروفةٌ بأسمائها. والوصلُ شرطٌ لازمٌ لا كاف.
"""

import ast
import os
import re
import unittest

BOT = "bot"

# مداخلُ تشغيلٍ تُنفَّذ بـ`python -m` — فغيابُ مستوردٍ لها **هو الصواب**
ENTRY_POINTS = {
    "backtest",       # python -m bot.backtest
    "daily_report",   # يُشغَّل من `run.bat`
    "demo_tools",     # python -m bot.demo_tools — أمرُ برهانٍ مستقلّ
    "quotes",         # python -m bot.quotes
    "runner",         # python -m bot.runner
}

# ⛔ الوحداتُ المبنيّةُ غيرُ الموصولة — **مسجَّلةٌ كي لا تُنسى**.
# وكلُّ سطرٍ هنا دَينٌ معلَن: كُتب وجُرِّب ولا يقرّر شيئًا اليوم.
UNWIRED = {
    # ① الثلاثةُ التي كانت موثَّقةً في `CLAUDE.md`
    "instructor":  "تحاليلُ المدرّب قبل القياس — ⭐ ومدخلُها التحاليلُ اليوميّة",
    "learning":    "diagnose() يفرّق «ضُرب الوقف» عن «الوقف ضيّق»",
    "observer":    "ما فعلته الشموع لا ما قرّره البوت",
    # ② وثمانٍ لم تكن — كُشفت 2026-09-27
    "structural":  "موثَّقةٌ في جدول «بُنيا ولم يُوصلا»",
    "channel":     "موثَّقةٌ في جدول «بُنيا ولم يُوصلا»",
    "bat":         "هارمونيك — والهارمونيك مُعطَّلٌ بقياس (خسر 21.30$)",
    "butterfly":   "هارمونيك — ولا يستوردها حتى `harmonic.py` نفسُه",
    "continuation": "⭐ النماذجُ الاستمراريّة — 332 سطرًا، واقتباساتُها "
                    "كانت محرَّفةً إلى 09-27",
    "fake_break":  "⭐ الكسرُ الوهميّ من الحقيقيّ — وهو بندٌ مركزيّ في وايكوف",
    "key_zones":   "⭐ المناطقُ المفتاحيّة — و`TARGET_KEY_ZONE_BUFFER` في الدفتر",
    "trendline":   "خطوطُ الاتّجاه والقنوات",
    "volume":      "⭐⭐ الفوليوم — و`VOLUME_WEAK_RATIO` و"
                   "`VOLUME_OPPOSING_LOOKBACK` في الدفتر كأنّهما عاملان",
}


# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⛔⛔⛔ **طبقةٌ أدقُّ من جرد الوحدات — كُشفت 2026-09-27.**           ║
# ║                                                                  ║
# ║  فوحدةٌ **موصولة** قد تحوي دالّةً عامّةً **لا يستدعيها شيء**.       ║
# ║  وجردُ الوحدات لا يراها: `patterns.py` موصولةٌ، و`find_engulfing` ║
# ║  فيها ميّتة — **والمدرّبُ سمّى الشمعةَ الابتلاعيّة نموذجًا          ║
# ║  انعكاسيًّا بلفظه**.                                              ║
# ║                                                                  ║
# ║  ⇒ فتُسجَّل هنا بأسمائها وأسبابها، ودالّةٌ جديدةٌ تموت **تُسقط     ║
# ║  الطقم** حتى تُسجَّل. وهذا لا يطلب وصلَها — يطلب **ألّا تختفي**.   ║
# ╚══════════════════════════════════════════════════════════════════╝
UNCALLED = {
    # ⭐⭐ ما يمسُّ الاستراتيجية — دَينٌ معلَن
    ("bot/primitives/patterns.py", "find_engulfing"):
        "⭐⭐ «شمعة ابتلاعية · دبل توب · **أي نموذج انعكاسي**» — سمّاها "
        "بلفظه، وبُنيت باقتباسه، **ولا تُستدعى**",
    ("bot/primitives/structure.py", "validate_swings"):
        "⭐⭐⭐ قاعدةُ «القمّة الحقيقيّة» (م2/د4): قمّةٌ تُعتبر حقيقيّةً إن "
        "كسرت الحركةُ التالية **القاعَ الحاكم**. مبنيّةٌ ولا تُستدعى",
    ("bot/primitives/structure.py", "governing_levels"):
        "⭐⭐⭐ «آخر قمّةٍ وقاعٍ هيكليَّين مؤكَّدين» — وهو **المرجعُ الذي "
        "تحتاجه بوّابةُ الاتّجاه** (السؤال المفتوح ④: 81 رفضًا من 221 "
        "بـ«الهيكل غير محدَّد»). مبنيٌّ ولا يُستدعى",
    ("bot/primitives/liquidity.py", "equal_levels"):
        "⭐ تجمّعاتُ السيولة عند القمم المتساوية («إيكوال هاي»)",
    ("bot/primitives/fvg.py", "mark_mitigated"):
        "⭐ الفجوةُ المُستهلَكة — و`FVG.mitigated` **لا يُقرأ في مكان**، "
        "فالحقلُ خامدٌ لا بوّابةٌ صامتة",
    # ✅ وخرجت `mark_protected` من هذه القائمة 2026-09-27 — وُصلت خلف
    #    مفتاح `protected_not_target` (🔴 PT1). **وحارسُ «لا تتعفّن»
    #    هو الذي أجبرني على حذفها** — وهو الغرضُ منه.
    ("bot/primitives/liquidity_map.py", "read_cycle"):
        "دورةُ CRT — ويمسُّ السؤالَ المفتوح ⑤ (نموذجُ الأسبوع)",
    ("bot/primitives/pivot.py", "pivot_point"):
        "نقاطُ البيفوت — الوحدةُ مستورَدةٌ ودالّتاها ميّتتان",
    ("bot/primitives/pivot.py", "position"):
        "موضعُ السعر من البيفوت",
    # 🔶 طلباتٌ للمستخدم بُنيت ولم تُوصَل
    ("bot/reporting.py", "full_report"):
        "🔶 وطلبُه: [أريد أيضًا شرحًا مفصلًا لماذا دخل الصفقة وماذا حدث "
        "أثناء عمل الصفقة كاملًا]",
    ("bot/render.py", "to_png"):
        "🔶 تحويلُ الشارت إلى صورة",
    ("bot/render.py", "legend"):
        "مفتاحُ الرسم",
    # ✅ ولا حاجةَ بها — القدرةُ مخدومةٌ في مكانٍ آخر أو تافهة
    ("bot/primitives/order_block.py", "breakers"):
        "✅ مرشِّحٌ مريحٌ فقط — و`state = \"breaker\"` يُضبط في التصنيف، "
        "و`chain.py` يستثني `failed`/`mitigated` **فيمرّ البريكر**",
    ("bot/primitives/order_block.py", "fresh_blocks"):
        "✅ مرشِّحٌ مريحٌ فقط — كسابقه",
    ("bot/primitives/swings.py", "last_swing"):
        "✅ مساعدٌ تافه",
    ("bot/local_config.py", "redact"):
        "✅ **وليست ثغرةً في القاعدة ③**: المستعمَلةُ هي `describe()` "
        "وهي لا تطبع قيمةً أصلًا، بل أسماءَ المفاتيح و«محجوبة». فهذه "
        "بديلٌ غيرُ مستعمَل",
    ("bot/params.py", "not_running"):
        "✅ واجهةٌ للقراءة — و`NOT_RUNNING` يُقرأ مباشرةً في التقرير",
}


def _modules():
    out = {}
    for root, _dirs, names in os.walk(BOT):
        if "tests" in root.split(os.sep):
            continue
        for name in names:
            if name.endswith(".py") and name != "__init__.py":
                out[name[:-3]] = os.path.join(root, name)
    return out


def _importers():
    """اسمُ الوحدة ⇒ مجموعةُ الملفّات التي تستوردها (بلا الاختبارات)."""
    seen = {}
    for root, _dirs, names in os.walk(BOT):
        if "tests" in root.split(os.sep):
            continue
        for name in names:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            for node in ast.walk(tree):
                parts = []
                if isinstance(node, ast.ImportFrom):
                    parts += (node.module or "").split(".")
                    parts += [a.name for a in node.names]
                elif isinstance(node, ast.Import):
                    for a in node.names:
                        parts += a.name.split(".")
                for p in parts:
                    if p:
                        seen.setdefault(p, set()).add(path)
    return seen


def unwired():
    """أسماءُ الوحدات التي لا يستوردها شيءٌ داخل `bot/`."""
    importers = _importers()
    out = set()
    for name, path in _modules().items():
        if importers.get(name, set()) - {path}:
            continue
        out.add(name)
    return out


def uncalled():
    """
    دوالٌّ عامّةٌ في وحداتٍ **موصولة** لا يستدعيها شيءٌ في `bot/`.

    ⚠️ **والاختباراتُ مستثناة عمدًا**: دالّةٌ لا يستدعيها إلّا اختبارُها
    **ميّتةٌ في الإنتاج** — وذلك بعينه ما يُخفي الدَّين.
    """
    text = {}
    for root, _dirs, names in os.walk(BOT):
        if "tests" in root.split(os.sep):
            continue
        for name in names:
            if name.endswith(".py"):
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as fh:
                    text[path.replace("\\", "/")] = fh.read()

    out = set()
    for path, body in text.items():
        stem = os.path.basename(path)[:-3]
        if stem in UNWIRED or stem in ENTRY_POINTS or stem == "__init__":
            continue
        for node in ast.parse(body, filename=path).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            word = re.compile(rf"\b{re.escape(node.name)}\b")
            if any(word.search(s) for p, s in text.items() if p != path):
                continue
            if len(word.findall(body)) > 1:      # تُستدعى داخل ملفِّها
                continue
            out.add((path, node.name))
    return out


class TestNoBuiltFunctionDiesQuietly(unittest.TestCase):
    """
    ⛔⛔ **«بُني، واختُبر، ولا يُستدعى»** — والفرقُ عن جرد الوحدات أنّ
    الوحدةَ هنا **موصولة**، فلا شيء يشير إلى الدَّين.
    """

    @classmethod
    def setUpClass(cls):
        cls.found = uncalled()

    def test_no_new_function_died_unrecorded(self):
        strays = sorted(self.found - set(UNCALLED))
        self.assertEqual(
            strays, [],
            "دالّةٌ عامّةٌ صارت بلا مستدعٍ ولم تُسجَّل في UNCALLED: %s" % strays)

    def test_the_registry_does_not_rot(self):
        """✅ ودالّةٌ **وُصلت** تُحذف من القائمة."""
        stale = sorted(set(UNCALLED) - self.found)
        self.assertEqual(
            stale, [], "صارت مستدعاةً — تُحذف من UNCALLED: %s" % stale)

    def test_every_entry_carries_a_reason(self):
        for key, why in UNCALLED.items():
            with self.subTest(fn=key):
                self.assertGreater(len(why.strip()), 10, "بلا سببٍ مكتوب")


class TestTheWiringInventoryIsHonest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.found = unwired()

    def test_no_module_quietly_fell_out_of_the_chain(self):
        """⛔ وحدةٌ انفصلت ولم تُسجَّل — **يُسقط الطقم**."""
        strays = sorted(self.found - set(UNWIRED) - ENTRY_POINTS)
        self.assertEqual(
            strays, [],
            "وحدةٌ بلا مستوردٍ ولم تُسجَّل في UNWIRED: %s" % strays)

    def test_the_inventory_does_not_rot(self):
        """✅ ووحدةٌ **وُصلت** تُحذف من القائمة — وإلّا كذبت القائمة."""
        stale = sorted(set(UNWIRED) - self.found)
        self.assertEqual(
            stale, [],
            "صارت موصولةً — تُحذف من UNWIRED ومن CLAUDE.md: %s" % stale)

    def test_the_entry_points_still_exist(self):
        missing = sorted(ENTRY_POINTS - set(_modules()))
        self.assertEqual(missing, [], "مدخلُ تشغيلٍ اختفى: %s" % missing)

    def test_the_ledger_declares_which_of_its_numbers_do_not_run(self):
        """
        ⛔⛔ **والدفترُ كان يُقرأ كأنّ كلَّ رقمٍ فيه سارٍ.** وليس كذلك:
        تسعةَ عشرَ معاملًا تنتمي إلى وحداتٍ غيرِ موصولة، **واثنان
        فقط** كانا يصرّحان بذلك في ملاحظتهما. ⇒ صار التصريحُ
        مركزيًّا في `params.NOT_RUNNING` ومحروسًا هنا.
        """
        from bot import params as P
        for name, why in P.not_running().items():
            with self.subTest(param=name):
                self.assertIn(name, P.registry(), "اسمٌ لا وجودَ له")
                self.assertTrue(why.strip(), "بلا سببٍ مكتوب")

    def test_a_not_running_param_of_a_wired_module_names_its_function(self):
        """
        ⚠️ **والوحدةُ الموصولة قد تحوي دالّةً لا يستدعيها شيء** — وهي
        طبقةٌ **أدقُّ** من جرد الوحدات، ولا يكشفها. فمن كان سببُه
        وحدةً موصولةً يلزمه أن يسمّي الدالّة.
        """
        from bot import params as P
        modules = {m for m in UNWIRED}
        for name, why in P.not_running().items():
            stem = why.split(".py")[0].split("/")[-1].strip()
            if stem in modules:
                continue
            with self.subTest(param=name):
                self.assertIn("()", why,
                              "وحدةٌ موصولة ⇒ سمِّ الدالّة التي لا تُستدعى")

    def test_the_count_matches_what_claude_md_claims(self):
        """
        ⭐ **والعددُ مذكورٌ في `CLAUDE.md`** — فيُفحَص، كي لا يتكرّر
        خطأُ «ثلاث» حين كانت إحدى عشرة.
        """
        with open("CLAUDE.md", encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(f"{len(UNWIRED)} وحدات غير موصولة", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
