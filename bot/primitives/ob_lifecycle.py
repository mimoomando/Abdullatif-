"""
مراحل الأوردر بلوك — Mitigation · BMS · Propulsion.

⭐⭐⭐ **أوضح نصٍّ وصل للتسلسل** — البثّ ٣ (≈12:29):

    «هي عندي نقطة أوردر بلوك ابتدَّ منه، **أول مرّة أعمل له تخفيف**،
     وهي **المرّة الثانية طلع من الميتيجيشن**… كان عنّا هون **أول لمس
     اللي هو هيدا الميتيجيشن**، وطلع **عمل بي إم إس**، وهون هيدا
     **البروبلشن بلوك**. فإذا هي **آخر مرحلة من الأوردر بلوك** —
     بعد هلّا ها المنطقة **إذا في حال انضربت راح تروح نهائي**»

فالتسلسل:

    أوردر بلوك
      → **تخفيف** (أول لمس)            = Mitigation Block
      → **BMS** (كسر هيكل مع الاتجاه)
      → **بروبلشن**                    = آخر مرحلة
      → إن ضُربت البروبلشن: **تروح نهائيًّا** ⛔

⛔ **وقيدٌ من المصدر لا يجوز تجاوزه** (§7):

    «The instructor treats the primary OB and higher-timeframe structure as
     the source of meaning; mitigation, propulsion, and breaker labels are
     valid only in that history and are **not independent candle patterns**.»

⇒ فهذه المناطق **مشتقّةٌ من أمٍّ** ولا تُرصد وحدها أبدًا. ولذلك لا
دالّة هنا تمسح السلسلة بحثًا عن «بروبلشن»: كلُّ منطقةٍ تحمل
`parent_index`، ولا تُبنى إلّا بتتبّع تاريخ أمّها.

⚠️ **وفرقها عن البريكر:** البريكر منطقةٌ **فشلت** فانقلب دورها،
وشرطُه ألّا تكون خُفِّفت. وهذه مراحلُ منطقةٍ **نجحت**: خُفِّفت ثم
دفعت السعر فكسر الهيكل. فالمساران متنافيان — ولذلك يُفحص التعارض
في `trace` ولا يُترك للمصادفة.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional, Sequence

from ..data import Series
from .order_block import Direction, OrderBlock, _defining_candle
from .structure import find_breaks
from .swings import Swing

Stage = Literal["mitigation", "propulsion"]


@dataclass(frozen=True)
class DerivedBlock:
    """منطقةٌ مشتقّة من أوردر بلوك — لا كائنٌ مستقلّ."""

    parent_index: int
    stage: Stage
    index: int
    time: datetime
    direction: Direction
    top: float
    bottom: float
    bms_index: Optional[int] = None      # للبروبلشن وحدها

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def touched_by(self, candle) -> bool:
        return candle.low <= self.top and candle.high >= self.bottom

    def stop_for(self, buffer: float) -> float:
        if buffer < 0:
            raise ValueError("الهامش لا يكون سالبًا")
        return self.bottom - buffer if self.direction == "bullish" else self.top + buffer

    def render(self) -> str:
        name = "تخفيف" if self.stage == "mitigation" else "بروبلشن"
        return (f"{name} {self.direction} {self.bottom:g}–{self.top:g} "
                f"(أمّها @{self.parent_index})")


@dataclass(frozen=True)
class Lifecycle:
    """
    تاريخ منطقةٍ واحدة من أوّل لمسةٍ إلى موتها.

    و`dead_at` هو ما يجعل هذا الكائن ذا قيمة: «**إذا في حال انضربت
    راح تروح نهائي**». فمنطقةٌ ميّتة لا تُعرَض ولا تُتداول ولو عاد
    السعر إليها ألف مرّة.
    """

    parent: OrderBlock
    mitigation: Optional[DerivedBlock] = None
    propulsion: Optional[DerivedBlock] = None
    bms_index: Optional[int] = None
    dead_at: Optional[int] = None

    @property
    def dead(self) -> bool:
        return self.dead_at is not None

    @property
    def stage(self) -> str:
        """المرحلة التي بلغتها — بالعربيّة، للسجلّ والتقرير."""
        if self.dead:
            return "ميّتة"
        if self.propulsion is not None:
            return "بروبلشن — آخر مرحلة"
        if self.bms_index is not None:
            return "بعد BMS بلا بروبلشن"
        if self.mitigation is not None:
            return "مخفَّفة"
        return "طازجة"

    @property
    def active(self) -> Optional[object]:
        """
        المنطقة التي يُتعامل معها الآن — أو None إن ماتت.

        ⭐ والبروبلشن تتقدّم على الأمّ متى وُجدت: هي «**آخر مرحلة**»
        وهي الأقرب إلى السعر، ومنها يكون الدفع.
        """
        if self.dead:
            return None
        return self.propulsion or self.parent

    def render(self) -> str:
        out = [f"أوردر بلوك {self.parent.direction} "
               f"{self.parent.bottom:g}–{self.parent.top:g} · {self.stage}"]
        for b in (self.mitigation, self.propulsion):
            if b is not None:
                out.append("    " + b.render())
        if self.dead:
            out.append(f"    ⛔ ضُربت البروبلشن @{self.dead_at} — راحت نهائيًّا")
        return "\n".join(out)


def _first_touch(series: Series, ob: OrderBlock) -> Optional[int]:
    for i in range(ob.break_index + 1, len(series)):
        if ob.touched_by(series[i]):
            return i
    return None


def _bms_after(
    series: Series,
    swings: Sequence[Swing],
    direction: Direction,
    after: int,
    use_body: bool = True,
) -> Optional[int]:
    """
    أوّل كسر هيكل **مع اتجاه المنطقة** بعد لمسةِ التخفيف.

    ويُستعمل `find_breaks` القائمة — فالكسر بالجسم لا بالذيل
    (الدرس 10)، ولا يُعاد تعريفه هنا.
    """
    want = "up" if direction == "bullish" else "down"
    for b in find_breaks(series, list(swings), use_body=use_body):
        if b.index > after and b.direction == want:
            return b.index
    return None


def trace(
    series: Series,
    ob: OrderBlock,
    swings: Sequence[Swing],
    use_body: bool = True,
) -> Lifecycle:
    """
    يتتبّع مراحل منطقةٍ واحدة على شموعها.

    ⚠️ **والمنطقة الفاشلة لا تدخل هنا.** `failed` و`breaker` مسارٌ
    آخر: تلك فشلت فانقلب دورها، وهذه نجحت فدفعت. فإن جاءت فاشلةً
    رُجِّعت بلا مراحل — ولا يُخترع لها تسلسلٌ لم يحدث.
    """
    if ob.state in ("failed", "breaker"):
        return Lifecycle(ob)

    touch = _first_touch(series, ob)
    if touch is None:
        return Lifecycle(ob)

    c = series[touch]
    mitigation = DerivedBlock(
        parent_index=ob.index, stage="mitigation", index=touch, time=c.time,
        direction=ob.direction, top=c.high, bottom=c.low,
    )

    bms = _bms_after(series, swings, ob.direction, touch, use_body)
    if bms is None:
        return Lifecycle(ob, mitigation)

    # البروبلشن = الشمعة المعرِّفة للاندفاع الذي صنع الـBMS،
    # بالتعريف نفسه المستعمل للأمّ — آخر شمعة معاكسة قبله.
    def_idx = _defining_candle(series, touch, bms, ob.direction)
    if def_idx is None:
        return Lifecycle(ob, mitigation, bms_index=bms)

    d = series[def_idx]
    propulsion = DerivedBlock(
        parent_index=ob.index, stage="propulsion", index=def_idx, time=d.time,
        direction=ob.direction, top=d.high, bottom=d.low, bms_index=bms,
    )

    # «إذا في حال انضربت راح تروح نهائي» — والضرب إغلاقٌ بالجسم عبرها
    dead_at: Optional[int] = None
    for i in range(bms + 1, len(series)):
        k = series[i]
        broke = (k.body_bottom < propulsion.bottom
                 if ob.direction == "bullish"
                 else k.body_top > propulsion.top)
        if broke:
            dead_at = i
            break

    return Lifecycle(ob, mitigation, propulsion, bms, dead_at)


def trace_all(
    series: Series,
    blocks: Sequence[OrderBlock],
    swings: Sequence[Swing],
    use_body: bool = True,
) -> List[Lifecycle]:
    return [trace(series, ob, swings, use_body) for ob in blocks]


def usable(cycles: Sequence[Lifecycle]) -> List[Lifecycle]:
    """ما لم يمت — وهو وحده ما يُعرَض على السلسلة."""
    return [c for c in cycles if not c.dead]
