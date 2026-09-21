"""
إعدادات البريدج.

كل قيمة تُقرأ من متغيرات البيئة، وتُحمَّل من ملف ‎.env‎ إن وُجد.
لا يُكتب أي سر داخل الكود، فملف ‎.env‎ خارج المستودع دائماً.
"""

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # الحزمة غير مثبّتة: تبقى متغيرات البيئة وحدها
    pass


def _str(name, default=""):
    return os.environ.get(name, default).strip()


def _float(name, default):
    raw = _str(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name}: يُنتظر رقم، ووصل «{raw}»")


def _int(name, default):
    raw = _str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name}: يُنتظر عدد صحيح، ووصل «{raw}»")


def _bool(name, default):
    raw = _str(name).lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on", "نعم"):
        return True
    if raw in ("0", "false", "no", "off", "لا"):
        return False
    raise ValueError(f"{name}: يُنتظر نعم أو لا، ووصل «{raw}»")


@dataclass
class Settings:
    # ── الخادم ──
    host: str = "0.0.0.0"
    port: int = 80          # تيرادينغ فيو لا ترسل إلا إلى 80 أو 443
    webhook_path: str = "/webhook"

    # كلمة السر التي تحملها كل رسالة تنبيه. بدونها تُرفض الرسالة،
    # فالعنوان وحده لا يكفي: من عرفه لا يملك أن يفتح به صفقة.
    webhook_secret: str = ""

    # ── مفتاح الإيقاف ──
    # تجريبي: كل شيء يعمل ويُسجَّل، ولا يُرسل أمر إلى الحساب.
    dry_run: bool = True
    enabled: bool = True

    # ── حساب الميتاتريدر ──
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""      # مسار terminal64.exe إن لم يُعثر عليه وحده

    # ── الرمز ──
    # رمز الذهب عند جست ماركتس. يختلف عن رمز الشارت أحياناً
    # (XAUUSD مقابل XAUUSD.m وغيرهما) فيُضبط هنا صراحة.
    symbol: str = "XAUUSD"
    # ما ترسله تيرادينغ فيو في خانة ticker، وما يقابله عند الوسيط
    symbol_map: dict = field(default_factory=dict)

    # ── حجم الصفقة ──
    lot: float = 0.01
    # نسبة المخاطرة من الرصيد. صفر يعني: الزم اللوت الثابت أعلاه.
    risk_percent: float = 0.0
    max_lot: float = 1.0

    # ── حدود الأمان ──
    max_open_positions: int = 1
    # أبعد من ذلك: خطأ قراءة أو توصية لا يحتملها الحساب
    max_risk_usd: float = 50.0
    min_stop_distance: float = 0.5   # بسعر الأداة، لا بالنقاط
    max_stop_distance: float = 100.0
    slippage_points: int = 30
    magic: int = 26092101            # بصمة صفقات هذا البريدج وحده

    # ── إدارة الصفقة بعد فتحها ──
    # عند بلوغ الهدف الأول: كم يُغلق من الصفقة، وهل يُنقل الوقف للدخول.
    tp1_close_percent: float = 0.0
    tp1_move_to_breakeven: bool = True
    # أي الأهداف يوضع هدفاً للصفقة عند الوسيط: 1 أو 2 أو 3
    target_tp: int = 1
    # إشارة معاكسة وصفقة مفتوحة: تُغلق القديمة ثم تُفتح الجديدة
    reverse_on_opposite: bool = True

    # ── التنبيه على تيليغرام ──
    telegram_token: str = ""
    telegram_chat_id: str = ""

    # ── السجل ──
    log_file: str = "bridge.log"

    @classmethod
    def load(cls):
        s = cls()
        s.host = _str("HOST", s.host)
        s.port = _int("PORT", s.port)
        s.webhook_path = _str("WEBHOOK_PATH", s.webhook_path)
        s.webhook_secret = _str("WEBHOOK_SECRET")

        s.dry_run = _bool("DRY_RUN", s.dry_run)
        s.enabled = _bool("ENABLED", s.enabled)

        s.mt5_login = _int("MT5_LOGIN", s.mt5_login)
        s.mt5_password = _str("MT5_PASSWORD")
        s.mt5_server = _str("MT5_SERVER")
        s.mt5_path = _str("MT5_PATH")

        s.symbol = _str("SYMBOL", s.symbol)
        s.symbol_map = _parse_symbol_map(_str("SYMBOL_MAP"), s.symbol)

        s.lot = _float("LOT", s.lot)
        s.risk_percent = _float("RISK_PERCENT", s.risk_percent)
        s.max_lot = _float("MAX_LOT", s.max_lot)

        s.max_open_positions = _int("MAX_OPEN_POSITIONS", s.max_open_positions)
        s.max_risk_usd = _float("MAX_RISK_USD", s.max_risk_usd)
        s.min_stop_distance = _float("MIN_STOP_DISTANCE", s.min_stop_distance)
        s.max_stop_distance = _float("MAX_STOP_DISTANCE", s.max_stop_distance)
        s.slippage_points = _int("SLIPPAGE_POINTS", s.slippage_points)
        s.magic = _int("MAGIC", s.magic)

        s.tp1_close_percent = _float("TP1_CLOSE_PERCENT", s.tp1_close_percent)
        s.tp1_move_to_breakeven = _bool("TP1_MOVE_TO_BREAKEVEN", s.tp1_move_to_breakeven)
        s.target_tp = _int("TARGET_TP", s.target_tp)
        s.reverse_on_opposite = _bool("REVERSE_ON_OPPOSITE", s.reverse_on_opposite)

        s.telegram_token = _str("TELEGRAM_TOKEN")
        s.telegram_chat_id = _str("TELEGRAM_CHAT_ID")
        s.log_file = _str("LOG_FILE", s.log_file)

        s.validate()
        return s

    def validate(self):
        """يُمنع الإقلاع بإعداد يفتح صفقة خاطئة أو يترك الباب مفتوحاً."""
        if not self.webhook_secret:
            raise ValueError(
                "WEBHOOK_SECRET فارغ. بدونه يفتح أي من عرف العنوان صفقة على حسابك."
            )
        if len(self.webhook_secret) < 16:
            raise ValueError("WEBHOOK_SECRET قصير: ستة عشر محرفاً فأكثر.")
        if not self.webhook_secret.isascii():
            # ترويسات HTTP لا تحمل إلا اللاتيني، وكلمة السر قد تُرسل
            # فيها. فتُشترط لاتينية من البداية لا أن تُكتشف وقت التنفيذ.
            raise ValueError(
                "WEBHOOK_SECRET: حروف وأرقام لاتينية فقط. "
                "ولّدها بـ python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if self.target_tp not in (1, 2, 3):
            raise ValueError("TARGET_TP: واحد أو اثنان أو ثلاثة.")
        if self.lot <= 0:
            raise ValueError("LOT: أكبر من صفر.")
        if self.max_lot < self.lot:
            raise ValueError("MAX_LOT أصغر من LOT.")
        if not 0 <= self.tp1_close_percent <= 100:
            raise ValueError("TP1_CLOSE_PERCENT: بين صفر ومئة.")
        if self.min_stop_distance <= 0:
            raise ValueError("MIN_STOP_DISTANCE: أكبر من صفر.")
        if self.max_stop_distance <= self.min_stop_distance:
            raise ValueError("MAX_STOP_DISTANCE أصغر من MIN_STOP_DISTANCE أو يساويه.")
        if self.max_risk_usd <= 0:
            raise ValueError("MAX_RISK_USD: أكبر من صفر.")
        if not self.dry_run and not (self.mt5_login and self.mt5_password and self.mt5_server):
            raise ValueError(
                "التنفيذ الحقيقي يحتاج MT5_LOGIN و MT5_PASSWORD و MT5_SERVER."
            )

    def broker_symbol(self, ticker):
        """رمز الوسيط المقابل لما أرسلته تيرادينغ فيو."""
        if not ticker:
            return self.symbol
        key = ticker.strip().upper()
        # OANDA:XAUUSD ← نأخذ ما بعد النقطتين
        if ":" in key:
            key = key.split(":", 1)[1]
        return self.symbol_map.get(key, self.symbol)


def _parse_symbol_map(raw, fallback):
    """‎XAUUSD=XAUUSD.m,EURUSD=EURUSD.m‎ ← قاموساً."""
    mapping = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"SYMBOL_MAP: يُنتظر رمز=رمز، ووصل «{pair}»")
        left, right = pair.split("=", 1)
        left, right = left.strip().upper(), right.strip()
        if not left or not right:
            raise ValueError(f"SYMBOL_MAP: طرف فارغ في «{pair}»")
        mapping[left] = right
    mapping.setdefault("XAUUSD", fallback)
    return mapping
