"""
سجل ما بعد إغلاق السوق — يُرسَل على تيليجرام يوميًا.

قرار المستخدم 2026-08-27:
    «أريد سجلًا بعد إغلاق السوق يرسله لي البوت على التلجرام… كي نعرف السوق
     كيف يعمل، وما هي التناقضات التي حصلت، وما هي أهم النقاط التي يجب أن
     نعتمد عليها — لأنني أريد تجربته أكثر من أسبوع وبعدها نأخذ قرارات»

مبدآن يحكمان التصميم:

  ١. **أرقام لا انطباعات.** كل بند يذكر قيمه، فيمكن التحقق منه ومراجعته.
  ٢. **قابل للتحليل لا للقراءة فقط.** يحمل كتلة مضغوطة في آخره ليُقرأ آليًا
     حين يُعاد إرسال السجل، بدل إعادة استخراج الأرقام من نص حر.

⚠️ **العيّنة الصغيرة لا تُنتج قرارًا.** التقرير يعرض التكرارات ولا يستنتج
   منها قواعد. الاستنتاج بعد أسابيع، وبقرار مشترك.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Literal, Optional, Sequence

from .data import Candle
from .render import Level, Scene, Zone, write_svg
from .reporting import TradeJournal, TradeRationale
from .verdicts import Accuracy, Judge, JudgedSetup, Verdict, parse_verdicts, prompt_for

Disposition = Literal["taken", "blocked", "rejected"]
Severity = Literal["high", "medium", "low"]

TELEGRAM_LIMIT = 4096


# ─────────────────────────── لقطة السوق ───────────────────────────


@dataclass
class MarketSnapshot:
    day: date
    symbol: str
    open: float
    high: float
    low: float
    close: float
    structure: Dict[str, str] = field(default_factory=dict)   # إطار → صاعد/هابط/غير محدد
    key_levels: Dict[str, float] = field(default_factory=dict)

    @property
    def range_size(self) -> float:
        return self.high - self.low

    @property
    def net(self) -> float:
        return self.close - self.open

    @property
    def structures_agree(self) -> bool:
        vals = {v for v in self.structure.values() if v != "undefined"}
        return len(vals) <= 1


# ─────────────────────────── الإعدادات المرصودة ───────────────────────────


@dataclass
class SetupRecord:
    rationale: TradeRationale
    disposition: Disposition
    note: str = ""
    journal: Optional[TradeJournal] = None
    hypothetical_r: Optional[float] = None   # للمحجوب: ماذا كان سيحدث
    near_miss: bool = False                  # رصده المراقب كرفض بفارق ضئيل
    verdict: Optional[Verdict] = None        # الحكم على الشكل
    window: List[Candle] = field(default_factory=list)   # الشموع حول الإعداد
    zones: List[Zone] = field(default_factory=list)      # ما رسمه البوت: FVG · OB

    @property
    def r(self) -> Optional[float]:
        if self.journal is not None:
            return self.journal.r_multiple
        return self.hypothetical_r

    @property
    def shape_ok(self) -> Optional[bool]:
        return self.verdict.shape_ok if self.verdict else None

    def scene(self, setup_id: Optional[int] = None, plain: bool = False) -> Scene:
        """
        مشهد الشارت لهذا الإعداد.

        `plain=True` يرسم الشموع **عارية** — بلا مناطق ولا خطوط. تلك هي
        الصورة الصالحة للحكم على الشكل: ما إن يُرسم فوقها ما استنتجه البوت
        حتى يصير الناظر يقيّم استنتاج البوت لا شكل السوق.

        ⚠️ **لماذا التسميات لاتينية والشرح عربي؟** محوّلات SVG→PNG لا تصل
        الحروف العربية ولا تعكس اتجاهها، فتخرج «شراء» مقلوبة «ءارش».
        والصورة المقروءة خطأً أسوأ من صورة بلا تسمية، فبقيت التسميات على
        الشارت رموزًا تُرسم كما هي في كل عارض — والشرح العربي في نصّ السجل
        حيث يُعرض صحيحًا.
        """
        if not self.window:
            raise ValueError("لا شموع محفوظة لهذا الإعداد")

        r = self.rationale
        head = f"{r.symbol} · {r.poi_timeframe}"
        if setup_id is not None:
            head = f"#{setup_id} - {head}"

        if plain:
            return Scene(list(self.window), r.poi_timeframe, r.symbol, head)

        levels: List[Level] = []
        if r.entry is not None:
            levels.append(Level(r.entry, f"Entry {r.entry:g}", "entry"))
        if r.stop is not None:
            levels.append(Level(r.stop, f"SL {r.stop:g}", "stop"))
        for k, t in enumerate(r.targets or [], 1):
            levels.append(Level(t, f"TP{k} {t:g}", "target"))

        return Scene(
            candles=list(self.window),
            timeframe=r.poi_timeframe,
            symbol=r.symbol,
            title=f"{head} · {r.direction.upper()}",
            zones=list(self.zones),
            levels=levels,
        )


# ─────────────────────────── التناقضات ───────────────────────────


@dataclass(frozen=True)
class Finding:
    severity: Severity
    title: str
    detail: str
    evidence: str


def detect_findings(
    snapshot: MarketSnapshot,
    setups: Sequence[SetupRecord],
) -> List[Finding]:
    """
    يرصد ما يستحق النظر — **بلا استنتاج قواعد**.

    كل بند هنا حالة يمكن قياسها، لا رأيًا. الغرض أن يُعرَض على المستخدم
    ليقرر، لا أن يغيّر البوت سلوكه من تلقائه.
    """
    out: List[Finding] = []

    # ١. تعارض الهيكل بين الأطر
    if not snapshot.structures_agree:
        out.append(
            Finding(
                "medium",
                "الأطر لا تتفق على الاتجاه",
                "إعدادات الأطر المتعارضة أقل موثوقية — راقب أيها كان محقًا.",
                " · ".join(f"{k}={v}" for k, v in snapshot.structure.items()),
            )
        )

    taken = [s for s in setups if s.disposition == "taken" and s.journal]
    blocked = [s for s in setups if s.disposition == "blocked"]
    rejected = [s for s in setups if s.disposition == "rejected"]

    # ٢. وقف ضُرب بعد بلوغ ربح معتبر
    for s in taken:
        j = s.journal
        risk = s.rationale.risk
        if not risk or j.outcome != "sl":
            continue
        if j.mfe >= risk:
            out.append(
                Finding(
                    "high",
                    "ضُرب الوقف بعد بلوغ ربح",
                    "إما أن الهدف الأول بعيد، أو أن التأمين يجب أن يكون أبكر.",
                    f"{s.rationale.poi_timeframe} · بلغت +{j.mfe / risk:.2f}R ثم أُغلقت على الوقف",
                )
            )

    # ٣. الوقف كاد يُضرب ثم نجحت الصفقة
    for s in taken:
        j = s.journal
        risk = s.rationale.risk
        if not risk or j.outcome == "sl":
            continue
        if j.mae >= risk * 0.9:
            out.append(
                Finding(
                    "medium",
                    "الوقف ضيّق على الحافة",
                    "نجحت الصفقة بعد أن لامس السعر الوقف تقريبًا — تكرار هذا يعني وقفًا ضيقًا.",
                    f"{s.rationale.poi_timeframe} · بلغ التراجع {j.mae / risk:.2f}R قبل النجاح",
                )
            )

    # ٤. إعداد محجوب كان رابحًا
    for s in blocked:
        if s.hypothetical_r is not None and s.hypothetical_r >= 2:
            out.append(
                Finding(
                    "medium",
                    "فرصة محجوبة كانت رابحة",
                    "حدّ المركز الواحد منعها. تراكم هذه الحالات يبرّر إعادة النظر في الحد.",
                    f"{s.rationale.poi_timeframe} · كانت ستحقق {s.hypothetical_r:+.2f}R",
                )
            )

    # ٥. الشرط الأكثر رفضًا
    fails: Dict[str, int] = {}
    for s in rejected:
        for c in s.rationale.failed_checks:
            fails[c.name] = fails.get(c.name, 0) + 1
    if fails:
        name, n = max(fails.items(), key=lambda kv: kv[1])
        if n >= 2:
            out.append(
                Finding(
                    "low",
                    "شرط يرفض أكثر من غيره",
                    "قد يكون معايرته ضيقة — أو أنه يؤدي عمله بالضبط. العيّنة تحسم.",
                    f"«{name}» رفض {n} إعدادًا اليوم",
                )
            )

    # ٦. يوم بلا إعدادات مع مدى واسع
    if not setups and snapshot.range_size > 0:
        out.append(
            Finding(
                "low",
                "لا إعدادات رغم حركة السوق",
                "تحرّك السوق ولم يجد البوت إعدادًا — راجع إن كانت الشروط ضيقة.",
                f"مدى اليوم {snapshot.range_size:.2f} وحدة",
            )
        )

    return out


# ─────────────────────────── التقرير ───────────────────────────


@dataclass
class DailyReport:
    snapshot: MarketSnapshot
    setups: List[SetupRecord] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    accuracy: Optional[Accuracy] = None       # الحصيلة التراكمية عبر الأيام

    # ── إحصاء ──
    @property
    def taken(self) -> List[SetupRecord]:
        return [s for s in self.setups if s.disposition == "taken"]

    @property
    def closed(self) -> List[SetupRecord]:
        return [s for s in self.taken if s.journal and s.journal.outcome != "open"]

    @property
    def total_r(self) -> float:
        return sum(s.journal.r_multiple or 0 for s in self.closed)

    @property
    def wins(self) -> int:
        return sum(1 for s in self.closed if (s.journal.r_multiple or 0) > 0)

    # ── الحكم على الشكل ──
    def apply_verdicts(self, text: str, by: Judge = "user") -> int:
        """
        يلصق الردّ بالإعدادات حسب ترقيم العرض (١، ٢، ٣…).

        الرقم خارج المدى يُتجاهَل — الترقيم ترقيم هذا اليوم لا معرّفًا عالميًا.
        `by="assistant"` حين يحكم المساعد بدل المستخدم. يعيد عدد ما التصق.
        """
        n = 0
        for v in parse_verdicts(text, by=by):
            if 1 <= v.setup_id <= len(self.setups):
                self.setups[v.setup_id - 1].verdict = v
                n += 1
        return n

    def judged(self) -> List[JudgedSetup]:
        """
        الإعدادات في صيغة القياس — تُضاف إلى الحصيلة التراكمية.

        `saw_candles` يُشتق من وجود نافذة شموع فعلية: فهي وحدها ما يجعل
        حكم المساعد مراجعة مستقلة بدل إعادة لحساب البوت.
        """
        return [
            JudgedSetup(
                setup_id=i,
                disposition=s.disposition,
                timeframe=s.rationale.poi_timeframe,
                shape_ok=s.shape_ok,
                near_miss=s.near_miss,
                note=s.verdict.note if s.verdict else "",
                by=s.verdict.by if s.verdict else "user",
                saw_candles=bool(s.window),
            )
            for i, s in enumerate(self.setups, 1)
        ]

    @property
    def awaiting_verdict(self) -> List[SetupRecord]:
        return [s for s in self.setups if s.verdict is None]

    def by_timeframe(self) -> Dict[str, Dict[str, float]]:
        """أداء كل إطار منفصلًا — لتبيّن أيها يستحق البقاء."""
        out: Dict[str, Dict[str, float]] = {}
        for s in self.closed:
            tf = s.rationale.poi_timeframe
            row = out.setdefault(tf, {"عدد": 0, "رابحة": 0, "R": 0.0})
            row["عدد"] += 1
            r = s.journal.r_multiple or 0
            row["R"] += r
            if r > 0:
                row["رابحة"] += 1
        return out

    # ── العرض ──
    def render(self) -> str:
        s = self.snapshot
        arrow = "▲" if s.net > 0 else ("▼" if s.net < 0 else "◆")
        L = [
            f"📊 سجل {s.day:%Y-%m-%d} — {s.symbol}",
            "─" * 34,
            f"{arrow} {s.open:.2f} → {s.close:.2f}   ({s.net:+.2f})",
            f"المدى: {s.low:.2f} – {s.high:.2f}  ({s.range_size:.2f})",
        ]

        if s.structure:
            marks = " · ".join(f"{k}: {v}" for k, v in s.structure.items())
            flag = "" if s.structures_agree else "   ⚠️ غير متفقة"
            L += ["", f"الهيكل — {marks}{flag}"]

        if s.key_levels:
            L += ["", "مستويات اليوم:"]
            L += [f"   {k}: {v:.2f}" for k, v in s.key_levels.items()]

        # الإعدادات
        L += ["", "─" * 34, f"الإعدادات: {len(self.setups)}"]
        if not self.setups:
            L.append("   لا شيء")
        for i, st in enumerate(self.setups, 1):
            tag = {"taken": "✅ نُفِّذت", "blocked": "🔔 تنبيه", "rejected": "⛔ مرفوضة"}[
                st.disposition
            ]
            side = "شراء" if st.rationale.direction == "buy" else "بيع"
            r = st.r
            res = f"   {r:+.2f}R" if r is not None else ""
            L.append(f"{i}. {tag} · {side} · {st.rationale.poi_timeframe}{res}")
            if st.disposition == "rejected" and st.rationale.failed_checks:
                L.append(f"     السبب: {st.rationale.failed_checks[0].name}")
            elif st.note:
                L.append(f"     {st.note}")
            if st.verdict is not None:
                mark = "✅ الشكل مطابق" if st.verdict.shape_ok else "❌ الشكل غير مطابق"
                tail = f" — {st.verdict.note}" if st.verdict.note else ""
                L.append(f"     حكمك: {mark}{tail}")

        # النتيجة
        if self.closed:
            L += [
                "",
                "─" * 34,
                f"المغلقة: {len(self.closed)}  ·  رابحة: {self.wins}  ·  الحصيلة: {self.total_r:+.2f}R",
            ]
            for tf, row in self.by_timeframe().items():
                L.append(
                    f"   {tf}: {int(row['عدد'])} صفقة · "
                    f"{int(row['رابحة'])} رابحة · {row['R']:+.2f}R"
                )

        # ما يستحق النظر
        if self.findings:
            L += ["", "─" * 34, "🔍 يستحق النظر:"]
            icon = {"high": "🔴", "medium": "🟠", "low": "⚪"}
            for f in self.findings:
                L += [f"{icon[f.severity]} {f.title}", f"     {f.evidence}", f"     {f.detail}"]

        if self.notes:
            L += ["", "─" * 34, "ملاحظات:"] + [f"   • {n}" for n in self.notes]

        # دقة الشكل — الحصيلة التراكمية إن وُجدت
        if self.accuracy is not None and self.accuracy.rated:
            L += ["", "─" * 34, self.accuracy.render()]

        L += [
            "",
            "─" * 34,
            "⚠️ عيّنة يوم واحد لا تُنتج قاعدة. التقرير يعرض ولا يستنتج.",
        ]

        ask = prompt_for([i for i, s in enumerate(self.setups, 1) if s.verdict is None])
        if ask:
            L += ["", ask]

        L += ["", self.machine_block()]
        return "\n".join(L)

    def machine_block(self) -> str:
        """كتلة مضغوطة تُقرأ آليًا حين يُعاد إرسال السجل."""
        payload = {
            "v": 1,
            "day": f"{self.snapshot.day:%Y-%m-%d}",
            "symbol": self.snapshot.symbol,
            "ohlc": [
                self.snapshot.open, self.snapshot.high,
                self.snapshot.low, self.snapshot.close,
            ],
            "structure": self.snapshot.structure,
            "setups": [
                {
                    "id": i,
                    "tf": s.rationale.poi_timeframe,
                    "dir": s.rationale.direction,
                    "disp": s.disposition,
                    "r": round(s.r, 3) if s.r is not None else None,
                    "failed": [c.name for c in s.rationale.failed_checks],
                    "near_miss": s.near_miss,
                    "shape_ok": s.shape_ok,
                }
                for i, s in enumerate(self.setups, 1)
            ],
            "by_tf": {
                tf: {k: round(v, 3) for k, v in row.items()}
                for tf, row in self.by_timeframe().items()
            },
            "findings": [f.title for f in self.findings],
        }
        return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    def judging_packet(self, decimals: int = 2) -> str:
        """
        حزمة الحكم — ما يُعاد توجيهه إلى المساعد ليحكم على الشكل.

        قرار المستخدم 2026-08-27:
            «حتى لو لم أعرف أين الخطأ وأين الصح، أرسل السجل إليك وأنت تحكم»

        ما تحمله **الشموع الخام** حول كل إعداد، ونوع الشكل المزعوم،
        والمستويات التي بُني عليها. وما **لا** تحمله مقصود بالقدر نفسه:

            لا سبب الرفض · لا قيمة العتبة · لا «رُفض بفارق ضئيل» · لا النتيجة

        لأن الحاكم لو رأى خلاصة البوت حكم بها لا بالشكل، فوافقه بحكم البناء.
        الحجب هنا **شرط صحة القياس**، لا اختصارًا.

        النتيجة (R) محجوبة أيضًا: الصفقة الرابحة قد يكون شكلها خاطئًا،
        والخاسرة قد يكون شكلها سليمًا — والسؤال عن الشكل وحده.
        """
        def q(x: float) -> float:
            return round(x, decimals)

        setups = []
        for i, s in enumerate(self.setups, 1):
            r = s.rationale
            setups.append({
                "id": i,
                "tf": r.poi_timeframe,
                "confirm_tf": r.confirm_timeframe,
                "dir": r.direction,
                "levels": {
                    "entry": q(r.entry) if r.entry is not None else None,
                    "stop": q(r.stop) if r.stop is not None else None,
                    "targets": [q(t) for t in (r.targets or [])],
                },
                "candles": [
                    [f"{c.time:%m-%d %H:%M}", q(c.open), q(c.high), q(c.low), q(c.close)]
                    for c in s.window
                ],
            })

        payload = {
            "v": 1,
            "kind": "judging_packet",
            "day": f"{self.snapshot.day:%Y-%m-%d}",
            "symbol": self.snapshot.symbol,
            "candles_format": ["time", "open", "high", "low", "close"],
            "ask": "لكل إعداد: هل الشكل مطابق لنموذج المدرّب؟ ردّ «رقم نعم/لا».",
            "withheld": ["سبب الرفض", "العتبات", "الرفض بفارق ضئيل", "النتيجة"],
            "setups": setups,
        }

        missing = [s["id"] for s in setups if not s["candles"]]
        head = "🧾 حزمة الحكم — أعد توجيهها إلى المساعد"
        if missing:
            head += (
                f"\n⚠️ إعدادات بلا شموع: {' · '.join(map(str, missing))}"
                " — حكمها عليها سيكون تصديقًا لا مراجعة."
            )
        return head + "\n```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    # ── الشارت ──
    def write_charts(self, directory: str) -> Dict[str, List[str]]:
        """
        يكتب شارتَين لكل إعداد، ولكلٍّ غرض مختلف — والخلط بينهما يفسد القياس:

          `annotated` — الشموع + ما رسمه البوت (المناطق · الدخول · الوقف ·
              الهدف). **للدراسة**: ترى أين وضع البوت مناطقه، فإن أخطأ
              الموضع عرفته بعينك فورًا.

          `plain` — الشموع عارية. **للحكم**: ما إن تُرسم فوقها استنتاجات
              البوت حتى يصير الناظر يقيّم استنتاجه لا شكل السوق.

        يعيد المسارات مصنَّفة. الإعداد بلا شموع يُتخطّى بلا خطأ — غياب
        الصورة أهون من صورة فارغة تُوهم بأن شيئًا رُئي.
        """
        os.makedirs(directory, exist_ok=True)
        out: Dict[str, List[str]] = {"annotated": [], "plain": []}
        day = f"{self.snapshot.day:%Y%m%d}"

        for i, s in enumerate(self.setups, 1):
            if not s.window:
                continue
            for kind, plain in (("annotated", False), ("plain", True)):
                path = os.path.join(directory, f"{day}_setup{i}_{kind}.svg")
                write_svg(s.scene(setup_id=i, plain=plain), path)
                out[kind].append(path)

        return out


def split_for_telegram(text: str, limit: int = TELEGRAM_LIMIT) -> List[str]:
    """
    يقسّم التقرير إلى رسائل ضمن حد تيليجرام، بلا قطع سطر في منتصفه.

    السطر الأطول من الحد يُرسَل وحده — القطع داخله يفسد الأرقام.
    """
    if limit <= 0:
        raise ValueError("الحد يجب أن يكون موجبًا")

    parts: List[str] = []
    buf: List[str] = []
    size = 0

    for line in text.split("\n"):
        add = len(line) + 1
        if buf and size + add > limit:
            parts.append("\n".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += add

    if buf:
        parts.append("\n".join(buf))

    if len(parts) > 1:
        parts = [f"{p}\n\n({i}/{len(parts)})" for i, p in enumerate(parts, 1)]
    return parts


def build(
    snapshot: MarketSnapshot,
    setups: Sequence[SetupRecord],
    notes: Sequence[str] = (),
    accuracy: Optional[Accuracy] = None,
) -> DailyReport:
    return DailyReport(
        snapshot=snapshot,
        setups=list(setups),
        findings=detect_findings(snapshot, setups),
        notes=list(notes),
        accuracy=accuracy,
    )
