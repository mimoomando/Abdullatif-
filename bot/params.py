"""
معاملات «استراتيجية الذكاء» — نقطة الضبط الوحيدة.

كل معامل هنا يحمل مصدره:
  SOURCE   = مأخوذ حرفيًا من درس ‏(الدرس مذكور)
  DERIVED  = مشتق من مثال في درس، يحتاج اختبارًا تاريخيًا
  UNDEFINED= لم يعرّفه المصدر — قيمة أولية للاختبار فقط، تُضبط بالبيانات

القائمة UNDEFINED هي بالضبط §17 «Not yet automatable» من الملف الجامع،
محوّلة إلى مقابض قابلة للضبط بدل أن تبقى عائقًا مجرّدًا.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any


@dataclass(frozen=True)
class Param:
    value: Any
    origin: str          # SOURCE | DERIVED | UNDEFINED
    lesson: str          # مرجع الدرس، أو "-" إن لم يوجد
    note: str = ""


# ─────────────────────────── الأطر الزمنية ───────────────────────────

TIMEFRAMES = Param(
    value={
        "structure": ["MN1", "W1", "D1", "H4"],
        "intermediate": ["H2", "H1", "M15"],
        "execution": ["M5", "M3", "M1"],
    },
    origin="SOURCE",
    lesson="Lesson 12",
    note="أطر الهيكل الكبرى، ثم المتوسطة، ثم أطر التأكيد والتنفيذ",
)

# جدول ترابط الفريمات — درس «ترابط الفريمات واستمرارية الهيكل»
# كل نقطة اهتمام لها إطار تأكيد واحد محدد. ممنوع تخطّي الأطر:
#   «ما فيك تيجي من اليومي فورًا تفوت خمس دقائق… إذا ما أعطاني من الساعة ما بفوت»
TIMEFRAME_PAIRS = Param(
    value={
        "W1": "H4",
        "D1": "H1",
        "H4": "M30",   # المدرّب يفضّل M30 على M15
        "H1": "M5",
        "M15": "M3",
    },
    origin="SOURCE",
    lesson="ترابط الفريمات",
    note="M1 مستبعد كإطار تأكيد: «احتمال 50% إنه ينضرب الستوب» — "
         "بينما M3 يعطي «60–70%» بحسب المدرّب",
)

ACTIVE_POI_TIMEFRAMES = Param(
    value=["H4", "H1", "M15"],
    origin="USER",
    lesson="قرار 2026-08-26",
    note="ثلاثة أزواج نشطة: H4←M30 · H1←M5 · M15←M3. "
         "اليومي والأسبوعي مستبعدان لندرة إعداداتهما. "
         "⚠️ تُسجَّل نتائج كل إطار منفصلة، ليتبيّن بالأرقام أيها يستحق البقاء.",
)

MAX_OPEN_POSITIONS_ACTIVE = Param(
    value=1,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="مركز واحد فقط على XAUUSD.m. لا يُفتح جديد قبل إغلاق القائم — "
         "حتى لو ظهر إعداد صالح على إطار آخر.",
)

NOTIFY_BLOCKED_SETUPS = Param(
    value=True,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="كل إعداد صالح يمنعه حد المراكز يُرسَل كتنبيه لا كأمر — "
         "الثاني والثالث والرابع، بلا حد لعدد التنبيهات. "
         "كلٌّ يُسجَّل مع نتيجته الافتراضية، ليتبيّن لاحقًا بالأرقام "
         "هل كان رفع الحد سيربح أم يخسر.",
)

MAX_NOTIFICATIONS_PER_DAY = Param(
    value=None,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="بلا حد — «أو ثالثة أو رابعة».",
)

EXPLAIN_EVERY_TRADE = Param(
    value=True,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="كل صفقة ترافقها: (1) سلسلة الأسباب الكاملة للدخول بكل فحص ونتيجته، "
         "(2) سجل زمني لما حدث أثناء الصفقة حتى إغلاقها. "
         "الغرض أن يفهم المستخدم التحليل ويراجعه، لا أن يثق بصندوق مغلق.",
)

SYMBOL = Param("XAUUSD.m", "SOURCE", "§1", "ذهب فقط")

RUNTIME_HOST = Param(
    value="windows_desktop",
    origin="USER",
    lesson="قرار 2026-08-26",
    note="ويندوز مباشر عبر حزمة MetaTrader5 الرسمية، والجهاز يبقى شغالًا دائمًا. "
         "لا حاجة لـWine ولا لجسر Expert Advisor.",
)

# جهاز شخصي يعمل 24 ساعة ليس خادمًا: ينقطع بانقطاع الكهرباء أو الإنترنت،
# ويعيد ويندوز تشغيله للتحديثات. لذلك يلزم التعامل مع الانقطاع لا افتراض استمراره.
RESILIENCE_REQUIREMENTS = Param(
    value={
        "detect_data_gaps": True,        # كشف الشموع المفقودة بعد أي انقطاع
        "reconnect_on_drop": True,       # إعادة الاتصال بالطرفية تلقائيًا
        "adopt_open_positions": True,    # يتبنّى المركز من السجل ويكمل إدارته
        "heartbeat_to_telegram": True,   # نبضة دورية تثبت أن البوت حيّ
    },
    origin="USER",
    lesson="قرار 2026-08-26",
    note="التبنّي يعتمد على أن كل صفقة تُكتب على القرص لحظة فتحها: "
         "الأهداف · حالة الوقف · المرحلة. "
         "⚠️ إن وُجد مركز بلا سجل مطابق (فتحته يدويًا مثلًا) "
         "فالبوت ينبّه ولا يلمسه.",
)


# ─────────────────────────── القمم والقيعان ───────────────────────────

SWING_LOOKBACK = Param(
    value=1,
    origin="SOURCE",
    lesson="Lesson 9",
    note="Swing High أعلى من القمة السابقة مباشرة واللاحقة مباشرة ⇒ فراكتال 3 شموع",
)

STRUCTURAL_SWING_LOOKBACK = Param(
    value=3,
    origin="UNDEFINED",
    lesson="§17 swing detection",
    note="القمم الهيكلية على H4+ تحتاج نافذة أوسع. المصدر لم يعطِ رقمًا.",
)


# ─────────────────────────── كسر الهيكل ───────────────────────────

BREAK_BY_BODY = Param(
    value=True,
    origin="SOURCE",
    lesson="Lesson 10",
    note="«The structural break must be by candle body, not wick»",
)

BREAK_TOLERANCE_POINTS = Param(
    value=0.0,
    origin="UNDEFINED",
    lesson="§17 close tolerance",
    note="كم يجب أن يتجاوز الإغلاق المستوى ليُعدّ كسرًا؟ المصدر لم يحدد.",
)


# ─────────────────────────── الفراغ السعري ───────────────────────────

FVG_CANDLES = Param(3, "SOURCE", "Lesson 5", "ثلاث شموع")

FVG_WICK_TO_WICK = Param(
    value=True,
    origin="SOURCE",
    lesson="Lesson 5",
    note="صاعد: بين high الشمعة 1 و low الشمعة 3 — بالذيول لا الأجسام",
)

FVG_MIN_SIZE_POINTS = Param(
    value=0.0,
    origin="UNDEFINED",
    lesson="§17 FVG minimum size",
    note="0.0 = اقبل أي فراغ. يحتاج ضبطًا لتفادي الضجيج على الذهب.",
)

FVG_GROUP_MAX_GAP_POINTS = Param(
    value=0.0,
    origin="UNDEFINED",
    lesson="§17 zone merging",
    note="متى تُدمج فراغات متجاورة في منطقة واحدة ويُستعمل منتصفها؟",
)


# ─────────────────────────── السيولة ───────────────────────────

SWEEP_REQUIRES_RECLAIM = Param(
    value=True,
    origin="SOURCE",
    lesson="Liquidity & structure",
    note="الاختراق وحده ليس sweep — يلزم استعادة الإغلاق للجهة الأخرى",
)

SWEEP_MAX_BARS_TO_RECLAIM = Param(
    value=3,
    origin="UNDEFINED",
    lesson="§17 sweep tolerance",
    note="خلال كم شمعة يجب أن تتم الاستعادة؟",
)

SWEEP_MIN_PENETRATION_POINTS = Param(
    value=0.0,
    origin="UNDEFINED",
    lesson="§17 sweep tolerance",
    note="⚠️ مرتبط بالتعارض C4: قد لا يظهر الاختراق أصلًا على فيد XAUUSD.m",
)


# ─────────────────────────── الترند لاين ───────────────────────────

TRENDLINE_ANCHOR = Param(
    value="body",
    origin="SOURCE",
    lesson="Lesson 3",
    note="الترند لاين الهيكلي على الأجسام عبر Line Chart",
)

PATTERN_BOUNDARY_ANCHOR = Param(
    value="wick",
    origin="SOURCE",
    lesson="Lesson 8",
    note="⚠️ التعارض C1: حدود Flag/Pennant على الذيول صراحةً — عكس الترند الهيكلي",
)

CHANNEL_ANCHOR = Param(
    value="body",
    origin="SOURCE",
    lesson="Lesson 12",
    note="⚠️ التعارض C1: «permits wick-based but prefers candle bodies»",
)

TRENDLINE_MIN_PIVOTS = Param(2, "SOURCE", "Lesson 3", "لمستان على الأقل")


# ─────────────────────────── فيبوناتشي وموقع القيمة ───────────────────────────

FIB_LEVELS = Param(
    value=[0.236, 0.382, 0.5, 0.618, 0.786],
    origin="SOURCE",
    lesson="Lesson 6",
    note="المستعملة فعليًا: 50 · 61.8 · 78.6 — و23.6 غير مستعملة و38.2 لأنماط الاستمرار",
)

FIB_EXTENSION_LEVELS = Param([1.0, 1.382, 1.618, 1.84], "SOURCE", "Lesson 8", "مستويات الإسقاط")

PREMIUM_DISCOUNT_GATE = Param(
    value=0.5,
    origin="SOURCE",
    lesson="Lesson 14",
    note="الشراء فوق 50% غالٍ، والبيع تحته غالٍ — تقدير مخاطرة لا منع مطلق (§9)",
)

CONTINUATION_MAX_PULLBACK = Param(
    value=0.5,
    origin="SOURCE",
    lesson="Lesson 8",
    note="الارتداد يبقى عادةً ضمن 38.2%، ويُقبل حتى 50% — وأعمق من ذلك يُبطل النمط",
)


# ─────────────────────────── المخاطرة ───────────────────────────

# ⛔ نظام نسخ إشارات القناة — مُلغى
#
# الملف الجامع كان ينص على نسخ رسائل «buy»/«sell» من قناة علاء الدين
# تنفيذًا فوريًا بلوت 0.01 ووقف ثابت 10.00 وحدة.
#
# المستخدم صحّح هذا في 2026-08-26: «لا يوجد إشارة من هذه القناة،
# هذه فقط للتحليل» — أي أن القناة مصدر تعليمي لا مصدر إشارات.
#
# الأثر: مصدر صفقات واحد فقط هو محرك الاستراتيجية،
# والوقف يُشتق من الهيكل دائمًا — لا يوجد وقف ثابت بـ10.00 وحدة.

TELEGRAM_COPY_ENABLED = Param(
    value=False,
    origin="USER",
    lesson="تصحيح 2026-08-26",
    note="⛔ مُلغى. القناة للتحليل والتعلّم فقط، لا تُرسل إشارات تداول.",
)

NOTIFY_CHANNEL = Param(
    value="telegram",
    origin="USER",
    lesson="قرار 2026-08-26",
    note="البوت ← المستخدم: الصفقات المقترحة والشروحات والتنبيهات وسجل ما بعد الإغلاق. "
         "الاتجاه المعاكس (قناة ← بوت) مُلغى.",
)

JOURNAL_TO_DISK = Param(
    value=True,
    origin="USER",
    lesson="لازم تقني لقرار 2026-08-26",
    note="حفظ محلي إلزامي رغم اختيار التيليجرام — لأن تتبّع سلاسل الخسائر "
         "وأداء الجلسات (المتفق عليهما) يحتاجان تاريخًا قابلًا للاستعلام، "
         "ورسائل التيليجرام لا تصلح قاعدةَ بيانات.",
)

ACCOUNT_MODE = Param(
    value="demo",
    origin="USER",
    lesson="قرار 2026-08-26",
    note="حساب تجريبي أولًا. لا يُبدَّل إلى real إلا بقرار صريح.",
)

STRATEGY_LOT = Param(
    value=0.01,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="لوت ثابت لكل صفقة — «أريد أن أرى كيف تجري الأمور أولًا». "
         "لا تُحسب نسبة مخاطرة، ولا تتغير مع حجم الحساب.",
)

STRATEGY_RISK_PERCENT = Param(
    value=None,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="لا ينطبق — الحجم ثابت لا نسبي. "
         "بلوت ثابت تتغيّر الخسارة بالدولار حسب مسافة الوقف: "
         "وقف أوسع = خسارة أكبر. هذا مقبول ومقصود في مرحلة التجربة.",
)

MAX_CONSECUTIVE_LOSSES = Param(
    value=None,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="لا حد في التجريبي — «لأرى المنهج كاملًا بلا تدخل». "
         "⛔ يجب ضبطه برقم قبل أي انتقال إلى حساب حقيقي. "
         "البوت يحسب سلاسل الخسائر ويسجّلها رغم عدم التوقف، "
         "ليُختار الرقم لاحقًا من البيانات لا من التقدير.",
)

TRACK_LOSS_STREAKS = Param(
    value=True,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="يسجّل أطول سلسلة خسائر يومية وإجمالية حتى بلا حد فعّال.",
)

SESSION_FILTER = Param(
    value=None,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="24 ساعة بلا مرشّح جلسة. المصدر لا يذكر مرشّح وقت أصلًا. "
         "البوت يسجّل ساعة كل صفقة ونتيجتها، ليتبيّن لاحقًا "
         "هل جلسة آسيا تستحق الاستبعاد.",
)

TRACK_SESSION_PERFORMANCE = Param(
    value=True,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="تصنيف النتائج حسب الجلسة (آسيا · لندن · التداخل · ما بعد نيويورك).",
)

NEWS_FILTER = Param(
    value=None,
    origin="USER",
    lesson="قرار 2026-08-26",
    note="لا مرشّح أخبار — يتداول عاديًا. متّسق مع «بلا حدود في التجريبي». "
         "المصدر نفسه لا يعطي مرشّحًا: «no usable news filter is given» (د14). "
         "⛔ يُعاد النظر فيه قبل الحساب الحقيقي.",
)

TRACK_SPREAD_AT_ENTRY = Param(
    value=True,
    origin="USER",
    lesson="لازم تقني لقرار 2026-08-26",
    note="يسجّل السبريد لحظة كل دخول وخروج، والانزلاق الفعلي مقابل السعر المتوقع. "
         "بلا مرشّح أخبار، هذه هي الطريقة الوحيدة لمعرفة كم كلّفك اتساع السبريد "
         "— وهي بيانات ستحتاجها لاختيار مرشّح لاحقًا إن لزم.",
)

SPREAD_BUFFER_POINTS = Param(None, "UNDEFINED", "§17 spread buffers", "يُشتق من مواصفات الرمز الحية")


# ─────────────────────────── أدوات ───────────────────────────

def registry() -> Dict[str, Param]:
    """كل المعاملات المعرّفة في هذه الوحدة."""
    g = globals()
    return {k: v for k, v in g.items() if isinstance(v, Param)}


def by_origin(origin: str) -> Dict[str, Param]:
    return {k: v for k, v in registry().items() if v.origin == origin}


def undefined_report() -> str:
    """تقرير المعاملات غير المعرّفة — أي §17 محوّلة إلى قائمة عمل."""
    rows = by_origin("UNDEFINED")
    lines = [f"معاملات غير معرّفة من المصدر: {len(rows)}", ""]
    for name, p in sorted(rows.items()):
        lines.append(f"  {name}")
        lines.append(f"      قيمة أولية : {p.value}")
        lines.append(f"      المرجع     : {p.lesson}")
        lines.append(f"      ملاحظة     : {p.note}")
        lines.append("")
    return "\n".join(lines)


def value(p: Param):
    return p.value


if __name__ == "__main__":
    r = registry()
    print(f"إجمالي المعاملات: {len(r)}")
    for o in ("SOURCE", "USER", "DERIVED", "UNDEFINED"):
        print(f"  {o:10s}: {len(by_origin(o))}")

    print()
    print("قرارات المستخدم:")
    for name, p in sorted(by_origin("USER").items()):
        print(f"  {name} = {p.value}")

    print()
    print(undefined_report())
