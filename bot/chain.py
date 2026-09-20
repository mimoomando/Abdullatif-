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
from .primitives.fvg import FVG, find_bprs, find_fvgs, find_inversions
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
from .primitives.harmonic_entry import HarmonicEntry, best as best_harmonic
from .primitives.order_block import (
    OrderBlock,
    find_order_blocks,
    qualifies_for_direct_touch,
    stop_buffer,
    update_states,
)
from .primitives.line_chart import rejected as line_rejected, survivors
from .primitives.patterns import activate, entry_plan, find_all
from .primitives.refine import refine
from .primitives.ob_lifecycle import trace_all
from .primitives.structure import classify_trend, describe_trend
from .primitives.swings import Swing, find_swings
from .reporting import TradeRationale
from .trail import ladder as trail_ladder

Disposition = Literal["taken", "blocked", "rejected"]

MAX_TARGET_RR = 3.0   # «واحد على ثلاثة يكون ماكسيموم» — ترابط الفريمات

# ⭐ عددُ الأهداف المعلَنة — **منطوقٌ بالعدّ** (الأوردر بلوك ج2 ≈19:25):
#
#     «الأهداف تبعت الأوردر بلوك هي القيعان السابقة — واحد، اثنين،
#      ثلاثة، **أربعة**. يعني أربع أهداف. بدك الخامس؟ **لا، ما بيمشي
#      الحال**»
#
# ⛔ وكان هنا `3` عاريًا بلا مصدر. فالأربعة **تصحيحُ رقمٍ مخترَع**، لا
#    توسيعُ سقف.
MAX_TARGETS = 4


@dataclass
class ChainConfig:
    poi_timeframe: str
    confirm_timeframe: str
    spread: float
    swing_lookback: int = 1
    thinning_proximity: float = 2.0
    pattern_tolerance: float = 1.5
    require_containment: bool = False      # D1 — غير محسوم
    # ⭐ **رُفع حدّ المراكز** (المستخدم 2026-09-20): «لا أريد حدًّا».
    #    `None` = بلا سقف. وما يحكم الآن هو الدولار لا العدد — انظر
    #    `daily_loss_limit` أدناه.
    open_positions: int = 0
    max_open_positions: Optional[int] = None

    # ⛔ **سقفُ خسارة اليوم — 100$** (المستخدم 2026-09-20). وبلغَه ⇒ لا
    #    إعداد جديد يُعلَن بقيّته. و`daily_loss` حصيلةُ اليوم بالدولار،
    #    يمرّرها المشغّل من قرارات اليوم نفسِها مصحَّحةً بـ`replay`.
    #    ⚠️ وهي **موجبةٌ ربحًا وسالبةٌ خسارة** — فالبلوغ عند ‎−100.
    daily_loss: float = 0.0
    daily_loss_limit: Optional[float] = 100.0

    # T2 — «درجتان» و«الدولار كاملًا» (المستخدم 2026-08-27) ⇒ هامش 2.00
    stop_degrees: Optional[float] = 2.0
    degree_value: Optional[float] = 1.00

    # البثّ المباشر: بوابة الـ50% تُقاس بالإغلاق لا باللمس
    gate_by_close: bool = True

    # ⭐⭐ اختبار الخطّ — «هيدا مش دبل بتم» (البثّ ٣ ≈20:05).
    # النموذج الذي تصنعه الذيول وحدها يُردّ. اعتراضٌ لا استبدال.
    line_chart_veto: bool = True

    # ⭐⭐ تنقيح الدخول داخل المنطقة — أعلى بندٍ قِسنا كلفته بالدولار.
    # «بدون تأكيد ما بنصح» (البثّ ٣ ≈1:10:26). ويُعطَّل بسطر.
    refine_entry: bool = True
    # سماحية احتواء طرف النموذج في المنطقة. صفرٌ = داخلها تمامًا.
    refine_tolerance: float = 0.0
    # عتبة «الأوردر بلوك الكبير» ⇒ الدخول من منتصفه. None = غير مطبَّقة
    # (البثّ ٣ ≈14:41 — «كبير» بلا رقم).
    ob_large_threshold: Optional[float] = None

    # ⭐⭐ الهارمونيك — **تأكيدٌ على الإطار المقابل، لا استراتيجيّة موازية**:
    #
    #     «عندك نقطة اهتمام من ربع ساعة، فأنا على الدقيقة أو ثلاث
    #      دقائق باخذ موجة، **نقطة انعكاس على الهارمونيك، منها بأكّد**»
    #
    # فلا يولّد نقطةَ اهتمام ولا يغيّر هدفًا — يعطي الدخول ووقفَه حين
    # يقع D داخل المنطقة. انظر `harmonic_entry.py`.
    #
    # ⛔⛔ **وهو مُطفَأ — قِيس فخسر** (09-14…15 على شموع المنصّة):
    #
    #     بلا هارمونيك   5 إعدادات · 2 هدف · 2 وقف · 1 ملتبس   **+3.94$**
    #     مع الهارمونيك  4 إعدادات · 1 هدف · 2 وقف · 1 ملتبس  **−17.36$**
    #     ────────────────────────────────────────────────────────────
    #     الفرق                                        **−21.30$** · وإعدادٌ أقلّ
    #
    # ⚠️ **وقلتُ إنّ أثرَه «مُضافٌ لا مُزيح» — وكان ذلك خطأً**، كشفه
    # العدد: 5 ⇐ 4. فهو في مسار اللمس المباشر **يستبدل** الدخول والوقف
    # حين يعجز التنقيح الكلاسيكيّ، ووقفُه الصلب درجتان خلف D فيتّسع —
    # فيتجاوز سقفَ الـ20$ أحيانًا، فيسقط الإعدادُ كلُّه. أزاح رابحًا.
    #
    # ⇒ فيبقى مبنيًّا مختبَرًا **مطفأً**، كـ`structural.py`، حتى يُصلَح
    # الاستبدالُ ويُقاس من جديد. انظر
    # `knowledge/analyses/2026-09-20-harmonic-wired.md`.
    harmonic_enabled: bool = False
    # سماحية وقوع D داخل المنطقة. صفرٌ = داخلها تمامًا.
    harmonic_tolerance: float = 0.0

    # ⭐ نوعا نقاط الاهتمام من البثّ ٣ — ويُعطَّل أيٌّ منهما بسطر.
    # ولماذا مفتوحان؟ لأن نصّه فيهما صريح، وكلاهما يلزمه **تأكيد من
    # الإطار المقابل** فلا يدخل من مجرّد اللمس.
    bpr_enabled: bool = True
    inversion_enabled: bool = True

    # ⭐ سقفُ الأهداف — «واحد، اثنين، ثلاثة، **أربعة**… بدك الخامس؟
    #    **لا، ما بيمشي الحال**» (الأوردر بلوك ج2 ≈19:25). وكان `3`
    #    عاريًا هنا، فهذا تصحيحُ رقمٍ مخترَع لا توسيعُ سقف.
    max_targets: int = MAX_TARGETS

    # ⭐ سقف مسافة الوقف — **مستخرَج من أسبوع الملاحظة**، لا مخترَع.
    # انظر `max_stop` أدناه. ويُعطَّل بوضع None.
    max_stop: Optional[float] = 20.0
    # سبريد شاذّ يوقف التداول. لم يقع هذا الأسبوع (أعلى سبريد عند
    # إعداد مقبول 0.68$) — فهو تأمينٌ بلا كلفة مقاسة.
    max_spread: Optional[float] = 2.0

    @property
    def stop_buffer(self) -> float:
        """
        هامش الوقف الفعلي — 2 درجة × 1.00 = **2.00 دولار** افتراضًا.

        بسبريد ذهب نموذجي (0.20–0.40) تحكم الدرجتان دائمًا، والسبريد
        أرضية لا تُبلَغ إلا في اتساع شاذّ — وحينها يتّسع الوقف معه.
        """
        return stop_buffer(self.spread, self.stop_degrees, self.degree_value)


@dataclass
class ChainResult:
    rationale: TradeRationale
    disposition: Disposition
    note: str = ""
    poi: Optional[Internal] = None
    order_block: Optional[OrderBlock] = None
    targets: Sequence[External] = ()


# ─────────────────────────── أدوات ───────────────────────────


def _buffer_why(cfg: "ChainConfig") -> str:
    """يشرح في السجل من أين جاء الهامش — رقم بلا مصدر لا يُراجَع."""
    if cfg.stop_degrees is None or cfg.degree_value is None:
        return f"السبريد الحي {cfg.spread:g} — قيمة الدرجة معلّقة"
    span = cfg.stop_degrees * cfg.degree_value
    if span >= cfg.spread:
        return f"{cfg.stop_degrees:g} درجة × {cfg.degree_value:g}"
    return f"السبريد {cfg.spread:g} فاق {cfg.stop_degrees:g} درجة — الأرضية تحكم"


def _patterns_on_line(series: Series, swings: Sequence[Swing],
                      cfg: "ChainConfig") -> List:
    """
    نماذج الإطار المقابل بعد عرضها على **خطّ الإغلاقات**.

    ⭐ «هيدا مش دبل بتم — شوفوا ع الشموع، **هيدا قاع واحد**». فالنموذج
    يُكتشَف بالذيول (والمناطق تُرسم بها، وذلك مقيسٌ من شاشته)، ثم
    يُعرَض على الخطّ: ما لم يبقَ نموذجًا عليه رُدَّ.
    """
    found = find_all(swings, cfg.pattern_tolerance)
    if not cfg.line_chart_veto:
        return found
    return survivors(series, found, cfg.pattern_tolerance, cfg.swing_lookback)


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

    # ── ٠. سبريد شاذّ ──
    #
    # لم يقع هذا الأسبوع: أعلى سبريد عند إعدادٍ **مقبول** كان 0.68$،
    # وبلغ 6.87$ في ثلاثة قرارات — كلها عند تدوير اليوم ومرفوضة
    # لأسباب أخرى. فالحارس تأمينٌ لم تُقَس كلفته، لكنّ ضرره مقيس:
    # `stop_buffer = max(2.00, spread)` ⇒ سبريد 6.87 يفتح وقفًا بـ6.87$.
    if cfg.max_spread is not None and cfg.spread > cfg.max_spread:
        r.add(
            "السبريد طبيعي",
            False,
            f"{cfg.spread:.2f}$ > {cfg.max_spread:g}$ — اتساع شاذّ يوسّع الوقف معه",
            "أسبوع 09-07…11",
        )
        return reject("سبريد شاذّ")

    # ── ١. الهيكل ──
    swings = find_swings(poi_series, cfg.swing_lookback)
    structure, why = describe_trend(swings)
    if structure == "undefined":
        r.add("الهيكل محدد", False, why, "الدرس 9")
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

    # ⭐ البثّ ٣ — «إذا في حال انضربت راح تروح نهائي»
    #
    # البروبلشن آخر مرحلة، وضربُها يقتل الأمّ. فالمنطقة الميّتة تُسقط
    # **قبل** أي فحصٍ آخر: تقييدٌ خالص، لا يزيد إعدادًا بل يمنع
    # إعدادًا على منطقةٍ استُنفدت.
    cycles = trace_all(poi_series, blocks, swings)
    dead = {c.parent.index for c in cycles if c.dead}
    if dead:
        blocks = [b for b in blocks if b.index not in dead]

    # ⭐⭐ ونوعان جديدان من نقاط الاهتمام — البثّ ٣.
    #
    # ⚠️ **ولا يدخل أيٌّ منهما من مجرّد اللمس.** فحصُ اللمس المباشر
    # يشترط أوردر بلوك، فيسقط هذان إلى مسار «نموذج انعكاسي مفعَّل»
    # على الإطار المقابل — وهو ما نصّ عليه للمنعكسة حرفيًّا:
    # «أنا منها بفوت شراء **مع تأكيد من الفريم المرتبط**».
    bprs = find_bprs(gaps) if cfg.bpr_enabled else []
    inversions = (
        find_inversions(poi_series, gaps, structure)
        if cfg.inversion_enabled else []
    )

    zones = usable_internal(
        internal_from(gaps, blocks, bprs, inversions), structure)

    if not zones:
        r.add(
            "نقطة اهتمام مع الاتجاه",
            False,
            f"لا فراغ ولا أوردر بلوك باتجاه {structure} — «ما بيتخيّط»"
            + (f" · وأُسقطت {len(dead)} منطقة ميّتة" if dead else ""),
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
        # البثّ المباشر: «بس **ما يغلق** — هي مش غالق فوق الـ50%»
        # ⇒ الحكم على **إغلاق** آخر شمعة، لا على مستوى مجرَّد.
        # الذيل فوق المنتصف مقبول — كقاعدته العامة: الذيل يستكشف
        # والإغلاق يقرّر.
        last = poi_series.last_closed()
        if cfg.gate_by_close and last is not None:
            expensive = impulse.closed_beyond_midpoint(last, impulse.direction)
            how = f"إغلاق {last.close:.2f}"
        else:
            expensive = impulse.is_expensive(entry_ref, impulse.direction)
            how = f"الدخول المرجعي {entry_ref:.2f}"
        r.add(
            "الموقع تحت بوابة الـ50%",
            not expensive,
            f"المنتصف {impulse.midpoint:.2f} و{how}",
            "الدرس 14 · C3 · البثّ المباشر",
        )
        if expensive:
            return reject("الدخول غالٍ")
    else:
        r.add("الموقع تحت بوابة الـ50%", True, "لا موجة مقاسة — البوابة غير مطبَّقة", "الدرس 14")

    # ── ٥/٦. التأكيد: لمس مباشر أو نموذج مفعَّل ──
    nested = [g for g in gaps if g.direction == structure]
    direct: Optional[OrderBlock] = None

    for ob in blocks:
        # أول لمسة لا غير — «اللمسة الثانية أو الثالثة ما بنتعامل معها»
        if ob.direction != structure or ob.state in ("failed", "mitigated"):
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
        buf = cfg.stop_buffer
        entry = direct.entry_for(cfg.ob_large_threshold)
        stop = direct.stop_for(buf)
        stop_why = f"أدنى الأوردر بلوك {direct.bottom} − هامش {buf:g} ({_buffer_why(cfg)})"

        # ── ٦½. تنقيح الدخول **داخل** المنطقة ──
        #
        # ⭐⭐⭐ البثّ ٣ (≈1:10:26) — نصٌّ فاصل:
        #
        #     «هي الارتداد من الأوردر بلوك العالم بتفوت، في أغلبيتها
        #      بتفوت من الأوردر بلوك بيكون **الستوب تبعها قاع الأوردر
        #      بلوك**، **ولكن أنا بدون تأكيد ما بنصح**»
        #
        # فالدخول من حدّ المنطقة بوقفٍ عند قاعها كاملًا هو ما يفعله
        # «العالم» — وهو ما لا ينصح به بلا تأكيد. وطريقتُه: نموذجٌ
        # انعكاسيّ **داخل** المنطقة على الإطار المقابل، والوقف من
        # **قاع النموذج** لا من قاع المنطقة (ترابط الفريمات §3/§8).
        #
        # 🔴 وكلفة غيابه مقيسة: وسيط وقف البوت في أسبوع 09-07…11 كان
        # **10.91$** وأقصاه **74.77$**، وأرقامه هو **1–3.5$**.
        if cfg.refine_entry:
            c_swings_r = find_swings(confirm_series, cfg.swing_lookback)
            c_gaps_r = find_fvgs(confirm_series)
            ref = refine(
                zone_entry=entry, zone_stop=stop, direction=structure,
                confirm_series=confirm_series,
                patterns=activate(
                    confirm_series,
                    _patterns_on_line(confirm_series, c_swings_r, cfg),
                    c_gaps_r,
                ),
                buffer=buf,
                zone_bottom=direct.bottom, zone_top=direct.top,
                tolerance=cfg.refine_tolerance,
            )
            # ⚠️ الرقمان معًا — المسلوك والمتروك. فسجلٌّ بلا المتروك
            # لا يقيس ما وفّره التنقيح، وذلك هو الغرض من بنائه.
            r.add(
                "تنقيح الدخول داخل المنطقة",
                ref.refined,
                ref.render(),
                "البثّ ٣ ≈1:10:26 · ترابط الفريمات §3 و§9",
            )
            if ref.refined:
                entry, stop = ref.entry, ref.stop
                stop_why = (
                    f"قاع النموذج {ref.pattern.extreme} − هامش {buf:g} "
                    f"({_buffer_why(cfg)}) · بدل قاع الأوردر بلوك "
                    f"{direct.bottom} — «بدون تأكيد ما بنصح»"
                )
            elif cfg.harmonic_enabled:
                # ⭐ والهارمونيك **بعد** الكلاسيكيّ لا قبله: فحين ينقّح
                # النموذجُ الانعكاسيّ لا حاجة لثانٍ، وحين لا ينقّح يبقى
                # الدخول من حدّ المنطقة — «بدون تأكيد ما بنصح». فهنا
                # موضعُه: يملأ فراغًا، ولا يزيح شيئًا قائمًا.
                harm = best_harmonic(
                    confirm_series, c_swings_r, structure,
                    direct.bottom, direct.top, cfg.harmonic_tolerance,
                )
                if harm is not None and harm.risk < ref.zone_risk:
                    r.add("تأكيد هارمونيّ داخل المنطقة", True,
                          f"{harm.render()} — بدل {ref.zone_risk:.2f}$ من حدّ المنطقة",
                          "البرق السريع §9 — «منها بأكّد»")
                    entry, stop = harm.entry, harm.stop
                    stop_why = (
                        f"وقف البرق السريع الصلب {harm.stop:.2f} "
                        f"(امتداد {harm.pattern.extension:g}) · "
                        f"بدل قاع الأوردر بلوك {direct.bottom}"
                    )
    else:
        c_swings = find_swings(confirm_series, cfg.swing_lookback)
        c_gaps = find_fvgs(confirm_series)
        on_line = _patterns_on_line(confirm_series, c_swings, cfg)
        patterns = [
            p
            for p in activate(confirm_series, on_line, c_gaps)
            if p.activated and p.direction == structure
        ]
        harm: Optional[HarmonicEntry] = None
        if not patterns and cfg.harmonic_enabled:
            # ⭐ ولا نموذجَ كلاسيكيًّا — فهل عند الهارمونيك تأكيد؟
            #
            #     «نقطة انعكاس على الهارمونيك، **منها بأكّد**»
            #
            # وشرطُ الاحتواء هو نفسُه: D داخل نقطة الاهتمام، وإلّا فهو
            # إعدادٌ آخر في مكانٍ آخر من الشارت لا تأكيدٌ لهذه.
            harm = best_harmonic(
                confirm_series, c_swings, structure,
                poi.bottom, poi.top, cfg.harmonic_tolerance,
            )

        if harm is not None:
            r.add("نموذج انعكاسي مفعَّل", True,
                  f"لا نموذج كلاسيكيّ — والتأكيد هارمونيّ: {harm.render()}",
                  "البرق السريع §9 — «منها بأكّد»")
            entry, stop = harm.entry, harm.stop
            stop_why = (
                f"وقف البرق السريع الصلب {harm.stop:.2f} "
                f"(امتداد {harm.pattern.extension:g}) — الدرجة بعد وقف الإغلاق"
            )
        else:
            if not patterns:
                # ⭐ ويُسمّى عددُ ما ردّه الخطّ — فرفضٌ سببه «نموذجٌ من
                # ذيول» غيرُ رفضٍ سببه «لا نموذج أصلًا»، والفرق يضبط
                # السماحية.
                vetoed = (
                    len(line_rejected(confirm_series,
                                      find_all(c_swings, cfg.pattern_tolerance),
                                      cfg.pattern_tolerance, cfg.swing_lookback))
                    if cfg.line_chart_veto else 0
                )
                r.add(
                    "نموذج انعكاسي مفعَّل",
                    False,
                    f"لا نموذج مفعَّل على {cfg.confirm_timeframe} — «إذا ما أعطاني ما بفوت»"
                    + (f" · وردَّ الخطُّ {vetoed} نموذجًا من ذيول" if vetoed else "")
                    + (" · ولا برقًا سريعًا داخل المنطقة"
                       if cfg.harmonic_enabled else ""),
                    "ترابط الفريمات",
                )
                return reject("لا تأكيد على الإطار المقابل")

            pat = patterns[-1]
            plan = entry_plan(pat, cfg.stop_buffer)
            if plan is None:
                r.add("خطة دخول من الريتست", False,
                      "النموذج مفعَّل بلا فراغ كسر", "§10")
                return reject("لا فراغ عند الكسر")

            r.add(
                "نموذج انعكاسي مفعَّل",
                True,
                f"{pat.kind} · كسر خط العنق {pat.neckline} بالجسم "
                f"· فراغ {pat.fvg.bottom}–{pat.fvg.top}",
                "الدرس 7 · ترابط الفريمات",
            )
            entry, stop = plan.entry, plan.stop
            stop_why = (
                f"طرف النموذج {pat.extreme} − هامش {cfg.stop_buffer:g} "
                f"({_buffer_why(cfg)})"
            )

    # ── ٦½. سقف مسافة الوقف ──
    #
    # ⭐ **الرقم مقيس لا مقدَّر.** في أسبوع الملاحظة (2026-09-07…11)
    # أُعيد بناء مسار M15 من السجل نفسه واختُبرت الإعدادات العشرون
    # عليه، فتبيّن:
    #
    #   • أقصى ارتدادٍ معاكس احتاجه **رابح** قبل هدفه: **13.30$**
    #     (ووسيط ما احتاجه الرابحون 8.71$)
    #   • سقفٌ عند 20$ يترك الأسبوع **كما هو تمامًا** (−10.21$)
    #   • وتشديدٌ إلى 12$ يقلبه إلى **−109.85$** — يقتل الرابحين
    #
    # ⇒ فالعشرون دولارًا هو السقف **الذي لا يكلّف شيئًا** ويقصّ
    # الذيل: أسوأ إعداد في الأسبوع كان وقفه **74.77$** لصفقةٍ واحدة.
    #
    # ويوافق حدَّ المدرّب المنطوق في درس الخفاش: دخول 4416 بوقف 4440
    # — «24$ — **كارثي** بالنسبة لمتداول على الذهب».
    if cfg.max_stop is not None and abs(entry - stop) > cfg.max_stop:
        r.entry, r.stop, r.stop_reason = entry, stop, stop_why
        r.add(
            "مسافة الوقف ضمن السقف",
            False,
            f"{abs(entry - stop):.2f}$ > {cfg.max_stop:g}$ — «خلّي ستوبك معقول»",
            "أسبوع 09-07…11 · درس الخفاش",
        )
        return reject("الوقف أبعد من السقف")
    if cfg.max_stop is not None:
        r.add(
            "مسافة الوقف ضمن السقف",
            True,
            f"{abs(entry - stop):.2f}$ ≤ {cfg.max_stop:g}$",
            "أسبوع 09-07…11 · درس الخفاش",
        )

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
        " · ".join(f"{t.price:.2f} ({t.strength})" for t in pool[:cfg.max_targets]),
        "السيولة الخارجية · «أول قمة آمن»",
    )

    r.entry, r.stop = entry, stop
    r.stop_reason = stop_why
    r.targets = [t.price for t in pool[:cfg.max_targets]]
    r.target_reason = "قمم/قيعان سابقة — سيولة خارجية · الأقرب أولًا"

    # ── ٧½. سلّمُ نقل الوقف ──
    #
    # ⭐ «بس ضرب الهدف الأوّل، **بدك تأمّن**… بترفع الستوب لوز لفوق
    #    دخولك **بدولار**» (الأوردر بلوك ج3) — ثم سلّمُ المستخدم بعدها.
    #
    # ⚠️ **ويُعرَض ولا يُنفَّذ**: البوت لا يلمس مركزًا. لكنّ عرضَه قبل
    #    الدخول يجعل الخطّة مقروءةً وقتَ القرار، لا بعده.
    r.trail_plan = [
        s.render() for s in trail_ladder(
            entry, stop, r.targets,
            "buy" if structure == "bullish" else "sell")
    ]

    # ── ٨. بوابة المخاطرة ──
    #
    # ⛔ **حدُّ الخسارة اليوميّ أوّلًا** — فهو الحدّ العامل بعد رفع حدّ
    # المراكز (المستخدم 2026-09-20). ويُقاس بالدولار لا بالعدّ، لأنّ
    # مركزين وقفُهما 3$ ليسا كمركزٍ وقفُه 20$.
    if (cfg.daily_loss_limit is not None
            and cfg.daily_loss <= -abs(cfg.daily_loss_limit)):
        r.blocked_reason = (
            f"بلغ اليومُ حدَّ خسارته ({cfg.daily_loss:+.2f}$ ≤ "
            f"−{abs(cfg.daily_loss_limit):g}$) — لا إعداد جديد اليوم"
        )
        return ChainResult(r, "blocked", r.blocked_reason, poi, direct, pool)

    if (cfg.max_open_positions is not None
            and cfg.open_positions >= cfg.max_open_positions):
        r.blocked_reason = (
            f"مركز مفتوح ({cfg.open_positions}/{cfg.max_open_positions}) — تنبيه لا أمر"
        )
        return ChainResult(r, "blocked", r.blocked_reason, poi, direct, pool)

    return ChainResult(r, "taken", "", poi, direct, pool)
