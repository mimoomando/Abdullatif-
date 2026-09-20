"""
إعادة تشغيل السلسلة على تاريخٍ حقيقيّ — لقياس أثر قاعدةٍ قبل إبقائها.

╔══════════════════════════════════════════════════════════════════╗
║  ولماذا لا يكفي `replay.py`؟                                      ║
║                                                                  ║
║  `replay` يقرأ السجلّ فيصحّح **نتيجة** قراراتٍ اتُّخذت — ولا يعيد   ║
║  اتّخاذها. فإن تغيّرت قاعدةٌ في `chain.py` لم يُظهر أثرها.        ║
║                                                                  ║
║  وأسوأ من ذلك: السجلّ يحمل **شمعةً واحدة من إطار التأكيد لكلّ      ║
║  قرار** — أي 8.6% من شموع M3 في أسبوع 09-14. وقاعدةٌ تعمل على     ║
║  إطار التأكيد (كالهارمونيك) لا تُقاس على تسعة أعشارِ فراغ.         ║
╚══════════════════════════════════════════════════════════════════╝

⇒ فهذا يجلب التاريخ **من المنصّة** — الإطارين كاملين — ويمشي شمعةً
شمعةً، يستدعي `evaluate` عند كلّ إغلاق كما يفعل البوت الحيّ، ثم
يصحّح النتائج بـ`replay.walk` نفسِه.

**ويشغَّل مرّتين**: بالقاعدة وبدونها، ويُعرض الرقمان جنبًا إلى جنب.

⛔ **ولا يُرسل أمرٌ ولا يُفتح مركز.** يُقرأ تاريخٌ ويُحسَب.

⚠️ **وحدودُه حدودُ `replay`**: دقّةُ الشمعة، والملتبس يُحسب خسارة،
والعيّنة الصغيرة تكشف عطبًا ولا تثبّت عتبة.
"""

from __future__ import annotations

import argparse
from dataclasses import replace as _replace
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

from .chain import ChainConfig, evaluate
from .data import Series
from .replay import Bar, Result, Setup, net, setups_from, tally, walk

# كم شمعةً تُعطى للسلسلة في كلّ تقييم — كما في `RunConfig.candles`
WINDOW = 200


def _bars(series: Series) -> List[Bar]:
    return [Bar(c.time, c.open, c.high, c.low, c.close) for c in series]


def _upto(series: Series, when: datetime) -> Series:
    """شموعُ الإطار المقابل حتى هذه اللحظة — لا بعدها."""
    n = 0
    for c in series:
        if c.time > when:
            break
        n += 1
    return series[:n]


def _row(result, poi_tf: str, confirm_tf: str, when: datetime) -> Optional[Dict]:
    """صفٌّ بشكل سطر السجلّ — ليقرأه `setups_from` بلا تحويل."""
    r = result.rationale
    if result.disposition != "taken" or r.entry is None or not r.targets:
        return None
    return {
        "poi_tf": poi_tf,
        "confirm_tf": confirm_tf,
        "direction": r.direction,
        "entry": r.entry,
        "stop": r.stop,
        "targets": list(r.targets),
        "candle_time": when.isoformat(),
        "disposition": "taken",
    }


def decisions(
    poi: Series,
    confirm: Series,
    poi_tf: str,
    confirm_tf: str,
    spread: float,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    window: int = WINDOW,
    **overrides,
) -> List[Dict]:
    """
    يمشي على شموع الإطار الأكبر ويستدعي السلسلة عند كلّ إغلاق.

    ⚠️ **ولا تُعطى السلسلة شمعةً لم تُغلق بعد**: عند الفهرس `i`
    تُعطى `poi[:i+1]` وشموعَ التأكيد حتى وقت إغلاقها. وهذا هو الفرق
    بين قياسٍ وبين قراءةِ المستقبل.
    """
    out: List[Dict] = []
    for i in range(len(poi)):
        when = poi[i].time
        if since is not None and when < since:
            continue
        if until is not None and when > until:
            break
        lo = max(0, i + 1 - window)
        result = evaluate(
            poi[lo:i + 1],
            _upto(confirm, when),
            ChainConfig(poi_timeframe=poi_tf, confirm_timeframe=confirm_tf,
                        spread=spread, **overrides),
        )
        row = _row(result, poi_tf, confirm_tf, when)
        if row is not None:
            out.append(row)
    return out


def grade(rows: Sequence[Dict], bars: Sequence[Bar]) -> List[Result]:
    return [walk(bars, s) for s in setups_from(rows)]


def compare(
    poi: Series,
    confirm: Series,
    poi_tf: str,
    confirm_tf: str,
    spread: float,
    variants: Sequence[Tuple[str, Dict]],
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    window: int = WINDOW,
) -> List[Tuple[str, List[Result]]]:
    """يشغّل كلّ صيغةٍ على المسار نفسه ويرجع نتائجها بأسمائها."""
    bars = _bars(poi)
    out = []
    for name, overrides in variants:
        rows = decisions(poi, confirm, poi_tf, confirm_tf, spread,
                         since, until, window, **overrides)
        out.append((name, grade(rows, bars)))
    return out


def render(runs: Sequence[Tuple[str, List[Result]]]) -> str:
    lines = [
        f"{'الصيغة':28} {'إعداد':>6} {'هدف':>5} {'وقف':>5} {'ملتبس':>6} {'الحصيلة':>10}",
        "─" * 68,
    ]
    for name, results in runs:
        t = tally(results)
        lines.append(
            f"{name:28} {len(results):6} {t.get('tp1', 0):5} {t.get('stop', 0):5} "
            f"{t.get('ambiguous', 0):6} {net(results):+9.2f}$"
        )

    if len(runs) == 2:
        (an, ar), (bn, br) = runs
        d = net(br) - net(ar)
        lines += ["", f"الفرق ({bn} − {an}): {d:+.2f}$ · "
                      f"وإعدادات {len(br) - len(ar):+d}"]
        if abs(d) < 1e-9 and len(ar) == len(br):
            lines.append("⇒ **لا أثر** — القاعدة لم تغيّر قرارًا واحدًا.")

    lines += ["", "⚠️ دقّة الشمعة · الملتبس يُحسب خسارة · والعيّنة تكشف "
                  "عطبًا ولا تثبّت عتبة."]
    return "\n".join(lines)


def _day(text: str) -> datetime:
    return datetime.combine(date.fromisoformat(text), datetime.min.time())


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="قياس أثر قاعدةٍ على تاريخٍ حقيقيّ — لا أوامر تُرسل")
    ap.add_argument("--poi", default="M15")
    ap.add_argument("--confirm", default="M3")
    ap.add_argument("--from", dest="since", help="YYYY-MM-DD")
    ap.add_argument("--to", dest="until", help="YYYY-MM-DD (شاملًا)")
    ap.add_argument("--poi-bars", type=int, default=1500)
    ap.add_argument("--confirm-bars", type=int, default=5000)
    ap.add_argument("--spread", type=float, default=0.30)
    args = ap.parse_args(list(argv) if argv is not None else None)

    from . import local_config as lc
    from .mt5_bridge import BridgeConfig, open_terminal

    try:
        settings = lc.load()
        bridge = open_terminal(
            BridgeConfig(symbol=settings.get("SYMBOL", "XAUUSD.m")),
            **lc.mt5_credentials(settings),
        )
    except Exception as exc:                 # noqa: BLE001
        print("[!!] CANNOT OPEN THE BRIDGE - is MetaTrader 5 running?")
        print(f"❌ تعذّر فتح الجسر: {exc}")
        return 1

    print("BACKTEST - no orders are ever sent. Reading history only.")
    print("⛔ قياسٌ على التاريخ — لا أوامر تُرسل.")

    poi = bridge.fetch(args.poi, args.poi_bars)
    confirm = bridge.fetch(args.confirm, args.confirm_bars)
    print(f"{args.poi}: {len(poi)} bars  {poi[0].time:%m-%d %H:%M} -> "
          f"{poi[-1].time:%m-%d %H:%M}")
    print(f"{args.confirm}: {len(confirm)} bars  {confirm[0].time:%m-%d %H:%M} -> "
          f"{confirm[-1].time:%m-%d %H:%M}")

    since = _day(args.since) if args.since else None
    until = _day(args.until).replace(hour=23, minute=59) if args.until else None

    runs = compare(
        poi, confirm, args.poi, args.confirm, args.spread,
        variants=[("بلا هارمونيك", {"harmonic_enabled": False}),
                  ("مع الهارمونيك", {"harmonic_enabled": True})],
        since=since, until=until,
    )
    print()
    print(render(runs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
