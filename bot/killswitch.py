"""
مفتاح الإيقاف — **ملفٌّ واحد يوقف البوت، وحذفُه يعيده.**

╔══════════════════════════════════════════════════════════════════╗
║  ضع ملفًّا اسمه  STOP  في مجلّد المشروع  ⇒  يتوقّف عن التنبيه      ║
║  احذفه                                    ⇒  يعود من تلقائه      ║
╚══════════════════════════════════════════════════════════════════╝

**ولماذا ملفٌّ لا أمرٌ ولا زرّ؟** لأنّ يومًا يسوء — خبرٌ مفاجئ، أو
سبريدٌ جنونيّ، أو شكٌّ في الإعدادات — تحتاج فيه إيقافًا **في ثانية**،
لا بحثًا عن نافذة cmd بين عشرين نافذة، ولا تذكّرًا لأمر. وإنشاء ملفٍّ
على سطح المكتب يفعله أيُّ أحدٍ تحت الضغط.

⭐⭐ **ويقبل `STOP.txt` كما يقبل `STOP`** — وهذا ليس تسامحًا زائدًا:
ويندوز يخفي الامتدادات افتراضًا، والمفكّرةُ تُلحق `.txt` صامتةً. فمن
أنشأ «STOP» بالمفكّرة يظنّه `STOP` وهو `STOP.txt`. ومفتاحُ إيقافٍ
يفشل صامتًا لأنّ النظام أضاف ثلاثة أحرف **أسوأ من عدمه**.

⚠️ **وما الذي يوقفه؟ التنبيه لا التسجيل.** فالبوت يبقى يقرأ ويحكم
ويكتب، ولا يُعلن إعدادًا. وذلك مقصود: السجلّ يبقى متّصلًا فنعرف ما
**كان** سيحدث في الساعات التي أوقفتَه فيها — وهو أنفعُ ما يُقاس.
ومن أراد إيقافًا تامًّا فـ`Ctrl+C` موجود.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

# ⚠️ الترتيب مقصود: العاري أوّلًا، ثم ما يلحقه ويندوز.
NAMES: Tuple[str, ...] = ("STOP", "STOP.txt", "stop", "stop.txt")


def path(root: str = ".") -> Optional[str]:
    """مسارُ ملفّ الإيقاف إن وُجد — أو `None`."""
    for name in NAMES:
        p = os.path.join(root, name)
        if os.path.exists(p):
            return p
    return None


def active(root: str = ".") -> bool:
    return path(root) is not None


def reason(root: str = ".") -> str:
    """
    ما كتبه المستخدم داخل الملفّ — يُعرض في السجلّ.

    ⭐ فمن أوقف البوت الخميس وعاد الاثنين لا يذكر لماذا. وسطرٌ داخل
    الملفّ يذكّره.
    """
    p = path(root)
    if p is None:
        return ""
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            return fh.read(200).strip()
    except OSError:
        return ""


def banner(root: str = ".") -> str:
    """
    سطرُ الحالة — **لاتينيٌّ أوّلًا**، فنافذة cmd تقلب العربيّة.

    (رآها المستخدم مقلوبةً أوّلَ تشغيل — انظر `Heartbeat`.)
    """
    p = path(root) or ""
    why = reason(root)
    out = [f"[STOP] KILL SWITCH IS ON - no setups announced. File: {p}"]
    if why:
        out.append(f"       note: {why}")
    out.append(f"       delete the file to resume.")
    out.append(f"⛔ مفتاح الإيقاف مفعَّل — لا إعداد يُعلَن. احذف {p} ليعود.")
    return "\n".join(out)


CLEARED = ("[OK] KILL SWITCH REMOVED - back to normal.\n"
           "✅ رُفع مفتاح الإيقاف — عاد البوت.")
