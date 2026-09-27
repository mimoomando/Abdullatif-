"""
قراءة رسالة التنبيه الآتية من تيرادينغ فيو.

الرسالة نصّ يكتبه صاحب الحساب في خانة Message، فيصل كما هو. ولأن
صيغته قد تتغير — رسالة المؤشر الجاهزة أو رسالة نكتبها بأنفسنا —
فالقارئ هنا متسامح في أسماء الحقول، صارم في معناها: ما لم يُفهم
معناه بيقين لا يفتح صفقة.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field

BUY = "BUY"
SELL = "SELL"
TP1 = "TP1"
TP2 = "TP2"
TP3 = "TP3"
TP_ANY = "TP_ANY"
SL_HIT = "SL_HIT"
CLOSE = "CLOSE"

ENTRY_KINDS = (BUY, SELL)
TP_KINDS = (TP1, TP2, TP3, TP_ANY)

# ما قد يُكتب في خانة القرار، وما يعنيه عندنا
_KIND_WORDS = {
    "buy": BUY, "long": BUY, "buy signal": BUY, "buy signal only": BUY,
    "sell": SELL, "short": SELL, "sell signal": SELL, "sell signal only": SELL,
    "tp1": TP1, "tp1 hit": TP1, "takeprofit1": TP1,
    "tp2": TP2, "tp2 hit": TP2, "takeprofit2": TP2,
    "tp3": TP3, "tp3 hit": TP3, "takeprofit3": TP3,
    "tp": TP_ANY, "tp hit": TP_ANY, "tp hit (any)": TP_ANY, "takeprofit": TP_ANY,
    "sl": SL_HIT, "sl hit": SL_HIT, "stop": SL_HIT, "stoploss": SL_HIT,
    "close": CLOSE, "exit": CLOSE, "flat": CLOSE,
}

_KIND_KEYS = ("signal", "action", "side", "event", "type", "kind", "order")
_ENTRY_KEYS = ("entry", "entry_price", "price", "open")
_SL_KEYS = ("sl", "stop", "stoploss", "stop_loss")
_TP_KEYS = (("tp1", "tp", "takeprofit1", "take_profit_1"),
            ("tp2", "takeprofit2", "take_profit_2"),
            ("tp3", "takeprofit3", "take_profit_3"))
_TICKER_KEYS = ("ticker", "symbol", "instrument", "pair")
_TF_KEYS = ("tf", "timeframe", "interval", "resolution", "period")
_ID_KEYS = ("id", "alert_id", "uid", "time", "timenow", "bar_time")

# قالب لم تستبدله تيرادينغ فيو: يصل حرفياً هكذا حين يُخطئ اسم الحقل
_UNRESOLVED = re.compile(r"\{\{.*?\}\}")

# ما تكتبه المنصات للفريم الواحد يختلف: تيرادينغ فيو ترسل «1» للدقيقة
# و«60» للساعة و«D» لليوم، والميتاتريدر يكتبها «M1» و«H1» و«D1»،
# والناس يكتبونها «1m» و«1h». فتُردّ كلها إلى عدد الدقائق.
_TF_WORDS = {
    "D": 1440, "DAY": 1440, "DAILY": 1440,
    "W": 10080, "WEEK": 10080, "WEEKLY": 10080,
    "M": 43200, "MONTH": 43200, "MONTHLY": 43200,
}
# «M1» بادئتها حرف: دقيقة عند الميتاتريدر. و«1M» لاحقتها حرف: شهر
# عند تيرادينغ فيو. فالفرق في الموضع لا في الحرف.
_TF_PREFIX = re.compile(r"^([SMHDW])(\d+)$")
_TF_SUFFIX = re.compile(r"^(\d+)([SMHDWsmhdw])$")
_TF_UNIT_MINUTES = {"S": 1 / 60.0, "M": 1, "H": 60, "D": 1440, "W": 10080}


def normalize_timeframe(raw):
    """
    فريم مكتوب بأي صيغة ← عدد دقائقه، أو لا شيء إن لم يُفهم.

    تيرادينغ فيو ترسل «1» للدقيقة و«60» للساعة و«D» لليوم و«M» للشهر.
    والميتاتريدر يكتبها «M1» و«H1». والناس يكتبون «1m» و«1h».

    وحالة الحرف وحدها تفرّق بين اثنين يلتبسان: «1M» بحرف كبير شهرٌ
    كما تكتبه تيرادينغ فيو، و«1m» بحرف صغير دقيقةٌ كما يكتبها الناس.
    فلا تُرفع الحروف إلى الكبير قبل التفرقة.
    """
    if raw is None:
        return None
    text = str(raw).strip().replace(" ", "")
    if not text or _UNRESOLVED.search(text):
        return None

    if text.isdigit():
        return int(text)

    upper = text.upper()
    if upper in _TF_WORDS:
        return _TF_WORDS[upper]

    # «M1» و«H4»: البادئة حرف، والميتاتريدر لا يعني بالميم إلا الدقيقة
    match = _TF_PREFIX.match(upper)
    if match:
        return _minutes(int(match.group(2)), match.group(1), month_for_m=False)

    # «1M» و«1m» و«4H»: اللاحقة حرف، وحالتها تحسم الميم
    match = _TF_SUFFIX.match(text)
    if match:
        unit = match.group(2)
        return _minutes(int(match.group(1)), unit.upper(),
                        month_for_m=unit == "M")

    # «15min» و«4hour» وأمثالهما
    match = re.match(r"^(\d+)(SEC|SECOND|MIN|MINUTE|HOUR|DAY|WEEK|MONTH)S?$", upper)
    if match:
        unit = {"SEC": 1 / 60.0, "SECOND": 1 / 60.0, "MIN": 1, "MINUTE": 1,
                "HOUR": 60, "DAY": 1440, "WEEK": 10080, "MONTH": 43200}
        return int(round(int(match.group(1)) * unit[match.group(2)])) or 1
    return None


def _minutes(count, unit, month_for_m):
    if unit == "M" and month_for_m:
        return count * 43200
    return int(round(count * _TF_UNIT_MINUTES[unit])) or 1


class SignalError(ValueError):
    """رسالة لا تصلح لفتح صفقة ولا لإدارتها."""


@dataclass
class Signal:
    kind: str
    ticker: str = ""
    entry: float = None
    sl: float = None
    tps: list = field(default_factory=list)
    secret: str = ""
    alert_id: str = ""
    timeframe: int = None        # بالدقائق، أو لا شيء إن لم يُرسل
    raw: dict = field(default_factory=dict)

    @property
    def side(self):
        """اتجاه الصفقة: شراء أو بيع. لغير إشارات الدخول: لا شيء."""
        if self.kind in ENTRY_KINDS:
            return self.kind.lower()
        return None

    @property
    def risk_distance(self):
        """المسافة بين الدخول والوقف كما أرادها المؤشر."""
        if self.entry is None or self.sl is None:
            return None
        return abs(self.entry - self.sl)

    def reward_distance(self, index):
        """المسافة بين الدخول والهدف رقم (١ أو ٢ أو ٣)."""
        if self.entry is None or index < 1 or index > len(self.tps):
            return None
        return abs(self.tps[index - 1] - self.entry)

    def fingerprint(self):
        """بصمة تميّز التنبيه، فلا يُنفَّذ مرتين إن أُعيد إرساله."""
        if self.alert_id:
            base = f"{self.kind}|{self.ticker}|{self.alert_id}"
        else:
            base = "|".join(str(x) for x in (
                self.kind, self.ticker, self.entry, self.sl, tuple(self.tps)
            ))
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def parse(body):
    """نصّ التنبيه ← إشارة مفهومة. يرفع SignalError إن لم تُفهم."""
    data = _as_dict(body)

    kind = _read_kind(data)
    signal = Signal(
        kind=kind,
        ticker=str(_first(data, _TICKER_KEYS) or "").strip(),
        secret=str(data.get("secret") or data.get("key") or "").strip(),
        raw=data,
    )

    signal.timeframe = normalize_timeframe(_first(data, _TF_KEYS))

    alert_id = _first(data, _ID_KEYS)
    if alert_id is not None and not _is_unresolved(alert_id):
        signal.alert_id = str(alert_id).strip()

    signal.entry = _read_number(data, _ENTRY_KEYS, "سعر الدخول")
    signal.sl = _read_number(data, _SL_KEYS, "الوقف")
    for keys in _TP_KEYS:
        tp = _read_number(data, keys, "الهدف")
        if tp is None:
            break
        signal.tps.append(tp)

    if kind in ENTRY_KINDS:
        _validate_entry(signal)
    return signal


def _validate_entry(signal):
    """إشارة الدخول وحدها تحتاج أرقاماً، وتحتاج أن تتفق مع نفسها."""
    if signal.entry is None:
        raise SignalError("إشارة دخول بلا سعر دخول.")
    if signal.sl is None:
        raise SignalError("إشارة دخول بلا وقف.")
    if signal.entry == signal.sl:
        raise SignalError("الوقف يساوي الدخول: لا اتجاه لها ولا مخاطرة محسوبة.")

    # الوقف تحت الدخول شراء، وفوقه بيع. فإن خالف ذلك ما كُتب في
    # الرسالة فأحدهما خطأ، ولا نخمّن أيّهما: نرفض التنبيه كله.
    implied = BUY if signal.sl < signal.entry else SELL
    if implied != signal.kind:
        raise SignalError(
            f"الرسالة تقول {signal.kind} وموضع الوقف يقول {implied}: "
            f"دخول {signal.entry} ووقف {signal.sl}."
        )

    for index, tp in enumerate(signal.tps, start=1):
        if signal.kind == BUY and tp <= signal.entry:
            raise SignalError(f"هدف الشراء رقم {index} ليس فوق الدخول: {tp}.")
        if signal.kind == SELL and tp >= signal.entry:
            raise SignalError(f"هدف البيع رقم {index} ليس تحت الدخول: {tp}.")


def _as_dict(body):
    if isinstance(body, dict):
        return body
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    text = text.strip()
    if not text:
        raise SignalError("رسالة فارغة.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SignalError(f"الرسالة ليست JSON سليماً: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise SignalError("الرسالة ليست كائن JSON.")
    return data


def _first(data, keys):
    """أول قيمة موجودة من أسماء الحقول المقبولة."""
    lowered = {str(k).strip().lower(): v for k, v in data.items()}
    for key in keys:
        if key in lowered and lowered[key] not in (None, ""):
            return lowered[key]
    return None


def _read_kind(data):
    raw = _first(data, _KIND_KEYS)
    if raw is None:
        raise SignalError("لا يُعرف ماذا تريد الرسالة: لا شراء ولا بيع ولا هدف.")
    if _is_unresolved(raw):
        raise SignalError(f"قالب لم تستبدله تيرادينغ فيو: «{raw}».")
    word = re.sub(r"[_\-]+", " ", str(raw).strip().lower())
    word = re.sub(r"\s+", " ", word)
    if word in _KIND_WORDS:
        return _KIND_WORDS[word]
    raise SignalError(f"قرار غير مفهوم: «{raw}».")


def _read_number(data, keys, label):
    raw = _first(data, keys)
    if raw is None:
        return None
    if _is_unresolved(raw):
        raise SignalError(
            f"{label}: قالب لم تستبدله تيرادينغ فيو «{raw}». "
            "راجع اسم الحقل في خانة Message."
        )
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip().replace(",", "").replace(" ", "")
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            raise SignalError(f"{label}: يُنتظر رقم، ووصل «{raw}».") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise SignalError(f"{label}: رقم غير صالح «{raw}».")
    if value <= 0:
        raise SignalError(f"{label}: يُنتظر سعراً موجباً، ووصل «{raw}».")
    return value


def _is_unresolved(value):
    return isinstance(value, str) and bool(_UNRESOLVED.search(value))
