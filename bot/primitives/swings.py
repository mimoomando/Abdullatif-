"""
القمم والقيعان (Swing Highs / Lows) — الدرس 9.

النص المصدري:
    «A Swing High is higher than the immediately preceding and immediately
     following high. A Swing Low is lower than the immediately preceding and
     immediately following low.»

وينبّه الدرس نفسه إلى أن قمم M5/M15 غالبًا سيولة داخلية لا نقاط انعكاس كبرى،
ولذلك تُفصل هنا «القمة الفراكتالية» عن «القمة الهيكلية» (structure.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal

from ..data import Series

Kind = Literal["high", "low"]


@dataclass(frozen=True)
class Swing:
    index: int
    time: datetime
    price: float
    kind: Kind

    @property
    def is_high(self) -> bool:
        return self.kind == "high"

    @property
    def is_low(self) -> bool:
        return self.kind == "low"


def find_swings(series: Series, lookback: int = 1) -> List[Swing]:
    """
    يرجع القمم والقيعان مرتبة بالفهرس.

    lookback=1 هو التعريف الحرفي في الدرس 9 (فراكتال ثلاث شموع).
    قيم أكبر تعطي قممًا أندر وأكثر أهمية — تُستعمل على الأطر الكبرى.

    شمعة واحدة قد تكون قمة وقاعًا معًا (شمعة خارجية)؛ الاثنتان تُرجعان.
    """
    if lookback < 1:
        raise ValueError("lookback يجب أن يكون 1 أو أكثر")

    out: List[Swing] = []
    n = len(series)
    for i in range(lookback, n - lookback):
        c = series[i]
        left = range(i - lookback, i)
        right = range(i + 1, i + lookback + 1)

        if all(c.high > series[j].high for j in left) and all(
            c.high > series[j].high for j in right
        ):
            out.append(Swing(i, c.time, c.high, "high"))

        if all(c.low < series[j].low for j in left) and all(
            c.low < series[j].low for j in right
        ):
            out.append(Swing(i, c.time, c.low, "low"))

    out.sort(key=lambda s: (s.index, s.kind))
    return out


def highs(swings: List[Swing]) -> List[Swing]:
    return [s for s in swings if s.is_high]


def lows(swings: List[Swing]) -> List[Swing]:
    return [s for s in swings if s.is_low]


def last_swing(swings: List[Swing], kind: Kind) -> Swing | None:
    for s in reversed(swings):
        if s.kind == kind:
            return s
    return None
