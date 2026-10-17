"""
سجل ما بعد إغلاق السوق.

╔══════════════════════════════════════════════════════════════════╗
║  ✅✅✅ **وُصل 2026-10-17 — `python -m bot.daily_report --day …`.**  ║
║  انظر [من السجلّ المكتوب] في آخر الملفّ.                          ║
║                                                                  ║
║  ⛔⛔⛔ **وكان قبلها لا يعمل — كُشف 2026-09-28، وكان هنا مكتوبًا    ║
║  [يُرسَل على تيليجرام يوميًا].**                                   ║
║                                                                  ║
║  فلا بوّابةَ تشغيلٍ كانت فيه، ولا يستورده شيءٌ داخل `bot/`،         ║
║  ولا يذكره `run.bat`. ⇒ **635 سطرًا لم تُنفَّذ قطّ.**                ║
║                                                                  ║
║  ⚠️⚠️ **وهذه الجملةُ نفسُها كانت تُخفي الدَّين**: حارسُ المداخل      ║
║  كان يبحث عن **كلمة** `__main__` في نصّ الملفّ، وكانت هنا في       ║
║  وصف غيابها ⇒ **فالملاحظةُ عن الدَّين كانت تسدّده.** صُحّح          ║
║  2026-10-17 — يُقرأ بـ`ast` (وهو `fvg.group_adjacent` ثالثةً).     ║
║                                                                  ║
║  وخفي لأنّ الملفّ كان مسجَّلًا في `test_wiring.ENTRY_POINTS`        ║
║  بحجّة [يُشغَّل من `run.bat`] — **وكان `ENTRY_POINTS` إعفاءً بلا     ║
║  برهان**: يكفي كتابةُ الاسم فيه لتخرج الوحدةُ من كلّ فحص.         ║
║  (وصار المدخلُ يُبرهِن على نفسه: `__main__` أو ذكرٌ في `run.bat`.) ║
║                                                                  ║
║  ⇒ **وما يصل المستخدمَ فعلًا هو `runner.render_package`** —        ║
║  [حصاد التشغيل]: عددُ القرارات · الإعداداتُ المتمايزة ·            ║
║  الفحوصُ الراسبة. وهو **لا يحمل**: سؤالَ الحكم على الشكل، ولا      ║
║  حزمةَ الحكم، ولا حصيلةَ الدقّة، ولا فجواتِ الإغلاق.               ║
║                                                                  ║
║  ⚠️ **ولا يُوصَل بلا قياس.** فالوصلُ تغييرُ سلوكٍ لا إصلاحُ صمت،     ║
║  و[قِس قبل أن تغيّر] تسري عليه. وأوّلُ ما يلزم: أيُّ أرقامه         ║
║  يملكها `runner` أصلًا؟ فـ`TradeJournal` **لا يُبنى في الإنتاج**   ║
║  إطلاقًا ⇒ `closed` و`wins` و`total_r` و`by_timeframe` كلُّها      ║
║  فارغةٌ بالبناء، لا بالسوق.                                       ║
╚══════════════════════════════════════════════════════════════════╝

قرار المستخدم 2026-08-27:
    [أريد سجلًا بعد إغلاق السوق يرسله لي البوت على التلجرام… كي نعرف السوق
     كيف يعمل، وما هي التناقضات التي حصلت، وما هي أهم النقاط التي يجب أن
     نعتمد عليها — لأنني أريد تجربته أكثر من أسبوع وبعدها نأخذ قرارات]

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
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from .data import Candle
from .render import Level, Scene, Zone, write_svg
from .reporting import TradeJournal, TradeRationale
from .verdicts import (
    Accuracy, Judge, JudgedSetup, Verdict, dropped, parse_verdicts, prompt_for,
)

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

    # ٦. صفقة نامت عبر إغلاق السوق — مراجعة قرار «أبقِها مفتوحة»
    slept = [s for s in taken if s.journal.slept]
    if slept:
        harmed = [s for s in slept if s.journal.gap_effect < 0]
        net = sum(s.journal.gap_effect for s in slept)
        out.append(
            Finding(
                "high" if harmed else "low",
                "صفقة نامت عبر الإغلاق",
                "المدرّب ينصح بعدم تنييم الصفقة. أنت اخترت إبقاءها — "
                "وهذا هو الرقم الذي يراجَع به الاختيار، لا الجدل.",
                f"{len(slept)} صفقة عبرت الإغلاق · "
                f"{len(harmed)} تضرّرت · صافي أثر الفجوات {net:+.2f} وحدة",
            )
        )

    # ٧. يوم بلا إعدادات مع مدى واسع
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
    unread_reply: List[str] = field(default_factory=list)   # ما لم يُفهَم من الردّ

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

        ⭐ **وما سقط يُسمّى** في `unread_reply` — سطرٌ بدا جوابًا ولم
        يُفهَم، أو رقمٌ خارج مدى اليوم. [صُحّح 09-28: كان الردُّ الناقص
        يبدو كاملًا.]
        """
        n = 0
        out_of_range: List[str] = []
        for v in parse_verdicts(text, by=by):
            if 1 <= v.setup_id <= len(self.setups):
                self.setups[v.setup_id - 1].verdict = v
                n += 1
            else:
                out_of_range.append(f"{v.setup_id} — رقمٌ خارج إعدادات اليوم")
        self.unread_reply = dropped(text) + out_of_range
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

        # ⭐ ما بدا جوابًا ولم يُفهَم — **يُقال**. وردٌّ عن ثلاثةٍ يُفهَم
        #   منه اثنان كان يبدو كاملًا. [09-28]
        if self.unread_reply:
            L += ["", "─" * 34, "⚠️ لم أفهم من ردّك:"]
            L += [f"   • {line}" for line in self.unread_reply]
            L += ["   الصيغة: رقم ثم نعم/لا — مثال: [3 لا الشكل ما كان مطابق]"]

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
                    "slept": bool(s.journal and s.journal.slept),
                    "gap_effect": (
                        round(s.journal.gap_effect, 3)
                        if s.journal and s.journal.slept else None
                    ),
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
            [حتى لو لم أعرف أين الخطأ وأين الصح، أرسل السجل إليك وأنت تحكم]

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


# ─────────────────────────── من السجلّ المكتوب ───────────────────────────
#
# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⭐⭐⭐ **الوصلُ — 2026-10-17، بطلب المستخدم [اكمل وصل الوحدات].**  ║
# ║                                                                  ║
# ║  وكانت 635 سطرًا **لم تُنفَّذ قطّ** (كُشف 09-28)، ومعها            ║
# ║  `verdicts.py` (397 سطرًا) — **يستوردها هذا الملفُّ وحدَه**         ║
# ║  فكانت لها مظهرُ الموصولة.                                        ║
# ║                                                                  ║
# ║  ⛔ **والوصلُ من السجلّ المكتوب لا من شمعةٍ حيّة**: لا جسرَ         ║
# ║  يُفتح، ولا `order_send` ولا `order_check` — القاعدةُ ②.           ║
# ║  ومدخلٌ **يُبرهِن على نفسه** (`__main__`)، لا اسمٌ في قائمةِ        ║
# ║  إعفاء — **وذلك بعينه هو العطبُ الذي أخفاها**.                    ║
# ║                                                                  ║
# ║  ⚠️⚠️ **ولا سلوكَ حيًّا يتغيّر**: `runner` لا يستورد هذا الملفّ،    ║
# ║  وما يصل المستخدمَ في التشغيل يبقى `runner.render_package`.        ║
# ║  ⇒ **فهو أمرُ يدٍ كـ`instructor`**، وأثرُه على القياس صفرٌ.         ║
# ╚══════════════════════════════════════════════════════════════════╝

STRUCTURE_FIELDS = ("closes", "swings")


@dataclass
class LogRead:
    """
    ما قُرئ وما تعذّر — **والعجزُ يُعَدّ ويُصاح به، لا يُبتلَع.**

    ⚠️ فسطرُ `[!!]` هو عرفُ هذا المشروع: [اجعلها تكتب سطرًا حين لا
    تعمل]. **والصمتُ ليس نجاحًا.**
    """

    rows: int = 0
    day_rows: int = 0
    bars: int = 0
    gaps: List[Tuple[str, str, int]] = field(default_factory=list)
    unreadable_structure: int = 0
    blocked_duplicate: int = 0
    blocked_fresh: int = 0
    stopped_dropped: int = 0
    rejected_rows: int = 0
    rejected_kinds: int = 0

    def shouts(self) -> List[str]:
        out: List[str] = []
        if not self.bars:
            out.append("[!!] لا شمعةَ واحدةٌ لهذا اليوم على هذا الإطار — "
                       "والتقريرُ فارغٌ بعجزِ السجلّ لا بسكوتِ السوق")
        for a, b, mins in self.gaps:
            out.append(f"[!!] فجوةُ تسجيل: {a} → {b} ({mins} دقيقة)")
        if self.unreadable_structure:
            out.append(f"[!!] {self.unreadable_structure} صفًّا تعذّر "
                       "انتزاعُ هيكلِ `classify_trend` منه — "
                       "**عجزُ قراءةٍ عندي، لا [هيكلًا غيرَ محدَّد]**")
        if self.stopped_dropped:
            out.append(f"[!!] {self.stopped_dropped} صفًّا كُتب وقتَ `STOP` "
                       "⇒ أُسقط (وهو قرارُ KS2 المسجَّل)")
        if self.blocked_duplicate:
            out.append(
                f"⚠️ {self.blocked_duplicate} صفًّا محجوبًا **هو الإعدادُ "
                "المأخوذُ نفسُه** (تكرارُ إعلان) ⇒ فلا يُعَدّ فرصةً محجوبة، "
                "ولا يُحسب له [ماذا كان سيحدث]")
        return out


def _rationale_of(row: Dict) -> TradeRationale:
    """صفُّ السجلّ ⇒ سلسلةُ القرار — **حقلًا بحقل، بلا انتزاعٍ من نصّ**."""
    from datetime import datetime

    r = TradeRationale(
        symbol=row.get("symbol", ""),
        direction=row.get("direction", "buy"),
        poi_timeframe=row.get("poi_tf", ""),
        confirm_timeframe=row.get("confirm_tf", ""),
        detected_at=datetime.fromisoformat(row["candle_time"]),
        entry=row.get("entry"),
        stop=row.get("stop"),
        stop_reason=row.get("stop_reason", "") or "",
        targets=list(row.get("targets") or []),
        target_reason=row.get("target_reason", "") or "",
        blocked_reason=row.get("blocked_reason", "") or "",
        trail_plan=list(row.get("trail_plan") or []),
    )
    for c in row.get("checks") or ():
        r.add(str(c.get("name", "")), bool(c.get("passed")),
              str(c.get("evidence", "")), str(c.get("source", "")))
    return r


def snapshot_of(day_rows: Sequence[Dict], day: date, timeframe: str,
                structure: str = "closes",
                read: Optional[LogRead] = None) -> MarketSnapshot:
    """
    لقطةُ اليوم — **من الشموع التي سجّلها البوت، لا من السوق.**

    ⚠️⚠️ **والفرقُ يُقال**: البوتُ يسجّل حين يعمل. فيومٌ توقّف فيه
    ساعتين **مداه مدى ما رُئي**، وسطرُ الفجوة في `LogRead` هو ما
    يمنع قراءةَ ذلك سكوتًا للسوق. **وهو BR1 بعينه في جهته الثالثة:**
    عجزُ إمدادٍ يتنكّر في صورة حالةِ سوق.

    `structure`: `closes` ⇒ حقلُ `structure_closes` **نظيفًا**
    (قاعدةُ المدرّب بلفظها) · `swings` ⇒ `classify_trend`
    **انتزاعًا من نصّ الفحص** — والعجزُ يُعَدّ.

    ⭐ **وآخرُ شمعةٍ في اليوم هي حكمُ اليوم** — وهو اختياري أنا،
    **وهو عينُ اختيار `instructor.measured_from_log`** فلا يفترق
    الموضعان.
    """
    from . import replay as _replay
    from .instructor import trend_from_checks

    if structure not in STRUCTURE_FIELDS:
        raise ValueError(f"هيكلٌ غيرُ معروف: {structure!r} — "
                         f"والمعروفُ {STRUCTURE_FIELDS}")

    rd = read if read is not None else LogRead()
    bars = _replay.rebuild(day_rows, timeframe)
    rd.bars = len(bars)
    cov = _replay.coverage(bars, timeframe)
    rd.gaps = [(f"{a:%H:%M}", f"{b:%H:%M}", m) for a, b, m in cov.gaps]

    o = bars[0].o if bars else 0.0
    c = bars[-1].c if bars else 0.0
    hi = max((b.h for b in bars), default=0.0)
    lo = min((b.l for b in bars), default=0.0)

    frames: Dict[str, str] = {}
    for r in day_rows:
        tf = r.get("poi_tf")
        if not tf:
            continue
        got = (r.get("structure_closes") if structure == "closes"
               else trend_from_checks(r.get("checks") or ()))
        if got is None:
            rd.unreadable_structure += 1
            continue
        frames[tf] = got                      # ⬅ الأخيرةُ تغلب

    return MarketSnapshot(day=day, symbol=_symbol_of(day_rows),
                          open=o, high=hi, low=lo, close=c,
                          structure=frames)


def _symbol_of(rows: Sequence[Dict]) -> str:
    for r in rows:
        if r.get("symbol"):
            return str(r["symbol"])
    return ""


def records_of(day_rows: Sequence[Dict], all_rows: Sequence[Dict],
               timeframe: str, read: LogRead,
               window: int = 0) -> List[SetupRecord]:
    """
    الإعداداتُ **المتمايزة** في صيغة التقرير — بثلاث دفعاتٍ مرتَّبة.

    | الدفعة | التمايزُ بماذا | و`r` |
    |---|---|---|
    | المأخوذة | `replay.setups_with_rows` — **موضعٌ واحد** | من دفترٍ مرصودٍ شمعةً شمعة |
    | المحجوبة | `Setup.key()` نفسُها | 🔴 **ولا شيء** — انظر أدناه |
    | المرفوضة | (الإطار · الجهة · **أوّلُ فحصٍ رسب**) | لا شيء — لا دخولَ لها |

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⛔⛔⛔ **وفخٌّ كشفه العدُّ قبل أن يُكتب سطرٌ واحد.**             ║
    ║                                                              ║
    ║  فـ`detect_findings` فيه بندٌ اسمُه [فرصة محجوبة كانت          ║
    ║  رابحة] وتفسيرُه [**حدّ المركز الواحد منعها**]. **وجُردت        ║
    ║  المحجوباتُ في السجلّ كلِّه فكانت 24، و24 منها مفتاحُها          ║
    ║  مفتاحُ إعدادٍ مأخوذ** — وسببُها المكتوب «الإعداد نفسه          ║
    ║  أُعلن… تكرارٌ لا تنبيه».                                      ║
    ║                                                              ║
    ║  ⇒ ⭐⭐⭐ **فلو حُسب لها [ماذا كان سيحدث] لأعلن التقريرُ         ║
    ║  أربعًا وعشرين فرصةً رابحةً محجوبة — وهي الصفقاتُ التي         ║
    ║  أخذها البوتُ فعلًا.** رقمٌ خاطئٌ يمرّ، وهو أسوأُ من الغائب.    ║
    ║                                                              ║
    ║  ⇒ **والمحجوبُ المكرَّر يُسقَط ويُعَدّ**، والمحجوبُ الذي لا       ║
    ║  نظيرَ له يبقى **ويُعَدّ كذلك** — ⚠️ **وعدُّه صفرٌ اليومَ         ║
    ║  بالقياس لا بالبناء**، فالفرعُ حيٌّ ينتظر حالتَه.               ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    from . import replay as _replay

    out: List[SetupRecord] = []
    bars = _replay.rebuild(all_rows, timeframe)

    taken = [(s, r) for s, r in _replay.setups_with_rows(day_rows, "taken")
             if s.timeframe == timeframe]
    read.stopped_dropped += _replay.stopped_dropped
    taken_keys = {s.key() for s, _ in _replay.setups_with_rows(all_rows, "taken")}
    read.stopped_dropped += _replay.stopped_dropped

    for s, row in taken:
        result = _replay.walk(bars, s)
        out.append(SetupRecord(
            rationale=_rationale_of(row), disposition="taken",
            note=f"×{s.announcements} إعلانًا · {result.outcome}",
            journal=_replay._journal_of(result, bars),
            window=_window_of(bars, s, window),
        ))

    for s, row in _replay.setups_with_rows(day_rows, "blocked"):
        if s.timeframe != timeframe:
            continue
        if s.key() in taken_keys:
            read.blocked_duplicate += s.announcements
            continue
        read.blocked_fresh += 1
        res = _replay.walk(bars, s)
        risk = s.risk or 0.0
        out.append(SetupRecord(
            rationale=_rationale_of(row), disposition="blocked",
            note=row.get("blocked_reason", "") or "",
            hypothetical_r=(res.pnl / risk) if risk else None,
            window=_window_of(bars, s, window),
        ))

    seen: Dict[Tuple, Dict] = {}
    order: List[Tuple] = []
    for r in day_rows:
        if r.get("disposition") != "rejected" or r.get("poi_tf") != timeframe:
            continue
        read.rejected_rows += 1
        first = next((c for c in r.get("checks") or ()
                      if not c.get("passed")), None)
        k = (r.get("direction"), str(first.get("name")) if first else "")
        if k not in seen:
            seen[k] = dict(r=r, n=0)
            order.append(k)
        seen[k]["n"] += 1
    read.rejected_kinds = len(order)
    for k in order:
        row, n = seen[k]["r"], seen[k]["n"]
        out.append(SetupRecord(
            rationale=_rationale_of(row), disposition="rejected",
            note=f"×{n} شمعة",
        ))
    return out


def _window_of(bars: Sequence, setup, span: int) -> List[Candle]:
    """
    شموعُ ما حول الإعداد — **أو لا شيء، و`span=0` هو القائم.**

    ⚠️⚠️ **ولمَ مطفأً؟** لأنّ `JudgedSetup.saw_candles` يُشتقُّ من
    وجود النافذة، **وهو ما يجعل حكمَ المساعد مراجعةً مستقلّة**. فمن
    ملأها بلا أن يرى الصورةَ فعلًا **جعل التصديقَ يُحسب مراجعة.**
    ⇒ **فالنافذةُ تُطلَب صريحًا** (`--window N`)، ومعها تُكتب الصور.
    """
    if span <= 0:
        return []
    from datetime import datetime

    t = datetime.fromisoformat(setup.first_seen)
    idx = [i for i, b in enumerate(bars) if b.time <= t]
    if not idx:
        return []
    i = idx[-1]
    lo, hi = max(0, i - span), min(len(bars), i + span + 1)
    return [Candle(b.time, b.o, b.h, b.l, b.c) for b in bars[lo:hi]]


def from_log(path: str, day: date, timeframe: str = "M15",
             structure: str = "closes",
             window: int = 0) -> Tuple[DailyReport, LogRead]:
    """السجلُّ المكتوب ⇒ تقريرُ يومٍ واحد — **ولا شمعةَ حيّة تُقرأ.**"""
    from . import replay as _replay

    rows = _replay.read_journal(path)
    read = LogRead(rows=len(rows))
    day_rows = _replay.on_day(rows, day)
    read.day_rows = len(day_rows)

    snap = snapshot_of(day_rows, day, timeframe, structure, read)
    setups = records_of(day_rows, rows, timeframe, read, window)

    notes = [f"المصدر: {os.path.basename(path)} · "
             f"{read.day_rows} قرارًا في اليوم من {read.rows} · "
             f"الإطار {timeframe} · الهيكل من "
             f"{'حقلِ الإغلاقات' if structure == 'closes' else 'انتزاعِ الفحص'}"]
    if read.rejected_rows:
        notes.append(f"المرفوضة: {read.rejected_rows} شمعةً في "
                     f"{read.rejected_kinds} نوعًا — "
                     "**والعدُّ المعروضُ عددُ الأنواع**")
    return build(snap, setups, notes), read


def main(argv=None) -> int:
    """
    `python -m bot.daily_report --day 2026-10-09`

    ⛔ **ولا يرسل شيئًا ولا يفتح جسرًا** — يطبع على الشاشة، وقراءةُ
    `runs/decisions.jsonl` كلُّ ما يفعل.
    """
    import argparse
    from datetime import datetime

    from . import replay as _replay

    _replay.utf8_console()

    p = argparse.ArgumentParser(
        prog="python -m bot.daily_report",
        description="سجلُّ ما بعد إغلاق السوق — من السجلّ المكتوب")
    p.add_argument("--day", required=True, help="YYYY-MM-DD")
    p.add_argument("--log", default=os.path.join("runs", "decisions.jsonl"))
    p.add_argument("--tf", default="M15")
    p.add_argument("--structure", default="closes", choices=STRUCTURE_FIELDS)
    p.add_argument("--window", type=int, default=0,
                   help="شموعُ ما حول الإعداد — ومعها تُحسب [رأى الشموع]")
    p.add_argument("--charts", default="", help="مجلّدٌ تُكتب فيه الصور")
    p.add_argument("--verdicts", default="",
                   help="ملفُّ ردٍّ يُطبَّق: [3 لا الشكل ما كان مطابق]")
    p.add_argument("--packet", action="store_true",
                   help="حزمةُ الحكم وحدَها")
    args = p.parse_args(argv)

    try:
        day = datetime.strptime(args.day, "%Y-%m-%d").date()
    except ValueError:
        print(f"⛔ تاريخٌ غيرُ صالح: {args.day!r} — والصيغةُ YYYY-MM-DD")
        return 1
    if not os.path.exists(args.log):
        print(f"⛔ لا سجلَّ في {args.log}")
        return 1

    report, read = from_log(args.log, day, args.tf, args.structure,
                            args.window)

    if args.verdicts:
        if not os.path.exists(args.verdicts):
            print(f"⛔ لا ملفَّ ردٍّ في {args.verdicts}")
            return 1
        with open(args.verdicts, encoding="utf-8") as fh:
            n = report.apply_verdicts(fh.read())
        print(f"✅ التصق {n} حكمًا")
        acc = Accuracy()
        acc.add([j for j in report.judged() if j.shape_ok is not None])
        report.accuracy = acc

    for line in read.shouts():
        print(line)

    if args.packet:
        print(report.judging_packet())
    else:
        print(report.render())

    if args.charts:
        made = report.write_charts(args.charts)
        for kind, paths in made.items():
            print(f"🖼 {kind}: {len(paths)} صورة")
        if not any(made.values()):
            print("[!!] لا صورةَ واحدة — ولا نافذةَ شموعٍ محفوظة "
                  "(أضف `--window N`)")
    return 0


if __name__ == "__main__":        # pragma: no cover
    raise SystemExit(main())
