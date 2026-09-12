"""
الفراغ السعري / Fair Value Gap — الدرس 5.

النص المصدري:
    «A Fair Value Gap (FVG) is drawn across three candles using the wicks of the
     first and third candles. A bullish FVG is the untraded zone between the
     first candle's high and the third candle's low after upward displacement.
     A bearish FVG is the untraded zone between the third candle's high and the
     first candle's low after downward displacement.»

بالذيول لا الأجسام — وهذا مؤكَّد في المصدر ولا لبس فيه.

⭐⭐⭐ **وقد قيس من الشاشة وثبت (C9 · 2026-08-31).** أوهم تفريغُ درس
الفجوات أن ثمّة تعارضًا: «راسم الفير فاليو جاب **من الذيل إلى الجسم**».
فقيست لقطتان من الشارت نفسه:

    حافة الصندوق السفلى  =  y 736  ·  y 787
    طرف ذيل الشمعة الثالثة =  y 736  ·  y 787   ✅ مطابق
    أعلى جسمها             =  y 806  ·  y 858   ❌ يبعد ~70 بكسل

⇒ الحدّ يقف على **طرف الشمعة** — ذيلًا إن وُجد، وحافةَ جسم إن لم يوجد.
وهذا ما تفعله `high`/`low` أصلًا. وقولُه «من الذيل إلى الجسم» وصفٌ لمثالٍ
شمعتُه الأولى بلا ذيل سفليّ، لا قاعدةً تخلط مرجعين.

التفصيل والقياسات في `knowledge/episodes/ta-fvg-drawing.md`.

قيد الاستعمال (الدرس 5): الفراغ ليس إشارة مستقلة. هذه الوحدة تكتشف الموقع فقط،
والقرار يُبنى في سلسلة التأكيد.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional, Sequence

from ..data import Series

Direction = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class FVG:
    index: int          # فهرس الشمعة الثالثة (لحظة اكتمال الفراغ)
    time: datetime
    direction: Direction
    top: float
    bottom: float
    mitigated: bool = False

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        """المنتصف — يُستعمل كمرجع إعادة تسعير (الدرس 10 والمرحلة 2 الدرس 3)."""
        return (self.top + self.bottom) / 2.0

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top


def find_fvgs(series: Series, min_size: float = 0.0) -> List[FVG]:
    """
    يمسح السلسلة بنافذة ثلاث شموع.

    صاعد : low[i] > high[i-2]   ⇒ المنطقة (high[i-2] .. low[i])
    هابط : high[i] < low[i-2]   ⇒ المنطقة (high[i] .. low[i-2])

    الشمعة الوسطى هي الاندفاع؛ التعريف لا يفرض عليها شرطًا رقميًا
    (قوة الاندفاع من §17 غير المعرّفة).
    """
    out: List[FVG] = []
    for i in range(2, len(series)):
        first, third = series[i - 2], series[i]

        if third.low > first.high:
            gap = third.low - first.high
            if gap > min_size:
                out.append(FVG(i, third.time, "bullish", third.low, first.high))

        elif third.high < first.low:
            gap = first.low - third.high
            if gap > min_size:
                out.append(FVG(i, third.time, "bearish", first.low, third.high))

    return out


def mark_mitigated(series: Series, fvgs: List[FVG]) -> List[FVG]:
    """
    يضع علامة على الفراغات التي عاد إليها السعر بعد تكوّنها.

    «A failed FVG/zone must change state when structure invalidates it; do not
     preserve a permanently bullish or bearish label after failure.» (§7)

    هنا تُرصد المخالطة الأولى فقط. عتبة الاستنفاد الكامل غير معرّفة في المصدر.
    """
    out: List[FVG] = []
    for f in fvgs:
        touched = any(
            series[j].low <= f.top and series[j].high >= f.bottom
            for j in range(f.index + 1, len(series))
        )
        out.append(
            FVG(f.index, f.time, f.direction, f.top, f.bottom, mitigated=touched)
        )
    return out


# ═══════════════════════ الفراغ المنعكس ═══════════════════════


@dataclass(frozen=True)
class Inversion:
    """
    فراغٌ **عكس الاتجاه** انقلب دوره فصار نقطة ارتكاز معه.

    ⭐ منصوص في البثّ ٣ (≈24:22):

        «في عندي فير فالو هون **سلبية** اللي بيتعامل معها **بكسر
         إيديه**… ليه؟ لأنه نحن صرنا **بسوق صاعد**… **ما بتعامل مع
         الفير فالو السلبية في حال السوق عندي صاعد**.
         ⭐ ممكن تكون **نقطة ارتكاز** عندي **إذا طلع أغلق فوق وعاد
         الاختبار** — أنا منها بفوت شراء **مع تأكيد من الفريم
         المرتبط**»

    فثلاثة شروط، والثالث ليس من شأن هذه الوحدة:

        ١. إغلاقٌ خلف الفراغ بالكامل   ⇒ `closed_beyond_at`
        ٢. إعادة اختبارٍ له             ⇒ `retested_at`
        ٣. تأكيدٌ من الفريم المرتبط     ⇒ **في `chain` لا هنا**

    ⚠️ ولذلك `confirmed` تعني الشرطين الأوّلين فقط — واستعمالها
    مَدخلًا بلا تأكيد الفريم المرتبط يخالف نصّه.
    """

    source: FVG                    # الفراغ الأصليّ — عكس الاتجاه الجديد
    direction: Direction           # الاتجاه بعد الانقلاب
    closed_beyond_at: int
    retested_at: Optional[int] = None

    @property
    def top(self) -> float:
        return self.source.top

    @property
    def bottom(self) -> float:
        return self.source.bottom

    @property
    def midpoint(self) -> float:
        return self.source.midpoint

    @property
    def confirmed(self) -> bool:
        """إغلاقٌ خلفه **وإعادة اختبار** — ولا يكفي الإغلاق وحده."""
        return self.retested_at is not None

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def render(self) -> str:
        state = "مؤكَّدة" if self.confirmed else "بانتظار إعادة الاختبار"
        return (f"فراغ منعكس {self.direction} {self.bottom:g}–{self.top:g} · "
                f"{state}")


def find_inversions(
    series: Series,
    fvgs: Sequence[FVG],
    structure: str,
) -> List[Inversion]:
    """
    يرصد الفراغات المعاكسة التي أُغلق خلفها ثم أُعيد اختبارها.

    `structure` هو اتجاه الهيكل القائم: فالفراغ المرشَّح للانقلاب هو
    **المعاكس له** — إذ الموافق يُتداول كما هو ولا يحتاج انقلابًا.

    ⚠️ والإغلاق **خلف الفراغ بالكامل** لا داخله: إغلاقٌ في منتصفه
    مخالطةٌ لا اختراق.
    """
    if structure not in ("bullish", "bearish"):
        return []

    opposite: Direction = "bearish" if structure == "bullish" else "bullish"
    out: List[Inversion] = []

    for f in fvgs:
        if f.direction != opposite:
            continue

        beyond: Optional[int] = None
        retest: Optional[int] = None

        for i in range(f.index + 1, len(series)):
            c = series[i]
            if beyond is None:
                # الإغلاق خلف الحدّ البعيد باتجاه الهيكل
                passed = c.close > f.top if structure == "bullish" else c.close < f.bottom
                if passed:
                    beyond = i
                continue
            if c.low <= f.top and c.high >= f.bottom:
                retest = i
                break

        if beyond is not None:
            out.append(Inversion(f, structure, beyond, retest))

    return out


# ═══════════════════════ نطاق السعر المتوازن — BPR ═══════════════════════


@dataclass(frozen=True)
class BPR:
    """
    **Balanced Price Range** — فراغان متعاكسان يتراكبان.

    ⭐ استعمله بلفظه في البثّ ٣ (≈53:21):

        «أنا من هون نقطة دخوله اللي هي **البي بي آر مع الفير فالو
         جاب السلبية**. هي كان عندي **صفقة بيع** من هون، **ستوبي
         هيدا القمّة عليها بقليل**، **هدفي الأول** هون… ليه؟ **هيدي
         منطقة دعم على ربع ساعة**»

    ⇒ فالمنطقة هي **التراكب** بين الفراغين، والوقف خلف طرفها بقليل،
    والهدف الأول المنطقة المقابلة على إطار نقطة الاهتمام.

    🔶 **والاتجاه مشتقٌّ من مثالٍ واحد**: تداول بيعًا مع الفراغ
    **السلبيّ** وهو الأحدث، فاعتُمد **اتجاه الأحدث**. ومثالٌ واحد لا
    يثبّت قاعدة ⇒ انظر `BPR_DIRECTION_FROM` في `params`.
    """

    first: FVG
    second: FVG                    # الأحدث — ومنه الاتجاه
    top: float
    bottom: float

    @property
    def direction(self) -> Direction:
        return self.second.direction

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0

    @property
    def index(self) -> int:
        """لحظة اكتمال التراكب — أي الفراغ الأحدث."""
        return self.second.index

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def stop_for(self, buffer: float) -> float:
        """«ستوبي هيدا القمّة عليها بقليل» — خلف الطرف البعيد بالهامش."""
        if buffer < 0:
            raise ValueError("الهامش لا يكون سالبًا")
        return self.bottom - buffer if self.direction == "bullish" else self.top + buffer

    def render(self) -> str:
        return (f"BPR {self.direction} {self.bottom:g}–{self.top:g} · "
                f"المنتصف {self.midpoint:g}")


def find_bprs(fvgs: Sequence[FVG], min_overlap: float = 0.0) -> List[BPR]:
    """
    يقرن كل فراغٍ بفراغٍ **معاكسٍ** بعده يتراكب معه.

    ⚠️ والتراكب شرطٌ لا التجاور: فراغان متعاكسان متباعدان ليسا BPR —
    إنما هما منطقتان مستقلّتان.

    ولا يُقرَن الفراغ الواحد إلّا مرّة: أوّل معاكسٍ يتراكب معه، فأطولُ
    سلسلةٍ من الفراغات لا تولّد تراكباتٍ وهميّة.
    """
    ordered = sorted(fvgs, key=lambda f: f.index)
    used: set = set()
    out: List[BPR] = []

    for i, a in enumerate(ordered):
        if a.index in used:
            continue
        for b in ordered[i + 1:]:
            if b.index in used or b.direction == a.direction:
                continue
            top = min(a.top, b.top)
            bottom = max(a.bottom, b.bottom)
            if top - bottom <= min_overlap:
                continue
            out.append(BPR(a, b, top, bottom))
            used.add(a.index)
            used.add(b.index)
            break

    out.sort(key=lambda p: p.index)
    return out


def group_adjacent(fvgs: List[FVG], max_gap: float) -> List[tuple[float, float, float]]:
    """
    يدمج فراغات متجاورة بنفس الاتجاه في منطقة واحدة، ويرجع (bottom, top, midpoint).

    «When several adjacent FVGs are created by the same confirmed displacement,
     they may be grouped into one composite zone and their combined midpoint used
     as a contextual balance reference.» (§7)

    max_gap غير معرّف في المصدر (§17 zone merging) — يأتي من params.
    """
    if not fvgs:
        return []

    ordered = sorted(fvgs, key=lambda f: f.bottom)
    groups: List[List[FVG]] = [[ordered[0]]]

    for f in ordered[1:]:
        prev = groups[-1][-1]
        same_dir = f.direction == prev.direction
        close_enough = f.bottom - prev.top <= max_gap
        if same_dir and close_enough:
            groups[-1].append(f)
        else:
            groups.append([f])

    out = []
    for g in groups:
        bottom = min(f.bottom for f in g)
        top = max(f.top for f in g)
        out.append((bottom, top, (bottom + top) / 2.0))
    return out
