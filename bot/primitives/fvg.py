"""
الفراغ السعري / Fair Value Gap — الدرس 5.

النص المصدري:
    «A Fair Value Gap (FVG) is drawn across three candles using the wicks of the
     first and third candles. A bullish FVG is the untraded zone between the
     first candle's high and the third candle's low after upward displacement.
     A bearish FVG is the untraded zone between the third candle's high and the
     first candle's low after downward displacement.»

بالذيول لا الأجسام — وهذا مؤكَّد في المصدر ولا لبس فيه.

قيد الاستعمال (الدرس 5): الفراغ ليس إشارة مستقلة. هذه الوحدة تكتشف الموقع فقط،
والقرار يُبنى في سلسلة التأكيد.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal

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
