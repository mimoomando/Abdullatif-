"""
مدرسة الهارمونيك — نموذج «البرق السريع» (ABCD).

╔══════════════════════════════════════════════════════════════════╗
║   A ──▶ B      الضلع الدافع                                       ║
║      B ──▶ C   تصحيح  (نسبته تُقرأ من الضلع A→B)                  ║
║         C ──▶ D  امتداد (نسبته تُقرأ من **الجدول**)               ║
║                                                                   ║
║   الدخول عند D · الوقف الدرجة التالية · الأهداف من C إلى D        ║
╚══════════════════════════════════════════════════════════════════╝

⭐⭐⭐ **أول درس في المنهج يعطي جدول أرقام دقيقًا.** كل ما سبقه وصفٌ
نوعيّ تركني أضع مقابض `UNDEFINED`؛ وهذا نسبٌ مصرَّح بها، تحقّقت من
اثني عشر مثالًا في الدرس والبثّ بلا استثناء واحد.

⭐⭐ **A · B · C لازم تكون سوينج · و D ليست سوينج:**

    «أي قمة أو قاع بدك تبلش منها أو تصحح عليها **لازم تكون سوينج**»
    «أما وين بيوصل امتداد D — **هيدا ما دخله يكون سوينج**»

فـ D **هدف محسوب** لا نقطة مرصودة. ولذلك يبنى النموذج من ثلاث نقاط
ويُشتقّ الرابع.

⛔ **وحدّ التصحيح الأدنى قاطع:**

    «**أقل نسبة مسموح يصحح فيها هي 0.382**. اذا نزل تحت،
     ما في تصحيح وما في استهداف»

⚠️⚠️ **والوقف عنده بالإغلاق لا باللمس** — «طالما جسم الشمعة [فوق]
المستوى ما في وقف خسارة» و«مش لازم تحط ستوب تلقائي». وهذا يترك المركز
مكشوفًا بين الإغلاقين على أداةٍ تتحرك عشرات الدولارات في شمعة أخبار.

⭐ **فقرّر المستخدم (2026-09-05) وضع وقف صلب خلفه** — شبكة أمان لا
تُضرب في الحالة العادية:

    الدخول D        ← الدرجة من الجدول
    وقف الإغلاق     ← الدرجة التالية      (قاعدة المدرّب · مراقَبة)
    الوقف الصلب     ← الدرجة التي تليها   (قرار المستخدم · أمرٌ عند الوسيط)

فالخسارة القصوى صارت محدودة، وقاعدةُ «الذيل ليس وقفًا» باقيةً على حالها.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from ..data import Series
from .swings import Swing

Direction = Literal["bullish", "bearish"]

# «أقل نسبة مسموح يصحح فيها هي 0.382»
MIN_RETRACE = 0.382

# ⭐ الجدول — منصوص: «من 0.382 لـ0.48 امتداد 2.24، من 0.49 الى 0.59
# امتداد 2.00… من الـ60 الى 68 امتداد 1.618… من 69 لـ76 امتداد 1.41»
#
# كل مدخلة: (الحدّ الأعلى للتصحيح شاملًا، الامتداد)
EXTENSION_TABLE: Tuple[Tuple[float, float], ...] = (
    (0.48, 2.24),
    (0.59, 2.00),
    (0.68, 1.618),
    (0.76, 1.41),
    (0.85, 1.13),      # 🔴 H1 — بداية هذا النطاق غير منصوصة
)

# ⭐ سلّم الامتدادات — درجاته بالترتيب.
#
#   الوقف بالإغلاق  = الدرجة **التالية** بعد الدخول
#   الوقف الصلب     = الدرجة **التي تليها**
#
# منصوصة: 1.41 ⇒ 1.618 · 1.618 ⇒ 2.00 · 2.00 ⇒ 2.24
# و2.24 ⇒ **2.618** ✅ أكّدها المستخدم (2026-09-05): قال المدرّب «618»
# والتفريغ لا يميّز 1.618 من 2.618، و1.618 مستحيل لأنه يقع في الجهة
# الرابحة. **H2 مغلق.**
LADDER: Tuple[float, ...] = (1.13, 1.41, 1.618, 2.00, 2.24, 2.618)

STOP_LADDER: Dict[float, Optional[float]] = {
    1.13: 1.41,
    1.41: 1.618,
    1.618: 2.00,
    2.00: 2.24,
    2.24: 2.618,
}


def _next_rung(ratio: float) -> Optional[float]:
    """الدرجة التالية في السلّم — أو None عند طرفه."""
    for i, r in enumerate(LADDER):
        if abs(r - ratio) < 1e-9:
            return LADDER[i + 1] if i + 1 < len(LADDER) else None
    return None

# «بتحط عندك نسب 0.382 · 0.5 · 0.618» + «بدك هدف سريع حط الـ0.236»
TARGET_RATIOS: Tuple[float, ...] = (0.382, 0.5, 0.618)
FAST_TARGET_RATIO = 0.236


class PatternRejected(ValueError):
    """تصحيح خارج الجدول — «ما في تصحيح وما في استهداف»."""


def extension_for(retrace: float) -> float:
    """
    امتداد D المقابل لنسبة تصحيح C — من الجدول لا بالاجتهاد.

    يرفع `PatternRejected` تحت 0.382 (منصوص) وفوق أعلى نطاق في الجدول
    (لأن ما بعده **لم يُعطَ**، وليس لأنه ممنوع — والفرق مذكور في الرسالة).
    """
    if retrace < MIN_RETRACE:
        raise PatternRejected(
            f"التصحيح {retrace:.3f} تحت 0.382 — "
            "«أقل نسبة مسموح يصحح فيها هي 0.382، اذا نزل تحت ما في نموذج»"
        )
    tops = [t for t, _ in EXTENSION_TABLE]
    i = bisect_right(tops, retrace - 1e-12)
    if i >= len(EXTENSION_TABLE):
        raise PatternRejected(
            f"التصحيح {retrace:.3f} فوق آخر نطاق في الجدول ({tops[-1]}) — "
            "الجدول الكامل لم يصل (H1)، ولا يُخمَّن امتداد"
        )
    return EXTENSION_TABLE[i][1]


@dataclass(frozen=True)
class FastLightning:
    """
    نموذج برق سريع مكتمل الحساب — **قبل** بلوغ السعر نقطة الدخول.

    `direction` اتجاه **الصفقة** لا اتجاه الضلع الأول:
    شراءٌ حين تكون D تحت C، وبيعٌ حين تكون فوقها.
    """

    a: Swing
    b: Swing
    c: Swing
    retrace: float
    extension: float
    timeframe: str

    @property
    def direction(self) -> Direction:
        # A قمة ⇒ B قاع ⇒ C قمة ⇒ D تحت ⇒ شراء
        return "bullish" if self.a.is_high else "bearish"

    @property
    def leg_bc(self) -> float:
        """مدى الضلع B→C — وهو ما يُضرب في نسبة الامتداد."""
        return abs(self.c.price - self.b.price)

    @property
    def entry(self) -> float:
        """
        نقطة D — «هي نقطة الدخول عندي».

        تُسقَط من C في اتجاه الضلع A→B (أي مواصلةً لا ارتدادًا).
        """
        step = self.leg_bc * self.extension
        return self.c.price - step if self.direction == "bullish" else self.c.price + step

    def _project(self, ratio: Optional[float]) -> Optional[float]:
        if ratio is None:
            return None
        step = self.leg_bc * ratio
        return self.c.price - step if self.direction == "bullish" else self.c.price + step

    @property
    def stop(self) -> Optional[float]:
        """
        وقف المدرّب — الدرجة التالية في السلّم.

        ⚠️ **يُنفَّذ بالإغلاق لا باللمس**: «طالما جسم الشمعة [فوق]
        المستوى ما في وقف خسارة». فهو مستوى **مراقَبة**، لا أمرٌ عند
        الوسيط. انظر `HARMONIC_STOP_ON_CLOSE`.
        """
        return self._project(STOP_LADDER.get(self.extension))

    @property
    def hard_stop(self) -> Optional[float]:
        """
        ⭐ **شبكة الأمان** — الدرجة التي تلي وقف الإغلاق.

        قرار المستخدم (2026-09-05): «ضع وقفًا صلبًا خلفه».

        **ولماذا درجةً كاملةً لا هامشًا صغيرًا:** وقفُ الإغلاق موضوعٌ
        أصلًا **ليحتمل الذيول** — «الذيل منه وقف خسارة». فوقفٌ صلب
        قريبٌ منه يُضرب بالذيل نفسه الذي جيء بالقاعدة لتجاوزه، فيُبطلها
        بدل أن يحميها. والدرجة التالية مسافةٌ من هندسة النموذج نفسه،
        تتّسع باتّساعه.

        ⚠️ `None` عند الدخول من **2.24**: وقف إغلاقه 2.618 وهو **طرف
        السلّم**، فلا درجة بعده. ولا تُخترَع — انظر `protected`.
        """
        return self._project(_next_rung(STOP_LADDER.get(self.extension) or -1.0))

    @property
    def protected(self) -> bool:
        """
        هل للصفقة شبكة أمان؟

        صفقةٌ لا تُحمى لا تُؤخذ — والنموذج يُعرَض مع ذلك، لأن الرصد
        غير الدخول. الوحيد غير المحميّ هو الدخول من 2.24 (نطاق التصحيح
        0.382–0.48): سلّم المدرّب ينتهي دونه. 🔴 **H5**
        """
        return self.hard_stop is not None

    def risk(self) -> Optional[float]:
        """أقصى خسارة ممكنة — من الدخول إلى **الوقف الصلب** لا وقف الإغلاق."""
        h = self.hard_stop
        return None if h is None else abs(h - self.entry)

    def targets(self, include_fast: bool = False) -> List[float]:
        """
        «التارجت **من الـC إلى نقطة الدخول**» — لا إلى الوقف.

        نبّه على هذا صراحةً، وهي زلّة سهلة: الوقف أبعد من D، فلو قيست
        منه لتضخّمت كل الأهداف.
        """
        span = self.entry - self.c.price          # موجب هبوطًا، سالب صعودًا
        ratios = ((FAST_TARGET_RATIO,) if include_fast else ()) + TARGET_RATIOS
        return [self.entry - span * r for r in ratios]

    def stop_distance(self) -> Optional[float]:
        s = self.stop
        return None if s is None else abs(s - self.entry)

    def invalidated_by(self, series: Series, upto: Optional[int] = None) -> Optional[int]:
        """
        أول شمعة تكسر C **قبل** بلوغ D ⇒ النموذج باطل.

            «اذا في حال قبل ما يوصل لمنطقة الارتداد **طلع كسر الـC** —
             فهو **نموذج يُلغى**»

        يرجع فهرس شمعة الإبطال، أو None. ويتوقّف عند بلوغ D: بعده
        النموذج قد عمل، ولم يعد كسر C إبطالًا.
        """
        stop_at = len(series) if upto is None else min(len(series), upto)
        for i in range(self.c.index + 1, stop_at):
            k = series[i]
            reached = k.low <= self.entry if self.direction == "bullish" else k.high >= self.entry
            if reached:
                return None
            beyond = k.high > self.c.price if self.direction == "bullish" else k.low < self.c.price
            if beyond:
                return i
        return None

    def render(self) -> str:
        side = "شراء" if self.direction == "bullish" else "بيع"
        stop = f"{self.stop:g}" if self.stop is not None else "—"
        hard = f"{self.hard_stop:g}" if self.protected else "لا شبكة أمان ⇒ لا تُؤخذ"
        tps = " · ".join(f"{t:g}" for t in self.targets())
        return (
            f"برق سريع {side} · تصحيح {self.retrace * 100:.1f}% "
            f"⇒ امتداد {self.extension:g} · دخول {self.entry:g} "
            f"· وقف إغلاق {stop} · وقف صلب {hard} · أهداف {tps}"
        )


def measure_retrace(a: Swing, b: Swing, c: Swing) -> float:
    """
    كم صحّحت الموجة C من الضلع A→B؟

    «امتداد الـB للقاع اللي وصلت عليه الموجة C هي نسبة التصحيح»
    """
    leg = abs(b.price - a.price)
    if leg <= 0:
        raise ValueError("ضلع A→B بلا مدى")
    return abs(c.price - b.price) / leg


def build(a: Swing, b: Swing, c: Swing, timeframe: str) -> FastLightning:
    """
    يبني النموذج من ثلاث نقاط سوينج متعاقبة ومتناوبة (قمة/قاع/قمة).

    ⚠️ لا يُبنى نموذجٌ «ضعيف»: التصحيح خارج الجدول يرفع `PatternRejected`
    — لأن النصّ يقول «**ما في نموذج**» لا «نموذج أضعف».
    """
    if not (a.index < b.index < c.index):
        raise ValueError("النقاط يجب أن تكون متعاقبة زمنيًّا: A ثم B ثم C")
    if a.kind == b.kind or b.kind == c.kind:
        raise ValueError("النقاط يجب أن تتناوب: قمة ثم قاع ثم قمة (أو العكس)")

    retrace = measure_retrace(a, b, c)
    return FastLightning(
        a=a, b=b, c=c,
        retrace=retrace,
        extension=extension_for(retrace),
        timeframe=timeframe,
    )


def find_patterns(
    series: Series,
    swings: Sequence[Swing],
    limit: Optional[int] = None,
) -> List[FastLightning]:
    """
    يمسح كل ثلاثية سوينج متناوبة ويبني ما يقبله الجدول.

    ما يُرفض يُسقَط صامتًا — الرفض هنا هو **القاعدة العاملة**، لا خطأ:
    أغلب الثلاثيات لا تصحّح ضمن النطاق.

    ⚠️ `swings` تأتي من `find_swings`، وقد تحمل قمةً وقاعًا **لنفس
    الشمعة** (شمعة خارجية). فتُصفّى الثلاثيات غير المتناوبة أو غير
    المتعاقبة قبل البناء.
    """
    alternating: List[FastLightning] = []
    ordered = sorted(swings, key=lambda s: (s.index, s.kind))

    for i in range(len(ordered) - 2):
        a, b, c = ordered[i], ordered[i + 1], ordered[i + 2]
        if not (a.index < b.index < c.index):
            continue
        if a.kind == b.kind or b.kind == c.kind:
            continue
        try:
            alternating.append(build(a, b, c, series.timeframe))
        except (PatternRejected, ValueError):
            continue

    if limit is not None:
        alternating = alternating[-limit:]
    return alternating


def active(
    series: Series,
    patterns: Sequence[FastLightning],
) -> List[FastLightning]:
    """النماذج التي لم تُبطَل بكسر C — «كسر السي تغيّرت الحسابات»."""
    return [p for p in patterns if p.invalidated_by(series) is None]
