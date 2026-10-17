"""
نموذج الجارتلي — **أقدمُ نماذج الهارمونيك، ووصل درسُه 2026-10-17.**

╔══════════════════════════════════════════════════════════════════╗
║  ⭐⭐⭐ **والنصُّ يسمّيه الدرسَ الأخير في المدرسة:**                  ║
║                                                                  ║
║    «الدرس السابع **والاخير** من مدرسه الهارمونيك ومع نموذج         ║
║     الجارتلي **اقدم نماذج** مدرسه الهارمونيك»                     ║
║                                                                  ║
║  ⇒ فصارت السلسلةُ عندنا كاملةً: برق سريع · خفّاش · فراشة ·         ║
║  ألت-بات · كراب · ديب كراب · قرش · **وهذا**.                     ║
╚══════════════════════════════════════════════════════════════════╝

⛔⛔⛔ **وهو غيرُ موصول** — كبقيّة الهارمونيك. **والهارمونيك مُعطَّلٌ
بقياس** (`harmonic_enabled = False` — خسر 21.30$) ⇒ **فلا قرارَ
يتغيّر بهذا الملفّ، ولا رقمٌ منشورٌ يتحرّك.**

⚠️⚠️ **وشكلُه شكلُ `bat.py` بعينه** (XABCD · تصحيحُ B · تصحيحُ C ·
امتدادُ B→D · D نسبةً من XA) — **ولم يُدمج الملفّان**: فعرفُ المشروع
المكتوب **ملفٌّ لكلّ نموذج** (`bat` · `butterfly` · `altbat` …)،
**ومخالفتُه هنا وحدَها تجعل هذا الملفَّ شاذًّا.** ⇒ **والتكرارُ
معلَنٌ لا مخفيّ**، ودمجُ الثلاثة قرارٌ منهجيٌّ يُطلَب.

⭐⭐ **ومعه جاء سندٌ ثانٍ لأربعة أرقامٍ مبنيّةٍ عندنا — فُحصت كلُّها:**

| الرقم عندنا | وما قاله هذا الدرس | الحكم |
|---|---|---|
| `harmonic.MIN_RETRACE = 0.382` | «وهو **الحد الادنى لكل نماذج الهارمونيك** مع عدا شارك» | ✅ مطابق |
| `bat.B_RETRACE = (0.382, 0.58)` | «البات مسموح يصحح البي … **0.58 اكثر شيء**» | ✅ مطابق |
| `bat.BD_EXTENSION = (1.618, 2.618)` | «نموذج خفاش اللي هو حدوده بين **1.618 الى 2.618**» | ✅ مطابق |
| `butterfly.AB_RETRACE = (0.75, 0.82)` و`AB_TOLERANCE = 0.03` | «**0.75 اقل شيء** والنسبه العليا هي **0.82** مسموح توصل ل **0.85**» | ✅ مطابق — **و0.85 = 0.82 + 0.03 بعينها** |

⇒ ⭐⭐⭐ **فأربعةُ أرقامٍ صارت منصوصةً في موضعين** — كـOB1 وOB3.
**ولا واحدٌ منها احتاج تصحيحًا.** ⚠️ **وفُحص الكودُ قبل أن يُكتب هذا
الجدول** — درسُ OB3/BK3: [يُفتح الملفُّ قبل أن يُكتب حكمٌ من غياب].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple

from ..data import Series
from .harmonic import (DEFAULT_SCAN, FAST_TARGET_RATIO, PatternRejected,
                       TARGET_RATIOS, _groups, prz_from)
from .swings import Swing

Direction = Literal["bullish", "bearish"]


# ─────────────────────────── النسب ───────────────────────────
#
# «لهذا السبب شوف **النسب مقدسه** خلص عندك اقل نسبه خمسه س التزم فيها»

#: أدنى تصحيحٍ لـB من الضلع XA — «نسبه التصحيح لموجه B من الموجه
#: اكس اي هي **اقلها 0.586**»
B_RETRACE_FLOOR = 0.586

# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⛔⛔⛔ **والحدُّ الأعلى قيل مرّتين برقمين — فيبقى `UNDEFINED`.**     ║
# ║                                                                  ║
# ║    2:45  «اقلها 0.586 **الى 0.664** 664»                         ║
# ║    4:45  «وعننا اكثر شيء ممكن يصحح هو **0.646** 6 4 6 هي         ║
# ║           النسبه ممنوع نلعب فيها نهائي»                           ║
# ║                                                                  ║
# ║  ⇒ **وهما في الدرس نفسِه، والفرقُ 0.018.** ⛔ **ولا يُختار        ║
# ║  أحدُهما** (القاعدة ①: الرقمُ الذي لا مصدرَ قاطعٌ له لا يُملأ       ║
# ║  بالتخمين) — **ولا يُؤخَذ الأوسعُ ولا الأضيقُ احتياطًا**، فكلٌّ      ║
# ║  منهما اختيارٌ مني.                                               ║
# ║                                                                  ║
# ║  ⇒ **فيُطلَب صريحًا** كما طُلبت `trendline.max_deviation` يوم     ║
# ║  10-16: **مَن طلب نموذجًا بلا أن يقول أيَّ قراءةٍ يعني، طلبَ بلا   ║
# ║  معنًى.** ⚠️ **ولا تُقبل قيمةٌ ثالثة** — فالثالثةُ اختراع.         ║
# ╚══════════════════════════════════════════════════════════════════╝
#: قراءتان **مسمّاتان** للحدّ الأعلى — 🔴 UNDEFINED · ولا افتراضَ لها
B_RETRACE_TOP_READINGS: Tuple[float, ...] = (0.646, 0.664)

#: ⚠️ استثناءٌ **منصوصٌ ومحفوفٌ بتحفّظه** — «الاستثناء هي نسبه 0.586
#: ممكن تتاخذ على **0.52** 52 ما في مشكله **ولكن بيبقى دائما في
#: خطوره وخاصه مع جارتلي**»
B_RETRACE_RISKY_FLOOR = 0.52

#: تصحيح C من الضلع AB — «ممنوع تكون اقل من 0.382 … فهون عننا بين
#: 0.382 الى 0.886»
C_RETRACE = (0.382, 0.886)

#: D — «نقطه اللي بحددها هو اكس على 0.786»
D_RETRACE = 0.786

# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⭐⭐⭐ **وهذا الحدُّ وحدَه بلا سماحيّة — والنصُّ يقول لماذا.**        ║
# ║                                                                  ║
# ║    «اذا B 1.130 الى **1.610 بالضبط ممنوع هي النسبه ممنوع         ║
# ║     تتغير** … ليه 610 بالضبط **لانه اذا في حال صارت 618          ║
# ║     تغيرت صار عندك نموذج خفاش**»                                  ║
# ║                                                                  ║
# ║  ⇒ **فالحدُّ فاصلٌ بين نموذجين لا سماحيّةَ قياس**: 1.618 هو        ║
# ║  **أرضُ الخفّاش** (`bat.BD_EXTENSION[0]`). ⇒ **وتوسيعُه 0.010    ║
# ║  كما في الخفّاش يجعل النموذجين يتداخلان** — وهو ما ينفيه النصّ.   ║
# ║  ⚠️ **ولذلك `BD_TOLERANCE = 0.0` وليست سهوًا.**                   ║
# ╚══════════════════════════════════════════════════════════════════╝
BD_EXTENSION = (1.130, 1.610)
BD_TOLERANCE = 0.0

#: الوقف — «نقطه وقف الخساره هي **واحد على صفر عند الاكس** ما في داعي
#: انك انت تحددها وهي واضحه بالعين المجرده»
STOP_RETRACE = 1.0

# سماحية عدديّة بحتة — لا توسيعًا للنطاق (نسخةُ `bat._EPS` بحجّتها)
_EPS = 1e-9


@dataclass(frozen=True)
class Gartley:
    """
    نموذج جارتلي مستوفٍ لنسبه — **و`risky` رايةٌ لا رفض.**

    النقاط سوينج كبقيّة المدرسة، و D محسوبةٌ لا مرصودة.
    """

    x: Swing
    a: Swing
    b: Swing
    c: Swing
    b_retrace: float
    c_retrace: float
    bd_extension: float
    timeframe: str
    #: ⚠️ تصحيحُ B دون 0.586 وفوق 0.52 — **مقبولٌ بنصّه ومحفوفٌ
    #: بتحفّظه**، فيُحمَل مع النموذج ولا يُكتَم (عرفُ VL1).
    risky: bool = False
    #: أيُّ قراءةٍ للحدّ الأعلى بُني عليها — **يُحمَل كي لا يُنسى**
    b_top: float = 0.0

    @property
    def direction(self) -> Direction:
        """X قمة ⇒ بيع (شكل M) · X قاع ⇒ شراء (شكل W) — كالخفّاش."""
        return "bearish" if self.x.is_high else "bullish"

    @property
    def leg_xa(self) -> float:
        return self.x.price - self.a.price

    @property
    def entry(self) -> float:
        """D — ارتداد 0.786 من A نحو X."""
        return self.a.price + self.leg_xa * D_RETRACE

    @property
    def stop(self) -> float:
        """
        **عند X بعينها** — «واحد على صفر عند الاكس».

        ⚠️⚠️ **ويقول إنّه كبير، ويعطي الرقم**: «الستوب تبعه كبير مش
        مثل البات نسبه قليله لا هون نسبه عم نحكي **تقريبا 25% من قيمه
        الصفقه**». ⇒ **فهو تحفُّظٌ منصوصٌ على النموذج نفسِه**، ولا
        يُقرأ عيبًا في الكود.
        """
        return self.a.price + self.leg_xa * STOP_RETRACE

    @property
    def risk(self) -> float:
        return abs(self.stop - self.entry)

    def targets(self, include_fast: bool = False) -> List[float]:
        """**من A إلى D** — «تحقيق الاهداف هي من نقطه A الى دي»."""
        span = self.a.price - self.entry
        ratios = ((FAST_TARGET_RATIO,) if include_fast else ()) + TARGET_RATIOS
        return [self.entry + span * r for r in ratios]

    def prz(self) -> Tuple[float, float]:
        """
        منطقةُ الانعكاس المحتملة — **وفي الجارتلي تطابق الدخولَ عادةً.**

            «وعننا البي ارزدش ريسون اللي هي نقطه الانعكاس المحتمله
             عليه **اغلب الاوقات بنموذج الجارتلي بتطابق منطقه الدخول**
             مش على عكس غير نماذج»

        ⇒ **وهو فرقٌ منصوصٌ عن بقيّة المدرسة**، ويُرجَع للعرض لا
        للدخول — والدخولُ عند D، كما في `bat.prz`.
        """
        return prz_from(self.a.price, self.b.price)

    def invalidated_by(self, series: Series,
                       upto: Optional[int] = None) -> Optional[int]:
        """كسر C قبل بلوغ D ⇒ النموذج باطل — قاعدةُ المدرسة كلِّها."""
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
        tail = "  ⚠️ تصحيحٌ دون 0.586 — «بيبقى في خطوره»" if self.risky else ""
        return (
            f"جارتلي {side} · B {self.b_retrace:.3f} (سقف {self.b_top:g}) "
            f"· C {self.c_retrace:.3f} · BD {self.bd_extension:.3f} "
            f"· دخول {self.entry:g} · وقف {self.stop:g} · أهداف {tps}{tail}"
        )


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        raise ValueError("ضلع بلا مدى")
    return abs(numerator) / abs(denominator)


def build(x: Swing, a: Swing, b: Swing, c: Swing, timeframe: str,
          b_top: Optional[float] = None,
          allow_risky: bool = False) -> Gartley:
    """
    يبني جارتلي من أربع نقاط سوينج — و D محسوبة.

    ⛔ **و`b_top` يُطلَب ولا يُفترَض** — انظر رأس الملفّ:
    **قيلت قراءتان في الدرس نفسِه**، واختيارُ إحداهما عني اختراع.

    ⚠️ **و`allow_risky` مطفأٌ افتراضًا**: الاستثناءُ `0.52` منصوصٌ
    **ومعه تحفُّظُه**، فإشعالُه قرارُ من يستدعي — **ولا يُشعَل صامتًا.**
    """
    if b_top is None:
        raise ValueError(
            "⛔ الجارتلي بلا `b_top` — والدرسُ يقول "
            f"{B_RETRACE_TOP_READINGS[0]} في موضعٍ و"
            f"{B_RETRACE_TOP_READINGS[1]} في موضعٍ آخر منه. "
            "⇒ فسمِّ القراءةَ التي تقيسها (القاعدة ①)")
    if b_top not in B_RETRACE_TOP_READINGS:
        raise ValueError(
            f"⛔ سقفٌ غيرُ منصوص: {b_top!r} — والمنصوصُ "
            f"{B_RETRACE_TOP_READINGS}. **وقيمةٌ ثالثةٌ اختراع.**")

    if not (x.index < a.index < b.index < c.index):
        raise ValueError("النقاط يجب أن تتعاقب: X ثم A ثم B ثم C")
    if x.kind != b.kind or a.kind != c.kind or x.kind == a.kind:
        raise ValueError("النقاط يجب أن تتناوب: X و B من جنس، "
                         "و A و C من الجنس الآخر")

    b_r = _ratio(b.price - a.price, x.price - a.price)
    risky = False
    if b_r > b_top + _EPS:
        raise PatternRejected(
            f"تصحيح B = {b_r:.3f} فوق السقف {b_top} — "
            "«هي النسبه ممنوع نلعب فيها نهائي»")
    if b_r < B_RETRACE_FLOOR - _EPS:
        if not (allow_risky and b_r >= B_RETRACE_RISKY_FLOOR - _EPS):
            raise PatternRejected(
                f"تصحيح B = {b_r:.3f} دون {B_RETRACE_FLOOR} — "
                f"والاستثناءُ المنصوصُ {B_RETRACE_RISKY_FLOOR} "
                "ويلزمه `allow_risky`")
        risky = True

    c_r = _ratio(c.price - b.price, a.price - b.price)
    if not (C_RETRACE[0] - _EPS <= c_r <= C_RETRACE[1] + _EPS):
        raise PatternRejected(
            f"تصحيح C = {c_r:.3f} خارج {C_RETRACE[0]}–{C_RETRACE[1]} — "
            "«كل ما طلعنا فوق ال 0.886 في خطوره لفشل النموذج»")

    entry = a.price + (x.price - a.price) * D_RETRACE
    bd = _ratio(entry - c.price, c.price - b.price)
    if not (BD_EXTENSION[0] - BD_TOLERANCE <= bd
            <= BD_EXTENSION[1] + BD_TOLERANCE):
        raise PatternRejected(
            f"امتداد B→D = {bd:.3f} خارج {BD_EXTENSION[0]}–"
            f"{BD_EXTENSION[1]} — «1.610 بالضبط ممنوع تتغير»، "
            "و1.618 أرضُ الخفّاش")

    return Gartley(x=x, a=a, b=b, c=c, b_retrace=b_r, c_retrace=c_r,
                   bd_extension=bd, timeframe=timeframe, risky=risky,
                   b_top=b_top)


def find_patterns(series: Series, swings: Sequence[Swing],
                  b_top: Optional[float] = None,
                  scan: str = DEFAULT_SCAN,
                  allow_risky: bool = False) -> List[Gartley]:
    """
    يمسح الرباعيّاتِ من سوينج متناوبة ويبني ما تقبله النسب.

    ⚠️ **والمسحُ `adjacent` افتراضًا** — وهو حدُّ HA1/BT2 المسجَّل،
    و`scan="all"` هو العمودُ الثاني في `--rule harmonic-scan`.
    ⇒ **فلا يُكتب هنا [يمسح كلّ رباعيّة]**، وهي العبارةُ التي صُحّحت
    في `harmonic` و`bat` و`butterfly` ثلاثَ مرّات.
    """
    out: List[Gartley] = []
    ordered = sorted(swings, key=lambda s: (s.index, s.kind))

    for group in _groups(ordered, 4, scan):
        x, a, b, c = group
        if any(group[k].index >= group[k + 1].index for k in range(3)):
            continue
        if any(group[k].kind == group[k + 1].kind for k in range(3)):
            continue
        try:
            out.append(build(x, a, b, c, series.timeframe, b_top=b_top,
                             allow_risky=allow_risky))
        except PatternRejected:
            continue
        except ValueError:
            raise          # ⬅ ⛔ سقفٌ غير مسمًّى عطبُ نداءٍ لا رفضُ نموذج
    return out


def active(series: Series, patterns: Sequence[Gartley]) -> List[Gartley]:
    """النماذج التي لم تُبطَل بكسر C."""
    return [p for p in patterns if p.invalidated_by(series) is None]
