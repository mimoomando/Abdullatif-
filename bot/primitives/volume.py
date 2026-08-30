"""
قراءة الفوليوم — وايكوف/د4 «الفوليوم وإشارات الضعف».

╔══════════════════════════════════════════════════════════════════╗
║  المميِّز الثاني للكسر الوهمي — يسبق إغلاق إعادة الاختبار زمنيًا:   ║
║                                                                   ║
║      حجم شمعة الكسر **أقلّ** من الطرف المقابل  ⇒  كسر وهمي        ║
║      حجم شمعة الكسر **أعلى**                   ⇒  كسر حقيقي       ║
╚══════════════════════════════════════════════════════════════════╝

    «الشمعة اللي طلعت على أعلى من مستوى البائعين… ولكن بالفوليوم كانت
     هي أقل. شو بيعني لي هذا؟ هذا بيعني لي إنه هذا كسر وهمي»

    «لو كان حجم الفوليوم عالي ما كان كسر وهمي… وكنت انت من إعادة
     الاختبار فيك تكمل معه طلوع **إذا أعطاك نموذج استمراري**»

⚠️ **الكسر الحقيقي لا يُتداوَل معه هنا:** شرطه نموذج استمراري
(Flag · Pennant) **لم يُدرَّس بعد**. فيُرصد ولا يُبنى عليه دخول.

╔══════════════════════════════════════════════════════════════════╗
║  Sign of Weakness — تباعد السعر عن الحجم                          ║
║      «المشتريين أدنى من البائعين، ولكن شموع الخضر أعلى            ║
║       ⇒ هذا الصعود وهم»                                           ║
╚══════════════════════════════════════════════════════════════════╝

⚠️ **ملاحظة تقنية أرفعها أنا لا هو:** الذهب عقد فرقي بلا حجم تداول
حقيقي. ما تعرضه المنصّات — TradingView و MT5 معًا — هو **حجم التكّات**:
عدد تغيّرات السعر لا كمية العقود. هذا لا يُبطل الدرس (يقرأ هو الرقم
نفسه)، لكنه يعني أن الأرقام **نسبية بين الشموع لا مطلقة**، وقد تختلف
بين وسيط وآخر — امتداد للتعارض C4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Sequence

from ..data import Candle, Series

Side = Literal["up", "down"]
Verdict = Literal["fake", "real", "unknown"]


@dataclass(frozen=True)
class VolumeRead:
    """حكم الفوليوم على شمعة كسر."""

    verdict: Verdict
    break_volume: float
    opposing_volume: float
    ratio: Optional[float]          # حجم الكسر ÷ حجم المقابل
    detail: str

    @property
    def usable(self) -> bool:
        return self.verdict != "unknown"

    def render(self) -> str:
        ar = {"fake": "وهمي", "real": "حقيقي", "unknown": "بلا حكم"}[self.verdict]
        r = f" · النسبة {self.ratio:.2f}" if self.ratio is not None else ""
        return f"الفوليوم: {ar}{r} — {self.detail}"


def opposing_volume(
    series: Series,
    break_index: int,
    direction: Side,
    lookback: int = 5,
) -> float:
    """
    حجم الطرف المقابل قبل الكسر — ما يُقاس عليه حجم شمعة الكسر.

    🔴 **V2 — غير معرَّف.** المدرّب أشار إلى «مستوى البائعين» ولم يحدّد
    أهو آخر شمعة معاكسة أم متوسط عدة، ولا كم. اعتُمد **أقصى حجم لشمعة
    معاكسة** ضمن `lookback` — لأنه يقول «أدنى بكثير من حجم الفوليوم
    هون» مشيرًا إلى شمعة بعينها بارزة، لا إلى متوسط.

    يُرجَع 0.0 إن لم توجد شمعة معاكسة — ويصير الحكم `unknown` لا تخمينًا.
    """
    if lookback < 1:
        raise ValueError("النظر للخلف شمعة أو أكثر")

    start = max(0, break_index - lookback)
    opposing = [
        c.volume
        for c in list(series)[start:break_index]
        if (c.close < c.open if direction == "up" else c.close > c.open)
    ]
    return max(opposing) if opposing else 0.0


def read_break(
    series: Series,
    break_index: int,
    direction: Side,
    lookback: int = 5,
    weak_ratio: float = 1.0,
) -> VolumeRead:
    """
    يحكم على شمعة الكسر بحجمها مقابل الطرف المقابل.

    `weak_ratio` : النسبة التي دونها يُعدّ الحجم ضعيفًا.
        🔴 **V1 — غير معرَّف.** قال «أدنى **بكثير**» ولم يعطِ نسبة.
        1.0 يعني «أقلّ ببساطة» — أي حرفية «أدنى» بلا تشديد. رفعه فوق
        الواحد يشدّد الشرط، وهو ما تضبطه البيانات لا التخمين.

    ⚠️ يُرجَع `unknown` إن غاب الحجم — الفيد بلا فوليوم، أو لا شمعة
    معاكسة. **ولا يُفترض حكم**: غياب البيانات ليس دليلًا على شيء.
    """
    if not 0 <= break_index < len(series):
        raise ValueError("رقم شمعة الكسر خارج المدى")
    if weak_ratio <= 0:
        raise ValueError("النسبة يجب أن تكون موجبة")

    brk = series[break_index]
    opp = opposing_volume(series, break_index, direction, lookback)

    if brk.volume <= 0 or opp <= 0:
        return VolumeRead(
            "unknown", brk.volume, opp, None,
            "لا فوليوم صالح للمقارنة — الفيد بلا حجم أو لا شمعة معاكسة",
        )

    ratio = brk.volume / opp
    if ratio < weak_ratio:
        return VolumeRead(
            "fake", brk.volume, opp, ratio,
            f"حجم الكسر {brk.volume:g} أدنى من المقابل {opp:g} "
            "— «بالفوليوم كانت هي أقل ⇒ كسر وهمي»",
        )
    return VolumeRead(
        "real", brk.volume, opp, ratio,
        f"حجم الكسر {brk.volume:g} يفوق المقابل {opp:g} "
        "— «لو كان حجم الفوليوم عالي ما كان كسر وهمي». "
        "⛔ الدخول معه يلزمه نموذج استمراري لم يُدرَّس بعد.",
    )


# ─────────────────────────── ضعف المشتريين/البائعين ───────────────────────────


@dataclass(frozen=True)
class Weakness:
    """
    Sign of Weakness — السعر يصنع قمة أعلى والحجم لا يسنده.

    «المشتريين أدنى من البائعين، ولكن شموع الخضر أعلى
     ⇒ هذا الصعود وهم»
    """

    index: int
    side: Side                      # up = ضعف المشتريين
    price_extreme: float
    with_volume: float              # حجم الاتجاه الظاهر
    against_volume: float           # حجم الطرف المقابل
    detail: str

    def render(self) -> str:
        who = "المشتريين" if self.side == "up" else "البائعين"
        return (
            f"ضعف {who} عند {self.price_extreme:g} — "
            f"حجمهم {self.with_volume:g} مقابل {self.against_volume:g} · {self.detail}"
        )


def find_weakness(
    series: Series,
    direction: Side,
    window: int = 5,
    zones: Optional[Sequence[Any]] = None,
    proximity: float = 0.0,
) -> List[Weakness]:
    """
    يرصد التباعد: السعر يتقدّم والحجم المؤيّد أدنى من المعارض.

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⚠️ `zones` ليس زينةً — هو **شرط الصحة**.                     ║
    ╚══════════════════════════════════════════════════════════════╝

    نهى المدرّب صراحةً عن قراءة الفوليوم خارج المناطق المفتاحية:

        «**ما تيجي بكرة تقول لي الشمعة الحمراء بيّنت كثير بدي أبيع.
          هذا الحكي مرفوض.**»
        «نحن بنقرا الفوليوم **عند المناطق المفتاحية فقط**»
        «بغير المنطقة المفتاحية — **ما تشوفه**»

    وعلّته منصوصة: المنطقة القوية **تحتاج حجمًا لتُكسَر**، فالحجم عندها
    يعني شيئًا. أما وسط المدى فالحجم رقم بلا مرجع.

    `zones=None` يفحص السلسلة كلها — **وهو بالضبط ما سمّاه مرفوضًا**.
    يبقى متاحًا للاستكشاف والاختبار التاريخي فقط، ولا يُبنى عليه قرار.

    `window` : 🔴 **V3 غير معرَّف** — «أبطأ أبطأ أبطأ» بلا عدد شموع.
    """
    if window < 2:
        raise ValueError("النافذة شمعتان أو أكثر")
    if proximity < 0:
        raise ValueError("القرب لا يكون سالبًا")

    out: List[Weakness] = []
    candles = list(series)

    for i in range(window, len(candles)):
        if zones is not None and not _at_zone(zones, candles[i], proximity):
            continue
        window_slice = candles[i - window:i + 1]
        cur = candles[i]

        if direction == "up":
            advanced = cur.high >= max(c.high for c in window_slice[:-1])
            with_v = [c.volume for c in window_slice if c.close > c.open]
            against_v = [c.volume for c in window_slice if c.close < c.open]
        else:
            advanced = cur.low <= min(c.low for c in window_slice[:-1])
            with_v = [c.volume for c in window_slice if c.close < c.open]
            against_v = [c.volume for c in window_slice if c.close > c.open]

        if not advanced or not with_v or not against_v:
            continue

        w, a = max(with_v), max(against_v)
        if w <= 0 or a <= 0 or w >= a:
            continue

        out.append(
            Weakness(
                i, direction, cur.high if direction == "up" else cur.low, w, a,
                "السعر تقدّم والحجم المؤيّد أدنى من المعارض — «هذا الصعود وهم»"
                if direction == "up"
                else "السعر تقدّم هبوطًا والحجم المؤيّد أدنى من المعارض",
            )
        )

    return out


def _at_zone(zones: Sequence[Any], candle: Any, proximity: float) -> bool:
    """
    هل لامست الشمعة منطقة مفتاحية؟

    يُفحص **بمدى الشمعة** لا بإغلاقها: الشمعة التي اخترقت المنطقة ثم
    أغلقت خارجها هي بالضبط ما نريد قراءة حجمه.
    """
    return any(
        z.distance_from(candle.high) <= proximity
        or z.distance_from(candle.low) <= proximity
        or (candle.low <= z.top and candle.high >= z.bottom)
        for z in zones
    )


def has_volume(series: Series) -> bool:
    """
    هل يحمل الفيد فوليومًا أصلًا؟

    يُفحص قبل أي حكم: بلا حجم، تسقط كل قواعد هذا الدرس ويعود التمييز
    إلى إغلاق إعادة الاختبار وحده (وايكوف/د3).
    """
    return any(c.volume > 0 for c in series)
