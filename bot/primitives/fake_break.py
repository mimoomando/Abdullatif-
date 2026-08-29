"""
الكسر الوهمي مقابل الحقيقي — وايكوف/د3 «منطقة السبرينغ والكسر الوهمي».

هذا الدرس سدّ فجوة كانت موثّقة عندي منذ وايكوف ١ («تمييز الكسر الوهمي
من الحقيقي — موعود ولم يُسلَّم»).

╔══════════════════════════════════════════════════════════════════╗
║  ١. لا كسر بلا إغلاق خارج المنطقة                                 ║
║     «هل أغلقت شموع أعلى المنطقة؟ لا» ⇒ لم يحدث كسر أصلًا           ║
║                                                                   ║
║  ٢. وقع الكسر — والفاصل هو **إعادة الاختبار**                      ║
║     «لو كان كسر حقيقي كان تغيّر الهيكل: لما طلع عاد اختبار،        ║
║      نزل عاد اختبار. أما لأنه كسر وهمي — تصعّدت وأغلقت فوق»        ║
╚══════════════════════════════════════════════════════════════════╝

    حقيقي : عاد للمستوى · **لم يُغلق داخله** · واصل باتجاه الكسر
    وهمي  : عاد للمستوى · **أغلق عائدًا** إلى الجهة الأصلية

الفاصل **إغلاق إعادة الاختبار** — لا حجم الكسر ولا عدد شموعه.

🔄 **تحديث — وايكوف/د4:** كان مسجَّلًا هنا أن وايكوف «لا يعطي صفقة»،
وهو ما قاله أربع مرات. ثم أعطى في الدرس الرابع **دخولًا ووقفًا وهدفًا**
كاملة. والتوفيق بلفظه هو لا باجتهادي:

    «التحليل وايكوف **نظرية وليست استراتيجية**، ولكن بتكشف السلوك»
    «مجرد ما **تدمج قراءة الفوليوم مع المناطق المفتاحية**،
     انت بتاخذ **دخول هاي كواليتي**»

⇒ وايكوف **وحده** لا يعطي صفقة. ووايكوف **+ الفوليوم + المنطقة
المفتاحية** يعطيها. القاعدة لم تُنقَض بل صار لها استثناء مسمّى بشرطه،
وهو `plan_from_fake_break()` أدناه.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional, Sequence, Set

from ..data import Series

Side = Literal["up", "down"]
BreakState = Literal["pending", "real", "fake"]


@dataclass(frozen=True)
class BreakAttempt:
    """محاولة كسر لمستوى، وما آلت إليه."""

    index: int                    # الشمعة التي أغلقت خارج المنطقة
    time: datetime
    level: float
    direction: Side
    close: float                  # إغلاق شمعة الكسر
    state: BreakState
    resolved_at: Optional[int] = None
    detail: str = ""

    @property
    def is_spring(self) -> bool:
        """
        السبرينغ — تسميته للكسر الوهمي **هبوطًا** داخل التجميع.

        لم يُسمِّ نظيره الصاعد في هذا الدرس، فلا يُسمّى هنا.
        """
        return self.state == "fake" and self.direction == "down"

    def render(self) -> str:
        ar = {
            "real": "كسر حقيقي",
            "fake": "كسر وهمي",
            "pending": "كسر بلا حسم",
        }[self.state]
        tag = " (سبرينغ)" if self.is_spring else ""
        way = "فوق" if self.direction == "up" else "تحت"
        return f"{self.time:%H:%M}  {ar}{tag} {way} {self.level:g} — {self.detail}"


def find_break_attempts(
    series: Series,
    level: float,
    direction: Side,
    retest_window: int = 12,
    level_tolerance: float = 0.0,
    start: int = 0,
) -> List[BreakAttempt]:
    """
    يرصد محاولات كسر `level` ويصنّف كلًّا منها.

    `retest_window` : كم شمعة تُمهَل لحسم إعادة الاختبار.
        🔴 **FB1 — غير معرَّف في الدرس.** لم يذكر عددًا إطلاقًا.
        القيمة هنا مقبض مكشوف يُضبط بالاختبار التاريخي، لا رقم منه.

    `level_tolerance` : سماحية «أغلقت **عند** المستوى».
        🔴 **FB2 — غير معرَّف.** صفر = المستوى بحرفه.

    تُرجَع المحاولات بالترتيب. لا يُبدأ رصد محاولة جديدة قبل حسم سابقتها،
    لأن الكسر وإعادة اختباره حدث واحد لا حدثان.

    **ويتوقّف الرصد عند أول كسر حقيقي**: «لو كان كسر حقيقي كان تغيّر
    الهيكل» — فالمستوى انتهى دوره، وما بعده إغلاقات في السوق الجديد لا
    محاولات كسر لمستوى قائم. أما الوهمي فالمستوى صمد ويُهاجَم ثانيةً.
    """
    if retest_window < 1:
        raise ValueError("نافذة إعادة الاختبار يجب أن تكون شمعة أو أكثر")
    if level_tolerance < 0:
        raise ValueError("السماحية لا تكون سالبة")
    if direction not in ("up", "down"):
        raise ValueError("الاتجاه: up أو down")

    out: List[BreakAttempt] = []
    i = max(0, start)
    n = len(series)

    while i < n:
        c = series[i]
        if not _closed_beyond(c.close, level, direction, level_tolerance):
            i += 1
            continue

        attempt = _resolve(series, i, level, direction, retest_window, level_tolerance)
        out.append(attempt)
        if attempt.state == "real":
            break
        # نكمل بعد نقطة الحسم — أو بعد النافذة إن لم تُحسم
        i = (attempt.resolved_at or min(i + retest_window, n - 1)) + 1

    return out


def _closed_beyond(close: float, level: float, direction: Side, tol: float) -> bool:
    """الإغلاق خارج المستوى — «الكسر بالجسم لا بالذيل» (د10)."""
    return close > level + tol if direction == "up" else close < level - tol


def _closed_back(close: float, level: float, direction: Side, tol: float) -> bool:
    """الإغلاق عائدًا إلى الجهة الأصلية — هذا ما يجعل الكسر وهميًا."""
    return close < level - tol if direction == "up" else close > level + tol


def _touched(candle, level: float, direction: Side, tol: float) -> bool:
    """
    هل عاد السعر ولامس المستوى؟

    🔴 **FB3** — لم يحدّد هل يلزم اللمس بالذيل أم يكفي القرب. اعتُمد اللمس
    بالمدى، وهو أدنى ما يصحّ تسميته «إعادة اختبار».
    """
    return candle.low <= level + tol if direction == "up" else candle.high >= level - tol


def _resolve(
    series: Series,
    break_index: int,
    level: float,
    direction: Side,
    window: int,
    tol: float,
) -> BreakAttempt:
    """
    يمشي على شموع النافذة كاملةً ثم يحسم: وهمي · حقيقي · بلا حسم.

    ⭐ **النافذة تُمسح كاملةً قبل الحكم**، ولا يُحسم عند أول ارتداد يبدو
    مؤكِّدًا. لأن **الإغلاق العائد ينقض الكسر مهما بدا قويًا قبله**:

        «أما لأنه كسر وهمي — هي تصعّدت وأغلقت فوق»

    فالحسم ليس أول إشارة بل ما استقرّ عليه الإغلاق. ولو حُكم عند أول
    لمسة صامدة لصُنِّف كسرٌ وهميّ «حقيقيًا» لمجرد أن ارتداده تأخّر شمعة.
    """
    brk = series[break_index]
    end = min(break_index + 1 + window, len(series))
    retested = False
    held_at: Optional[int] = None

    for j in range(break_index + 1, end):
        c = series[j]

        if _closed_back(c.close, level, direction, tol):
            return BreakAttempt(
                break_index, brk.time, level, direction, brk.close,
                "fake", j,
                f"أُعيد الاختبار فأغلق عائدًا عند {c.close:g} — «تصعّدت وأغلقت فوق»",
            )

        if _touched(c, level, direction, tol):
            retested = True
            if held_at is None and _closed_beyond(c.close, level, direction, tol):
                held_at = j

    if held_at is not None:
        return BreakAttempt(
            break_index, brk.time, level, direction, brk.close, "real", held_at,
            f"عاد للمستوى وأغلق خارجه عند {series[held_at].close:g} "
            "— «نزل، أغلق، تست، أغلق»",
        )

    detail = (
        "عاد للمستوى ولم يُحسم إغلاقه ضمن النافذة"
        if retested
        else "لم يُعِد اختبار المستوى ضمن النافذة"
    )
    return BreakAttempt(
        break_index, brk.time, level, direction, brk.close, "pending", None, detail,
    )


@dataclass(frozen=True)
class FakeBreakPlan:
    """
    الصفقة من الكسر الوهمي — وايكوف/د4.

    منصوصة ثلاث مرات بألفاظ متقاربة:

        «مجرد الخروج والإغلاق من الكسر الوهمي كان في صفقة سيل،
         **الستوب عند أعلى قمة بالكسر الوهمي**،
         والهدف عند القيعان — **هي أول قاع تستهدفه**»
    """

    direction: Literal["buy", "sell"]
    entry: float                  # إغلاق الشمعة العائدة
    entry_index: int
    stop: float                   # أقصى طرف بلغه الكسر الوهمي
    targets: List[float]
    level: float
    why: str

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)

    def rr_of(self, target: float) -> Optional[float]:
        r = self.risk
        return None if r == 0 else abs(target - self.entry) / r

    def render(self) -> str:
        side = "بيع" if self.direction == "sell" else "شراء"
        tg = " · ".join(f"{t:g}" for t in self.targets) or "—"
        return (
            f"{side} من {self.entry:g} · وقف {self.stop:g} · أهداف {tg}\n"
            f"   {self.why}"
        )


def plan_from_fake_break(
    series: Series,
    attempt: BreakAttempt,
    prior_extremes: Sequence[float],
    max_targets: int = 3,
    key_zones: Sequence[float] = (),
    key_zone_buffer: float = 0.0,
) -> Optional[FakeBreakPlan]:
    """
    يبني الصفقة من كسر وهمي محسوم — الدخول والوقف والهدف كما نصّها.

    الزناد   : **إغلاق** الشمعة عائدةً — «مجرد الخروج والإغلاق»
    الاتجاه  : عكس الكسر — كسر وهمي لأعلى ⇒ بيع
    الوقف    : **أقصى طرف بلغه الكسر الوهمي** لا حدّ المنطقة
    الأهداف  : `prior_extremes` — «أول قاع تستهدفه» ثم الأبعد

    `key_zones` : مناطق مفتاحية تُقصَّر عندها الأهداف — قاعدة منصوصة:

        «ما بحط هدفي بعد منها، ممكن يرتد — **أنا بحطه قبل منها**»

    يُرجَع None إن لم يكن الكسر وهميًا أو لا هدف صالحًا: لا صفقة بلا هدف.
    """
    if attempt.state != "fake" or attempt.resolved_at is None:
        return None
    if max_targets < 1:
        raise ValueError("عدد الأهداف واحد أو أكثر")

    entry_candle = series[attempt.resolved_at]
    entry = entry_candle.close

    # الاتجاه عكس الكسر
    direction = "sell" if attempt.direction == "up" else "buy"

    # الوقف: أقصى ما بلغه السعر أثناء الكسر الوهمي — لا المستوى
    span = list(series)[attempt.index:attempt.resolved_at + 1]
    stop = max(c.high for c in span) if direction == "sell" else min(c.low for c in span)

    pool = sorted(
        (p for p in prior_extremes if (p < entry if direction == "sell" else p > entry)),
        reverse=(direction == "sell"),
    )
    pool = _shorten_at_key_zones(pool, entry, direction, key_zones, key_zone_buffer)
    if not pool:
        return None

    return FakeBreakPlan(
        direction=direction,
        entry=entry,
        entry_index=attempt.resolved_at,
        stop=stop,
        targets=pool[:max_targets],
        level=attempt.level,
        why=(
            f"كسر وهمي {'فوق' if attempt.direction == 'up' else 'تحت'} "
            f"{attempt.level:g} ثم إغلاق عائد عند {entry:g} — "
            "«مجرد الخروج والإغلاق من الكسر الوهمي كان في صفقة»"
        ),
    )


def _shorten_at_key_zones(
    targets: Sequence[float],
    entry: float,
    direction: str,
    key_zones: Sequence[float],
    buffer: float,
) -> List[float]:
    """
    «ما بحط هدفي بعد منها — أنا بحطه **قبل** منها» (وايكوف/د4 ≈16:13).

    كل هدف يقع خلف منطقة مفتاحية يُستبدَل بموضع **قبلها** بمقدار الهامش.
    🔴 **V4 غير معرَّف**: لم يحدّد كم «قبلها» — الهامش صفر افتراضًا.
    """
    if not key_zones:
        return list(targets)
    if buffer < 0:
        raise ValueError("الهامش لا يكون سالبًا")

    out: List[float] = []
    for t in targets:
        blocking = [
            z for z in key_zones
            if (t <= z < entry if direction == "sell" else entry < z <= t)
        ]
        if blocking:
            z = max(blocking) if direction == "sell" else min(blocking)
            capped = z + buffer if direction == "sell" else z - buffer
            if (capped < entry) if direction == "sell" else (capped > entry):
                out.append(capped)
        else:
            out.append(t)

    # إزالة التكرار مع حفظ الترتيب
    seen: Set[float] = set()
    return [t for t in out if not (t in seen or seen.add(t))]


def crossing_rule(passed: bool) -> str:
    """
    قاعدة العبور — منصوصة (07:38):

        «منطقة بده يتجاوزها السعر: **ما تجاوزها السعر — بده يرتد**.
         **تجاوز السعر — بده يرتكز عليه ويكفّي**»

    وصف سلوك لا أمر تنفيذ: المنطقة المفتاحية تعمل مرجعًا في الاتجاهين،
    وما قبلها تاريخيًا يعمل مثلها — «لهون ولوراء».
    """
    return (
        "تجاوز المستوى ⇒ يصير ارتكازًا والحركة تكمل"
        if passed
        else "فشل التجاوز ⇒ ارتداد"
    )
