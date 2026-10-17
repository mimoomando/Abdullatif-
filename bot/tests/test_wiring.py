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
    # ╔══════════════════════════════════════════════════════════════╗
    # ║  ⭐⭐⭐ **وُصلت 2026-10-17 بطلب المستخدم** — 635 سطرًا كانت    ║
    # ║  **لم تُنفَّذ قطّ**، وهي أثقلُ سطرٍ في `UNWIRED`.               ║
    # ║                                                              ║
    # ║  ⛔⛔⛔ **والفرقُ عن إقامتها السابقة هنا جوهريّ**: كانت        ║
    # ║  مسجَّلةً في `ENTRY_POINTS` **بحجّة [يُشغَّل من `run.bat`]**     ║
    # ║  — ولا ذكرَ لها فيه ولا `__main__` فيها. **وذلك هو عينُ      ║
    # ║  العطب الذي أوجد هذا الحارس.** ⇒ **فلا تدخل اليومَ إلّا       ║
    # ║  و`__main__` فيها، ويفحصه `TestEntryPointsProveThemselves`.** ║
    # ╚══════════════════════════════════════════════════════════════╝
    "daily_report",   # python -m bot.daily_report --day YYYY-MM-DD
}

ENTRY_POINTS = LIVE_ENTRY | TOOL_ENTRY

# ⛔ وحداتٌ **يستوردها أحدٌ** فلا يراها جردُ الوحدات — ولا يبلغها
#    مدخلُ تشغيل. وهذه أخطرُ من `UNWIRED`: لها مظهرُ الموصولة.
UNREACHABLE = {
    # ✅✅✅ وخرجت `verdicts` من هنا 2026-10-17 — **لا بعملٍ فيها، بل
    #    لأنّ مستوردَها الوحيد (`daily_report`) صار له `__main__`.**
    #    ⇒ **وهو برهانُ أنّ هذه القائمةَ تقيس ما تقول**: الوحدةُ لم
    #    تُمَسّ بحرف، والذي تغيّر أنّ الطريقَ إليها صار مسلوكًا.
    #    ⭐ و`--verdicts FILE` يطبّق الردّ، و`Accuracy` تُحسب وتُطبع.
    # ╔══════════════════════════════════════════════════════════════╗
    # ║  ⛔⛔⛔ **ونُقلت `channel` إلى هنا 2026-10-16 — والحارسُ هو   ║
    # ║  الذي أجبرني.**                                              ║
    # ║                                                              ║
    # ║  بُني TL1 فاستوردت `trendline` دالّةَ `channel.anchor_ok`     ║
    # ║  — **إعادةُ استعمالٍ مقصودة**، كي لا يُكتب شرطان لنصٍّ         ║
    # ║  واحدٍ فيفترقا يومًا (صنفُ OB2).                              ║
    # ║                                                              ║
    # ║  ⇒ **فصار لها مستوردٌ ⇒ فخرجت من `UNWIRED`** — وأسقط         ║
    # ║  الحارسُ الطقمَ. ⭐⭐⭐ **وهو `verdicts` بعينه**: مستوردُها     ║
    # ║  (`trendline`) **ميّتٌ هو نفسُه** ⇒ فلها مظهرُ الموصولة        ║
    # ║  ولا يبلغها قرار.                                            ║
    # ║                                                              ║
    # ║  ⚠️⚠️ **ولولا الحارسُ لمرّت**: كنتُ سأكتب [وُصلت `channel`]،  ║
    # ║  **وهو كذبٌ** — وصلٌ إلى ميّتٍ ليس وصلًا.                      ║
    # ║                                                              ║
    # ║  ⇒ **والبديلُ المرفوض**: نسخُ شرط المرتكز في `trendline`      ║
    # ║  ليبقى الجردُ هادئًا — **أي إفسادُ الكود لإراحة حارس.**        ║
    # ╚══════════════════════════════════════════════════════════════╝
    "channel": "⭐ القناةُ الأوفى للنصّ — **يستوردها `trendline` "
               "وحدَها** (لـTL1 · `anchor_ok`)، و`trendline` ميّتةٌ "
               "هي نفسُها ⇒ **فلا قرارَ يبلغها**. وهي موثَّقةٌ في "
               "جدول «بُنيا ولم يُوصلا»",
}

# ⛔ الوحداتُ المبنيّةُ غيرُ الموصولة — **مسجَّلةٌ كي لا تُنسى**.
# وكلُّ سطرٍ هنا دَينٌ معلَن: كُتب وجُرِّب ولا يقرّر شيئًا اليوم.
UNWIRED = {
    # ① وكانت هنا `learning` — ✅ **وُصلت 2026-10-03** عبر
    #    `replay.autopsy` (`--autopsy`)، وهو مدخلٌ يُبرهِن على نفسه.
    #    ⭐ ووصلُها أغلق LN1 وLN2 معًا في ذلك المسار: الرصدُ حقيقيٌّ
    #    شمعةً شمعة، و`after` تصل من `followups.jsonl`.
    "observer":    "ما فعلته الشموع لا ما قرّره البوت",
    # ② وثمانٍ لم تكن — كُشفت 2026-09-27
    "structural":  "موثَّقةٌ في جدول «بُنيا ولم يُوصلا»",
    "bat":         "هارمونيك — والهارمونيك مُعطَّلٌ بقياس (خسر 21.30$)",
    "butterfly":   "هارمونيك — ولا يستوردها حتى `harmonic.py` نفسُه",
    "continuation": "⭐ النماذجُ الاستمراريّة — 332 سطرًا، واقتباساتُها "
                    "كانت محرَّفةً إلى 09-27",
    "fake_break":  "⭐ الكسرُ الوهميّ من الحقيقيّ — وهو بندٌ مركزيّ في وايكوف",
    "key_zones":   "⭐ المناطقُ المفتاحيّة — و`TARGET_KEY_ZONE_BUFFER` في الدفتر",
    "trendline":   "خطوطُ الاتّجاه والقنوات",
    "volume":      "⭐⭐ الفوليوم — و`VOLUME_WEAK_RATIO` و"
                   "`VOLUME_OPPOSING_LOOKBACK` في الدفتر كأنّهما عاملان",
    # ③ وكانت هنا `daily_report` — ✅✅✅ **وُصلت 2026-10-17**، وهي
    #    في `TOOL_ENTRY` أعلاه بـ`__main__` يُفحَص. ⭐ **ومعها خرجت
    #    `verdicts` من `UNREACHABLE`** بلا سطرٍ واحدٍ فيها.
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
    # ⛔⛔ **ووصلُ دالّةٍ ليس وصلَ وحدة — كُشف 2026-10-03.**
    #    وُصلت `learning.diagnose` عبر `replay.autopsy`، فخرجت الوحدةُ
    #    من `UNWIRED` — **وأسقط الحارسُ الطقمَ فورًا** لأنّ دالّتين
    #    فيها بقيتا بلا مستدعٍ. ⇒ **وذلك هو الصواب**: الوحدةُ صارت
    #    مقروءةً فصار دَينُها الداخليُّ مرئيًّا، ولم يكن مرئيًّا قبلها.
    ("bot/learning.py", "lessons"):
        "⭐ يستخرج الدروسَ المتكرّرة من دفاترَ كثيرة — **ويحتاج "
        "دفاترَ مجمَّعة**، و`autopsy` تشخّص صفقةً صفقةً. دَينٌ معلَن",
    ("bot/learning.py", "render_lessons"):
        "عرضُ ما تُخرجه `lessons` — يتبعها، فيموت بموتها",
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


class TestTheBatchOf1016IsGuarded(unittest.TestCase):
    """
    ⭐⭐⭐ **حُرّاسُ دفعة 2026-10-16** — KS2 · HA1/BT2/BF2 · TM1 · TL1.

    ⚠️ **وكلُّها مطفأةٌ، فالحارسُ على شيئين**: أنّ القائمَ لم يتغيّر،
    **وأنّ المفتاحَ يبلغ القرارَ فعلًا** — وهو صنفُ LB1.
    """

    # ── KS2 ──

    def test_the_killswitch_scope_is_still_all(self):
        from bot import killswitch
        from bot.runner import RunConfig
        self.assertEqual(killswitch.DEFAULT_SCOPE, "all")
        self.assertEqual(RunConfig().killswitch_scope, "all")

    def test_a_stopped_row_is_dropped_and_counted_not_silent(self):
        """
        ⭐⭐⭐ **وهو الثمنُ الذي سمّاه جدولُ الطريق ②**: رايةٌ في
        الصفّ **وقرار**. ⇒ تُسقَط **وتُعَدّ**.

        ⛔ **والصمتُ هو المرفوضُ وحدَه**: أن تُحسَب بلا تمييزٍ أو
        تُستثنى بلا عدّ — **وكلاهما صنفُ RW2.**
        """
        from bot import replay
        rows = [
            {"disposition": "taken", "poi_tf": "M15", "direction": "buy",
             "entry": 100.0, "stop": 99.0, "targets": [103.0],
             "candle_time": "2026-10-16T09:00"},
            {"disposition": "taken", "poi_tf": "M15", "direction": "buy",
             "entry": 200.0, "stop": 199.0, "targets": [203.0],
             "candle_time": "2026-10-16T09:15", "stopped": True},
        ]
        got = replay.setups_from(rows)
        self.assertEqual(len(got), 1, "⇒ المكتومُ لا يصير صفقة")
        self.assertEqual(replay.stopped_dropped, 1, "⇒ ويُعَدّ")
        self.assertIn("[!!]", replay.render([]))

    def test_and_the_count_resets_so_it_never_accumulates(self):
        """⚠️ **وعدّادٌ يتراكم يكذب على التشغيل الثاني.**"""
        from bot import replay
        replay.setups_from([{"disposition": "taken", "poi_tf": "M15",
                             "entry": 1.0, "stop": 0.5, "targets": [2.0],
                             "stopped": True}])
        self.assertEqual(replay.stopped_dropped, 1)
        replay.setups_from([])
        self.assertEqual(replay.stopped_dropped, 0)

    def test_the_flag_is_raised_at_write_time(self):
        """⭐ **الرايةُ عند الكتابة لا بعدها** — فالصفُّ يحمل أثرَه معه."""
        import inspect

        from bot import runner
        src = inspect.getsource(runner.Recorder.write)
        self.assertIn("killswitch.STOPPED_FLAG", src)
        self.assertIn('killswitch_scope == "alerts"', src)

    # ── HA1 · BT2 · BF2 ──

    def test_the_scan_default_is_adjacent_in_all_three(self):
        from bot.chain import ChainConfig
        from bot.primitives import bat, butterfly, harmonic
        self.assertEqual(harmonic.DEFAULT_SCAN, "adjacent")
        self.assertEqual(ChainConfig("M15", "M3", 0.0).harmonic_scan,
                         "adjacent")
        for mod in (bat, butterfly):
            self.assertIs(mod.DEFAULT_SCAN, harmonic.DEFAULT_SCAN,
                          "⛔ ولا نسخةٌ ثانيةٌ للافتراض — مصدرٌ واحد")

    def test_the_two_scans_genuinely_differ_on_the_recorded_example(self):
        """
        ⭐⭐⭐ **ومقيسٌ على مثال HA1 المسجَّل**: قمم 112·110·100·107.

        المتجاورُ يفحص (0,1,2) و(1,2,3) ⇒ **ويُسقط (0,2,3)** وهي
        متناوبةٌ صالحة. ⇒ **فلو تطابق الوضعان كان المفتاحُ زينة.**
        """
        from bot.primitives.harmonic import _groups
        sw = [self._swing(i, k, p) for i, (k, p) in enumerate(
            [("high", 112.0), ("high", 110.0), ("low", 100.0),
             ("high", 107.0)])]
        adj = [tuple(x.index for x in g) for g in _groups(sw, 3, "adjacent")]
        alls = [tuple(x.index for x in g) for g in _groups(sw, 3, "all")]
        self.assertEqual(adj, [(0, 1, 2), (1, 2, 3)])
        self.assertIn((0, 2, 3), alls, "⇒ وهي التي كان المتجاورُ يُسقطها")

    def test_an_unknown_scan_is_refused_not_guessed(self):
        from bot.primitives.harmonic import _groups
        with self.assertRaises(ValueError):
            list(_groups([], 3, "deepest"))

    def test_the_cap_fallback_is_counted_not_silent(self):
        """
        ⛔⛔ **ورجوعٌ صامتٌ إلى المتجاور يجعل عمودًا معنونًا [كلُّ
        متناوبة] متجاورًا سرًّا** — وهو صنفُ LB1.
        """
        from bot.primitives import harmonic
        kept = harmonic.scan_fell_back
        try:
            harmonic.scan_fell_back = 0
            big = [self._swing(i, "high" if i % 2 else "low", 100.0 + i)
                   for i in range(harmonic.SCAN_MAX_SWINGS + 2)]
            list(harmonic._groups(big, 3, "all"))
            self.assertEqual(harmonic.scan_fell_back, 1)
        finally:
            harmonic.scan_fell_back = kept

    def test_the_scan_reaches_every_harmonic_call_not_just_one(self):
        """
        ⛔⛔⛔ **وهذا الحارسُ صمت أوّلَ مرّة — والتجريبُ كشفه.**

        فـ`evaluate` تنادي `best_harmonic` **في موضعين** (تأكيدٌ بعد
        التنقيح · وتأكيدٌ حين لا نموذجَ كلاسيكيّ)، **وفحصُ [الاسمُ
        مذكورٌ مرّةً] يمرّ ولو نُزع من أحدهما** ⇒ **فيبقى موضعٌ
        يمسح متجاورًا والمفتاحُ يقول `all`.**

        ⇒ ⭐⭐⭐ **وهو صنفُ [جردٌ لا ينزل إلى آخر الطريق]** — في
        حارسٍ كتبتُه اليوم. **فيُعَدّ المناداة ويُطابق.**
        """
        import inspect
        import re

        from bot import chain
        src = inspect.getsource(chain.evaluate)
        calls = len(re.findall(r"best_harmonic\(", src))
        self.assertGreaterEqual(calls, 2, "⛔ الجردُ لم يجد المناداة")
        self.assertEqual(
            len(re.findall(r"cfg\.harmonic_scan", src)), calls,
            "⛔ وموضعُ مناداةٍ لا يبلغه المفتاح — فيمسح متجاورًا "
            "والعمودُ يقول [كلُّ متناوبة]")

    # ── TM1 ──

    def test_the_blackout_is_off_because_its_anchor_is_unstated(self):
        """
        🔴 **[اول ساعتين] — من ماذا؟** لم يُنصَّ ⇒ `None` ومطفأة.
        ⛔ **ولا تُشتقّ من أوّل شمعةٍ في المجلوب**: تلك **تزحف مع كلّ
        تشغيل** ⇒ فاشتقاقُها يصنع [رقمًا يقلبه اختيارُك] من العدم.
        """
        from bot import params
        from bot.chain import ChainConfig
        c = ChainConfig("M15", "M3", 0.0)
        self.assertIsNone(c.session_open_hour)
        self.assertEqual(c.session_blackout_hours, 2, "والعددُ منصوص")
        self.assertEqual(params.SESSION_OPEN_HOUR.origin, "UNDEFINED")
        self.assertEqual(params.SESSION_BLACKOUT_HOURS.origin, "SOURCE")

    def test_the_hours_are_read_from_the_ledger_not_retyped(self):
        """⭐ **والمكتوبُ باليد يبيت** — درسُ LB1."""
        import inspect

        from bot import chain
        self.assertIn("_BLACKOUT.value", inspect.getsource(chain))

    def test_naming_the_anchor_closes_the_gate_inside_the_window(self):
        """
        ⛔⛔⛔ **وهذا الحارسُ كان يفحص النصَّ لا السلوك — وصمت.**

        جُرّب نزعُ `return reject(...)` من البوّابة **فمرّ الطقم**:
        لأنّ الفحصَ كان `assertIn` على نصِّ `evaluate` وحدَه، **وبقاءُ
        العبارة لا يعني أنّ البوّابةَ تُغلق.**

        ⇒ ⭐⭐⭐ **وهو صنفُ المشروع المسجَّل في أسوأ موضع**: حارسٌ
        **يبدو** مقيسًا وليس كذلك — كاسمِ اختبار KS2 الذي كان جسمُه
        `assertTrue(banner.__doc__)` فقط. ✅ **فصار يُشغّل السلسلةَ
        ويقرأ القرار.**
        """
        from datetime import datetime

        from bot.chain import ChainConfig, evaluate
        from bot.data import Candle, Series

        def run(hour, open_hour):
            t = datetime(2026, 10, 16, hour, 0)
            poi = Series("M15", [Candle(t, 100, 101, 99, 100)] * 5)
            cfg = ChainConfig("M15", "M3", 0.0,
                              session_open_hour=open_hour)
            return evaluate(poi, poi, cfg, now=t)

        inside = run(10, 9)                   # مضت ساعةٌ من تسع
        self.assertEqual(inside.disposition, "rejected")
        self.assertEqual(inside.note, "داخل الساعات الممنوعة")
        gate = [c for c in inside.rationale.checks
                if c.name == "خارج الساعات الممنوعة"]
        self.assertTrue(gate and not gate[0].passed, "⇒ والفحصُ راسب")

        # ⬇️ وخارجَ النافذة تمرّ البوّابةُ ويُفحَص ما بعدها
        outside = run(13, 9)                  # مضت أربع
        names = [c.name for c in outside.rationale.checks]
        self.assertIn("خارج الساعات الممنوعة", names)
        self.assertTrue(
            [c for c in outside.rationale.checks
             if c.name == "خارج الساعات الممنوعة"][0].passed)

        # ⬇️ ومطفأةً لا تُسجَّل أصلًا — فلا سطرَ زائدٌ في السجلّ
        off = run(10, None)
        self.assertNotIn("خارج الساعات الممنوعة",
                         [c.name for c in off.rationale.checks])

    # ── TL1 ──

    def test_the_trendline_borrows_the_anchor_rule_not_a_copy(self):
        """
        ⭐⭐⭐ **وشرطان لنصٍّ واحدٍ يفترقان يومًا** — صنفُ OB2.
        ⇒ فـ`trendline` **تستدعي `channel.anchor_ok`** ولا تنسخه.
        """
        import inspect

        from bot.primitives import trendline
        src = inspect.getsource(trendline.build)
        self.assertIn("from .channel import anchor_ok", src)
        self.assertIn("require_anchors", src)

    def test_it_is_off_and_demands_a_decision_moment(self):
        from bot.data import Candle, Series
        from bot.primitives.trendline import build
        from datetime import datetime, timedelta
        t0 = datetime(2026, 10, 1, 9, 0)
        s = Series("M15", [Candle(t0 + timedelta(minutes=15 * i),
                                  100, 101, 99, 100) for i in range(6)])
        lows = [self._swing(1, "low", 99.0), self._swing(4, "low", 99.0)]
        self.assertIsNotNone(build(s, lows), "⇒ مطفأٌ فيبني كما كان")
        with self.assertRaises(ValueError) as cm:
            build(s, lows, require_anchors=True)
        self.assertIn("TL1", str(cm.exception))

    def test_channel_is_unreachable_not_wired(self):
        """
        ⛔⛔⛔ **ووصلٌ إلى ميّتٍ ليس وصلًا.**

        استوردتها `trendline` لـTL1، **و`trendline` ميّتةٌ هي
        نفسُها** ⇒ فلها **مظهرُ الموصولة** — وهي `verdicts` بعينها.
        ⭐ **والحارسُ هو الذي أجبر النقل**، ولولاه لكُتب [وُصلت].
        """
        self.assertIn("channel", UNREACHABLE)
        self.assertNotIn("channel", UNWIRED)

    @staticmethod
    def _swing(index, kind, price):
        from datetime import datetime, timedelta

        from bot.primitives.swings import Swing
        return Swing(index=index, kind=kind, price=price,
                     time=datetime(2026, 10, 1, 9, 0)
                     + timedelta(minutes=15 * index))
