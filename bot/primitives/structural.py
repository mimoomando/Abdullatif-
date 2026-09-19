"""
القمم والقيعان **الحقيقيّة** — تمييزُها عن السوينج العاديّ.

╔══════════════════════════════════════════════════════════════════╗
║  سوينج        = أعلى من الجارَين  (فراكتال — `swings.py`)          ║
║  قمّة حقيقيّة = سوينج **عند انتهاء الموجة، لا داخلها**             ║
║  والهيكل      = يُبنى على الحقيقيّة **وحدها**                      ║
╚══════════════════════════════════════════════════════════════════╝

**المصدر:** درس «القمم والقيعان الحقيقيّة» — ونزل **قبل** درس الأوردر
بلوك عمدًا:

    «أنا قرّرت أعطيها اليوم **قبل درس الأوردر بلوك**، لأنه ضروريّ:
     نحن لمّا ندرس الأوردر بلوك في عنّا سحب سيولة — وسحبُ السيولة
     **لازم يكون من قاعٍ محدَّد، مش أيّ قاع**»

    «الهيكل **ما بيتحدّد عن طريق قمم وقيعان داخل الموجة** —
     بيتحدّدوا عن قمّة وقاع **الموجة الأساسيّة**»

⚠️⚠️ **والنصّ يحتمل قراءتين، وكلتاهما فيه حرفيًّا.** فلم تُرجَّح
واحدةٌ بالرأي — بُنيتا معًا و**قِيستا** على أسبوع حقيقيّ:

| القراءة | النصّ الذي يسندها |
|---|---|
| `UNSWEPT` | «هل هي هون؟ **لا، والله ليك سحبت سيولتها**» · «هيدي القيعان **كلّياتها ضُربت** ما[عدا] القاع الرئيسيّ» |
| `SWEEPER` | «ما في قمّة حقيقيّة أو قاع حقيقيّ **إلّا ما تكون ساحبة سيولة ما قبل**» |

و`BOTH` تجمعهما: سحبت ما قبلها، **ولم تُسحَب** بعدُ.

⛔ **ولا تُستعمل في قرارٍ حتى يقول القياس أيُّها ينفع.** انظر
`knowledge/episodes/swing-true-highs-and-lows.md`.
"""

from __future__ import annotations

from typing import List, Literal, Optional, Sequence

from ..data import Series
from .swings import Swing

Rule = Literal["unswept", "sweeper", "both", "all"]


def swept_at(series: Series, swing: Swing,
             upto: Optional[int] = None) -> Optional[int]:
    """
    أوّلُ شمعةٍ سحبت سيولة هذا السوينج — أو `None` إن لم تُسحَب.

    والسحبُ هنا **تجاوزٌ بالطرف** لا إغلاقًا: السيولة عند الذيل
    (C1)، ومجرّدُ بلوغها يستهلكها.
    """
    stop = len(series) if upto is None else min(len(series), upto)
    for i in range(swing.index + 1, stop):
        k = series[i]
        if swing.is_high and k.high > swing.price:
            return i
        if not swing.is_high and k.low < swing.price:
            return i
    return None


def swept_before(swing: Swing, earlier: Sequence[Swing]) -> bool:
    """
    هل سحب هذا السوينج سيولةَ آخرِ سوينجٍ من جنسه قبله؟

    «ما في قمّة حقيقيّة إلّا ما تكون **ساحبة سيولة ما قبل**»

    ⚠️ والمقارنة مع **آخر** سوينجٍ من جنسه فقط — لا مع أعلى ما مضى.
    فالأوّل يقيس «هل تجاوز ما قبله»، والثاني يقيس شيئًا آخر.
    """
    prev = [s for s in earlier
            if s.index < swing.index and s.is_high == swing.is_high]
    if not prev:
        return False                      # لا سابقَ له ⇒ لم يسحب شيئًا
    last = max(prev, key=lambda s: s.index)
    return (swing.price > last.price) if swing.is_high else (swing.price < last.price)


def structural(series: Series, swings: Sequence[Swing],
               rule: Rule = "unswept",
               upto: Optional[int] = None) -> List[Swing]:
    """
    يرشّح السوينجات إلى «الحقيقيّة» بحسب القراءة المطلوبة.

    `rule="all"` يُرجع الجميع بلا ترشيح — وهو **السلوك القائم**،
    ويُستعمل خطَّ أساسٍ في القياس.
    """
    if rule == "all":
        return list(swings)

    ordered = sorted(swings, key=lambda s: (s.index, s.kind))
    out: List[Swing] = []
    for s in ordered:
        unswept = swept_at(series, s, upto) is None
        sweeper = swept_before(s, ordered)
        if rule == "unswept" and unswept:
            out.append(s)
        elif rule == "sweeper" and sweeper:
            out.append(s)
        elif rule == "both" and unswept and sweeper:
            out.append(s)
    return out
