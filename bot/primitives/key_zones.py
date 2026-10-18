"""
المناطق المفتاحية — درس الدعوم والمقاومات · البثّ المباشر ٢.

╔══════════════════════════════════════════════════════════════════╗
║  ثلاثة خطوط لكل إطار، من **الشمعة المغلقة السابقة**:              ║
║      High  ← الذيل الأعلى                                         ║
║      Low   ← الذيل الأدنى                                         ║
║      Close ← الإغلاق                                              ║
║                                                                   ║
║  والأطر أربعة لا غير: **الشهري · الأسبوعي · اليومي · H4**          ║
╚══════════════════════════════════════════════════════════════════╝

⭐ **لماذا الإغلاق مع الذيول ولا يُغني أحدهما عن الآخر** — منصوص:

    «**أغلب المدرسين والمحللين بيقولوا: أنا بكتفي بس بالهاي واللو،
      الكلوز ما بدي إياه.** أنا حسب خبرتي وتجربتي — **أنا الكلوز
      بيهمني كثير**»

فالإغلاق **إضافةٌ منه** لا بديلًا. غيره يرسم اثنين، وهو يرسم ثلاثة.

⛔ **ولا تُرسم على H1 ولا M15** — منصوص:

    «**ما في أجي أرسم دعم ومقاومة على نطاق ساعة أو ربع ساعة**، لأنه
     هذا من **الهيكل الداخلي وليس الخارجي**. منه نطاق يُحترم بالكامل»

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

Role = Literal["resistance", "support", "none"]
LevelKind = Literal["high", "low", "close"]

# «بنشتغل فيها على الشهري… الأسبوعي… اليومي… الأربع ساعات»
# و«ما في أجي أرسم دعم ومقاومة على نطاق ساعة أو ربع ساعة»
LEVEL_TIMEFRAMES = ("MN1", "W1", "D1", "H4")

#: 🔴 **KZ4** — قاعدةُ تجميع المستويات · `UNDEFINED` · والقائمُ الأوّل
CLUSTER_RULES = ("anchor", "gap")

#: والقائمُ — وهو السلوكُ القديم. ⭐ **ويُقرأ منه لا يُكتب باليد**
#: (درسُ LB1)، ومحروسٌ بأنّه يساوي `params.KEY_ZONE_CLUSTER`.
DEFAULT_CLUSTER = "anchor"

#: ⭐ **KZ3** — الدورُ حين يكون السعرُ **داخلَ** المنطقة.
#: والنصُّ يعطي حالتين ويسكت عن الثالثة.
ROLE_RULES = ("silent", "midpoint", "prior_side")

#: ✅ **أُقرّ 2026-10-18 بقرار المستخدم** — `USER` لا `SOURCE`.
#: **والنصُّ سكت فتسكت**: `none` = [لا يُحكَم]، لا قيمةٌ مُقحَمة.
DEFAULT_ROLE = "silent"

#: 🔶 **KZ1** — سماحيّةُ المنطقة · أُقرّت 2026-10-18 · `USER`.
#: ⚠️ **وجدولُ المسح يخالفها** (الفارقُ الأعلى عند 10$) — والسندُ
#: بنيويٌّ لا جدوليّ، وحدودُه مكتوبةٌ في الدفتر.
DEFAULT_TOLERANCE = 2.0

#: ✅ **KZ2** — وهو القائمُ أصلًا، ولا اختيارَ فيه: مستوًى واحدٌ ليس
#: تجمّعًا. **ومقيسٌ: 2 · 3 · 4 تعطي العددَ نفسَه.**
DEFAULT_MIN_TOUCHES = 2


class TimeframeNotAllowed(ValueError):
    """
    إطار لا تُرسم عليه الدعوم والمقاومات.

    خطأ صريح لا تجاهل صامت: رسمها على H1 يُنتج خطوطًا **تبدو** صحيحة
    وهي من الهيكل الداخلي — وذلك أسوأ من غيابها.
    """


@dataclass(frozen=True)
class Level:
    """خطّ مرجعي واحد من شمعة مغلقة."""

    price: float
    kind: LevelKind
    timeframe: str

    @property
    def label(self) -> str:
        return f"{self.timeframe} {self.kind}".upper()

    def render(self) -> str:
        return f"{self.label} @ {self.price:g}"


def reference_levels(candle, timeframe: str) -> List[Level]:
    """
    الخطوط الثلاثة من **الشمعة المغلقة السابقة** — لا من الجارية.

        «هذا هو الشهر اللي نحن ماشيين عليه — هي الشمعة. فنحن بنيجي على
         **الشمعة اللي قبلها**، يعني **مش هي** اللي بدنا نحدد عليها»

    وهو ما يفعله الجسر أصلًا: الشمعة قيد التكوّن محذوفة دائمًا.

    ⚠️ الخطوط **تثبت حتى تُغلق فترتها**: الشهري لا يتغيّر خلال الشهر،
    والأسبوعي يُحدَّث عند إغلاق الأسبوع. فيُمرَّر هنا آخر شمعة مغلقة
    من ذلك الإطار لا آخر سعر.
    """
    if timeframe not in LEVEL_TIMEFRAMES:
        raise TimeframeNotAllowed(
            f"{timeframe} ليس من أطر الدعوم والمقاومات "
            f"({' · '.join(LEVEL_TIMEFRAMES)}) — "
            "«ما في أجي أرسم دعم ومقاومة على نطاق ساعة أو ربع ساعة»"
        )
    return [
        Level(candle.high, "high", timeframe),
        Level(candle.low, "low", timeframe),
        Level(candle.close, "close", timeframe),
    ]


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

    def role_for(self, price: float, rule: str = DEFAULT_ROLE) -> Role:
        """
        «طالما السعر تحت منها هي مقاومة، بس يصير فوق منها بصير دعم».

        الدور يتبع موضع السعر لا تاريخ المنطقة — ولذلك يُسأل عنه ولا
        يُخزَّن.

        ╔══════════════════════════════════════════════════════════════╗
        ║  ✅✅ **KZ3 — أُقرّ 2026-10-18 بقرار المستخدم** [اقر الثلاثة]. ║
        ║                                                              ║
        ║  فالنصُّ يقول **تحت منها** و**فوق منها**، **ولا يقول شيئًا**  ║
        ║  عن سعرٍ **بينهما**. ⇒ **فالحالتان تُطبَّقان، والثالثةُ**      ║
        ║  **يُمتنَع عنها** — `none` = [لا يُحكَم]، لا قيمةٌ مُقحَمة.     ║
        ║                                                              ║
        ║  ⛔ **والقديمُ `midpoint` اختراعُ حدٍّ لم يقله** — ومن مناطق   ║
        ║  هذا المشروع ما ارتفاعُه دولاراتٌ، **وينقلب حكمُها بفلس**:     ║
        ║  مقيسٌ من سجلّ المستخدم — عند 0.5$ تختلف `midpoint`           ║
        ║  و`prior_side` في **99 من 170**.                              ║
        ║                                                              ║
        ║  ⚠️ **والثمنُ مقيسٌ ويُقال**: عند 2$ ⇒ **575 شمعةً تصمت**     ║
        ║  عندها المنطقة — وهو الأغلب لا الشاذّ.                        ║
        ║                                                              ║
        ║  ⭐ **والقراءتان الأخريان تبقيان مبلوغتين** — فالقرارُ ألّا    ║
        ║  تكونا الافتراض، لا أن تُحذفا (عرفُ `scoped` في `instructor`). ║
        ╚══════════════════════════════════════════════════════════════╝

        `prior_side` يلزمه تاريخٌ لا تحمله المنطقة، فيُحسب في المنادي
        (`replay --key-zones`) ولا يُدَّعى هنا: **طلبُه من هنا يُرفض
        صريحًا** ولا يُرجَع منه `none` صامتًا.
        """
        if rule not in ROLE_RULES:
            raise ValueError(f"role: {rule!r} ليست من {ROLE_RULES}")
        if rule == "prior_side":
            raise ValueError(
                "prior_side يلزمه تاريخُ الأسعار — ويُحسب في المنادي، "
                "ولا تملكه المنطقة. (KZ3)"
            )
        if price < self.bottom:
            return "resistance"
        if price > self.top:
            return "support"
        # ⬅ وهنا بيتُ القصيد: السعرُ **داخلَ** المنطقة.
        if rule == "midpoint":
            return "resistance" if price < self.mid else "support"
        return "none"

    def distance_from(self, price: float) -> float:
        """صفر داخل المنطقة، وإلا المسافة إلى أقرب حافّة."""
        if self.contains(price):
            return 0.0
        return self.bottom - price if price < self.bottom else price - self.top

    def render(self, price: Optional[float] = None) -> str:
        role = ""
        if price is not None:
            # ⭐ KZ3 — و[لا يُحكَم] يُقال ولا يُترجَم إلى أحد الدورين.
            role = {"resistance": " · مقاومة", "support": " · دعم",
                    "none": " · داخلها — ولا دورَ منصوص"}[self.role_for(price)]
        return f"منطقة {self.bottom:g}–{self.top:g} ({self.touches} إغلاق){role}"


def find_key_zones(
    series: Series,
    tolerance: float = DEFAULT_TOLERANCE,
    min_touches: int = DEFAULT_MIN_TOUCHES,
    max_zones: Optional[int] = None,
    kinds: Sequence[LevelKind] = ("high", "low", "close"),
    require_allowed_timeframe: bool = True,
    cluster: str = DEFAULT_CLUSTER,
) -> List[KeyZone]:
    """
    يستخرج المناطق المفتاحية من تاريخ الشموع.

    «بتبيّن معك بالتشارت — بس في حال انت **رجعت لورا بالهيستوري**»

    ⭐ **`kinds` ثلاثة افتراضًا: القمة والقاع والإغلاق.**
    وهذا **تصحيح**: كان التنفيذ الأول يستعمل الإغلاقات وحدها. والمنصوص
    أن غيره يكتفي بالقمة والقاع، **وهو يضيف الإغلاق** — فالإضافة لا
    تُسقط الأصل.

    `tolerance` : كم يبعد مستويان ويظلّان في منطقة واحدة.
        ✅ **KZ1 — أُقرّ 2.0$ يوم 2026-10-18 · `USER` لا `SOURCE`.**
        فالنصُّ لا يعطي مقدارًا، **بل يحيل الأمرَ صراحةً**: «زيدها
        هيدي **على حسب الخبره**» ⇒ فهو سكوتٌ مقصود، لا ثغرة.
        ⚠️⚠️ **وجدولُ المسح يخالف هذه القيمة** — الفارقُ الأعلى عند
        10$ (‎+26.2‎) ومعها ‎−10.5‎. **والسندُ بنيويٌّ لا جدوليّ**:
        عند 10$ وسيطُ العرض 9.41$ ⇒ **أوسعُ من وقفِ البوت كلِّه**،
        والمناطقُ تغطّي ≈273$ من 336$ ⇒ **فـ[داخلها] تقارب [في أيّ
        مكان]**. وعند 2$ الوسيط 1.62$ ⇒ **تبقى أصغرَ من المخاطرة
        فتميّز موضعًا.** ⇒ **وهو رأيٌ مُقَرٌّ، لا رقمٌ فاز بالقياس.**

    `min_touches` : أقلّ عدد مستويات تصنع منطقة.
        ✅ **KZ2 — أُقرّ 2 يوم 2026-10-18، وهو القائمُ أصلًا.**
        مستوًى واحدٌ ليس تجمّعًا. ⭐ **ومقيسٌ: 2 · 3 · 4 تعطي
        العددَ نفسَه** (14 من 14) ⇒ **فلا اختيارَ فيه أصلًا**،
        والسببُ أنّ `kinds` ثلاثة فالشمعةُ الواحدة تعطي ثلاثة.

    `cluster` : **كيف** تُجمَّع المستويات في حزمة.
        🔴 **KZ4 — غير معرَّف، وكُشف 2026-10-18.** والنصُّ لا يذكره
        أصلًا، **وكان اختيارًا صامتًا** حتى سُئل الجدولُ عنه:
          `anchor` القطعُ عند البُعد عن **أوّل** الحزمة  ⬅ القائم
          `gap`    القطعُ عند البُعد عن **سابقه**        ⬅ ومطّردة
        ⇒ انظر الصندوقَ في جسم الدالّة: **الأولى غيرُ مطّردة**
        وثلاثةُ صفوفٍ مأخوذةٍ في السجلّ تُثبتها.

    `require_allowed_timeframe` : يمنع الرسم على H1 وما دونه.
        إطفاؤه للاستكشاف والاختبار التاريخي فقط — لا للقرار.
    """
    if tolerance <= 0:
        raise ValueError("السماحية يجب أن تكون موجبة")
    if min_touches < 2:
        raise ValueError("المنطقة تحتاج مستويين على الأقل — واحد نقطة لا منطقة")
    if not kinds:
        raise ValueError("لا بدّ من نوع مستوى واحد على الأقل")

    if require_allowed_timeframe and series.timeframe not in LEVEL_TIMEFRAMES:
        raise TimeframeNotAllowed(
            f"{series.timeframe} ليس من أطر الدعوم والمقاومات "
            f"({' · '.join(LEVEL_TIMEFRAMES)}) — "
            "«هذا من الهيكل الداخلي وليس من الهيكل الخارجي»"
        )

    if cluster not in CLUSTER_RULES:
        raise ValueError(f"قاعدةُ التجميع من {CLUSTER_RULES}")

    picker = {"high": lambda c: c.high, "low": lambda c: c.low, "close": lambda c: c.close}
    points = sorted(
        (picker[k](c), i)
        for i, c in enumerate(series)
        for k in kinds
    )
    if not points:
        return []

    zones: List[KeyZone] = []
    bucket: List[tuple] = [points[0]]

    for price, idx in points[1:]:
        # ╔══════════════════════════════════════════════════════════╗
        # ║  🔴 **KZ4 — وقاعدةُ التجميع نفسُها غيرُ منصوصة** · كُشفت   ║
        # ║  2026-10-18، **ومقيسةٌ على سجلّ المستخدم لا على مثال.**   ║
        # ║                                                          ║
        # ║  `anchor` تقطع حين يبعد السعرُ عن **أوّل** الحزمة ⇒       ║
        # ║  **فموضعُ القطع يقرّره أدنى سعرٍ في الحزمة**، ويتحرّك      ║
        # ║  بتغيُّر السماحيّة.                                        ║
        # ║  ⛔⛔⛔ **فالتغطيةُ غيرُ مطّردة**: سعرٌ داخلَ منطقةٍ عند      ║
        # ║  10$ يصير **خارجَ كلّ منطقة** عند 20$ — وثلاثةُ صفوفٍ      ║
        # ║  **مأخوذةٍ** في السجلّ تفعلها (09-21 · 09-25 · 09-30).    ║
        # ║                                                          ║
        # ║  `gap` تقطع حين يبعد السعرُ عن **سابقه** ⇒ فالحزمةُ        ║
        # ║  سلسلةٌ متّصلة، **والتوسيعُ يدمج ولا يُفرّق** ⇒ مطّردة.     ║
        # ║                                                          ║
        # ║  ⚠️ **ولا يُنصّ على أيّهما** (القاعدة ①) — والقائمُ        ║
        # ║  `anchor` لأنّه السلوكُ القائم، **لا لأنّه الأصحّ.**        ║
        # ╚══════════════════════════════════════════════════════════╝
        edge = bucket[0][0] if cluster == "anchor" else bucket[-1][0]
        if price - edge <= tolerance:
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
