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
from .mt5_bridge import TIMEFRAME_MINUTES
from .replay import (Bar, Result, Setup, net, setups_from, tally,
                     utf8_console, walk, walk_managed)


# هامشٌ فوق العدد المحسوب — الجسرُ يعيد أقلَّ ممّا يُطلب أحيانًا
CONFIRM_MARGIN = 1.10


def confirm_bars_needed(poi_tf: str, confirm_tf: str, poi_bars: int,
                        margin: float = CONFIRM_MARGIN) -> int:
    """
    كم شمعةَ تأكيدٍ يلزم لتغطية نطاق شموع نقطة الاهتمام كلِّه.

    ⛔⛔ **وعطبٌ كُشف 2026-09-25 — ثلثُ نافذة القياس بلا تأكيدٍ أصلًا.**

    كان الافتراضيّان `--poi-bars 1500` و`--confirm-bars 5000`، وبينهما
    نسبةٌ لا تصحّ:

        1500 شمعة M15  ⇒  17.9 يومَ تداول  (84 شمعة/يوم من سجلٍّ حيّ)
        5000 شمعة M3   ⇒  12.0 يومَ تداول
        ────────────────────────────────────────────────
        الفجوة          ⇒  **6.0 أيّام · 33% من النافذة**

    فـ`_upto(confirm, when)` يُرجع **سلسلةً فارغة** لكلّ لحظةٍ تسبق
    أوّلَ شمعة تأكيد. وأثرُه يختلف بالمسار:

    · `direct_touch_only=True` ⇒ الإعدادُ **يُؤخذ** ولا يُنقَّح — فيبدو
      التنقيحُ فاشلًا وهو **لم يُسأل أصلًا**.
    · ومسارُ النموذج الانعكاسيّ ⇒ `patterns` فارغة ⇒ **رفضٌ دائم**.

    ⚠️ **ولا يفسّر هذا فارقَ العدد** (تسعةٌ حيّةٌ مقابل اثنين متوقَّعين):
    فالمسارُ الحيّ `direct_touch_only=True`، وفيه غيابُ التأكيد **لا
    يمنع إعدادًا**. ⇒ العطبُ حقيقيّ ويُصلَح، والفارقُ سؤالٌ آخر.
    """
    big = TIMEFRAME_MINUTES.get(poi_tf)
    small = TIMEFRAME_MINUTES.get(confirm_tf)
    if not big or not small or small > big:
        return poi_bars
    return int(poi_bars * (big / small) * margin)


def range_gap(poi: Series, since: Optional[datetime],
              until: Optional[datetime] = None) -> Optional[str]:
    """
    تحذيرٌ إن كان النطاقُ المطلوب خارجَ ما جُلب أصلًا — أو `None`.

    ⛔ **وهو العطبُ نفسُه في ثوبٍ ثانٍ** (كُشف 2026-09-25، قبل التشغيل
    لا بعده): `--from 2026-08-26` مع `--poi-bars 1500` وأقدمُ شمعةٍ
    مجلوبةٍ `09-02` ⇒ **سبعةُ أيّامٍ مطلوبةٍ غيرُ موجودةٍ أصلًا**.

    و`decisions()` يتخطّاها بـ`continue` صامتًا، فيخرج الرقمُ باسم
    ثلاثةِ أسابيعَ ونصف وهو أسبوعان وثلث. **فالمدى يُعلَن لا يُفترض.**
    """
    if len(poi) == 0:
        return "[!!] EMPTY POI SERIES."
    out = []
    if since is not None and poi[0].time > since:
        days = (poi[0].time - since).days
        out.append(
            f"[!!] ASKED FROM {since:%Y-%m-%d} BUT OLDEST BAR IS "
            f"{poi[0].time:%Y-%m-%d} - {days} DAYS MISSING.\n"
            f"⛔ {days} يومًا من أوّل النطاق **غيرُ مجلوبةٍ أصلًا** — "
            f"ارفع ‎--poi-bars.")
    if until is not None and poi[-1].time < until:
        out.append(
            f"[!] Newest bar {poi[-1].time:%Y-%m-%d %H:%M} is before "
            f"--to {until:%Y-%m-%d}.")
    return "\n".join(out) if out else None


def higher_gap(poi: Series, higher: Optional[Series],
               name: str) -> Optional[str]:
    """
    تحذيرٌ إن كان الإطارُ الأعلى لا يغطّي نطاقَ نقطة الاهتمام — أو `None`.

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⛔⛔⛔ **BR1 في موضعه الثالث — كُشف 2026-09-30.**             ║
    ╚══════════════════════════════════════════════════════════════╝

    `range_gap` تفحص المطلوبَ مقابل المجلوب، و`coverage_gap` تفحص شموعَ
    التأكيد — **ولم يكن للإطار الأعلى فحصٌ إطلاقًا**. وكلُّ ما يُطبع
    عنه سطرٌ عارٍ: [H1: 60 bars].

    ⭐⭐ **ولمَ هذا بعينه خطير؟** لأنّ `grade` تمرّر
    `_upto(higher, when)`، وهي تُرجع **سلسلةً فارغة** لكلّ لحظةٍ تسبق
    أوّلَ شمعةٍ عليا. و`chain.evaluate` عندها **لا يرفض ولا يفحص**:

        if cfg.require_higher_trend and (higher_series is None
                                         or len(higher_series) < 3):
            r.add("الإطار الأعلى لا يخالف", True, "⚠️ لم يُفحَص …")

    ⇒ **فبوّابتا الإطار الأعلى تمرّان صامتتين** على ذلك الجزء
    (و`higher_poi_required` مثلُها)، **والصفُّ يخرج موسومًا
    [مع سند الإطار الأكبر]** — فيُقارَن صفٌّ بصفٍّ والبوّابةُ لم تعمل
    في كليهما.

    ⚠️ **وهذا يقع فعلًا لا نظريًّا**: MT5 ينزّل التاريخَ **لكلّ إطارٍ
    على حدة وعند الطلب**. فطرفيّةٌ لم يُفتح فيها H4 قطّ تُرجع عشراتِ
    الشموع لا آلافَها — **ولا كلمة**.

    ⚠️⚠️ **والسلسلةُ نفسُها صادقة** (تكتب [⚠️ لم يُفحَص] في الصفّ)،
    **والتقريرُ الجامعُ هو الذي كان يصمت** — فالقارئُ يرى عمودين
    متساويين فيحكم [لا أثرَ للبوّابة]، والحقُّ أنّها **لم تُجرَّب**.
    """
    if higher is None or len(higher) == 0:
        return ("[!!] NO HIGHER BARS AT ALL - the higher-frame gates are "
                "inert for the whole run.\n"
                "⛔ بلا شمعةٍ عليا واحدة — بوّابتا الإطار الأعلى خامدتان "
                "في القياس كلِّه، والصفُّ يخرج كأنّهما عملتا.")
    if len(poi) == 0:
        return None
    if higher[0].time <= poi[0].time:
        return None
    hours = (higher[0].time - poi[0].time).total_seconds() / 3600
    return (f"[!!] {name} DATA STARTS {hours:.0f}h AFTER THE POI RANGE.\n"
            f"     {poi[0].time:%m-%d %H:%M} -> {higher[0].time:%m-%d %H:%M} "
            f"has NO higher-frame bars.\n"
            f"⛔ أوّلُ {hours:.0f} ساعةً من النطاق بلا شمعةٍ عليا — "
            f"فبوّابتا الإطار الأعلى **تمرّان بلا فحص** فيها، والصفُّ "
            f"يخرج موسومًا كأنّهما عملتا. نزّل تاريخَ {name} في "
            f"الطرفيّة (افتح الإطار واسحب إلى أقدم شمعة)، أو قصِّر "
            f"‎--poi-bars.")


def coverage_gap(poi: Series, confirm: Series) -> Optional[str]:
    """تحذيرٌ إن كانت شموعُ التأكيد لا تغطّي نطاق نقطة الاهتمام — أو `None`."""
    if len(poi) == 0 or len(confirm) == 0:
        return "[!!] EMPTY SERIES - nothing to measure."
    if confirm[0].time <= poi[0].time:
        return None
    hours = (confirm[0].time - poi[0].time).total_seconds() / 3600
    return (f"[!!] CONFIRM DATA STARTS {hours:.0f}h AFTER THE POI RANGE.\n"
            f"     {poi[0].time:%m-%d %H:%M} -> {confirm[0].time:%m-%d %H:%M} "
            f"has NO confirmation bars.\n"
            f"⛔ أوّلُ {hours:.0f} ساعةً من النطاق بلا شمعةِ تأكيدٍ واحدة — "
            f"فالتنقيحُ لا يُسأل فيها، ومسارُ النموذج الانعكاسيّ يُرفض "
            f"دائمًا. ارفع ‎--confirm-bars أو قصِّر ‎--poi-bars.")

# كم شمعةً تُعطى للسلسلة في كلّ تقييم — كما في `RunConfig.candles`
WINDOW = 200

# ⭐ النتائجُ التي **لها عمودٌ** في `render`. وما عداها يُسمّى بعدده
#   بدل أن يختفي — انظر ترويسة `render`. [09-28]
SHOWN_OUTCOMES = ("tp1", "stop", "ambiguous", "unfilled", "open")


def _impulse_variants() -> List[Tuple[str, Dict]]:
    """
    صيغتا بوّابة الـ50% — **و[القائم] تُقرأ من الدفتر لا تُكتب بيد.**

    ⛔⛔⛔ **ولماذا دالّةٌ لسطرين؟** لأنّ الوسم كُتب باليد يومًا،
    ثمّ **قُلب البندُ ولم يُقلب الوسم** — فصار الجدولُ يسمّي
    المردودَ قائمًا عشرةَ أيّام. **والمكتوبُ باليد يبيت، والمقروءُ
    من المصدر لا يبيت.**

    ⚠️ **والنصُّ يبقى منسوبًا لدرسه** — فالمصدرُ لا يتغيّر بقلب
    إعداد.
    """
    from .params import IMPULSE_SPAN_RULE

    live = IMPULSE_SPAN_RULE.value
    names = {"last": "آخرُ قاعٍ وقمّة", "governing": "الموجةُ كاملة — درس 18"}
    return [(f"{names[span]}{' — القائم' if span == live else ''}",
             {"impulse_span": span})
            for span in ("last", "governing")]


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
    # ⭐ ويُحفظ **أيُّ مسارٍ سُلك** — فالحصيلة وحدها لا تقول من أين
    #   جاء الوقفُ الواسع، و`refine` هو طريقةُ المدرّب في تصغيره.
    by = {c.name: c for c in r.checks}
    touch = by.get("دخول من مجرد اللمس")
    refine_check = by.get("تنقيح الدخول داخل المنطقة")
    if refine_check is not None:
        path = "منقَّح" if refine_check.passed else "من حدّ المنطقة"
    elif touch is not None and touch.passed:
        path = "لمسٌ بلا تنقيح"
    else:
        path = "نموذج انعكاسيّ"

    return {
        "poi_tf": poi_tf,
        "confirm_tf": confirm_tf,
        "direction": r.direction,
        "entry": r.entry,
        "stop": r.stop,
        "targets": list(r.targets),
        "candle_time": when.isoformat(),
        "disposition": "taken",
        "path": path,
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
    higher: Optional[Series] = None,
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
            # ⚠️ والإطارُ الأعلى مقطوعٌ عند اللحظة نفسِها — وإلّا قرأ
            #    القياسُ مستقبلًا من إطارٍ آخر، وهو أخفى من الأوّل.
            higher_series=None if higher is None else _upto(higher, when),
        )
        row = _row(result, poi_tf, confirm_tf, when)
        if row is not None:
            out.append(row)
    return out


def grade(rows: Sequence[Dict], bars: Sequence[Bar], walker=walk) -> List[Result]:
    return [walker(bars, s) for s in setups_from(rows)]


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
    higher: Optional[Series] = None,
    graders: Optional[Sequence[Tuple[str, object]]] = None,
) -> List[Tuple[str, List[Result], List[Dict]]]:
    """
    يشغّل كلّ صيغةٍ على المسار نفسه ويرجع نتائجها بأسمائها.

    ⚠️ **ويُرجع الصفوف معها** — وكان `--why` يمشي على الشموع مرّةً
    ثالثة ليحصل عليها، فيضاعف الانتظار بلا سبب.

    ⭐ **و`graders` بابٌ ثانٍ للمقارنة** (MG1 · 09-28): كلُّ ما سبق
    يقارن **قراراتٍ مختلفة** بمسطرةٍ واحدة. وبعضُ البنود عكسُ ذلك —
    سلّمُ نقل الوقف لا يغيّر قرارًا واحدًا، **يغيّر كيف تُقاس
    النتيجة**. فتُشتقّ القراراتُ مرّةً وتُقاس بمسطرتين.
    """
    bars = _bars(poi)
    out = []
    for name, overrides in variants:
        rows = decisions(poi, confirm, poi_tf, confirm_tf, spread,
                         since, until, window, higher, **overrides)
        if graders:
            for gname, walker in graders:
                label = gname if len(variants) == 1 else f"{name} · {gname}"
                out.append((label, grade(rows, bars, walker), rows))
        else:
            out.append((name, grade(rows, bars), rows))
    return out


def detail(runs: Sequence[Tuple[str, List[Result]]]) -> str:
    """
    كلُّ صفقةٍ بيومها واتّجاهها ونتيجتها.

    ⭐ **ولماذا يلزم؟** لأنّ الحصيلة وحدها تقول «خسر الأسبوع» ولا تقول
    **أيُّ يومٍ خسر ولا في أيّ اتّجاه**. وبلا ذلك لا تُقارَن قرارات
    البوت بأحكام المدرّب المسجَّلة — وهي الحَكَم الوحيد الخارجيّ عندنا.
    """
    out: List[str] = []
    for name, results, _rows in runs:
        out.append(f"\n── {name} ──")
        out.append(f"{'اليوم':12}{'وقت':>7}  {'ط':>4} {'اتج':>5} "
                   f"{'دخول':>9} {'مخاطرة':>8} {'النتيجة':>10} {'الحصيلة':>9}")
        out.append("─" * 72)
        for r in results:
            s = r.setup
            when = s.first_seen[:16].replace("T", "  ")
            out.append(f"{when:19} {s.timeframe:>4} {s.direction:>5} "
                       f"{s.entry:>9.2f} {s.risk:>8.2f} {r.outcome:>10} "
                       f"{r.pnl:>+8.2f}$")
        if not results:
            out.append("  (لا إعدادات)")
    return "\n".join(out)


def diagnose(bars: Sequence[Bar], results: Sequence[Result],
             horizon: int = 96) -> str:
    """
    ⭐⭐⭐ **لماذا ضُربت الخاسرات؟** — واحتمالان لا ثالث:

      • بلغ السعرُ الهدفَ بعد الوقف  ⇒ **الاتّجاه صحيح والوقف ضيّق**
      • لم يبلغه                     ⇒ **الإعداد خطأ، والوقف بريء**

    ولا يُخمَّن الفرق: يُمشى على الشموع **متجاهلًا الوقف** (`survival`)
    فيُعرف أيُّهما وقع، وكم وقفًا كان يلزم.
    """
    from .replay import survival

    lost = [r for r in results if r.outcome in ("stop", "ambiguous")]
    won = [r for r in results if r.outcome.startswith("tp")]

    out = ["", f"── تشريحُ الخاسرات ({len(lost)} من {len(results)}) ──",
           f"{'الوقت':17}{'أُعطي':>8}{'لزمه':>8}  {'بلغ الهدف بعدها؟':>18}"]
    out.append("─" * 56)

    tight = wrong = 0
    extra: List[float] = []
    for r in lost:
        s = survival(bars, r.setup, horizon)
        if s.reached:
            tight += 1
            extra.append(s.needed)
            verdict = f"✅ نعم — بعد {s.bars} شمعة"
        else:
            wrong += 1
            verdict = "❌ لا"
        out.append(f"{r.setup.first_seen[:16].replace('T', '  '):19}"
                   f"{r.setup.risk:>6.2f}$ {s.needed:>6.2f}$  {verdict:>18}")

    n = tight + wrong
    if n:
        out += ["", f"⇒ وقفٌ ضيّق : {tight:2} ({tight/n*100:.0f}%)"
                    f"   · إعدادٌ خطأ: {wrong:2} ({wrong/n*100:.0f}%)"]
    if extra:
        extra.sort()
        out.append(f"  وما كان يلزمها من وقف: وسيط {extra[len(extra)//2]:.2f}$ "
                   f"· أقصى {extra[-1]:.2f}$")
    if won:
        need = sorted(survival(bars, r.setup, horizon).needed for r in won)
        out.append(f"  وما احتاجه الرابحون فعلًا: وسيط "
                   f"{need[len(need)//2]:.2f}$ · أقصى {need[-1]:.2f}$")

    out.append(f"\n⚠️ الأفق {horizon} شمعة بعد الدخول — وبلا سقفٍ يصير "
               f"السؤال «هل يُبلَغ يومًا ما»، وكلُّ سعرٍ يُبلَغ إن انتظرت.")
    return "\n".join(out)


def sweep_stop(bars: Sequence[Bar], setups: Sequence[Setup],
               caps: Sequence[float]) -> str:
    """
    ⭐⭐⭐ **ماذا لو شُدَّ الوقف؟** — على المسار نفسِه، وبلا إعادة قرار.

    والسؤال جاء من `--diagnose`: الخاسرات صحيحةُ الاتّجاه في 91%،
    **والرابحون لم يحتاجوا أكثر من 5.56$ قطّ** بينما وسيطُ ما لزم
    الخاسرين **17.98$**.

    ⇒ فإن كان الرابحُ لا يحتاج أكثر من ستّة، فوقفٌ عندها يُبقيه
    **ويقطع الخاسر مبكّرًا** بدل أن يمتصّ ضِعفَها. وهو عكسُ ما يبدو
    بديهيًّا، ويوافق نهيَه: «**24$ كارثي**» · «خلّي ستوبك معقول».

    ⚠️ **والشدُّ هنا لا يطرح إعدادًا** — يقرّب وقفَه فقط
    (`walk(max_stop=…)`). فالفرقُ بينهما جوهريّ: الطرحُ يفقدك الصفقة،
    والشدُّ يُبقيها بمخاطرةٍ أقلّ.
    """
    out = ["", "── مسحُ سقف الوقف ──",
           f"{'السقف':>8} {'إعداد':>6} {'هدف':>5} {'وقف':>5} {'ملتبس':>6} "
           f"{'الحصيلة':>10}"]
    out.append("─" * 48)
    for cap in caps:
        res = [walk(bars, s, cap) for s in setups]
        t = tally(res)
        label = "بلا سقف" if cap is None else f"{cap:g}$"
        out.append(f"{label:>8} {len(res):6} {t.get('tp1', 0):5} "
                   f"{t.get('stop', 0):5} {t.get('ambiguous', 0):6} "
                   f"{net(res):+9.2f}$")
    out.append("\n⚠️ الشدُّ يقرّب الوقف ولا يطرح الإعداد — والمسار واحدٌ "
               "في كلّ السطور.")
    return "\n".join(out)


def by_path(bars: Sequence[Bar], rows: Sequence[Dict]) -> str:
    """
    ⭐⭐⭐ **من أين جاء الوقفُ الواسع؟**

    والسؤال جاء من مسح السقف: وقفٌ عند 6$ يقلب الأسبوع، **وطريقةُ
    المدرّب في تصغير الوقف ليست مقصًّا بل موضعَ الدخول**:

        [بلا ترابط فريمات 110 نقطة · على الساعة 590 · بترابط
         الفريمات **10 نقاط**]
        «الستوب قاع الأوردر بلوك — **ولكن أنا بدون تأكيد ما بنصح**»

    ⇒ فإن كانت الصفقاتُ واسعةُ الوقف هي التي **فشل فيها التنقيح**،
    فالعلاجُ طريقتُه لا مقصّي. وهذا ما يقيسه هذا الجدول.
    """
    import statistics

    groups: Dict[str, List[Dict]] = {}
    for row in rows:
        groups.setdefault(row.get("path", "؟"), []).append(row)

    out = ["", "── من أين جاء الوقف؟ ──",
           f"{'المسار':18}{'عدد':>5}{'وسيط الوقف':>12}{'أقصاه':>9}"
           f"{'الحصيلة':>11}"]
    out.append("─" * 56)
    for name, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        risks = [abs(r["entry"] - r["stop"]) for r in rs]
        res = [walk(bars, s) for s in setups_from(rs)]
        out.append(f"{name:18}{len(rs):5}{statistics.median(risks):>11.2f}$"
                   f"{max(risks):>8.2f}${net(res):>+10.2f}$")

    out.append("\n⚠️ العددُ هنا **قرارات** لا إعدادات متمايزة — فالإعداد "
               "الواحد يُعلَن مرّاتٍ ما دام قائمًا.")
    return "\n".join(out)


def render(runs: Sequence[Tuple[str, List[Result]]]) -> str:
    """
    جدولُ المقارنة — **والصيغةُ الأولى هي الأساس** الذي يُقاس عليه.

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⛔⛔ **وعطبان فيه صُحّحا 2026-09-27** — وكلاهما يضلّل القارئ    ║
    ║  في أداةٍ **تخرج منها كلُّ نتيجةٍ في هذا المشروع**.             ║
    ║                                                              ║
    ║  ① **سطرُ الفرق كان `if len(runs) == 2` فقط.** و`refine`       ║
    ║    أربعُ صيغ و`refine-pick` **ثلاث** ⇒ فتُطبع الأرقامُ **بلا**  ║
    ║    **سطرِ فرقٍ ولا حكمِ «لا أثر»**، ويُترك القارئُ يحسب الفروقَ  ║
    ║    بعينه — وهو موضعُ الخطأ بعينه.                             ║
    ║                                                              ║
    ║  ② **و`Outcome` خمسُ قيم والجدولُ يُظهر ثلاثًا**: `unfilled`    ║
    ║    و`open` **غيرُ مرئيَّين**، فلا تجمع الأعمدةُ عددَ الإعدادات    ║
    ║    ولا يعرف القارئُ لماذا. و«لم تُملأ» **واقعةٌ في السجلّ**      ║
    ║    (أسبوع 09-21: تسعُ صفقاتٍ إحداها لم تُملأ).                 ║
    ║                                                              ║
    ║  ⭐ **وصار العطبُ ② محروسًا بالحساب لا بقائمةِ أعمدة** —        ║
    ║  09-28. فـ`walk_managed` يُخرج `tp2` و`tp2·open` ولا عمودَ     ║
    ║  لهما ⇒ كانت **ستختفي بالصمت نفسِه**. ⇒ يُطرح المعروضُ من       ║
    ║  العدد، وما بقي **يُسمّى بعدده**.                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    lines = [
        f"{'الصيغة':28} {'إعداد':>6} {'هدف':>5} {'وقف':>5} {'ملتبس':>6} "
        f"{'لم تُملأ':>8} {'معلَّق':>6} {'الحصيلة':>10}",
        "─" * 86,
    ]
    stray: List[str] = []
    for name, results, _rows in runs:
        t = tally(results)
        rest = {k: v for k, v in sorted(t.items()) if k not in SHOWN_OUTCOMES}
        if rest:
            stray.append(f"  {name:26} "
                         + " · ".join(f"{k} {v}" for k, v in rest.items()))
        lines.append(
            f"{name:28} {len(results):6} {t.get('tp1', 0):5} "
            f"{t.get('stop', 0):5} {t.get('ambiguous', 0):6} "
            f"{t.get('unfilled', 0):8} {t.get('open', 0):6} "
            f"{net(results):+9.2f}$" + ("  ⚠️" if rest else "")
        )

    if stray:
        lines += ["", "⚠️ **ونتائجُ لا عمودَ لها — فالأعمدةُ أعلاه لا تجمع "
                      "عددَ الإعدادات:**"] + stray

    # ⭐ والفروقُ تُقاس على **الأولى** — وهي «القائم» في كلّ الصيغ.
    if len(runs) >= 2:
        base_name, base, _ = runs[0]
        lines += ["", f"والفروقُ مقيسةٌ على «{base_name}»:"]
        for name, results, _rows in runs[1:]:
            d = net(results) - net(base)
            dn = len(results) - len(base)
            flat = abs(d) < 1e-9 and dn == 0
            lines.append(
                f"  {name:26} {d:+9.2f}$ · إعدادات {dn:+d}"
                + ("   ⇒ **لا أثر** — لم تغيّر قرارًا واحدًا" if flat else "")
            )
        best = max(runs, key=lambda r: net(r[1]))
        if abs(net(best[1]) - net(base)) > 1e-9:
            lines.append(f"  ⇒ الأعلى حصيلةً: **{best[0]}**")

    # ⛔⛔ **RW2** — «وقتٌ لا يُقرأ» عطبُ بياناتٍ لا حكمُ سوق، فيصيح.
    broken = sum(tally(r[1]).get("unreadable", 0) for r in runs)
    if broken:
        lines += ["", f"⛔⛔ **{broken} صفًّا وقتُه غيرُ مقروء** — عطبُ "
                      f"بياناتٍ لا حكمُ سوق. **والنتيجةُ أدناه ناقصةٌ "
                      f"بمقدارها**، فافحص السجلّ قبل أن تقرأها."]

    lines += ["", "⚠️ دقّة الشمعة · الملتبس يُحسب خسارة · والعيّنة تكشف "
                  "عطبًا ولا تثبّت عتبة."]
    lines.append("⚠️ **واقرأ عددَ الإعدادات مع الحصيلة**: حصيلةٌ أعلى "
                 "بإعداداتٍ أكثر قد تكون ضجيجًا رابحًا بالحظّ.")
    return "\n".join(lines)


def _day(text: str) -> datetime:
    return datetime.combine(date.fromisoformat(text), datetime.min.time())


def main(argv: Optional[Sequence[str]] = None) -> int:
    utf8_console()           # ⛔ قبل أوّل `print` — انظر `replay.utf8_console`
    ap = argparse.ArgumentParser(
        description="قياس أثر قاعدةٍ على تاريخٍ حقيقيّ — لا أوامر تُرسل")
    ap.add_argument("--poi", default="M15")
    ap.add_argument("--confirm", default="M3")
    ap.add_argument("--higher", default="H1",
                    help="الإطار الأعلى الذي يُطلب منه السند")
    ap.add_argument("--rule", default="harmonic",
                    choices=("harmonic", "higher-poi", "higher-trend",
                             "refine", "refine-floor", "refine-pick", "impulse",
                             "protected", "trail",
                             "path", "swings"),
                    help="أيّ قاعدةٍ تُقاس؟")
    ap.add_argument("--from", dest="since", help="YYYY-MM-DD")
    ap.add_argument("--to", dest="until", help="YYYY-MM-DD (شاملًا)")
    ap.add_argument("--poi-bars", type=int, default=1500)
    # ⛔ صفرٌ = احسبه من نطاق نقطة الاهتمام. والرقمُ المكتوب هو الذي
    #    ترك ثلثَ النافذة بلا تأكيد — فلا يُكتب رقمٌ بعده.
    ap.add_argument("--confirm-bars", type=int, default=0,
                    help="0 = يُحسب من ‎--poi-bars ونسبة الإطارين")
    ap.add_argument("--spread", type=float, default=0.30)
    ap.add_argument("--detail", action="store_true",
                    help="اطبع كلّ صفقة بيومها واتّجاهها ونتيجتها")
    ap.add_argument("--diagnose", action="store_true",
                    help="لماذا ضُربت الخاسرات — وقفٌ ضيّق أم إعدادٌ خطأ؟")
    ap.add_argument("--why", action="store_true",
                    help="من أين جاء الوقف — تنقيحٌ أم حدُّ المنطقة؟")
    ap.add_argument("--sweep-stop", action="store_true",
                    help="جرّب سقوفَ وقفٍ مختلفة على المسار نفسه")
    ap.add_argument("--horizon", type=int, default=96,
                    help="كم شمعةً بعد الدخول يُنتظَر الهدف (افتراضيًّا يومٌ كامل)")
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

    want = args.confirm_bars or confirm_bars_needed(
        args.poi, args.confirm, args.poi_bars)
    poi = bridge.fetch(args.poi, args.poi_bars)
    confirm = bridge.fetch(args.confirm, want)
    # ⚠️ و[asked] يُطبع على الثلاثة جميعًا — فنقصٌ بلا ‎--from لا
    #    يلتقطه `range_gap`، ويبقى العددُ العاري لا يقول بمَ يُقارَن.
    print(f"{args.poi}: {len(poi)} bars (asked {args.poi_bars})  "
          f"{poi[0].time:%m-%d %H:%M} -> {poi[-1].time:%m-%d %H:%M}")
    print(f"{args.confirm}: {len(confirm)} bars (asked {want})  "
          f"{confirm[0].time:%m-%d %H:%M} -> {confirm[-1].time:%m-%d %H:%M}")

    # ⛔ والفجوةُ تُصاح لا تُخمَّن — انظر `confirm_bars_needed`.
    gap = coverage_gap(poi, confirm)
    if gap:
        print(gap)

    since = _day(args.since) if args.since else None
    _until_warn = _day(args.until) if args.until else None
    miss = range_gap(poi, since, _until_warn)
    if miss:
        print(miss)
    until = _day(args.until).replace(hour=23, minute=59) if args.until else None

    higher = None
    # ⛔⛔ **يُجلَب الإطارُ الأعلى متى طُلب — أيًّا كانت القاعدة.**
    #
    # وكان الشرطُ هنا `args.rule in ("higher-poi", "higher-trend")`،
    # فيُتجاهَل `--higher` صامتًا مع `path` و`refine`. وبوّابتا H1
    # **مشغَّلتان افتراضيًّا** الآن، فتشغيلٌ بلا الإطار الأعلى يقيس
    # إعدادًا **غير الإعداد الحيّ** — ويبدو صحيحًا.
    #
    # ⚠️ وحين لا يُعطى، يُقال ذلك بصوتٍ عالٍ لا صامتًا: رقمٌ بلا
    #    شرطِه يُقرأ خطأً بعد يوم.
    if args.higher and args.higher.lower() not in ("", "none", "-"):
        higher = bridge.fetch(args.higher, args.poi_bars)
        print(f"{args.higher}: {len(higher)} bars (asked {args.poi_bars})")
        # ⛔⛔⛔ BR1 · الموضعُ الثالث — انظر ترويسة `higher_gap`.
        hgap = higher_gap(poi, higher, args.higher)
        if hgap:
            print(hgap)
    else:
        print("[!] NO HIGHER FRAME - the two H1 gates are NOT active.")
        print("⚠️ بلا إطارٍ أعلى — بوّابتا H1 معطَّلتان في هذا القياس.")
    graders = None
    if args.rule == "trail":
        # ╔══════════════════════════════════════════════════════════╗
        # ║  ⭐⭐⭐ **MG1 — سلّمُ نقل الوقف لم يُقَس قطّ · كُشف 09-28.**  ║
        # ║                                                          ║
        # ║  `walk_managed` مبنيّةٌ ومختبَرةٌ **ولا يستدعيها شيء**.     ║
        # ║  فكلُّ رقمٍ في هذا المشروع خرج من `walk` — أي **وقفٌ       ║
        # ║  ثابتٌ لا يتحرّك**. وترويسةُ `walk_managed` نفسُها تقول     ║
        # ║  إنّ الفرقَ بينهما [كلفةُ التأمين أو عائدُه، بالدولار] —    ║
        # ║  وهو فرقٌ **لم يُحسَب مرّةً واحدة**.                       ║
        # ║                                                          ║
        # ║  ⚠️ **وهذا يقيس المسطرةَ لا القرار**: القراراتُ واحدةٌ     ║
        # ║  في الصفّين، فـ[إعداد] لا يتغيّر. والمتغيّرُ الحصيلةُ       ║
        # ║  وحدَها.                                                  ║
        # ║                                                          ║
        # ║  ⚠️⚠️ **واقرأ سطرَ [نتائجُ لا عمودَ لها]**: الوقفُ المنقول  ║
        # ║  يُخرج `tp2` و`tp2·open` ولا عمودَ لهما. وهي **ليست       ║
        # ║  خسائر** — بل خروجٌ عند وقفٍ فوق الدخول.                  ║
        # ╚══════════════════════════════════════════════════════════╝
        variants = [("القائم", {})]
        graders = [("وقفٌ ثابت — القائم", walk),
                   ("وقفٌ منقول — سلّم trail.py", walk_managed)]
    elif args.rule == "higher-poi":
        variants = [("بلا سند الإطار الأكبر", {"higher_poi_required": False}),
                    ("مع سند الإطار الأكبر", {"higher_poi_required": True})]
    elif args.rule == "higher-trend":
        variants = [("بلا موافقة الاتّجاه", {"require_higher_trend": False}),
                    ("مع موافقة الاتّجاه", {"require_higher_trend": True})]
    elif args.rule == "path":
        # ⭐⭐⭐ النزيفُ في فرعٍ واحد — فماذا لو أُغلق؟
        variants = [("كلا المسارين", {"direct_touch_only": False}),
                    ("اللمس المباشر وحده", {"direct_touch_only": True})]
    elif args.rule == "refine":
        # ⭐⭐⭐ **الفرضيّة**: التنقيح لم يشتغل ولا مرّةً في 3.5 أسابيع،
        #    لأنّه يشترط وقوعَ طرف النموذج **داخل** المنطقة — والنموذج
        #    الانعكاسيّ عند منطقةٍ يكاد يكون دائمًا **ساحبًا سيولةً
        #    تحتها**، فطرفُه أسفلها لا داخلها.
        variants = [(f"سماحية {t:g}$", {"refine_tolerance": t})
                    for t in (0.0, 1.0, 2.0, 3.0)]
    elif args.rule == "swings":
        # ⭐⭐⭐ **SW1 — «إيكوال هاي» بشمعتين متجاورتين لا يراه البوت.**
        #
        #   المقارنةُ صارمةٌ في الجهتين، فقمّتان متساويتان **متجاورتان**
        #   تُسقطان معًا ⇒ المستوى غيرُ موجود ⇒ **لا كسحَ يُكشَف** ⇒
        #   **ولا أوردر بلوك يُولَد منه**. (مقيسٌ في `test_primitives`.)
        #
        #   والمدرّب يسمّيه «منطقة سيولة مستهدفة — إيكوال هاي».
        #
        # ⚠️ **وهذا التشغيلُ يزيد السوينجات، فيزيد الكسحَ، فيزيد
        #    الإعدادات.** فيُقرأ **عددُ الإعدادات** مع الحصيلة: زيادةٌ
        #    في العدد بحصيلةٍ أسوأ تعني ضجيجًا لا سيولة.
        variants = [("صارمٌ في الجهتين — القائم", {"swing_plateau": "strict"}),
                    ("أوّلُ الهضبة يُسجَّل", {"swing_plateau": "first"})]
    elif args.rule == "protected":
        # ⭐⭐ **PT1 — «المحميّة ليست هدفًا»: قاعدةٌ منصوصةٌ لا تعمل.**
        #
        #   `mark_protected` مبنيّةٌ ومختبَرةٌ ولا يستدعيها شيء، فـ
        #   `protected` يبقى `False` دائمًا.
        #
        # ⚠️ **ويُقرأ «لا هدف صالح» أوّلًا**: هذه القاعدةُ **تحذف**
        #    أهدافًا، فقد تُسقط إعداداتٍ كاملةً عند سقف 1:3 — وهو
        #    السقفُ الذي كان يحذف المنقَّح صامتًا. فنقصانُ الإعدادات
        #    هنا **متوقَّع**، والسؤالُ: أتتحسّن الحصيلةُ بما يكفي؟
        variants = [("المحميّةُ هدفٌ — القائم", {"protected_not_target": False}),
                    ("المحميّةُ ليست هدفًا", {"protected_not_target": True})]
    elif args.rule == "impulse":
        # ⭐⭐⭐ **IM1 — وهو الوحيدُ من الثلاثة الذي يخالف نصًّا نملكه.**
        #
        #   بوّابةُ الـ50% (الخطوةُ ④، ورفضُها يُسقط الشمعة) تُقاس على
        #   **آخرِ** قاعٍ وقمّة — أي تذبذبًا داخليًّا. وقِيس: موجةٌ من 95
        #   إلى 112 أعطت منتصفًا **109.0** بدل **103.5**.
        #   والنصّ: «التصحيح تبع هي الموجة، **من هي الموجة كاملة**».
        #
        # ⚠️ **ويُقرأ عددُ الإعدادات أوّلًا**: المنتصفُ الأصحُّ **أدنى**
        #    في الصاعد، فالبوّابةُ تصير **أصرمَ** ⇒ إعداداتٌ أقلّ.
        #    فحصيلةٌ أفضل بعددٍ أقلّ = البوّابةُ كانت تمرّر غاليًا.
        # ╔══════════════════════════════════════════════════════════╗
        # ║  ⛔⛔⛔ **وسمٌ بائتٌ كذَب على القارئ — صُحّح 2026-10-11.**   ║
        # ║                                                          ║
        # ║  كان مكتوبًا هنا حرفيًّا:                                  ║
        # ║      ("آخرُ قاعٍ وقمّة — **القائم**", …"last")             ║
        # ║                                                          ║
        # ║  **وقُلب `IMPULSE_SPAN_RULE` إلى `governing` يوم 10-01**  ║
        # ║  ⇒ فصار الوسمُ يسمّي **المردودَ** قائمًا، والعكسَ بالعكس.   ║
        # ║  ⛔ ومقيسٌ: قرأ المستخدمُ الجدولَ يوم 10-11 **فكاد**       ║
        # ║  يُقلب الحكمُ مقلوبًا — ولولا فحصُ القيمة الحيّة لمرّ.       ║
        # ║                                                          ║
        # ║  ⇒ **والعلاجُ ألّا يُكتب [القائم] باليد أصلًا**: يُقرأ     ║
        # ║  من الدفتر، فلا يمكن أن يبيت. وحُرس باختبار.              ║
        # ║                                                          ║
        # ║  ⭐ وهو صنفُ المشروع المسجَّل: [بندٌ معلَنٌ لا يطابق         ║
        # ║  الكود] — وموضعُه هنا **في أداة القياس نفسِها**، كـRW1.    ║
        # ╚══════════════════════════════════════════════════════════╝
        variants = _impulse_variants()
    elif args.rule == "refine-pick":
        # ⭐⭐⭐ **RP1 — قاعدةُ الاختيار، وهي المتّهمُ الأوّل في
        #    «لماذا يخسر المنقَّح؟».**
        #
        #    فالقياسُ أعطى المنقَّحَ **صفرًا من خمس** بأوقافٍ في نطاق
        #    المدرّب بعينه (4.39…5.76$) ⇒ فحجمُ الوقف ليس العلّة.
        #    واختيارُ **الأصغر دائمًا** يعني اختيارَ الأقربِ إلى الكسح.
        #
        # ⚠️ **ويُقرأ عددُ الإعدادات مع الحصيلة**: الأوضاعُ الثلاثة
        #    تختار من **المجموعة نفسِها**، فعددُ الإعدادات يكاد لا
        #    يتغيّر — والمتغيّرُ هو **موضعُ الوقف**. فإن تغيّر العددُ
        #    كثيرًا فذلك نفسُه خبرٌ يستحقّ نظرًا.
        variants = [("أصغرُ مخاطرة — القائم", {"refine_pick": "smallest"}),
                    ("أعمقُ طرفٍ في المنطقة", {"refine_pick": "deepest"}),
                    ("الأحدثُ زمنًا", {"refine_pick": "latest"})]
    elif args.rule == "refine-floor":
        # ⭐⭐ **تناقضٌ داخليّ لا رقمٌ جديد** (2026-09-26):
        #    الوقفُ المقبول أصلًا هو `قاع المنطقة − الهامش`، ومع ذلك
        #    يُختبر الاحتواءُ عند القاع وحده — فيُردّ نموذجٌ قاعُه
        #    **بين الحدّين**، وهو داخل مخاطرةٍ قَبِلها البوت بالفعل.
        #
        #    ⛔ ولا يوسّع وقفًا: حارسُ `risk >= zone_risk` قائم. فأثرُه
        #    إمّا وقفٌ أضيق وإمّا لا شيء — **والأضيق يُضرب أكثر، وذلك
        #    ما يقيسه هذا التشغيل.**
        variants = [("قاعُ المنطقة — القائم", {"refine_floor_to_stop": False}),
                    ("ممتدٌّ إلى الوقف", {"refine_floor_to_stop": True})]
    else:
        variants = [("بلا هارمونيك", {"harmonic_enabled": False}),
                    ("مع الهارمونيك", {"harmonic_enabled": True})]

    runs = compare(
        poi, confirm, args.poi, args.confirm, args.spread,
        variants=variants, since=since, until=until, higher=higher,
        graders=graders,
    )
    print()
    print(render(runs))
    if args.detail:
        print(detail(runs))
    if args.diagnose:
        bars = _bars(poi)
        for name, results, _rows in runs:
            print(f"\n════ {name} ════")
            print(diagnose(bars, results, args.horizon))
    if args.why:
        bars = _bars(poi)
        name, _res, rows = runs[-1]       # ⭐ من المحسوب، لا بمشيةٍ ثالثة
        print(f"\n════ {name} ════")
        print(by_path(bars, rows))
    if args.sweep_stop:
        bars = _bars(poi)
        name, results, _rows = runs[-1]   # الصيغةُ العاملة
        print(f"\n════ {name} ════")
        print(sweep_stop(bars, [r.setup for r in results],
                         (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0, None)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
