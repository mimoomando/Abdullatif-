"""
حلقة التشغيل — أسبوعُ ملاحظةٍ يُحوِّل التخمين إلى قياس.

╔══════════════════════════════════════════════════════════════════╗
║  خطة المستخدم (2026-09-05):                                       ║
║    «نشغّل البوت على وضعه، ونجعل له سجلًّا للصفقات وسجلًّا للشارت،   ║
║     وبعد أسبوع أرسل لك السجل وأنت تستنتج الأجوبة **من الواقع      ║
║     لا تخمينًا**»                                                 ║
╚══════════════════════════════════════════════════════════════════╝

⭐ **وهذا يفتح ~24 معاملًا `UNDEFINED`** لم يعطها المدرّب رقمًا: كم
سماحية؟ كم شمعة؟ كم قربًا؟ لا تُخترَع — تُقاس.

⛔ **ووضع الورق هو المشغَّل: لا أوامر إطلاقًا.**

    الجسر يقرأ ولا يأمر، و`guards.EXECUTION_ENABLED = False`.
    فالبوت يسجّل **ما كان سيفعله** ثم يقيس ما جرى بعده.

وليس هذا نقصًا في الخطة بل أنسبُ لها: أغلب المعاملات المعلّقة
**عتباتُ رصد** تُجاب من الشموع والقرارات وحدها، ولا تحتاج تنفيذًا.
والتي تحتاجه (الانزلاق، ثمن السبريد الفعليّ) تنتظر مرحلةً ثانية.

⚠️ **والمتانة شرطٌ لا تحسين**: أسبوعٌ يسقط في ليلته الثالثة لا يعطي
أسبوعًا. فكل تمريرة معزولة، وخطؤها يُسجَّل ولا يوقف الحلقة، والسجل
**يُلحَق سطرًا سطرًا** فلا يضيع ما مضى بانقطاع.
"""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from . import guards
from . import params as P
from .chain import ChainConfig, ChainResult, evaluate
from .data import Series

RUN_VERSION = 1

# H4←M30 · H1←M5 · M15←M3 — جدول ترابط الفريمات، والأزواج النشطة
DEFAULT_PAIRS: Dict[str, str] = {
    tf: P.TIMEFRAME_PAIRS.value[tf] for tf in P.ACTIVE_POI_TIMEFRAMES.value
}


@dataclass
class RunConfig:
    """إعداد الجلسة — ما يُقرأ وأين يُكتب."""

    out_dir: str = "runs"
    pairs: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PAIRS))
    candles: int = 200
    save_charts: bool = True
    chart_window: int = 60

    # ⭐ ملفٌّ مقروء **لكل صفقة**: لماذا فُتحت، وما الذي وافق وما خالف.
    save_dossiers: bool = True
    # كم فحصًا راسبًا يبقى الإعداد معه جديرًا بملفّ؟
    # صفر = المقبولة وحدها · واحد = ومعها ما رسب بفحصٍ واحد — وتلك
    # أنفع ما في الأسبوع: الرفض بفارق ضئيل هو ما يضبط العتبة.
    dossier_max_failed: int = 1

    @property
    def journal_path(self) -> str:
        return os.path.join(self.out_dir, "decisions.jsonl")

    @property
    def errors_path(self) -> str:
        return os.path.join(self.out_dir, "errors.jsonl")

    @property
    def charts_dir(self) -> str:
        return os.path.join(self.out_dir, "charts")

    @property
    def dossiers_dir(self) -> str:
        return os.path.join(self.out_dir, "trades")

    @property
    def index_path(self) -> str:
        return os.path.join(self.dossiers_dir, "000-index.txt")


# ─────────────────────────── المسجّل ───────────────────────────


class Recorder:
    """
    سجلّ يُلحَق سطرًا سطرًا — JSONL.

    **لماذا JSONL لا ملفّ واحد؟** لأن كل سطر مستقلّ: انقطاعُ الكهرباء
    في منتصف الكتابة يُتلف السطر الأخير وحده، ويبقى الأسبوع كلّه
    مقروءًا. وملفٌّ واحد يُعاد كتابته كلَّ مرة يضيع بأكمله.

    ولا يُسجَّل القرار مرّتين: التمريرة تتكرّر كل دقائق والشمعة
    نفسها تبقى آخر مغلقة، فيُمنع التكرار بمفتاح (الإطار، وقت الشمعة).

    ⭐ **وللإعداد المقبول مفتاحٌ ثانٍ.** الشمعة تتغيّر كل ربع ساعة
    بينما الأوردر بلوك نفسه يبقى `fresh`، فيُعلَن من جديد في كل
    شمعة. وقد وقع هذا فعلًا في أسبوع الملاحظة: **20 إعدادًا
    متمايزًا أُعلنت 60 مرّة** — أحدها تسع مرّات.

    وعلى حساب حقيقيّ هذا يعني فتح الصفقة نفسها كل ربع ساعة. وأثره
    مقيس على الأسبوع نفسه:

        20 إعدادًا متمايزًا   ⇒  −10.21$
        60 قرارًا كما سُجّلت  ⇒  −316.26$        ⬅ واحدٌ وثلاثون ضعفًا

    ⇒ فالتكرار **أكبر بندٍ منفرد في خسارة الأسبوع** — وليس قاعدةً
    تداوليّة يُستأذَن فيها، بل عطبٌ في التسجيل.

    والمفتاح هو هويّة الإعداد: (الإطار · الاتجاه · الدخول · الوقف)
    مقرَّبةً إلى سنتٍ واحد، لأن الأوردر بلوك الواحد يعطي الأرقام
    نفسها ما دام قائمًا. والمرفوضات لا تُخضَع له — إنما تُسجَّل كلها،
    فالفحص الراسب المعدود هو ما يضبط المعاملات.
    """

    def __init__(self, cfg: RunConfig):
        self.cfg = cfg
        os.makedirs(cfg.out_dir, exist_ok=True)
        if cfg.save_charts:
            os.makedirs(cfg.charts_dir, exist_ok=True)
        if cfg.save_dossiers:
            os.makedirs(cfg.dossiers_dir, exist_ok=True)
        self._seen: set = set()
        self._setups: Dict = {}          # هويّة الإعداد ⇒ وقت أول إعلان
        self._load_seen()

    @staticmethod
    def setup_key(record: Dict):
        """هويّة الإعداد — أو None إن لم يكن إعدادًا ذا دخول."""
        entry, stop = record.get("entry"), record.get("stop")
        if entry is None or stop is None:
            return None
        return (record.get("poi_tf"), record.get("direction"),
                round(float(entry), 2), round(float(stop), 2))

    def _load_seen(self) -> None:
        if not os.path.exists(self.cfg.journal_path):
            return
        with open(self.cfg.journal_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue          # سطر مبتور — يُتخطّى ولا يُسقط الملفّ
                self._seen.add((d.get("poi_tf"), d.get("candle_time")))
                key = self.setup_key(d)
                if key is not None and d.get("disposition") == "taken":
                    self._setups.setdefault(key, d.get("candle_time"))

    def already(self, poi_tf: str, candle_time: str) -> bool:
        return (poi_tf, candle_time) in self._seen

    def announced_at(self, record: Dict) -> Optional[str]:
        """وقت أول إعلانٍ لهذا الإعداد نفسه — أو None إن كان جديدًا."""
        key = self.setup_key(record)
        return self._setups.get(key) if key is not None else None

    def write(self, record: Dict) -> None:
        self._seen.add((record.get("poi_tf"), record.get("candle_time")))
        key = self.setup_key(record)
        if key is not None and record.get("disposition") == "taken":
            self._setups.setdefault(key, record.get("candle_time"))
        with open(self.cfg.journal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def write_error(self, where: str, exc: BaseException) -> None:
        row = {
            "at": datetime.now(timezone.utc).isoformat(),
            "where": where,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(limit=6),
        }
        with open(self.cfg.errors_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def save_chart(self, name: str, svg: str) -> str:
        path = os.path.join(self.cfg.charts_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        return path

    def save_dossier(self, name: str, text: str, index_line: str) -> str:
        """
        ملفّ صفقة واحد + سطرٌ في الفهرس.

        الفهرس ليس زينة: بعد أسبوع تصير الملفّات مئات، وبلا فهرس
        لا يُعرف أين يُبدأ.
        """
        path = os.path.join(self.cfg.dossiers_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        with open(self.cfg.index_path, "a", encoding="utf-8") as fh:
            fh.write(index_line + "\n")
        return path

    def count(self) -> int:
        return len(self._seen)


# ─────────────────────────── التمريرة ───────────────────────────


def _record_from(
    result: ChainResult,
    poi_tf: str,
    confirm_tf: str,
    series: Series,
    spread: float,
    chart: Optional[str] = None,
    confirm_series: Optional[Series] = None,
) -> Dict:
    r = result.rationale
    last = series.last_closed()
    cl = confirm_series.last_closed() if confirm_series is not None else None
    return {
        "v": RUN_VERSION,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "symbol": series.symbol,
        "poi_tf": poi_tf,
        "confirm_tf": confirm_tf,
        "candle_time": last.time.isoformat(),
        "candle": {"o": last.open, "h": last.high, "l": last.low, "c": last.close},
        # ⭐ وشمعةُ **الإطار المقابل** معها — أُضيفت 2026-09-12.
        #
        # ولماذا؟ لأن أسبوع 09-07…11 لم يحفظ إلّا شمعة إطار نقطة
        # الاهتمام، فتعذّر قياسُ **تنقيح الدخول** عليه أصلًا: التنقيح
        # يقع على الإطار المقابل (M3 لـM15)، وذلك الإطار غائبٌ عن
        # السجل. فلمّا شُغّلت السلسلة عليه اضطُرّ M15 أن يكون إطارَ
        # تأكيد نفسه، فلم يقع تنقيحٌ واحد — لا لأن القاعدة عاطلة بل
        # **لأن البيانات لا تحملها**.
        #
        # ⇒ بهذا السطر يصير الأسبوع القادم قابلًا للقياس: تُعاد
        # السلسلتان معًا، ويُقارَن الوقف المنقَّح بوقف حدّ المنطقة.
        "confirm_candle": (
            {"o": cl.open, "h": cl.high, "l": cl.low, "c": cl.close,
             "t": cl.time.isoformat()} if cl is not None else None
        ),
        "spread": spread,
        "disposition": result.disposition,
        "note": result.note,
        "direction": r.direction,
        "entry": r.entry,
        "stop": r.stop,
        "stop_reason": r.stop_reason,
        "targets": list(r.targets or []),
        "target_reason": r.target_reason,
        "blocked_reason": r.blocked_reason,
        # ⭐ سلسلة الفحص كاملة — الفحص الذي **رسب** هو الجواب على
        # «لماذا لا يجد إعدادات؟»، وهو ما يضبط العتبات.
        "checks": [
            {"name": c.name, "passed": c.passed,
             "evidence": c.evidence, "source": c.source}
            for c in r.checks
        ],
        # ⭐ **مسجَّلة ولا تحكم بعد.** هيكل المدرّب بقاعدته هو —
        # «ما أغلق تحت بشمعتين» — إلى جانب هيكل `classify_trend`
        # الذي يقرّر فعلًا. وهما يختلفان، ولذلك يُسجَّلان معًا.
        #
        # ولماذا لا تُطبَّق الآن؟ لأن أسبوع 09-07…11 **لم يستطع
        # الحكم**: 30 شمعة H4 فيها تحوّلان اثنان لا غير، فوافقت
        # القاعدةُ المدرّبَ 1/5 يومًا و`classify_trend` 2/5 — وهذا
        # فرقٌ لا يُبنى عليه. والسطر أدناه هو ما يجعل الأسبوع القادم
        # قادرًا على الحكم: مئتا شمعة لا ثلاثون، والرقمان في السجلّ
        # معًا يومًا بيوم.
        "structure_closes": _closes_trend(series),
        "chart": chart,
    }


def _closes_trend(series: Series) -> Optional[str]:
    """هيكل الإطار بقاعدة الإغلاقات المتتالية — للتسجيل لا للحكم."""
    try:
        from .params import STRUCTURE_BREAK_CLOSES
        from .primitives.structure import trend_at_close
        from .primitives.swings import find_swings

        n = STRUCTURE_BREAK_CLOSES.value
        if not n:
            return None
        return trend_at_close(series, find_swings(series), closes=n)
    except Exception:                        # noqa: BLE001 — تسجيلٌ لا حكم
        return None


def dossier_text(
    result: ChainResult,
    poi_tf: str,
    confirm_tf: str,
    series: Series,
    spread: float,
    chart: Optional[str],
) -> str:
    """
    ملفّ الصفقة الواحدة — **يُقرأ بالعين لا بالآلة**.

    طلب المستخدم (2026-09-05): «أريد لكل صفقة سجلًّا خاصًّا: لماذا
    فتحها، وما توافقت، والتاريخ، وكل شيء».

    و`TradeRationale.render()` يحمل قلب ذلك أصلًا: كل شرط ✅/❌ مع
    **دليله ومصدر درسه**. فما يُضاف هنا سياقُه: السوق وقتها، والشمعة،
    والسبريد، وأين الشارت، وموضعٌ يُملأ بالنتيجة لاحقًا.
    """
    r = result.rationale
    last = series.last_closed()
    passed = [c for c in r.checks if c.passed]

    head = {
        "accepted": "✅ صفقة مقترحة",
        "rejected": "⛔ إعداد مرفوض",
        "blocked": "🔔 صالح لكنه محجوب",
    }.get(result.disposition, result.disposition)

    lines = [
        "═" * 58,
        f"{head}",
        "═" * 58,
        "",
        f"  الرمز        : {series.symbol}",
        f"  الأطر        : {poi_tf} ← {confirm_tf}",
        f"  وقت الشمعة   : {last.time:%Y-%m-%d %H:%M}",
        f"  سُجّل في      : {datetime.now():%Y-%m-%d %H:%M}",
        f"  الاتجاه      : {'شراء' if r.direction == 'buy' else 'بيع'}",
        "",
        "  الشمعة المغلقة:",
        f"    افتتاح {last.open:g} · أعلى {last.high:g} · "
        f"أدنى {last.low:g} · إغلاق {last.close:g}",
        f"  السبريد وقتها: {spread:g}",
        "",
        f"  الخلاصة      : وافق {len(passed)} من {len(r.checks)} شرطًا",
    ]
    if result.note:
        lines.append(f"  الملاحظة     : {result.note}")
    if chart:
        lines.append(f"  الشارت       : charts/{chart}")

    lines += ["", r.render()]

    # موضعٌ يُملأ لاحقًا — النتيجة لا تُعرف ساعةَ القرار.
    lines += [
        "─" * 58,
        "النتيجة (تُملأ بعد الإغلاق)",
        "─" * 58,
        "  ما حدث       : ",
        "  أقصى ربح عابر: ",
        "  أقصى خسارة   : ",
        "  حكمك على الشكل (سليم / غير سليم) : ",
        "",
    ]
    return "\n".join(lines)


def _try_dossier(result, poi_tf, confirm_tf, series, spread, chart, cfg, recorder):
    """يكتب ملفّ الصفقة إن استحقّ — والفشل يُسجَّل ولا يُسقط التمريرة."""
    failed = len(result.rationale.failed_checks)
    if failed > cfg.dossier_max_failed:
        return None
    try:
        last = series.last_closed()
        stamp = f"{last.time:%Y%m%d-%H%M}"
        name = f"{stamp}_{poi_tf}_{result.disposition}.txt"
        mark = {"accepted": "✅", "blocked": "🔔"}.get(result.disposition, "⛔")
        index = (
            f"{mark} {stamp}  {poi_tf:4s}  "
            f"وافق {len(result.rationale.checks) - failed}"
            f"/{len(result.rationale.checks)}  {name}"
        )
        recorder.save_dossier(
            name,
            dossier_text(result, poi_tf, confirm_tf, series, spread, chart),
            index,
        )
        return name
    except Exception as exc:                 # noqa: BLE001
        recorder.write_error("dossier", exc)
        return None


class OffsetProbe:
    """
    يقيس إزاحة خادم الوسيط **مرّة واحدة** ويحتفظ بها.

    ⭐ **لماذا تُرفَق بكل قرار؟** أوقات الشموع كلها **بوقت الخادم** —
    وهو الصواب: قواعد المدرّب عن تسلسل الشموع لا عن UTC، وما تراه في
    الملفّ يطابق ما تراه في MT5. لكن أسبوعًا من الطوابع **بلا منطقة
    زمنية مرفقة** يفقد نصف معناه عند التحليل: لا يُعرف أيّ شمعة وقعت
    في جلسة لندن ولا أيّها عند فتح نيويورك.

    ⚠️ ولا تُقاس إلا والسوق مفتوح (`StaleTick`)، فتُعاد المحاولة حتى
    تنجح — ولا يتعطّل التسجيل في انتظارها.

    ⭐ **وبتباطؤ.** في أسبوع الملاحظة أُعيدت المحاولة في كل تمريرة
    والسوق مغلق، فكتبت **3632 خطأً** — أغلبها هذا السبب وحده، ونصُّها
    واحد مكرَّر. وسجلُّ أخطاءٍ بهذا الحجم يُخفي الخطأ الحقيقيّ بين
    آلاف النسخ من خطأٍ متوقَّع.

    فتتضاعف المهلة: 1 ثم 2 ثم 4 … حتى `MAX_BACKOFF` تمريرة. وعطلةُ
    نهاية أسبوعٍ كاملة تكلّف عندئذٍ **عشرات الأسطر لا آلافها**.
    """

    MAX_BACKOFF = 64                            # تمريرات

    def __init__(self):
        self.value: Optional[float] = None
        self._skip = 0                          # تمريرات متبقّية قبل المحاولة
        self._backoff = 1
        self.attempts = 0

    def read(self, bridge, recorder: Recorder) -> Optional[float]:
        if self.value is not None:
            return self.value
        if self._skip > 0:
            self._skip -= 1
            return None
        self.attempts += 1
        try:
            self.value = bridge.measure_server_offset()
        except Exception as exc:                 # noqa: BLE001 — StaleTick أو غيره
            recorder.write_error("offset", exc)
            self._skip = self._backoff
            self._backoff = min(self._backoff * 2, self.MAX_BACKOFF)
        return self.value


def run_once(bridge, cfg: RunConfig, recorder: Recorder,
             probe: Optional[OffsetProbe] = None) -> int:
    """
    تمريرة واحدة على كل زوج أطر. تُرجع عدد القرارات المسجَّلة.

    ⛔ لا تُرسل أمرًا ولا تُعدّل مركزًا. تقرأ، تحكم، تسجّل.

    وكلُّ زوجٍ معزول: عطبُ إطارٍ لا يُسقط البقية.
    """
    guards.assert_analysis_only.__doc__      # توثيقٌ للنية؛ لا تنفيذ هنا
    written = 0

    try:
        spread = bridge.spread()
    except Exception as exc:                 # noqa: BLE001 — تُسجَّل وتُستكمل
        recorder.write_error("spread", exc)
        spread = 0.0

    offset = probe.read(bridge, recorder) if probe is not None else None

    for poi_tf, confirm_tf in cfg.pairs.items():
        try:
            poi = bridge.fetch(poi_tf, cfg.candles)
            confirm = bridge.fetch(confirm_tf, cfg.candles)
            if len(poi) == 0 or len(confirm) == 0:
                continue

            stamp = poi.last_closed().time.isoformat()
            if recorder.already(poi_tf, stamp):
                continue                     # الشمعة نفسها — لا تُسجَّل مرّتين

            result = evaluate(
                poi, confirm,
                ChainConfig(poi_timeframe=poi_tf, confirm_timeframe=confirm_tf,
                            spread=spread),
            )

            chart = None
            if cfg.save_charts:
                chart = _try_chart(poi, poi_tf, cfg, recorder, stamp)

            row = _record_from(result, poi_tf, confirm_tf, poi, spread, chart,
                               confirm_series=confirm)

            # ⭐ الإعداد نفسه لا يُعلَن مرّتين. يُسجَّل — كي يبقى معدودًا —
            # لكنه يُحوَّل إلى `blocked` فلا يُقرأ تنبيهًا جديدًا.
            first = recorder.announced_at(row) if row.get("disposition") == "taken" else None
            repeat = first is not None
            if repeat:
                row["disposition"] = "blocked"
                row["repeat_of"] = first
                row["blocked_reason"] = f"الإعداد نفسه أُعلن عند {first} — تكرارٌ لا تنبيه"

            dossier = None
            if cfg.save_dossiers and not repeat:
                dossier = _try_dossier(
                    result, poi_tf, confirm_tf, poi, spread, chart, cfg, recorder)

            row["dossier"] = dossier
            row["server_utc_offset"] = offset
            recorder.write(row)
            written += 1

        except Exception as exc:             # noqa: BLE001
            recorder.write_error(f"pair:{poi_tf}", exc)

    return written


def _try_chart(series, poi_tf, cfg, recorder, stamp) -> Optional[str]:
    """
    يحفظ الشارت **عاريًا** — بلا مناطق ولا خطوط.

    ⭐ وهذا مقصود: ما إن يُرسَم فوقه استنتاجُ البوت حتى يصير الناظر
    يقيّم استنتاج البوت لا شكل السوق. والصورة العارية وحدها تصلح
    للحكم المستقلّ.
    """
    try:
        from .render import Scene, render_svg
        window = list(series)[-cfg.chart_window:]
        if not window:
            return None
        scene = Scene(window, poi_tf, series.symbol, f"{series.symbol} · {poi_tf}")
        name = f"{poi_tf}_{stamp.replace(':', '-')}.svg"
        recorder.save_chart(name, render_svg(scene))
        return name
    except Exception as exc:                 # noqa: BLE001
        recorder.write_error("chart", exc)
        return None


# ─────────────────────────── الحزمة ───────────────────────────


def package(out_dir: str) -> Dict:
    """
    يلمّ الأسبوع في ملخّصٍ واحد — هذا ما تُرسله إليّ.

    ولا يلخّص إلى نِسَبٍ فقط: يُبقي **الفحوص الراسبة معدودةً**، لأنها
    الجواب المباشر على كل معامل معلّق. «رسب فحص القرب 41 مرة» يقول
    عن السماحية ما لا يقوله «لم يجد إعدادات».
    """
    cfg = RunConfig(out_dir=out_dir)
    rows: List[Dict] = []
    broken = 0

    if os.path.exists(cfg.journal_path):
        with open(cfg.journal_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    broken += 1

    errors = 0
    if os.path.exists(cfg.errors_path):
        with open(cfg.errors_path, encoding="utf-8") as fh:
            errors = sum(1 for _ in fh)

    by_disp: Dict[str, int] = {}
    by_tf: Dict[str, int] = {}
    failed_checks: Dict[str, int] = {}
    spreads: List[float] = []

    for r in rows:
        by_disp[r.get("disposition", "?")] = by_disp.get(r.get("disposition", "?"), 0) + 1
        tf = r.get("poi_tf", "?")
        by_tf[tf] = by_tf.get(tf, 0) + 1
        if r.get("spread"):
            spreads.append(r["spread"])
        for c in r.get("checks", []):
            if not c.get("passed"):
                failed_checks[c["name"]] = failed_checks.get(c["name"], 0) + 1

    # ⭐ الإعداد المتمايز غير القرار. في أسبوع 09-07…11 كانت 60 قرارًا
    # مقبولًا **عشرين إعدادًا** — والفرق بينهما 31 ضعفًا في الحصيلة.
    distinct = {Recorder.setup_key(r) for r in rows
                if r.get("disposition") == "taken"}
    distinct.discard(None)

    times = sorted(r["candle_time"] for r in rows if r.get("candle_time"))
    return {
        "v": RUN_VERSION,
        "decisions": len(rows),
        "distinct_setups": len(distinct),
        "repeats": sum(1 for r in rows if r.get("repeat_of")),
        "broken_lines": broken,
        "errors": errors,
        "first": times[0] if times else None,
        "last": times[-1] if times else None,
        "by_disposition": by_disp,
        "by_timeframe": by_tf,
        "failed_checks": dict(sorted(failed_checks.items(),
                                     key=lambda kv: kv[1], reverse=True)),
        "spread": {
            "n": len(spreads),
            "min": min(spreads) if spreads else None,
            "max": max(spreads) if spreads else None,
            "avg": round(sum(spreads) / len(spreads), 3) if spreads else None,
        },
        "charts": (len(os.listdir(cfg.charts_dir))
                   if os.path.isdir(cfg.charts_dir) else 0),
        "dossiers": sum(1 for r in rows if r.get("dossier")),
        # منطقة الأوقات التي كُتبت بها كل الطوابع — بلا هذا لا يُعرف
        # أيّ شمعة وقعت في أيّ جلسة.
        "server_utc_offset": next(
            (r["server_utc_offset"] for r in reversed(rows)
             if r.get("server_utc_offset") is not None), None),
    }


def render_package(pkg: Dict) -> str:
    lines = ["═" * 58, "حصاد التشغيل", "═" * 58, ""]
    lines.append(f"  قرارات مسجَّلة : {pkg['decisions']}")
    # ⭐ الرقمان معًا — فالقرار غير الإعداد، والخلط بينهما كلّف
    # أسبوع 09-07…11 واحدًا وثلاثين ضعفًا.
    lines.append(f"  إعدادات متمايزة: {pkg.get('distinct_setups', 0)}"
                 f"   (تكرار مكبوح: {pkg.get('repeats', 0)})")
    lines.append(f"  من {pkg['first']} إلى {pkg['last']}")
    lines.append(f"  شارتات        : {pkg['charts']}")
    lines.append(f"  ملفّات صفقات   : {pkg['dossiers']}")
    lines.append(f"  أخطاء         : {pkg['errors']}")
    off = pkg.get("server_utc_offset")
    lines.append(
        f"  توقيت الخادم  : UTC{off:+g}  (كل الأوقات أدناه بوقت الخادم)"
        if off is not None else
        "  توقيت الخادم  : ⚠️ لم يُقَس بعد (السوق كان مغلقًا)")
    if pkg["broken_lines"]:
        lines.append(f"  ⚠️ أسطر مبتورة: {pkg['broken_lines']} (انقطاع كتابة)")

    lines += ["", "  الأحكام:"]
    for k, v in sorted(pkg["by_disposition"].items(), key=lambda kv: -kv[1]):
        lines.append(f"    {k:12s} {v}")

    lines += ["", "  حسب الإطار:"]
    for k, v in sorted(pkg["by_timeframe"].items(), key=lambda kv: -kv[1]):
        lines.append(f"    {k:6s} {v}")

    sp = pkg["spread"]
    if sp["n"]:
        lines += ["", f"  السبريد: أدنى {sp['min']} · أعلى {sp['max']} · متوسط {sp['avg']}"]

    lines += ["", "  ⭐ الفحوص الراسبة — هنا تُضبط العتبات:"]
    if not pkg["failed_checks"]:
        lines.append("    لا شيء.")
    for k, v in pkg["failed_checks"].items():
        lines.append(f"    {v:5d}  {k}")

    lines += ["", "أرسل لي: هذا الملخّص · decisions.jsonl · مجلّد trades/"]
    return "\n".join(lines)


# ─────────────────────────── التشغيل ───────────────────────────


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    `python -m bot.runner`            تمريرة واحدة
    `python -m bot.runner --watch`    حلقة مستمرّة
    `python -m bot.runner --package`  حصاد ما جُمع
    """
    import argparse

    ap = argparse.ArgumentParser(description="حلقة تشغيل البوت — وضع الورق")
    ap.add_argument("--out", default="runs")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--every", type=int, default=60, help="ثوانٍ بين التمريرات")
    ap.add_argument("--package", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    cfg = RunConfig(out_dir=args.out)

    if args.package:
        print(render_package(package(args.out)))
        return 0

    from . import local_config as lc
    from .mt5_bridge import BridgeConfig, open_terminal

    try:
        settings = lc.load()
        bridge = open_terminal(
            BridgeConfig(symbol=settings.get("SYMBOL", "XAUUSD.m")),
            **lc.mt5_credentials(settings),
        )
    except Exception as exc:                 # noqa: BLE001
        print(f"❌ تعذّر فتح الجسر: {exc}")
        return 1

    recorder = Recorder(cfg)
    probe = OffsetProbe()
    print("⛔ وضع الورق — لا أوامر تُرسل. تسجيل فقط.")
    print(f"📁 {os.path.abspath(cfg.out_dir)}")

    if not args.watch:
        n = run_once(bridge, cfg, recorder, probe)
        print(f"✅ سُجّل {n} قرارًا (الإجمالي {recorder.count()})")
        return 0

    import time
    print(f"🔁 كل {args.every} ثانية — أوقفه بـ Ctrl+C")
    try:
        while True:
            try:
                n = run_once(bridge, cfg, recorder, probe)
                if n:
                    print(f"  {datetime.now():%m-%d %H:%M}  +{n}  "
                          f"(الإجمالي {recorder.count()})")
            except Exception as exc:         # noqa: BLE001
                # الحلقة لا تموت: أسبوعٌ يسقط ليلته الثالثة لا يعطي أسبوعًا
                recorder.write_error("loop", exc)
            time.sleep(max(5, args.every))
    except KeyboardInterrupt:
        print(f"\n⏹️ توقّف. الإجمالي {recorder.count()} قرارًا.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
