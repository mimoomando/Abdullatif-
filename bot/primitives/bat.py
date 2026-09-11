"""
نموذج الخفاش (Bat) — الهارمونيك ٢ · XABCD.

╔══════════════════════════════════════════════════════════════════╗
║   X ──▶ A      الضلع الأصل                                        ║
║      A ──▶ B   تصحيح  0.382 – 0.58   من X→A                       ║
║         B ──▶ C  تصحيح  0.382 – 0.99   من A→B                     ║
║            C ──▶ D  ارتداد **0.886 بالضبط** من X→A                ║
║                                                                   ║
║   وشرطٌ رابع: امتداد B→D من B→C بين **1.618 و 2.618**             ║
╚══════════════════════════════════════════════════════════════════╝

⚠️ **خمس نقاط لا أربع.** البرق السريع `ABCD`، والخفاش `XABCD`:

    «نموذج البرق السريع كنا ناخذه من الـABCD باترن، أما نموذج الخفاش
     بدنا ناخذه من **XABCD**»

والشكل **W** للشراء و**M** للبيع.

⭐⭐ **والجملة التي تحكم هذه الوحدة كلها:**

    «**النسب بالهارمونيك مقدّسة — ما في مزح**»

وبرهنها بمثال: رفض نموذجًا لأن C جاءت **0.996**، ثم قَبِله حين صُحّح
الرسم إلى **0.99**. أي أن **جزءًا من المئة يُسقط النموذج**. ولذلك
تُرفع `PatternRejected` عند أي خرقٍ لأي نسبة — ولا يُرجَع «نموذج
ضعيف».

⭐ **والأهداف من A لا من C** — وهذا فرقٌ جوهريّ عن البرق السريع
وسهلُ الخلط:

    «طريقة أخذ الأهداف بالنسبة لنموذج البات **مختلفة شوي**… بتكون
     **من A إلى D**. نحن كنا ناخذ من C إلى D»
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple

from ..data import Series
from .harmonic import TARGET_RATIOS, FAST_TARGET_RATIO, PatternRejected
from .swings import Swing

Direction = Literal["bullish", "bearish"]

# «لازم تكون بين 0.382 لـ0.58 — إذا نزلت يُلغى وإذا طلعت فوق 58 يُلغى»
B_RETRACE = (0.382, 0.58)

# «المفروض تكون بين 0.382 إلى 0.99… وإذا زادت عن 0.99 يُلغى النموذج»
C_RETRACE = (0.382, 0.99)

# «نقطة الدخول عنّا 0.886 — **لا بتزيد ولا بتنقص**»
D_RETRACE = 0.886

# «امتداد من D إلى B لازم يكون بين 1.618 إلى 2.618»
BD_EXTENSION = (1.618, 2.618)

# «وقف الخسارة يلي هو على 1.130» — امتدادًا من X، أي **خلف X**
STOP_RETRACE = 1.130

# 🔴 D1 — «بالضبط» بلا سماحية مذكورة. وصفرُ سماحية يرفض كل نموذج
# حقيقي (الرسم اليدويّ لا يصيب ثلاث خانات)، فتُترك مقبضًا صريحًا.
D_TOLERANCE = 0.010

# سماحية عدديّة بحتة — لا توسيعًا للنطاق. الحدّ نفسه يجب أن يمرّ:
# 100 + 100×0.382 ثم القسمة يعطي 0.38199999999999995، فيسقط حدٌّ
# صحيح لسبب لا علاقة له بالقاعدة.
_EPS = 1e-9


@dataclass(frozen=True)
class Bat:
    """
    نموذج خفاش مستوفٍ لنسبه الأربع.

    النقاط سوينج — كما نصّ الدرس الأول: «أي قمة أو قاع بدك تبلش منها
    أو تصحح عليها **لازم تكون سوينج**». و D وحدها محسوبة لا مرصودة.
    """

    x: Swing
    a: Swing
    b: Swing
    c: Swing
    b_retrace: float
    c_retrace: float
    bd_extension: float
    timeframe: str

    @property
    def direction(self) -> Direction:
        """
        اتجاه **الصفقة**.

        X قمة ⇒ A قاع ⇒ D قربَ القمة ⇒ **بيع** (شكل M).
        X قاع ⇒ A قمة ⇒ D قربَ القاع ⇒ **شراء** (شكل W).
        """
        return "bearish" if self.x.is_high else "bullish"

    @property
    def leg_xa(self) -> float:
        return self.x.price - self.a.price

    @property
    def entry(self) -> float:
        """D — ارتداد 0.886 من A نحو X. «لا بتزيد ولا بتنقص»."""
        return self.a.price + self.leg_xa * D_RETRACE

    @property
    def stop(self) -> float:
        """
        1.130 — **خلف X** لا خلف D.

        ⚠️ والخفاش **الاستثناء الوحيد** الذي أجاز فيه الوقف باللمس:
        «هو النموذج الوحيد اللي بنعتمد عليه وقف الخسارة باللمس… ولكن
        نصيحة المدرسة الأم بتقول إنه بإغلاق الجسم». عرض الطريقتين ولم
        يحسم (🔴 B1)، وقرار المستخدم (وقف صلب خلف وقف الإغلاق) يغطّي
        الحالتين معًا فلم يُغيَّر شيء.
        """
        return self.a.price + self.leg_xa * STOP_RETRACE

    @property
    def risk(self) -> float:
        return abs(self.stop - self.entry)

    def targets(self, include_fast: bool = False) -> List[float]:
        """
        ⭐ **من A إلى D** — لا من C.

            «نحن كنا ناخذ من C إلى D، ولكن بالنماذج هي بدها تكون
             **من A إلى D**»

        و A أبعد من C، فالأهداف أوسع. وهذا أسهل ما يُخلَط بين
        النموذجين.
        """
        span = self.a.price - self.entry
        ratios = ((FAST_TARGET_RATIO,) if include_fast else ()) + TARGET_RATIOS
        return [self.entry + span * r for r in ratios]

    def fast_targets(self) -> List[float]:
        """
        البديل السريع — من C إلى D.

            «في حال بدك تاخذها من C إلى D تكون أهدافك **سريعة** —
             انت حر، ولكن النموذج الأساسي… هي هذي»

        مسموح لا مفضَّل، ولذلك في دالة منفصلة لا في الافتراضي.
        """
        span = self.c.price - self.entry
        return [self.entry + span * r for r in TARGET_RATIOS]

    def prz(self) -> Tuple[float, float]:
        """
        منطقة الانعكاس المحتملة — «الـPRZ بيتاخذ **من B إلى A**».

        ⚠️ **ولا يُدخَل منها.** منصوص:

            «ما تعتمد كثير على البي ار زد — ليه؟ لأنه راح يعطيك مناطق
             انعكاس ولكن راح **يكبّر لك الستوب**… إذا بدك تفوت على
             4416 ستوبك خطك على 4440 — **فكارثي** بالنسبة لمتداول
             على الذهب»

        فتُرجَع للعرض والسياق، والدخول يبقى عند D.
        🔴 **H3** — النِّسَب داخل هذا المدى لم تصل؛ فيُرجَع المدى خامًا.
        """
        lo, hi = sorted((self.b.price, self.a.price))
        return (lo, hi)

    def invalidated_by(self, series: Series, upto: Optional[int] = None) -> Optional[int]:
        """
        كسر C قبل بلوغ D ⇒ النموذج باطل.

            «بيفشل النموذج لما بيتغيّر عندي القاع تبع C»
        """
        stop_at = len(series) if upto is None else min(len(series), upto)
        for i in range(self.c.index + 1, stop_at):
            k = series[i]
            reached = k.high >= self.entry if self.direction == "bearish" else k.low <= self.entry
            if reached:
                return None
            beyond = k.low < self.c.price if self.direction == "bearish" else k.high > self.c.price
            if beyond:
                return i
        return None

    def render(self) -> str:
        side = "بيع" if self.direction == "bearish" else "شراء"
        tps = " · ".join(f"{t:g}" for t in self.targets())
        return (
            f"خفاش {side} · B {self.b_retrace:.3f} · C {self.c_retrace:.3f} "
            f"· BD {self.bd_extension:.3f} · دخول {self.entry:g} "
            f"· وقف {self.stop:g} · أهداف {tps}"
        )


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        raise ValueError("ضلع بلا مدى")
    return abs(numerator) / abs(denominator)


def build(x: Swing, a: Swing, b: Swing, c: Swing, timeframe: str,
          d_tolerance: float = D_TOLERANCE) -> Bat:
    """
    يبني خفاشًا من أربع نقاط سوينج — و D محسوبة.

    ⛔ **كل نسبة خارج نطاقها تُلغي النموذج.** «النسب بالهارمونيك
    مقدّسة — ما في مزح»: رفض هو نفسه نموذجًا لأن C جاءت 0.996 بدل
    0.99. فلا تُرجَع نماذج «قريبة».
    """
    if not (x.index < a.index < b.index < c.index):
        raise ValueError("النقاط يجب أن تتعاقب: X ثم A ثم B ثم C")
    if x.kind != b.kind or a.kind != c.kind or x.kind == a.kind:
        raise ValueError("النقاط يجب أن تتناوب: X و B من جنس، و A و C من الجنس الآخر")

    b_r = _ratio(b.price - a.price, x.price - a.price)
    if not (B_RETRACE[0] - _EPS <= b_r <= B_RETRACE[1] + _EPS):
        raise PatternRejected(
            f"تصحيح B = {b_r:.3f} خارج {B_RETRACE[0]}–{B_RETRACE[1]} — "
            "«إذا نزلت يُلغى وإذا طلعت فوق 58 يُلغى»"
        )

    c_r = _ratio(c.price - b.price, a.price - b.price)
    if not (C_RETRACE[0] - _EPS <= c_r <= C_RETRACE[1] + _EPS):
        raise PatternRejected(
            f"تصحيح C = {c_r:.3f} خارج {C_RETRACE[0]}–{C_RETRACE[1]} — "
            "«إذا زادت عن 0.99 يُلغى النموذج»"
        )

    entry = a.price + (x.price - a.price) * D_RETRACE
    bd = _ratio(entry - c.price, c.price - b.price)
    if not (BD_EXTENSION[0] - d_tolerance <= bd <= BD_EXTENSION[1] + d_tolerance):
        raise PatternRejected(
            f"امتداد B→D = {bd:.3f} خارج {BD_EXTENSION[0]}–{BD_EXTENSION[1]} — "
            "«إذا ما كانت بينهم، نموذج يُلغى»"
        )

    return Bat(x=x, a=a, b=b, c=c, b_retrace=b_r, c_retrace=c_r,
               bd_extension=bd, timeframe=timeframe)


def find_patterns(series: Series, swings: Sequence[Swing]) -> List[Bat]:
    """
    يمسح كل رباعية سوينج متناوبة ويبني ما تقبله النسب.

    والرفض هو **القاعدة العاملة** لا خطأ: أغلب الرباعيات لا تحقّق
    أربع نسب معًا — وتلك دقّة النموذج لا عيبه.
    """
    out: List[Bat] = []
    ordered = sorted(swings, key=lambda s: (s.index, s.kind))

    for i in range(len(ordered) - 3):
        x, a, b, c = ordered[i:i + 4]
        try:
            out.append(build(x, a, b, c, series.timeframe))
        except (PatternRejected, ValueError):
            continue
    return out


def active(series: Series, patterns: Sequence[Bat]) -> List[Bat]:
    """النماذج التي لم تُبطَل بكسر C."""
    return [p for p in patterns if p.invalidated_by(series) is None]
