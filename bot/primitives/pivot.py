"""
نقطة الارتكاز اليومية والأسبوعية — المرحلة 2 الدرس 4.

المعادلة المؤكدة بصريًا في المصدر:

    Pivot = (High + Low + Close) / 3

من الشمعة **المكتملة** على الإطار المقابل (يومي أو أسبوعي).

مثال آخر على أن «الأداة» حساب لا برنامج: المنصة ترسم خطًا عند الرقم،
والبوت يحتاج الرقم فقط.

قيد الاستعمال (المصدر):
    «Pivot is a control/support-resistance reference, not a touch trigger.»

ما زال غير معرّف: حدود يوم/أسبوع الوسيط، وأي شمعة تُعتبر مكتملة عند التدوير،
والتقريب، وسماحية الإغلاق والريتست، واختيار الهدف.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..data import Candle

Period = Literal["daily", "weekly"]


@dataclass(frozen=True)
class Pivot:
    period: Period
    value: float
    source_high: float
    source_low: float
    source_close: float


def pivot_point(candle: Candle, period: Period = "daily") -> Pivot:
    """يحسب الارتكاز من شمعة مكتملة."""
    value = (candle.high + candle.low + candle.close) / 3.0
    return Pivot(period, value, candle.high, candle.low, candle.close)


def pivot_from_values(high: float, low: float, close: float, period: Period = "daily") -> Pivot:
    return Pivot(period, (high + low + close) / 3.0, high, low, close)


def position(price: float, pivot: Pivot) -> Literal["above", "below", "at"]:
    if abs(price - pivot.value) < 1e-9:
        return "at"
    return "above" if price > pivot.value else "below"
