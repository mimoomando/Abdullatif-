"""
خريطة السيولة — سلسلة دروس السيولة الثلاثة.

╔══════════════════════════════════════════════════════════════════╗
║  السيولة الداخلية = الفراغات السعرية + الأوردر بلوك              ║
║  السيولة الخارجية = القمم والقيعان                               ║
║                                                                  ║
║  الداخلية موضع **دخول** — واستهدافها خطأ منصوص عليه.              ║
║  الخارجية هي **الهدف**.                                          ║
╚══════════════════════════════════════════════════════════════════╝

    «السيولة الداخلية ما تكمن فقط في الفراغ السعري، ولكن **الأوردر بلوك
     هو نفسه سيولة داخلية**… والسيولة الخارجية تكمن **بالقمم والقيعان**»

    «بدي أستهدف السيولة الداخلية — **خطأ**»

الدورة:  اكسبانشن → سيولة داخلية → انطلاق → سيولة خارجية

    «أخذ انترنال، راح ضرب اكسترنال — إذًا هو بمساره، بعده صاعد»
    «أي منطقة في حال بياخذ سيولة داخلية ما بيرجع بيضرب سيولة خارجية —
     فهو **احتمال لتغيّر الهيكل**»
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Literal, Optional, Sequence

from ..data import Series
from .fvg import FVG
from .order_block import OrderBlock
from .swings import Swing

Tier = Literal["major", "medium", "light", "negligible"]
Strength = Literal["strong", "thinned"]
Kind = Literal["fvg", "order_block"]
CycleState = Literal["continuation", "possible_structure_change", "pending"]


# درس «السيولة الضخمة والمخففة» — التصنيف بالإطار الزمني
TIER_BY_TIMEFRAME = {
    "MN1": "major", "W1": "major", "D1": "major",
    "H4": "medium", "H2": "medium", "H1": "medium",
    "M30": "light", "M15": "light",
    "M5": "negligible", "M3": "negligible", "M1": "negligible",
}


def tier_for(timeframe: str) -> Tier:
    """«سيولة منعدمة بتكون مجرد ردّ لضرب ستوب لحظي على الدقيقة والخمس دقائق»."""
    try:
        return TIER_BY_TIMEFRAME[timeframe]  # type: ignore[return-value]
    except KeyError:
        raise ValueError(f"إطار زمني غير معروف: {timeframe}")


# ─────────────────────────── السيولة الخارجية ───────────────────────────


@dataclass(frozen=True)
class External:
    swing: Swing
    timeframe: str
    tier: Tier
    strength: Strength
    protected: bool = False
    swept: bool = False

    @property
    def price(self) -> float:
        return self.swing.price

    @property
    def is_target(self) -> bool:
        """
        المحمية ليست هدفًا — «هذا القاع نظّف كل السيولة السابقة،
        ومرتد هو أصلًا من أوردر بلوك».
        والمكسوحة استُهلكت.
        """
        return not self.protected and not self.swept


def classify_external(
    swings: Sequence[Swing],
    timeframe: str,
    proximity: float,
) -> List[External]:
    """
    يصنّف كل قمة/قاع: قوية أم مخففة.

        «لما بيكون في **قمة ثانية مقرّبة لها** بتكون سيولة مستهدفة مخففة.
         أما لما بتكون **لحالها** فهي سيولة قوية، وعند ضربها رح يصير
         انعكاس كثير قوي»

    `proximity` غير معرّف في المصدر (L12) — يأتي من params ويُضبط بالاختبار.
    """
    if proximity < 0:
        raise ValueError("مسافة القرب لا تكون سالبة")

    tier = tier_for(timeframe)
    out: List[External] = []

    for s in swings:
        peers = [
            o
            for o in swings
            if o is not s and o.kind == s.kind and abs(o.price - s.price) <= proximity
        ]
        out.append(
            External(
                swing=s,
                timeframe=timeframe,
                tier=tier,
                strength="thinned" if peers else "strong",
            )
        )

    return out


def mark_protected(
    externals: Sequence[External],
    order_blocks: Sequence[OrderBlock],
    swept_levels: Sequence[float],
    tolerance: float = 0.0,
) -> List[External]:
    """
    يعلّم السيولة المحمية.

        «قاع ساحب كل اللي ما قبله… **ومرتد هو أصلًا من أوردر بلوك**»

    شرطان معًا:
      ١. المستوى نفسه كسح ما قبله  (يُمرَّر في swept_levels)
      ٢. يقع داخل أوردر بلوك بنفس الاتجاه
    """
    out: List[External] = []

    for e in externals:
        cleaned = any(abs(e.price - lv) <= tolerance for lv in swept_levels)
        want: str = "bullish" if e.swing.is_low else "bearish"
        from_ob = any(
            ob.direction == want and ob.bottom - tolerance <= e.price <= ob.top + tolerance
            for ob in order_blocks
        )
        out.append(replace(e, protected=cleaned and from_ob))

    return out


def mark_swept(series: Series, externals: Sequence[External]) -> List[External]:
    """يعلّم المستويات التي تجاوزها السعر بعد تكوّنها — استُهلكت كأهداف."""
    out: List[External] = []
    for e in externals:
        hit = any(
            (series[i].high > e.price) if e.swing.is_high else (series[i].low < e.price)
            for i in range(e.swing.index + 1, len(series))
        )
        out.append(replace(e, swept=hit))
    return out


def targets_above(externals: Sequence[External], price: float) -> List[External]:
    """أهداف الشراء مرتّبة من الأقرب — «أول قمة آمن»."""
    hits = [e for e in externals if e.is_target and e.swing.is_high and e.price > price]
    return sorted(hits, key=lambda e: e.price)


def targets_below(externals: Sequence[External], price: float) -> List[External]:
    hits = [e for e in externals if e.is_target and e.swing.is_low and e.price < price]
    return sorted(hits, key=lambda e: e.price, reverse=True)


# ─────────────────────────── السيولة الداخلية ───────────────────────────


@dataclass(frozen=True)
class Internal:
    kind: Kind
    direction: str
    top: float
    bottom: float
    index: int

    @property
    def midpoint(self) -> float:
        """«ليه بنقول خط المنتصف؟ لأنه هو **متوسط الفراغ**»"""
        return (self.top + self.bottom) / 2.0

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top


def internal_from(
    fvgs: Sequence[FVG] = (),
    order_blocks: Sequence[OrderBlock] = (),
) -> List[Internal]:
    """يجمع الفراغات والأوردر بلوك في قائمة سيولة داخلية واحدة."""
    out = [Internal("fvg", g.direction, g.top, g.bottom, g.index) for g in fvgs]
    out += [
        Internal("order_block", ob.direction, ob.top, ob.bottom, ob.index)
        for ob in order_blocks
    ]
    out.sort(key=lambda z: z.index)
    return out


def usable_internal(zones: Sequence[Internal], structure: str) -> List[Internal]:
    """
    بوابة استمرارية الهيكل — درس ترابط الفريمات:

        «طالما توجهي صاعد… ليه بدي أتعامل مع الفراغات السعرية **السلبية**؟
         أنا بدي أتعامل مع الفراغات **الإيجابية**، لأنه توجهي صعودي مش هبوطي»
        «إنت مفكر إنه بدك تخيّط الشارت؟ **ما بيتخيّط**»
    """
    if structure not in ("bullish", "bearish"):
        return []
    return [z for z in zones if z.direction == structure]


# ─────────────────────────── الدورة ───────────────────────────


@dataclass(frozen=True)
class CycleReading:
    state: CycleState
    internal_index: Optional[int]
    external_index: Optional[int]
    detail: str


def read_cycle(
    series: Series,
    zone: Internal,
    externals: Sequence[External],
    direction: str,
    max_bars_to_external: int,
    start: Optional[int] = None,
) -> CycleReading:
    """
    يقرأ الدورة: هل أخذ السعر السيولة الداخلية ثم بلغ الخارجية؟

        بلغ الخارجية        ⇒ الاتجاه مستمر
        لم يبلغها في المهلة ⇒ **احتمال تغيّر الهيكل**

    `max_bars_to_external` غير معرّف في المصدر (L6).
    """
    begin = (zone.index + 1) if start is None else start

    touched = next(
        (
            i
            for i in range(begin, len(series))
            if series[i].low <= zone.top and series[i].high >= zone.bottom
        ),
        None,
    )
    if touched is None:
        return CycleReading("pending", None, None, "لم يصل السعر إلى السيولة الداخلية بعد")

    pool = [e for e in externals if e.is_target and (e.swing.is_high if direction == "bullish" else e.swing.is_low)]
    if not pool:
        return CycleReading("pending", touched, None, "لا سيولة خارجية صالحة كهدف")

    nearest = min(pool, key=lambda e: abs(e.price - series[touched].close))
    deadline = min(touched + max_bars_to_external, len(series))

    for i in range(touched, deadline):
        c = series[i]
        reached = c.high >= nearest.price if direction == "bullish" else c.low <= nearest.price
        if reached:
            return CycleReading(
                "continuation", touched, i,
                f"أخذ الداخلية عند {i - touched} شمعة ثم بلغ الخارجية {nearest.price} — الاتجاه مستمر",
            )

    if deadline >= len(series):
        return CycleReading(
            "pending", touched, None,
            f"أخذ الداخلية ولم يبلغ {nearest.price} بعد — المهلة لم تنتهِ",
        )

    return CycleReading(
        "possible_structure_change", touched, None,
        f"أخذ الداخلية ولم يبلغ الخارجية {nearest.price} خلال {max_bars_to_external} شمعة "
        "— احتمال تغيّر الهيكل",
    )
