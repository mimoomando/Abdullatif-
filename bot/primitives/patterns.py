"""
الأنماط الانعكاسية — الدرس 7 · م2/د3 · ترابط الفريمات.

╔══════════════════════════════════════════════════════════════════╗
║  الشكل وحده لا يكفي.                                             ║
║  النموذج لا يُعتمد إلا بعد **كسر خط العنق** — و«التفعيل» هو الحكم. ║
╚══════════════════════════════════════════════════════════════════╝

    «A recognizable shape is not enough. A reversal model must complete
     and **activate** through its valid neckline/boundary break» (§10)

    «راس الكتفين **شرطه يكسر هالمنطقة** — ما كسرها…
     إيمتى كسرها؟ كسرها هون مع خط العنق»

    «هون اللي فكّر إنها تتاخذ براسه كتفين — شوف السوق كيف ضحك عليك…
     عمل لك راسه كتفين ولكن **ما كمّل الشروط**»

وتسلسل الدخول (ترابط الفريمات):

    نموذج انعكاسي → كسر خط العنق → **فراغ سعري عند الكسر** → إعادة اختبار → دخول
    الوقف: أدنى قاع النموذج بقليل — بمقدار السبريد (م2/د3)

⚠️ **التساوي**: المصدر يقول «90%» للنموذج الثلاثي دون بيان **مقامها**
(التعارض C6). لذلك يُستعمل هنا **فرق سعري مطلق** — معرَّف وقابل للضبط —
ولا تُخترع نسبة لا يُعرف أساسها.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import List, Literal, Optional, Sequence

from ..data import Series
from .fvg import FVG
from .swings import Swing

Kind = Literal[
    "double_bottom", "double_top",
    "triple_bottom", "triple_top",
    "inverse_head_shoulders", "head_shoulders",
]
Direction = Literal["bullish", "bearish"]
State = Literal["forming", "activated", "invalidated"]


@dataclass(frozen=True)
class ReversalPattern:
    kind: Kind
    direction: Direction
    pivots: tuple                # القمم/القيعان المعرِّفة، مرتبة زمنيًا
    neckline: float
    state: State = "forming"
    break_index: Optional[int] = None
    fvg: Optional[FVG] = None

    @property
    def time(self) -> datetime:
        return self.pivots[-1].time

    @property
    def index(self) -> int:
        return self.pivots[-1].index

    @property
    def extreme(self) -> float:
        """أقصى نقطة في النموذج — مرجع الوقف."""
        prices = [p.price for p in self.pivots]
        return min(prices) if self.direction == "bullish" else max(prices)

    @property
    def activated(self) -> bool:
        return self.state == "activated"

    def stop_for(self, buffer: float) -> float:
        """
        م2/د3: «الستوب أدنى قاع… بقليل مشان السبريد».

        الهامش يُحسب بـ`order_block.stop_buffer()` — نفس القاعدة للنموذج
        وللأوردر بلوك، فلا يكون للوقف تعريفان.
        """
        if buffer < 0:
            raise ValueError("الهامش لا يكون سالبًا")
        return self.extreme - buffer if self.direction == "bullish" else self.extreme + buffer


# ─────────────────────────── أدوات ───────────────────────────


def _equal(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def _between(swings: Sequence[Swing], a: Swing, b: Swing, kind: str) -> List[Swing]:
    return [s for s in swings if a.index < s.index < b.index and s.kind == kind]


# ─────────────────────────── الكشف ───────────────────────────


def find_doubles(swings: Sequence[Swing], tolerance: float) -> List[ReversalPattern]:
    """
    قاعان متساويان تقريبًا بينهما قمة ⇒ دبل بتم · والعكس دبل توب.

    خط العنق = القمة الفاصلة (أو القاع الفاصل للنموذج الهابط).
    """
    if tolerance < 0:
        raise ValueError("السماحية لا تكون سالبة")

    out: List[ReversalPattern] = []

    for kind, direction, opposite, pick in (
        ("low", "bullish", "high", max),
        ("high", "bearish", "low", min),
    ):
        pool = [s for s in swings if s.kind == kind]
        for a, b in zip(pool, pool[1:]):
            if not _equal(a.price, b.price, tolerance):
                continue
            mids = _between(swings, a, b, opposite)
            if not mids:
                continue
            neck = pick(m.price for m in mids)
            out.append(
                ReversalPattern(
                    kind=f"double_{'bottom' if direction == 'bullish' else 'top'}",  # type: ignore[arg-type]
                    direction=direction,  # type: ignore[arg-type]
                    pivots=(a, b),
                    neckline=neck,
                )
            )

    return sorted(out, key=lambda p: p.index)


def find_triples(swings: Sequence[Swing], tolerance: float) -> List[ReversalPattern]:
    """
    ثلاثة أطراف متساوية تقريبًا ⇒ نموذج ثلاثي.

    ⚠️ «90% متساوية» من الدرس 7 بلا مقام معروف — يُستعمل الفرق المطلق بدلًا منها.
    """
    if tolerance < 0:
        raise ValueError("السماحية لا تكون سالبة")

    out: List[ReversalPattern] = []

    for kind, direction, opposite, pick in (
        ("low", "bullish", "high", max),
        ("high", "bearish", "low", min),
    ):
        pool = [s for s in swings if s.kind == kind]
        for a, b, c in zip(pool, pool[1:], pool[2:]):
            if not (_equal(a.price, b.price, tolerance) and _equal(b.price, c.price, tolerance)):
                continue
            mids = _between(swings, a, c, opposite)
            if len(mids) < 2:
                continue
            out.append(
                ReversalPattern(
                    kind=f"triple_{'bottom' if direction == 'bullish' else 'top'}",  # type: ignore[arg-type]
                    direction=direction,  # type: ignore[arg-type]
                    pivots=(a, b, c),
                    neckline=pick(m.price for m in mids),
                )
            )

    return sorted(out, key=lambda p: p.index)


def find_head_shoulders(
    swings: Sequence[Swing],
    shoulder_tolerance: float,
) -> List[ReversalPattern]:
    """
    كتف ← رأس أعمق/أعلى ← كتف، والكتفان متساويان تقريبًا.

    خط العنق: يُعتمد **الطرف الأصعب** من النقطتين الفاصلتين — أي الأعلى
    للنموذج الصاعد والأدنى للهابط. اختيار متحفّظ، لأن المصدر يصف خط العنق
    بصريًا ولا يحدد طريقة حسابه.
    """
    if shoulder_tolerance < 0:
        raise ValueError("السماحية لا تكون سالبة")

    out: List[ReversalPattern] = []

    for kind, direction, opposite, deeper, pick in (
        ("low", "bullish", "high", lambda h, s: h < s, max),
        ("high", "bearish", "low", lambda h, s: h > s, min),
    ):
        pool = [s for s in swings if s.kind == kind]
        for ls, head, rs in zip(pool, pool[1:], pool[2:]):
            if not deeper(head.price, ls.price) or not deeper(head.price, rs.price):
                continue
            if not _equal(ls.price, rs.price, shoulder_tolerance):
                continue
            mids = _between(swings, ls, rs, opposite)
            if len(mids) < 2:
                continue
            out.append(
                ReversalPattern(
                    kind="inverse_head_shoulders" if direction == "bullish" else "head_shoulders",
                    direction=direction,  # type: ignore[arg-type]
                    pivots=(ls, head, rs),
                    neckline=pick(m.price for m in mids),
                )
            )

    return sorted(out, key=lambda p: p.index)


def find_all(
    swings: Sequence[Swing],
    tolerance: float,
    shoulder_tolerance: Optional[float] = None,
) -> List[ReversalPattern]:
    st = tolerance if shoulder_tolerance is None else shoulder_tolerance
    return sorted(
        find_doubles(swings, tolerance)
        + find_triples(swings, tolerance)
        + find_head_shoulders(swings, st),
        key=lambda p: p.index,
    )


# ─────────────────────────── التفعيل ───────────────────────────


def activate(
    series: Series,
    patterns: Sequence[ReversalPattern],
    fvgs: Sequence[FVG],
    require_fvg: bool = True,
    use_body: bool = True,
    max_bars: int = 30,
) -> List[ReversalPattern]:
    """
    يفعّل النموذج بكسر خط العنق — **بالجسم لا بالذيل** (الدرس 10).

    و«الكسر بلا فراغ» غير كافٍ (§10 وترابط الفريمات):
        «الكسر… وشكّل فراغ سعري» — فالفراغ دليل الزخم.

    من كسر خط العنق **عكس اتجاهه** قبل التفعيل يُبطَل.
    """
    out: List[ReversalPattern] = []

    for p in patterns:
        state: State = "forming"
        brk: Optional[int] = None
        gap: Optional[FVG] = None

        for i in range(p.index + 1, min(p.index + 1 + max_bars, len(series))):
            c = series[i]
            top = c.body_top if use_body else c.high
            bottom = c.body_bottom if use_body else c.low

            if p.direction == "bullish":
                if bottom < p.extreme:
                    state = "invalidated"
                    break
                crossed = top > p.neckline
            else:
                if top > p.extreme:
                    state = "invalidated"
                    break
                crossed = bottom < p.neckline

            if crossed:
                gap = next(
                    (
                        g
                        for g in fvgs
                        if g.direction == p.direction and i - 1 <= g.index <= i + 2
                    ),
                    None,
                )
                if require_fvg and gap is None:
                    continue
                state, brk = "activated", i
                break

        out.append(replace(p, state=state, break_index=brk, fvg=gap))

    return out


# ─────────────────────────── خطة الدخول ───────────────────────────


@dataclass(frozen=True)
class EntryPlan:
    pattern: ReversalPattern
    entry: float
    stop: float
    reason: str

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)

    def target_for(self, rr: float) -> float:
        d = self.risk * rr
        return self.entry + d if self.pattern.direction == "bullish" else self.entry - d


def entry_plan(pattern: ReversalPattern, spread: float) -> Optional[EntryPlan]:
    """
    الدخول من **إعادة اختبار فراغ الكسر** — لا من الكسر نفسه.

        «مجرد كسر خط العنق أنا كان في عندي نقطة اهتمام للدخول…
         مجرد إعادة الاختبار… كان في عننا دخول»
    """
    if not pattern.activated or pattern.fvg is None:
        return None

    g = pattern.fvg
    entry = g.top if pattern.direction == "bullish" else g.bottom
    return EntryPlan(
        pattern=pattern,
        entry=entry,
        stop=pattern.stop_for(spread),
        reason=(
            f"{pattern.kind} · كسر خط العنق {pattern.neckline} بالجسم · "
            f"فراغ {g.bottom}–{g.top} · الدخول عند إعادة اختباره"
        ),
    )


def activated(patterns: Sequence[ReversalPattern]) -> List[ReversalPattern]:
    return [p for p in patterns if p.activated]
