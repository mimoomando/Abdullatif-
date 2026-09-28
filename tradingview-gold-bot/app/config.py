"""
إعدادات البريدج.

كل قيمة تُقرأ من متغيرات البيئة، وتُحمَّل من ملف ‎.env‎ إن وُجد.
لا يُكتب أي سر داخل الكود، فملف ‎.env‎ خارج المستودع دائماً.
"""

import hashlib
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
class Source:
    """
    مؤشرٌ بعينه: حجمه ووقفه وهدفه وبصمته.

    البصمة هي المهمّة: بها يعرف الجسر صفقات هذا المؤشر من صفقات
    غيره، فلا يغلق تنبيهُ أحدهما صفقةَ الآخر. وتُشتقّ من الاسم
    اشتقاقاً ثابتاً، فلا يتغيّر رقمها ما دام الاسم على حاله.
    """
    name: str
    lot: float = 0.0
    sl_distance: float = 0.0
    tp_distance: float = 0.0
    magic: int = 0


def _magic_for(name, base):
    """بصمة ثابتة من الاسم: نفس الاسم ← نفس الرقم في كل إقلاع."""
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:6]
    return int(base) + 1 + int(digest, 16) % 900


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

    # ── الفريم المسموح ──
    # مؤشر واحد يعطي إشارات مختلفة على كل فريم، والمقصود فريمٌ بعينه.
    # التنبيه في تيرادينغ فيو مربوط بفريم الشارت الذي أُنشئ عليه، لكن
    # تنبيهاً أُنشئ سهواً على شارت آخر لا يردّه شيء. فهذا حارسه.
    # قائمة بالدقائق مفصولة بفواصل، والفراغ يقبل كل فريم.
    allowed_timeframes: set = field(default_factory=set)

    # ── أرجل الصفقة ──
    # الإشارة الواحدة قد تُفتح على أكثر من صفقة، لكل واحدة هدفها
    # وحجمها. مثال: «1:0.01,3:0.01» صفقتان بحجم 0.01، الأولى هدفها
    # الهدف الأول والثانية الثالث — فتُجنى أرباح مبكرة ويُترك الباقي
    # يجري. والخروج كله عند الوسيط: كل صفقة تحمل هدفها ووقفها، فلا
    # يُنتظر تنبيه ولا يُخشى انقطاع.
    # والفراغ يعني صفقة واحدة بـ LOT و TARGET_TP أدناه.
    legs: list = field(default_factory=list)

    # ── حجم الصفقة ──
    lot: float = 0.01
    # نسبة المخاطرة من الرصيد. صفر يعني: الزم اللوت الثابت أعلاه.
    risk_percent: float = 0.0
    max_lot: float = 1.0
    # ── حين لا يرسل المؤشر أرقامه ──
    # بعض المؤشرات ترسم الدخول والوقف والأهداف رسماً على الشاشة لا
    # قيماً تُقرأ، فتصل التنبيهات بلا أرقام. وهذه المسافة — بسعر
    # الأداة لا بالنقاط — تصير وقفاً يُقاس من سعر التنفيذ الفعلي،
    # ولا هدف عند الوسيط: الخروج بتنبيه «TP1 Hit» من المؤشر نفسه.
    # وصفر يعني: لا تفتح صفقة بلا أرقام، وهو الأصل.
    sl_distance: float = 0.0

    # ── أكثر من مؤشر على الأداة نفسها ──
    # «lux:lot=0.05,sl=5,tp=5» ← مؤشر يكتب "src":"lux" في رسالته،
    # فيأخذ حجمه ووقفه وهدفه، وتُختَم صفقاته ببصمته وحدها. وما وصل
    # بلا "src" فعلى الإعداد العام أعلاه، فلا تُلمس تنبيهات قائمة.
    sources: dict = field(default_factory=dict)

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

    # ── حارس الصمت ──
    # تنبيهات تيرادينغ فيو على خطة Essential تنتهي بعد شهرين، فتسكت
    # القناة ويبقى البريدج ينصت وصاحبه يحسبه يتداول. هذه المدة التي
    # إن مرّت بلا تنبيه واحد والسوق يتحرك، أُرسل إشعار. صفر يُطفئه.
    silence_hours: float = 48.0
    silence_repeat_hours: float = 24.0
    silence_check_minutes: float = 15.0
    # أسعار الوسيط متجمدة هذه المدة ⇒ السوق مقفل، فالصمت طبيعي
    stale_quote_minutes: float = 10.0

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

        s.allowed_timeframes = _parse_timeframes(_str("ALLOWED_TIMEFRAMES"))

        s.legs = _parse_legs(_str("LEGS"))
        s.lot = _float("LOT", s.lot)
        s.risk_percent = _float("RISK_PERCENT", s.risk_percent)
        s.max_lot = _float("MAX_LOT", s.max_lot)

        s.sl_distance = _float("SL_DISTANCE", s.sl_distance)
        s.magic = _int("MAGIC", s.magic)
        s.sources = _parse_sources(_str("SOURCES"), s.magic)

        s.max_open_positions = _int("MAX_OPEN_POSITIONS", s.max_open_positions)
        s.max_risk_usd = _float("MAX_RISK_USD", s.max_risk_usd)
        s.min_stop_distance = _float("MIN_STOP_DISTANCE", s.min_stop_distance)
        s.max_stop_distance = _float("MAX_STOP_DISTANCE", s.max_stop_distance)
        s.slippage_points = _int("SLIPPAGE_POINTS", s.slippage_points)

        s.tp1_close_percent = _float("TP1_CLOSE_PERCENT", s.tp1_close_percent)
        s.tp1_move_to_breakeven = _bool("TP1_MOVE_TO_BREAKEVEN", s.tp1_move_to_breakeven)
        s.target_tp = _int("TARGET_TP", s.target_tp)
        s.reverse_on_opposite = _bool("REVERSE_ON_OPPOSITE", s.reverse_on_opposite)

        s.silence_hours = _float("SILENCE_HOURS", s.silence_hours)
        s.silence_repeat_hours = _float("SILENCE_REPEAT_HOURS", s.silence_repeat_hours)
        s.silence_check_minutes = _float("SILENCE_CHECK_MINUTES", s.silence_check_minutes)
        s.stale_quote_minutes = _float("STALE_QUOTE_MINUTES", s.stale_quote_minutes)

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
        if self.legs and self.risk_percent > 0:
            raise ValueError(
                "LEGS و RISK_PERCENT لا يجتمعان: الأرجل تحمل أحجامها، "
                "فاترك RISK_PERCENT صفراً أو امسح LEGS."
            )
        if self.lot <= 0:
            raise ValueError("LOT: أكبر من صفر.")
        if self.max_lot < self.lot:
            raise ValueError("MAX_LOT أصغر من LOT.")
        if not 0 <= self.tp1_close_percent <= 100:
            raise ValueError("TP1_CLOSE_PERCENT: بين صفر ومئة.")
        if self.sl_distance < 0:
            raise ValueError("SL_DISTANCE: صفر فأكثر، وصفر يعني لا تفتح بلا أرقام.")
        if self.sl_distance and self.legs:
            raise ValueError(
                "SL_DISTANCE و LEGS لا يجتمعان: بلا أرقام لا أهداف عند الوسيط "
                "تُوزَّع على الأرجل. اجعلها صفقة واحدة بـ LOT."
            )
        seen = {}
        for source in self.sources.values():
            if source.lot <= 0:
                raise ValueError(f"SOURCES: حجم «{source.name}» أكبر من صفر.")
            if source.sl_distance <= 0:
                raise ValueError(
                    f"SOURCES: وقف «{source.name}» أكبر من صفر — "
                    "مؤشرٌ بلا وقف يفتح صفقة لا يحدّها شيء."
                )
            if source.tp_distance < 0:
                raise ValueError(f"SOURCES: هدف «{source.name}» صفر فأكثر.")
            if source.magic in seen:
                raise ValueError(
                    f"SOURCES: «{source.name}» و«{seen[source.magic]}» "
                    f"بصمتهما واحدة ({source.magic}). غيّر أحد الاسمين "
                    "أو اكتب magic= صريحاً."
                )
            seen[source.magic] = source.name
        if self.magic in seen:
            raise ValueError(
                f"SOURCES: بصمة «{seen[self.magic]}» تساوي البصمة العامة "
                f"({self.magic})، فلا تتميّز صفقاتها عن غيرها."
            )
        if self.min_stop_distance <= 0:
            raise ValueError("MIN_STOP_DISTANCE: أكبر من صفر.")
        if self.max_stop_distance <= self.min_stop_distance:
            raise ValueError("MAX_STOP_DISTANCE أصغر من MIN_STOP_DISTANCE أو يساويه.")
        if self.max_risk_usd <= 0:
            raise ValueError("MAX_RISK_USD: أكبر من صفر.")
        if self.silence_hours < 0:
            raise ValueError("SILENCE_HOURS: صفر فأكثر، وصفر يطفئ الحارس.")
        if self.silence_hours > 0:
            if self.silence_check_minutes <= 0:
                raise ValueError("SILENCE_CHECK_MINUTES: أكبر من صفر.")
            if self.silence_repeat_hours <= 0:
                raise ValueError("SILENCE_REPEAT_HOURS: أكبر من صفر.")
            if self.stale_quote_minutes <= 0:
                raise ValueError("STALE_QUOTE_MINUTES: أكبر من صفر.")
        if not self.dry_run and not (self.mt5_login and self.mt5_password and self.mt5_server):
            raise ValueError(
                "التنفيذ الحقيقي يحتاج MT5_LOGIN و MT5_PASSWORD و MT5_SERVER."
            )

    def source_for(self, name):
        """المصدر الذي سمّته الرسالة، ولا شيء إن لم تسمّ أو لم يُعرف."""
        if not name:
            return None
        return self.sources.get(str(name).strip().lower())

    def broker_symbol(self, ticker):
        """رمز الوسيط المقابل لما أرسلته تيرادينغ فيو."""
        if not ticker:
            return self.symbol
        key = ticker.strip().upper()
        # OANDA:XAUUSD ← نأخذ ما بعد النقطتين
        if ":" in key:
            key = key.split(":", 1)[1]
        return self.symbol_map.get(key, self.symbol)


def _parse_sources(raw, base_magic):
    """«lux:lot=0.05,sl=5,tp=5;abc:lot=0.01,sl=3» ← {اسم: مصدر}."""
    sources = {}
    for block in raw.split(";"):
        block = block.strip()
        if not block:
            continue
        if ":" not in block:
            raise ValueError(
                f"SOURCES: يُنتظر «اسم:lot=…,sl=…»، ووصل «{block}»"
            )
        name, body = block.split(":", 1)
        name = name.strip().lower()
        if not name:
            raise ValueError("SOURCES: اسم فارغ.")
        if name in sources:
            raise ValueError(f"SOURCES: «{name}» مكرّر.")

        source = Source(name=name, magic=_magic_for(name, base_magic))
        for pair in body.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                raise ValueError(f"SOURCES: يُنتظر «مفتاح=قيمة»، ووصل «{pair}»")
            key, value = pair.split("=", 1)
            key, value = key.strip().lower(), value.strip()
            try:
                if key == "lot":
                    source.lot = float(value)
                elif key in ("sl", "sl_distance"):
                    source.sl_distance = float(value)
                elif key in ("tp", "tp_distance"):
                    source.tp_distance = float(value)
                elif key == "magic":
                    source.magic = int(value)
                else:
                    raise ValueError(
                        f"SOURCES: مفتاح لا يُعرف «{key}» — "
                        "المعروف lot و sl و tp و magic."
                    )
            except ValueError as exc:
                if "لا يُعرف" in str(exc):
                    raise
                raise ValueError(
                    f"SOURCES: رقم غير مفهوم في «{pair}»"
                ) from None
        sources[name] = source
    return sources


def _parse_legs(raw):
    """«1:0.01,3:0.01» ← [(هدف, حجم)، …]. والفراغ يعني صفقة واحدة."""
    legs = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if ":" not in piece:
            raise ValueError(
                f"LEGS: يُنتظر «هدف:حجم» مثل 1:0.01، ووصل «{piece}»"
            )
        target, lot = piece.split(":", 1)
        try:
            target = int(target.strip())
            lot = float(lot.strip())
        except ValueError:
            raise ValueError(f"LEGS: رقم غير مفهوم في «{piece}»") from None
        if target not in (1, 2, 3):
            raise ValueError(f"LEGS: الهدف واحد أو اثنان أو ثلاثة، ووصل «{target}»")
        if lot <= 0:
            raise ValueError(f"LEGS: حجم أكبر من صفر، ووصل «{lot}»")
        legs.append((target, lot))
    return legs


def _parse_timeframes(raw):
    """«1» أو «1,5» أو «M1,M5» ← مجموعة دقائق. والفراغ يقبل الكل."""
    from app.signals import normalize_timeframe

    allowed = set()
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        minutes = normalize_timeframe(piece)
        if minutes is None:
            raise ValueError(
                f"ALLOWED_TIMEFRAMES: فريم غير مفهوم «{piece}». "
                "اكتبه بالدقائق (1 أو 5 أو 60) أو بصيغة M1 و H1."
            )
        allowed.add(minutes)
    return allowed


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
