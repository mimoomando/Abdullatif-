"""
إعادة تشغيل السجلّ على مسار السعر الذي يحمله السجلّ نفسه.

⭐ **الفكرة كلّها في سطر:** كلُّ قرارٍ في `decisions.jsonl` يحمل
**شمعته**. فأسبوعٌ من القرارات على M15 هو أسبوعٌ من شموع M15 — أي
مسار السعر كاملًا. ولا حاجة إلى بيانات تاريخية من خارج الملفّ.

ومن ذلك يُسأل عن كل إعداد أُعلن: **الهدف الأول أم الوقف — أيّهما
أولًا؟** فتُستخرَج المعاملات من الواقع لا من التقدير.

⚠️ **وحدود القياس تُذكر مع نتيجته، لا بعدها:**

  • **دقّة الشمعة ربع ساعة** — ما جرى داخلها مجهول.
  • **التعارض داخل الشمعة الواحدة** (بلغت الوقفَ والهدفَ معًا)
    يُسمّى `ambiguous` ولا يُخمَّن. وفي الحصيلة يُحسب **خسارة**،
    فالرقم الخارج أسوأ من الواقع لا أفضل منه.
  • **الفجوات**: عطلةُ الأسبوع وتدويرُ اليوم وأيّ انقطاع تسجيل —
    تُعدّ وتُعلَن (`coverage`)، فلا تُقرأ نتيجةٌ فوق مسارٍ مثقوب.
  • **العدد**: عشرون إعدادًا لا تثبّت عتبة. تكشف عطبًا، وتنفي
    اقتراحًا، ولا تُبنى عليها قاعدة.

⛔ ولا يُنفَّذ شيء هنا ولا يُرسَل أمر: يُقرأ ملفٌّ ويُحسَب.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

Outcome = str        # "tp1" | "stop" | "ambiguous" | "open" | "unfilled"

# فجوةٌ أطول من هذه تُعدّ انقطاعًا يستحقّ الذكر
GAP_MINUTES = 120


@dataclass(frozen=True)
class Bar:
    time: datetime
    o: float
    h: float
    l: float
    c: float


@dataclass(frozen=True)
class Setup:
    """إعدادٌ متمايز — لا قرارٌ مفرد."""

    timeframe: str
    direction: str
    entry: float
    stop: float
    target: float
    first_seen: str
    announcements: int = 1          # كم مرّة أُعلن نفسه
    # ⭐ الأهدافُ كلُّها — يلزمها سلّمُ نقل الوقف (`trail.py`). و`target`
    #   يبقى الأوّل، فكلُّ ما بُني قبلها يقرؤه كما كان.
    targets: Tuple[float, ...] = ()

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def reward(self) -> float:
        return abs(self.target - self.entry)

    @property
    def rr(self) -> float:
        return self.reward / self.risk if self.risk else 0.0

    def key(self) -> Tuple:
        return (self.timeframe, self.direction,
                round(self.entry, 2), round(self.stop, 2))


@dataclass(frozen=True)
class Result:
    setup: Setup
    outcome: Outcome
    filled_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    mae: float = 0.0          # أقصى ارتدادٍ معاكس **قبل** الحسم
    mfe: float = 0.0          # أقصى صالحٍ بلغه
    # ⭐ الحصيلةُ الفعليّة بالدولار حين لا تُشتقّ من الاسم — وهي حالُ
    #   الوقف المنقول (`walk_managed`): يخرج عند سعرٍ بين الوقف والهدف.
    gain: Optional[float] = None

    @property
    def pnl(self) -> float:
        """
        بلوت 0.01 على الذهب: **دولارٌ لكل دولار حركة** (قرار المستخدم
        2026-08-27، وأكّده عقد الوسيط عند التشغيل).

        والملتبس خسارة — التشاؤم مقصود.
        """
        if self.gain is not None:
            return self.gain
        if self.outcome == "tp1":
            return self.setup.reward
        if self.outcome in ("stop", "ambiguous"):
            return -self.setup.risk
        return 0.0


@dataclass
class Coverage:
    """ما يجعل قراءة النتيجة ممكنة — أو تمنعها."""

    timeframe: str
    bars: int = 0
    first: Optional[datetime] = None
    last: Optional[datetime] = None
    gaps: List[Tuple[datetime, datetime, int]] = field(default_factory=list)

    def render(self) -> str:
        if not self.bars:
            return f"{self.timeframe}: لا شموع"
        out = [f"{self.timeframe}: {self.bars} شمعة · "
               f"{self.first:%m-%d %H:%M} → {self.last:%m-%d %H:%M}"]
        if self.gaps:
            out.append(f"  فجوات أطول من {GAP_MINUTES} دقيقة: {len(self.gaps)}")
            for a, b, m in self.gaps:
                out.append(f"    {a:%m-%d %H:%M} → {b:%m-%d %H:%M}  ({m} دقيقة)")
        return "\n".join(out)


# ─────────────────────────── القراءة ───────────────────────────


def read_journal(path: str) -> List[Dict]:
    """يقرأ JSONL متسامحًا مع السطر المبتور — كما كُتب."""
    rows: List[Dict] = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def rebuild(rows: Sequence[Dict], timeframe: str) -> List[Bar]:
    """
    يعيد بناء سلسلة الشموع من قرارات إطارٍ واحد.

    الشمعة الواحدة قد تتكرّر عبر قراراتٍ عدّة — تُطوى بوقتها، لأنها
    **الشمعة نفسها** لا شمعتان.
    """
    seen: Dict[datetime, Bar] = {}
    for r in rows:
        if r.get("poi_tf") != timeframe:
            continue
        c = r.get("candle") or {}
        if not all(k in c for k in "ohlc"):
            continue
        try:
            t = datetime.fromisoformat(r["candle_time"])
        except (KeyError, TypeError, ValueError):
            continue
        seen.setdefault(t, Bar(t, c["o"], c["h"], c["l"], c["c"]))
    return [seen[t] for t in sorted(seen)]


def coverage(bars: Sequence[Bar], timeframe: str,
             gap_minutes: int = GAP_MINUTES) -> Coverage:
    cov = Coverage(timeframe, len(bars))
    if not bars:
        return cov
    cov.first, cov.last = bars[0].time, bars[-1].time
    limit = timedelta(minutes=gap_minutes)
    for a, b in zip(bars, bars[1:]):
        d = b.time - a.time
        if d > limit:
            cov.gaps.append((a.time, b.time, int(d.total_seconds() // 60)))
    return cov


def setups_from(rows: Sequence[Dict]) -> List[Setup]:
    """
    يستخرج الإعدادات **المتمايزة** من القرارات المقبولة.

    ⭐ والتمايز هو بيت القصيد: في أسبوع 09-07…11 كانت 60 قرارًا
    مقبولًا **عشرين إعدادًا** لا أكثر — والأوردر بلوك الواحد يعطي
    الأرقام نفسها ما دام قائمًا.
    """
    order: List[Tuple] = []
    found: Dict[Tuple, Dict] = {}
    for r in rows:
        if r.get("disposition") != "taken":
            continue
        entry, stop, targets = r.get("entry"), r.get("stop"), r.get("targets") or []
        if entry is None or stop is None or not targets:
            continue
        k = (r.get("poi_tf"), r.get("direction"), round(entry, 2), round(stop, 2))
        if k not in found:
            found[k] = dict(r=r, n=0)
            order.append(k)
        found[k]["n"] += 1

    out = []
    for k in order:
        r, n = found[k]["r"], found[k]["n"]
        out.append(Setup(r["poi_tf"], r["direction"], r["entry"], r["stop"],
                         r["targets"][0], r["candle_time"], n,
                         tuple(r["targets"])))
    return out


# ─────────────────────────── المشي ───────────────────────────


def walk(bars: Sequence[Bar], setup: Setup,
         max_stop: Optional[float] = None) -> Result:
    """
    يمشي على الشموع من **بعد** إعلان الإعداد.

    ولماذا من بعده لا منه؟ لأن القرار يُتَّخذ على الشمعة **المغلقة**،
    فالأمر لا يوجد قبل إغلاقها. واحتسابُ الشمعة نفسها يقرأ حركةً
    سبقت الأمر — وهو أشهر أخطاء إعادة التشغيل.

    و`max_stop` يشدّ الوقف عند السقف بدل أن يطرح الإعداد — الفرق
    بينهما جوهريّ: الطرح يفقدك الصفقة، والشدّ يُبقيها بمخاطرةٍ أقلّ.
    """
    stop = setup.stop
    if max_stop is not None and setup.risk > max_stop:
        stop = (setup.entry - max_stop if setup.direction == "buy"
                else setup.entry + max_stop)
    risk = abs(setup.entry - stop)
    tight = Setup(setup.timeframe, setup.direction, setup.entry, stop,
                  setup.target, setup.first_seen, setup.announcements)

    try:
        start = datetime.fromisoformat(setup.first_seen)
    except (TypeError, ValueError):
        return Result(tight, "unfilled")

    filled: Optional[datetime] = None
    mae = mfe = 0.0

    for bar in bars:
        if bar.time <= start:
            continue
        if filled is None:
            if not (bar.l <= setup.entry <= bar.h):
                continue
            filled = bar.time

        if setup.direction == "buy":
            adverse, favour = setup.entry - bar.l, bar.h - setup.entry
        else:
            adverse, favour = bar.h - setup.entry, setup.entry - bar.l

        hit_stop = adverse >= risk
        hit_target = favour >= setup.reward

        if hit_stop and hit_target:
            return Result(tight, "ambiguous", filled, bar.time, mae, max(mfe, favour))
        if hit_stop:
            return Result(tight, "stop", filled, bar.time, mae, max(mfe, favour))
        if hit_target:
            return Result(tight, "tp1", filled, bar.time,
                          max(mae, adverse), max(mfe, favour))
        mae, mfe = max(mae, adverse), max(mfe, favour)

    return Result(tight, "open" if filled else "unfilled", filled, None, mae, mfe)


def walk_managed(bars: Sequence[Bar], setup: Setup,
                 plus: float = None) -> Result:
    """
    كـ`walk` — لكنّ الوقف **يتحرّك مع الأهداف** (انظر `trail.py`).

    ⭐ وهذا ما يجعل القاعدة **مقيسةً لا مُدّعاة**: الفرق بين
    `walk` و`walk_managed` على المسار نفسِه هو كلفةُ التأمين أو
    عائدُه، بالدولار.

    ⚠️ **وحدودُه حدودُ `walk`**: دقّةُ الشمعة، وبلوغُ الوقف والهدف في
    الشمعة الواحدة **يُحسب وقفًا** — تشاؤمًا مقصودًا. وهنا يزداد ثقلُه:
    صفقةٌ بلغت هدفها الثاني ووقفَها المنقول في شمعةٍ واحدة تُقرأ عند
    الوقف المنقول، أي عند الهدف الأوّل. فالرقم الخارج **أدنى** من
    الواقع لا أعلى.
    """
    from .trail import BREAK_EVEN_PLUS, never_looser, stop_after

    step = BREAK_EVEN_PLUS if plus is None else plus
    targets = setup.targets or (setup.target,)
    buy = setup.direction == "buy"

    try:
        start = datetime.fromisoformat(setup.first_seen)
    except (TypeError, ValueError):
        return Result(setup, "unfilled")

    filled: Optional[datetime] = None
    stop, reached = setup.stop, 0
    mae = mfe = 0.0

    def out(outcome: str, when, exit_price: float) -> Result:
        # ⭐ الحصيلة من **سعر الخروج** لا من اسم النتيجة — فالوقف
        #   المنقول يخرج رابحًا، واسمُه ليس «tp1».
        gain = (exit_price - setup.entry) if buy else (setup.entry - exit_price)
        return Result(setup, outcome, filled, when, mae, mfe, gain)

    for bar in bars:
        if bar.time <= start:
            continue
        if filled is None:
            if not (bar.l <= setup.entry <= bar.h):
                continue
            filled = bar.time

        adverse = (setup.entry - bar.l) if buy else (bar.h - setup.entry)
        favour = (bar.h - setup.entry) if buy else (setup.entry - bar.l)
        mae, mfe = max(mae, adverse), max(mfe, favour)

        # ⚠️⚠️ **والشمعةُ الواحدة قد تبلغ هدفين** — وحينها يتحرّك الوقف
        # مرّةً ثم **يُعاد فحصُه على الشمعة نفسِها**. فمسارُ السعر داخلها
        # مجهول، وشمعةٌ قمّتُها عند الهدف الثاني وقاعُها تحت الوقف
        # المنقول تُقرأ **عند الوقف المنقول**.
        #
        # ⛔ والتشاؤم مقصود كما في `walk`: الرقم الخارج أدنى من الواقع
        #    لا أعلى. وبلا هذه الحلقة الداخليّة كان الوقفُ المنقول
        #    يُتجاوَز صامتًا — وهو ربحٌ لم يقع.
        while True:
            hit_stop = (bar.l <= stop) if buy else (bar.h >= stop)
            if hit_stop:
                name = "stop" if reached == 0 else f"tp{reached}"
                return out(name, bar.time, stop)

            nxt = targets[reached] if reached < len(targets) else None
            if nxt is None:
                break
            if not ((bar.h >= nxt) if buy else (bar.l <= nxt)):
                break

            reached += 1
            if reached >= len(targets):
                return out(f"tp{reached}", bar.time, targets[-1])
            stop = never_looser(
                setup.direction, stop,
                stop_after(setup.entry, setup.stop, targets, reached,
                           setup.direction, step))

    if filled is None:
        return Result(setup, "unfilled", None, None, mae, mfe)
    return Result(setup, "open" if reached == 0 else f"tp{reached}·open",
                  filled, None, mae, mfe)


def replay(rows: Sequence[Dict], timeframe: str = "M15",
           max_stop: Optional[float] = None) -> List[Result]:
    """يعيد تشغيل كل إعدادٍ متمايز على مسار السعر المُعاد بناؤه."""
    bars = rebuild(rows, timeframe)
    return [walk(bars, s, max_stop) for s in setups_from(rows)]


@dataclass(frozen=True)
class Survival:
    """
    ما كان سيحدث للإعداد **لو لم يكن له وقفٌ إطلاقًا**.

    ⭐ وهذا ما يفصل بين احتمالين يبدوان واحدًا في السجلّ:

      • بلغ الهدفَ بعد ضربِ وقفه  ⇒ **الاتّجاه صحيح والوقف ضيّق**
      • لم يبلغه                  ⇒ **الإعداد نفسُه خطأ، والوقف بريء**

    و`needed` هو أقصى ارتدادٍ معاكس احتاجه **قبل** بلوغ الهدف — أي
    أصغرُ وقفٍ كان سينجو به.
    """

    filled: bool
    reached: bool
    needed: float             # كم دولارًا من الوقف لزمه ليبقى
    bars: int                 # كم شمعةً حتى الهدف


def survival(bars: Sequence[Bar], setup: Setup,
             horizon: Optional[int] = None) -> Survival:
    """
    يمشي على الشموع **متجاهلًا الوقف** — هل يبلغ الهدف، وبكم؟

    ⚠️ و`horizon` سقفُ الشموع بعد الدخول. بلا سقفٍ يصير السؤال «هل
    يبلغه يومًا ما» — وذلك سؤالٌ بلا معنًى تداوليّ: كلُّ سعرٍ يُبلَغ
    إن انتظرتَ كفاية. فالافتراضيّ **96 شمعة** (يومُ M15 كامل)، ويُذكر
    مع الرقم.
    """
    cap = 96 if horizon is None else horizon
    try:
        start = datetime.fromisoformat(setup.first_seen)
    except (TypeError, ValueError):
        return Survival(False, False, 0.0, 0)

    buy = setup.direction == "buy"
    filled: Optional[datetime] = None
    adverse = 0.0
    seen = 0

    for bar in bars:
        if bar.time <= start:
            continue
        if filled is None:
            if not (bar.l <= setup.entry <= bar.h):
                continue
            filled = bar.time
        seen += 1
        if seen > cap:
            break
        adverse = max(adverse, (setup.entry - bar.l) if buy
                      else (bar.h - setup.entry))
        hit = (bar.h >= setup.target) if buy else (bar.l <= setup.target)
        if hit:
            return Survival(True, True, adverse, seen)

    return Survival(filled is not None, False, adverse, seen)


def on_day(rows: Sequence[Dict], day: date) -> List[Dict]:
    """قرارات يومٍ واحد — بتاريخ شمعتها لا بوقت كتابتها."""
    out = []
    for r in rows:
        try:
            if datetime.fromisoformat(r["candle_time"]).date() == day:
                out.append(r)
        except (KeyError, TypeError, ValueError):
            continue
    return out


def realized_pnl(rows: Sequence[Dict], day: date) -> float:
    """
    حصيلةُ يومٍ واحد بالدولار — **المحسومةُ وحدها**.

    ⛔ **وما زال مفتوحًا لا يُحسب خسارةً ولا ربحًا.** فحدُّ الخسارة
    اليوميّ يقيس ما وقع، لا ما قد يقع — وإلّا أوقف اليومَ إعدادٌ لم
    يُحسَم بعدُ فينقلب رابحًا بعد ساعة.

    ⚠️ و`ambiguous` (بلغت الوقف والهدف في الشمعة نفسها) **تُحسب
    خسارة** كما في كلّ هذا الملفّ — فالرقم الخارج أسوأ من الواقع لا
    أفضل منه، وذلك ما يُراد من حدٍّ للخسارة.
    """
    today = on_day(rows, day)
    if not today:
        return 0.0
    total = 0.0
    for tf in {r.get("poi_tf") for r in today if r.get("poi_tf")}:
        bars = rebuild(rows, tf)             # المسار كلُّه، لا يومًا منه
        for s in setups_from([r for r in today if r.get("poi_tf") == tf]):
            res = walk(bars, s)
            if res.outcome in ("tp1", "stop", "ambiguous"):
                total += res.pnl
    return total


# ─────────────────────────── القراءة البشرية ───────────────────────────


def stop_demand(results: Sequence[Result]) -> List[Tuple[Setup, float]]:
    """
    ⭐ كم وقفًا احتاج الرابحون **فعلًا**؟

    وهذا هو ما يضبط سقف الوقف — لا وسيطُ المخاطرة المعلَنة، فتلك
    تقول كم أُعطي لا كم لزم. وفي أسبوع 09-07…11: **لا رابحَ واحدًا
    احتاج أكثر من 13.30$**.
    """
    return sorted(((r.setup, r.mae) for r in results if r.outcome == "tp1"),
                  key=lambda x: -x[1])


def net(results: Sequence[Result], weighted: bool = False) -> float:
    """`weighted` يضرب كل إعداد بعدد إعلاناته — كلفةُ التكرار."""
    return sum(r.pnl * (r.setup.announcements if weighted else 1) for r in results)


def tally(results: Sequence[Result]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in results:
        out[r.outcome] = out.get(r.outcome, 0) + 1
    return out


def render(results: Sequence[Result], cov: Optional[Coverage] = None) -> str:
    lines: List[str] = []
    if cov is not None:
        lines += [cov.render(), ""]

    lines.append(f"{'وقت':16}{'ط':5}{'اتج':6}{'دخول':>9}{'مخاطرة':>8}"
                 f"{'عائد':>7}{'R:R':>6}{'×':>3}  {'النتيجة':10}")
    lines.append("─" * 76)
    for r in results:
        s = r.setup
        lines.append(f"{s.first_seen[5:16]:16}{s.timeframe:5}{s.direction:6}"
                     f"{s.entry:9.2f}{s.risk:8.2f}{s.reward:7.2f}{s.rr:6.2f}"
                     f"{s.announcements:3}  {r.outcome:10}")

    t = tally(results)
    lines += ["", f"الحصيلة: {net(results):+.2f}$   "
                  f"({t.get('tp1', 0)} هدف · {t.get('stop', 0)} وقف · "
                  f"{t.get('ambiguous', 0)} ملتبس · "
                  f"{t.get('open', 0) + t.get('unfilled', 0)} معلَّق)"]

    w = net(results, weighted=True)
    if abs(w - net(results)) > 0.005:
        shots = sum(r.setup.announcements for r in results)
        lines.append(f"ولو فُتح كل إعلان ({shots} قرارًا): {w:+.2f}$"
                     f"   ⬅ كلفة التكرار")

    demand = stop_demand(results)
    if demand:
        lines += ["", f"أقصى وقفٍ احتاجه رابح: {demand[0][1]:.2f}$"
                      f"  (وأعلى وقفٍ أُعطي: "
                      f"{max(r.setup.risk for r in results):.2f}$)"]

    lines += ["", "⚠️ دقّة ربع ساعة · الملتبس يُحسب خسارة · "
                  f"{len(results)} عيّنة — تكشف عطبًا ولا تثبّت عتبة."]
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="إعادة تشغيل سجلّ القرارات")
    ap.add_argument("journal", help="مسار decisions.jsonl")
    ap.add_argument("--tf", default="M15", help="إطار إعادة البناء")
    ap.add_argument("--max-stop", type=float, default=None,
                    help="سقف مسافة الوقف — يُشَدّ الوقف إليه لا يُطرح الإعداد")
    a = ap.parse_args(argv)

    rows = read_journal(a.journal)
    if not rows:
        print("سجلّ فارغ أو غير موجود")
        return 1
    bars = rebuild(rows, a.tf)
    print(render(replay(rows, a.tf, a.max_stop), coverage(bars, a.tf)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
