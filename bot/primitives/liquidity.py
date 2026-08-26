"""
السيولة وكسحها (Liquidity / Sweep) — ملف liquidity-structure والدرس 10.

النص المصدري:
    «Treat liquidity as a map of likely price destinations, not an entry signal.»
    «Wait for a sweep plus structure or price-action confirmation before an entry.»
    «A liquidity break has no direction by itself.»

الكسح = اختراق قمة/قاع سابق ثم **استعادة** الإغلاق للجهة الأخرى.
مجرد التجاوز ليس كسحًا؛ لو أُغلق فوق القمة واستمر فهو كسر لا كسح.

⚠️ التعارض C4: المدرّب يقارن مزوّدين لأن الذيل قد يظهر عند أحدهما فقط.
البوت يعتمد فيد `XAUUSD.m` وحده — فقد لا يرى كسحًا رآه المدرّب على شارت آخر.
هذا قيد حقيقي مسجَّل، لا خطأ برمجي.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal

from ..data import Series
from .swings import Swing

Side = Literal["buy_side", "sell_side"]


@dataclass(frozen=True)
class Sweep:
    swept_swing: Swing
    penetration_index: int      # الشمعة التي تجاوزت المستوى
    reclaim_index: int          # الشمعة التي أعادت الإغلاق
    time: datetime
    side: Side                  # buy_side = فوق قمة · sell_side = تحت قاع
    level: float
    extreme: float              # أقصى سعر بلغه التجاوز

    @property
    def penetration(self) -> float:
        return abs(self.extreme - self.level)

    @property
    def bars_to_reclaim(self) -> int:
        return self.reclaim_index - self.penetration_index


def find_sweeps(
    series: Series,
    swings: List[Swing],
    max_bars_to_reclaim: int = 3,
    min_penetration: float = 0.0,
    require_reclaim: bool = True,
) -> List[Sweep]:
    """
    يرصد كسح السيولة عند القمم والقيعان.

    فوق قمة  : high > level، ثم إغلاق < level خلال max_bars_to_reclaim.
    تحت قاع  : low  < level، ثم إغلاق > level خلال المدة نفسها.

    max_bars_to_reclaim و min_penetration غير معرّفين في المصدر (§17).
    """
    out: List[Sweep] = []
    consumed: set[int] = set()

    for s in swings:
        if s.index in consumed:
            continue

        for i in range(s.index + 1, len(series)):
            c = series[i]

            if s.is_high and c.high > s.price:
                if c.high - s.price < min_penetration:
                    continue
                extreme = c.high
                for j in range(i, min(i + max_bars_to_reclaim + 1, len(series))):
                    extreme = max(extreme, series[j].high)
                    if not require_reclaim or series[j].close < s.price:
                        out.append(
                            Sweep(s, i, j, series[j].time, "buy_side", s.price, extreme)
                        )
                        consumed.add(s.index)
                        break
                break

            if s.is_low and c.low < s.price:
                if s.price - c.low < min_penetration:
                    continue
                extreme = c.low
                for j in range(i, min(i + max_bars_to_reclaim + 1, len(series))):
                    extreme = min(extreme, series[j].low)
                    if not require_reclaim or series[j].close > s.price:
                        out.append(
                            Sweep(s, i, j, series[j].time, "sell_side", s.price, extreme)
                        )
                        consumed.add(s.index)
                        break
                break

    out.sort(key=lambda x: x.reclaim_index)
    return out


def equal_levels(swings: List[Swing], tolerance: float) -> List[List[Swing]]:
    """
    يجمّع القمم/القيعان المتساوية تقريبًا — تجمّعات سيولة (الدرس 9).

    المصدر لا يعطي سماحية رقمية للتساوي؛ tolerance من params.
    """
    groups: List[List[Swing]] = []
    for kind in ("high", "low"):
        pool = sorted([s for s in swings if s.kind == kind], key=lambda s: s.price)
        current: List[Swing] = []
        for s in pool:
            if current and abs(s.price - current[-1].price) <= tolerance:
                current.append(s)
            else:
                if len(current) > 1:
                    groups.append(current)
                current = [s]
        if len(current) > 1:
            groups.append(current)
    return groups
