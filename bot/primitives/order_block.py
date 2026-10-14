"""
الأوردر بلوك — الدرس 10 · الدرس 11 · م2/د3 · م2/د4 · درس السيولة.

╔══════════════════════════════════════════════════════════════════╗
║  الثلاثية (الدرس 10) — الشروط الثلاثة بالترتيب:                    ║
║      ١. كسح سيولة من قمة/قاع سابق                                 ║
║      ٢. كسر النقطة الهيكلية الحاكمة — **بالجسم لا بالذيل**         ║
║      ٣. صنع فراغ سعري مع الاندفاع                                 ║
╚══════════════════════════════════════════════════════════════════╝

مؤكَّدة صوتيًا في م2/د3:
    «أوردر بلوك — كيف أوردر بلوك؟ ساحب سيولة، كاسر نقطة هيكل،
     ومشكّل فراغات سعرية»

**النقطة الهيكلية الحاكمة** (الدرس 10):
    في الحالة الصاعدة: القمة التي أنشأت القاع المكسوح.
    في الحالة الهابطة: القاع الذي أنشأ القمة المكسوحة.
    لا أقرب قمة/قاع صغير عشوائي.

**الشمعة المعرِّفة** (الدرس 10):
    أوردر بلوك صاعد = آخر شمعة هابطة قبل الاندفاع الصاعد.
    أوردر بلوك هابط = آخر شمعة صاعدة قبل الاندفاع الهابط.
    Rejection Block = شمعة ذيلها ذو الصلة ≥ جسمها — ولونها لا يهم.

**المنطقة** (م2/د4): المدى الكامل من الأعلى إلى الأدنى، بالذيل.

**السيولة:** الأوردر بلوك **سيولة داخلية** — منطقة دخول لا هدف
(درس السيولة الداخلية والخارجية).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import List, Literal, Optional, Sequence

from ..data import Series
from .fvg import FVG
from .liquidity import Sweep
from .swings import Swing

Direction = Literal["bullish", "bearish"]
State = Literal["fresh", "mitigated", "failed", "breaker"]


@dataclass(frozen=True)
class OrderBlock:
    index: int                 # فهرس الشمعة المعرِّفة
    time: datetime
    direction: Direction
    top: float                 # المدى الكامل — أعلى الشمعة المعرِّفة
    bottom: float              # المدى الكامل — أدنى الشمعة المعرِّفة
    sweep: Sweep
    break_index: int           # الشمعة التي كسرت النقطة الحاكمة بالجسم
    governing_level: float     # النقطة الهيكلية المكسورة
    fvg: FVG
    is_rejection_block: bool
    state: State = "fresh"

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def touched_by(self, candle) -> bool:
        """هل لامست الشمعة المنطقة؟ — اللمس بالمدى لا بالإغلاق."""
        return candle.low <= self.top and candle.high >= self.bottom

    def stop_for(self, buffer: float) -> float:
        """
        الوقف — م2/د3: «أدنى قاع الأوردر بلوك بقليل مشان السبريد».

        صاعد: تحت أدنى المنطقة بمقدار الهامش.
        هابط: فوق أعلى المنطقة بمقدار الهامش.

        الهامش يُحسب بـ`stop_buffer()` — لا يُمرَّر رقمًا مرتجلًا.
        """
        if buffer < 0:
            raise ValueError("الهامش لا يكون سالبًا")
        return self.bottom - buffer if self.direction == "bullish" else self.top + buffer

    @property
    def near_edge(self) -> float:
        """الحدّ الذي يلمسه السعر أوّلًا — أعلى الصاعدة وأدنى الهابطة."""
        return self.top if self.direction == "bullish" else self.bottom

    def entry_for(self, large_threshold: Optional[float] = None) -> float:
        """
        نقطة الدخول — الحدّ القريب، أو **المنتصف** إن كانت المنطقة كبيرة.

        ⭐ منصوص في البثّ ٣ (≈14:41):

            «نفس الأوردر بلوك ولكن **بحجم أصغر**… ونحن قلنا لمّا
             بكون **بهالشكل الكبير بحدّد منطقة المنتصف** لنتعامل مع
             منطقة المنتصف فيها»

        ⚠️ **و«كبير» بلا رقم.** لم يعطِ عتبةً، ولذلك `None` تعني
        «غير مطبَّق» ⇒ الحدّ القريب كما كان. وأيُّ رقمٍ يُمرَّر هنا
        يأتي من `params.OB_LARGE_THRESHOLD` المعلَّق، لا من تقدير.

        ولماذا المنتصف أضيق؟ لأن الوقف يبقى خلف الطرف البعيد، فالدخول
        من المنتصف **ينصّف المخاطرة** — وهو المعنى نفسه الذي يقصده
        بالتدرّج في الأطر: «الغرض من التدرّج تصغير الوقف».
        """
        if large_threshold is None or self.size <= large_threshold:
            return self.near_edge
        return self.midpoint


def stop_buffer(
    spread: float,
    degrees: Optional[float] = None,
    degree_value: Optional[float] = None,
) -> float:
    """
    هامش الوقف تحت حدّ المنطقة.

    مصدران يتكاملان ولا يتعارضان:

      **السبب** — م2/د3: «أدنى قاع الأوردر بلوك بقليل **مشان السبريد**».
      **المقدار** — المستخدم 2026-08-27 على T2: «درجتان».

    فالنتيجة `max(الدرجات × قيمة الدرجة, السبريد)`: المقدار المنصوص عليه
    يحكم، والسبريد أرضية دنيا — لأن هامشًا أضيق من السبريد يُضرب قبل أن
    يتحرك السعر أصلًا، وذلك يناقض سبب وجود الهامش نفسه.

    `degree_value=None` ⇒ الوحدة لم تُحسم بعد، فيرتدّ إلى السبريد وحده
    **صراحةً**. الارتداد الصامت إلى رقم مخترع هو ما يجب تفاديه: الخطأ في
    وحدة الدرجة يضاعف كل وقف مئة مرة.
    """
    if spread < 0:
        raise ValueError("السبريد لا يكون سالبًا")
    if degrees is not None and degrees < 0:
        raise ValueError("الدرجات لا تكون سالبة")

    if degrees is None or degree_value is None:
        return spread

    if degree_value <= 0:
        raise ValueError("قيمة الدرجة يجب أن تكون موجبة")

    return max(degrees * degree_value, spread)


# ─────────────────────────── أدوات داخلية ───────────────────────────


def _is_rejection_candle(candle, direction: Direction) -> bool:
    """
    شمعةٌ ذيلُها ذو الصلة ≥ جسمها. **واللونُ لا يهمّ** — منصوصٌ مرّتين
    في الجملة نفسها (`lesson-16` ≈2:00):

        «فنحن هون **ما بيهمّنا لون الشمعة** بالريجكشن بلوك… الريجكشن
         هو: الشمعة بدها تكون ريجكشن — ساعتها أنا **ما بهتمّ للونها**،
         **بحدّد الشمعة اللي سحبت السيولة** وبمشي»

    و«الذيل أطول من الجسم» في `basics-10` ≈8:25: «الريجكشن بلوك بيكون
    **الذال أطول من الشمعة**».

    ⭐ **والريجكشن صفةٌ عارضةٌ لا نوعٌ رابع** — وذلك منصوصٌ صراحة:
    «الأوردر بلوك العادة في منه عادي **وريجكشن**، الميتيجيشن في منه
    عادي **وريجكشن**، البروبورشن في منه عادي **وريجكشن**». ولذلك هو
    حقلٌ مستقلّ (`is_rejection_block`) لا قيمةٌ في `State` — **وهذا
    مطابقٌ للنصّ**.

    صاعد ⇒ يُنظر إلى الذيل السفلي · هابط ⇒ العلوي.
    """
    wick = candle.lower_wick if direction == "bullish" else candle.upper_wick
    return wick >= candle.body_size


def _defining_candle(series: Series, start: int, end: int, direction: Direction) -> Optional[int]:
    """
    آخر شمعة معاكسة للاندفاع قبله — أو شمعة رفض إن وُجدت أقرب.

    والقاعدةُ العامّة منصوصة: «بناخذ **آخر شمعة حمراء حدث بعدها
    الصعود**» (`lesson-16` ≈1:15).

    ╔══════════════════════════════════════════════════════════════╗
    ║  🔴 **OB1 — وللريجكشن نصٌّ يسمّي شمعةً بعينها. كُشف 2026-09-27.**║
    ║                                                              ║
    ║      «ساعتها أنا ما بهتمّ للونها، **بحدّد الشمعة اللي سحبت**   ║
    ║       **السيولة** وبمشي»                    (لسن 16 ≈2:15)   ║
    ║                                                              ║
    ║  وهذا البحثُ يمشي **للخلف من الكسر**، فيُرجع الأقربَ إليه.     ║
    ║  فلو كانت الشمعةُ **الساحبة** شمعةَ رفضٍ ووُجدت بعدها شمعةٌ     ║
    ║  معاكسةٌ أقربُ إلى الكسر، **فُضِّلت الثانية** — والنصُّ في حال   ║
    ║  الريجكشن يسمّي **الساحبة**.                                  ║
    ║                                                              ║
    ║  ⚠️ **ولم يُغيَّر — والسببُ المنهج لا التردّد.** هذا **مسارٌ     ║
    ║  حيّ**: يقرّر حدَّ المنطقة، ومنه الدخولُ والوقف. و«قِس قبل أن   ║
    ║  تغيّر»: يُقاس بتشغيل النطاق مرّتين (الساحبة أوّلًا مقابل        ║
    ║  الأقرب أوّلًا) ومقارنةِ الحصيلة وحجمِ الوقف — **ولا بُدَّ من**  ║
    ║  **MT5 للقياس**، فلا يُحسم من جلسةٍ سحابيّة.                  ║
    ║                                                              ║
    ║  🔶 ومدى أثره غيرُ معلوم: كم أوردر بلوك من الاثني عشر كانت     ║
    ║  شمعتُه الساحبةُ شمعةَ رفضٍ أصلًا؟ **لم يُحصَ.**                ║
    ╚══════════════════════════════════════════════════════════════╝

    يُبحث للخلف من بداية الاندفاع.
    """
    for i in range(end, start - 1, -1):
        c = series[i]
        opposite = c.bearish if direction == "bullish" else c.bullish
        if opposite or _is_rejection_candle(c, direction):
            return i
    return None


def _governing_point(swings: Sequence[Swing], swept: Swing) -> Optional[Swing]:
    """
    النقطة الهيكلية الحاكمة: آخر قمة/قاع معاكس **قبل** المستوى المكسوح.

    الدرس 10: «the high that established the low» — لا أقرب نقطة صغيرة.
    """
    want_high = swept.is_low
    found = None
    for s in swings:
        if s.index >= swept.index:
            break
        if s.is_high == want_high:
            found = s
    return found


def _body_breaks(series: Series, i: int, level: float, direction: Direction, tol: float) -> bool:
    """الكسر بالجسم لا بالذيل — الدرس 10."""
    c = series[i]
    if direction == "bullish":
        return c.body_top > level + tol
    return c.body_bottom < level - tol


# ─────────────────────────── الكشف ───────────────────────────


def find_order_blocks(
    series: Series,
    swings: Sequence[Swing],
    sweeps: Sequence[Sweep],
    fvgs: Sequence[FVG],
    max_bars_to_break: int = 20,
    break_tolerance: float = 0.0,
) -> List[OrderBlock]:
    """
    يطبّق الثلاثية بالترتيب المنصوص عليه.

    لكل كسح:
      ١. يُحدَّد الاتجاه: كسح تحت قاع ⇒ أوردر بلوك صاعد.
      ٢. تُحدَّد النقطة الحاكمة (القمة التي أنشأت ذلك القاع).
      ٣. يُبحث عن إغلاق **بالجسم** يكسرها خلال max_bars_to_break.
      ٤. يجب أن يصنع الاندفاع فراغًا سعريًا بنفس الاتجاه.
      ٥. تُحدَّد الشمعة المعرِّفة، والمنطقة = مداها الكامل.

    إن سقط شرط سقط الأوردر بلوك كله — لا يُقبل جزئيًا.
    """
    out: List[OrderBlock] = []

    for sw in sweeps:
        direction: Direction = "bullish" if sw.side == "sell_side" else "bearish"

        gov = _governing_point(swings, sw.swept_swing)
        if gov is None:
            continue

        start = sw.reclaim_index
        stop = min(start + max_bars_to_break, len(series))

        break_idx = next(
            (
                i
                for i in range(start, stop)
                if _body_breaks(series, i, gov.price, direction, break_tolerance)
            ),
            None,
        )
        if break_idx is None:
            continue

        gap = next(
            (
                g
                for g in fvgs
                if g.direction == direction and start <= g.index <= break_idx + 2
            ),
            None,
        )
        if gap is None:
            continue

        def_idx = _defining_candle(series, sw.penetration_index, break_idx, direction)
        if def_idx is None:
            continue

        c = series[def_idx]
        out.append(
            OrderBlock(
                index=def_idx,
                time=c.time,
                direction=direction,
                top=c.high,
                bottom=c.low,
                sweep=sw,
                break_index=break_idx,
                governing_level=gov.price,
                fvg=gap,
                is_rejection_block=_is_rejection_candle(c, direction),
            )
        )

    out.sort(key=lambda o: o.index)
    return out


# ─────────────────────────── الحالات ───────────────────────────

# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⛔⛔ **BK1 — نافذةُ الفراغ عند كسر الأوردر بلوك.**                 ║
# ║                                                                  ║
# ║  ⭐ **والرقمان مشتقّان لا مختارَان**: الفراغُ كائنُ **ثلاث شموع**     ║
# ║  وفهرسُه فهرسُ **الثالثة** (`fvg.FVG.index`) ⇒ ففراغٌ فهرسُه `g`     ║
# ║  يغطّي الشموع `g-2 … g`، **وهو يحوي شمعةَ الكسر `b`** إذا وفقط     ║
# ║  إذا `b ≤ g ≤ b+2`. ⇒ **فالنافذةُ `(0, 2)` تعريفُ الفراغ نفسُه**،   ║
# ║  لا رقمًا مرتجلًا (القاعدة ①).                                     ║
# ║                                                                  ║
# ║  ⚠️ **ولها سابقةٌ في المستودع**: `patterns.BREAK_GAP_*` —          ║
# ║  `(-1, +2)` حول كسر خطّ العنق، مسجَّلةٌ في الدفتر بالاسم.           ║
# ╚══════════════════════════════════════════════════════════════════╝
BREAKER_GAP_BEFORE = 0
BREAKER_GAP_AFTER = 2


def opposite(direction: Direction) -> Direction:
    """الجهةُ المقابلة — تُسمّى مرّةً ولا تُكتب شرطًا في كلّ موضع."""
    return "bearish" if direction == "bullish" else "bullish"


def _gap_at_the_break(
    fvgs: Sequence[FVG], failed_at: int, direction: Direction
) -> Optional[FVG]:
    """
    أوّلُ فراغٍ **باتّجاه الكسر** تحوي شموعُه الثلاثُ شمعةَ الكسر.

    ⭐ **واتّجاهُه مشتقٌّ لا مختار**: كسرُ منطقةٍ صاعدةٍ إغلاقٌ **تحت**
    قاعها ⇒ إزاحةٌ هابطة ⇒ فراغٌ هابط. وهو ما في البثّ حرفًا: المنطقةُ
    هناك **هابطة** («اوردر بلوك هابط»)، كُسرت صاعدةً، فصارت دعمًا.
    """
    want: Direction = "bearish" if direction == "bullish" else "bullish"
    lo = failed_at + BREAKER_GAP_BEFORE
    hi = failed_at + BREAKER_GAP_AFTER
    for g in fvgs:
        if g.direction == want and lo <= g.index <= hi:
            return g
    return None


def update_states(
    series: Series,
    blocks: Sequence[OrderBlock],
    fvgs: Optional[Sequence[FVG]] = None,
    require_break_gap: bool = False,
    flip_breaker: bool = False,
) -> List[OrderBlock]:
    """
    يحدّث حالة كل منطقة — الدرس 11 و§7.

        fresh     : لم يعُد إليها السعر بعد
        mitigated : عاد ولامسها
        failed    : أُغلق عبرها **بالجسم** عكس اتجاهها
        breaker   : فشلت **ولم تُخفَّف قبل ذلك** ثم عاد إليها السعر

    «A reaction alone does not prove the block will hold;
     a failed OB can reverse role as a Breaker» (§8)

    ⭐ **شرط عدم التخفيف — منصوص في البثّ المباشر:**

        «نحن قلنا من شروط البريكر إنه **ما بينعمل له تخفيف**.
         **مجرد إنه انعمل تخفيف للأوردر بلوك — ما بقى بريكر**»

    فالمنطقة التي لامسها السعر قبل أن تفشل **لا تصير بريكر أبدًا**:
    سيولتها استُهلكت مرة، فلم يبقَ فيها ما يقلب الدور.

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⛔⛔ **BK1 — والشرطُ الثاني منصوصٌ وكان لا يُفحَص · 10-13.**    ║
    ║                                                              ║
    ║  بثُّ الجمعة يعرّف البريكر بشرطين، لا بشرطٍ واحد:                ║
    ║                                                              ║
    ║    43:52  «هو اوردر بلوك يتم كسره بدون تخفيف»                 ║
    ║    46:13  «اقواها يلي هي ما بيتخفف وش شرط اساسي عند           ║
    ║            كسر الاوردر بلوك تشكل فراغ سعري»                   ║
    ║    46:26  «مش فير فالو جاب بلوس»  ⬅ **وهو يسمّي الكائن**        ║
    ║                                                              ║
    ║  ⭐ **فالفراغُ المطلوبُ فير فاليو جاب** — فلا يُبتدَع له تعريفٌ،  ║
    ║  و`find_fvgs` هي المرجع.                                      ║
    ║                                                              ║
    ║  ⚠️ **و«شرط اساسي» تعني لزومًا لا تدريجَ قوّة** ⇒ فمن لا فراغَ   ║
    ║  عند كسره **يبقى `failed`**، وهي حالةٌ مرفوضةٌ أصلًا.           ║
    ║  ⛔ ومع ذلك **القائمُ `False`** — فالوصلُ تغييرُ سلوكٍ لم         ║
    ║  يُقَس، و[قِس قبل أن تغيّر] تسري على ما له سندٌ كما على غيره.    ║
    ║                                                              ║
    ║  ✅ **ولا يقرأ مستقبلًا**: الفراغُ المطلوبُ قد يكتمل بعد شمعةِ   ║
    ║  العودة بشمعةٍ أو شمعتين، **و`fvgs` مشتقّةٌ من `series`          ║
    ║  المقطوعةِ عند الشمعة الحاليّة** ⇒ فلا يُرى إلّا ما أُغلق.        ║
    ║  ⚠️ **والثمنُ يُقال**: الوسمُ قد يتأخّر شمعةً أو شمعتين عن        ║
    ║  العودة — **تأخُّرٌ لا استباق**، وهو الاتّجاه الآمن.             ║
    ╚══════════════════════════════════════════════════════════════╝

    ⚠️⚠️ **و`None` ليست `[]`** — والفرقُ هو الذي يمنع عطبًا صامتًا:

        `fvgs=None`  ⇒ **لم تُمرَّر** — عطبُ مستدعٍ، فيصيح `ValueError`
        `fvgs=[]`    ⇒ **مُرِّرت وهي فارغة** — حالةُ سوقٍ مشروعة
                        (سلسلةٌ بلا فراغٍ واحد) ⇒ لا بريكر، بلا صياح

    ⛔ **وأوّلُ كتابةٍ لهذا الحارس خلطت الاثنين** فصاحت على سلسلةٍ
    مسطَّحةٍ لا فراغَ فيها — **وكشفه اختبارُ الوصل في `chain`، لا
    القراءة.** وهو عينُ القاعدة: **لا يُصدَّق حارسٌ جديدٌ قبل أن
    يُجرَّب.**

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⛔⛔⛔ **BK2 — `flip_breaker` · والدورُ ينقلب بالنصّ.**         ║
    ║                                                              ║
    ║    42:55  «هذا البريكر بلوك صار عندي نقطه دعم هو كان         ║
    ║            مقاومه»                                            ║
    ║    46:46  «وهل البريكر بيتحول عندي من نقطه اهتمام للبيع       ║
    ║            الى نقطه اهتمام للشراء»                            ║
    ║                                                              ║
    ║  **والكودُ كان يُبقي `direction` كما وُلدت** ⇒ فمنطقةٌ هابطةٌ    ║
    ║  كُسرت صاعدةً تبقى `bearish`، فتُسقطها بوّابةُ الاتّجاه في        ║
    ║  `chain` متى صار الهيكلُ صاعدًا — **وهو ما يصير بعد كسرها.**   ║
    ║                                                              ║
    ║  ⭐ **والقلبُ يصحّح الهندسةَ معه لا بعده** — وهذا برهانٌ على    ║
    ║  أنّ الحقلَ هو الموضعُ الصحيح لا حقلٌ ثانٍ:                    ║
    ║      `near_edge`  هابطة ⇒ `bottom` · وصاعدة ⇒ `top`           ║
    ║                   والسعرُ يعود إلى الدعم **من فوق** ⇒ `top` ✅  ║
    ║      `stop_for`   صاعدة ⇒ `bottom − buffer` **تحت** المنطقة ✅  ║
    ║                                                              ║
    ║  ⚠️⚠️ **والترتيبُ مقصود**: الحالةُ تُحسب أوّلًا وفيها             ║
    ║  `_gap_at_the_break(ob.direction)` — **بالاتّجاه الأصليّ**،     ║
    ║  **والقلبُ بعد الحلقة**. ولو قُلب قبلها لانعكس شرطُ الكسر       ║
    ║  نفسُه. ⇒ **وهو محروسٌ باختبار.**                              ║
    ║                                                              ║
    ║  ⛔ **ولا يُقلب إلّا البريكر** — و`failed` تبقى كما هي، فهي     ║
    ║  مرفوضةٌ أصلًا ولم ينقلب دورُها بعد.                            ║
    ╚══════════════════════════════════════════════════════════════╝

    ⚠️ **وحدٌّ يُقال**: `sweep` و`fvg` و`governing_level` تبقى بجهة
    التأسيس — **فهي سجلُّ ما وقع لا دورُ المنطقة اليوم**، ولا تُقلب.
    وهي لا تُقرأ إلّا في نصّ الأسباب.
    """
    if require_break_gap and fvgs is None:
        raise ValueError(
            "require_break_gap=True بلا تمرير `fvgs` ⇒ يرفض كلَّ بريكر بصمت"
        )

    out: List[OrderBlock] = []

    for ob in blocks:
        state: State = "fresh"
        failed_at: Optional[int] = None
        mitigated_before_failing = False

        for i in range(ob.break_index + 1, len(series)):
            c = series[i]

            if failed_at is None:
                broke = (
                    c.body_bottom < ob.bottom
                    if ob.direction == "bullish"
                    else c.body_top > ob.top
                )
                if broke:
                    state, failed_at = "failed", i
                    continue
                if state == "fresh" and ob.touched_by(c):
                    state = "mitigated"
                    mitigated_before_failing = True
            elif ob.touched_by(c):
                # «مجرد إنه انعمل تخفيف — ما بقى بريكر»
                if mitigated_before_failing:
                    break
                # ⛔ BK1 — «وش شرط اساسي عند كسر الاوردر بلوك تشكل فراغ سعري»
                if require_break_gap and _gap_at_the_break(
                    fvgs or (), failed_at, ob.direction
                ) is None:
                    break  # ⇒ تبقى `failed`، وهي مرفوضةٌ في السلسلة
                state = "breaker"
                break

        # ⛔⛔⛔ **BK2 — والقلبُ هنا، بعد الحلقة لا قبلها.**
        role = (opposite(ob.direction)
                if flip_breaker and state == "breaker"
                else ob.direction)
        out.append(replace(ob, state=state, direction=role))

    return out


# ─────────────────────────── الدخول من اللمس ───────────────────────────


@dataclass(frozen=True)
class DirectTouchCheck:
    """نتيجة فحص أهلية الدخول من مجرد اللمس، بأسبابها."""

    eligible: bool
    reasons: List[str]


def qualifies_for_direct_touch(
    ob: OrderBlock,
    higher_tf_fvgs: Sequence[FVG],
    impulse_midpoint: Optional[float] = None,
    require_containment: bool = False,
) -> DirectTouchCheck:
    """
    م2/د3 — «فنحن نقطة الدخول بتكون عنّا عند مجرد اللمس».

    الشروط:
      ١. الثلاثية مستوفاة  ⇒ مضمونة ببناء الكائن أصلًا (D3).
      ٢. المنطقة **مسنودة** بفراغ على إطار أعلى — «مدعومة من فير فاليو جاب
         على الربع ساعة».
      ٣. الموقع تحت بوابة الـ50% للشراء، وفوقها للبيع (C3).
      ٤. الحالة **fresh** — أول لمسة لا غير.

    ⭐⭐ **٤ تصحيح — أغلق C2** (دفعة المنهج، درس طريقة الدخول):

        «بيهمنا **أول لمسة الفريش**… اللمسة **الثانية أو الثالثة
         ما بنتعامل معها**»

    كان الشرط «ليست failed» فيمرّ منه `mitigated` — أي لمسة ثانية.
    وهذا خطأ: السيولة تُستهلك باللمسة الأولى. والآن `mitigated` مرفوضة
    صراحةً. و`breaker` يبقى مقبولًا — كائن آخر بشروطه، ومن شرطه أصلًا
    ألّا يكون خُفِّف.

    ❓ D1 غير محسوم: هل يلزم الاحتواء الكامل أم يكفي التطابق؟
       الافتراضي **التطابق** (require_containment=False) لأنه أقرب للفظ
       «مدعومة من» ولا يشترط هندسة صارمة.
    """
    reasons: List[str] = []
    ok = True

    if ob.state == "failed":
        ok = False
        reasons.append("❌ المنطقة فاشلة — أُغلق عبرها بالجسم")
    elif ob.state == "mitigated":
        ok = False
        reasons.append(
            "❌ لمسة ثانية — «بيهمنا أول لمسة الفريش، "
            "اللمسة الثانية أو الثالثة ما بنتعامل معها»"
        )
    else:
        reasons.append(f"✅ الحالة: {ob.state}")

    reasons.append(
        f"✅ الثلاثية مستوفاة — كسح {ob.sweep.level} · "
        f"كسر {ob.governing_level} بالجسم · فراغ {ob.fvg.bottom}–{ob.fvg.top}"
    )

    support = None
    for g in higher_tf_fvgs:
        if g.direction != ob.direction:
            continue
        if require_containment:
            fits = g.bottom <= ob.bottom and ob.top <= g.top
        else:
            fits = g.bottom <= ob.top and g.top >= ob.bottom
        if fits:
            support = g
            break

    if support is None:
        ok = False
        reasons.append("❌ لا يسندها فراغ على إطار أعلى — تلزم القاعدة العامة (تأكيد)")
    else:
        reasons.append(f"✅ مسنودة بفراغ إطار أعلى {support.bottom}–{support.top}")

    if impulse_midpoint is not None:
        entry = ob.top if ob.direction == "bullish" else ob.bottom
        cheap = entry < impulse_midpoint if ob.direction == "bullish" else entry > impulse_midpoint
        if cheap:
            reasons.append(f"✅ الموقع مقبول — المنتصف {impulse_midpoint}")
        else:
            ok = False
            reasons.append(f"❌ الدخول غالٍ — تجاوز منتصف الموجة {impulse_midpoint}")

    return DirectTouchCheck(eligible=ok, reasons=reasons)


def fresh_blocks(blocks: Sequence[OrderBlock]) -> List[OrderBlock]:
    return [b for b in blocks if b.state == "fresh"]


def breakers(blocks: Sequence[OrderBlock]) -> List[OrderBlock]:
    return [b for b in blocks if b.state == "breaker"]
