"""
جردُ الوحدات غير الموصولة — **بالاستيراد الفعليّ، لا بالذاكرة.**

╔══════════════════════════════════════════════════════════════════╗
║  ⛔⛔⛔ **لماذا وُجد — خطأٌ في `CLAUDE.md` كُشف 2026-09-27.**        ║
║                                                                  ║
║  كان مكتوبًا: [وحداتٌ مبنيّةٌ غيرُ موصولة — **جُردت آليًّا**        ║
║  2026-09-26] ومعه **ثلاثُ** وحدات. **والعددُ الحقيقيّ 12** —      ║
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

# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⛔⛔⛔ **ثقبٌ في هذا الحارس نفسِه — كُشف 2026-09-28.**             ║
# ║                                                                  ║
# ║  `unwired()` تسأل: **[أيستوردها أحد؟]** — ولا تسأل: [أتُبلَغ من   ║
# ║  مدخلِ تشغيلٍ حقيقيّ؟]. والفرقُ ليس نظريًّا:                        ║
# ║                                                                  ║
# ║    • `daily_report` كانت **مسجَّلةً هنا مدخلَ تشغيل** بحجّة        ║
# ║      [يُشغَّل من `run.bat`] — و`run.bat` **لا يذكرها**، ولا          ║
# ║      `__main__` فيها أصلًا. 593 سطرًا لا تُنفَّذ.                   ║
# ║    • و`verdicts` يستوردها `daily_report` وحدَها ⇒ فلها             ║
# ║      مستوردٌ ⇒ فهي [موصولة] في عين الجرد — **وهي ميّتة**.          ║
# ║                                                                  ║
# ║  ⇒ وهذا هو **العطبُ نفسُه للمرّة الثالثة**: جردٌ لا ينزل إلى        ║
# ║  آخر الطريق (`os.listdir` في `quotes.py` · `bot/primitives/`      ║
# ║  في الجرد الأوّل · وها هو في الجرد ذاته).                         ║
# ║                                                                  ║
# ║  ⇒ فصار المقياسُ **البلوغَ من مدخلٍ يُبرهِن على نفسه**، لا وجودَ    ║
# ║  مستوردٍ — ومدخلُ التشغيل يلزمه `__main__` أو ذكرٌ في `run.bat`.   ║
# ╚══════════════════════════════════════════════════════════════════╝

# ⭐ المدخلُ الحيُّ الوحيد — وهو ما يشغّله `run.bat`
LIVE_ENTRY = {"runner"}

# أوامرُ يدٍ يشغّلها المستخدم بـ`python -m` — ولكلٍّ `__main__` يُفحَص
TOOL_ENTRY = {
    "backtest",       # python -m bot.backtest
    "demo_tools",     # python -m bot.demo_tools — أمرُ برهانٍ مستقلّ
    "quotes",         # python -m bot.quotes
    # ⭐⭐⭐ **وُصلت 2026-10-02 بطلب المستخدم** — وكانت أوّلَ سطرٍ في
    #   `UNWIRED`. ومدخلُها الحقيقيُّ وصل: تحاليلُ 28·29·30 سبتمبر،
    #   وفيها أوّلُ مقابلةٍ مباشرة (30/9: اشترى المدرّب 4182 وباع
    #   البوت 4182.52 — وكلاهما ربح).
    "instructor",     # python -m bot.instructor
}

ENTRY_POINTS = LIVE_ENTRY | TOOL_ENTRY

# ⛔ وحداتٌ **يستوردها أحدٌ** فلا يراها جردُ الوحدات — ولا يبلغها
#    مدخلُ تشغيل. وهذه أخطرُ من `UNWIRED`: لها مظهرُ الموصولة.
UNREACHABLE = {
    "verdicts": "⭐⭐ حكمُ المستخدم على الشكل — **يستوردها "
                "`daily_report` وحدَها**، وهي ميّتةٌ هي نفسُها. ⇒ "
                "فسؤالُ [هل كان الشكل مطابقًا؟] يصل في ملفّ الصفقة "
                "سطرًا يُملأ باليد، **ولا شيء يقرأ الجواب**",
}

# ⛔ الوحداتُ المبنيّةُ غيرُ الموصولة — **مسجَّلةٌ كي لا تُنسى**.
# وكلُّ سطرٍ هنا دَينٌ معلَن: كُتب وجُرِّب ولا يقرّر شيئًا اليوم.
UNWIRED = {
    # ① الثلاثةُ التي كانت موثَّقةً في `CLAUDE.md`
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
    # ③ وواحدةٌ كانت **مسجَّلةً مدخلَ تشغيل** — كُشفت 2026-09-28
    "daily_report": "⭐⭐⭐ 593 سطرًا: السجلُّ اليوميُّ · حزمةُ الحكم · "
                    "طلبُ [هل كان الشكل مطابقًا؟] · حصيلةُ الدقّة. "
                    "**كانت في `ENTRY_POINTS` بحجّة «يُشغَّل من "
                    "`run.bat`»** — ولا `__main__` فيها ولا ذكرَ لها "
                    "في `run.bat`. وما يصل المستخدمَ فعلًا هو "
                    "`runner.render_package`",
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
    # ⛔ واثنتان **أخفاهما البحثُ النصّيُّ عبر الملفّات** — كُشفتا 09-29
    ("bot/primitives/fvg.py", "group_adjacent"):
        "⭐⭐ تجميعُ الفجوات المتجاورة — و`FVG_GROUP_MAX_GAP_POINTS` "
        "معلَنٌ في `params.NOT_RUNNING` بسببها. ⛔ **وذلك السطرُ نفسُه "
        "هو ما أخفاها**: البحثُ النصّيُّ وجد اسمَها في نصِّ السبب "
        "فعدَّه استدعاءً — **فالملاحظةُ عن الدَّين كانت تمحو الدَّين**",
    ("bot/primitives/ob_lifecycle.py", "usable"):
        "⭐⭐ [ما لم يمت — **وهو وحده ما يُعرَض على السلسلة**] تقول "
        "ترويستُها، **ولا تُستدعى**. ⛔ وأخفاها **تصادمُ أسماء**: في "
        "`volume.py` خاصّيّةٌ اسمُها `usable` لا صلةَ لها بها",
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
    # ✅ وثلاثةٌ **غيابُ مستدعيها هو الغرضُ منها** — القاعدة ②
    ("bot/guards.py", "send_order"):
        "✅ **سلكُ تعثُّرٍ مقصود**: موجودةٌ لتفشل بصوتٍ عالٍ إن استدعاها "
        "كودٌ يومًا. فاستدعاؤها **هو** العطب، وغيابُه هو الصواب. "
        "(ظهرت 09-28 حين صار الفحصُ شجريًّا — وكان النصُّ يعدّ ذكرَها "
        "في رسالة الخطأ استدعاءً)",
    ("bot/guards.py", "modify_position"):
        "✅ سلكُ تعثُّرٍ مقصود — كسابقتها",
    ("bot/guards.py", "close_position"):
        "✅ سلكُ تعثُّرٍ مقصود — كسابقتها",
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


def _edges():
    """وحدة ⇒ الوحداتُ التي تستوردها هي (بلا الاختبارات)."""
    mods = _modules()
    out = {}
    for stem, path in mods.items():
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        found = set()
        for node in ast.walk(tree):
            parts = []
            if isinstance(node, ast.ImportFrom):
                parts += (node.module or "").split(".")
                parts += [a.name for a in node.names]
            elif isinstance(node, ast.Import):
                for a in node.names:
                    parts += a.name.split(".")
            found |= {p for p in parts if p in mods and p != stem}
        out[stem] = found
    return out


def unreached():
    """
    ⭐ الوحداتُ التي **لا يبلغها** مدخلُ تشغيل — ولو استوردها أحد.

    وهذا سؤالٌ **أدقُّ** من `unwired()`: وحدةٌ ميّتةٌ يستوردها جارٌ
    ميّتٌ تبدو موصولةً تمامًا. وبها خفيت `verdicts` خلف
    `daily_report`.
    """
    edges = _edges()
    seen, stack = set(), list(ENTRY_POINTS)
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        stack += list(edges.get(m, ()))
    return set(_modules()) - seen


def uncalled():
    """
    دوالٌّ عامّةٌ في وحداتٍ **موصولة** لا يستدعيها شيءٌ في `bot/`.

    ⚠️ **والاختباراتُ مستثناة عمدًا**: دالّةٌ لا يستدعيها إلّا اختبارُها
    **ميّتةٌ في الإنتاج** — وذلك بعينه ما يُخفي الدَّين.

    ⛔⛔ **UC1 — وكان الاستدعاءُ داخل الملفّ يُقاس بالنصّ · كُشف
    2026-09-28.** فـ`len(findall) > 1` **تَعُدُّ ذكرَ الاسم في تعليقٍ
    أو في نصٍّ استدعاءً**. وبها خفيت `replay.walk_managed`: اسمُها
    يَرِد في تعليقَين ولا يستدعيها شيء — **وهي التي تقيس سلّمَ نقل
    الوقف** (MG1).

    ⇒ صار الاستدعاءُ داخل الملفّ يُقرأ من **الشجرة** (`Name` ·
    `Attribute`) لا من النصّ.

    ⛔⛔ **UC2 — والبحثُ عبر الملفّات بقي نصّيًّا · صُحّح 2026-09-29.**

    وكنتُ كتبتُ يومَها أنّه [تساهلٌ في الاتّجاه الآمن: يبالغ في
    [مستدعاة] فلا يتّهم بريئًا]. **وذلك خطأ** — فالمبالغةُ في
    [مستدعاة] **تُخفي دَينًا حقيقيًّا**، وهي الجهةُ الغالية في هذا
    المشروع. وقد أخفت اثنتين، **كلٌّ بآليّةٍ أخرى**:

      • `fvg.group_adjacent` — **أخفاها سطرُ الدفتر الذي يوثّق
        موتَها**: `params.NOT_RUNNING` يذكر اسمَها في نصِّ السبب،
        فيجده البحثُ النصّيُّ [استدعاءً]. ⇒ **الملاحظةُ عن الدَّين
        كانت تمحو الدَّينَ من السجلّ.**

      • `ob_lifecycle.usable` — **أخفاها تصادمُ أسماء**: في
        `volume.py` خاصّيّةٌ اسمُها `usable` لا صلةَ لها بها.

    ⇒ فصار الاتّجاهان شجريَّين. ⚠️ **وتُقرأ التكنيةُ معهما**
    (`ast.alias`): `from .trail import ladder as trail_ladder`
    استدعاءٌ لـ`ladder` — **وبلا هذا اتُّهم بريئان**
    (`trail.ladder` · `higher_poi.required_for`).
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

    # ⭐ UC1+UC2 — إشاراتٌ **فعليّة** لا ذكرٌ في تعليقٍ أو نصّ، ومعها
    #   التكنية: `from .trail import ladder as trail_ladder` استدعاء.
    ref = {}
    for path, body in text.items():
        seen = set()
        for n in ast.walk(ast.parse(body, filename=path)):
            if isinstance(n, ast.Name):
                seen.add(n.id)
            elif isinstance(n, ast.Attribute):
                seen.add(n.attr)
            elif isinstance(n, ast.alias):
                seen.add(n.name.split(".")[-1])
        ref[path] = seen

    out = set()
    for path, body in text.items():
        stem = os.path.basename(path)[:-3]
        # ⚠️ و`UNREACHABLE` مستثناةٌ هنا عمدًا: وحدةٌ **كلُّها** ميّتةٌ
        #    مُعلَنةٌ بذلك أعلاه، وسردُ دوالّها فردًا فردًا ضجيجٌ يُغرق
        #    الدَّينَ الحقيقيَّ في وحدةٍ تعمل.
        if (stem in UNWIRED or stem in ENTRY_POINTS
                or stem in UNREACHABLE or stem == "__init__"):
            continue
        tree = ast.parse(body, filename=path)
        here = ref[path]
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            if any(node.name in r for p, r in ref.items() if p != path):
                continue
            if node.name in here:                # تُستدعى داخل ملفِّها
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

    def test_the_module_a_ledger_entry_blames_is_really_dead(self):
        """
        ⛔⛔ **PR1 — و`NOT_RUNNING` قائمةٌ باليد لا يفحصها شيء في أيّ
        اتّجاه · كُشف 2026-09-29.**

        فالفحصُ القائم يسأل: أللاسم وجودٌ في الدفتر؟ وأله سببٌ مكتوب؟
        **ولا يسأل: أالوحدةُ التي يتّهمها ميّتةٌ فعلًا؟** ⇒ فلو وُصلت
        `volume.py` غدًا لبقي الدفترُ يقول إنّ معاملاتِها لا تعمل،
        **ويطبع `undefined_report` ⛔ كاذبة**.

        ⇒ وهذا هو الاتّجاهُ **القابلُ للفحص** من الاثنين. (والآخر —
        اكتمالُ القائمة — **لا يُفحص آليًّا**: أسماءُ الدفتر أسماءُ
        توثيقٍ لا معرّفاتٌ يقرؤها الكود، فموضعُ تطبيقِ المعامل غيرُ
        مكتشَفٍ بالاسم. وذلك **مُعلَنٌ في `undefined_report` نفسِه**.)
        """
        from bot import params as P
        dead = set(UNWIRED) | set(UNREACHABLE)
        called = {fn for _path, fn in UNCALLED}
        for name, why in P.not_running().items():
            with self.subTest(param=name):
                if "()" in why:
                    fn = why.split("(")[0].split(".")[-1].strip()
                    self.assertIn(fn, called,
                                  "دالّةٌ صارت مستدعاةً — يُراجَع الدفتر")
                    continue
                stem = why.split(".py")[0].split("/")[-1].strip()
                self.assertIn(
                    stem, dead,
                    "الوحدةُ صارت تعمل — فالدفترُ يكذب على قارئه")

    def test_a_not_running_param_of_a_wired_module_names_its_function(self):
        """
        ⚠️ **والوحدةُ الموصولة قد تحوي دالّةً لا يستدعيها شيء** — وهي
        طبقةٌ **أدقُّ** من جرد الوحدات، ولا يكشفها. فمن كان سببُه
        وحدةً موصولةً يلزمه أن يسمّي الدالّة.
        """
        from bot import params as P
        modules = set(UNWIRED) | set(UNREACHABLE)
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


class TestAnEntryPointMustProveItIsOne(unittest.TestCase):
    """
    ⛔⛔ **و`ENTRY_POINTS` كانت إعفاءً بلا برهان** — يكفي أن أكتب
    الاسمَ فيها لتخرج الوحدةُ من كلّ فحص. وبها مرّت `daily_report`
    ثلاثةَ أسابيعَ [تُشغَّل من `run.bat`] و`run.bat` لا يذكرها.

    ⇒ فالمدخلُ يُثبت نفسَه: إمّا `__main__` في الملفّ، وإمّا ذكرٌ
    صريحٌ في `run.bat`.
    """

    def test_every_entry_point_is_runnable(self):
        for stem in sorted(ENTRY_POINTS):
            with self.subTest(module=stem):
                with open(_modules()[stem], encoding="utf-8") as fh:
                    self.assertIn(
                        "__main__", fh.read(),
                        "لا `__main__` — فليست مدخلَ تشغيلٍ مهما قالت القائمة")

    def test_the_live_entry_is_the_one_run_bat_starts(self):
        """⭐ والمدخلُ الحيُّ يُقرأ من `run.bat` لا من ذاكرتي."""
        with open("run.bat", encoding="utf-8") as fh:
            bat = fh.read()
        for stem in sorted(LIVE_ENTRY):
            with self.subTest(module=stem):
                self.assertIn(f"bot.{stem}", bat, "لا يشغّله `run.bat`")


class TestReachabilityNotJustImports(unittest.TestCase):
    """
    ⭐⭐⭐ **الطبقةُ الثالثة: [يستوردها أحد] ≠ [تعمل].**

    فوحدةٌ يستوردها جارٌ ميّتٌ تبدو موصولةً في جرد الوحدات تمامًا.
    وبها خفيت `verdicts` — كلُّ آلةِ [هل كان الشكل مطابقًا؟] — خلف
    `daily_report` التي لا تعمل هي نفسُها.
    """

    @classmethod
    def setUpClass(cls):
        cls.found = unreached()

    def test_no_module_is_quietly_out_of_reach(self):
        strays = sorted(self.found - set(UNWIRED) - set(UNREACHABLE))
        self.assertEqual(
            strays, [],
            "لا يبلغها مدخلُ تشغيلٍ ولم تُسجَّل: %s" % strays)

    def test_the_unreachable_list_does_not_rot(self):
        """✅ ووحدةٌ صار يبلغها مدخلٌ تُحذف — وإلّا كذبت القائمة."""
        stale = sorted(set(UNREACHABLE) - self.found)
        self.assertEqual(
            stale, [], "صارت تُبلَغ — تُحذف من UNREACHABLE: %s" % stale)

    def test_unreachable_is_not_a_duplicate_of_unwired(self):
        """
        ⚠️ والقائمتان تقولان شيئين مختلفين: `UNWIRED` **لا يستوردها
        أحد**، و`UNREACHABLE` **يستوردها أحدٌ ولا تعمل**. فخلطُهما
        يُضيع الفرقَ الذي كشف العطب.
        """
        both = sorted(set(UNREACHABLE) & set(UNWIRED))
        self.assertEqual(both, [], "اسمٌ في القائمتين: %s" % both)
        for stem in UNREACHABLE:
            with self.subTest(module=stem):
                self.assertNotIn(stem, unwired(), "بلا مستوردٍ ⇒ مكانُها UNWIRED")

    def test_every_entry_carries_a_reason(self):
        for stem, why in UNREACHABLE.items():
            with self.subTest(module=stem):
                self.assertGreater(len(why.strip()), 10, "بلا سببٍ مكتوب")


if __name__ == "__main__":
    unittest.main(verbosity=2)
