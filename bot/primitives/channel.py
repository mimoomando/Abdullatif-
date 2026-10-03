"""
القناة السعريّة — ومرتكزاتُها **مشروطة**، لا أيّ قمّتين.

╔══════════════════════════════════════════════════════════════════╗
║  صاعد  ⇒  **قاعان وقمّة**        هابط  ⇒  **قمّتان وقاع**          ║
║  تُرسم على الذيول — **والأفضل على جسم الشمعة**                     ║
║  وكلُّ مرتكزٍ: **منتهٍ** · **مصحَّحٌ أكثر من 50%**                   ║
║  والنسخ: **مرّتان أو ثلاث — كحدٍّ أقصى**                            ║
╚══════════════════════════════════════════════════════════════════╝

**النصّ** (درس القنوات السعريّة):

    «بالاتّجاه الصاعد بدنا نرتكز على **قاعين وقمّة**، بالاتّجاه الهابط
     بدنا نرتكز على **قمّتين وقاع**»

    «ولتكون القناة السعريّة صحيحة ومضبوطة نحن **بنرسم على الذيول،
     ولكن الأفضل والأنسب إنّك ترسمها على جسم الشمعة**»

    «القاعين والقمّتين اللي بدّك تحدّدهم — **ما بدها تكون قمّة عم
     تتشكّل هلّق** تحدّدها… لا، ما بتزبط. **بدها تكون قمّة منتهية
     ومصحَّحة — مصحّحها أكثر من 50%** — اللي في وراها **قمّة حقيقيّة
     سابقة**. أمّا إنّك تيجي تحطّها بهالشكل… **فهي مرفوضة، هي صارت
     فرعيّة**»

    «القناة السعريّة ممكن **تنسخ مرّتين أو ثلاث، مش أكثر**… مرّة
     ثالثة رابعة خامسة؟ لا — **مرّتين أو ثلاث كحدٍّ أقصى**»

    «صار عندي كسر — كلّ ما عليّ أجي **أعمل كلون** وأحطّ مستوى
     **المقاومة عند مستوى الدعم**»

    «بعمل كلون هي نفسها بسحبها» · «بحط هيدا اللي تحت اللي كان دعم من
     تحت على **خط المقاومه**»

⚠️ **وهو نفسُه يقول إنّها لا تُحترم دائمًا**: «مش شرط إنّه يحترمها
السعر بشكل كثير كبير». فهي **قراءةٌ للموجة** لا زنادُ دخول:

    «القنوات السعريّة هي **بتعبّر عن الموجة كاملة**: كيف بدها تمشي،
     من وين بدها ترتدّ، وين بدها تنعكس»

⛔ **فلا تُوصَل بقرارٍ هنا.** بُنيت كما وُصفت، وتُقاس قبل أن تُستعمل.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

from ..data import Series
from .swings import Swing

Direction = Literal["bullish", "bearish"]

# «بدها تكون قمّة منتهية ومصحَّحة — **مصحّحها أكثر من 50%**»
MIN_CORRECTION = 0.50

# «مرّتين أو ثلاث — مش أكثر… **كحدٍّ أقصى**»
MAX_CLONES = 3


def _price(series: Series, swing: Swing, on_body: bool) -> float:
    """سعرُ المرتكز — بالجسم أو بالذيل."""
    if not on_body:
        return swing.price
    k = series[swing.index]
    return k.body_top if swing.is_high else k.body_bottom


def corrected(series: Series, swing: Swing,
              upto: Optional[int] = None) -> Optional[float]:
    """
    كم صحّح السعرُ عن هذا المرتكز — نسبةً إلى الموجة التي أسّسته؟

    ⛔ و`None` تعني **لا يُحكَم**: لا شمعةَ بعده، أو لا موجةَ خلفه.
    وذلك غيرُ «صحّح صفرًا».

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⛔⛔⛔ **CH1 — والمقامُ ليس الموجةَ، بل التاريخَ كلَّه.**        ║
    ║  **وُصف 2026-09-30.**                                         ║
    ║                                                              ║
    ║  فهذه الترويسةُ تقول [نسبةً إلى **الموجة التي أسّسته**]،       ║
    ║  والكودُ يأخذ `base` = **أدنى قاعٍ في كلّ ما سبق** لا في        ║
    ║  الموجة. ⇒ فكلّما طال التاريخُ كبر المقامُ وصغرت النسبة.       ║
    ║                                                              ║
    ║  ⛔ **ومقيسٌ**: قمّةٌ عند 110 موجتُها من 99.5، والتصحيحُ إلى    ║
    ║  104 — أي **57%** بحساب الموجة:                               ║
    ║                                                              ║
    ║      بلا تاريخٍ سابق        ⇒ 57.1%  · `anchor_ok` **True**   ║
    ║      وقبله هبوطٌ من 160     ⇒ 15.0%  · `anchor_ok` **False**  ║
    ║                                                              ║
    ║  **والسوقُ واحد، والموجةُ واحدة، والتصحيحُ واحد** — والذي      ║
    ║  تغيّر **كم شمعةً جلبتَ**. ⇒ فهذا صنفُ [رقمٌ يقلبه اختيارُك]:  ║
    ║  الحكمُ يقرّره `--poi-bars` لا السعر.                          ║
    ║                                                              ║
    ║  🔴 **والمقامُ غيرُ منصوصٍ أصلًا**: قال «مصحّحها أكثر من 50%»  ║
    ║  ولم يقل **من أيّ شيء**. فتحديدُ الموجة يلزمه قاعدةُ تحديدٍ    ║
    ║  هي نفسُها `UNDEFINED` (وهو عينُ ما عطّل IM1).                 ║
    ║                                                              ║
    ║  ⇒ **ولم يُغيَّر**: الوحدةُ غيرُ موصولة، وأيُّ مقامٍ أضعه بديلًا  ║
    ║  اختراعٌ. **والواجبُ عند الوصل**: يُثبَّت المقام ويُعلَن،        ║
    ║  ويُمرَّر `upto` (وإلّا انضاف فخُّ ST1 إليه).                   ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    stop = len(series) if upto is None else min(len(series), upto)
    if swing.index + 1 >= stop:
        return None                      # «قمّة عم تتشكّل هلّق» — لا تُقاس

    after = list(range(swing.index + 1, stop))
    if swing.is_high:
        extreme = min(series[i].low for i in after)
        base = min(series[i].low for i in range(0, swing.index + 1))
        wave = swing.price - base
        move = swing.price - extreme
    else:
        extreme = max(series[i].high for i in after)
        base = max(series[i].high for i in range(0, swing.index + 1))
        wave = base - swing.price
        move = extreme - swing.price

    if wave <= 0:
        return None
    return move / wave


def anchor_ok(series: Series, swing: Swing, upto: Optional[int] = None,
              minimum: float = MIN_CORRECTION) -> bool:
    """
    هل يصلح هذا السوينج مرتكزًا؟

    شرطان منصوصان: **منتهٍ** (له شمعةٌ بعده) و**مصحَّحٌ أكثر من 50%**.

    ⚠️ و«أكثر من» حرفيّة: الخمسون بالضبط **لا تكفي**.
    """
    c = corrected(series, swing, upto)
    return c is not None and c > minimum


@dataclass(frozen=True)
class Channel:
    """
    قناةٌ من ثلاثة مرتكزات — اثنان على القاعدة وواحدٌ مقابلها.

    `generation` صفرٌ للأساسيّة، ويزيد بكلّ نسخة. و«فرعيّة» ليست
    نسخةً: هي قناةٌ بُنيت على مرتكزٍ لم يستوفِ الشرط — «هي مرفوضة، هي
    صارت **فرعيّة**».
    """

    direction: Direction
    first: Swing              # المرتكز الأوّل على القاعدة
    second: Swing             # والثاني — وهما يرسمان الخطّ
    opposite: Swing           # المرتكز المقابل — يرسم الخطّ الموازي
    on_body: bool = True
    generation: int = 0
    sub: bool = False         # فرعيّة: مرتكزٌ لم يستوفِ الشرط

    @property
    def kind(self) -> str:
        if self.sub:
            return "فرعيّة"
        return "أساسيّة" if self.generation == 0 else f"نسخة {self.generation}"

    def slope(self, series: Series) -> float:
        """ميلُ القاعدة — دولارٌ لكلّ شمعة."""
        span = self.second.index - self.first.index
        if span == 0:
            return 0.0
        a = _price(series, self.first, self.on_body)
        b = _price(series, self.second, self.on_body)
        return (b - a) / span

    def _line(self, series: Series, index: int) -> float:
        """الخطُّ القاعديُّ **قبل الإزاحة** — ومنه يُقاس العرض."""
        a = _price(series, self.first, self.on_body)
        return a + self.slope(series) * (index - self.first.index)

    def width(self, series: Series) -> float:
        """المسافةُ بين الخطّين — وهي ما يُنسَخ عند الكسر."""
        c = _price(series, self.opposite, self.on_body)
        return c - self._line(series, self.opposite.index)

    def shift(self, series: Series) -> float:
        """
        إزاحةُ هذه النسخة عن الأصل — **عرضٌ واحدٌ لكلّ جيل، عبر
        الخطّ القاعديّ**.

        ⭐ والقاعدةُ منصوصةٌ لا مخترَعة: المرتكزان المزدوجان هما
        القاعدة، **وهي الخطُّ الذي يُكسَر** — «مجرد الخرق للمره
        الثالثه او للمره الرابعه هون انا صار عندي تاكيد انه خلص صار
        في خرق لهالمستوى». والنسخةُ تعبره فيصير **خطُّها المقابلُ
        على خطّ الأصل القاعديّ** بعينه. انظر `cloned`.
        """
        return -self.width(series) * self.generation

    def base_at(self, series: Series, index: int) -> float:
        return self._line(series, index) + self.shift(series)

    def top_at(self, series: Series, index: int) -> float:
        return self.base_at(series, index) + self.width(series)

    def cloned(self) -> Optional["Channel"]:
        """
        النسخة التالية — «أعمل كلون وأحطّ **المقاومة عند مستوى الدعم**».

        ⛔ و`None` بعد الحدّ: «مرّتين أو ثلاث — **مش أكثر**».

        ╔══════════════════════════════════════════════════════════╗
        ║  ✅✅✅ **CH2 — أُغلق 2026-10-03 · والنسخةُ تُزيح الآن.**   ║
        ║                                                          ║
        ║  كانت هذه الدالّةُ تزيد `generation` **وحدَه** والمرتكزاتُ  ║
        ║  كما هي ⇒ **كلُّ نسخةٍ ترسم الخطّين ذاتهما**، و`chain()`   ║
        ║  تُرجع أربعًا **فتبدو عاملة** — صنفُ [بندٌ معلَنٌ لا يعمل   ║
        ║  ويصمت]. **وقدرُ الإزاحة كان معلومًا** (عرضُ القناة مرّةً   ║
        ║  واحدة) **واتّجاهُها لا** ⇒ فلم تُبنَ (القاعدة ①).         ║
        ║                                                          ║
        ║  ⭐⭐⭐ **والدرسُ يحسمه — ويعطي الحالتين، كلًّا بلفظها:**    ║
        ║                                                          ║
        ║    3:46 «هون صار في عننا **خرق** للقناه السعريه»          ║
        ║    4:00 «بعمل كلون **هي نفسها بسحبها**»                   ║
        ║    4:06 «بحط **هيدا اللي تحت اللي كان دعم من تحت** على    ║
        ║          **خط المقاومه**»          ⇒ والنسخةُ **أعلى**    ║
        ║                                                          ║
        ║    6:36 «صار عندي **كسر** — كل ما علي انا اجي اعمل كلون»  ║
        ║    6:43 «**واحط مستوى المقاومه عند مستوى الدعم**»         ║
        ║                                    ⇒ والنسخةُ **أسفل**    ║
        ║                                                          ║
        ║  ⭐ **واللفظان ليسا متناقضين — هما الجهتان**: فالأوّلُ على ║
        ║  قناةٍ **هابطة** كُسرت صاعدةً، والثاني على قناةٍ **صاعدة**  ║
        ║  كُسرت هابطةً. وتسميتُهما منصوصة: «بمجرد **الاختراق من     ║
        ║  فوق** او **الكسر من تحت**».                              ║
        ║                                                          ║
        ║  ⭐⭐⭐ **والصيغةُ واحدةٌ في الحالتين، ولا تحتاج اتّجاهًا:**  ║
        ║  فالمكسورُ في المثالين هو **الجانبُ المزدوجُ المرتكزات**    ║
        ║  — أي `base` — «مجرد الخرق للمره الثالثه او للمره الرابعه ║
        ║  هون انا صار عندي تاكيد انه خلص صار في خرق لهالمستوى».    ║
        ║  ⇒ **فالنسخةُ تعبره: خطُّها المقابلُ على خطّ الأصل          ║
        ║  القاعديّ.** وذلك `shift = −width` لكلّ جيل:               ║
        ║                                                          ║
        ║      أساسيّة  القاعدة 97.50   المقابل 110.00             ║
        ║      نسخة 1   القاعدة 85.00   المقابل  97.50  ⬅ على قاعدة ║
        ║      نسخة 2   القاعدة 72.50   المقابل  85.00    الأصل    ║
        ║                                                          ║
        ║  ⚠️ **والمرتكزاتُ لا تتغيّر** ⇒ فالميلُ واحد: «**هي نفسها  ║
        ║  بسحبها**». والمتغيّرُ الإزاحةُ وحدَها.                     ║
        ║                                                          ║
        ║  ⛔⛔ **وخطئي يُقال**: كتبتُ هنا صباحَ 10-03 [وقُرئ الدرسُ  ║
        ║  كاملًا فلم يحسمها] و[فهذا بابٌ مغلق] — **ولم أكن قرأتُه   ║
        ║  كاملًا**: قرأتُ حولَ 6:43 و5:48، **والجوابُ عند 4:06**    ║
        ║  — دقيقتان ونصفٌ أبكر، **في ملفٍّ عندنا منذ 09-26**.       ║
        ║  ⇒ وهو **ثاني** تقصيرٍ في الملفّ نفسِه واليومِ نفسِه (الأوّلُ ║
        ║  أنّي طلبتُه من المستخدم وهو في المستودع). ⭐ **والدرس:     ║
        ║  يُقرأ المقطعُ كلُّه لا جوارُ السطر المقتبَس.**              ║
        ╚══════════════════════════════════════════════════════════╝
        """
        if self.generation >= MAX_CLONES:
            return None
        return Channel(self.direction, self.first, self.second, self.opposite,
                       self.on_body, self.generation + 1, self.sub)

    def render(self) -> str:
        side = "صاعدة" if self.direction == "bullish" else "هابطة"
        return (f"قناة {side} {self.kind} · مرتكزات "
                f"{self.first.index}·{self.second.index}·{self.opposite.index}"
                + (" · على الجسم" if self.on_body else " · على الذيل"))


def build(series: Series, swings: Sequence[Swing], direction: Direction,
          on_body: bool = True, upto: Optional[int] = None) -> Optional[Channel]:
    """
    أحدثُ قناةٍ صالحة — أو `None`.

    **صاعد ⇒ قاعان وقمّة · هابط ⇒ قمّتان وقاع.** والقاعدة هي الجانبُ
    المزدوج: «لمّا بدي أكّد على الصعود بدي أكون مرتكز على قمّتين — يعني
    مجرّد الخرق للمرّة الثالثة صار عندي تأكيد».

    ⚠️ ومرتكزٌ لم يستوفِ الشرط لا يُسقط القناة — **يجعلها فرعيّة**،
    بنصّه: «هي مرفوضة، هي صارت فرعيّة».
    """
    want_low_base = direction == "bullish"
    base = [s for s in swings if s.is_low == want_low_base]
    other = [s for s in swings if s.is_low != want_low_base]
    if len(base) < 2 or not other:
        return None

    first, second = base[-2], base[-1]
    between = [s for s in other if first.index < s.index < second.index]
    opposite = between[-1] if between else other[-1]

    ok = all(anchor_ok(series, s, upto) for s in (first, second, opposite))
    return Channel(direction, first, second, opposite, on_body, 0, sub=not ok)


def chain(channel: Channel) -> List[Channel]:
    """القناةُ ونسخُها كلُّها — حتى الحدّ المنصوص."""
    out, cur = [channel], channel
    while True:
        nxt = cur.cloned()
        if nxt is None:
            return out
        out.append(nxt)
        cur = nxt
