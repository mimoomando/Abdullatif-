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

╔══════════════════════════════════════════════════════════════════╗
║  ⛔⛔ **وصياغتي لاقتباسات هذا الملفّ كانت محرَّفة — صُحّحت          ║
║  2026-09-27** بعد أن وُسّع `bot/quotes.py` ليفحص الكود لا          ║
║  `params.py` وحده. وكان فيه **ثلاثةُ** اقتباساتٍ من كلامي أنا     ║
║  موضوعةً بين «» كأنّها كلامُه:                                     ║
║                                                                  ║
║    [إذا رجع صحّح لعند الـ61.8 فهذا النموذج باطل — صار انعكاس]     ║
║        ⇒ قال «**61%**» لا 61.8 · و«نموذج **علم**» لا              ║
║          «استمراري» · و«**صار انعكاس**» **لم يقلها أصلًا**.        ║
║        ⚠️ **وكانت في رسالة الخطأ التي يطبعها البوت** — أي في      ║
║          مخرَجٍ يراه المستخدم، لا في تعليقٍ فقط.                   ║
║    [التصحيح المقبول لحدود الـ38، وبالفريمات الكبيرة الـ50…]       ║
║        ⇒ المعنى صحيح، **واللفظ لي**. ونصُّه أدناه.                 ║
║    [بقيسه من جسم أول شمعة للاندفاع إلى جسم آخر شمعة]              ║
║        ⇒ **«بقيسه» صفرُ مواضع** في السجلّ كلِّه. ونصُّه أدناه.      ║
║                                                                  ║
║  ⭐ **وصُحّح الثلاثةُ في `params.py` يوم 26-09 ولم تُصحَّح هنا** —  ║
║  لأنّ الحارس كان يقرأ الدفتر ولا يقرأ الكود. **والتصحيحُ          ║
║  الناقص أخطرُ من غيابه**: ظنّ المشروعُ أنّ البابَ أُغلق.            ║
╚══════════════════════════════════════════════════════════════════╝

⭐⭐ **الشرط الفاصل — عمق التصحيح · وهذا نصُّه:**

    «شروطها هي **الماكسيموم 38%** — اذا صححت لل **50% ما في مشكله
     وخاصه على الاطارات الكبيره** — اما اذا صححت **لتحت يلغى بشكل
     كامل**»                                    (لسن 27 · ≈2:24)
    «في حال وصححت لل **61%** هيدا **ما بقى نموذج علم** وما بتطبق
     عندها هي الشروط»                        (بيسكس 09 · ≈1:17)

🔶 **CP5 — والنصّان يعطيان عتبتَي إبطالٍ لا واحدة: «لتحت» الـ50 ⇒
«يلغى بشكل كامل» · والـ61% ⇒ «ما بقى نموذج علم».** والكود يرفع
`PatternInvalid` عند **61.8%** وحدها، ويسمّي ما بين 50 و61.8
`unstated` — **وذلك لم يبقَ صحيحًا**: لسن 27 يسمّيه ملغىً.
⚠️ **ولم يُغيَّر الرقم** — الوحدةُ **غيرُ موصولة** (انظر أسفل
الترويسة)، فلا أثرَ لها في صفقة، والقرارُ للمستخدم لا لقراءتي.
وأثرُه العمليّ محدود: `valid` أصلًا يرفض كلَّ ما فوق السقف.

⚠️ **وهذا معنى ثالث للنسب — لا يُخلَط بالاثنين السابقين:**

    بوابة القيمة        : تحت 50% رخيص وفوقه غالٍ        (الدرس 14)
    التصحيح الهيكلي     : المعتبر **يتجاوز** 50%
    النموذج الاستمراري  : الصالح **لا يتجاوز** 38–50%    ← هنا

ليست متعارضة: هذا يقيس **ضحالة الراحة** دليلًا على أن الطرف المقابل لم
يدخل — لا يقيس رُخص السعر.

⭐ **ومرجعا الرسم مختلفان داخل النموذج الواحد — وكلاهما منصوص:**

    حدّ العلم →  **ذيول**
        «بدنا نرسم ترند لاين **على الذيول**… وننتظر اختراق
         هالترند»                                (لسن 27 · ≈2:51)
        «بنحدد ترند لاين مثل ما حكينا **من الذال للذال**»
                                              (بيسكس 09 · ≈3:40)
    الاندفاع  →  **أجسام**  (مدى فعليّ يُنسخ هدفًا)
        «بياخذوها **من الذيل الى الذيل** — انا باخذها **من السيوله
         للسيوله**، يعني **من جسم الشمعه الى جسم الشمعه**، اضمن لي
         انا هيك حسب خبرتي»                     (لسن 27 · ≈10:08)
        «انا كخبرتي بقول لك ارسمها **لعند اغلاق الشمعه، لعند
         السيوله المتمركزه** — بتعطيك نتائج افضل»
                                              (بيسكس 09 · ≈3:25)

⇒ **فالفرقُ مقصودٌ عنده لا عندي**: يصرّح بأنّ غيرَه يقيس ذيلًا إلى
ذيل و«أنا باخذها من السيوله للسيوله». وهو تطبيق للقاعدة المحسومة
C1 لا خرقٌ لها.

╔══════════════════════════════════════════════════════════════════╗
║  ⛔⛔ **والوحدةُ غيرُ موصولة — جُردت 2026-09-27.**                  ║
║                                                                  ║
║  لا مستوردَ لها في `bot/` كلِّه (بلا الاختبارات). فما تقوله هذه    ║
║  الترويسةُ **لا يقرّر صفقةً اليوم**، ومنه الاقتباساتُ المصحَّحة    ║
║  أعلاه. وكانت `CLAUDE.md` تُعدّ **ثلاثَ** وحداتٍ غيرِ موصولة —     ║
║  **والعددُ الحقيقيّ 11**. انظر `test_wiring.py`.                   ║
║                                                                  ║
║  🔶 **وفيها بندٌ منصوصٌ غيرُ مبنيّ**: وقفُ العلم.                   ║
║    «بالنسبه للعلم نحن **وقف الخساره عننا عند ادنى قاعه**»         ║
║                                            (لسن 27 · ≈10:37)     ║
║    «بنفوت صفقه اللونج من هون **ستوب عند ادنى قاع** والهدف»        ║
║                                          (بيسكس 09 · ≈4:22)      ║
║  ⇒ و`ContinuationPattern` يحسب الهدف **ولا يحسب الوقف**.          ║
╚══════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

from ..data import Series
from .fibonacci import Impulse

Direction = Literal["bullish", "bearish"]
Shape = Literal["flag", "pennant"]

# «شروطها هي **الماكسيموم 38%** — اذا صححت لل **50% ما في مشكله
# وخاصه على الاطارات الكبيره**» (لسن 27 ≈2:24)
MAX_RETRACE = 0.382
MAX_RETRACE_HIGHER_TF = 0.5

# «في حال وصححت لل **61%** هيدا **ما بقى نموذج علم**» (بيسكس 09 ≈1:17)
# ⚠️ والرقمُ 0.618 لا 0.61 — **اختيارٌ لي**: نسبةُ فيبوناتشي
# المرسومة على الأداة، وهو يسمّيها «61%» اختصارًا لها.
INVALIDATING_RETRACE = 0.618

# 🔴 CP2 — **اللفظُ منصوص، والعضويّةُ لا.** قال «وخاصه على الاطارات
# الكبيره» ولم يسمِّ أيَّها. وهذه قراءتي لجدول ترابط الفريمات: ما فوق
# H1 أطر خارجية. صريحة كي تُراجَع لا مخفيّة.
# (وكان مكتوبًا هنا «غير محدَّدة بالنصّ» — وذلك أوسعُ من الحقّ: غيرُ
#  المحدَّد أيُّها، لا أنّ للأطر الكبيرة حكمًا خاصًّا.)
HIGHER_TIMEFRAMES = ("MN1", "W1", "D1", "H4")


class PatternInvalid(ValueError):
    """راحة عمّقت حتى أبطلت الاندفاع — «**ما بقى نموذج علم**»."""


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
        """
        «الماكسيموم 38%… اذا صححت لل 50%… وخاصه على الاطارات الكبيره».

        ╔══════════════════════════════════════════════════════════╗
        ║  🔶 **CP6 — و«وخاصه» مبنيّةٌ هنا «فقط» · وُصف 09-30.**     ║
        ║                                                          ║
        ║  فالنصُّ: «اذا صححت لل 50% **ما في مشكله** وخاصه على       ║
        ║  الاطارات الكبيره». و«خاصّةً» **تشديدٌ لا حصر**: تقول      ║
        ║  إنّ الخمسين مقبولةٌ، وعلى الأطر الكبيرة أكثر.             ║
        ║                                                          ║
        ║  **والكودُ يقرأها حصرًا**: سقفُ الأطر الصغيرة 38% بلا      ║
        ║  استثناء. ⇒ **ومقيسٌ**: تصحيحُ 45% على H1 يخرج             ║
        ║  `valid=False`، وعلى H4 `valid=True` — والنصُّ واحد.       ║
        ║                                                          ║
        ║  ⚠️ **ولم يُغيَّر**: الوحدةُ غيرُ موصولة، والقراءةُ القائمةُ ║
        ║  **أصرمُ** (تُسقط نماذجَ ولا تُدخل غالية)، وقلبُها قراءةٌ    ║
        ║  أخرى بلا سندٍ أقوى. **والقرارُ للمستخدم.**                ║
        ╚══════════════════════════════════════════════════════════╝
        """
        return MAX_RETRACE_HIGHER_TF if self.is_higher_timeframe else MAX_RETRACE

    @property
    def valid(self) -> bool:
        return self.retrace <= self.max_allowed_retrace

    @property
    def grade(self) -> Literal["clean", "tolerated", "unstated", "invalid"]:
        """
        درجة النموذج بعمق تصحيحه.

        ⛔⛔ **واسمُ `unstated` لم يبقَ صحيحًا — 2026-09-27.** كان
        مكتوبًا أنّ ما بين 50% و61.8% «لم ينصّ عليه الدرس» (🔴 CP1)،
        **ودرس 27 ينصّ عليه**: «اما اذا صححت **لتحت يلغى بشكل
        كامل**» (≈2:24). فهو **ملغى** لا مسكوتٌ عنه.

        ⚠️ **ولم يُغيَّر السلوك** (انظر CP5 في الترويسة): الوحدةُ غيرُ
        موصولة، و`valid` يرفضه أصلًا. والاسمُ يبقى حتى يقرّر
        المستخدم، **والحدُّ مكتوبٌ هنا كي لا يُقرأ الاسمُ حجّةً**.

        ⛔⛔ **وللاسم موضعٌ ثانٍ فات التصحيحَ — CP6 · 09-30.**

        فالنطاقُ **38%…50% على إطارٍ صغير** يخرج كذلك `unstated`،
        **ودرس 27 ينصّ عليه هو أيضًا**: «اذا صححت لل 50% **ما في
        مشكله**». ⇒ فالاسمُ يقول [لم يُنصَّ] عن **نطاقين** نُصَّ
        عليهما، لا عن واحد.

        ⭐ **وهذا درسُ المشروع المتكرّر**: صُحّح نصفُ العطب 09-27
        وبقي نصفُه — **فيُسأل دائمًا: أين الموضعُ الثاني؟**
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

            «انا باخذها **من السيوله للسيوله**، يعني **من جسم الشمعه
             الى جسم الشمعه**»                   (لسن 27 · ≈10:08)

        ⛔ وكان مكتوبًا هنا [بقيسه من جسم أول شمعة للاندفاع إلى جسم
        آخر شمعة] بين «» — **و«بقيسه» صفرُ مواضع في السجلّ**. المعنى
        صحيح واللفظ كان لي.

        وهو أطراف الأجسام لا الذيول. على ساقٍ نظيفة أحادية الاتجاه
        يساوي هذا حرفَ النصّ (افتتاح الأولى → إغلاق الأخيرة)؛ وعلى
        ساقٍ متعرّجة يبقى الأوسع — وهو الأسلم للهدف.
        """
        return self.impulse.size

    def target(self, breakout_price: Optional[float] = None) -> float:
        """
        الهدف — «وبيجي **بستنسخها وبحطها عند الكسر**» (لسن 27 ≈10:25).

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
    نموذجًا ضعيفًا بل **يرفع عنه الاسم**: «**ما بقى نموذج علم**».
    إرجاع كائن «باطل» يغري باستعماله.

    🔶 وانظر CP5: درس 27 يُلغيه فوق الـ50 لا فوق الـ61.8.
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
            "«ما بقى نموذج علم وما بتطبق عندها هي الشروط»"
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
        🔴 **CP3 — وحجّتُه سقطت، صُحّح 2026-09-27.**

        كان مكتوبًا أنّ المدرّب قال [بيفضّل يرجع يعمل ريتست] ⇒
        «تفضيلٌ لا إلزام». **و«بيفضّل» صفرُ مواضع في السجلّ كلِّه.**
        وصُحّح هذا في `params.py` يوم 26-09 وبقي هنا يومًا كاملًا.

        والنصُّ الذي نملكه يذكره **في التسلسل نفسِه بلا لفظ تفضيل**:

            «هو كسر، اعاده اختبار — **عند اعاده اختبار هي الدخول**»
                                              (بيسكس 09 · ≈4:05)

        ⇒ فالإلزامُ في الكود **أقربُ إلى النصّ** لا أبعدُ منه. 🔶 ويبقى
        استنتاجًا: النصُّ يصف مثالًا ولا يقول «لازم» صراحةً.
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
