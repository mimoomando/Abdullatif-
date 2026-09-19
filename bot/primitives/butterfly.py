"""
مدرسة الهارمونيك — نموذج **الفراشة** (Butterfly · XABCD).

╔══════════════════════════════════════════════════════════════════╗
║   X ──▶ A      الضلع الأصل                                        ║
║      A ──▶ B   تصحيح  **0.75 – 0.82**  من X→A                     ║
║         B ──▶ C  تصحيح  0.382 – 0.886  من A→B                     ║
║            C ──▶ D  امتداد 1.618 – 2.618  من B→C                  ║
║                                                                   ║
║   D = **1.270** من X→A  ⬅ وهي **خلف X** لا دونها                  ║
║   الوقف = **1.414**  ·  الأهداف **من A إلى D**                    ║
╚══════════════════════════════════════════════════════════════════╝

**المصدر:** «نموذج الفراشة — الدرس الثالث من مدرسة الهارمونيك»
(2026-09-18)

⭐ **وما يميّزه عن الخفاش هندسيًّا**: D في الخفاش **دون X** (0.886)،
وفي الفراشة **خلفها** (1.270). فهو يُدخَل عند اختراق القمة/القاع
الأصل، لا عند الارتداد دونه.

⚠️ **ونادر**، ومصرَّح بذلك:

    «هو من النماذج **النادرة** اللي نادر إنه تتشكل بالشارت، وما
     بتلاقيه على الأطر الزمنية الصغيرة إلا قليل»
    «رح تشوفني إني **بدوّر كثير** لحتى للنموذج»

⇒ فقلّةُ ما يجده الماسح **خاصّيّةٌ لا عطب**.

⭐⭐ **وخاصّيّته الكبرى — المنطقة لا تُزار ثانيةً:**

    «القاع أو القمة اللي بيحدث منها الانعكاس **من النادر جدًّا إنه
     هي تنزار قريبًا** — ممكن تطول أسبوع أسبوعين شهرين أحيانًا سنة…
     ولكن هذا **مش شرط أساسي**، ولكن **90%** هذا الشيء بيتحقق»

وأراه حيًّا: قمّةُ بيتكوين التاريخيّة (6 أكتوبر 2025) لم تُزَر حتى
18 سبتمبر 2026، وقمّةٌ أخرى من 16 أبريل 2026 كذلك.

⛔ **و90% تقديرٌ لا إحصاء** (كسائر نسبه — انظر C6)، فلا يُبنى عليه
قرار. ولا شيء في هذه الوحدة يستعمله.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple

from ..data import Series
from .harmonic import (TARGET_RATIOS, FAST_TARGET_RATIO, PatternRejected,
                       PRZ_LEVELS, prz_from)
from .swings import Swing

Direction = Literal["bullish", "bearish"]

# «موجة تصحيح من الضلع X→A بدها تكون بين **0.75 و0.82**»
AB_RETRACE = (0.75, 0.82)

# ⭐ «بس بنموذج البترفلاي **بحقّ لك تنقص ثلاث درجات وتزيد ثلاث
#    درجات** — يعني الـ0.75 ممكن تكون **0.72** بتشتغل معك، وإذا كانت
#    0.78 هي أساسًا ضمن الرينج»
#
# ⚠️ و«درجة» هنا = **جزءٌ من مئة في النسبة** (0.75 − 0.03 = 0.72) —
# وهو **غير** «الدرجة» في هامش الوقف (`DEGREE_VALUE = 1.00 دولار`).
# اسمٌ واحد لوحدتين، فلا يُخلطا.
#
# 🔴 **BF1 — والسماحية مطبَّقة على الحدّ الأدنى وحده.** لأنه الوحيد
# الذي أثبته: قَبِل **0.73** صراحةً، ورَفَض **0.69**. ومثاله للزيادة
# (0.78) يقع داخل النطاق أصلًا، فلا يُثبت شيئًا عن 0.85. ولا حالة
# واحدة فوق 0.82 في الدرس كلّه.
AB_TOLERANCE = 0.03

# «تصحيح الموجة C من الضلع A→B بدها تكون بين 0.382 إلى 0.886»
BC_RETRACE = (0.382, 0.886)

# «امتداد تصحيح الموجة D من C→B هو من 1.618 إلى 2.618»
CD_EXTENSION = (1.618, 2.618)

# «امتداد D بده يكون على **1.270**»
D_EXTENSION = 1.270

# «امتداد ديله لوقف الخسارة **1.414**»
STOP_EXTENSION = 1.414

# 🔴 كما في الخفاش (D1): «بالضبط» بلا سماحية، وصفرُ سماحية يرفض كل
# رسمٍ يدويّ. ويُستعمل هنا على امتداد C→D وحده — لا على D نفسها،
# فـ D محسوبةٌ لا مرصودة.
CD_TOLERANCE = 0.010

_EPS = 1e-9


@dataclass(frozen=True)
class Butterfly:
    """فراشةٌ مستوفيةٌ لنسبها الثلاث — و D محسوبة."""

    x: Swing
    a: Swing
    b: Swing
    c: Swing
    ab_retrace: float
    bc_retrace: float
    cd_extension: float
    timeframe: str

    @property
    def direction(self) -> Direction:
        """
        X قمة ⇒ D **فوقها** ⇒ بيع.  ·  X قاع ⇒ D **تحتها** ⇒ شراء.

        وهو المنطق نفسه في الخفاش — والفرق أنّ D هنا تتجاوز X.
        """
        return "bearish" if self.x.is_high else "bullish"

    @property
    def leg_xa(self) -> float:
        return self.x.price - self.a.price

    @property
    def entry(self) -> float:
        """D — امتداد **1.270** من X→A، أي **خلف X**."""
        return self.a.price + self.leg_xa * D_EXTENSION

    @property
    def stop(self) -> float:
        """
        1.414 — الدرجة التي تلي الدخول على ضلع X→A نفسه.

        ⚠️ **بإغلاق شمعة لا بلمس**: «الستوب تبع الهارمونيك بيكون
        **بإغلاق شمعة**» — والخفاش وحده استُثني باللمس. ويبقى قرار
        المستخدم (وقفٌ صلب خلفه) ساريًا كما في `harmonic.py`.

        🔶 وقال عن الأطر الصغيرة: «إذا انت عم تشتغل على نطاق ثلاث
        دقائق، الستوب لوز عندك **كثير بسيط كثير خفيف — ما تعطي الهمّ**».
        وذلك وصفُ حجمٍ لا قاعدةُ إلغاء.
        """
        return self.a.price + self.leg_xa * STOP_EXTENSION

    @property
    def risk(self) -> float:
        return abs(self.stop - self.entry)

    def targets(self, include_fast: bool = False) -> List[float]:
        """«الأهداف بتكون **من A إلى D** نقطة الدخول» — كالخفاش."""
        span = self.a.price - self.entry
        ratios = ((FAST_TARGET_RATIO,) if include_fast else ()) + TARGET_RATIOS
        return [self.entry + span * r for r in ratios]

    def prz(self) -> Tuple[float, float]:
        """
        منطقة الانعكاس المحتملة — «بدنا ناخذ النسب **من B إلى A**».

        ⭐ **وفي الفراشة وحدها لها وزنٌ عمليّ:**

            «نموذج الفراشة **أحيانًا كثير ما بيوصل لنقطة الدخول** —
             **بيرتد من الـPRZ زون**، لأنه بمنطقة انعكاسية محتملة…
             واحتمال كثير إنه هو ما يوصل لها»

        ⛔ **ولا يُدخَل منها** — نهيُه عن الدخول من PRZ (وقفٌ متضخّم)
        قائمٌ كما في الخفاش. فهي **تفسيرُ فشلِ البلوغ** لا بديلُ دخول.

        ⭐ والنطاق بين **1.27 و1.618** من بطاقته المنشورة — انظر
        `harmonic.PRZ_LEVELS`. 🔶 **H3 ضُيِّق لا أُغلق.**
        """
        return prz_from(self.a.price, self.b.price)

    def invalidated_by(self, series: Series,
                       upto: Optional[int] = None) -> Optional[int]:
        """
        تغيّرُ موضع C قبل بلوغ D ⇒ النموذج باطل.

            «هالنموذج بيفشل **بحال تغيّر موقع C**. إذا في حال ما تغيّر
             موقع C وطلع، فهي **نقطة ارتداد قوية** وراح يوصل لها ويرتد»
        """
        stop_at = len(series) if upto is None else min(len(series), upto)
        for i in range(self.c.index + 1, stop_at):
            k = series[i]
            reached = (k.high >= self.entry if self.direction == "bearish"
                       else k.low <= self.entry)
            if reached:
                return None
            beyond = (k.low < self.c.price if self.direction == "bearish"
                      else k.high > self.c.price)
            if beyond:
                return i
        return None

    def render(self) -> str:
        side = "بيع" if self.direction == "bearish" else "شراء"
        tps = " · ".join(f"{t:g}" for t in self.targets())
        return (
            f"فراشة {side} · AB {self.ab_retrace:.3f} · BC {self.bc_retrace:.3f} "
            f"· CD {self.cd_extension:.3f} · دخول {self.entry:g} "
            f"· وقف {self.stop:g} · أهداف {tps}"
        )


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        raise ValueError("ضلع بلا مدى")
    return abs(numerator) / abs(denominator)


def build(x: Swing, a: Swing, b: Swing, c: Swing, timeframe: str,
          ab_tolerance: float = AB_TOLERANCE,
          cd_tolerance: float = CD_TOLERANCE) -> Butterfly:
    """
    يبني فراشةً من أربع نقاط سوينج.

    ⛔ **والنسب مقدّسة**: «هذه النسب بالهارمونيك بشكل عام هي نسب
    **مقدّسة** — ما فينا نلعب فيها ولا نزيحها أبدًا، بدها تكون
    **على الميلي**». والسماحية الوحيدة المصرَّح بها هي `ab_tolerance`
    على الحدّ الأدنى، وقد نصّ عليها هو.
    """
    if not (x.index < a.index < b.index < c.index):
        raise ValueError("النقاط يجب أن تتعاقب: X ثم A ثم B ثم C")
    if x.kind != b.kind or a.kind != c.kind or x.kind == a.kind:
        raise ValueError("النقاط يجب أن تتناوب: X و B من جنس، و A و C من الجنس الآخر")

    ab = _ratio(b.price - a.price, x.price - a.price)
    lo = AB_RETRACE[0] - ab_tolerance          # 🔴 BF1 — الأدنى وحده
    if not (lo - _EPS <= ab <= AB_RETRACE[1] + _EPS):
        raise PatternRejected(
            f"تصحيح A→B = {ab:.3f} خارج {lo:.2f}–{AB_RETRACE[1]} — "
            f"«أقل نسبة هي {AB_RETRACE[0]} كنموذج فراشة» "
            f"(بسماحية {ab_tolerance:g} على الأدنى)"
        )

    bc = _ratio(c.price - b.price, a.price - b.price)
    if not (BC_RETRACE[0] - _EPS <= bc <= BC_RETRACE[1] + _EPS):
        raise PatternRejected(
            f"تصحيح B→C = {bc:.3f} خارج {BC_RETRACE[0]}–{BC_RETRACE[1]}"
        )

    entry = a.price + (x.price - a.price) * D_EXTENSION
    cd = _ratio(entry - c.price, c.price - b.price)
    if not (CD_EXTENSION[0] - cd_tolerance <= cd <= CD_EXTENSION[1] + cd_tolerance):
        raise PatternRejected(
            f"امتداد C→D = {cd:.3f} خارج {CD_EXTENSION[0]}–{CD_EXTENSION[1]}"
        )

    return Butterfly(x=x, a=a, b=b, c=c, ab_retrace=ab, bc_retrace=bc,
                     cd_extension=cd, timeframe=timeframe)


def find_patterns(series: Series, swings: Sequence[Swing]) -> List[Butterfly]:
    """
    يمسح كل رباعية سوينج متناوبة.

    ⚠️ **وقلّةُ المخرَج متوقَّعة**: النموذج نادرٌ بنصّ الدرس، ونطاق
    A→B عنده **ضيّق** (0.72–0.82 مقابل 0.382–0.58 للخفاش). فصفرُ
    نماذجَ على سلسلةٍ قصيرة نتيجةٌ سليمة.
    """
    out: List[Butterfly] = []
    ordered = sorted(swings, key=lambda s: (s.index, s.kind))
    for i in range(len(ordered) - 3):
        x, a, b, c = ordered[i:i + 4]
        try:
            out.append(build(x, a, b, c, series.timeframe))
        except (PatternRejected, ValueError):
            continue
    return out


def active(series: Series, patterns: Sequence[Butterfly]) -> List[Butterfly]:
    """النماذج التي لم يتغيّر موضع C فيها قبل بلوغ D."""
    return [p for p in patterns if p.invalidated_by(series) is None]
