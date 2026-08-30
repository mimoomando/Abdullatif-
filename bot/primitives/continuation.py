"""
الأنماط الاستمرارية — العلم والمثلث · الدرس 8.

╔══════════════════════════════════════════════════════════════════╗
║  اندفاع  →  راحة لا تُبطله  →  كسر في اتجاه الاندفاع              ║
╚══════════════════════════════════════════════════════════════════╝

⭐⭐⭐ **هذه الوحدة تفتح قاعدة كانت معطَّلة.** وايكوف/د4 علّق الدخول على
الكسر الحقيقي بشرط:

    «لو كان الفوليوم عالي… فيك تكمل معه طلوع **إذا أعطاك نموذج استمراري**»

ولم تكن الأنماط الاستمرارية مُدرَّسة يومها، فكان الشرط غير قابل للتحقق
⇒ عُطِّل الدخول. والآن دُرِّست، فصار المسار: **كسر حقيقي + نموذج مؤكَّد**.
والكسر الحقيقي وحده ما زال لا يُدخِل.

⭐⭐ **الشرط الفاصل — عمق التصحيح:**

    «إذا رجع صحّح لعند **الـ61.8 فهذا النموذج باطل** — صار انعكاس»
    «التصحيح المقبول لحدود **الـ38**، وبالفريمات الكبيرة **الـ50** مقبولة»

⚠️ **وهذا معنى ثالث للنسب — لا يُخلَط بالاثنين السابقين:**

    بوابة القيمة        : تحت 50% رخيص وفوقه غالٍ        (الدرس 14)
    التصحيح الهيكلي     : المعتبر **يتجاوز** 50%
    النموذج الاستمراري  : الصالح **لا يتجاوز** 38–50%    ← هنا

ليست متعارضة: هذا يقيس **ضحالة الراحة** دليلًا على أن الطرف المقابل لم
يدخل — لا يقيس رُخص السعر.

⭐ **ومرجعا الرسم مختلفان داخل النموذج الواحد:**

    الاندفاع  →  **أجسام**  (مدى فعليّ يُنسخ هدفًا)
    حدّ العلم →  **ذيول**   («حدود العلم بترسمها على ذيول الشموع»)

وهو تطبيق للقاعدة المحسومة C1 لا خرقٌ لها: الحدّ يقيس مدى الراحة،
والمدى يُقاس بالذيول.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

from ..data import Series
from .fibonacci import Impulse

Direction = Literal["bullish", "bearish"]
Shape = Literal["flag", "pennant"]

# «التصحيح المقبول لحدود الـ38، وبالفريمات الكبيرة الـ50 مقبولة»
MAX_RETRACE = 0.382
MAX_RETRACE_HIGHER_TF = 0.5

# «إذا رجع صحّح لعند الـ61.8 فهذا النموذج باطل»
INVALIDATING_RETRACE = 0.618

# 🔴 CP2 — «الفريمات الكبيرة» غير محدَّدة بالنصّ. هذه قراءتي لجدول
# ترابط الفريمات: ما فوق H1 أطر خارجية. صريحة كي تُراجَع لا مخفيّة.
HIGHER_TIMEFRAMES = ("MN1", "W1", "D1", "H4")


class PatternInvalid(ValueError):
    """راحة عمّقت حتى أبطلت الاندفاع — «ما بقى نموذج استمراري، صار انعكاس»."""


@dataclass(frozen=True)
class Consolidation:
    """
    الراحة بين الاندفاع واستكماله.

    `high`/`low` **بالذيول** — لأنها تقيس مدى الراحة لا هيكلها.
    """

    start: int
    end: int
    high: float
    low: float

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @property
    def height(self) -> float:
        return self.high - self.low


@dataclass(frozen=True)
class ContinuationPattern:
    """
    نموذج استمراري مكتمل الشكل — **قبل** الكسر.

    وجوده لا يعطي صفقة: الدخول عند كسر الحدّ (`breakout_level`) ثم
    إعادة الاختبار.
    """

    impulse: Impulse
    consolidation: Consolidation
    direction: Direction
    shape: Shape
    timeframe: str
    retrace: float

    @property
    def is_higher_timeframe(self) -> bool:
        return self.timeframe in HIGHER_TIMEFRAMES

    @property
    def max_allowed_retrace(self) -> float:
        """«لحدود الـ38، وبالفريمات الكبيرة الـ50 مقبولة»."""
        return MAX_RETRACE_HIGHER_TF if self.is_higher_timeframe else MAX_RETRACE

    @property
    def valid(self) -> bool:
        return self.retrace <= self.max_allowed_retrace

    @property
    def grade(self) -> Literal["clean", "tolerated", "unstated", "invalid"]:
        """
        درجة النموذج بعمق تصحيحه.

        `unstated` هو ما بين 50% و61.8%: **لم ينصّ عليه الدرس**
        (🔴 CP1). لا يُقبل ولا يُسمّى باطلًا — يُعرَض كما هو.
        """
        if self.retrace >= INVALIDATING_RETRACE:
            return "invalid"
        if self.retrace <= MAX_RETRACE:
            return "clean"
        if self.retrace <= MAX_RETRACE_HIGHER_TF:
            return "tolerated" if self.is_higher_timeframe else "unstated"
        return "unstated"

    @property
    def breakout_level(self) -> float:
        """
        حدّ العلم الذي يُكسر — **بالذيل**.

        صاعد: قمة الراحة · هابط: قاعها.
        """
        return self.consolidation.high if self.direction == "bullish" else self.consolidation.low

    @property
    def price_range(self) -> float:
        """
        مدى الاندفاع — **جسمًا إلى جسم**.

            «بقيسه من **جسم** أول شمعة للاندفاع إلى **جسم** آخر شمعة»

        وهو أطراف الأجسام لا الذيول. على ساقٍ نظيفة أحادية الاتجاه
        يساوي هذا حرفَ النصّ (افتتاح الأولى → إغلاق الأخيرة)؛ وعلى
        ساقٍ متعرّجة يبقى الأوسع — وهو الأسلم للهدف.
        """
        return self.impulse.size

    def target(self, breakout_price: Optional[float] = None) -> float:
        """
        الهدف — «بنسخه وبحطه عند **نقطة الكسر**».

        يُنسخ المدى من سعر الكسر الفعليّ إن أُعطي، وإلا من حدّ العلم.
        """
        base = self.breakout_level if breakout_price is None else breakout_price
        return base + self.price_range if self.direction == "bullish" else base - self.price_range

    def render(self) -> str:
        name = "علم" if self.shape == "flag" else "مثلث"
        grades = {
            "clean": "سليم",
            "tolerated": "مقبول (إطار كبير)",
            "unstated": "غير منصوص",
            "invalid": "باطل",
        }
        return (
            f"{name} {'صاعد' if self.direction == 'bullish' else 'هابط'} "
            f"· تصحيح {self.retrace * 100:.1f}% · {grades[self.grade]} "
            f"· كسر {self.breakout_level:g} → هدف {self.target():g}"
        )


def measure_retrace(impulse: Impulse, consolidation: Consolidation, direction: Direction) -> float:
    """
    كم صحّحت الراحة من الاندفاع؟ نسبة بين 0 و1 (وقد تتجاوزه).

    تُقاس بالذيل — لأن الحدّ نفسه مرسوم على الذيول، ولأن السؤال «كم
    بلغ التصحيح» سؤال مدى.
    """
    if impulse.size <= 0:
        raise ValueError("اندفاع بلا مدى")
    if direction == "bullish":
        return (impulse.high - consolidation.low) / impulse.size
    return (consolidation.high - impulse.low) / impulse.size


def build(
    series: Series,
    impulse_start: int,
    impulse_end: int,
    consolidation_end: int,
    shape: Shape = "flag",
) -> ContinuationPattern:
    """
    يبني نموذجًا من فهارس ثلاثة: بداية الاندفاع · نهايته · نهاية الراحة.

    ⚠️ يرفع `PatternInvalid` عند 61.8% فأكثر — لأن النصّ لا يسمّيه
    نموذجًا ضعيفًا بل **باطلًا**: «ما بقى نموذج استمراري، صار انعكاس».
    إرجاع كائن «باطل» يغري باستعماله.
    """
    if not (impulse_start < impulse_end < consolidation_end < len(series)):
        raise ValueError("الفهارس يجب أن تكون متصاعدة وداخل السلسلة")

    leg = series[impulse_start:impulse_end + 1]
    direction: Direction = (
        "bullish" if series[impulse_end].close > series[impulse_start].open else "bearish"
    )

    # الاندفاع بالأجسام — لأنه المدى الذي يُنسخ هدفًا
    top = max(c.body_top for c in leg)
    bottom = min(c.body_bottom for c in leg)
    if top <= bottom:
        raise ValueError("اندفاع بلا مدى جسم")
    impulse = Impulse(low=bottom, high=top, direction=direction)

    rest = series[impulse_end + 1:consolidation_end + 1]
    if len(rest) == 0:
        raise ValueError("لا راحة بعد الاندفاع")
    consolidation = Consolidation(
        start=impulse_end + 1,
        end=consolidation_end,
        high=max(c.high for c in rest),      # ذيول — «حدود العلم على الذيول»
        low=min(c.low for c in rest),
    )

    retrace = measure_retrace(impulse, consolidation, direction)
    if retrace >= INVALIDATING_RETRACE:
        raise PatternInvalid(
            f"التصحيح بلغ {retrace * 100:.1f}% ≥ 61.8% — "
            "«ما بقى نموذج استمراري، صار انعكاس»"
        )

    return ContinuationPattern(
        impulse=impulse,
        consolidation=consolidation,
        direction=direction,
        shape=shape,
        timeframe=series.timeframe,
        retrace=retrace,
    )


@dataclass(frozen=True)
class Breakout:
    """كسر حدّ النموذج — والريتست بعده."""

    pattern: ContinuationPattern
    break_index: int
    break_price: float
    retest_index: Optional[int]

    @property
    def confirmed(self) -> bool:
        """
        🔴 **CP3** — «بيفضّل يرجع يعمل ريتست»: تفضيل لا إلزام في النصّ.

        والكود **يلزمه**: الإلزام يفوّت صفقة، وتركه يفتح دخولًا لم
        يُنصّ عليه. والأول أرخص.
        """
        return self.retest_index is not None

    @property
    def target(self) -> float:
        return self.pattern.target(self.break_price)

    @property
    def entry(self) -> Optional[float]:
        """الدخول عند الريتست — لا عند الكسر نفسه."""
        return self.break_price if self.confirmed else None


def find_breakout(
    series: Series,
    pattern: ContinuationPattern,
    retest_tolerance: float,
    limit: Optional[int] = None,
) -> Optional[Breakout]:
    """
    يبحث عن كسر حدّ النموذج ثم إعادة اختباره.

    الكسر **بالإغلاق** لا بالذيل (الدرس 10: «الكسر بالجسم») — الحدّ
    يُرسم بالذيول ويُكسر بالإغلاق: الرسم مدى، والكسر قرار. وهو ما
    يفعله `fake_break._resolve` نفسه، فلا يختلف حدّان في البوت.

    `retest_tolerance` : كم يقترب السعر من الحدّ ليُعدّ ريتستًا.
        🔴 **CP4 — غير معرَّف** في المصدر.
    """
    if retest_tolerance < 0:
        raise ValueError("السماحية لا تكون سالبة")

    level = pattern.breakout_level
    stop = len(series) if limit is None else min(len(series), limit)

    for i in range(pattern.consolidation.end + 1, stop):
        c = series[i]
        broke = (
            c.close > level if pattern.direction == "bullish"
            else c.close < level
        )
        if not broke:
            continue

        retest = None
        for j in range(i + 1, stop):
            r = series[j]
            probe = r.low if pattern.direction == "bullish" else r.high
            if abs(probe - level) <= retest_tolerance:
                retest = j
                break
            # فشل النموذج: عاد وأغلق داخل الراحة قبل الريتست
            failed = (
                r.close < level if pattern.direction == "bullish"
                else r.close > level
            )
            if failed:
                break

        return Breakout(
            pattern=pattern,
            break_index=i,
            break_price=c.close,
            retest_index=retest,
        )

    return None
