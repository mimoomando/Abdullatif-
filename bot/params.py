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

SYMBOL = Param("XAUUSD.m", "SOURCE", "§1", "ذهب فقط")


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

TELEGRAM_COPY_LOT = Param(0.01, "SOURCE", "§Telegram", "ثابت لإشارات القناة")
TELEGRAM_COPY_STOP_POINTS = Param(10.00, "SOURCE", "§Telegram", "ثابت: دخول ∓ 10.00")

STRATEGY_RISK_PERCENT = Param(
    value=None,
    origin="UNDEFINED",
    lesson="-",
    note="🔴 لا يوجد في أي درس. قرار المستخدم. الثابت أعلاه لإشارات التيليجرام فقط.",
)

MAX_DAILY_LOSS_PERCENT = Param(None, "UNDEFINED", "-", "🔴 غير موجود في المصدر — قرار المستخدم")
MAX_OPEN_POSITIONS = Param(None, "UNDEFINED", "-", "🔴 غير موجود في المصدر — قرار المستخدم")
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
    for o in ("SOURCE", "DERIVED", "UNDEFINED"):
        print(f"  {o:10s}: {len(by_origin(o))}")
    print()
    print(undefined_report())
