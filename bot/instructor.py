"""
تحاليل المدرّب مُسجَّلةً **قبل** القياس — لا بعده.

⚠️ **لماذا هذه الوحدة موجودة أصلًا؟** لأن قياس أسبوع 09-07…11 كان
معيبًا في طريقته وإن صحّ في حسابه: جدولُ «ما قاله المدرّب» الذي
قِست عليه كتبتُه **أنا**، وأنا من ترجم كلامه إلى `bullish` و`bearish`
— **بعد** أن رأيتُ ما ستقوله القاعدة.

وذلك يفتح بابًا لا يُغلق بحسن النيّة: كلامُ المدرّب نثرٌ يحتمل
قراءتين، فمن يقرؤه وهو يعرف النتيجة يرجّح — بلا قصد — القراءةَ التي
تناسبها. ويوم الأربعاء 09-09 مثالٌ حيّ: سجّلتُه `bullish` لأنه قال
«تحيّزي إيجابي»، وكان يمكن تسجيله `bearish` لأنه وصف الصعود بأنه
«تصحيح لاستكمال الهبوط». والفرق يقلب النتيجة.

⇒ **فالحكم يُسجَّل يوم قوله، ومعه نصُّه، وقبل تشغيل أي قياس.** وهذا
هو الشرط الوحيد الذي يجعل نتيجة الأسبوع القادم دليلًا لا انطباعًا.

⛔ ولا تُعدَّل مقولةٌ بعد رؤية نتيجتها. وإن تبيّن أن تسجيلها خطأ
فالصواب **إبطالها صراحةً** (`void` مع سببه) لا إعادة صياغتها:
الإبطال يُعَدّ ويظهر في التقرير، والصياغة الجديدة تختفي.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import date as Date
from typing import Dict, List, Optional, Sequence

from .primitives.structure import Trend

# ما يقوله المدرّب عن الهيكل، مترجَمًا إلى ثلاث حالات لا أكثر
BIAS = ("bullish", "bearish", "undefined")


@dataclass(frozen=True)
class Call:
    """
    حكمٌ واحد للمدرّب في يومٍ واحد — مع نصّه.

    `quote` ليس زينة: هو ما يسمح لك أنت بمراجعة ترجمتي. وحُكمٌ بلا
    نصٍّ مرفوض في `validate`.
    """

    day: str                  # YYYY-MM-DD
    timeframe: str            # الإطار الذي تكلّم عنه
    bias: Trend               # bullish | bearish | undefined
    quote: str                # نصّه حرفيًّا
    levels: Dict[str, float] = field(default_factory=dict)
    void: str = ""            # سبب الإبطال — إن أُبطل

    @property
    def live(self) -> bool:
        return not self.void

    def render(self) -> str:
        head = f"{self.day} · {self.timeframe} · {self.bias}"
        if self.void:
            head += f"   ⛔ مُبطَل: {self.void}"
        out = [head, f'    «{self.quote}»']
        if self.levels:
            out.append("    " + " · ".join(f"{k} {v:g}" for k, v in self.levels.items()))
        return "\n".join(out)


@dataclass(frozen=True)
class Verdict:
    """مقارنةُ حكمٍ واحد بما قالته قاعدةٌ ما."""

    call: Call
    got: Trend
    agrees: bool


@dataclass
class Scorecard:
    rule: str
    verdicts: List[Verdict] = field(default_factory=list)

    @property
    def live(self) -> List[Verdict]:
        return [v for v in self.verdicts if v.call.live]

    @property
    def hits(self) -> int:
        return sum(1 for v in self.live if v.agrees)

    @property
    def n(self) -> int:
        return len(self.live)

    def render(self) -> str:
        out = [f"{self.rule}:"]
        for v in self.live:
            out.append(f"  {v.call.day}  المدرّب {v.call.bias:10}"
                       f" · القاعدة {v.got:10} {'✅' if v.agrees else '❌'}")
        voided = [v for v in self.verdicts if not v.call.live]
        for v in voided:
            out.append(f"  {v.call.day}  ⛔ مُبطَل — {v.call.void}")
        out.append(f"  ⇒ {self.hits}/{self.n}")
        return "\n".join(out)


# ─────────────────────────── التحقّق ───────────────────────────


class InvalidCall(ValueError):
    """حكمٌ لا يصلح للتسجيل — يُرفض عند الكتابة لا عند القياس."""


def validate(call: Call) -> Call:
    """
    ⛔ يُرفض الحكم الناقص **وقت تسجيله**، لا وقت استعماله.

    فحُكمٌ بلا نصّ لا يمكن مراجعة ترجمتي فيه، وحُكمٌ بحالةٍ غير
    الثلاث ترجمةٌ لم تكتمل.
    """
    try:
        Date.fromisoformat(call.day)
    except ValueError as exc:
        raise InvalidCall(f"تاريخ غير صالح: {call.day!r}") from exc
    if call.bias not in BIAS:
        raise InvalidCall(f"حالة غير معروفة: {call.bias!r} — والمسموح {BIAS}")
    if not call.quote.strip():
        raise InvalidCall("حكمٌ بلا نصّ — لا تُقاس ترجمةٌ لا يُراجَع أصلها")
    if not call.timeframe.strip():
        raise InvalidCall("حكمٌ بلا إطار")
    return call


# ─────────────────────────── الملفّ ───────────────────────────


def load(path: str) -> List[Call]:
    """يقرأ JSONL متسامحًا مع السطر المبتور — كما في بقيّة السجلّات."""
    out: List[Call] = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            out.append(Call(
                day=d.get("day", ""),
                timeframe=d.get("timeframe", ""),
                bias=d.get("bias", "undefined"),
                quote=d.get("quote", ""),
                levels=d.get("levels", {}) or {},
                void=d.get("void", ""),
            ))
    return out


def append(path: str, call: Call) -> Call:
    """
    يُلحِق حكمًا — بعد التحقّق منه.

    ولا يُعاد كتابة الملفّ أبدًا: الإلحاق وحده يضمن أن ما سُجّل يوم
    الاثنين لا يتغيّر يوم الجمعة.
    """
    validate(call)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "day": call.day, "timeframe": call.timeframe, "bias": call.bias,
            "quote": call.quote, "levels": call.levels, "void": call.void,
        }, ensure_ascii=False) + "\n")
    return call


def latest(calls: Sequence[Call], timeframe: Optional[str] = None) -> Dict[str, Call]:
    """
    آخر حكمٍ لكل يوم — فقد يتكلّم عن الإطار نفسه مرّتين في اليوم.

    والإبطال يُحترَم: حكمٌ مُبطَل لا يُزيح حكمًا حيًّا سبقه.
    """
    out: Dict[str, Call] = {}
    for c in calls:
        if timeframe is not None and c.timeframe != timeframe:
            continue
        if not c.live and c.day in out:
            continue
        out[c.day] = c
    return out


# ─────────────────────────── المقارنة ───────────────────────────


def score(calls: Sequence[Call], measured: Dict[str, Trend], rule: str,
          timeframe: str) -> Scorecard:
    """
    يقارن أحكام المدرّب بما قالته قاعدةٌ ما، يومًا بيوم.

    `measured` = {اليوم: الهيكل كما حكمت به القاعدة} على `timeframe`.

    ⚠️ **و`timeframe` مُلزَم لا اختياريّ.** وقد وقع الخطأ الذي يمنعه:
    في أوّل تشغيلٍ لهذه الوحدة قِستُ حكم الجمعة — وهو عن **إطار
    الساعة** («على إطار الساعة عملنا ماركت ستراكتشر شفت») — على
    هيكل **الأربع ساعات**، فسجّلتُه خطأً وهو ليس خطأً أصلًا. وحكمٌ
    على إطارٍ لا يُقاس على إطارٍ آخر.

    ويومٌ لا قياس له **يُسقَط** ولا يُحسب خطأً: السلسلة قد تبدأ بعده
    أو تنقطع، وذلك عيبُ التغطية لا عيبُ القاعدة.
    """
    card = Scorecard(rule)
    for day, call in sorted(latest(calls, timeframe).items()):
        got = measured.get(day)
        if got is None:
            continue
        card.verdicts.append(Verdict(call, got, got == call.bias))
    return card


def compare(cards: Sequence[Scorecard], min_gap: int = 2) -> str:
    """
    ⭐ **وهذا ما عجز عنه أسبوع 09-07…11**: القواعد تقاربت
    (1/5 · 1/5 · 2/5) فلم يترجّح شيء، وكان الصواب أن يُقال «لا حكم»
    لا أن يُختار الأعلى.

    فلا يُعلَن فائز إلا إذا سبق الثاني بـ`min_gap` على الأقلّ.
    """
    live = [c for c in cards if c.n]
    lines = [c.render() for c in cards]
    if not live:
        return "\n\n".join(lines + ["⛔ لا قياس — لا يومَ قابلًا للمقارنة."])

    ranked = sorted(live, key=lambda c: -c.hits)
    best = ranked[0]
    lines.append("")
    if len(ranked) == 1:
        lines.append(f"قاعدةٌ واحدة فقط ({best.rule}) — لا مقارنة.")
    elif best.hits - ranked[1].hits >= min_gap:
        lines.append(f"⇒ **{best.rule}** يسبق بـ{best.hits - ranked[1].hits}"
                     f" على {best.n} يومًا.")
    else:
        lines.append(f"⛔ **لا حكم**: الفارق {best.hits - ranked[1].hits}"
                     f" على {best.n} يومًا — دون العتبة ({min_gap}).")
        lines.append("   والعيّنة تُوسَّع، ولا يُختار الأعلى بفارقٍ كهذا.")
    return "\n\n".join(lines)
