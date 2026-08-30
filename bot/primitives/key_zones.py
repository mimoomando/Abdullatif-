"""
المناطق المفتاحية — البثّ المباشر ٢.

╔══════════════════════════════════════════════════════════════════╗
║  «كيف نحدّد المناطق المفتاحية؟                                    ║
║   بتتحدّد من **الدعوم والمقاومات والإغلاق تبع الجسوم**»            ║
╚══════════════════════════════════════════════════════════════════╝

⭐⭐ **ولماذا الجسم لا الذيل؟** أجاب بنفسه، وحلّ به تعارضًا ظلّ مفتوحًا
عندي من أول يوم (C1):

    «**السيولة الحقيقية** تكمن بالمنطقة عند **إغلاق جسم الشمعة**،
     ولكن **السيولة المرتكزة لسحب الستوبات** والأوردرات
     بتكون **عند الذيل**»

فليست المسألة «جسم أم ذيل» بل **لكلٍّ وظيفته**:

    الجسم ⇒ سيولة حقيقية ⇒ **المناطق المفتاحية** · كسر الهيكل · بوابة الـ50%
    الذيل ⇒ سيولة ستوبات ⇒ **الكسح** · الفراغ السعري

ولهذا يتجمّع التفاعل عند الإغلاقات:

    «بصير **تفاعل كثير عند الإغلاقات**، لأنه بيكون المكان
     **مكان أقوى لظهور بائع أو مشتري**»

**والدور ثنائي — منصوص:**

    «طالما السعر **تحت منها هي مقاومة**،
     بس السعر يصير **فوق منها بصير دعم**»

⚠️ **المنطقة المفتاحية ليست إشارة دخول.** هي **موضع**: عندها تُقرأ
الأحجام، وعندها تُنتظر النماذج. «التشارت مليان مناطق مفتاحية — مش يعني
كسر منطقة مفتاحية يعني هرب السعر».
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

from ..data import Series

Role = Literal["resistance", "support"]


@dataclass(frozen=True)
class KeyZone:
    """
    منطقة تجمّعت عندها إغلاقات أجسام — «مكان أقوى لظهور بائع أو مشتري».

    `touches` عدد الإغلاقات التي شكّلتها: كلما كثرت، قوي الموضع.
    """

    bottom: float
    top: float
    touches: int
    first_index: int
    last_index: int

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0

    @property
    def height(self) -> float:
        return self.top - self.bottom

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def role_for(self, price: float) -> Role:
        """
        «طالما السعر تحت منها هي مقاومة، بس يصير فوق منها بصير دعم».

        الدور يتبع موضع السعر لا تاريخ المنطقة — ولذلك يُسأل عنه ولا
        يُخزَّن.
        """
        return "resistance" if price < self.mid else "support"

    def distance_from(self, price: float) -> float:
        """صفر داخل المنطقة، وإلا المسافة إلى أقرب حافّة."""
        if self.contains(price):
            return 0.0
        return self.bottom - price if price < self.bottom else price - self.top

    def render(self, price: Optional[float] = None) -> str:
        role = ""
        if price is not None:
            role = " · مقاومة" if self.role_for(price) == "resistance" else " · دعم"
        return f"منطقة {self.bottom:g}–{self.top:g} ({self.touches} إغلاق){role}"


def find_key_zones(
    series: Series,
    tolerance: float,
    min_touches: int = 2,
    max_zones: Optional[int] = None,
) -> List[KeyZone]:
    """
    يستخرج المناطق المفتاحية من **إغلاقات الأجسام** في التاريخ.

    «بتبيّن معك بالتشارت — بس في حال انت **رجعت لورا بالهيستوري**»

    `tolerance` : كم يبعد إغلاقان ويظلّان في منطقة واحدة.
        🔴 **KZ1 — غير معرَّف.** لم يعطِ مقدارًا. مقبض مكشوف.

    `min_touches` : أقلّ عدد إغلاقات يصنع منطقة.
        🔴 **KZ2 — غير معرَّف.** اثنان هو أقلّ ما يصحّ تسميته «تجمّعًا»:
        إغلاق واحد نقطة لا منطقة.

    ⚠️ **الإغلاق وحده يدخل الحساب** — لا الأعلى ولا الأدنى. الذيول
    سيولة ستوبات لا مناطق، وإدخالها هنا يخلط الوظيفتين اللتين فرّقهما.
    """
    if tolerance <= 0:
        raise ValueError("السماحية يجب أن تكون موجبة")
    if min_touches < 2:
        raise ValueError("المنطقة تحتاج إغلاقين على الأقل — إغلاق واحد نقطة")

    closes = sorted((c.close, i) for i, c in enumerate(series))
    if not closes:
        return []

    zones: List[KeyZone] = []
    bucket: List[tuple] = [closes[0]]

    for price, idx in closes[1:]:
        if price - bucket[0][0] <= tolerance:
            bucket.append((price, idx))
        else:
            zones.append(_zone_from(bucket))
            bucket = [(price, idx)]
    zones.append(_zone_from(bucket))

    zones = [z for z in zones if z.touches >= min_touches]
    zones.sort(key=lambda z: z.touches, reverse=True)
    if max_zones is not None:
        zones = zones[:max_zones]

    return sorted(zones, key=lambda z: z.bottom)


def _zone_from(bucket: Sequence[tuple]) -> KeyZone:
    prices = [p for p, _ in bucket]
    idx = [i for _, i in bucket]
    return KeyZone(
        bottom=min(prices),
        top=max(prices),
        touches=len(bucket),
        first_index=min(idx),
        last_index=max(idx),
    )


def zone_at(
    zones: Sequence[KeyZone],
    price: float,
    proximity: float = 0.0,
) -> Optional[KeyZone]:
    """
    المنطقة التي يقف السعر عندها — أو None.

    ⭐ **هذه بوابة قراءة الفوليوم.** منصوص:

        «الفوليوم أنا بدي إياك تشوفه **بس بالمنطقة المفتاحية**.
         **بغير المنطقة المفتاحية — ما تشوفه**»

    فبلا منطقة، لا يُقرأ حجم — ولا يُبنى عليه حكم.
    """
    if proximity < 0:
        raise ValueError("القرب لا يكون سالبًا")

    near = [z for z in zones if z.distance_from(price) <= proximity]
    return min(near, key=lambda z: z.distance_from(price)) if near else None


def opposite_zone(
    zones: Sequence[KeyZone],
    price: float,
    direction: Literal["up", "down"],
) -> Optional[KeyZone]:
    """
    المنطقة المفتاحية المقابلة — هدف الصفقة بعد الكسر الوهمي.

        «مجرد الخروج من المنطقة… **بستهدف المنطقة المقابلة فورًا**.
         ليه ما في استهداف تحت؟ لأنه **بعد هو ما كسر تحت**»

    ⇒ الهدف أقرب منطقة في اتجاه الحركة، لا مستوى بعيد مختار بنسبة عائد.
    """
    pool = [z for z in zones if (z.bottom > price if direction == "up" else z.top < price)]
    if not pool:
        return None
    return min(pool, key=lambda z: z.distance_from(price))


def between_zones(
    zones: Sequence[KeyZone],
    low: float,
    high: float,
) -> bool:
    """
    هل السعر يتذبذب **بين منطقتين مفتاحيتين**؟

        «الأكيوميوليشن… بدها تصير **بين منطقتين مفتاحيتين**»

    وهذا يوافق قاعدة «الكونسوليديشن ساحة حرب — إنت ما لك فيها»
    المسجَّلة من وايكوف ٢: النطاق بين منطقتين موضعُ انتظار لا دخول.
    """
    if low > high:
        raise ValueError("الأدنى فوق الأعلى")
    below = any(z.top <= low for z in zones)
    above = any(z.bottom >= high for z in zones)
    return below and above
