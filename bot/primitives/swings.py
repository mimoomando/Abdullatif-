"""
القمم والقيعان (Swing Highs / Lows) — الدرس 9.

النص المصدري:
    «A Swing High is higher than the immediately preceding and immediately
     following high. A Swing Low is lower than the immediately preceding and
     immediately following low.»

وينبّه الدرس نفسه إلى أن قمم M5/M15 غالبًا سيولة داخلية لا نقاط انعكاس كبرى،
ولذلك تُفصل هنا «القمة الفراكتالية» عن «القمة الهيكلية» (structure.py).

╔══════════════════════════════════════════════════════════════════╗
║  🔴🔴 **SW1 — «إيكوال هاي» بشمعتين متجاورتين لا يراه البوت.**       ║
║  كُشف 2026-09-27، **ومقيسٌ لا مُستنتَج** (`test_swings.py`).        ║
║                                                                  ║
║  فالمقارنةُ هنا **صارمةٌ في الجهتين** (`>` و`<`). وقمّتان          ║
║  متساويتان **متجاورتان** تُسقط كلَّ واحدةٍ منهما: الأولى ليست       ║
║  أعلى من الثانية، والثانية ليست أعلى من الأولى. ⇒ **صفرُ           ║
║  سوينجات**، والمستوى **غيرُ موجود** في نظر البوت.                 ║
║                                                                  ║
║  ⛔ **والأثرُ يمتدّ إلى الأوردر بلوك**: `find_sweeps` لا تكسح إلّا  ║
║  سوينجًا، و`find_order_blocks` لا تُولَد إلّا من كسح. ⇒ **فكسحُ**   ║
║  **إيكوال-هاي متجاورٍ لا يُكشَف، ولا يُولَد منه أوردر بلوك**.       ║
║  (وبشمعةٍ أدنى بينهما يُكشَف الاثنان والكسحُ معهما — مقيس.)        ║
║                                                                  ║
║  ⭐ **والمدرّب يسمّيه منطقةَ سيولةٍ مستهدَفة بلفظه:**               ║
║    «عندي **منطقة سيولة مستهدفة — إيكوال هاي** — وعندي سيولة       ║
║     مبنيّة من إنجينيرينغ ليكويديتي… أوّل شيء في عندي **هيدا        ║
║     الهدف مستهدف من جهة الإيكوال هاي**»                           ║
║                          (تحليل التضخّم/الأوردر بلوك H4 ≈2:56)    ║
║                                                                  ║
║  🔶 **ولم يُغيَّر — والسببُ المنهج.** فـ`>=` في الجهتين يجعل كلَّ    ║
║  شمعةٍ في هضبةٍ مستويةٍ سوينجًا، والعرفُ المعتاد صارمٌ في جهةٍ       ║
║  ومتساهلٌ في الأخرى — **وذلك تغييرُ سلوكٍ على المسار الحيّ**:      ║
║  يزيد السوينجات فيزيد الكسحَ فيزيد الأوردر بلوك. ⇒ **يُقاس**      ║
║  بتشغيل النطاق مرّتين ومقارنةِ الحصيلة وعددِ الإعدادات.            ║
║                                                                  ║
║  ⚠️ **والصمتُ هو الأسوأ فيه**: لا سطرَ في السجلّ يقول «رأيت        ║
║  مستوًى ولم أُسجّله» — وهو صنفُ العطب المسجَّل في `CLAUDE.md`.      ║
╚══════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal

from ..data import Series

Kind = Literal["high", "low"]


@dataclass(frozen=True)
class Swing:
    index: int
    time: datetime
    price: float
    kind: Kind

    @property
    def is_high(self) -> bool:
        return self.kind == "high"

    @property
    def is_low(self) -> bool:
        return self.kind == "low"


Plateau = Literal["strict", "first"]

# ⛔ **الافتراضُ يبقى `strict`** — أي السلوكَ القائم. فالتعريفُ المنقول
# أعلاه **صارمٌ في الجهتين بحرفه**، والبديلُ يزيد السوينجات فيزيد
# الكسحَ فيزيد الأوردر بلوك. ولا يُقلب افتراضٌ بلا قياس.
DEFAULT_PLATEAU: Plateau = "strict"


def find_swings(series: Series, lookback: int = 1,
                plateau: Plateau = DEFAULT_PLATEAU) -> List[Swing]:
    """
    يرجع القمم والقيعان مرتبة بالفهرس.

    lookback=1 هو التعريف الحرفي في الدرس 9 (فراكتال ثلاث شموع).
    قيم أكبر تعطي قممًا أندر وأكثر أهمية — تُستعمل على الأطر الكبرى.

    شمعة واحدة قد تكون قمة وقاعًا معًا (شمعة خارجية)؛ الاثنتان تُرجعان.

    ╔══════════════════════════════════════════════════════════════╗
    ║  🔴 **`plateau` — معالجةُ الهضبة المستوية (SW1).**             ║
    ║                                                              ║
    ║    `strict` : صارمٌ في الجهتين — **السلوكُ القائم، وهو حرفُ**  ║
    ║               **التعريف المنقول**. وقمّتان متساويتان           ║
    ║               **متجاورتان** تُسقطان معًا.                      ║
    ║    `first`  : صارمٌ يسارًا ومتساهلٌ يمينًا (`>` ثمّ `>=`) ⇒       ║
    ║               **أوّلُ شمعةٍ في الهضبة تُسجَّل، وحدها**.          ║
    ║                                                              ║
    ║  ⚠️ **ولِمَ «أوّل» لا «آخر»؟** لأنّ المستوى يصير سيولةً **متى**  ║
    ║  **تشكّل**، فالفهرسُ الأسبق يجعله قابلًا للكسح في كلّ ما بعده.  ║
    ║  ولا يُنشئ كسحًا كاذبًا: `find_sweeps` تشترط `high > level`     ║
    ║  **صارمةً**، فالشمعةُ المساويةُ لا تكسح مستوى نفسِها.           ║
    ║                                                              ║
    ║  ⛔ **ولا يُزعم أنّ `first` أصوبُ.** التعريفُ المنقول صارمٌ،     ║
    ║  والمدرّبُ يسمّي الإيكوال هاي «منطقة سيولة مستهدفة». **فهذان   ║
    ║  سندان متعارضان، والقياسُ يفصل** — لا ترجيحي.                 ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    if lookback < 1:
        raise ValueError("lookback يجب أن يكون 1 أو أكثر")
    if plateau not in ("strict", "first"):
        raise ValueError("plateau إمّا strict أو first")

    out: List[Swing] = []
    n = len(series)
    lax = plateau == "first"
    for i in range(lookback, n - lookback):
        c = series[i]
        left = range(i - lookback, i)
        right = range(i + 1, i + lookback + 1)

        higher_right = (
            all(c.high >= series[j].high for j in right) if lax
            else all(c.high > series[j].high for j in right)
        )
        if all(c.high > series[j].high for j in left) and higher_right:
            out.append(Swing(i, c.time, c.high, "high"))

        lower_right = (
            all(c.low <= series[j].low for j in right) if lax
            else all(c.low < series[j].low for j in right)
        )
        if all(c.low < series[j].low for j in left) and lower_right:
            out.append(Swing(i, c.time, c.low, "low"))

    out.sort(key=lambda s: (s.index, s.kind))
    return out


def highs(swings: List[Swing]) -> List[Swing]:
    return [s for s in swings if s.is_high]


def lows(swings: List[Swing]) -> List[Swing]:
    return [s for s in swings if s.is_low]


def last_swing(swings: List[Swing], kind: Kind) -> Swing | None:
    for s in reversed(swings):
        if s.kind == kind:
            return s
    return None
