"""
فيبوناتشي وموقع القيمة — الدرس 6 والدرس 8 والدرس 14.

⚠️ ملاحظة مفاهيمية مهمة:

فيبوناتشي ليست «أداة» يحتاج البوت أن يجلبها من منصة. إنها معادلة:

    المستوى = القمة − (القمة − القاع) × النسبة

ما تفعله المنصة هو رسم خط أفقي عند الرقم الناتج **لترى أنت**. البوت لا
يحتاج الخط — يحتاج الرقم، ويحسبه هنا. الشيء نفسه ينطبق على الترند لاين
(خط بين نقطتين)، والقناة (الخط نفسه مزاحًا)، والمستطيل (سعران).

النص المصدري (الدرس 6):
    «For an upward impulse, draw from the meaningful low to the meaningful high;
     for a downward impulse, draw from the meaningful high to the meaningful low.
     The source's selected retracement levels are 50%, 61.8%, and 78.6%.»

والدرس 14 لبوابة القيمة:
    «In the bearish H4 example, sells are not taken below the 50% midpoint of the
     measured range; in the bullish example, buys are not taken above it.»

و§9 يخفّف ذلك من منع مطلق إلى تقدير مخاطرة:
    «50% grades value and risk … it neither triggers entry nor guarantees a
     retracement.»
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal

Direction = Literal["bullish", "bearish"]
Value = Literal["discount", "premium", "midpoint"]

# الدرس 6 — المستعملة فعليًا في المنهج
SOURCE_LEVELS: List[float] = [0.5, 0.618, 0.786]

# تُعرض للسياق: 23.6 غير مستعملة، و38.2 لأنماط الاستمرار (الدرس 8)
CONTEXT_LEVELS: List[float] = [0.236, 0.382]

# الدرس 8 — مستويات الإسقاط
EXTENSION_LEVELS: List[float] = [1.0, 1.382, 1.618, 1.84]


@dataclass(frozen=True)
class Impulse:
    """
    موجة مؤكدة تُقاس عليها النسب.

    الدرس 6: تُقاس **الموجة الفعّالة كاملة**، لا تذبذبًا داخليًا صغيرًا.
    و§9: يُعاد الحساب عند تأكّد موجة جديدة — النسب ليست خطوطًا دائمة.
    """

    low: float
    high: float
    direction: Direction

    def __post_init__(self):
        if self.high <= self.low:
            raise ValueError("القمة يجب أن تكون أعلى من القاع")

    @property
    def size(self) -> float:
        return self.high - self.low

    @property
    def midpoint(self) -> float:
        """نقطة الـ50% — بوابة القيمة (الدرس 14)."""
        return self.low + self.size * 0.5

    def retracement(self, ratio: float) -> float:
        """
        سعر مستوى الارتداد.

        صاعدة : يُقاس من القاع إلى القمة، والارتداد ينزل ⇒ high − size×ratio
        هابطة : يُقاس من القمة إلى القاع، والارتداد يصعد ⇒ low + size×ratio
        """
        if self.direction == "bullish":
            return self.high - self.size * ratio
        return self.low + self.size * ratio

    def extension(self, ratio: float) -> float:
        """إسقاط ما بعد الموجة (الدرس 8) — أهداف محتملة."""
        if self.direction == "bullish":
            return self.low + self.size * ratio
        return self.high - self.size * ratio

    def levels(self, ratios: List[float] | None = None) -> Dict[float, float]:
        return {r: self.retracement(r) for r in (ratios or SOURCE_LEVELS)}

    def extensions(self, ratios: List[float] | None = None) -> Dict[float, float]:
        return {r: self.extension(r) for r in (ratios or EXTENSION_LEVELS)}

    # ── بوابة القيمة ──

    def value_of(self, price: float) -> Value:
        """
        أين يقع السعر من منتصف الموجة؟

        في موجة صاعدة: فوق المنتصف = premium (شراء غالٍ)، تحته = discount.
        وفي موجة هابطة تنعكس الأدوار للبيع.
        """
        mid = self.midpoint
        if abs(price - mid) < 1e-9:
            return "midpoint"
        above = price > mid
        if self.direction == "bullish":
            return "premium" if above else "discount"
        return "discount" if above else "premium"

    def is_expensive(self, price: float, side: Direction) -> bool:
        """
        هل هذا الدخول غالٍ حسب موقعه من الـ50%؟

        ليس منعًا — الدرس 14 و§9 يجعلانه **تقدير مخاطرة**: الدخول الغالي
        يحتاج مبررًا أقوى، ولا يُمنع تلقائيًا.
        """
        if side == "bullish":
            return price > self.midpoint
        return price < self.midpoint

    def golden_zone(self) -> tuple[float, float]:
        """منطقة 61.8–78.6 — التصحيح العميق المعتبر (الدرس 6)."""
        a, b = self.retracement(0.618), self.retracement(0.786)
        return (min(a, b), max(a, b))


def measure(low: float, high: float, direction: Direction) -> Impulse:
    return Impulse(low=low, high=high, direction=direction)
