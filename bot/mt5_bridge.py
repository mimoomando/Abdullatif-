"""
جسر MT5 — قراءة الشموع الحيّة من الطرفية.

هذا ما يحوّل المحرّك من كود يمرّ اختباراته إلى بوت يقرأ الذهب فعلًا.

╔══════════════════════════════════════════════════════════════════╗
║  ⛔ الجسر **يقرأ ولا يأمر**                                       ║
║     لا `order_send` ولا `order_check` ولا أي دالة تنفيذ.          ║
║     المنع في الكود لا في التوثيق — واختبار يثبته.                 ║
╚══════════════════════════════════════════════════════════════════╝

**لماذا فيد الوسيط نفسه؟** التعارض C4، وقد أكّده المدرّب أربع مرات،
آخرها في البثّ المباشر: «على الأربع ساعات في عندي فير… **على غير بروكر**
في هون فين». الفراغ موجود عند وسيط وغائب عند آخر. فالتحليل يقرأ الأرقام
التي سيُنفَّذ عليها، لا أرقام مزوّد آخر.

**ثلاثة مزالق تُفسد التحليل صامتةً — وكلها محروسة هنا:**

  ١. **الشمعة الأخيرة غير مغلقة.** الطرفية تعيد الشمعة قيد التكوّن،
     وكل قواعد المدرّب تقوم على الإغلاق («ما يغلق فوق الـ50%» ·
     «الكسر بالجسم» · «أغلق تحت»). فتُحذف دائمًا.

  ٢. **الحجم tick_volume لا real_volume.** الذهب عقد فرقي بلا حجم
     حقيقي — `real_volume` يعود صفرًا. وهو ما يقرأه المدرّب نفسه
     (وايكوف/د4).

  ٣. **وقت الخادم لا وقتك.** الطرفية تعيد توقيت خادم الوسيط. أي قاعدة
     زمنية («افتتاح 18 نيويورك») تحتاج الإزاحة — وهي **معلَن عنها
     صراحةً** لا مخمَّنة.

⚠️ **لا بيانات اعتماد في المستودع.** المسار ورقم الحساب وكلمة السر
تُقرأ من ملف محلي على جهازك يمنعه `.gitignore`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from .data import Candle, Series

# دقائق كل إطار — لكشف الفجوات وحساب اكتمال الشمعة
TIMEFRAME_MINUTES: Dict[str, int] = {
    "M1": 1, "M3": 3, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440, "W1": 10080,
}

# أسماء ثوابت الطرفية — تُقرأ منها لا تُكتب أرقامًا
TIMEFRAME_CONST: Dict[str, str] = {
    "M1": "TIMEFRAME_M1", "M3": "TIMEFRAME_M3", "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15", "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1",
}

# دوال ممنوعة — أي منها يعني أن الجسر تجاوز دوره
FORBIDDEN_CALLS = (
    "order_send", "order_check", "order_calc_margin", "order_calc_profit",
    "positions_modify", "Buy", "Sell",
)


class BridgeError(RuntimeError):
    """خطأ في الجسر — يُرفع بدل إعادة بيانات ناقصة بصمت."""


class NotConnected(BridgeError):
    pass


# ─────────────────────────── الإعداد ───────────────────────────


@dataclass
class BridgeConfig:
    """
    إعداد الجسر. **لا يحمل كلمة سرّ ولا رقم حساب** — تلك تُمرَّر عند
    الاتصال من ملفك المحلي ولا تُخزَّن هنا ولا تُطبع.
    """

    symbol: str = "XAUUSD.m"
    server_utc_offset_hours: float = 0.0
    """
    إزاحة توقيت خادم الوسيط عن UTC.

    ⚠️ **تُقاس ولا تُخمَّن** — `measure_server_offset()` يقارن ختم آخر
    تكّة بالساعة الحقيقية. الخطأ هنا يزيح كل قاعدة زمنية ساعاتٍ كاملة.
    """

    drop_forming_candle: bool = True
    """الشمعة قيد التكوّن تُحذف. إطفاؤه يفسد كل قاعدة إغلاق."""

    max_gap_bars: int = 1
    """كم شمعة مفقودة تُحتمل قبل الإنذار (RESILIENCE: detect_data_gaps)."""


# ─────────────────────────── صحة البيانات ───────────────────────────


@dataclass(frozen=True)
class DataGap:
    """فجوة في الشموع — انقطاع اتصال أو عطلة سوق."""

    after: datetime
    before: datetime
    missing_bars: int

    def render(self) -> str:
        return (
            f"فجوة {self.missing_bars} شمعة بين "
            f"{self.after:%m-%d %H:%M} و {self.before:%m-%d %H:%M}"
        )


def find_gaps(series: Series, timeframe: str, tolerance: int = 1) -> List[DataGap]:
    """
    يكشف الشموع المفقودة — `RESILIENCE_REQUIREMENTS.detect_data_gaps`.

    ⚠️ عطلة نهاية الأسبوع فجوة مشروعة، فلا يصحّ إنذار أعمى. التمييز
    بينها وبين الانقطاع يحتاج جدول جلسات الوسيط، وهو غير معرَّف بعد —
    فتُرصد الفجوات كلها **ويُترك تفسيرها للعرض** بدل ادّعاء تمييز
    لا نملك بياناته.
    """
    step = TIMEFRAME_MINUTES.get(timeframe)
    if step is None:
        raise BridgeError(f"إطار غير معروف: {timeframe}")
    if tolerance < 1:
        raise BridgeError("السماحية شمعة أو أكثر")

    out: List[DataGap] = []
    candles = list(series)
    for a, b in zip(candles, candles[1:]):
        gap_minutes = (b.time - a.time).total_seconds() / 60.0
        missing = int(round(gap_minutes / step)) - 1
        if missing >= tolerance:
            out.append(DataGap(a.time, b.time, missing))
    return out


# ─────────────────────────── الجسر ───────────────────────────


class MT5Bridge:
    """
    غلاف حول طرفية MT5 — قراءةً فقط.

    `terminal` يُحقَن ليمكن اختباره بلا طرفية: في التشغيل يُمرَّر
    `import MetaTrader5`، وفي الاختبار طرفية زائفة. وهذا ليس ترفًا —
    مكتبة MT5 تعمل على ويندوز فقط، فبلا الحقن يستحيل اختبار الجسر.
    """

    def __init__(self, terminal: Any, config: Optional[BridgeConfig] = None):
        self._t = terminal
        self.config = config or BridgeConfig()
        self._connected = False
        self._reject_execution_surface()

    def _reject_execution_surface(self) -> None:
        """
        الجسر لا يحمل دوال تنفيذ. لا يمنع هذا الطرفية من امتلاكها،
        لكنه يمنع **هذا الكائن** من تمريرها — فلا يصل إليها استدعاء
        عبر الجسر سهوًا.
        """
        for name in FORBIDDEN_CALLS:
            if hasattr(self, name):
                raise BridgeError(f"الجسر لا يملك دالة تنفيذ: {name}")

    # ── الاتصال ──
    def connect(self, **credentials: Any) -> None:
        """
        يفتح الاتصال بالطرفية.

        `credentials` تُمرَّر كما هي إلى `initialize()` وتُنسى فورًا:
        لا تُخزَّن على الكائن ولا تدخل أي رسالة خطأ. وهذا مقصود —
        رسالة خطأ تحمل كلمة سرّ تُسرَّب في السجل وتيليجرام معًا.
        """
        ok = self._t.initialize(**credentials) if credentials else self._t.initialize()
        if not ok:
            raise NotConnected(f"تعذّر فتح الطرفية: {self._last_error()}")

        if self._t.symbol_info(self.config.symbol) is None:
            self._t.shutdown()
            raise BridgeError(
                f"الرمز {self.config.symbol} غير موجود في الطرفية. "
                "تأكّد من اسمه الدقيق في نافذة Market Watch — "
                "قد يكون XAUUSD أو XAUUSD.m أو غيرهما بحسب الوسيط."
            )
        self._connected = True

    def shutdown(self) -> None:
        if self._connected:
            self._t.shutdown()
            self._connected = False

    def __enter__(self) -> "MT5Bridge":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.shutdown()

    @property
    def connected(self) -> bool:
        return self._connected

    def _require(self) -> None:
        if not self._connected:
            raise NotConnected("الجسر غير متصل — استُدعيت قراءة قبل connect()")

    def _last_error(self) -> str:
        try:
            return str(self._t.last_error())
        except Exception:
            return "غير معروف"

    # ── الشموع ──
    def fetch(self, timeframe: str, count: int) -> Series:
        """
        يقرأ آخر `count` شمعة **مغلقة**.

        ⭐ **الشمعة قيد التكوّن تُحذف.** الطرفية تعيدها ضمن النتيجة،
        وكل قواعد المدرّب تقوم على الإغلاق: «بس ما يغلق فوق الـ50%» ·
        «الكسر بالجسم» · «أغلق تحت المنطقة». فالتحليل على شمعة نصف
        مكتملة يقرأ سعرًا سيتغيّر بعد ثانية.

        ولذلك يُطلب `count + 1` ثم تُسقَط الأخيرة — فيعود العدد المطلوب
        كاملًا لا ناقصًا واحدًا.
        """
        self._require()
        if timeframe not in TIMEFRAME_CONST:
            raise BridgeError(f"إطار غير مدعوم: {timeframe}")
        if count < 1:
            raise BridgeError("العدد شمعة أو أكثر")

        const = getattr(self._t, TIMEFRAME_CONST[timeframe], None)
        if const is None:
            raise BridgeError(f"الطرفية لا تعرف الإطار {timeframe}")

        want = count + 1 if self.config.drop_forming_candle else count
        rows = self._t.copy_rates_from_pos(self.config.symbol, const, 0, want)
        if rows is None or len(rows) == 0:
            raise BridgeError(
                f"لا بيانات لـ{self.config.symbol} على {timeframe}: {self._last_error()}"
            )

        candles = [self._to_candle(r) for r in rows]
        candles.sort(key=lambda c: c.time)

        if self.config.drop_forming_candle:
            candles = candles[:-1]
        if not candles:
            raise BridgeError("لم تبقَ شمعة مغلقة بعد حذف الشمعة قيد التكوّن")

        return Series(timeframe, candles[-count:], self.config.symbol)

    def _to_candle(self, row: Any) -> Candle:
        """
        يحوّل صفًّا من الطرفية إلى شمعة.

        ⭐ **الحجم `tick_volume`** — الذهب عقد فرقي بلا حجم تداول حقيقي،
        و`real_volume` يعود صفرًا عند أغلب الوسطاء. وهو الرقم نفسه الذي
        يقرأه المدرّب على منصّته (وايكوف/د4).
        """
        return Candle(
            time=self._server_time(row["time"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["tick_volume"]),
        )

    def _server_time(self, epoch: Any) -> datetime:
        """
        ختم الوقت كما تعطيه الطرفية — **بتوقيت خادم الوسيط**.

        يُحوَّل إلى وقت ساذج (naive) موحّد كي لا يختلط بتوقيتك المحلي.
        القواعد الزمنية تستعمل `to_utc()` صراحةً.
        """
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).replace(tzinfo=None)

    def to_utc(self, server_time: datetime) -> datetime:
        """
        يحوّل وقت الخادم إلى UTC بالإزاحة المعلَنة.

        ⚠️ الإزاحة الخاطئة تزيح كل قاعدة زمنية ساعاتٍ كاملة — ولذلك
        تُقاس بـ`measure_server_offset()` ولا تُفترض.
        """
        return server_time - timedelta(hours=self.config.server_utc_offset_hours)

    def measure_server_offset(self) -> float:
        """
        يقيس إزاحة خادم الوسيط بمقارنة ختم آخر تكّة بالساعة الحقيقية.

        يُقرَّب إلى نصف ساعة — إزاحات الوسطاء كلها من مضاعفاتها،
        والفرق الباقي تأخّرُ شبكةٍ لا إزاحة.
        """
        self._require()
        tick = self._t.symbol_info_tick(self.config.symbol)
        if tick is None:
            raise BridgeError(f"لا تكّة لـ{self.config.symbol}: {self._last_error()}")

        server = datetime.fromtimestamp(int(tick.time), tz=timezone.utc).replace(tzinfo=None)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        hours = (server - now).total_seconds() / 3600.0
        return round(hours * 2) / 2

    # ── السعر والسبريد ──
    def spread(self) -> float:
        """
        السبريد الحيّ **بوحدات السعر** لا بالنقاط.

        يُقرأ من الفرق بين العرض والطلب مباشرةً — أدقّ من حقل `spread`
        المقرَّب في `symbol_info`. وهو أرضية هامش الوقف الدنيا (T2).
        """
        self._require()
        tick = self._t.symbol_info_tick(self.config.symbol)
        if tick is None:
            raise BridgeError(f"لا تكّة لـ{self.config.symbol}: {self._last_error()}")

        value = float(tick.ask) - float(tick.bid)
        if value < 0:
            raise BridgeError(f"سبريد سالب ({value}) — بيانات تكّة فاسدة")
        return value

    def symbol_digits(self) -> int:
        """عدد الخانات العشرية — لتقريب الأسعار كما يعرضها الوسيط."""
        self._require()
        info = self._t.symbol_info(self.config.symbol)
        if info is None:
            raise BridgeError(f"لا معلومات لـ{self.config.symbol}")
        return int(info.digits)

    # ── المراكز المفتوحة ──
    def open_positions(self) -> List[Dict[str, Any]]:
        """
        المراكز المفتوحة على الرمز — لأجل `adopt_open_positions`.

        قراءة محضة: تُرجَع كقواميس ولا يُعدَّل منها شيء. وقرارك
        المسجَّل صريح: **المركز بلا سجل مطابق يُنبَّه عنه ولا يُلمس.**
        """
        self._require()
        found = self._t.positions_get(symbol=self.config.symbol)
        if not found:
            return []
        return [
            {
                "ticket": int(p.ticket),
                "type": "buy" if int(p.type) == 0 else "sell",
                "volume": float(p.volume),
                "price_open": float(p.price_open),
                "sl": float(p.sl),
                "tp": float(p.tp),
                "time": self._server_time(p.time),
            }
            for p in found
        ]

    # ── النبضة ──
    def health(self, timeframe: str = "M15", count: int = 50) -> "BridgeHealth":
        """
        فحص شامل يصلح نبضةً لتيليجرام — `heartbeat_to_telegram`.

        يقرأ فعلًا ولا يكتفي بحالة الاتصال: طرفية «متصلة» تعيد بيانات
        متوقّفة حالةٌ واقعية، ولا يكشفها إلا آخر ختم وقت.
        """
        series = self.fetch(timeframe, count)
        last = series.last_closed()
        return BridgeHealth(
            connected=self._connected,
            symbol=self.config.symbol,
            timeframe=timeframe,
            bars=len(series),
            last_bar_time=last.time if last else None,
            gaps=find_gaps(series, timeframe, self.config.max_gap_bars),
            spread=self.spread(),
        )


@dataclass(frozen=True)
class BridgeHealth:
    connected: bool
    symbol: str
    timeframe: str
    bars: int
    last_bar_time: Optional[datetime]
    gaps: List[DataGap] = field(default_factory=list)
    spread: Optional[float] = None

    @property
    def healthy(self) -> bool:
        return self.connected and self.bars > 0 and not self.gaps

    def render(self) -> str:
        mark = "✅" if self.healthy else "⚠️"
        L = [
            f"{mark} جسر MT5 — {self.symbol} · {self.timeframe}",
            f"   شموع: {self.bars}"
            + (f" · آخرها {self.last_bar_time:%m-%d %H:%M}" if self.last_bar_time else ""),
        ]
        if self.spread is not None:
            L.append(f"   السبريد: {self.spread:.2f}")
        if self.gaps:
            L.append(f"   ⚠️ {len(self.gaps)} فجوة:")
            L += [f"      {g.render()}" for g in self.gaps[:5]]
        return "\n".join(L)


# ─────────────────────────── التشغيل ───────────────────────────


def open_terminal(config: Optional[BridgeConfig] = None, **credentials: Any) -> MT5Bridge:
    """
    يستورد مكتبة الطرفية ويفتح الجسر.

    تُستورد داخل الدالة عمدًا: `MetaTrader5` تعمل على ويندوز فقط،
    واستيرادها على مستوى الوحدة يكسر كل اختبارات المشروع على لينكس.
    """
    try:
        import MetaTrader5 as terminal
    except ImportError as exc:
        raise BridgeError(
            "حزمة MetaTrader5 غير مثبَّتة.\n"
            "على ويندوز:  pip install MetaTrader5\n"
            "وهي لا تعمل على لينكس/ماك — الطرفية نفسها يجب أن تكون "
            "مفتوحة على الجهاز."
        ) from exc

    bridge = MT5Bridge(terminal, config)
    bridge.connect(**credentials)
    return bridge


def self_check() -> int:
    """
    فحص ذاتي يُشغَّل على جهازك:  `python -m bot.mt5_bridge`

    يثبت أن الجسر يقرأ فعلًا قبل بناء أي شيء فوقه. ويطبع **إزاحة
    الخادم المقاسة** كي تنقلها إلى إعدادك — القاعدة الزمنية الوحيدة
    التي لا يمكن للكود أن يستنتجها وحده.
    """
    from . import local_config as lc

    print("═" * 58)
    print("فحص جسر MT5")
    print("═" * 58)

    try:
        settings = lc.load()
    except lc.ConfigMissing as exc:
        print(f"\n⚠️ {exc}")
        return 1

    print("\n" + lc.describe(settings).render())

    cfg = BridgeConfig(symbol=settings.get("SYMBOL", "XAUUSD.m"))
    try:
        creds = lc.mt5_credentials(settings)
        bridge = open_terminal(cfg, **creds)
    except (BridgeError, lc.ConfigMissing) as exc:
        print(f"\n❌ {exc}")
        return 1

    try:
        offset = bridge.measure_server_offset()
        print(f"\n🕐 إزاحة خادم الوسيط المقاسة: UTC{offset:+g}")
        print("   ضعها في BridgeConfig.server_utc_offset_hours")
        print("   ⚠️ بدونها تنزاح كل قاعدة زمنية بمقدارها.")

        print(f"\n💵 السبريد الحيّ: {bridge.spread():.2f}")
        print(f"   هامش الوقف = max(درجتان = 2.00 ، السبريد)")

        for tf in ("H4", "H1", "M15", "M5"):
            try:
                health = bridge.health(tf, count=60)
                print("\n" + health.render())
            except BridgeError as exc:
                print(f"\n⚠️ {tf}: {exc}")

        positions = bridge.open_positions()
        print(f"\n📌 مراكز مفتوحة على {cfg.symbol}: {len(positions)}")
        for p in positions:
            print(f"   #{p['ticket']} {p['type']} {p['volume']} @ {p['price_open']}")

        print("\n" + "═" * 58)
        print("⛔ التنفيذ ما زال محجوبًا — الجسر يقرأ ولا يأمر.")
        return 0
    finally:
        bridge.shutdown()


if __name__ == "__main__":
    raise SystemExit(self_check())
