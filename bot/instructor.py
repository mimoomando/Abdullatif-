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
import re
from dataclasses import dataclass, field
from datetime import date as Date
from typing import Dict, List, Optional, Sequence, Tuple

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


ANALYSES_DIR = os.path.join("knowledge", "source", "analyses")


def _cmd_infer(args) -> int:
    """
    يقرأ تحاليلَ المدرّب **ويستنتج حكمَ كلّ يومٍ بقاعدةٍ مكتوبة**.

    ⛔ **ولا يكتب شيئًا بلا `--write`** — فالعرضُ أوّلًا، والتسجيلُ
    بطلبٍ صريح.
    """
    import glob

    files = sorted(glob.glob(os.path.join(args.dir, "*.md")))
    if not files:
        print(f"⛔ لا تحاليلَ في {args.dir}")
        return 1

    AR = {"bullish": "صاعد", "bearish": "هابط", "undefined": "غير محدَّد"}
    n_written = 0
    for path in files:
        day = os.path.basename(path)[:10]
        text = open(path, encoding="utf-8").read()
        bias, evidence, dropped = read_bias(text)
        print(f"\n── {day}  ⇒  **{AR[bias]}**")
        for e in evidence:
            print(f"   ✅ {e}")
        for d in dropped:
            print(f"   ⛔ {d}")
        if not evidence and not dropped:
            print("   (لا عبارةَ موقفٍ في النصّ)")
        if not args.write:
            continue
        if bias == "undefined" and not evidence:
            print("   ⇒ لا يُسجَّل: لا دليلَ أصلًا")
            continue
        quote = evidence[0] if evidence else "(تعارض)"
        try:
            append(args.calls, Call(day=day, timeframe=args.tf, bias=bias,
                                    quote=quote))
            n_written += 1
        except InvalidCall as exc:
            print(f"   ⛔ {exc}")

    print(f"\n⇒ {len(files)} تحليلًا"
          + (f" · سُجّل منها {n_written}" if args.write else " · (عرضٌ فقط)"))
    print("\n⚠️⚠️ **والقاعدةُ ليست عمياء**: كُتبت وقد قرأتُ تحاليلَ")
    print("   28·29·30 سبتمبر. ⇒ **وفحصُها الحقيقيُّ يومٌ لم يُقرأ بعد.**")
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

    inf = sub.add_parser("infer", help="استنتج الأحكامَ من التحاليل")
    inf.add_argument("--dir", default=ANALYSES_DIR)
    inf.add_argument("--tf", default="M15")
    inf.add_argument("--write", action="store_true",
                     help="سجّل ما استُنتج — وبلاه عرضٌ فقط")
    inf.set_defaults(fn=_cmd_infer)

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



# ═════════════ استنتاجُ الحكم من النصّ — 2026-10-02 ═════════════
#
# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⭐⭐⭐ **بطلب المستخدم 2026-10-02**: [انا لا اريد ان اقول لك      ║
# ║  شيء — اريدك ان تستنتج من السجل، لان بعدها عندما نشغل البوت      ║
# ║  انا لم اقول لك شيء والبوت يستنتج وحده].                         ║
# ║                                                                  ║
# ║  ⚠️ **وترويسةُ هذه الوحدة تحذّر من الترجمة** — فهل هذا نقضٌ لها؟  ║
# ║  **لا.** فالخشيةُ المكتوبةُ هناك ليست من الآليّة، بل من أن        ║
# ║  أُترجم **بعد أن أرى النتيجة**:                                   ║
# ║      [فمن يقرؤه **وهو يعرف النتيجة** يرجّح — بلا قصد —            ║
# ║       القراءةَ التي تناسبها]                                     ║
# ║  ⇒ **وقاعدةٌ مكتوبةٌ تُطبَّق على كلّ يومٍ سواءً تغلق هذا الباب**،   ║
# ║  لأنّها لا ترى نتيجةً أصلًا. وهي **أقوى** من حكمي يومًا بيوم.      ║
# ║                                                                  ║
# ║  ⚠️⚠️ **وحدُّها يُقال، وهو ثقيل**: كتبتُها **وقد قرأتُ** تحاليلَ   ║
# ║  28·29·30 سبتمبر. فليست عمياء. ⇒ **والفحصُ الحقيقيُّ لها هو       ║
# ║  اليومُ القادم الذي لم أقرأه** — لا هذه الثلاثة.                  ║
# ╚══════════════════════════════════════════════════════════════════╝

# ⭐ **عباراتُ الموقف — وهي وحدَها تُحسب.**
#
#   و«هبوط» و«صعود» وحدَهما **لا تُحسبان**: المدرّبُ يصف حركةَ السوق
#   في كلّ جملةٍ تقريبًا، ووصفُ الحركة ليس حكمًا. ⇒ فلا يُقبل إلّا
#   ما كان **موقفًا بضمير المتكلّم**: [تحليلي] · [نحن متوجهين] ·
#   [اشترينا] · [بحترم].
#
# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⛔⛔⛔ **ووُسّعت القائمةُ 2026-10-09 — بقرار المستخدم.**          ║
# ║  **والثمنُ يُقال في موضعه، لا في ملفٍّ آخر.**                      ║
# ║                                                                  ║
# ║  جرى أوّلُ فحصٍ أعمى (5 · 6 · 8 أكتوبر) فأعطى **1 من 3**،         ║
# ║  فقرأتُ اليومين الساقطين لأشخّص. ⇒ **فكلُّ ما أُضيف أدناه         ║
# ║  مكتوبٌ وأنا أرى النصَّ الذي أسقطه** — وهو عينُ ما تحذّر منه      ║
# ║  ترويسةُ هذه الوحدة.                                             ║
# ║                                                                  ║
# ║  ⇒ **ولا تُقرأ تغطيةُ 5 و6 بعد اليوم إنجازًا** — القاعدةُ         ║
# ║  فُصّلت عليهما. **و10-08 وحدَه إصابةٌ عمياءُ نظيفة.**              ║
# ║                                                                  ║
# ║  ⭐ **والإضافاتُ مُشتقّةٌ من مسحِ السجلّ لا من خيالي**: مُسح        ║
# ║  كلُّ ضمير متكلّمٍ في التحاليل الاثني عشر، وقُرئ جوارُ كلّ         ║
# ║  موضع. **والمسحُ هو الذي كشف الفخّين أدناه** — ولولاه لأدخل      ║
# ║  التوسيعُ عطبين بدل أن يرفع تغطية.                                ║
# ╚══════════════════════════════════════════════════════════════════╝
STANCE: Tuple[Tuple[str, str], ...] = (
    ("bearish", "تحليلي هابط"),
    ("bullish", "تحليلي صاعد"),
    ("bearish", "متوجهين هبوط"),
    ("bullish", "متوجهين صعود"),
    ("bullish", "مكملين صعود"),
    ("bearish", "مكملين هبوط"),
    ("bullish", "اشترينا"),
    ("bearish", "بعنا"),
    ("bullish", "بحترم الصعود"),
    ("bearish", "بحترم الهبوط"),
    # ── أُضيفت 2026-10-09 · وكلُّ واحدةٍ لها موضعٌ في السجلّ ──
    #
    # ⭐ **صيغةُ المفرد** — والقائمةُ كانت تحمل الجمعَ وحدَه.
    #   و«متوجه» في **سبعة مواضعَ وخمسةِ أيّام**، والجمعُ في عشرة.
    ("bearish", "متوجه هبوط"),      # 09-10 «يا اما انا متوجه هبوط»
    ("bullish", "متوجه صعود"),
    ("bearish", "متوجه للهبوط"),    # 09-25 ×2 — وأحدهما منفيّ، انظر NEGATION
    ("bullish", "متوجه للصعود"),    # 09-30 «فهو متوجه للصعود»
    ("bullish", "متوجه صعودا"),     # 10-05 «هو متوجه صعودا»
    ("bearish", "متوجه هبوطا"),     # ⬅ مقابلُها، ولا موضعَ له بعد
    #
    # ⭐ **وتوقُّعٌ بضمير المتكلّم** — 10-05 وفيها أربعةُ مواضع.
    #   ⛔ **وثلاثةٌ منها فخّ**: واحدٌ عن الدي إكس واي، وواحدٌ عن
    #   انهيار 2008. ⇒ **فلا تُضاف [اتوقع] عاريةً** — بل بلفظها
    #   الحامل للاتّجاه، ومعها حارسُ الأداة أدناه.
    ("bullish", "اتوقع انه هي نهايه الهبوط"),
    ("bearish", "اتوقع انه هي نهايه الصعود"),   # ⬅ مقابلُها، ولا موضعَ له
    #
    # ⭐ **وامتناعٌ عن الشراء** — 10-06.
    #   ⚠️ **ويُدخَل منفيًّا بقصد**: اللفظُ «ما بدنا نفكر بالصعود»،
    #   والعبارةُ المسجّلةُ هنا موجبةٌ ويقلبها حارسُ النفي أدناه.
    ("bullish", "بدنا نفكر بالصعود"),
    ("bearish", "بدنا نفكر بالهبوط"),           # ⬅ مقابلُها، ولا موضعَ له
)

# ⛔⛔ **والفخُّ الأكبر: عبارةُ موقفٍ داخل شرطٍ ليست موقفًا.**
#
#   29/9: «**في حال** غير هيكل برجع بحترم الهبوط»  ⬅ شرطٌ لا حكم
#   28/9: «**في حال** ما قدر يقعد فوق… متوجهين هبوط» ⬅ وهذا أيضًا
#
# ⇒ فما سبقته أداةُ شرطٍ في النافذة أدناه **يُسقَط ويُسمّى**.
CONDITIONAL: Tuple[str, ...] = ("في حال", "اذا ", "لو ", "اما لا")
CONDITIONAL_WINDOW = 70          # حرفًا قبل العبارة

# ⭐⭐ **وفعلٌ وقع لا يحكمه شرطٌ سبقه** — ويُستثنى.
#
#   30/9: «**اذا** انت منك مشتري من تحت · نحن امبارح **اشترينا** على
#          4140» — والشرطُ على جملةٍ أخرى، **وهو اشترى فعلًا**.
#
# ⇒ فـ[اشترينا] و[بعنا] **خبرٌ عن فعلٍ وقع**، لا توجّهٌ مشروط.
#   وبقيّةُ العبارات ([تحليلي] · [متوجهين] · [مكملين] · [بحترم])
#   **توجّهاتٌ**، فيحكمها الشرط.
DONE_DEEDS: Tuple[str, ...] = ("اشترينا", "بعنا")

# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⛔⛔⛔ **فخُّ النفي — ولولا المسحُ لانقلب حكمٌ قائم.**            ║
# ║  **كُشف بمسح السجلّ 2026-10-09، قبل التوسيع لا بعده.**           ║
# ║                                                                  ║
# ║  09-25: «انه سوقنا **ما هو** متوجه للهبوط»                       ║
# ║  10-06: «حاليا **ما بدنا** نفكر بالصعود»                         ║
# ║                                                                  ║
# ║  ⇒ **واللفظُ هابطٌ والمعنى صاعد، والعكس.** فلو أُضيفت             ║
# ║  [متوجه للهبوط] بلا هذا الحارس **لصار 09-25 هابطًا بنصفه**       ║
# ║  فتعارض مع [متوجهين صعود] القائم ⇒ **وانقلب يومٌ محكومٌ إلى       ║
# ║  غير محدَّد على دليلٍ معناه عكسُ لفظه.**                          ║
# ║                                                                  ║
# ║  ⇒ **والنفيُ يقلب ولا يُسقط** — لأنّه حاملُ المعنى هنا، لا        ║
# ║  مانعُه. **وهو خلافُ الشرط**: الشرطُ يُسقط لأنّ المتكلّم لم       ║
# ║  يتّخذ موقفًا بعد، **والنفيُ موقفٌ متّخذٌ في الجهة المقابلة.**     ║
# ║                                                                  ║
# ║  ⚠️ **والقلبُ يُعلَن في الدليل** بوسم ⟨نفي⟩ — فلا يُقرأ رقمٌ      ║
# ║  مقلوبٌ على أنّه مطابقة.                                         ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# ⛔ **وعطبٌ ثانٍ كُتب وأُصلح في ساعته**: كانت الأداةُ تُطلب في
#   **نافذةٍ** قبل العبارة، و«ما **بدنا** نفكر بالصعود» أداتُها
#   ملاصقةٌ للعبارة ⇒ **فلا تدخل النافذة أصلًا** (العبارةُ تبدأ من
#   «بدنا»). ⇒ **فالشرطُ أن تكون أداةُ النفي هي الكلمةَ السابقةَ
#   مباشرةً** — وذلك أضيقُ وأصحُّ معًا: «مثل **ما** قلنا» بعيدةٌ
#   فلا تقلب، و«**ما** بدنا» ملاصقةٌ فتقلب.
NEGATION: Tuple[str, ...] = ("ما", "ما هو", "مش", "ليس", "وليس", "مو")
_FLIP = {"bullish": "bearish", "bearish": "bullish"}


def _negated(before: str) -> bool:
    """أأداةُ النفي هي الكلمةُ السابقةُ مباشرةً؟ — لا في الجوار."""
    b = before.rstrip()
    return any(b.endswith(n) and (len(b) == len(n)
                                  or not b[-len(n) - 1].isalnum())
               for n in NEGATION)


# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⛔⛔⛔ **وفخُّ الأداة — والمدرّب يحلّل أكثر من أداة في الفيديو.** ║
# ║                                                                  ║
# ║  10-05: «**فاتوقع هبوط الدي اكس واي** بشكل عنيف جدا»             ║
# ║                                                                  ║
# ║  ⇒ **وهذا هبوطُ الدولار لا الذهب — ومعناه صعودُ الذهب.**         ║
# ║  فلو حُسب لصار اليومُ هابطًا **على جملةٍ تقول عكسَه**.            ║
# ║                                                                  ║
# ║  ⚠️ **ولا يُقلب هنا** (كالنفي) — فالعلاقةُ بين الذهب والدولار     ║
# ║  **عكسيّةٌ بالعادة لا بالضرورة**، وبناؤها قاعدةً اختراعٌ          ║
# ║  (القاعدة ①). ⇒ **يُسقَط ويُسمّى**، كالشرط سواءً.                 ║
# ║                                                                  ║
# ║  ⚠️⚠️ **وحدُّه يُقال**: القائمةُ أسماءُ أدواتٍ رآها المسحُ في     ║
# ║  هذه التحاليل. **وأداةٌ رابعةٌ لم ترد بعد ستمرّ.**                ║
# ╚══════════════════════════════════════════════════════════════════╝
OTHER_INSTRUMENT: Tuple[str, ...] = (
    "الدي اكس واي", "الدولار", "السندات", "العائد",
    "البيتكوين", "العملات الرقميه", "البورصه",
)
INSTRUMENT_WINDOW = 45           # حرفًا بعد العبارة — فالأداةُ تلي الفعل

# ⚠️ **وما لا يُحسب وإن بدا حاسمًا** — ويُقال كي لا يُضاف لاحقًا بلا تفكير:
#   · «متوجهين **قطعا الى ال 4070**» — الاتّجاهُ يلزمه السعرُ الحاليّ،
#     ولا يُعرف من النصّ. **فلفظيًّا بلا اتّجاه.**
#   · «متوجهين **للاختبار الاخير**» — ولا اتّجاهَ فيه.
#   · «انا بفضل انه هو **يصحح** لدرجه 200» — والتصحيحُ صعودٌ أو هبوط
#     بحسب الاتّجاه السابق. **فلفظيًّا بلا اتّجاه.**


#: سطرُ طابعٍ زمنيّ — ويُسقَط، وإلّا **قطع العبارة نصفين**
_STAMP = re.compile(r"^\s*\d{1,2}:\d{2}\b.{0,30}$")

#: حرفٌ عربيّ — لحدود الكلمة
_AR = "\u0600-\u06FF"


def _word(phrase: str) -> "re.Pattern":
    """
    العبارةُ **كلمةً مستقلّة** — لا جزءًا من كلمة.

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⛔⛔⛔ **عطبٌ وقع فعلًا — 2026-10-02.**                        ║
    ║                                                              ║
    ║  كان البحثُ بالنصّ الجزئيّ، فالتقط [بعنا] **داخل**            ║
    ║  «الارتداد **تبعنا** من بريكر بلوك» ⇒ فصار تحليلُ 09-07     ║
    ║  **هابطًا على دليلٍ ليس من كلامه أصلًا**.                      ║
    ║                                                              ║
    ║  ⭐ **ولولا أنّ الدليل يُطبع لمرّ.** ⇒ فالأدلّةُ تُعرَض لا       ║
    ║  تُبتلَع، وهي التي كشفت العطب.                                 ║
    ╚══════════════════════════════════════════════════════════════╝

    ⚠️ **ويُسمح بالواو والفاء سابقتين** («**و**بعنا» · «**ف**نحن»)،
    وهما أداتا عطفٍ لا جزءٌ من الفعل.

    ⚠️⚠️ **وحدُّه يُقال**: الصيغةُ الملحقةُ تُفوَّت — «بعنا**ها**» لا
    تُطابَق. **وذلك تفويتٌ في الاتّجاه الآمن**: يُرجع [غير محدَّد]
    ولا يخترع حكمًا. وفتحُ اللاحقة يُعيد عطبَ [بعنا] في «بعناية».
    """
    return re.compile(f"(?<![{_AR}])[وف]?{re.escape(phrase)}(?![{_AR}])")


def _fenced(text: str) -> str:
    """
    ما بين السياج وحدَه — **فالترويسةُ كتابتي أنا**.

    ⭐ وهو عرفُ `bot.quotes` نفسُه: [لا يُقرأ إلّا ما بين ``` ```]،
    وإلّا صدّقت الأداةُ نفسَها.
    """
    parts = text.split("```")
    body = "\n".join(parts[1::2]) if len(parts) > 2 else ""
    # ⛔⛔ **والطوابعُ الزمنيّةُ تُسقَط — وعطبٌ حقيقيٌّ كشفه الرقم:**
    #   «فانا بحترم» ⏎ [2:01 دقيقتان وثانية] ⏎ «الصعود وبصعد معه»
    #   ⇒ فعبارةُ [بحترم الصعود] **لا تُطابَق أبدًا** بلا هذا السطر.
    return "\n".join(l for l in body.split("\n") if not _STAMP.match(l))


def read_bias(text: str) -> tuple:
    """
    حكمُ المدرّب من نصّه — **بقاعدةٍ مكتوبةٍ لا بتقديري**.

    يُرجع `(bias, evidence, dropped)`:
      · `bias`     bullish | bearish | undefined
      · `evidence` العباراتُ التي حُسبت، بسياقها
      · `dropped`  ما أُسقط لأنّه داخل شرط — **ويُعرَض لا يُبتلَع**

    ⛔ **والتعارضُ يُرجع `undefined`** ولا يُرجَّح. فالوحدةُ لها ثلاثُ
    حالات، و[غير محدَّد] **حالةٌ لا عجز**.
    """
    body = _fenced(text) or text
    flat = " ".join(body.split())
    hits: Dict[str, List[str]] = {"bullish": [], "bearish": []}
    dropped: List[str] = []

    for bias, phrase in STANCE:
        for m in _word(phrase).finditer(flat):
            i = m.start()
            before = flat[max(0, i - CONDITIONAL_WINDOW):i]
            context = flat[max(0, i - 40):i + len(phrase) + 40].strip()
            conditional = (phrase not in DONE_DEEDS
                           and any(c in before for c in CONDITIONAL))
            # ⬇️ أداةٌ أخرى **بعد** العبارة ⇒ الحكمُ ليس على الذهب
            after = flat[m.end():m.end() + INSTRUMENT_WINDOW]
            if any(o in after for o in OTHER_INSTRUMENT):
                dropped.append(f"{phrase} ⟨أداةٌ أخرى⟩ … {context}")
                continue
            # ⬇️ نفيٌ **ملاصقٌ** قبلها ⇒ الموقفُ في الجهة المقابلة
            # ⛔ **ولا يُكتب على `bias`**: هو متغيّرُ الحلقة، فقلبُه
            #    يسري على المطابقة التالية للعبارة نفسِها. عطبٌ كُتب
            #    وأُصلح في موضعه 2026-10-09 — **وحُرس باختبار.**
            negated = _negated(flat[:i])
            side = _FLIP[bias] if negated else bias
            if conditional:
                dropped.append(f"{phrase} ⟨شرط⟩ … {context}")
            else:
                # ⚠️⚠️ **وثغرةٌ معلومةٌ تُعلَن عند الدليل نفسِه:**
                #   [بعنا] و[اشترينا] قد تكون **سردًا لصفقةٍ سابقة**
                #   لا موقفَ اليوم. ومقيسٌ: تحليلُ 09-10 فيه «اخذناها
                #   شراء من هون وطلعنا معه ل 29 **وبعدين بعنا**» — وهو
                #   سردُ تسلسلٍ منتهٍ.
                # ⇒ **ولا يُحذف الفعل** (فـ30/9 «اشترينا اليوم الصبح»
                #   موقفُ اليوم بعينه)، **بل يحمل تحفّظَه معه**.
                tag = " ⚠️قد يكون سردَ صفقةٍ سابقة" if phrase in DONE_DEEDS else ""
                if negated:
                    tag += " ⟨نفي ⇒ قُلب⟩"
                hits[side].append(f"{phrase} ⟨{context}⟩{tag}")

    if hits["bullish"] and hits["bearish"]:
        return "undefined", hits["bullish"] + hits["bearish"], dropped
    for bias in ("bullish", "bearish"):
        if hits[bias]:
            return bias, hits[bias], dropped
    return "undefined", [], dropped

if __name__ == "__main__":
    raise SystemExit(main())
