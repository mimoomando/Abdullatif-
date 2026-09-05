"""
التعلّم من الأخطاء — بحدٍّ صريح.

╔══════════════════════════════════════════════════════════════════╗
║  ⛔ **البوت لا يتعلّم الاستراتيجية.**                             ║
║                                                                   ║
║  قاعدة المشروع من أوّل يوم: المستخدم يزوّد المعلومات، والكود        ║
║  ينفّذ. فلو غيّر البوت قواعد المدرّب من نتائجه، صار **يخترع**       ║
║  استراتيجية — وهو ما مُنع صراحةً.                                 ║
║                                                                   ║
║  ✅ **وما يتعلّمه: المعاملات `UNDEFINED` وحدها.**                  ║
║     تلك فراغات لم يملأها المدرّب أصلًا (كم سماحية؟ كم شمعة؟)،      ║
║     فضبطها من البيانات **ملءُ فراغ لا اختراع قاعدة**.             ║
║                                                                   ║
║  🔒 و`SOURCE` **مقفلة**. وإن ناقضتها البيانات، يُرفع تعارضٌ        ║
║     للمستخدم — ولا يُلغى المدرّب صامتًا.                          ║
║                                                                   ║
║  📋 و**يقترح ولا يطبّق**. القرار يبقى للمستخدم.                    ║
╚══════════════════════════════════════════════════════════════════╝

فالحلقة: صفقة تُغلق ⇒ تُشخَّص ⇒ يتكرّر الخطأ ⇒ يُنسَب إلى مقبض ⇒
يُقترَح تغييرٌ بأدلّته ⇒ **توافق أو ترفض**.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Literal, Optional, Sequence

from . import params as P

MistakeKind = Literal[
    "stop_too_tight",       # ضُرب الوقف ثم جاء الهدف
    "entry_wrong",          # لم تتحرك لصالحك قطّ
    "gave_back",            # بلغت الهدف مرورًا ولم تُقفل عليه
    "slept_and_harmed",     # نامت الصفقة فكلّفتها الفجوة
]

MISTAKE_AR: Dict[MistakeKind, str] = {
    "stop_too_tight": "وقف ضيّق — ضُرب ثم جاء الهدف",
    "entry_wrong": "دخول خاطئ — لم تتحرك لصالحك قطّ",
    "gave_back": "تُرك الربح — بلغت الهدف مرورًا ولم تُقفل",
    "slept_and_harmed": "نوم ضارّ — الفجوة كلّفت الصفقة",
}

# أي مقبض يعالج كل خطأ. القيمة اسم معامل في `params.py`.
KNOB_FOR: Dict[MistakeKind, str] = {
    "stop_too_tight": "STOP_BUFFER_DEGREES",
    "entry_wrong": "PATTERN_EQUALITY_TOLERANCE",
    "gave_back": "TARGET_ALTERNATIVES",
    "slept_and_harmed": "SESSION_FILTER",
}


@dataclass(frozen=True)
class Mistake:
    """خطأ واحد مشخَّص في صفقة واحدة، بدليله."""

    kind: MistakeKind
    evidence: str

    @property
    def label(self) -> str:
        return MISTAKE_AR[self.kind]

    def render(self) -> str:
        return f"{self.label} — {self.evidence}"


def diagnose(journal, after: Sequence = ()) -> List[Mistake]:
    """
    يشخّص صفقة مغلقة.

    `after` شموعُ ما **بعد** الإغلاق — وهي الدليل الوحيد على أن الوقف
    كان ضيّقًا: بلا رؤية ما جرى بعده، «ضُرب الوقف» و«الوقف ضيّق»
    لا يفترقان.

    ولا يُشخَّص شيء بلا دليلٍ مقيس. الخسارة وحدها **ليست خطأً**:
    منهجٌ سليم يخسر، وتسميةُ كل خسارة خطأً تُفسد التعلّم من أصله.
    """
    out: List[Mistake] = []
    if journal.outcome == "open":
        return out

    r = journal.rationale
    tp1 = r.targets[0] if r.targets else None

    if journal.outcome == "sl":
        if journal.mfe <= 0:
            out.append(Mistake(
                "entry_wrong",
                "لم تتحرك لصالحك ولو وحدة واحدة قبل الوقف",
            ))
        if tp1 is not None and after and _reached(after, tp1, r.direction):
            out.append(Mistake(
                "stop_too_tight",
                f"بعد الوقف بلغ السعر الهدف الأول {tp1:g} "
                f"({len(after)} شمعة) — الاتجاه كان صحيحًا",
            ))

    if tp1 is not None and journal.outcome != "tp":
        reach = abs(tp1 - journal.entry)
        if reach > 0 and journal.mfe >= reach:
            out.append(Mistake(
                "gave_back",
                f"أقصى ربح عابر {journal.mfe:.2f} بلغ الهدف {reach:.2f} "
                f"ولم تُقفل الصفقة عليه",
            ))

    if journal.slept and journal.gap_effect < 0:
        out.append(Mistake(
            "slept_and_harmed",
            f"الفجوات كلّفت {abs(journal.gap_effect):.2f} وحدة",
        ))

    return out


def _reached(candles: Sequence, level: float, direction: str) -> bool:
    if direction == "buy":
        return any(c.high >= level for c in candles)
    return any(c.low <= level for c in candles)


# ─────────────────────────── الدفتر ───────────────────────────


@dataclass
class RiskLedger:
    """
    ما فعلته الصفقات بالحساب — **يسجّل ولا يوقِف**.

    قرار المستخدم (2026-09-05): لا حدّ يوميّ ولا حدّ خسائر متتالية.
    فالدفتر يقيس ما كان سيوفّره كلُّ حدّ محتمل، ليُختار الرقم لاحقًا
    **من البيانات لا من التقدير**.

    `value_per_dollar` = 1.00 بلوت 0.01 (قرار المستخدم) ⇒ الوحدة
    السعرية دولارٌ واحد.
    """

    journals: List = field(default_factory=list)
    value_per_dollar: float = 1.00

    # ── الأساسيات ──
    def closed(self) -> List:
        return [j for j in self.journals if j.outcome != "open"]

    def is_loss(self, j) -> bool:
        res = j.result
        return res is not None and res < 0

    def dollars(self, j) -> float:
        res = j.result
        return 0.0 if res is None else res * self.value_per_dollar

    def net(self) -> float:
        return sum(self.dollars(j) for j in self.closed())

    # ── السلاسل ──
    def streaks(self) -> List[int]:
        """أطوال سلاسل الخسائر المتتالية بالترتيب."""
        out: List[int] = []
        run = 0
        for j in self.closed():
            if self.is_loss(j):
                run += 1
            elif run:
                out.append(run)
                run = 0
        if run:
            out.append(run)
        return out

    @property
    def longest_streak(self) -> int:
        s = self.streaks()
        return max(s) if s else 0

    @property
    def current_streak(self) -> int:
        run = 0
        for j in reversed(self.closed()):
            if not self.is_loss(j):
                break
            run += 1
        return run

    # ── الأيام ──
    def by_day(self) -> Dict[date, float]:
        out: Dict[date, float] = defaultdict(float)
        for j in self.closed():
            out[j.closed_at.date()] += self.dollars(j)
        return dict(out)

    def worst_day(self) -> Optional[tuple]:
        days = self.by_day()
        if not days:
            return None
        d = min(days, key=lambda k: days[k])
        return (d, days[d])

    # ── ماذا كان سيوفّر حدٌّ لو وُضع ──
    def saved_by_streak_limit(self, limit: int) -> float:
        """
        كم دولارًا كان سيوفّر «توقّف بعد N خسائر متتالية»؟

        يُحسب **يومًا بيوم** — لأن مفتاح التوقّف يُعاد ضبطه كل صباح.
        موجب ⇒ الحدّ كان نافعًا · سالب ⇒ كان سيحرمك ربحًا.
        """
        if limit < 1:
            raise ValueError("الحدّ لا يكون أقل من واحد")
        skipped = 0.0
        for _day, trades in self._grouped().items():
            run = 0
            stopped = False
            for j in trades:
                if stopped:
                    skipped += self.dollars(j)
                    continue
                run = run + 1 if self.is_loss(j) else 0
                if run >= limit:
                    stopped = True
        return -skipped

    def saved_by_daily_cap(self, cap: float) -> float:
        """كم كان سيوفّر «توقّف عند خسارة N دولار في اليوم»؟"""
        if cap <= 0:
            raise ValueError("السقف يجب أن يكون موجبًا")
        skipped = 0.0
        for _day, trades in self._grouped().items():
            running = 0.0
            stopped = False
            for j in trades:
                if stopped:
                    skipped += self.dollars(j)
                    continue
                running += self.dollars(j)
                if running <= -cap:
                    stopped = True
        return -skipped

    def _grouped(self) -> Dict[date, List]:
        out: Dict[date, List] = defaultdict(list)
        for j in sorted(self.closed(), key=lambda x: x.closed_at):
            out[j.closed_at.date()].append(j)
        return dict(out)

    def render(self) -> str:
        c = self.closed()
        lines = ["─" * 58, "دفتر المخاطرة — يسجّل ولا يوقِف", "─" * 58, ""]
        if not c:
            lines.append("  لا صفقات مغلقة بعد.")
            return "\n".join(lines)

        losses = sum(1 for j in c if self.is_loss(j))
        lines += [
            f"  صفقات مغلقة    : {len(c)}   (خاسرة {losses})",
            f"  الصافي         : {self.net():+.2f}$",
            f"  أطول سلسلة خسائر: {self.longest_streak}",
            f"  السلسلة الجارية : {self.current_streak}",
        ]
        worst = self.worst_day()
        if worst:
            lines.append(f"  أسوأ يوم       : {worst[0]}  {worst[1]:+.2f}$")

        lines += ["", "  ماذا كان سيوفّر حدٌّ لو وُضع:"]
        for n in (2, 3, 4):
            lines.append(f"    توقّف بعد {n} خسائر متتالية : {self.saved_by_streak_limit(n):+.2f}$")
        for cap in (10.0, 20.0, 40.0):
            lines.append(f"    توقّف عند خسارة {cap:g}$      : {self.saved_by_daily_cap(cap):+.2f}$")
        lines.append("")
        lines.append("  موجب ⇒ الحدّ كان نافعًا · سالب ⇒ كان سيحرمك ربحًا.")
        return "\n".join(lines)


# ─────────────────────────── الدروس ───────────────────────────


@dataclass(frozen=True)
class Lesson:
    """
    خطأ تكرّر بما يكفي ليُنسَب إلى مقبض.

    `locked` ⇒ المقبض من `SOURCE`: قاعدةُ المدرّب. لا يُقترَح تغييرها
    بل يُرفع تعارضٌ للمستخدم.
    """

    kind: MistakeKind
    count: int
    total: int
    knob: str
    origin: str

    @property
    def locked(self) -> bool:
        return self.origin == "SOURCE"

    @property
    def share(self) -> float:
        return self.count / self.total if self.total else 0.0

    def render(self) -> str:
        head = (
            f"{MISTAKE_AR[self.kind]} — {self.count} من {self.total} "
            f"({self.share * 100:.0f}%)"
        )
        if self.locked:
            return (
                f"🔒 {head}\n"
                f"     المقبض `{self.knob}` من **SOURCE** — قاعدة المدرّب.\n"
                f"     لا تُغيَّر من البيانات. **تعارضٌ يُرفع إليك.**"
            )
        return (
            f"📋 {head}\n"
            f"     يقترح مراجعة `{self.knob}` ({self.origin}).\n"
            f"     **اقتراح لا تطبيق** — القرار لك."
        )


def _origin_of(knob: str) -> str:
    p = P.registry().get(knob)
    return p.origin if p else "UNKNOWN"


def lessons(
    diagnoses: Sequence[Sequence[Mistake]],
    min_count: int = 3,
) -> List[Lesson]:
    """
    يجمع التشخيصات ويرفع ما تكرّر.

    `min_count` عتبة التكرار — 🔴 **غير معرَّفة من المصدر**: ثلاثٌ
    أقلّ ما يميّز نمطًا من مصادفة، والرقم قابل للضبط. ودونها يصير
    كل خسارة درسًا، وذلك أسوأ من ألّا يتعلّم.
    """
    if min_count < 2:
        raise ValueError("درسٌ من حالة واحدة مصادفة لا نمط")

    total = len(diagnoses)
    # التكرار يُحسب **بالنوع** لا بالدليل: خطأ واحد قد يُشخَّص
    # بأدلّة عدة في الصفقة الواحدة، فلا يُعدّ مرّتين.
    counts = Counter(k for ms in diagnoses for k in {m.kind for m in ms})

    out = [
        Lesson(kind=k, count=n, total=total,
               knob=KNOB_FOR[k], origin=_origin_of(KNOB_FOR[k]))
        for k, n in counts.items() if n >= min_count
    ]
    out.sort(key=lambda l: l.count, reverse=True)
    return out


def render_lessons(items: Sequence[Lesson]) -> str:
    lines = ["═" * 58, "ما يقترحه البوت — ولا يطبّقه", "═" * 58, ""]
    if not items:
        lines.append("  لا نمط متكرّرًا بعد. لا يُقترَح شيء.")
        lines.append("  (خسارةٌ متفرّقة ليست خطأً — المنهج السليم يخسر.)")
        return "\n".join(lines)

    for l in items:
        lines.append("  " + l.render().replace("\n", "\n  "))
        lines.append("")
    lines.append("⛔ لا يُغيَّر أي معامل تلقائيًّا — ولا معامل SOURCE أبدًا.")
    return "\n".join(lines)
