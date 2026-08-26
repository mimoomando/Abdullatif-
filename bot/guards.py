"""
حاجز التنفيذ — يمنع أي أمر تداول حقيقي.

المصدر الأصلي ينص:
    «No trading code is authorized until the user explicitly says نفذ»
    «Do not edit the trading bot until the user explicitly says نفذ»

والمستخدم أذن صراحةً بـ«محرك تحليل» فقط في 2026-08-26:
    «نعم انا معك هذا محرك تحليل … عند الانتهاء اريدك ان تجعله يحلل وثم ينفذ»

فالتنفيذ مؤجَّل حتى اكتمال الدروس وإذن صريح لاحق. هذه الوحدة تجعل ذلك
قيدًا في الكود لا وعدًا في التوثيق.
"""

EXECUTION_ENABLED = False

_AUTHORIZATION_NOTE = (
    "التنفيذ غير مأذون. المأذون حاليًا: التحليل والاقتراح فقط.\n"
    "لتفعيل التنفيذ يلزم: (1) اكتمال مراجعة الدروس، "
    "(2) إغلاق معاملات UNDEFINED في params.py، "
    "(3) إذن صريح جديد من المستخدم."
)


class ExecutionBlocked(RuntimeError):
    """يُرفع عند أي محاولة لإرسال أمر تداول."""


def assert_analysis_only(action: str = "أمر تداول") -> None:
    """يُستدعى في مدخل أي دالة قد تلمس التنفيذ."""
    if not EXECUTION_ENABLED:
        raise ExecutionBlocked(f"مرفوض: {action}\n{_AUTHORIZATION_NOTE}")


def send_order(*_args, **_kwargs):
    """موجودة عمدًا لتفشل بصوت عالٍ إن استدعاها أي كود."""
    assert_analysis_only("send_order()")


def modify_position(*_args, **_kwargs):
    assert_analysis_only("modify_position()")


def close_position(*_args, **_kwargs):
    assert_analysis_only("close_position()")
