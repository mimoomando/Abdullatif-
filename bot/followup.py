"""
تتبُّعُ الإعداد حتّى نهايته — وتسجيلُ دقائقه.

╔══════════════════════════════════════════════════════════════════╗
║  ⛔⛔⛔ **لماذا وُجدت — ورقمٌ خاطئٌ كاد يمرّ (2026-09-26)**         ║
║                                                                  ║
║  سُئل السجلُّ: «لماذا خسرت الصفقات؟» فأجاب **وقفٌ ضيّق 83%**.      ║
║  ثمّ أُعيد السؤال بآفاقٍ مختلفة:                                  ║
║                                                                  ║
║      أفق  2 ساعة   ⇒  وقفٌ ضيّق 0  ·  إعدادٌ خطأ 6               ║
║      أفق  6 ساعات  ⇒            2  ·             4               ║
║      أفق 24 ساعة   ⇒            5  ·             1               ║
║                                                                  ║
║  **فالجوابُ كان أثرَ اختيارٍ لا واقعًا.**                         ║
║                                                                  ║
║  والعلّةُ في السؤال لا في الأداة: «أبُلغ الهدفُ بعد الوقف؟» بلا    ║
║  مدّةٍ سؤالٌ بلا معنى — وكلُّ سعرٍ يُبلَغ إن انتظرت.               ║
╚══════════════════════════════════════════════════════════════════╝

⭐ **والسؤالُ الصحيح** — اقترحه المستخدم، ومنه بُنيت هذه الوحدة:

    **كم بقي السعرُ خلف الوقف قبل أن يعود؟**

فكسحُ سيولةٍ يعود في دقائق، وحركةٌ تمضي ساعاتٍ ثمّ ترتدّ شيءٌ آخر.
والأوّلُ يعني **موضعَ دخولك خطأ**، والثاني يعني **اتّجاهَك خطأ** —
وعلاجُهما مختلفٌ تمامًا. **وشمعةُ الربع ساعة لا تفرّق بينهما.**

⇒ فتُسجَّل **شمعةُ الدقيقة** حول كلّ إعدادٍ انتهى، ويُقاس الزمنُ
بدل أن يُختار الأفق.

**ويُسجَّل الرابحُ كالخاسر** — فبلا ضابطٍ لا يُقال إنّ الخاسرات
تصرّفت تصرّفًا مختلفًا.

⛔ **ولا تُرسل أمرًا ولا تقرأ مستقبلًا.** تصف ما جرى **بعد** أن جرى،
ولا تُستدعى من `chain.evaluate` ولا تمسّ قرارًا.

⚠️ **وفشلُها لا يوقف البوت.** تكتب في ملفٍّ مستقلّ (`followups.jsonl`)
لا في `decisions.jsonl`، والمناداةُ عليها مغلَّفةٌ عند المستدعي.
فنخسر نافذةَ دقائق ولا نخسر أسبوعَ تسجيل.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

# كم دقيقةً تُسجَّل **بعد** الحسم — وهي موضعُ الدليل كلِّه.
POST_MINUTES = 120

# وكم دقيقةً قبل الدخول، ليُرى الاقترابُ من المنطقة لا الحسمُ وحده.
PRE_MINUTES = 60

# متى يُهجَر إعدادٌ لم يُملأ قطّ؟ (دقائق سوقٍ لا دقائقَ جداريّة)
EXPIRE_MINUTES = 24 * 60

STATE_VERSION = 1


@dataclass(frozen=True)
class Watch:
    """إعدادٌ مُعلَنٌ يُتابَع حتّى ينتهي."""

    key: str
    timeframe: str
    direction: str            # "buy" | "sell"
    entry: float
    stop: float
    targets: Tuple[float, ...]
    announced: str            # ISO
    filled: Optional[str] = None
    resolved: Optional[str] = None
    outcome: Optional[str] = None      # "tp1" | "stop" | "expired"

    @property
    def target(self) -> Optional[float]:
        return self.targets[0] if self.targets else None

    @property
    def done(self) -> bool:
        return self.resolved is not None


def _t(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


# ⛔ **شمعتان باسمين مختلفين** — وهذا كاد يُسقط الوحدة حيًّا:
#
#     bot.data.Candle   ⇒  .high  .low   (ما يعيده الجسر — الحيّ)
#     bot.replay.Bar    ⇒  .h     .l     (ما يُبنى من السجلّ — التحليل)
#
# وهذه الوحدة تقف بينهما، فتقبلهما معًا. والاختبارُ يمرّ على النوعين.
def _hi(bar) -> float:
    return getattr(bar, "h", None) if hasattr(bar, "h") else bar.high


def _lo(bar) -> float:
    return getattr(bar, "l", None) if hasattr(bar, "l") else bar.low


def _op(bar) -> float:
    return getattr(bar, "o", None) if hasattr(bar, "o") else bar.open


def _cl(bar) -> float:
    return getattr(bar, "c", None) if hasattr(bar, "c") else bar.close


def _beyond(direction: str, price: float, level: float) -> bool:
    """أخَلْفَ المستوى في جهة الخسارة؟"""
    return price < level if direction == "buy" else price > level


def _favour(direction: str, price: float, level: float) -> bool:
    """أبلغ المستوى في جهة الربح؟"""
    return price >= level if direction == "buy" else price <= level


def advance(watch: Watch, bars: Sequence) -> Watch:
    """
    يمشي بالإعداد على شموع الدقيقة حتّى يُملأ ثمّ يُحسم.

    ⚠️ **ولا تُقرأ شمعةٌ قبل الإعلان.** فالأمرُ لا يوجد قبل إغلاق
    الشمعة التي قُرّر عليها — واحتسابُ ما قبلها قراءةُ ماضٍ لم يكن
    الإعدادُ فيه قائمًا.

    ⛔ **وعند تعارضٍ في الدقيقة الواحدة يُقدَّم الوقف.** فالتشاؤم
    مقصود: الرقمُ الخارج أسوأ من الواقع لا أفضل منه — وهو عُرفُ
    `replay` نفسُه.
    """
    if watch.done:
        return watch

    started = _t(watch.announced)
    if started is None:
        return watch

    filled = _t(watch.filled)
    out = watch
    for bar in bars:
        if bar.time <= started:
            continue
        hi, lo = _hi(bar), _lo(bar)
        if filled is None:
            if not (lo <= watch.entry <= hi):
                continue
            filled = bar.time
            out = replace(out, filled=bar.time.isoformat())

        buy = watch.direction == "buy"
        hit_stop = (lo <= watch.stop) if buy else (hi >= watch.stop)
        tgt = watch.target
        hit_tgt = tgt is not None and ((hi >= tgt) if buy else (lo <= tgt))

        if hit_stop:
            return replace(out, resolved=bar.time.isoformat(), outcome="stop")
        if hit_tgt:
            return replace(out, resolved=bar.time.isoformat(), outcome="tp1")

    if filled is None and bars:
        age = bars[-1].time - started
        if age >= timedelta(minutes=EXPIRE_MINUTES):
            return replace(out, resolved=bars[-1].time.isoformat(),
                           outcome="expired")
    return out


def measures(watch: Watch, bars: Sequence) -> Dict:
    """
    ⭐⭐⭐ **الأرقامُ التي بُنيت الوحدةُ من أجلها.**

    `minutes_beyond_stop` هو البديلُ عن الأفق المختار: كم دقيقةً بقي
    السعرُ خلف الوقف **قبل أن يعود إليه**. فرقمٌ صغير يقول «كسحُ
    سيولة — موضعُ الدخول خطأ»، ورقمٌ كبير يقول «الاتّجاه خطأ».

    ⚠️ **و`None` تعني «لم يعد ضمن النافذة المسجَّلة»** — لا تعني
    «لم يعد أبدًا». والفرقُ يُذكر مع الرقم ولا يُطوى.
    """
    out: Dict = {
        "minutes_to_fill": None,
        "minutes_to_resolve": None,
        "minutes_beyond_stop": None,
        "minutes_to_target_after_stop": None,
        "max_excursion_beyond_stop": None,
        "post_window_minutes": 0,
    }
    started, filled, resolved = (_t(watch.announced), _t(watch.filled),
                                 _t(watch.resolved))
    if started and filled:
        out["minutes_to_fill"] = round((filled - started).total_seconds() / 60)
    if filled and resolved:
        out["minutes_to_resolve"] = round(
            (resolved - filled).total_seconds() / 60)
    if watch.outcome != "stop" or not resolved:
        return out

    after = [b for b in bars if b.time > resolved]
    if after:
        out["post_window_minutes"] = round(
            (after[-1].time - resolved).total_seconds() / 60)

    buy = watch.direction == "buy"
    worst = 0.0
    for bar in after:
        hi, lo = _hi(bar), _lo(bar)
        far = (watch.stop - lo) if buy else (hi - watch.stop)
        worst = max(worst, far)
        if out["minutes_beyond_stop"] is None and _favour(
                watch.direction, hi if buy else lo, watch.stop):
            out["minutes_beyond_stop"] = round(
                (bar.time - resolved).total_seconds() / 60)
    out["max_excursion_beyond_stop"] = round(worst, 2) if after else None

    tgt = watch.target
    if tgt is not None:
        for bar in after:
            if _favour(watch.direction,
                       _hi(bar) if buy else _lo(bar), tgt):
                out["minutes_to_target_after_stop"] = round(
                    (bar.time - resolved).total_seconds() / 60)
                break
    return out


def window(watch: Watch, bars: Sequence,
           pre: int = PRE_MINUTES, post: int = POST_MINUTES) -> List[Dict]:
    """شموعُ الدقيقة حول الإعداد — من قبل الإعلان إلى ما بعد الحسم."""
    started, resolved = _t(watch.announced), _t(watch.resolved)
    if started is None:
        return []
    lo = started - timedelta(minutes=pre)
    hi = (resolved + timedelta(minutes=post)) if resolved else None
    return [
        {"t": b.time.isoformat(), "o": _op(b), "h": _hi(b),
         "l": _lo(b), "c": _cl(b)}
        for b in bars
        if b.time >= lo and (hi is None or b.time <= hi)
    ]


def ready(watch: Watch, now: datetime, post: int = POST_MINUTES) -> bool:
    """أانقضت نافذةُ ما بعد الحسم فصار السجلّ مكتملًا؟"""
    resolved = _t(watch.resolved)
    return bool(resolved and now >= resolved + timedelta(minutes=post))


@dataclass
class Tracker:
    """
    دفترُ المتابَعة — يعيش عبر إعادات التشغيل.

    ⚠️ **ويُحفظ في ملفٍّ مستقلّ.** فخللٌ هنا لا يمسّ `decisions.jsonl`
    الذي هو مادّةُ كلّ قياس.
    """

    state_path: str
    out_path: str
    watches: Dict[str, Watch] = field(default_factory=dict)

    # ── الحفظ والاسترجاع ──

    def load(self) -> "Tracker":
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            return self
        if raw.get("v") != STATE_VERSION:
            return self
        for w in raw.get("watches", []):
            try:
                w["targets"] = tuple(w.get("targets") or ())
                self.watches[w["key"]] = Watch(**w)
            except TypeError:
                continue
        return self

    def save(self) -> None:
        tmp = self.state_path + ".tmp"
        os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
        payload = {"v": STATE_VERSION,
                   "watches": [asdict(w) for w in self.watches.values()]}
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, self.state_path)

    # ── الاستعمال ──

    def note(self, key: str, timeframe: str, direction: str, entry: float,
             stop: float, targets: Sequence[float], when: str) -> None:
        """يسجّل إعدادًا أُعلن — ولا يكرّره."""
        if key in self.watches:
            return
        self.watches[key] = Watch(
            key=key, timeframe=timeframe, direction=direction, entry=entry,
            stop=stop, targets=tuple(targets or ()), announced=when)

    def tick(self, bars: Sequence, now: datetime) -> List[Dict]:
        """
        يمشي بكلّ متابَعةٍ على الشموع، ويُخرج ما اكتمل سجلُّه.

        ⛔ **ولا يرمي.** فما يُكتب هنا زينةُ تشخيصٍ لا شرطُ تشغيل.
        """
        finished: List[Dict] = []
        for key, w in list(self.watches.items()):
            try:
                moved = advance(w, bars)
                self.watches[key] = moved
                if moved.done and ready(moved, now):
                    finished.append(self._record(moved, bars))
                    del self.watches[key]
            except Exception:            # noqa: BLE001 — لا يوقف البوت
                continue
        return finished

    def _record(self, w: Watch, bars: Sequence) -> Dict:
        return {
            "v": STATE_VERSION,
            **{k: v for k, v in asdict(w).items()},
            "measures": measures(w, bars),
            "m1": window(w, bars),
        }

    def write(self, records: Sequence[Dict]) -> int:
        if not records:
            return 0
        os.makedirs(os.path.dirname(self.out_path) or ".", exist_ok=True)
        with open(self.out_path, "a", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return len(records)
