"""
اختبار الخطّ — النموذج الذي تصنعه الذيول ليس نموذجًا.

╔══════════════════════════════════════════════════════════════════╗
║  البثّ ٣ (≈20:05) — قلَب الشارت إلى **خطّ** ليختبر:                ║
║                                                                  ║
║    «بروح على الربع ساعة… أعطاني ارتداد، أنا هون **ما عندي دبل    ║
║     بوتم**… **هيدا مش دبل بتم** — شوفوا ع الشموع، **هيدا قاع     ║
║     واحد**»                                                      ║
╚══════════════════════════════════════════════════════════════════╝

⭐ **والخطّ يرسم الإغلاقات وحدها.** فما بدا قاعين على الشموع صار قاعًا
واحدًا على الخطّ — لأن القاع الثاني كان **ذيلًا** لا إغلاقًا.

وهذا مبدؤه نفسه المثبَّت من قبل (C1 · بثّ ٢):

    «الجسم = سيولة حقيقية  ·  **الذيل = سيولة ستوبات**»

⇒ فنموذجٌ قائمٌ على الذيول وحدها مبنيٌّ على **سيولة ستوبات** — أي على
المكان الذي تُصطاد فيه الوقوف، لا على قرارٍ حقيقيّ. والدخول منه دخولٌ
مع الصيد لا مع المؤسسة.

⛔ **وهذا اعتراضٌ لا استبدال** (قرار المستخدم 2026-09-12).

    يُكتشَف النموذج بالذيول كما هو — فالمناطق تُرسم بالذيول، وذلك
    **مقيسٌ من شاشته** (C9). ثم يُعرَض على الخطّ: فإن لم يبقَ نموذجًا
    عليه، رُدَّ.

وهو موافقٌ لما يفعله الكود أصلًا: المناطق بالذيول · الكسر بالجسم
(الدرس 10) · والآن **التحقّق بالإغلاق**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from ..data import Series
from .patterns import ReversalPattern
from .swings import DEFAULT_PLATEAU


@dataclass(frozen=True)
class LineCheck:
    """نتيجة عرض النموذج على الخطّ — بسببها."""

    ok: bool
    reason: str

    def __bool__(self) -> bool:
        return self.ok


def _is_local(closes: Sequence[float], i: int, want_low: bool,
              lookback: int = 1, plateau: str = DEFAULT_PLATEAU) -> bool:
    """
    طرفٌ محليّ على خطّ الإغلاقات — بالقاعدة الفراكتاليّة نفسها.

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⚠️⚠️ **وهذا موضعُ SW1 الثاني — وصلٌ 2026-09-27.**             ║
    ║                                                              ║
    ║  فالمقارنةُ كانت صارمةً في الجهتين هنا أيضًا: **إغلاقان        ║
    ║  متساويان متجاوران** يُسقطان الطرفَ ⇒ فيردّ الخطُّ نموذجًا       ║
    ║  صحيحًا بحجّة «لم يبقَ قاعًا على الخطّ».                        ║
    ║                                                              ║
    ║  ⛔⛔ **ولو تُرك صارمًا لتلوّث قياسُ SW1 نفسُه**: المفتاحُ يزيد   ║
    ║  السوينجات، **والفيتو يأكل الزيادة**، فيُقرأ «لا أثر» والعلّةُ  ║
    ║  في الفيتو لا في القاعدة. **وهو صنفُ الخطأ الذي وقع اليوم     ║
    ║  مرّتين**: عطبٌ واحدٌ في موضعين ولم أربط بينهما                ║
    ║  (`os.listdir` في `quotes.py` وفي جرد الوحدات).               ║
    ║                                                              ║
    ║  ⇒ فصار يتبع المفتاحَ نفسَه، والافتراضُ `strict` كما كان.       ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    if i - lookback < 0 or i + lookback >= len(closes):
        return False
    here = closes[i]
    left = [closes[j] for j in range(i - lookback, i)]
    right = [closes[j] for j in range(i + 1, i + lookback + 1)]
    lax = plateau == "first"
    if want_low:
        return (all(here < o for o in left)
                and all(here <= o if lax else here < o for o in right))
    return (all(here > o for o in left)
            and all(here >= o if lax else here > o for o in right))


def check(
    series: Series,
    pattern: ReversalPattern,
    tolerance: float,
    lookback: int = 1,
    plateau: str = DEFAULT_PLATEAU,
) -> LineCheck:
    """
    هل يبقى النموذج نموذجًا على خطّ الإغلاقات؟

    شرطان، وكلاهما مما أراه في الصورة:

      ١. **كل طرفٍ يبقى طرفًا** — وإلّا فهو «قاع واحد» لا قاعان.
      ٢. **الأطراف تبقى متساويةً** بالسماحية نفسها — وإلّا فليس
         دبل بوتم بل قاعٌ أدنى من قاع.

    والرأس والكتفان استثناءٌ في الشرط الثاني: المتساويان هما
    **الكتفان** (الطرفان)، والرأس يجب أن يبقى **أعمق** منهما.
    """
    closes = [c.close for c in series]
    idx = [p.index for p in pattern.pivots]

    if any(i < 0 or i >= len(closes) for i in idx):
        return LineCheck(False, "طرفٌ خارج السلسلة")

    want_low = pattern.direction == "bullish"

    # ١ — كل طرفٍ يبقى طرفًا على الخطّ
    lost = [i for i in idx
            if not _is_local(closes, i, want_low, lookback, plateau)]
    if lost:
        side = "قاعًا" if want_low else "قمّة"
        return LineCheck(
            False,
            f"على الخطّ لم يبقَ {side}: الشمعة {lost[0]} — «هيدا قاع واحد»",
        )

    # ٢ — التساوي على الإغلاقات
    if pattern.kind in ("head_shoulders", "inverse_head_shoulders"):
        if len(idx) < 3:
            return LineCheck(False, "رأسٌ وكتفان بأقلّ من ثلاثة أطراف")
        a, head, b = closes[idx[0]], closes[idx[1]], closes[idx[-1]]
        if abs(a - b) > tolerance:
            return LineCheck(
                False,
                f"الكتفان غير متساويين على الإغلاق: {a:g} مقابل {b:g}",
            )
        deeper = head < min(a, b) if want_low else head > max(a, b)
        if not deeper:
            return LineCheck(False, "الرأس لم يبقَ أعمق من الكتفين على الإغلاق")
        return LineCheck(True, "النموذج قائمٌ على الخطّ")

    prices = [closes[i] for i in idx]
    spread = max(prices) - min(prices)
    if spread > tolerance:
        return LineCheck(
            False,
            f"الأطراف غير متساوية على الإغلاق: فارق {spread:.2f} "
            f"يتجاوز السماحية {tolerance:g} — «هيدا مش دبل بتم»",
        )

    return LineCheck(True, "النموذج قائمٌ على الخطّ")


def survivors(
    series: Series,
    patterns: Sequence[ReversalPattern],
    tolerance: float,
    lookback: int = 1,
    plateau: str = DEFAULT_PLATEAU,
) -> List[ReversalPattern]:
    """ما بقي نموذجًا على الخطّ — وهو وحده ما يُعرَض على السلسلة."""
    return [p for p in patterns
            if check(series, p, tolerance, lookback, plateau).ok]


def rejected(
    series: Series,
    patterns: Sequence[ReversalPattern],
    tolerance: float,
    lookback: int = 1,
    plateau: str = DEFAULT_PLATEAU,
) -> List[tuple]:
    """
    ما ردّه الخطّ ولماذا — للسجل.

    ⚠️ والعدد نفسه إشارة: إن رُدّ أغلبُ النماذج فالسماحية واسعة،
    وإن لم يُرَدّ شيءٌ قطّ فالاختبار لا يعمل.
    """
    out = []
    for p in patterns:
        r = check(series, p, tolerance, lookback, plateau)
        if not r.ok:
            out.append((p, r.reason))
    return out
