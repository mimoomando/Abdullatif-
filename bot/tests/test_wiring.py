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
