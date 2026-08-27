"""
مراقب السوق — يسجّل ما فعلته الشموع، لا ما قرّره البوت.

سبب وجوده — اعتراض المدرّب (2026-08-27):

    «النماذج أشكال كثيرة للانعكاس — بالشكل إنت بتشوفها بتعرفها.
     أما عنده هو، هي طريقة حسابية.
     لو **الشكل صح بس الحساب غلط** — بيرفض.
     وإذا **الحساب صح بس الشكل غير مطابق** — بفوت»

الاعتراض صحيح، ويسمّي نوعَي خطأ حقيقيين. وهذه الوحدة تجعلهما **مرئيَّين
ومعدودَين** بدل أن يختفيا:

  ١. تسجّل كل نموذج تكوّن — **حتى الذي لم يُفعَّل**. فإن رفض البوت شكلًا
     صحيحًا، يبقى الشكل مسجَّلًا في سجل السوق ويظهر التناقض.

  ٢. ترصد **الرفض بفارق ضئيل**: ما سقط بفارق صغير عن عتبة رقمية.
     هذه بالضبط حالة «الشكل صح والحساب غلط» — ومرشّحات إعادة المعايرة.

⚠️ المراقب **لا يقرّر ولا يتداول**. يصف ما جرى فقط.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional, Sequence

from .data import Series
from .primitives.fvg import find_fvgs
from .primitives.liquidity import find_sweeps
from .primitives.order_block import find_order_blocks, update_states
from .primitives.patterns import activate, find_all
from .primitives.structure import classify_trend, find_breaks
from .primitives.swings import find_swings

EventKind = Literal[
    "swing", "structure_break", "sweep", "fvg",
    "order_block", "pattern", "notable_candle",
]


@dataclass(frozen=True)
class MarketEvent:
    index: int
    time: datetime
    kind: EventKind
    label: str
    detail: str = ""

    def render(self) -> str:
        tail = f" — {self.detail}" if self.detail else ""
        return f"{self.time:%H:%M}  {self.label}{tail}"


@dataclass(frozen=True)
class NearMiss:
    """
    ما سقط بفارق ضئيل عن عتبة رقمية — «الشكل صح والحساب غلط».

    `margin` = المسافة بين القيمة الفعلية والعتبة. كلما صغرت،
    قوي الاحتمال أن الرفض كان بسبب المعايرة لا بسبب الشكل.
    """

    what: str
    threshold_name: str
    threshold: float
    actual: float
    detail: str

    @property
    def margin(self) -> float:
        return abs(self.actual - self.threshold)

    def render(self) -> str:
        return (
            f"{self.what} · {self.threshold_name}={self.threshold:g} "
            f"والفعلي {self.actual:g} (بفارق {self.margin:g}) — {self.detail}"
        )


@dataclass
class DayObservation:
    timeframe: str
    events: List[MarketEvent] = field(default_factory=list)
    near_misses: List[NearMiss] = field(default_factory=list)
    trend: str = "undefined"

    def of(self, kind: EventKind) -> List[MarketEvent]:
        return [e for e in self.events if e.kind == kind]

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for e in self.events:
            out[e.kind] = out.get(e.kind, 0) + 1
        return out

    def render(self, max_events: int = 25) -> str:
        L = [f"🔭 مراقب {self.timeframe} — الاتجاه: {self.trend}"]

        c = self.counts()
        if c:
            names = {
                "swing": "قمم/قيعان", "structure_break": "كسور هيكل",
                "sweep": "كسح سيولة", "fvg": "فراغات",
                "order_block": "أوردر بلوك", "pattern": "نماذج",
                "notable_candle": "شموع لافتة",
            }
            L.append("   " + " · ".join(f"{names.get(k, k)}: {v}" for k, v in c.items()))

        pats = self.of("pattern")
        if pats:
            L += ["", "   النماذج التي تكوّنت:"]
            L += [f"      {p.render()}" for p in pats[:max_events]]

        if self.near_misses:
            L += ["", "   ⚠️ رُفض بفارق ضئيل — مرشّح لإعادة المعايرة:"]
            L += [f"      {n.render()}" for n in self.near_misses[:max_events]]

        return "\n".join(L)


# ─────────────────────────── الرصد ───────────────────────────


def observe(
    series: Series,
    timeframe: str,
    swing_lookback: int = 1,
    pattern_tolerance: float = 1.5,
    near_miss_factor: float = 2.0,
    notable_range_multiple: float = 2.0,
) -> DayObservation:
    """
    يمسح شموع اليوم ويصف ما جرى.

    `near_miss_factor` : يُعتبر الرفض «بفارق ضئيل» إن كان ضمن هذا المضاعف
                         من السماحية — أي أن الشكل كان قريبًا من القبول.
    """
    if near_miss_factor < 1:
        raise ValueError("مضاعف الفارق الضئيل يجب أن يكون 1 أو أكثر")

    obs = DayObservation(timeframe=timeframe)
    if len(series) < 3:
        return obs

    swings = find_swings(series, swing_lookback)
    obs.trend = classify_trend(swings)

    for s in swings:
        obs.events.append(
            MarketEvent(s.index, s.time, "swing",
                        f"{'قمة' if s.is_high else 'قاع'} {s.price:g}")
        )

    for b in find_breaks(series, swings, use_body=True):
        obs.events.append(
            MarketEvent(b.index, b.time, "structure_break",
                        f"{b.kind} {'صعودًا' if b.direction == 'up' else 'هبوطًا'}",
                        f"كُسر {b.level:g} بإغلاق {b.close:g}")
        )

    sweeps = find_sweeps(series, swings)
    for sw in sweeps:
        obs.events.append(
            MarketEvent(sw.reclaim_index, sw.time, "sweep",
                        f"كسح {'فوق قمة' if sw.side == 'buy_side' else 'تحت قاع'} {sw.level:g}",
                        f"بلغ {sw.extreme:g} ثم استعاد")
        )

    gaps = find_fvgs(series)
    for g in gaps:
        obs.events.append(
            MarketEvent(g.index, g.time, "fvg",
                        f"فراغ {'صاعد' if g.direction == 'bullish' else 'هابط'} "
                        f"{g.bottom:g}–{g.top:g}")
        )

    for ob in update_states(series, find_order_blocks(series, swings, sweeps, gaps)):
        obs.events.append(
            MarketEvent(ob.index, ob.time, "order_block",
                        f"أوردر بلوك {ob.bottom:g}–{ob.top:g}",
                        f"الحالة {ob.state}")
        )

    # ── النماذج: تُسجَّل كلها، حتى غير المفعَّلة ──
    patterns = activate(series, find_all(swings, pattern_tolerance), gaps)
    for p in patterns:
        state_ar = {"forming": "تكوّن ولم يُفعَّل", "activated": "مفعَّل", "invalidated": "أُبطل"}
        obs.events.append(
            MarketEvent(p.index, p.time, "pattern", f"{p.kind} — {state_ar[p.state]}",
                        f"خط العنق {p.neckline:g} · الطرف {p.extreme:g}")
        )

    obs.near_misses = _near_misses(swings, pattern_tolerance, near_miss_factor)
    obs.events += _notable_candles(series, notable_range_multiple)
    obs.events.sort(key=lambda e: (e.index, e.kind))
    return obs


def _near_misses(swings, tolerance: float, factor: float) -> List[NearMiss]:
    """
    أطراف كادت تتساوى ولم تبلغ السماحية.

    هذه حالة **«الشكل صح والحساب غلط»** التي سمّاها المدرّب: العين تراها
    نموذجًا، والعتبة ترفضها.
    """
    out: List[NearMiss] = []
    wide = tolerance * factor

    for kind, label in (("low", "قاعان"), ("high", "قمتان")):
        pool = [s for s in swings if s.kind == kind]
        for a, b in zip(pool, pool[1:]):
            diff = abs(a.price - b.price)
            if tolerance < diff <= wide:
                out.append(
                    NearMiss(
                        what=f"{label} {a.price:g} و {b.price:g}",
                        threshold_name="السماحية",
                        threshold=tolerance,
                        actual=round(diff, 4),
                        detail="كاد يكون نموذجًا مزدوجًا — العين قد تراه، والعتبة رفضته",
                    )
                )
    return out


def _notable_candles(series: Series, multiple: float) -> List[MarketEvent]:
    """شموع مداها يتجاوز متوسط اليوم بمضاعف — مؤشر اندفاع أو خبر."""
    ranges = [c.range_size for c in series]
    avg = sum(ranges) / len(ranges) if ranges else 0.0
    if avg <= 0:
        return []

    out: List[MarketEvent] = []
    for i, c in enumerate(series):
        if c.range_size >= avg * multiple:
            out.append(
                MarketEvent(i, c.time, "notable_candle",
                            f"شمعة مدى {c.range_size:g}",
                            f"{c.range_size / avg:.1f}× متوسط اليوم")
            )
    return out


def contradiction_note(
    obs: DayObservation,
    rejected_reasons: Sequence[str],
) -> Optional[str]:
    """
    يقارن ما رآه السوق بما رفضه البوت — الردّ المباشر على اعتراض المدرّب.

    إن تكوّنت نماذج ولم يدخل البوت، فذلك يستحق النظر: إما أن الشروط
    الأخرى منعت بحق، أو أن المعايرة ضيقة.
    """
    formed = [e for e in obs.of("pattern") if "لم يُفعَّل" in e.label]
    if not formed and not obs.near_misses:
        return None

    bits = []
    if formed:
        bits.append(f"{len(formed)} نموذجًا تكوّن ولم يُفعَّل")
    if obs.near_misses:
        bits.append(f"{len(obs.near_misses)} رفضًا بفارق ضئيل")
    if rejected_reasons:
        bits.append(f"أسباب الرفض: {' · '.join(sorted(set(rejected_reasons))[:3])}")

    return (
        "السوق أنتج أشكالًا لم يعتمدها البوت — " + " · ".join(bits) +
        ". راجعها بعينك: إن كانت أشكالًا صحيحة فالمعايرة ضيقة."
    )
