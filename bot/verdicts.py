"""
حكم المستخدم على الشكل — الطبقة التي لا يستطيع الكود توفيرها.

سبب وجودها — اعتراض المدرّب (2026-08-27):

    «إذا **الحساب صح بس الشكل غير مطابق** — بفوت»

هذا النوع من الخطأ **لا يراه الكود إطلاقًا**: الشروط الرقمية تحققت كلها،
فالبوت لا يملك ما ينبّهه. العين وحدها ترى أن الشكل لم يكن نموذجًا صحيحًا.

فالمستخدم يراجع صفقات اليوم ويضع حكمه، فيتحول الاعتراض من جدل إلى رقم:

    إيجابية كاذبة  =  البوت تصرّف  والشكل خاطئ   ⇒ شروطه فضفاضة
    سلبية كاذبة    =  البوت رفض    والشكل صحيح   ⇒ شروطه ضيقة

صيغة الردّ على تيليجرام مقصودة البساطة — سطر لكل إعداد:

    ١ نعم
    ٢ لا
    ٣ لا الشكل ما كان مطابق

⚠️ **الحكم لا يغيّر سلوك البوت تلقائيًا.** يُجمع ويُعرض، والقرار مشترك.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Set

YES = {"نعم", "ايوا", "أيوا", "اي", "صح", "صحيح", "مطابق", "y", "yes", "ok", "1", "١"}
NO = {"لا", "لأ", "غلط", "خطأ", "خطا", "مش", "n", "no", "0", "٠"}

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


@dataclass(frozen=True)
class Verdict:
    """حكم المستخدم على إعداد واحد."""

    setup_id: int
    shape_ok: bool
    note: str = ""
    at: Optional[datetime] = None

    def render(self) -> str:
        mark = "✅ الشكل مطابق" if self.shape_ok else "❌ الشكل غير مطابق"
        tail = f" — {self.note}" if self.note else ""
        return f"{self.setup_id}. {mark}{tail}"


def parse_verdicts(text: str, at: Optional[datetime] = None) -> List[Verdict]:
    """
    يقرأ ردّ المستخدم: رقم ثم نعم/لا ثم ملاحظة اختيارية.

    متسامح مع الأرقام العربية والمسافات الزائدة. السطر غير المفهوم
    يُتجاهَل بصمت — لأن رفض ردّ كامل بسبب سطر واحد أسوأ من تجاهله.
    """
    out: List[Verdict] = []
    seen: Set[int] = set()

    for raw in text.splitlines():
        line = raw.translate(_AR_DIGITS).strip()
        m = re.match(r"^(\d+)\s*[.)\-:]?\s+(.*)$", line)
        if not m:
            continue

        sid = int(m.group(1))
        rest = m.group(2).strip()
        if not rest or sid in seen:
            continue

        first = rest.split()[0].strip(".,،")
        if first in YES:
            ok = True
        elif first in NO:
            ok = False
        else:
            continue

        note = rest[len(first):].strip(" .,،")
        out.append(Verdict(sid, ok, note, at))
        seen.add(sid)

    return out


# ─────────────────────────── القياس ───────────────────────────


@dataclass(frozen=True)
class JudgedSetup:
    """إعداد مع حكم المستخدم عليه — الوحدة التي يُبنى عليها القياس."""

    setup_id: int
    disposition: str          # taken · blocked · rejected
    timeframe: str
    shape_ok: Optional[bool]
    near_miss: bool = False
    note: str = ""

    @property
    def acted(self) -> bool:
        """البوت تصرّف — نفّذ أو نبّه."""
        return self.disposition in ("taken", "blocked")

    @property
    def false_positive(self) -> bool:
        """تصرّف والشكل خاطئ — «الحساب صح بس الشكل غير مطابق»."""
        return self.acted and self.shape_ok is False

    @property
    def false_negative(self) -> bool:
        """رفض والشكل صحيح — «الشكل صح بس الحساب غلط»."""
        return self.disposition == "rejected" and self.shape_ok is True


@dataclass
class Accuracy:
    """حصيلة تراكمية عبر الأيام."""

    judged: List[JudgedSetup] = field(default_factory=list)

    def add(self, items: Sequence[JudgedSetup]) -> None:
        self.judged.extend(items)

    @property
    def rated(self) -> List[JudgedSetup]:
        return [j for j in self.judged if j.shape_ok is not None]

    @property
    def false_positives(self) -> List[JudgedSetup]:
        return [j for j in self.rated if j.false_positive]

    @property
    def false_negatives(self) -> List[JudgedSetup]:
        return [j for j in self.rated if j.false_negative]

    @property
    def correct(self) -> List[JudgedSetup]:
        return [j for j in self.rated if not (j.false_positive or j.false_negative)]

    def rate(self, which: str) -> Optional[float]:
        """نسبة نوع الخطأ من مجموع ما حُكم عليه — None إن لا عيّنة."""
        n = len(self.rated)
        if not n:
            return None
        pool = self.false_positives if which == "fp" else self.false_negatives
        return len(pool) / n

    def by_timeframe(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for j in self.rated:
            row = out.setdefault(j.timeframe, {"محكوم": 0, "إيجابية كاذبة": 0, "سلبية كاذبة": 0})
            row["محكوم"] += 1
            if j.false_positive:
                row["إيجابية كاذبة"] += 1
            if j.false_negative:
                row["سلبية كاذبة"] += 1
        return out

    def near_miss_link(self) -> Optional[str]:
        """
        هل الرفض بفارق ضئيل يتوافق مع السلبيات الكاذبة؟

        إن كان أكثر السلبيات الكاذبة مرصودًا أصلًا كـ«رفض بفارق ضئيل»،
        فالمعايرة هي المشكلة — لا المنهج.
        """
        fn = self.false_negatives
        if not fn:
            return None
        near = sum(1 for j in fn if j.near_miss)
        if near == 0:
            return "لا سلبية كاذبة كانت مرصودة كرفض بفارق ضئيل — المشكلة ليست في العتبات وحدها."
        return (
            f"{near} من {len(fn)} سلبية كاذبة كانت مرصودة كرفض بفارق ضئيل "
            "— توسيع السماحية مرشّح مباشر."
        )

    def render(self, min_sample: int = 20) -> str:
        n = len(self.rated)
        L = ["🎯 دقة الشكل — حكمك أنت", "─" * 34]

        if not n:
            L.append("   لا أحكام بعد.")
            return "\n".join(L)

        fp, fn = len(self.false_positives), len(self.false_negatives)
        L += [
            f"   محكوم عليها: {n}   ·   مطابق: {len(self.correct)}",
            "",
            f"   ❌ إيجابية كاذبة (تصرّف والشكل خاطئ): {fp}  ({fp / n:.0%})",
            "      ⇒ الشروط فضفاضة — «الحساب صح بس الشكل غير مطابق»",
            "",
            f"   ⛔ سلبية كاذبة (رفض والشكل صحيح): {fn}  ({fn / n:.0%})",
            "      ⇒ الشروط ضيقة — «الشكل صح بس الحساب غلط»",
        ]

        link = self.near_miss_link()
        if link:
            L += ["", f"   🔍 {link}"]

        rows = self.by_timeframe()
        if len(rows) > 1:
            L += ["", "   حسب الإطار:"]
            for tf, r in rows.items():
                L.append(
                    f"      {tf}: {r['محكوم']} محكوم · "
                    f"{r['إيجابية كاذبة']} إيجابية كاذبة · {r['سلبية كاذبة']} سلبية كاذبة"
                )

        if n < min_sample:
            L += ["", f"   ⚠️ العيّنة {n} من {min_sample} — لا تُتخذ قرارات معايرة بعد."]

        return "\n".join(L)


def prompt_for(setup_ids: Sequence[int]) -> str:
    """
    نصّ الطلب الذي يُذيَّل به السجل اليومي.

    يُبقي المطلوب سؤالًا واحدًا: **هل كان الشكل مطابقًا؟**
    لا رأي في النتيجة ولا في التوقيت — الربح والخسارة يقيسهما البوت وحده.

    تُمرَّر الأرقام كما تظهر في السجل — لا كترتيب داخلي — كي يبقى ردّ
    المستخدم مطابقًا لما رآه أمامه.
    """
    if not setup_ids:
        return ""
    ids = list(setup_ids)
    first = ids[0]
    second = ids[1] if len(ids) > 1 else first + 1
    return (
        "─" * 34 + "\n"
        "✍️ بانتظار حكمك — **هل كان الشكل مطابقًا؟**\n"
        f"   الإعدادات: {' · '.join(str(i) for i in ids)}\n"
        "   ردّ بسطر لكل واحد:\n"
        f"      {first} نعم\n"
        f"      {second} لا الشكل ما كان مطابق\n"
        "   (النتيجة يقيسها البوت — أنا أسأل عن **الشكل** فقط)"
    )
