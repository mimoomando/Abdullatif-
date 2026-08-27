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

⚠️ **لا يعطي صفقة.** تأكيد رابع من المدرّب في هذا الدرس نفسه:
«أنا ما بدي أعطيك إياها كصفقة، أنا بدي أعطيك إياها كسلوك سعر».
الموضع من هنا، والدخول من النموذج الانعكاسي — كما في سلسلة القرار.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional

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
