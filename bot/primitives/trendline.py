"""
الترند لاين والقنوات — الدرس 3 والدرس 8 والدرس 12.

الترند لاين خط بين نقطتين:  y = ميل × س + مقطع
والقناة هي الخط نفسه مزاحًا بمقدار ثابت.
لا حاجة لأداة رسم — الحاجة إلى نقطتين وحسبة.

⚠️ التعارض C1 — مرجع الإرساء يختلف حسب الكائن، والمصدر لم يوحّده:

    الدرس 3  : الترند لاين الهيكلي على **الأجسام** عبر Line Chart
    الدرس 8  : حدود Flag / Pennant على **الذيول** صراحةً
    الدرس 12 : القنوات «تسمح بالذيول وتفضّل الأجسام»

لذلك `anchor` معامل صريح هنا، ولا توجد قيمة مخفية. المستدعي يمرّر ما
يناسب الكائن الذي يرسمه.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Sequence

from ..data import Series
from .swings import Swing

Anchor = Literal["body", "wick"]
Side = Literal["support", "resistance"]


def anchor_price(series: Series, swing: Swing, anchor: Anchor) -> float:
    """السعر المستعمل كنقطة إرساء لهذه القمة/القاع."""
    c = series[swing.index]
    if anchor == "wick":
        return swing.price
    return c.body_top if swing.is_high else c.body_bottom


@dataclass(frozen=True)
class TrendLine:
    x1: int
    y1: float
    x2: int
    y2: float
    side: Side
    anchor: Anchor

    @property
    def slope(self) -> float:
        dx = self.x2 - self.x1
        return 0.0 if dx == 0 else (self.y2 - self.y1) / dx

    def price_at(self, index: int) -> float:
        """سعر الخط عند أي شمعة — بما فيها المستقبل (امتداد Ray)."""
        return self.y1 + self.slope * (index - self.x1)

    def distance(self, index: int, price: float) -> float:
        """موجب = فوق الخط · سالب = تحته."""
        return price - self.price_at(index)

    def broken_at(
        self, series: Series, use_body: bool = True, start: int | None = None
    ) -> int | None:
        """
        أول فهرس يكسر فيه السعر الخط.

        الكسر بالجسم افتراضًا (الدرس 10). خط الدعم يُكسر هبوطًا، والمقاومة صعودًا.
        """
        begin = self.x2 + 1 if start is None else start
        for i in range(begin, len(series)):
            c = series[i]
            level = self.price_at(i)
            top = c.body_top if use_body else c.high
            bottom = c.body_bottom if use_body else c.low
            if self.side == "support" and bottom < level:
                return i
            if self.side == "resistance" and top > level:
                return i
        return None

    def touches(
        self, series: Series, tolerance: float, use_body: bool = True
    ) -> List[int]:
        """الشموع التي لامست الخط ضمن السماحية — بين نقطتي الإرساء وبعدهما."""
        out: List[int] = []
        for i in range(self.x1, len(series)):
            c = series[i]
            level = self.price_at(i)
            probe = (
                (c.body_bottom if use_body else c.low)
                if self.side == "support"
                else (c.body_top if use_body else c.high)
            )
            if abs(probe - level) <= tolerance:
                out.append(i)
        return out


def build(
    series: Series,
    pivots: Sequence[Swing],
    anchor: Anchor = "body",
    min_pivots: int = 2,
) -> TrendLine | None:
    """
    يبني ترند لاين من آخر نقطتي إرساء متجانستين.

    الدرس 3: لمستان على الأقل، ورسم على الأجسام للترند الهيكلي.
    الدرس 4: الهابط من القمم (فوق)، والصاعد من القيعان (تحت).
    """
    if len(pivots) < min_pivots:
        return None

    kinds = {p.kind for p in pivots}
    if len(kinds) != 1:
        raise ValueError("نقاط الإرساء يجب أن تكون كلها قممًا أو كلها قيعانًا")

    a, b = pivots[-2], pivots[-1]
    side: Side = "resistance" if a.is_high else "support"
    return TrendLine(
        x1=a.index,
        y1=anchor_price(series, a, anchor),
        x2=b.index,
        y2=anchor_price(series, b, anchor),
        side=side,
        anchor=anchor,
    )


@dataclass(frozen=True)
class Channel:
    """
    قناة متوازية — الدرس 12 والمرحلة 2 الدرس 3.

    «اسمها بالل تشانل» = Parallel Channel. القناة الجاهزة التي تحدد نفسها
    (Regression Trend) مرفوضة صراحةً في المصدر.
    """

    base: TrendLine
    offset: float

    def upper_at(self, index: int) -> float:
        return self.base.price_at(index) + max(self.offset, 0.0)

    def lower_at(self, index: int) -> float:
        return self.base.price_at(index) + min(self.offset, 0.0)

    def mid_at(self, index: int) -> float:
        """
        خط المنتصف.

        ⚠️ المرحلة 2 الدرس 3: «Do not trade from the channel midpoint.»
        مرجع سياق لا نقطة دخول.
        """
        return (self.upper_at(index) + self.lower_at(index)) / 2.0

    def contains(self, index: int, price: float) -> bool:
        return self.lower_at(index) <= price <= self.upper_at(index)


def build_channel(
    series: Series,
    pivots: Sequence[Swing],
    opposite: Swing,
    anchor: Anchor = "body",
) -> Channel | None:
    """
    قناة من نقطتي إرساء متجانستين + النقطة المقابلة التي تحدد العرض.

    المرحلة 2 الدرس 3: صاعدة من قاعين مع القمة المقابلة، وهابطة من قمتين
    مع القاع الذي أنتج القمة الثانية — لا أي قاع صغير عشوائي.
    """
    line = build(series, pivots, anchor=anchor)
    if line is None:
        return None
    offset = anchor_price(series, opposite, anchor) - line.price_at(opposite.index)
    return Channel(base=line, offset=offset)
