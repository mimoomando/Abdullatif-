"""
طبقة الشرح — البوت يشرح نفسه.

قرار المستخدم 2026-08-26:
    «أريد أيضًا شرحًا مفصلًا لماذا دخل الصفقة وماذا حدث أثناء عمل الصفقة كاملًا»

جزآن منفصلان:

  TradeRationale  — **قبل** الدخول: كل فحص وسبب نجاحه أو فشله
  TradeJournal    — **أثناء وبعد**: سجل زمني لكل ما جرى حتى الإغلاق

مبدأ حاكم: **لا فحص بلا دليل رقمي.** كل بند يذكر القيمة التي قارنها،
لا مجرد «تحقّق ✓» — لأن الغرض أن يراجع المستخدم التحليل لا أن يثق به.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Literal, Optional

Direction = Literal["buy", "sell"]
Outcome = Literal["tp", "sl", "breakeven", "manual", "open"]

# درس ترابط الفريمات: «خلّي هدفك واحد على اثنين، واحد على ثلاثة…
#                      واحد على ثلاثة يكون ماكسيموم»
MAX_TARGET_RR = 3.0


# ─────────────────────────── فحص واحد ───────────────────────────


@dataclass(frozen=True)
class Check:
    """
    شرط واحد من سلسلة القرار.

    `evidence` إلزامي: الرقم أو المستوى الذي بُني عليه الحكم.
    `source` يربط الشرط بالدرس الذي جاء منه، فيمكن تتبّع أي قرار إلى مصدره.
    """

    name: str
    passed: bool
    evidence: str
    source: str

    def render(self) -> str:
        mark = "✅" if self.passed else "❌"
        return f"{mark} {self.name}\n      الدليل : {self.evidence}\n      المصدر : {self.source}"


# ─────────────────────────── سبب الدخول ───────────────────────────


@dataclass
class TradeRationale:
    """سلسلة القرار كاملة — تُبنى فحصًا فحصًا أثناء التحليل."""

    symbol: str
    direction: Direction
    poi_timeframe: str
    confirm_timeframe: str
    detected_at: datetime

    checks: List[Check] = field(default_factory=list)

    entry: Optional[float] = None
    stop: Optional[float] = None
    stop_reason: str = ""
    targets: List[float] = field(default_factory=list)
    target_reason: str = ""

    blocked_reason: str = ""      # يُملأ إن مُنع التنفيذ رغم صلاحية الإعداد

    def add(self, name: str, passed: bool, evidence: str, source: str) -> "TradeRationale":
        self.checks.append(Check(name, passed, evidence, source))
        return self

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> List[Check]:
        return [c for c in self.checks if not c.passed]

    @property
    def risk(self) -> Optional[float]:
        if self.entry is None or self.stop is None:
            return None
        return abs(self.entry - self.stop)

    def rr_of(self, target: float) -> Optional[float]:
        r = self.risk
        if not r:
            return None
        return abs(target - self.entry) / r

    def render(self) -> str:
        side = "شراء" if self.direction == "buy" else "بيع"
        head = "صفقة مقترحة" if self.accepted else "إعداد مرفوض"

        lines = [
            "═" * 58,
            f"{head} — {side} {self.symbol}",
            f"نقطة الاهتمام : {self.poi_timeframe}   ·   التأكيد : {self.confirm_timeframe}",
            f"الوقت         : {self.detected_at:%Y-%m-%d %H:%M}",
            "═" * 58,
            "",
            "سلسلة الفحص:",
            "",
        ]
        for i, c in enumerate(self.checks, 1):
            lines.append(f"  {i}. {c.render()}")
            lines.append("")

        if self.failed_checks:
            lines.append(f"⛔ الإعداد مرفوض — فشل {len(self.failed_checks)} من {len(self.checks)}")
            lines.append("")
            return "\n".join(lines)

        if self.entry is not None:
            lines.append("─" * 58)
            lines.append(f"  الدخول : {self.entry}")
            lines.append(f"  الوقف  : {self.stop}      ({self.stop_reason})")
            r = self.risk
            if r:
                lines.append(f"  المخاطرة: {r:.2f} وحدة")
            lines.append("")
            for i, t in enumerate(self.targets, 1):
                rr = self.rr_of(t)
                extra = f"  ·  1:{rr:.1f}" if rr else ""
                note = "   ← عنده يُنقل الوقف لنقطة الدخول" if i == 1 else ""
                if rr and rr > MAX_TARGET_RR + 1e-6:   # سماحية الفاصلة العائمة
                    note += f"   ⚠️ يتجاوز الحد 1:{MAX_TARGET_RR:g}"
                lines.append(f"  الهدف {i}: {t}{extra}{note}")
            if self.target_reason:
                lines.append(f"  ({self.target_reason})")
            lines.append("")

        if self.blocked_reason:
            lines.append("─" * 58)
            lines.append(f"🔔 تنبيه فقط — لم يُنفَّذ: {self.blocked_reason}")
            lines.append("")

        return "\n".join(lines)


# ─────────────────────────── سجل الصفقة ───────────────────────────


@dataclass(frozen=True)
class TradeEvent:
    time: datetime
    price: float
    label: str
    detail: str = ""


@dataclass
class TradeJournal:
    """
    ما حدث أثناء الصفقة، من الدخول إلى الإغلاق.

    يتتبّع أقصى ربح وأقصى خسارة عابرين (MFE / MAE) — وهما ما يكشف
    ما إذا كان الوقف قريبًا أكثر من اللازم، أو الهدف بعيدًا أكثر من اللازم.
    """

    rationale: TradeRationale
    opened_at: datetime
    entry: float

    events: List[TradeEvent] = field(default_factory=list)
    closed_at: Optional[datetime] = None
    close_price: Optional[float] = None
    outcome: Outcome = "open"

    _best: Optional[float] = None
    _worst: Optional[float] = None

    def _favourable(self, price: float) -> float:
        d = self.rationale.direction
        return price - self.entry if d == "buy" else self.entry - price

    def observe(self, time: datetime, price: float, label: str = "", detail: str = "") -> None:
        """تُستدعى مع كل شمعة أو حدث. تحدّث الأقصى وتسجّل ما يستحق."""
        move = self._favourable(price)
        if self._best is None or move > self._best:
            self._best = move
        if self._worst is None or move < self._worst:
            self._worst = move
        if label:
            self.events.append(TradeEvent(time, price, label, detail))

    def close(self, time: datetime, price: float, outcome: Outcome, detail: str = "") -> None:
        self.observe(time, price)
        self.closed_at = time
        self.close_price = price
        self.outcome = outcome
        self.events.append(TradeEvent(time, price, f"إغلاق — {outcome}", detail))

    @property
    def mfe(self) -> float:
        """أقصى ربح عابر بالوحدات."""
        return max(self._best or 0.0, 0.0)

    @property
    def mae(self) -> float:
        """أقصى خسارة عابرة بالوحدات (رقم موجب)."""
        return abs(min(self._worst or 0.0, 0.0))

    @property
    def result(self) -> Optional[float]:
        if self.close_price is None:
            return None
        return self._favourable(self.close_price)

    @property
    def r_multiple(self) -> Optional[float]:
        r = self.rationale.risk
        res = self.result
        if not r or res is None:
            return None
        return res / r

    @property
    def duration_minutes(self) -> Optional[int]:
        if self.closed_at is None:
            return None
        return int((self.closed_at - self.opened_at).total_seconds() // 60)

    def render(self) -> str:
        lines = ["═" * 58, "سجل الصفقة", "═" * 58, ""]

        for e in self.events:
            stamp = f"{e.time:%m-%d %H:%M}"
            lines.append(f"  {stamp}   {e.price:>10}   {e.label}")
            if e.detail:
                lines.append(f"                            {e.detail}")

        lines.append("")
        lines.append("─" * 58)

        r = self.rationale.risk
        if r:
            lines.append(f"  أقصى ربح عابر   : {self.mfe:.2f} وحدة   ({self.mfe / r:.2f}R)")
            lines.append(f"  أقصى خسارة عابرة: {self.mae:.2f} وحدة   ({self.mae / r:.2f}R)")
        else:
            lines.append(f"  أقصى ربح عابر   : {self.mfe:.2f} وحدة")
            lines.append(f"  أقصى خسارة عابرة: {self.mae:.2f} وحدة")

        if self.outcome == "open":
            lines.append("  الحالة          : مفتوحة")
            return "\n".join(lines)

        res, rm = self.result, self.r_multiple
        lines.append(f"  النتيجة         : {res:+.2f} وحدة" + (f"   ({rm:+.2f}R)" if rm else ""))
        lines.append(f"  المدة           : {self.duration_minutes} دقيقة")
        lines.append("")
        lines.extend(self._lessons(r))
        return "\n".join(lines)

    def _lessons(self, risk: Optional[float]) -> List[str]:
        """ملاحظات تُشتق من الأرقام وحدها — لا رأي ولا تخمين."""
        out: List[str] = []
        if not risk:
            return out

        if self.outcome == "sl" and self.mfe >= risk:
            out.append(f"  ⚠️ بلغت الصفقة +{self.mfe / risk:.1f}R قبل أن تُضرب — الخروج كان متاحًا.")
        if self.mae >= risk * 0.9 and self.outcome != "sl":
            out.append(f"  ⚠️ اقترب السعر من الوقف ({self.mae / risk:.2f}R) قبل أن ينجح.")
        if self.outcome == "tp" and self.mfe > abs(self.result or 0) * 1.5:
            out.append(f"  ℹ️ استمر السعر إلى +{self.mfe / risk:.1f}R بعد الخروج.")
        return out


# ─────────────────────────── التقرير الكامل ───────────────────────────


def full_report(journal: TradeJournal) -> str:
    """الشرح الكامل: لماذا دخل + ماذا حدث."""
    return journal.rationale.render() + "\n" + journal.render()
