"""
حكم المستخدم على الشكل — الطبقة التي لا يستطيع الكود توفيرها.

سبب وجودها — اعتراض المدرّب (2026-08-27):

    «إذا **الحساب صح بس الشكل غير مطابق** — بفوت»

هذا النوع من الخطأ **لا يراه الكود إطلاقًا**: الشروط الرقمية تحققت كلها،
فالبوت لا يملك ما ينبّهه. العين وحدها ترى أن الشكل لم يكن نموذجًا صحيحًا.

فيراجَع الشكل ويوضع الحكم، فيتحول الاعتراض من جدل إلى رقم:

    إيجابية كاذبة  =  البوت تصرّف  والشكل خاطئ   ⇒ شروطه فضفاضة
    سلبية كاذبة    =  البوت رفض    والشكل صحيح   ⇒ شروطه ضيقة

صيغة الردّ على تيليجرام مقصودة البساطة — سطر لكل إعداد:

    ١ نعم
    ٢ لا
    ٣ لا الشكل ما كان مطابق

**من يحكم؟** — قرار المستخدم 2026-08-27:

    «حتى لو لم أعرف أين الخطأ وأين الصح، أرسل السجل إليك وأنت تحكم»

فصار الحاكم اثنين، ويُسجَّل أيّهما حكم في الحقل `by`. والتمييز ليس شكليًا:

  • **المستخدم** يرى الشارت. عينه مستقلة عن حساب البوت تمامًا،
    فحكمه دليل حقيقي على الشكل.

  • **المساعد** لا يرى شيئًا إلا ما يصل إليه. فإن وصلته الأرقام النهائية
    وحدها — «رُفض لأن الفارق 3 والسماحية 1.5» — فهو **يعيد حساب البوت
    ولا يراجعه**، ويوافقه بحكم البناء لا بحكم النظر. وحدها الشموع الخام
    تجعل حكمه مراجعة فعلية، ولذلك تحمل «حزمة الحكم» الشموع لا الخلاصات.

⚠️ **الحكم لا يغيّر سلوك البوت تلقائيًا.** يُجمع ويُعرض، والقرار مشترك.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional, Sequence, Set

YES = {"نعم", "ايوا", "أيوا", "اي", "صح", "صحيح", "مطابق", "y", "yes", "ok", "1", "١"}
NO = {"لا", "لأ", "غلط", "خطأ", "خطا", "مش", "n", "no", "0", "٠"}

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

Judge = Literal["user", "assistant"]

JUDGE_AR = {"user": "أنت", "assistant": "المساعد"}


@dataclass(frozen=True)
class Verdict:
    """حكم على شكل إعداد واحد — من المستخدم أو من المساعد."""

    setup_id: int
    shape_ok: bool
    note: str = ""
    at: Optional[datetime] = None
    by: Judge = "user"

    def render(self) -> str:
        mark = "✅ الشكل مطابق" if self.shape_ok else "❌ الشكل غير مطابق"
        tail = f" — {self.note}" if self.note else ""
        return f"{self.setup_id}. {mark}{tail}  ({JUDGE_AR[self.by]})"


def parse_verdicts(
    text: str,
    at: Optional[datetime] = None,
    by: Judge = "user",
) -> List[Verdict]:
    """
    يقرأ الردّ: رقم ثم نعم/لا ثم ملاحظة اختيارية.

    متسامح مع الأرقام العربية والمسافات الزائدة. السطر غير المفهوم
    يُتجاهَل بصمت — لأن رفض ردّ كامل بسبب سطر واحد أسوأ من تجاهله.

    `by` يوسم مصدر الحكم؛ الصيغة نفسها للاثنين كي يمرّ حكم المساعد
    من البوابة ذاتها ويُقاس بالمسطرة ذاتها.
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
        out.append(Verdict(sid, ok, note, at, by))
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
    by: Judge = "user"              # من حكم
    saw_candles: bool = False       # هل رأى الحاكم الشموع الخام؟

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

    @property
    def independent(self) -> bool:
        """
        هل كان الحكم نظرة مستقلة عن حساب البوت؟

        المستخدم يرى الشارت فحكمه مستقل دائمًا. والمساعد مستقل **فقط**
        إن وصلته الشموع الخام؛ فإن حكم من خلاصات البوت فقد أعاد حسابه
        ووافقه بحكم البناء — وذلك ليس قياسًا.
        """
        if self.shape_ok is None:
            return False
        return self.by == "user" or self.saw_candles


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

    @property
    def independent(self) -> List[JudgedSetup]:
        """الأحكام التي كانت نظرة مستقلة — وحدها تصلح للمعايرة."""
        return [j for j in self.rated if j.independent]

    @property
    def dependent(self) -> List[JudgedSetup]:
        """أحكام صدرت من خلاصات البوت — تُعرَض ولا تُبنى عليها معايرة."""
        return [j for j in self.rated if not j.independent]

    def by_judge(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for j in self.rated:
            key = JUDGE_AR.get(j.by, j.by)
            row = out.setdefault(key, {"محكوم": 0, "مستقل": 0})
            row["محكوم"] += 1
            if j.independent:
                row["مستقل"] += 1
        return out

    def rate(self, which: str, independent_only: bool = True) -> Optional[float]:
        """
        نسبة نوع الخطأ — None إن لا عيّنة.

        تُحسب افتراضيًا على الأحكام المستقلة وحدها: إدخال حكمٍ مشتقٍّ من
        خلاصات البوت في النسبة يجعل البوت يصحّح نفسه بنفسه.
        """
        base = self.independent if independent_only else self.rated
        if not base:
            return None
        pool = [j for j in base if (j.false_positive if which == "fp" else j.false_negative)]
        return len(pool) / len(base)

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

        يُحسب على الأحكام المستقلة وحدها — لأنه اقتراح معايرة.
        """
        fn = [j for j in self.independent if j.false_negative]
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
        L = ["🎯 دقة الشكل — الحكم على الشكل", "─" * 34]

        if not self.rated:
            L.append("   لا أحكام بعد.")
            return "\n".join(L)

        base = self.independent
        n = len(base)
        if not n:
            L += [
                f"   أحكام: {len(self.rated)} — **ولا واحد منها مستقل**.",
                "      كلها صدرت من خلاصات البوت لا من الشموع.",
                "      ⇒ لا تصلح للقياس: البوت يصادق على نفسه.",
                "      أرسل حزمة الحكم (الشموع الخام) بدل السجل وحده.",
            ]
            return "\n".join(L)

        fp = [j for j in base if j.false_positive]
        fn = [j for j in base if j.false_negative]
        ok = [j for j in base if not (j.false_positive or j.false_negative)]

        L += [
            f"   محكوم عليها: {n}   ·   مطابق: {len(ok)}",
            "",
            f"   ❌ إيجابية كاذبة (تصرّف والشكل خاطئ): {len(fp)}  ({len(fp) / n:.0%})",
            "      ⇒ الشروط فضفاضة — «الحساب صح بس الشكل غير مطابق»",
            "",
            f"   ⛔ سلبية كاذبة (رفض والشكل صحيح): {len(fn)}  ({len(fn) / n:.0%})",
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

        judges = self.by_judge()
        if len(judges) > 1:
            L += ["", "   من حكم:"]
            for who, r in judges.items():
                L.append(f"      {who}: {r['محكوم']} — منها {r['مستقل']} نظرة مستقلة")

        excluded = len(self.dependent)
        if excluded:
            L += [
                "",
                f"   ⚠️ استُبعد {excluded} حكمًا من القياس — صدر من خلاصات البوت",
                "      لا من الشموع، فهو تصديق لا مراجعة.",
            ]

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
        "✍️ بانتظار الحكم — **هل كان الشكل مطابقًا؟**\n"
        f"   الإعدادات: {' · '.join(str(i) for i in ids)}\n"
        "   ردّ بسطر لكل واحد:\n"
        f"      {first} نعم\n"
        f"      {second} لا الشكل ما كان مطابق\n"
        "   (النتيجة يقيسها البوت — السؤال عن **الشكل** فقط)\n"
        "\n"
        "   ولو لم تعرف: أعد توجيه **حزمة الحكم** التالية إلى المساعد\n"
        "   وهو يحكم. الحزمة تحمل الشموع الخام — لا خلاصات البوت —\n"
        "   كي يكون حكمه مراجعة لا تصديقًا."
    )
