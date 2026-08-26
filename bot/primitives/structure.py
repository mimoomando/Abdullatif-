"""
هيكل السوق — الدرس 9 والمرحلة 2 الدرس 4.

مفهومان منفصلان يجب ألا يختلطا:

1. قمة/قاع فراكتالي  (swings.py) — ثلاث شموع، كثير وداخلي غالبًا.
2. قمة/قاع **هيكلي حقيقي** — هذه الوحدة.

النص المصدري للتحقق:
    «In bearish structure, a true high is validated when the bearish impulse from
     it breaks the governing low. A later rise remains corrective until its
     following bearish leg breaks that low. Mirror the rule in bullish structure:
     a true low must drive the break of the governing high.»

والكسر يكون **بالجسم لا بالذيل** (الدرس 10):
    «The structural break must be by candle body, not wick.»
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional

from ..data import Series
from .swings import Swing

Trend = Literal["bullish", "bearish", "undefined"]
BreakKind = Literal["BOS", "CHoCH"]


@dataclass(frozen=True)
class StructureBreak:
    index: int
    time: datetime
    kind: BreakKind
    direction: Literal["up", "down"]
    level: float          # المستوى المكسور
    close: float          # الإغلاق الذي كسره
    broken_swing: Swing


@dataclass(frozen=True)
class ValidatedSwing:
    swing: Swing
    validated_at: int     # فهرس الشمعة التي أكملت التحقق
    governing_level: float


def _break_price(series: Series, i: int, use_body: bool) -> tuple[float, float]:
    """يرجع (السعر الأعلى، السعر الأدنى) المستعمل لاختبار الكسر."""
    c = series[i]
    return (c.body_top, c.body_bottom) if use_body else (c.high, c.low)


def classify_trend(swings: List[Swing]) -> Trend:
    """
    صاعد  : قمم أعلى وقيعان أعلى.
    هابط  : قمم أدنى وقيعان أدنى.
    يحتاج قمتين وقاعين على الأقل للحكم.
    """
    hs = [s for s in swings if s.is_high]
    ls = [s for s in swings if s.is_low]
    if len(hs) < 2 or len(ls) < 2:
        return "undefined"

    higher_highs = hs[-1].price > hs[-2].price
    higher_lows = ls[-1].price > ls[-2].price
    lower_highs = hs[-1].price < hs[-2].price
    lower_lows = ls[-1].price < ls[-2].price

    if higher_highs and higher_lows:
        return "bullish"
    if lower_highs and lower_lows:
        return "bearish"
    return "undefined"


def find_breaks(
    series: Series,
    swings: List[Swing],
    use_body: bool = True,
    tolerance: float = 0.0,
) -> List[StructureBreak]:
    """
    يرصد كسور الهيكل.

    BOS   = كسر مع الاتجاه القائم (استمرار).
    CHoCH = أول كسر عكس الاتجاه القائم (تغيّر طابع).

    كل قمة/قاع يُكسر مرة واحدة فقط؛ بعدها يخرج من الاعتبار.
    """
    out: List[StructureBreak] = []
    consumed: set[int] = set()
    trend: Trend = "undefined"

    for i in range(len(series)):
        top, bottom = _break_price(series, i, use_body)

        for s in swings:
            if s.index >= i or s.index in consumed:
                continue

            if s.is_high and top > s.price + tolerance:
                kind: BreakKind = "CHoCH" if trend == "bearish" else "BOS"
                out.append(
                    StructureBreak(i, series[i].time, kind, "up", s.price, series[i].close, s)
                )
                consumed.add(s.index)
                trend = "bullish"

            elif s.is_low and bottom < s.price - tolerance:
                kind = "CHoCH" if trend == "bullish" else "BOS"
                out.append(
                    StructureBreak(i, series[i].time, kind, "down", s.price, series[i].close, s)
                )
                consumed.add(s.index)
                trend = "bearish"

    out.sort(key=lambda b: b.index)
    return out


def validate_swings(
    series: Series,
    swings: List[Swing],
    use_body: bool = True,
) -> List[ValidatedSwing]:
    """
    يطبّق قاعدة «القمة الحقيقية» من المرحلة 2 الدرس 4.

    قمة تُعتبر حقيقية إذا كسرت الحركة الهابطة التالية لها **القاع الحاكم**
    الذي سبقها. والعكس للقاع الحقيقي مع القمة الحاكمة.

    ما لم يتحقق ذلك، تبقى القمة ارتدادًا تصحيحيًا لا نقطة انعكاس هيكلية —
    وهذا ما يمنع البوت من معاملة كل تذبذب صغير كتغيّر هيكل.
    """
    out: List[ValidatedSwing] = []

    for s in swings:
        governing: Optional[Swing] = None
        for prev in swings:
            if prev.index >= s.index:
                break
            if s.is_high and prev.is_low:
                governing = prev
            elif s.is_low and prev.is_high:
                governing = prev

        if governing is None:
            continue

        for i in range(s.index + 1, len(series)):
            top, bottom = _break_price(series, i, use_body)
            if s.is_high and bottom < governing.price:
                out.append(ValidatedSwing(s, i, governing.price))
                break
            if s.is_low and top > governing.price:
                out.append(ValidatedSwing(s, i, governing.price))
                break

    return out


def governing_levels(validated: List[ValidatedSwing]) -> tuple[Optional[float], Optional[float]]:
    """آخر قمة وقاع هيكليين مؤكدين — مرجع الاتجاه الحاكم."""
    high = next((v.swing.price for v in reversed(validated) if v.swing.is_high), None)
    low = next((v.swing.price for v in reversed(validated) if v.swing.is_low), None)
    return high, low
