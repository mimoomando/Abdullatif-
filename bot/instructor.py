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

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⛔⛔⛔ **IN1 — والسطرُ أعلاه يُبطل آليّةَ الإبطال.**            ║
    ║  **وُصف 2026-09-30 · ولم يُختَر فيه.**                         ║
    ║                                                              ║
    ║  فترويسةُ هذه الوحدة تقول:                                    ║
    ║      [وإن تبيّن أن تسجيلها خطأ فالصواب **إبطالها صراحةً**      ║
    ║       (`void` مع سببه) لا إعادة صياغتها]                     ║
    ║                                                              ║
    ║  والملفُّ **إلحاقيٌّ لا يُعاد كتابته** ⇒ فالإبطالُ سطرٌ جديدٌ    ║
    ║  على اليوم نفسِه يحمل `void`. **وهذا السطرُ يتخطّاه**:          ║
    ║  الحكمُ الحيُّ سبقه فيبقى.                                     ║
    ║                                                              ║
    ║  ⛔ **ومقيسٌ**: حكمٌ حيٌّ ثمّ إبطالُه ⇒ `live = True` ·         ║
    ║  و`void = ''` · و`n = 1` · و`hits = 1`. **فالمُبطَلُ ما زال    ║
    ║  يُحسب.**                                                     ║
    ║                                                              ║
    ║  ⇒ **فالإبطالُ لا يعمل إلّا إن حمله التسجيلُ الأوّل** — أي      ║
    ║  إلّا في الحالة التي لا يُحتاج فيها إليه. **و[إن تبيّن]**      ║
    ║  تعني بعدَه لا معه.                                           ║
    ║                                                              ║
    ║  ⚠️⚠️ **وهذا ليس سهوًا**: السلوكُ مثبَّتٌ باختبارٍ صريح          ║
    ║  (`test_a_void_does_not_displace_a_live_call_for_that_day`)   ║
    ║  ⇒ **فهما نيّتان معلنتان تتصادمان**، لا عطبٌ يُصلَح.            ║
    ║                                                              ║
    ║  **والطريقان، ولا أختار** (والوحدةُ غيرُ موصولة فلا عجلة):     ║
    ║    ① **الأحدثُ يفوز مطلقًا** — يُحذف الاستثناء. يعمل الإبطال،  ║
    ║       ويصير سطرُ `void` الشارد قادرًا على محو حكمٍ حيّ.         ║
    ║    ② **حقلٌ يسمّي ما يُبطَل** (`voids: day`) — الإبطالُ صريحٌ    ║
    ║       والشاردُ لا يمحو شيئًا. وهو تغييرُ صيغةِ الملفّ.          ║
    ║                                                              ║
    ║  ⇒ **والقرارُ منهجيٌّ لا تقنيّ** — وهذه الوحدةُ بُنيت أصلًا      ║
    ║  لأنّ قرارًا منهجيًّا اتُّخذ بلا تصريح. فلا يُعاد.               ║
    ╚══════════════════════════════════════════════════════════════╝
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


# ═══════════════════════ الوصل — 2026-10-02 ═══════════════════════
#
# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⭐⭐⭐ **وُصلت الوحدةُ بطلب المستخدم — 2026-10-02.**               ║
# ║                                                                  ║
# ║  وكانت في `UNWIRED` منذ أوّل جرد: **مبنيّةٌ ومختبَرةٌ ولا يبلغها**   ║
# ║  **مدخلُ تشغيل**. وصار لها مدخلٌ يُبرهِن على نفسه (`__main__`).     ║
# ║                                                                  ║
# ║  ⭐ **ولمَ الآن؟** لأنّ مدخلَها الحقيقيّ وصل: تحاليلُ 28·29·30     ║
# ║  سبتمبر. وفيها **أوّلُ مقابلةٍ مباشرة**: يوم 30/9 اشترى المدرّبُ   ║
# ║  على 4182 **وباع البوتُ على 4182.52** — وكلاهما ربح. وحادثةٌ      ║
# ║  كهذه لا تُقاس بالذاكرة، **وهذه الوحدةُ هي أداةُ قياسها**.        ║
# ╚══════════════════════════════════════════════════════════════════╝

CALLS_PATH = os.path.join("runs", "instructor.jsonl")
DECISIONS_PATH = os.path.join("runs", "decisions.jsonl")

# الهيكلُ كما يسمّيه البوت في أوّل فحصٍ من السلسلة
_STRUCTURE_CHECK = "الهيكل محدد"


@dataclass
class Coverage:
    """
    كم يومًا قُرئ، وكم يومًا تعذّر — **والثاني يُقال لا يُبتلَع**.

    ⛔ **وهذا هو بندُ `CLAUDE.md`**: [حين تبني بوّابةً اجعلها تكتب
    سطرًا حين لا تعمل]. فيومٌ لا يُقرأ هيكلُه **ليس يومًا لا رأيَ
    فيه** — بل يومٌ عجزت القراءةُ عنه، والفرقُ يقلب أيَّ نسبة.
    """

    days: int = 0
    unreadable: int = 0
    rows: int = 0


def _trend_from_checks(checks: Sequence[dict]) -> Optional[str]:
    """
    هيكلُ `classify_trend` من سلسلة الفحص — أو `None` إن تعذّر.

    ⚠️⚠️ **وهذا انتزاعٌ من نصٍّ حرّ، لا حقلٌ نظيف.** فصفُّ القرار
    يحمل `structure_closes` حقلًا، **ولا يحمل هيكلَ `classify_trend`
    إلّا داخل دليلِ أوّلِ فحص** ([bullish — آخر قمة …]).

    ⇒ **فيُرجَع `None` عند العجز، ويُعَدّ** — ولا يُقرأ العجزُ
    [هيكلًا غيرَ محدَّد]. وهما شيئان: الأوّلُ عجزُ قراءةٍ عندي،
    والثاني حكمُ البوت.
    """
    for c in checks or ():
        if c.get("name") != _STRUCTURE_CHECK:
            continue
        if not c.get("passed"):
            return "undefined"          # ⬅ حكمُ البوت نفسِه، لا عجزي
        head = str(c.get("evidence", "")).strip().split()
        return head[0] if head and head[0] in BIAS else None
    return None


def measured_from_log(path: str, timeframe: str,
                      field: str = "closes") -> tuple:
    """
    هيكلُ البوت يومًا بيوم من السجلّ الحيّ — مع **تغطيتِه**.

    `field`: `closes` ⇒ `structure_closes` (قاعدةُ المدرّب نفسُها،
    حقلٌ نظيف) · `swings` ⇒ `classify_trend` (انتزاعٌ من الفحص).

    ⭐ **وآخرُ شمعةٍ في اليوم هي حكمُ اليوم.** فالمدرّب يسجّل تحليلَه
    صباحًا ويحكم على اليوم كلِّه، والسجلُّ يحمل عشرات الشموع فيه.
    **وهذا اختياري أنا** — ويُقال، لأنّ اختيارَ أوّلِ شمعةٍ يعطي
    رقمًا آخر. (وهو صنفُ [رقمٌ يقلبه اختيارُك].)
    """
    out: Dict[str, str] = {}
    cov = Coverage()
    if not os.path.exists(path):
        return out, cov
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("poi_tf") != timeframe:
                continue
            cov.rows += 1
            day = str(d.get("candle_time", ""))[:10]
            if not day:
                continue
            got = (d.get("structure_closes") if field == "closes"
                   else _trend_from_checks(d.get("checks") or ()))
            if got is None:
                cov.unreadable += 1
                continue
            out[day] = got                  # ⬅ الأخيرةُ تغلب
    cov.days = len(out)
    return out, cov


# ─────────────────────────── المدخل ───────────────────────────


def _parse_levels(pairs: Optional[Sequence[str]]) -> Dict[str, float]:
    """`اسم=رقم` ⇒ قاموس — ويُصاح بالمعطوب لا يُبتلَع."""
    out: Dict[str, float] = {}
    for p in pairs or ():
        if "=" not in p:
            raise InvalidCall(f"مستوًى بلا علامة يساوي: {p!r}")
        name, raw = p.split("=", 1)
        try:
            out[name.strip()] = float(raw)
        except ValueError as exc:
            raise InvalidCall(f"مستوًى غيرُ رقم: {p!r}") from exc
    return out


def _cmd_add(args) -> int:
    try:
        call = Call(day=args.day, timeframe=args.tf, bias=args.bias,
                    quote=args.quote, levels=_parse_levels(args.level),
                    void=args.void or "")
        validate(call)
    except InvalidCall as exc:
        print(f"⛔ {exc}")
        return 1
    append(args.calls, call)
    print("✅ سُجّل:")
    print(call.render())
    if call.void:
        # ⛔⛔ **IN1 — ويُصاح به عند اللحظة التي يعضّ فيها.**
        print()
        print("⛔⛔⛔ **تحذير — والإبطالُ قد لا يعمل (IN1):**")
        print("   `latest` تتخطّى المُبطَل إن سبقه حكمٌ حيٌّ في اليوم")
        print("   نفسِه ⇒ **فالمُبطَلُ ما زال يُحسب ويُصيب**.")
        print("   وهو قرارٌ منهجيٌّ معلَّقٌ — انظر IN1 في ترويسة `latest`.")
    return 0


def _cmd_list(args) -> int:
    calls = load(args.calls)
    if not calls:
        print(f"⛔ لا أحكامَ مسجَّلة في {args.calls}")
        return 0
    for c in calls:
        print(c.render())
    live = [c for c in calls if c.live]
    print(f"\n⇒ {len(live)} حكمًا حيًّا من {len(calls)}")
    return 0


def _cmd_score(args) -> int:
    calls = load(args.calls)
    if not calls:
        print(f"⛔ لا أحكامَ مسجَّلة في {args.calls} — ولا شيءَ يُقاس.")
        print("   سجّل حكمًا:  python -m bot.instructor add --help")
        return 1

    cards = []
    for field, label in (("closes", "قاعدةُ الإغلاقات (قاعدةُ المدرّب)"),
                         ("swings", "classify_trend (الذي يقرّر فعلًا)")):
        measured, cov = measured_from_log(args.log, args.tf, field)
        if cov.unreadable:
            # ⛔ [اجعلها تكتب سطرًا حين لا تعمل]
            print(f"[!!] {label}: تعذّرت قراءةُ {cov.unreadable} صفٍّ من "
                  f"{cov.rows} — **وهي ليست أيّامًا بلا رأي**.")
        cards.append(score(calls, measured, label, args.tf))

    print(f"\n── أحكامُ المدرّب مقابل البوت · {args.tf} ──\n")
    print(compare(cards, min_gap=args.min_gap))
    n = cards[0].n if cards else 0
    print(f"\n⚠️ والعيّنة {n} يومًا — **ولا تُثبت نسبةَ إصابة**.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    `python -m bot.instructor` — تسجيلُ أحكام المدرّب وقياسُها.

    ⛔ **ولا يقرأ شمعةً ولا يفتح جسرًا.** يقرأ السجلَّ المكتوبَ
    ويكتب سطرًا في `runs/instructor.jsonl` — لا أكثر.
    """
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m bot.instructor",
        description="تحاليلُ المدرّب مسجَّلةً قبل القياس — ثمّ مقيسة")
    ap.add_argument("--calls", default=CALLS_PATH)
    sub = ap.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="سجّل حكمًا — ويُرفض الناقص")
    a.add_argument("--day", required=True, help="YYYY-MM-DD")
    a.add_argument("--tf", required=True, help="الإطار الذي تكلّم عنه")
    a.add_argument("--bias", required=True, choices=BIAS)
    a.add_argument("--quote", required=True, help="نصُّه حرفيًّا")
    a.add_argument("--level", action="append", metavar="اسم=رقم")
    a.add_argument("--void", default="", help="سببُ الإبطال — انظر IN1")
    a.set_defaults(fn=_cmd_add)

    ls = sub.add_parser("list", help="اعرض ما سُجّل")
    ls.set_defaults(fn=_cmd_list)

    sc = sub.add_parser("score", help="قِس الأحكامَ على السجلّ الحيّ")
    sc.add_argument("--log", default=DECISIONS_PATH)
    sc.add_argument("--tf", default="M15")
    sc.add_argument("--min-gap", type=int, default=2, dest="min_gap")
    sc.set_defaults(fn=_cmd_score)

    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
