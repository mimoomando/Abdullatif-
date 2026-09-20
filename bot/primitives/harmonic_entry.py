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
from typing import List, Literal, Optional, Sequence

from ..data import Series
from .harmonic import FastLightning, active, find_patterns
from .swings import Swing

Direction = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class HarmonicEntry:
    """دخولٌ هارمونيّ جاهز — D ووقفُه الصلب."""

    pattern: FastLightning
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
    found = active(confirm_series, find_patterns(confirm_series, swings))
    out: List[HarmonicEntry] = []
    for p in found:
        if p.direction != direction or not p.protected:
            continue
        if not _inside(p.entry, zone_bottom, zone_top, tolerance):
            continue
        hard = p.hard_stop
        assert hard is not None                # مضمونٌ بـ`protected`
        # الوقف في الجهة الخاسرة — وهندسةُ النموذج تضمنها، والفحص تأمين
        if direction == "bullish" and hard >= p.entry:
            continue
        if direction == "bearish" and hard <= p.entry:
            continue
        out.append(HarmonicEntry(pattern=p, entry=p.entry, stop=hard))
    return out


def best(
    confirm_series: Series,
    swings: Sequence[Swing],
    direction: Direction,
    zone_bottom: float,
    zone_top: float,
    tolerance: float = 0.0,
) -> Optional[HarmonicEntry]:
    """
    أضيقُ دخولٍ هارمونيّ داخل المنطقة — أو `None`.

    ⭐ **والأضيقُ هو المختار** لأنّ الغرض المنصوص من التدرّج في
    الأطر هو **تصغير الوقف**: «بلا ترابط 110 نقطة · على الساعة 590 ·
    بترابط الفريمات **10 نقاط**».
    """
    found = candidates(confirm_series, swings, direction,
                       zone_bottom, zone_top, tolerance)
    if not found:
        return None
    return min(found, key=lambda h: h.risk)
