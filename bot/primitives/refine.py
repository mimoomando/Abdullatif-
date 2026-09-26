"""
تنقيح الدخول داخل نقطة الاهتمام — تصغير الوقف بالتدرّج.

⭐⭐⭐ **هذا أعلى بندٍ قِسنا كلفته بالدولار.** في أسبوع 09-07…11 كان
وسيط وقف البوت **10.91$** وأقصاه **74.77$**، بينما أرقام المدرّب في
البثّ ٣ **1–3.5$** للوقف و**8–11$** للهدف. أي أن **وقف البوت بحجم
هدفِه** — والسبب ليس سقفًا ناقصًا بل **موضع الدخول**.

╔══════════════════════════════════════════════════════════════════╗
║  والنصّ الفاصل — البثّ ٣ (≈1:10:26):                              ║
║                                                                  ║
║    «هي الارتداد من الأوردر بلوك العالم بتفوت، في أغلبيتها بتفوت   ║
║     من الأوردر بلوك بيكون **الستوب تبعها قاع الأوردر بلوك**،      ║
║     **ولكن أنا بدون تأكيد ما بنصح**»                             ║
╚══════════════════════════════════════════════════════════════════╝

⇒ فالدخول من حدّ المنطقة بوقفٍ عند قاعها كاملًا هو ما يفعله «العالم»،
وهو **ما لا ينصح به بلا تأكيد**. وطريقتُه: ينتظر نموذجًا انعكاسيًّا
**داخل** المنطقة على إطارٍ صغير، ويأخذ وقفه من **قاع النموذج**.

**والغرض منصوص** (ترابط الفريمات §9):

    بلا ترابط فريمات ⇒ 110 نقطة
    على الساعة       ⇒ 590 نقطة
    بترابط الفريمات  ⇒ **10 نقاط**
    «هيك بتتدرج بالفريمات» — والغرض **تصغير الوقف**

**والتسلسل الثماني يسمّي الوقف صراحةً** (ترابط الفريمات §3):

    ٨. الدخول · الوقف: **أدنى القاع بقليل** (أو أدنى الأوردر بلوك بقليل)

⇒ «أدنى القاع» هو قاع **النموذج**، و«أو أدنى الأوردر بلوك» هو البديل
الأوسع عند الدخول من مجرّد اللمس. فالأوّل أصلٌ والثاني رخصة.

**ومثالٌ عمليّ حين تتراكب المناطق** (البثّ ٣ ≈23:12):

    «عندي أوردر بلوك على ربع ساعة، عندي فير فالو جاب على أربع
     ساعات، عندي أوردر بلوك على الساعة — فأنا **أي لمس لهي المنطقة
     ما راح يوصل لي للقاع**، وستوبي بكون **أدنى هذا القاع بقليل
     مشان السبريد**»

⛔ **ولا يُلغى الدخول من مجرّد اللمس.** هو قاعدته في م2/د3 بشروطها
الثلاثة، ويبقى مسارًا قائمًا. وهذه الوحدة **تفضّل** المنقَّح عليه
حين يتوفّر، ولا تمنعه حين لا يتوفّر — وتُسمّي في السجل أيَّ المسارين
سُلك، كي تُقاس كلفة كلٍّ منهما في الأسبوع القادم.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

from ..data import Series
from .patterns import EntryPlan, ReversalPattern, entry_plan

Direction = Literal["bullish", "bearish"]
Source = Literal["pattern", "zone"]


@dataclass(frozen=True)
class Refinement:
    """
    مقارنةُ مسارَي الدخول على الإعداد الواحد — بالأرقام.

    ويحمل **كليهما دائمًا**: المنقَّح والأصلَ من حدّ المنطقة. فالسجل
    بلا الرقم المتروك لا يقيس شيئًا، وقياسُ ما وفّره التنقيح هو
    الغرض من بنائه.
    """

    direction: Direction
    zone_entry: float
    zone_stop: float
    entry: float
    stop: float
    source: Source
    reason: str
    pattern: Optional[ReversalPattern] = None

    # ⛔⛔⛔ **تشخيصُ الفشل — أُضيف 2026-09-26 بعد أغلى فجوةٍ في السجلّ.**
    #
    # ثلاثةُ أسابيعَ حيّة: **صفرٌ من اثنتي عشرة صفقةً نُقِّحت**. فدخلت
    # كلُّها من حدّ المنطقة — وهو بعينه ما ينهى عنه النصّ: «بدون تأكيد
    # ما بنصح». وكلفتُه ظاهرةٌ بالأرقام:
    #
    #     وقفُ البوت   وسيط 10.55$ · أصغرُه 8.23$
    #     وقفُ المدرّب «ماكسيموم **3 4 دولار**» · «1.3 · دولارين»
    #
    # ⇒ فالوقفُ **ثلاثةُ أضعافِ** سقفه، والتنقيحُ هو ما بُني لتصغيره:
    #   «الغرض من التدرّج في الفريمات **تصغير الوقف**».
    #
    # ⚠️ **وللفشل خمسةُ أسبابٍ مختلفة، والسجلُّ كان يقول «من حدّ
    #    المنطقة» في كلِّها** — فلا يُعرف أيُّها وقع، ولكلٍّ علاجٌ آخر:
    #
    #   ① لا نموذجَ انعكاسيًّا أصلًا على الإطار المقابل  ⇒ الكاشفُ أعمى
    #   ② نماذجُ بالاتّجاه المعاكس                      ⇒ لا شأن لها
    #   ③ نماذجُ صحيحةٌ لكنّ طرفَها **خارج** المنطقة     ⇒ السماحيّة
    #   ④ مفعَّلٌ بلا فراغ كسر (`entry_plan is None`)    ⇒ شرطُ الفراغ
    #   ⑤ لا يشدّ الوقف (`risk >= zone_risk`)           ⇒ سليمٌ ومقصود
    #
    # فتُحمَل الأعدادُ الآن، ويقولها `render()`. **ولا يتغيّر قرارٌ
    # واحد** — يتغيّر ما يُكتب عنه.
    seen: int = 0             # ① مفعَّلٌ وبالاتّجاه الصحيح
    inside: int = 0           # ③ ومنها ما وقع داخل المنطقة
    nearest: Optional[float] = None   # أقربُ طرفٍ خارجَها — بالدولار
    dropped: str = ""         # ④/⑤ لماذا رُدَّ ما كان داخلها

    @property
    def zone_risk(self) -> float:
        return abs(self.zone_entry - self.zone_stop)

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def refined(self) -> bool:
        return self.source == "pattern"

    @property
    def saved(self) -> float:
        """كم دولارًا وفّره التنقيح — صفرٌ إن لم يُنقَّح."""
        return max(0.0, self.zone_risk - self.risk)

    @property
    def shrink(self) -> float:
        """نسبةُ ما بقي من الوقف. 0.25 تعني رُبعَه."""
        return self.risk / self.zone_risk if self.zone_risk > 0 else 1.0

    def why_not(self) -> str:
        """⭐ سببُ عدم التنقيح بلفظه — لا «لم يُنقَّح» وحدها."""
        if self.seen == 0:
            return "ولا نموذجَ انعكاسيًّا مفعَّلًا بالاتّجاه على إطار التأكيد"
        if self.inside == 0:
            near = (f" · أقربُها خارجها بـ{self.nearest:.2f}$"
                    if self.nearest is not None else "")
            return f"{self.seen} نموذجًا — وكلُّها خارج المنطقة{near}"
        if self.dropped:
            return f"{self.inside} داخلها — ورُدَّت: {self.dropped}"
        return "غير محدَّد"

    def render(self) -> str:
        if not self.refined:
            return (f"من حدّ المنطقة · مخاطرة {self.risk:.2f}$ — "
                    f"«بدون تأكيد ما بنصح» · {self.why_not()}")
        return (f"منقَّح من {self.pattern.kind} · "
                f"مخاطرة {self.risk:.2f}$ بدل {self.zone_risk:.2f}$ "
                f"(وفّر {self.saved:.2f}$ — {self.shrink:.0%} مما كان)")


def _inside(price: float, bottom: float, top: float, tolerance: float) -> bool:
    return (bottom - tolerance) <= price <= (top + tolerance)


def candidates(
    confirm_series: Series,
    patterns: Sequence[ReversalPattern],
    direction: Direction,
    zone_bottom: float,
    zone_top: float,
    tolerance: float = 0.0,
) -> List[ReversalPattern]:
    """
    النماذج المفعَّلة التي **طرفُها داخل المنطقة**.

    ⚠️ وشرطُ الاحتواء هو ما يجعل هذا تنقيحًا لا صفقةً أخرى: نموذجٌ
    طرفُه بعيدٌ عن المنطقة إعدادٌ مستقلّ في مكانٍ آخر من الشارت، لا
    تنقيحٌ لهذه النقطة. وهو مقتضى قوله «**أي لمس لهي المنطقة** ما راح
    يوصل لي للقاع» — فالقاع المقصود قاعٌ **في** المنطقة.
    """
    return [
        p for p in patterns
        if p.activated
        and p.direction == direction
        and _inside(p.extreme, zone_bottom, zone_top, tolerance)
    ]


def refine(
    zone_entry: float,
    zone_stop: float,
    direction: Direction,
    confirm_series: Series,
    patterns: Sequence[ReversalPattern],
    buffer: float,
    zone_bottom: Optional[float] = None,
    zone_top: Optional[float] = None,
    tolerance: float = 0.0,
) -> Refinement:
    """
    يرجع الخطّة المنقَّحة إن وُجدت — وإلّا خطّة حدّ المنطقة كما هي.

    والمنطقة تُحدّ بـ`zone_bottom`/`zone_top`؛ وإن لم تُمرَّرا استُنبطا
    من الدخول والوقف، فهما طرفا المنطقة في مسار اللمس المباشر.

    ⛔ **ولا يُقبل تنقيحٌ لا يشدّ الوقف.** نموذجٌ وقفُه أوسع من قاع
    المنطقة ليس تنقيحًا، وقبوله يناقض الغرض المنصوص: «الغرض من
    التدرّج تصغير الوقف». فيُردّ ويبقى الأصل.

    ⚠️ ويُردّ كذلك ما انقلب فيه الدخول إلى الجهة الخاطئة من الوقف —
    فذلك خطأ هندسيّ لا صفقة.
    """
    lo = zone_bottom if zone_bottom is not None else min(zone_entry, zone_stop)
    hi = zone_top if zone_top is not None else max(zone_entry, zone_stop)

    # ⭐ يُعَدُّ أوّلًا ما رآه الكاشف — فالسجلُّ يحتاج المتروكَ كالمسلوك.
    aimed = [p for p in patterns if p.activated and p.direction == direction]
    found = candidates(confirm_series, patterns, direction, lo, hi, tolerance)
    outside = [p for p in aimed if p not in found]
    nearest = min((max(lo - p.extreme, p.extreme - hi) for p in outside),
                  default=None)

    def blank(dropped: str = "") -> "Refinement":
        return Refinement(
            direction=direction,
            zone_entry=zone_entry, zone_stop=zone_stop,
            entry=zone_entry, stop=zone_stop,
            source="zone",
            reason="لا نموذج مفعَّل داخل المنطقة — الدخول من حدّها",
            seen=len(aimed), inside=len(found),
            nearest=nearest if nearest is not None and nearest > 0 else None,
            dropped=dropped,
        )

    base = blank()
    if base.zone_risk <= 0:
        return base
    if not found:
        return base

    best: Optional[Refinement] = None
    why: List[str] = []
    for pat in found:
        plan: Optional[EntryPlan] = entry_plan(pat, buffer)
        if plan is None:
            why.append("بلا فراغ كسر")
            continue                     # مفعَّل بلا فراغ كسر — لا مدخل

        risk = abs(plan.entry - plan.stop)
        if risk <= 0:
            why.append("مخاطرة صفر")
            continue
        # الوقف في الجهة الخاسرة، والدخول في الرابحة
        if direction == "bullish" and plan.stop >= plan.entry:
            why.append("هندسة مقلوبة")
            continue
        if direction == "bearish" and plan.stop <= plan.entry:
            why.append("هندسة مقلوبة")
            continue
        if risk >= base.zone_risk:
            why.append(f"لا يشدّ ({risk:.2f}$ ≥ {base.zone_risk:.2f}$)")
            continue                     # لا يشدّ ⇒ ليس تنقيحًا

        cand = Refinement(
            direction=direction,
            zone_entry=zone_entry, zone_stop=zone_stop,
            entry=plan.entry, stop=plan.stop,
            source="pattern", reason=plan.reason, pattern=pat,
            seen=len(aimed), inside=len(found), nearest=nearest,
        )
        if best is None or cand.risk < best.risk:
            best = cand

    return best or blank(" · ".join(dict.fromkeys(why)))
