"""
سلسلة القرار — تجمّع البدائيات في التسلسل الذي وصفه درس ترابط الفريمات.

╔══════════════════════════════════════════════════════════════════╗
║  ١. الهيكل على إطار نقطة الاهتمام                                 ║
║  ٢. نقطة اهتمام **مع اتجاه الهيكل** (فراغ أو أوردر بلوك)          ║
║  ٣. وصول السعر إليها                                             ║
║  ٤. الموقع مقبول من بوابة الـ50%                                  ║
║  ٥. النزول إلى **الإطار المقابل** من جدول الأزواج                  ║
║  ٦. إمّا دخول من اللمس (بشرط التسلسل) أو نموذج انعكاسي مفعَّل      ║
║  ٧. هدف صالح على السيولة الخارجية                                ║
║  ٨. بوابة المخاطرة — حد المراكز                                   ║
╚══════════════════════════════════════════════════════════════════╝

    «ما فيك تيجي من اليومي فورًا تفوت خمس دقائق… في ترابط.
     إذا ما أعطاني من الساعة **ما بفوت**»

كل خطوة تُسجَّل كفحص بدليله ومصدره — فالنتيجة `TradeRationale` جاهزة
للعرض في تيليجرام وللسجل اليومي.

**السلسلة تتوقف عند أول فشل** وتسجّله: معرفة أول مانع أنفع من قائمة
فحوص لا معنى لها بعد سقوط ما قبلها.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional, Sequence

from .data import Series
from .primitives.fibonacci import Impulse, measure
from .primitives.fvg import FVG, find_fvgs
from .primitives.liquidity import find_sweeps
from .primitives.liquidity_map import (
    External,
    Internal,
    classify_external,
    internal_from,
    mark_swept,
    targets_above,
    targets_below,
    usable_internal,
)
from .primitives.order_block import (
    OrderBlock,
    find_order_blocks,
    qualifies_for_direct_touch,
    update_states,
)
from .primitives.patterns import activate, entry_plan, find_all
from .primitives.structure import classify_trend
from .primitives.swings import Swing, find_swings
from .reporting import TradeRationale

Disposition = Literal["taken", "blocked", "rejected"]

MAX_TARGET_RR = 3.0   # «واحد على ثلاثة يكون ماكسيموم» — ترابط الفريمات


@dataclass
class ChainConfig:
    poi_timeframe: str
    confirm_timeframe: str
    spread: float
    swing_lookback: int = 1
    thinning_proximity: float = 2.0
    pattern_tolerance: float = 1.5
    require_containment: bool = False      # D1 — غير محسوم
    open_positions: int = 0
    max_open_positions: int = 1


@dataclass
class ChainResult:
    rationale: TradeRationale
    disposition: Disposition
    note: str = ""
    poi: Optional[Internal] = None
    order_block: Optional[OrderBlock] = None
    targets: Sequence[External] = ()


# ─────────────────────────── أدوات ───────────────────────────


def active_impulse(swings: Sequence[Swing], direction: str) -> Optional[Impulse]:
    """
    الموجة الفعّالة التي تُقاس عليها بوابة الـ50%.

    الدرس 6: تُقاس **الموجة كاملة** من القاع الحاكم إلى القمة — لا تذبذبًا داخليًا.
    """
    lows = [s for s in swings if s.is_low]
    highs = [s for s in swings if s.is_high]
    if not lows or not highs:
        return None
    lo, hi = lows[-1].price, highs[-1].price
    if hi <= lo:
        return None
    return measure(lo, hi, "bullish" if direction == "bullish" else "bearish")


def _price_reached(series: Series, zone: Internal, since: int) -> Optional[int]:
    for i in range(max(since, 0), len(series)):
        c = series[i]
        if c.low <= zone.top and c.high >= zone.bottom:
            return i
    return None


def _capped(entry: float, stop: float, targets: Sequence[External], direction: str) -> List[External]:
    """يستبعد الأهداف التي تتجاوز 1:3 — «واحد على ثلاثة يكون ماكسيموم»."""
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    return [t for t in targets if abs(t.price - entry) / risk <= MAX_TARGET_RR + 1e-6]


# ─────────────────────────── السلسلة ───────────────────────────


def evaluate(
    poi_series: Series,
    confirm_series: Series,
    cfg: ChainConfig,
    now: Optional[datetime] = None,
) -> ChainResult:
    """
    يشغّل السلسلة كاملة ويرجع النتيجة بأسبابها.

    `poi_series`     : شموع إطار نقطة الاهتمام (H4 · H1 · M15)
    `confirm_series` : شموع الإطار المقابل    (M30 · M5 · M3)
    """
    stamp = now or (poi_series.last_closed().time if len(poi_series) else datetime.now())
    r = TradeRationale(
        symbol=poi_series.symbol,
        direction="buy",
        poi_timeframe=cfg.poi_timeframe,
        confirm_timeframe=cfg.confirm_timeframe,
        detected_at=stamp,
    )

    def reject(note: str = "") -> ChainResult:
        return ChainResult(r, "rejected", note)

    # ── ١. الهيكل ──
    swings = find_swings(poi_series, cfg.swing_lookback)
    structure = classify_trend(swings)
    if structure == "undefined":
        r.add("الهيكل محدد", False, "لا قمم/قيعان كافية للحكم", "الدرس 9")
        return reject("الهيكل غير محدد")

    r.direction = "buy" if structure == "bullish" else "sell"
    r.add(
        "الهيكل محدد",
        True,
        f"{structure} — آخر قمة {[s.price for s in swings if s.is_high][-1]} · "
        f"آخر قاع {[s.price for s in swings if s.is_low][-1]}",
        "الدرس 9",
    )

    # ── ٢. نقطة اهتمام مع الاتجاه ──
    gaps = find_fvgs(poi_series)
    sweeps = find_sweeps(poi_series, swings)
    blocks = update_states(poi_series, find_order_blocks(poi_series, swings, sweeps, gaps))
    zones = usable_internal(internal_from(gaps, blocks), structure)

    if not zones:
        r.add(
            "نقطة اهتمام مع الاتجاه",
            False,
            f"لا فراغ ولا أوردر بلوك باتجاه {structure} — «ما بيتخيّط»",
            "ترابط الفريمات",
        )
        return reject("لا نقطة اهتمام")

    poi = zones[-1]
    r.add(
        "نقطة اهتمام مع الاتجاه",
        True,
        f"{poi.kind} {poi.bottom}–{poi.top} · المنتصف {poi.midpoint}",
        "السيولة الداخلية · ترابط الفريمات",
    )

    # ── ٣. وصول السعر ──
    reached = _price_reached(poi_series, poi, poi.index + 1)
    if reached is None:
        r.add("السعر وصل إليها", False, "لم يصل بعد", "م2/د3")
        return reject("لم يصل السعر لنقطة الاهتمام")
    r.add("السعر وصل إليها", True, f"عند الشمعة {reached}", "م2/د3")

    # ── ٤. بوابة الـ50% ──
    impulse = active_impulse(swings, structure)
    entry_ref = poi.top if structure == "bullish" else poi.bottom
    if impulse is not None:
        expensive = impulse.is_expensive(entry_ref, impulse.direction)
        r.add(
            "الموقع تحت بوابة الـ50%",
            not expensive,
            f"المنتصف {impulse.midpoint:.2f} والدخول المرجعي {entry_ref:.2f}",
            "الدرس 14 · C3",
        )
        if expensive:
            return reject("الدخول غالٍ")
    else:
        r.add("الموقع تحت بوابة الـ50%", True, "لا موجة مقاسة — البوابة غير مطبَّقة", "الدرس 14")

    # ── ٥/٦. التأكيد: لمس مباشر أو نموذج مفعَّل ──
    nested = [g for g in gaps if g.direction == structure]
    direct: Optional[OrderBlock] = None

    for ob in blocks:
        if ob.direction != structure or ob.state == "failed":
            continue
        chk = qualifies_for_direct_touch(
            ob, nested,
            impulse_midpoint=impulse.midpoint if impulse else None,
            require_containment=cfg.require_containment,
        )
        if chk.eligible:
            direct, direct_reasons = ob, chk.reasons
            break

    if direct is not None:
        r.add("دخول من مجرد اللمس", True, " · ".join(direct_reasons[:2]), "م2/د3")
        entry = direct.top if structure == "bullish" else direct.bottom
        stop = direct.stop_for(cfg.spread)
        stop_why = f"أدنى الأوردر بلوك {direct.bottom} − السبريد {cfg.spread}"
    else:
        c_swings = find_swings(confirm_series, cfg.swing_lookback)
        c_gaps = find_fvgs(confirm_series)
        patterns = [
            p
            for p in activate(confirm_series, find_all(c_swings, cfg.pattern_tolerance), c_gaps)
            if p.activated and p.direction == structure
        ]
        if not patterns:
            r.add(
                "نموذج انعكاسي مفعَّل",
                False,
                f"لا نموذج مفعَّل على {cfg.confirm_timeframe} — «إذا ما أعطاني ما بفوت»",
                "ترابط الفريمات",
            )
            return reject("لا تأكيد على الإطار المقابل")

        pat = patterns[-1]
        plan = entry_plan(pat, cfg.spread)
        if plan is None:
            r.add("خطة دخول من الريتست", False, "النموذج مفعَّل بلا فراغ كسر", "§10")
            return reject("لا فراغ عند الكسر")

        r.add(
            "نموذج انعكاسي مفعَّل",
            True,
            f"{pat.kind} · كسر خط العنق {pat.neckline} بالجسم · فراغ {pat.fvg.bottom}–{pat.fvg.top}",
            "الدرس 7 · ترابط الفريمات",
        )
        entry, stop, stop_why = plan.entry, plan.stop, f"طرف النموذج {pat.extreme} − السبريد {cfg.spread}"

    # ── ٧. الأهداف ──
    ext = mark_swept(poi_series, classify_external(swings, cfg.poi_timeframe, cfg.thinning_proximity))
    pool = targets_above(ext, entry) if structure == "bullish" else targets_below(ext, entry)
    pool = _capped(entry, stop, pool, structure)

    if not pool:
        r.add(
            "هدف على السيولة الخارجية",
            False,
            "لا قمة/قاع صالح ضمن حد 1:3 — والداخلية ليست هدفًا",
            "السيولة الخارجية",
        )
        return reject("لا هدف صالح")

    r.add(
        "هدف على السيولة الخارجية",
        True,
        " · ".join(f"{t.price:.2f} ({t.strength})" for t in pool[:3]),
        "السيولة الخارجية · «أول قمة آمن»",
    )

    r.entry, r.stop = entry, stop
    r.stop_reason = stop_why
    r.targets = [t.price for t in pool[:3]]
    r.target_reason = "قمم/قيعان سابقة — سيولة خارجية · الأقرب أولًا"

    # ── ٨. بوابة المخاطرة ──
    if cfg.open_positions >= cfg.max_open_positions:
        r.blocked_reason = (
            f"مركز مفتوح ({cfg.open_positions}/{cfg.max_open_positions}) — تنبيه لا أمر"
        )
        return ChainResult(r, "blocked", r.blocked_reason, poi, direct, pool)

    return ChainResult(r, "taken", "", poi, direct, pool)
