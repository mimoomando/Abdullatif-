"""
وصلُ الهارمونيك بالسلسلة — **تأكيدًا، لا استراتيجيّةً موازية.**

╔══════════════════════════════════════════════════════════════════╗
║  والنصّ يحدّد موضعَه بالضبط:                                       ║
║                                                                  ║
║    «عندك **نقطة اهتمام من ربع ساعة**، فأنا على الدقيقة أو ثلاث    ║
║     دقائق باخذ موجة، **نقطة انعكاس على الهارمونيك، منها بأكّد**…  ║
║     ومنها بياخذ تأكيد وبننطلق نحو الهدف»                          ║
║                                                                  ║
║    «نصيحتي لك انه انت لما بدك تحدد نقاط انعكاس اهتمام **حاول      ║
║     تبدا من أوردر بلوك**… بيساعدك بشكل كثير مهم»                  ║
╚══════════════════════════════════════════════════════════════════╝

⇒ فهو **لا يولّد نقطة الاهتمام ولا يستبدلها**. نقطةُ الاهتمام تبقى من
الإطار الأكبر كما في السلسلة، والهارمونيك يُبنى على **الإطار المقابل**
ويعطي موضعَ الدخول ووقفَه — كما يفعل النموذج الانعكاسيّ في `refine.py`.

⭐ **وأثرُه محصورٌ في الدخول والوقف.** الأهدافُ تبقى من السيولة
الخارجيّة بسقف 1:3، لأنّ النصّ يقول «ومنها بياخذ تأكيد **وبننطلق نحو
الهدف**» — الهدفُ هدفُ السلسلة، والهارمونيك طريقُ الوصول إليه.

⚠️⚠️ **وشرطُ الاحتواء استنتاجٌ لا نصّ.** قولُه «عندك نقطة اهتمام…
منها بأكّد» يضع النموذجَ **عند** نقطة الاهتمام، فاشترطتُ وقوعَ D
داخلها. وهو ما تشترطه `refine.candidates` على النماذج الكلاسيكيّة
بالحجّة نفسها. 🔶 **يُقاس، ولا يُدَّعى.**
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Sequence, Tuple

from ..data import Series
from .harmonic import (DEFAULT_SCAN, FastLightning, active,
                       find_patterns)
from .swings import Swing

Direction = Literal["bullish", "bearish"]


# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⭐⭐⭐ **عائلاتُ النماذج — بُنيت 2026-10-17 بطلب المستخدم**        ║
# ║  [اكمل وصل الوحدات]، **ومطفأةً إلّا القائمة.**                    ║
# ║                                                                  ║
# ║  فـ`bat` و`butterfly` كانتا في `UNWIRED` **ولا يستوردهما حتّى     ║
# ║  `harmonic.py` نفسُه**، ووصل درسُ `gartley` يوم 10-17.            ║
# ║  ⇒ **وهذا هو مدخلُهنّ الثلاث**: مكانٌ واحدٌ يجمع المدرسةَ كلَّها،   ║
# ║  لا ثلاثةُ أبواب.                                                 ║
# ║                                                                  ║
# ║  ⛔ **ولا سلوكَ يتغيّر بحرف**: الافتراضُ `("lightning",)` وهو      ║
# ║  ما كان يُمسَح وحدَه، **والهارمونيك كلُّه مُعطَّلٌ بقياس**            ║
# ║  (`harmonic_enabled = False` — خسر 21.30$). ⇒ **فالأثرُ          ║
# ║  المتوقَّع `+0` إعداد، ويُقال سلفًا** كي لا يُقرأ التطابقُ          ║
# ║  تأكيدًا (شكلُ PT1).                                              ║
# ║                                                                  ║
# ║  ⚠️⚠️ **وما يسوّغ الجمعَ أنّ الدخولَ والوقفَ وحدَهما ما يُقرأ        ║
# ║  منها** — فـ`candidates` لا تسأل النموذجَ عن شيءٍ آخر:            ║
# ║  البرقُ السريعُ يعطي `hard_stop` **إن كان محميًّا**، والثلاثةُ      ║
# ║  الباقية **وقفُها منصوصٌ بنسبته** (خلف X أو امتدادًا) ⇒           ║
# ║  **فهي محميّةٌ بالبناء لا بالفحص.**                               ║
# ╚══════════════════════════════════════════════════════════════════╝

#: أسماءُ العائلات — ولكلٍّ وحدتُها ودرسُها
FAMILIES: Tuple[str, ...] = ("lightning", "bat", "butterfly", "gartley")

#: ⬅ القائم · USER — وهو ما كان يُمسَح وحدَه قبل 10-17
DEFAULT_FAMILIES: Tuple[str, ...] = ("lightning",)


@dataclass(frozen=True)
class HarmonicEntry:
    """
    دخولٌ هارمونيّ جاهز — D ووقفُه الصلب.

    ⚠️ **و`pattern` صار `Any` يوم 10-17** لأنّه قد يكون من أيّ عائلةٍ
    في `FAMILIES` — **والمقروءُ منه `entry` و`stop` وحدَهما**،
    و`render()` للعرض. ⇒ **فالتوسيعُ في النوع لا في المقروء.**
    """

    pattern: Any
    entry: float
    stop: float

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)

    def render(self) -> str:
        p = self.pattern
        return (f"برق سريع {p.timeframe} · تصحيح {p.retrace * 100:.1f}% "
                f"⇒ امتداد {p.extension:g} · دخول {self.entry:.2f} "
                f"· وقف صلب {self.stop:.2f} (مخاطرة {self.risk:.2f}$)")


def _inside(price: float, bottom: float, top: float, tolerance: float) -> bool:
    return (bottom - tolerance) <= price <= (top + tolerance)


def candidates(
    confirm_series: Series,
    swings: Sequence[Swing],
    direction: Direction,
    zone_bottom: float,
    zone_top: float,
    tolerance: float = 0.0,
    scan: str = DEFAULT_SCAN,
    families: Sequence[str] = DEFAULT_FAMILIES,
    gartley_b_top: Optional[float] = None,
) -> List[HarmonicEntry]:
    """
    النماذج الهارمونيّة الصالحة **داخل** نقطة الاهتمام.

    وتُرشَّح بأربعة شروط، كلُّها منصوصة إلّا الرابع:

    | | الشرط | المصدر |
    |---|---|---|
    | ١ | التصحيح داخل الجدول | «أقل نسبة 0.382» — يرفضه `build` |
    | ٢ | لم يُكسَر C قبل بلوغ D | «طلع كسر الـC ⇒ نموذج يُلغى» |
    | ٣ | اتّجاهُه اتّجاهُ الهيكل | «إذا انت فايت عكس الترند رح يضربك» |
    | ٤ | D داخل نقطة الاهتمام | 🔶 **استنتاج** — انظر رأس الملفّ |

    ⛔ **وغيرُ المحميّ يُستبعَد**: الدخول من 2.240 وقفُ إغلاقه 2.618 وهو
    طرفُ السلّم، فلا درجةَ بعده ولا وقفَ صلبًا. وقرارُ المستخدم
    (2026-09-05) أنّ الوقف الصلب شرطُ الدخول — فصفقةٌ لا تُحمى لا تُؤخذ.
    """
    out: List[HarmonicEntry] = []
    for p, hard in _found(confirm_series, swings, families, scan,
                          gartley_b_top):
        if p.direction != direction:
            continue
        if not _inside(p.entry, zone_bottom, zone_top, tolerance):
            continue
        # الوقف في الجهة الخاسرة — وهندسةُ النموذج تضمنها، والفحص تأمين
        if direction == "bullish" and hard >= p.entry:
            continue
        if direction == "bearish" and hard <= p.entry:
            continue
        out.append(HarmonicEntry(pattern=p, entry=p.entry, stop=hard))
    return out


def _found(confirm_series: Series, swings: Sequence[Swing],
           families: Sequence[str], scan: str,
           gartley_b_top: Optional[float]) -> List[tuple]:
    """
    النماذجُ القائمةُ من كلّ عائلةٍ مطلوبة — **ومعها وقفُها الصلب.**

    ⛔ **والعائلةُ المجهولةُ تُرفض ولا تُتخطّى صامتةً** — فتخطّيها
    يعطي عمودًا يبدو مقيسًا وليس كذلك.

    ⚠️ **وترتيبُ العائلات ترتيبُ `FAMILIES` لا ترتيبُ الطلب** — كي
    لا يقلب ترتيبُ النداء نتيجةَ `best` عند تساوي المخاطرة.
    """
    from . import bat as _bat
    from . import butterfly as _bf
    from . import gartley as _g

    unknown = [f for f in families if f not in FAMILIES]
    if unknown:
        raise ValueError(f"⛔ عائلةٌ غيرُ معروفة: {unknown} — "
                         f"والمعروفُ {FAMILIES}")

    out: List[tuple] = []
    for family in FAMILIES:
        if family not in families:
            continue
        if family == "lightning":
            for p in active(confirm_series,
                            find_patterns(confirm_series, swings, scan=scan)):
                # ⛔ غيرُ المحميّ يُستبعَد — انظر `candidates`
                if p.protected and p.hard_stop is not None:
                    out.append((p, p.hard_stop))
            continue
        if family == "gartley":
            # ⚠️⚠️ **وهذا الفحصُ زائدٌ لا سلوك — ومقيسٌ بالتجريب
            #   10-17**: نُزع فصمت الطقمُ، **لأنّ `gartley.build`
            #   ترفض بالرسالة نفسِها**، و`chain` ترفض قبلهما عند
            #   الإعداد. ⇒ **فهو ثالثُ سدٍّ على بابٍ واحد**، وفائدتُه
            #   أنّ الرسالةَ تسمّي العائلةَ لا النموذج.
            #   ⛔ **ولا يُخترَع له حارسٌ يوهم بأنّه سلوك.**
            if gartley_b_top is None:
                raise ValueError(
                    "⛔ عائلةُ الجارتلي بلا `gartley_b_top` — "
                    f"والدرسُ يقول {_g.B_RETRACE_TOP_READINGS} "
                    "في موضعين منه. ⇒ فسمِّ القراءة (القاعدة ①)")
            pats = _g.active(confirm_series,
                             _g.find_patterns(confirm_series, swings,
                                              b_top=gartley_b_top,
                                              scan=scan))
        else:
            mod = _bat if family == "bat" else _bf
            pats = mod.active(confirm_series,
                              mod.find_patterns(confirm_series, swings,
                                                scan=scan))
        # ⭐ والثلاثةُ وقفُها منصوصٌ بنسبته ⇒ **محميّةٌ بالبناء**
        out.extend((p, p.stop) for p in pats)
    return out


def best(
    confirm_series: Series,
    swings: Sequence[Swing],
    direction: Direction,
    zone_bottom: float,
    zone_top: float,
    tolerance: float = 0.0,
    scan: str = DEFAULT_SCAN,
    families: Sequence[str] = DEFAULT_FAMILIES,
    gartley_b_top: Optional[float] = None,
) -> Optional[HarmonicEntry]:
    """
    أضيقُ دخولٍ هارمونيّ داخل المنطقة — أو `None`.

    ⭐ **والأضيقُ هو المختار** لأنّ الغرض المنصوص من التدرّج في
    الأطر هو **تصغير الوقف**: [بلا ترابط 110 نقطة · على الساعة 590 ·
    بترابط الفريمات **10 نقاط**].

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⚠️⚠️ **HA3 — وهذا موضعُ RP1 الثاني · كُشف 2026-09-29.**       ║
    ║                                                              ║
    ║  فـ`refine._pick` يختار **أصغرَ مخاطرةٍ دائمًا** كذلك، وهو      ║
    ║  🔴 **المتّهمُ الأوّل** في [لماذا يخسر المنقَّح؟]: المنقَّح خسر   ║
    ║  خمسًا من خمس بأوقافٍ **في نطاق المدرّب بعينه** ⇒ فحجمُ         ║
    ║  الوقف ليس العلّة، **واختيارُ الأصغرِ اختيارٌ للأقربِ إلى        ║
    ║  الكسح كلَّ مرّة**.                                            ║
    ║                                                              ║
    ║  ⇒ **فإن رَدَّ قياسُ `--rule refine-pick` وضعَ `smallest`،      ║
    ║  فهذا السطرُ يُراجَع معه** — وإلّا أُغلق البابُ في موضعٍ         ║
    ║  وبقي مفتوحًا في آخر، وهو صنفُ العطب الذي تكرّر في هذا         ║
    ║  المشروع أربع مرّات.                                          ║
    ║                                                              ║
    ║  ⚠️ **ولا أثرَ له اليوم**: `harmonic_enabled = False`.         ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    found = candidates(confirm_series, swings, direction,
                       zone_bottom, zone_top, tolerance, scan,
                       families, gartley_b_top)
    if not found:
        return None
    return min(found, key=lambda h: h.risk)
