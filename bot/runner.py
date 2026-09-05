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

    @property
    def journal_path(self) -> str:
        return os.path.join(self.out_dir, "decisions.jsonl")

    @property
    def errors_path(self) -> str:
        return os.path.join(self.out_dir, "errors.jsonl")

    @property
    def charts_dir(self) -> str:
        return os.path.join(self.out_dir, "charts")


# ─────────────────────────── المسجّل ───────────────────────────


class Recorder:
    """
    سجلّ يُلحَق سطرًا سطرًا — JSONL.

    **لماذا JSONL لا ملفّ واحد؟** لأن كل سطر مستقلّ: انقطاعُ الكهرباء
    في منتصف الكتابة يُتلف السطر الأخير وحده، ويبقى الأسبوع كلّه
    مقروءًا. وملفٌّ واحد يُعاد كتابته كلَّ مرة يضيع بأكمله.

    ولا يُسجَّل القرار مرّتين: التمريرة تتكرّر كل دقائق والشمعة
    نفسها تبقى آخر مغلقة، فيُمنع التكرار بمفتاح (الإطار، وقت الشمعة).
    """

    def __init__(self, cfg: RunConfig):
        self.cfg = cfg
        os.makedirs(cfg.out_dir, exist_ok=True)
        if cfg.save_charts:
            os.makedirs(cfg.charts_dir, exist_ok=True)
        self._seen = self._load_seen()

    def _load_seen(self) -> set:
        seen = set()
        if not os.path.exists(self.cfg.journal_path):
            return seen
        with open(self.cfg.journal_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue          # سطر مبتور — يُتخطّى ولا يُسقط الملفّ
                seen.add((d.get("poi_tf"), d.get("candle_time")))
        return seen

    def already(self, poi_tf: str, candle_time: str) -> bool:
        return (poi_tf, candle_time) in self._seen

    def write(self, record: Dict) -> None:
        key = (record.get("poi_tf"), record.get("candle_time"))
        self._seen.add(key)
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
) -> Dict:
    r = result.rationale
    last = series.last_closed()
    return {
        "v": RUN_VERSION,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "symbol": series.symbol,
        "poi_tf": poi_tf,
        "confirm_tf": confirm_tf,
        "candle_time": last.time.isoformat(),
        "candle": {"o": last.open, "h": last.high, "l": last.low, "c": last.close},
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
        "chart": chart,
    }


def run_once(bridge, cfg: RunConfig, recorder: Recorder) -> int:
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

            recorder.write(_record_from(result, poi_tf, confirm_tf, poi, spread, chart))
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

    times = sorted(r["candle_time"] for r in rows if r.get("candle_time"))
    return {
        "v": RUN_VERSION,
        "decisions": len(rows),
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
    }


def render_package(pkg: Dict) -> str:
    lines = ["═" * 58, "حصاد التشغيل", "═" * 58, ""]
    lines.append(f"  قرارات مسجَّلة : {pkg['decisions']}")
    lines.append(f"  من {pkg['first']} إلى {pkg['last']}")
    lines.append(f"  شارتات        : {pkg['charts']}")
    lines.append(f"  أخطاء         : {pkg['errors']}")
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

    lines += ["", "أرسل لي هذا الملخّص + ملفّ decisions.jsonl."]
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
    print("⛔ وضع الورق — لا أوامر تُرسل. تسجيل فقط.")
    print(f"📁 {os.path.abspath(cfg.out_dir)}")

    if not args.watch:
        n = run_once(bridge, cfg, recorder)
        print(f"✅ سُجّل {n} قرارًا (الإجمالي {recorder.count()})")
        return 0

    import time
    print(f"🔁 كل {args.every} ثانية — أوقفه بـ Ctrl+C")
    try:
        while True:
            try:
                n = run_once(bridge, cfg, recorder)
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
