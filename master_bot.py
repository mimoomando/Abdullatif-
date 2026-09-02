"""
master_bot.py
-------------
البوت الشامل — واحة جولد 🐋
يجمع 4 أنظمة في ملف واحد:

  ١- استراتيجيات كتاب أحمد حسن (18+ استراتيجية من strategy_manager)
  ٢- تحليل أشكال الشموع على M1+M5+M15+M30+H1 (الأنماط المتكررة)
  ٣- قراءة المحادثات المثبتة في تيليغرام → فتح صفقة من التوصية
  ٤- التعلم من الصفقات السابقة والأخطاء (يعدل نفسه تلقائياً)

الاستخدام:
  python master_bot.py --symbol XAUUSD
  python master_bot.py --test          ← فحص آمن دون فتح صفقات

المتطلبات:
  pip install MetaTrader5 telethon requests
"""

import MetaTrader5 as mt5
import requests
import argparse
import threading
import asyncio
import json
import time
import re
import os
import queue
import types
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# ─────────────────────────────────────────────
# ⚙️ الإعدادات
# ─────────────────────────────────────────────
try:
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
except Exception:
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

try:
    from config import TELEGRAM_API_ID, TELEGRAM_API_HASH
except Exception:
    TELEGRAM_API_ID = 0
    TELEGRAM_API_HASH = ""

try:
    from config import TELEGRAM_PHONE
except Exception:
    TELEGRAM_PHONE = ""

# بصمة النسخة: تُطبع عند الإقلاع وتُرسل على التلجرام، فلا يبقى شك
# في أي ملف يعمل فعلاً حين نتفحّص سلوكاً على الحساب الحقيقي.
BOT_VERSION = "2026-09-02.2"
BOT_FEATURES = (
    "KINGS: صفقة واحدة 0.10 · الحيتان: خمس صفقات لكل منها هدف $5 ووقف $6 · "
    "بوت التوصيات: صفقة 0.05 بستوب وهدف التوصية (HOLD لا يفتح شيئاً) · "
    "وقفك وهدفك اليدويان لا يلمسهما البوت بحال"
)

DEFAULT_SYMBOL = "XAUUSD.vnw"
DEFAULT_LOT = 0.04
SIGNAL_LOT = 0.01  # لوت صفقات التوصيات من تيليغرام
PATTERN_SL_PIPS = 30  # SL صفقات الأنماط
MAGIC_BOOK = 20260810  # صفقات استراتيجيات الكتاب
MAGIC_PATTERN = 20260811  # صفقات الأنماط
MAGIC_SIGNAL = 20260812  # صفقات التوصيات
MAGIC_CHART = 20260813  # صفقات الأنماط الفنية الكلاسيكية
MAGIC_WHALES = 20260814  # صفقات قناة WHALES VIP الحيتان
MAGIC_KINGS = 20260815  # صفقات قناة KINGS EL GOLD VIP
MAGIC_GOLDBOT = 20260816  # صفقات بوت توصيات الذهب (n8n)

# ── سياسة موحدة لكل قنوات التوصيات الحالية والمستقبلية ──
CHANNEL_POSITION_COUNT = 5
CHANNEL_POSITION_LOT = 0.01
CHANNEL_INITIAL_SL_USD = 6.0
# التدرّج في الخروج مربوط بأهداف القناة لا بمسافة ثابتة:
# صفقتان تخرجان عند الهدف الأول، وصفقتان عند الثاني، والأخيرة
# تركب سلم الأهداف حتى نهايته.
CHANNEL_TP1_EXIT_COUNT = 2
CHANNEL_TP2_EXIT_COUNT = 2
# عتبة وصفية في التقارير وحدها: كم يُعدّ الربح الذي مرّت به الصفقة
# ثم أضاعته "قريباً من الربح". لا تحرّك وقفاً ولا تغلق صفقة.
REPORT_NEAR_WIN_USD = 3.0
CHANNEL_TARGET_APPROACH_USD = 1.0
# سلم الأهداف واحد لكل القنوات: الهدف ينتقل للتالي عند الاقتراب منه
# بدولار، والوقف يقفل على الهدف السابق بعد تجاوزه بثلاث درجات.
CHANNEL_TARGET_LOCK_USD = 3.0
# بعد آخر هدف رقمي لم يبق ما يقفل عليه الوقف، فكان يقف عند آخر هدف
# وتُعيد الصفقة كل ما ربحته فوقه. الآن يتتبع الوقف أعلى سعر بلغته
# الصفقة ويبقى تحته بهذه المسافة، ولا يتحرك لأقل من خطوة.
CHANNEL_TRAIL_AFTER_LAST_USD = 5.0
CHANNEL_TRAIL_STEP_USD = 0.5
# الدخول على الكلمة وحدها يأخذ هدفاً احتياطياً فوراً، فلا تبقى
# الصفقة لحظة واحدة بلا مخرج. وحين تصل أرقام القناة يحلّ هدفها محله.
CHANNEL_TARGETLESS_GRACE_SECONDS = 0
CHANNEL_FALLBACK_TP_USD = 5.0
CHANNEL_MANAGER_INTERVAL_SECONDS = 0.25
CHANNEL_PENDING_MIXED_GRACE_SECONDS = 10.0
# مهلة قصيرة تكفي لتسجيل الصفقات الخمس عند فتحها دفعة واحدة. بعدها
# تُدار المجموعة بما هو مفتوح فعلاً مهما كان عددها.
CHANNEL_GROUP_FILL_GRACE_SECONDS = 2.0

# ── إعدادات قناة WHALES VIP الحيتان ──
WHALES_LOT = CHANNEL_POSITION_LOT
WHALES_SL_USD = CHANNEL_INITIAL_SL_USD
# كل صفقة من الخمس تُدار وحدها: هدف خمس درجات ووقف ست درجات من
# دخولها. أهداف التوصية تُقرأ للتحقق فقط ولا تُدير الصفقات.
WHALES_FIXED_TP_USD = 5.0
WHALES_FIXED_SL_USD = 6.0

# ── توزيع الدخول على منطقة الحيتان ──
# القناة ترسل رسالتين: "Buy Gold Now" ثم رسالة المنطقة والأرقام.
# لا نفتح شيئاً على الرسالة الأولى؛ الدخول كله من رسالة المنطقة.
# المنطقة (مثال 4231-4226) تُقسم إلى خمسة مستويات بمسافة دولار واحد،
# تبدأ من الطرف الأفضل: الأدنى للشراء والأعلى للبيع.
# لا توضع أوامر معلقة عند الوسيط — البوت يراقب السعر ويفتح سوقياً عند كل مستوى.
ZONE_LEVEL_COUNT = CHANNEL_POSITION_COUNT
ZONE_LEVEL_STEP_USD = 1.0
ZONE_EXPIRY_SECONDS = 24 * 60 * 60
ZONE_TP_SANITY_USD = 200.0  # سلم أهداف الحيتان يمتد بعيداً (Tp3 قد يبعد +$90)
# مراقب المستويات يعمل في خيط مستقل سريع حتى لا يتأخر خلف الإدارة الثقيلة.
# الدخول عند وصول التوصية فوري ومباشر؛ هذا الفاصل للمستويات اللاحقة فقط.
ZONE_WATCH_INTERVAL_SECONDS = 0.05
ZONE_IDLE_INTERVAL_SECONDS = 0.5  # لا مجموعات نشطة — لا داعي لإرهاق MT5

# ── إعدادات قناة KINGS EL GOLD VIP ──
KINGS_LOT = CHANNEL_POSITION_LOT
KINGS_SL_USD = CHANNEL_INITIAL_SL_USD

# ── إعدادات بوت توصيات الذهب (n8n) ──
# رسالة واحدة مكتملة: القرار والدخول والوقف والهدف. لا نأخذ سعر
# الدخول المكتوب أبداً — قد يكون مضى عليه دقائق — بل نأخذ المسافتين
# (خطر/ربح) ونقيسهما من سعر التنفيذ الفعلي.
GOLDBOT_LOT = 0.05
GOLDBOT_MAX_RISK_USD = 20.0   # أبعد من ذلك: خطأ قراءة أو توصية لا يحتملها الحساب
GOLDBOT_MIN_RISK_USD = 0.5

CHANNEL_TITLE_ALLOWLIST = {
    "kings el gold vip": "kings",
    "whales vip | الحيتان": "whales",
    # أسماء محتملة لقناة بوت التوصيات. وإن اختلف الاسم فالقارئ يرشّح
    # أي محادثة مثبتة أخرى إلى هذه القناة، ولا تُنفَّذ منها إلا رسالة
    # بصيغة التوصية بالضبط (القرار + الوقف + الهدف).
    "booooooootttttt": "goldbot",
    "توصية الذهب": "goldbot",
    "gold signal bot": "goldbot",
}
# القناتان اللتان لا يعمل القارئ بدونهما. بوت التوصيات اختياري: إن
# ثُبّتت قناته عمل، وإن لم تُثبّت لم يمنع البوت من العمل.
REQUIRED_CHANNELS = {"kings", "whales"}
# المحادثة المثبتة غير المعروفة تُرشَّح لبوت التوصيات — فيكفي أن
# يثبّت صاحب الحساب القناة الجديدة دون أن نعرف اسمها مسبقاً.
FALLBACK_CHANNEL = "goldbot"
ACTIVE_CHANNEL_MAGICS = {MAGIC_KINGS, MAGIC_WHALES, MAGIC_GOLDBOT}
CHANNEL_MAGICS = {
    "whales": MAGIC_WHALES,
    "kings": MAGIC_KINGS,
    "goldbot": MAGIC_GOLDBOT,
}
# سقف صارم لكل قناة: القناة قد ترسل توصيتين خلال دقائق، ولا نريد
# أن تتضاعف الصفقات. التوصية الجديدة تُرفض ما لم تتسع تحت السقف.
CHANNEL_MAX_OPEN_POSITIONS = 5

# ── الصفقات اليدوية ──
# ما يفتحه صاحب الحساب بنفسه في MT5 (بلا Magic البوت). يضبط لها البوت
# وقفاً وهدفاً فور رؤيتها، وينقل الوقف إلى الدخول عند بلوغ ربح التأمين.
MANUAL_SL_USD = 6.0
# خمس درجات دائماً بطلب صاحب الحساب. وهي أبعد من حد نقل الوقف ($3)
# فيبقى للتأمين معنى: الوقف ينتقل للدخول ثم تكمل الصفقة إلى هدفها.
MANUAL_TP_USD = 5.0
MANUAL_BREAKEVEN_USD = 3.0

# ── ما يختلف بين القنوات ──
# الأساس واحد (خمس صفقات 0.01، وقف $6، تأمين عند +$3 وإبقاء اثنتين
# على وقف الدخول). ما يلي يغطي ما تنفرد به كل قناة عن هذا الأساس.
# entry_mode يحدد متى تُفتح الصفقات الخمس:
#   zone_levels — توزيع على المنطقة: صفقة عند لمس كل مستوى (الحيتان)
#   immediate   — فوراً بسعر السوق مهما كان، بلا انتظار (KINGS)
#   zone_wait   — انتظار دخول السعر المنطقة ثم فتح الخمس دفعة واحدة
CHANNEL_POLICIES = {
    # الحيتان: يرسل منطقة دخول، فنوزع عليها خمسة مستويات بمسافة دولار.
    # وكل صفقة من الخمس مستقلة تماماً: هدفها $5 ووقفها $6 من دخولها
    # هي. لا سلم أهداف ولا إغلاق جزئي ولا تتبع — بطلب صاحب الحساب.
    "whales": {
        "entry_mode": "zone_levels",
        "fixed_tp_usd": WHALES_FIXED_TP_USD,
        "fixed_sl_usd": WHALES_FIXED_SL_USD,
    },
    # KINGS: المدى المكتوب (4634-4635) إشارة لا منطقة — دخول فوري.
    # وينفّذ على رسالة الاتجاه نفسها ("خد شراء الان") دون انتظار
    # الأرقام؛ الأرقام حين تصل تُربط بالمجموعة المفتوحة.
    # صفقة واحدة 0.10 لا أكثر مهما قالت القناة "مرتين" أو "ثلاث مرات".
    # الوقف $6 عند التنفيذ الفوري، فإذا وصلت الأرقام انتقل إلى درجة
    # خلف ستوب التوصية المكتوب. والصفقة تخرج عند الهدف الأول.
    "kings": {
        "entry_mode": "immediate",
        "opens_on_direction": True,
        "position_count": 1,
        "position_lot": 0.10,
        "max_units": 1,
        "exit_all_at_tp1": True,
        "signal_sl_buffer_usd": 1.0,
    },
    # بوت التوصيات: رسالة واحدة مكتملة → صفقة واحدة 0.05 فوراً،
    # ووقفها وهدفها مسافتا التوصية نفسها مقيستين من سعر التنفيذ.
    "goldbot": {
        "entry_mode": "immediate",
        "position_count": 1,
        "position_lot": GOLDBOT_LOT,
        "max_units": 1,
    },
}


def channel_policy(channel, key):
    """قيمة القناة إن خالفت الأساس، وإلا القيمة الموحدة."""
    defaults = {
        "entry_mode": "immediate",
        "opens_on_direction": False,
        "target_lock_usd": CHANNEL_TARGET_LOCK_USD,
        "position_count": CHANNEL_POSITION_COUNT,
        "position_lot": CHANNEL_POSITION_LOT,
        "max_units": 1,
        "exit_all_at_tp1": False,
        "signal_sl_buffer_usd": 0.0,
        "target_approach_usd": CHANNEL_TARGET_APPROACH_USD,
        "initial_sl_usd": CHANNEL_INITIAL_SL_USD,
        "trail_after_last_usd": CHANNEL_TRAIL_AFTER_LAST_USD,
        # مسافة ثابتة لكل صفقة على حدة بدل سلم الأهداف المشترك.
        # صفر = لا مسافة ثابتة، فتُدار المجموعة بأهداف التوصية.
        "fixed_tp_usd": 0.0,
        "fixed_sl_usd": 0.0,
    }
    return CHANNEL_POLICIES.get(channel, {}).get(key, defaults[key])


def exit_plan_line(channel):
    """سطر يشرح خطة الخروج المطبَّقة على هذه القناة — للتنبيهات."""
    fixed_tp = channel_policy(channel, "fixed_tp_usd")
    if fixed_tp:
        fixed_sl = (
            channel_policy(channel, "fixed_sl_usd")
            or channel_policy(channel, "initial_sl_usd")
        )
        return (
            f"🎯 كل صفقة مستقلة: هدف ${fixed_tp:g} ووقف ${fixed_sl:g} "
            "من دخولها — لا سلم أهداف\n"
        )
    if channel_policy(channel, "exit_all_at_tp1"):
        return "🎯 كل الصفقات تخرج عند الهدف الأول\n"
    return (
        "🎯 صفقتان تخرجان عند الهدف الأول ووقف الباقيات ينتقل للدخول، "
        "وصفقتان عند الثاني ووقف الأخيرة يقفل على الأول\n"
        f"🎯 الهدف ينتقل عند اقتراب "
        f"${channel_policy(channel, 'target_approach_usd'):g}، والوقف يقفل "
        f"على الهدف بعد تجاوزه ${channel_policy(channel, 'target_lock_usd'):g}\n"
    )


PENDING_EXPIRY_SECONDS = 24 * 60 * 60
PROCESSED_SIGNALS_FILE = "processed_telegram_signals.json"
CHANNEL_QUARANTINE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "channel_cleanup_quarantine.json",
)

# ── إعدادات الاستراتيجيات الداخلية (تعمل دائماً) ──
STRAT_LOT = 0.01
STRAT_SL_PIPS = 50  # $5
STRAT_TP_PIPS = 100  # $10

# ── محاكي القنوات (التعلم من التوصيات) ──
MAGIC_MIMIC = 20260817
MAGIC_LONDON = 20260818  # استراتيجية اختراق افتتاح لندن
STRAT_SCORES_FILE = "strategy_scores.json"  # سجل أداء الاستراتيجيات (للحذف بعد 3 خسائر)
MIMIC_LOT = 0.02
MIMIC_SL_USD = 5.0
MIMIC_TP_USD = 10.0
LESSONS_FILE = "channel_lessons.json"

# الأنماط
STRONG_PIPS = 60
LOOKAHEAD = 8
HISTORY_BARS = 4000
MIN_REPEATS = 3
MIN_WIN_RATE = 55.0
SCAN_INTERVAL = 60

# التعلم الذاتي
LEARN_FILE = "learning_data.json"
MIN_SCORE_BOOK = 8  # الحد الأدنى لنقاط استراتيجيات الكتاب (يتعدل ذاتياً)

FINGERPRINT_TFS = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
}

def utc_now():
    """توقيت UTC ساذج — بديل datetime.utcnow() المهملة في بايثون 3.12+."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_from_timestamp(ts):
    """تحويل طابع زمني إلى UTC ساذج — بديل utcfromtimestamp المهملة."""
    return datetime.fromtimestamp(float(ts), timezone.utc).replace(tzinfo=None)


SHAPE_FULL = {
    "D": "⚖️ Doji",
    "BM": "🟢 Marubozu صعودي",
    "SM": "🔴 Marubozu هبوطي",
    "BP": "📌 Pin Bar صعودي",
    "SP": "📌 Pin Bar هبوطي",
    "BS": "💚 صعودية قوية",
    "SS": "❤️ هبوطية قوية",
    "BW": "🔼 صعودية ضعيفة",
    "SW": "🔽 هبوطية ضعيفة",
}


# ═════════════════════════════════════════════
#  الجزء ١ — تصنيف الشموع والأنماط
# ═════════════════════════════════════════════
def classify(c) -> str:
    o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
    rng = h - l
    if rng < 0.01:
        return "D"
    body = abs(cl - o)
    uw, lw = h - max(o, cl), min(o, cl) - l
    bp, bull = body / rng, cl > o
    if bp < 0.12:
        return "D"
    if bp > 0.85:
        return "BM" if bull else "SM"
    if lw > body * 2.2 and uw < body * 0.6:
        return "BP"
    if uw > body * 2.2 and lw < body * 0.6:
        return "SP"
    if bp > 0.55:
        return "BS" if bull else "SS"
    return "BW" if bull else "SW"


def get_fingerprint_at(symbol, ts):
    parts = []
    dt = utc_from_timestamp(ts)
    for tf_name, tf_const in FINGERPRINT_TFS.items():
        candles = mt5.copy_rates_from(symbol, tf_const, dt, 2)
        parts.append(
            f"{tf_name}:{classify(candles[-1]) if candles is not None and len(candles) else '?'}"
        )
    return "|".join(parts)


def get_live_fingerprint(symbol):
    parts = []
    for tf_name, tf_const in FINGERPRINT_TFS.items():
        candles = mt5.copy_rates_from_pos(symbol, tf_const, 0, 2)
        parts.append(
            f"{tf_name}:{classify(candles[-1]) if candles is not None and len(candles) else '?'}"
        )
    return "|".join(parts)


def fp_arabic(fp):
    lines = []
    for part in fp.split("|"):
        if ":" in part:
            tf, code = part.split(":", 1)
            lines.append(f"   <b>{tf}:</b> {SHAPE_FULL.get(code, code)}")
    return "\n".join(lines)


def build_pattern_db(symbol):
    print(f"[🔬] تحليل {HISTORY_BARS} شمعة H1 — انتظر بضع دقائق...")
    ch1 = mt5.copy_rates_from_pos(
        symbol, mt5.TIMEFRAME_H1, 0, HISTORY_BARS + LOOKAHEAD + 5
    )
    if ch1 is None or len(ch1) < 50:
        return {}
    ch1 = list(ch1)
    total = len(ch1) - LOOKAHEAD - 1
    db = defaultdict(lambda: {"total": 0, "up": 0, "down": 0, "up_p": [], "down_p": []})
    for i in range(total):
        fp = get_fingerprint_at(symbol, int(ch1[i]["time"]))
        base = ch1[i]["close"]
        ahead = ch1[i + 1 : i + 1 + LOOKAHEAD]
        up = round((max(c["high"] for c in ahead) - base) / 0.1)
        down = round((base - min(c["low"] for c in ahead)) / 0.1)
        st = db[fp]
        st["total"] += 1
        st["up_p"].append(up)
        st["down_p"].append(down)
        if up >= STRONG_PIPS:
            st["up"] += 1
        if down >= STRONG_PIPS:
            st["down"] += 1
        if (i + 1) % 200 == 0:
            print(f"   [{(i + 1) / total * 100:5.1f}%] {i + 1}/{total}")
    print(f"[✅] أنماط مكتشفة: {len(db)}")
    return dict(db)


def reliable_patterns(db):
    out = []
    for fp, st in db.items():
        t = st["total"]
        if t < MIN_REPEATS:
            continue
        ur, dr = st["up"] / t * 100, st["down"] / t * 100
        best = max(ur, dr)
        if best < MIN_WIN_RATE:
            continue
        d = "BUY" if ur >= dr else "SELL"
        avg = sum(st["up_p"]) / t if d == "BUY" else sum(st["down_p"]) / t
        out.append({"fp": fp, "direction": d, "rate": best, "total": t, "avg": avg})
    out.sort(key=lambda x: (x["rate"], x["total"]), reverse=True)
    return out


# ═════════════════════════════════════════════
#  الجزء ٢ — التعلم الذاتي
# ═════════════════════════════════════════════
class Learner:
    """يتتبع نتائج الصفقات ويعدل الإعدادات تلقائياً."""

    def __init__(self):
        self.data = {
            "trades": [],  # سجل الصفقات المغلقة
            "pattern_stats": {},  # نجاح كل نمط فعلياً
            "blocked_patterns": [],  # أنماط خسرت 3+ مرات متتالية → محظورة
            "min_score": MIN_SCORE_BOOK,
        }
        self.load()

    def load(self):
        try:
            if os.path.exists(LEARN_FILE):
                with open(LEARN_FILE, "r", encoding="utf-8") as f:
                    self.data.update(json.load(f))
                print(
                    f"[🧠] تم تحميل الذاكرة | صفقات محفوظة: {len(self.data['trades'])}"
                )
        except Exception as e:
            print(f"[🧠] ذاكرة جديدة ({e})")

    def save(self):
        try:
            tmp = LEARN_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, LEARN_FILE)  # كتابة ذرية — لا يتلف الملف عند انقطاع
        except Exception as e:
            print(f"[🧠] خطأ حفظ: {e}")

    def record_trade(self, source, direction, fp, profit, hour=None):
        """يسجل صفقة مغلقة ويتعلم منها — ويحلل سبب الخسارة."""
        if hour is None:
            hour = datetime.now().hour
        self.data["trades"].append(
            {
                "time": datetime.now().isoformat(),
                "source": source,
                "direction": direction,
                "fp": fp,
                "profit": profit,
                "hour": hour,
            }
        )

        # ── إحصائيات الساعة (متى يخسر البوت؟) ──
        hs = self.data.setdefault("hour_stats", {}).setdefault(
            str(hour), {"wins": 0, "losses": 0}
        )
        if profit > 0:
            hs["wins"] += 1
        else:
            hs["losses"] += 1
        # حظر ساعة سيئة: 5+ صفقات ونسبة نجاح أقل من 35%
        bad_hours = self.data.setdefault("bad_hours", [])
        total_h = hs["wins"] + hs["losses"]
        if (
            total_h >= 5
            and hs["wins"] / total_h < 0.35
            and hour not in bad_hours
        ):
            bad_hours.append(hour)
            print(f"[🧠] ⛔ الساعة {hour}:00 محظورة — البوت يخسر فيها كثيراً!")

        # ── إحصائيات الاتجاه لكل نظام (هل الشراء أم البيع يخسر؟) ──
        dkey = f"{source}|{direction}"
        ds = self.data.setdefault("dir_stats", {}).setdefault(
            dkey, {"wins": 0, "losses": 0}
        )
        if profit > 0:
            ds["wins"] += 1
        else:
            ds["losses"] += 1

        # تحديث إحصائيات النمط
        if fp:
            ps = self.data["pattern_stats"].setdefault(
                fp, {"wins": 0, "losses": 0, "streak_loss": 0}
            )
            if profit > 0:
                ps["wins"] += 1
                ps["streak_loss"] = 0
            else:
                ps["losses"] += 1
                ps["streak_loss"] += 1
                # حظر النمط بعد 3 خسائر متتالية
                if ps["streak_loss"] >= 3 and fp not in self.data["blocked_patterns"]:
                    self.data["blocked_patterns"].append(fp)
                    print(f"[🧠] ⛔ نمط محظور بعد 3 خسائر متتالية!")

        # تعديل الحد الأدنى للنقاط حسب الأداء العام
        recent = self.data["trades"][-20:]
        if len(recent) >= 10:
            wins = sum(1 for t in recent if t["profit"] > 0)
            win_rate = wins / len(recent)
            if win_rate < 0.4:
                self.data["min_score"] = min(12, self.data["min_score"] + 1)
                print(
                    f"[🧠] 📈 رفع الحد الأدنى إلى {self.data['min_score']} (نسبة نجاح منخفضة)"
                )
            elif win_rate > 0.6:
                self.data["min_score"] = max(6, self.data["min_score"] - 1)
                print(
                    f"[🧠] 📉 خفض الحد الأدنى إلى {self.data['min_score']} (أداء جيد)"
                )

        self.save()

    def is_blocked(self, fp):
        return fp in self.data["blocked_patterns"]

    def is_bad_hour(self, hour=None):
        """هل هذه ساعة يخسر فيها البوت عادةً؟"""
        if hour is None:
            hour = datetime.now().hour
        return hour in self.data.get("bad_hours", [])

    def loss_reason(self, source, direction, fp, hour):
        """يحلل لماذا خسرت الصفقة ويعيد شرحاً بالعربي."""
        reasons = []

        # ١- النمط نفسه ضعيف؟
        if fp:
            ps = self.data["pattern_stats"].get(fp)
            if ps:
                tot = ps["wins"] + ps["losses"]
                if tot >= 2 and ps["losses"] > ps["wins"]:
                    reasons.append(
                        f"هذا النمط خسر {ps['losses']} من {tot} مرات"
                    )
                if ps["streak_loss"] >= 3:
                    reasons.append("⛔ تم حظر النمط نهائياً (3 خسائر متتالية)")
                elif ps["streak_loss"] == 2:
                    reasons.append("⚠️ خسارة أخرى وسيُحظر هذا النمط")

        # ٢- الساعة سيئة؟
        hs = self.data.get("hour_stats", {}).get(str(hour))
        if hs:
            tot = hs["wins"] + hs["losses"]
            if tot >= 3 and hs["losses"] > hs["wins"]:
                reasons.append(
                    f"الساعة {hour}:00 خاسرة ({hs['losses']} من {tot})"
                )
        if hour in self.data.get("bad_hours", []):
            reasons.append(f"⛔ تم حظر التداول في الساعة {hour}:00")

        # ٣- الاتجاه ضعيف لهذا النظام؟
        ds = self.data.get("dir_stats", {}).get(f"{source}|{direction}")
        if ds:
            tot = ds["wins"] + ds["losses"]
            if tot >= 4 and ds["wins"] / tot < 0.35:
                dir_ar = "الشراء" if direction == "BUY" else "البيع"
                reasons.append(
                    f"{dir_ar} من هذا النظام ضعيف ({ds['wins']} ربح من {tot})"
                )

        if not reasons:
            return "السوق تحرك عكس الصفقة — لا نمط واضح للخطأ بعد، أراقب وأجمع البيانات"
        return " • ".join(reasons)

    def get_min_score(self):
        return self.data["min_score"]

    def summary(self):
        trades = self.data["trades"]
        if not trades:
            return "لا توجد صفقات بعد"
        wins = sum(1 for t in trades if t["profit"] > 0)
        total_profit = sum(t["profit"] for t in trades)
        return (
            f"صفقات: {len(trades)} | ربح: {wins} | "
            f"خسارة: {len(trades) - wins} | صافي: ${total_profit:.2f} | "
            f"أنماط محظورة: {len(self.data['blocked_patterns'])}"
        )


learner = Learner()
_open_trades = {}  # ticket -> {'source', 'fp', 'direction'}
_trades_lock = threading.Lock()
_channel_runtime_mode = {
    "enabled": False,
    "account_login": None,
    "allow_demo": False,  # لا يُفتح إلا بـ --demo عند التشغيل
}
_demo_channels_mode = _channel_runtime_mode  # اسم توافق داخلي قديم
_runtime_safety = {"suspended": False}


def allowed_gold_symbol(symbol):
    """الرمز الوحيد المسموح التداول عليه: ما بدأ به البوت هذه الجلسة.

    يُثبَّت في _channel_runtime_mode عند التشغيل (من --symbol أو الافتراضي)،
    فلا يتداول البوت على رمز غير الذي أقلعت عليه الجلسة."""
    active = _channel_runtime_mode.get("symbol") or DEFAULT_SYMBOL
    return symbol == active or (
        not _channel_runtime_mode["enabled"] and symbol in (DEFAULT_SYMBOL, "XAUUSD")
    )


def is_live_account(account, terminal, real_constant, expected_login=None):
    """فحص مغلق افتراضياً: حساب حقيقي متصل ومصرّح، وبنفس الدخول عند تحديده."""
    if account is None or terminal is None or real_constant is None:
        return False
    account_mode = getattr(account, "trade_mode", None)
    account_login = getattr(account, "login", None)
    account_allowed = getattr(account, "trade_allowed", None)
    terminal_connected = getattr(terminal, "connected", None)
    terminal_allowed = getattr(terminal, "trade_allowed", None)
    return (
        account_mode == real_constant
        and (expected_login is None or account_login == expected_login)
        and account_allowed is True
        and terminal_connected is True
        and terminal_allowed is True
    )


def live_account_ready():
    """حارس مركزي للحساب المسموح: حقيقي دائماً، وتجريبي في وضع --demo.

    وضع التجربة لا يُفتح إلا بكتابة --demo صراحة عند التشغيل، فالتشغيل
    العادي يبقى محصوراً بالحساب الحقيقي الذي بدأ عليه البوت."""
    real_constant = getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", None)
    demo_constant = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
    allowed = [real_constant]
    if _channel_runtime_mode.get("allow_demo"):
        allowed.append(demo_constant)
    try:
        account = mt5.account_info()
        terminal = mt5.terminal_info()
        return any(
            is_live_account(
                account,
                terminal,
                mode,
                _channel_runtime_mode.get("account_login"),
            )
            for mode in allowed
            if mode is not None
        )
    except Exception as exc:
        print(f"[LIVE-GUARD] ❌ تعذر التحقق من الحساب: {exc}")
        return False


def is_demo_account(account, terminal, demo_constant):
    """دالة توافق للاختبارات القديمة؛ التشغيل الفعلي يستخدم حارس الحساب الحقيقي."""
    if account is None or terminal is None or demo_constant is None:
        return False
    return bool(
        getattr(account, "trade_mode", None) == demo_constant
        and getattr(account, "trade_allowed", None) is True
        and getattr(terminal, "connected", None) is True
        and getattr(terminal, "trade_allowed", None) is True
    )


def demo_account_ready():
    """اسم توافق قديم؛ يتحقق فعلياً من الحساب الحقيقي المثبت عند التشغيل."""
    return live_account_ready()


def hedging_account_ready(account=None):
    """الخمس صفقات المنفصلة تتطلب حساب MT5 من نوع Retail Hedging."""
    hedging_constant = getattr(mt5, "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", None)
    try:
        account = account or mt5.account_info()
        return bool(
            account is not None
            and hedging_constant is not None
            and getattr(account, "margin_mode", None) == hedging_constant
        )
    except Exception as exc:
        print(f"[HEDGING-GUARD] ❌ تعذر التحقق من نوع الحساب: {exc}")
        return False


def require_live_account(operation, allow_suspended=False):
    """يمنع أي أمر أو تعديل إذا فقد البوت الحساب الحقيقي الذي بدأ عليه."""
    if not _channel_runtime_mode["enabled"]:
        return True
    if _runtime_safety["suspended"] and not allow_suspended:
        print(f"[LIVE-GUARD] ⛔ {operation}: التشغيل معلّق حتى اكتمال فحص الاستعادة")
        return False
    if live_account_ready():
        return True
    print(f"[LIVE-GUARD] ⛔ رُفضت العملية ({operation}) — الحساب الحقيقي غير مطابق أو غير آمن")
    return False


def require_demo_account(operation, allow_suspended=False):
    """اسم توافق قديم لمسارات الإدارة؛ الحارس الفعلي هو حارس الحساب الحقيقي."""
    return require_live_account(operation, allow_suspended)


# ═════════════════════════════════════════════
#  محاكي القنوات — يتعلم من توصيات القنوات
# ═════════════════════════════════════════════
def chart_features(symbol):
    """يلتقط 'صورة' للشارت الآن: الاتجاه، الزخم، التذبذب، الشموع، الساعة."""
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 24)
        if rates is None or len(rates) < 24:
            return None
        closes = [float(r["close"]) for r in rates]
        sma = sum(closes) / len(closes)
        last = closes[-1]
        rng = max(float(r["high"]) for r in rates[-12:]) - min(
            float(r["low"]) for r in rates[-12:]
        )
        bull6 = sum(1 for r in rates[-6:] if r["close"] > r["open"])
        return {
            "trend": "UP" if last > sma else "DOWN",
            "mom": round(last - closes[-4], 2),
            "range": round(rng, 2),
            "bull6": bull6,
            "hour": datetime.now().hour,
        }
    except Exception:
        return None


class ChannelLearner:
    """يسجل عند كل توصية قناة: شكل الشارت وقت الدخول + النتيجة بعد الإغلاق.
    بعد تجميع دروس كافية يستطيع البوت اقتراح صفقات بنفس أسلوب القنوات
    (وضع المحاكي — يعمل تلقائياً إذا لم توجد القنوات، أو بـ --solo)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.data = {"lessons": []}
        try:
            if os.path.exists(LESSONS_FILE):
                with open(LESSONS_FILE, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
        except Exception:
            pass

    def _save(self):
        try:
            tmp = LESSONS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, LESSONS_FILE)
        except Exception:
            pass

    def add(self, ticket, channel, direction, symbol):
        feats = chart_features(symbol)
        if not feats:
            return
        with self.lock:
            self.data["lessons"].append({
                "ticket": ticket, "channel": channel,
                "direction": direction, "features": feats,
                "profit": None, "time": time.time(),
            })
            self._save()
        print(f"[🎓] درس جديد من {channel}: {direction} | {feats}")

    def close(self, ticket, profit):
        with self.lock:
            for l in self.data["lessons"]:
                if l["ticket"] == ticket and l["profit"] is None:
                    l["profit"] = round(float(profit), 2)
                    self._save()
                    print(f"[🎓] اكتمل الدرس #{ticket}: ${profit:.2f}")
                    break

    def _similar(self, a, b):
        return (
            a["trend"] == b["trend"]
            and abs(a["mom"] - b["mom"]) <= 2.0
            and abs(a["bull6"] - b["bull6"]) <= 2
            and abs(a["hour"] - b["hour"]) <= 3
        )

    def stats(self):
        with self.lock:
            closed = [l for l in self.data["lessons"] if l["profit"] is not None]
            return len(self.data["lessons"]), len(closed)

    def suggest(self, symbol):
        """يرجع اتجاهاً مقترحاً إذا كان الشارت الآن يشبه دروساً رابحة سابقة."""
        feats = chart_features(symbol)
        if not feats:
            return None
        with self.lock:
            closed = [l for l in self.data["lessons"] if l["profit"] is not None]
        if len(closed) < 10:
            return None  # لم نتعلم بما يكفي بعد
        for direction in ("BUY", "SELL"):
            similar = [
                l for l in closed
                if l["direction"] == direction and self._similar(l["features"], feats)
            ]
            if len(similar) >= 5:
                wins = sum(1 for l in similar if l["profit"] > 0)
                rate = wins / len(similar) * 100
                if rate >= 60:
                    return {"direction": direction, "count": len(similar),
                            "rate": rate}
        return None


channel_learner = ChannelLearner()


# ═════════════════════════════════════════════
#  قاتل الاستراتيجيات الخاسرة — 3 خسائر متتالية = حذف نهائي
# ═════════════════════════════════════════════
class StrategyKiller:
    """يتابع أداء كل استراتيجية داخلية.
    3 خسائر متتالية → تُحذف الاستراتيجية نهائياً (حتى بعد إعادة التشغيل)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}  # name -> {"streak": n, "dead": bool, "wins": n, "losses": n}
        try:
            if os.path.exists(STRAT_SCORES_FILE):
                with open(STRAT_SCORES_FILE, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
        except Exception:
            pass

    def _save(self):
        try:
            tmp = STRAT_SCORES_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, STRAT_SCORES_FILE)
        except Exception:
            pass

    def alive(self, name):
        with self.lock:
            return not self.data.get(name, {}).get("dead", False)

    def record(self, name, profit):
        with self.lock:
            s = self.data.setdefault(
                name, {"streak": 0, "dead": False, "wins": 0, "losses": 0}
            )
            if profit > 0:
                s["wins"] += 1
                s["streak"] = 0
            else:
                s["losses"] += 1
                s["streak"] += 1
                if s["streak"] >= 3 and not s["dead"]:
                    s["dead"] = True
                    self._save()
                    return True  # أُعدمت الآن
            self._save()
        return False

    def summary_ar(self):
        with self.lock:
            lines = []
            for name, s in self.data.items():
                st = "☠️ محذوفة" if s["dead"] else f"سلسلة خسائر: {s['streak']}/3"
                lines.append(f"• {name}: ربح {s['wins']} / خسارة {s['losses']} — {st}")
            return "\n".join(lines) if lines else "لا بيانات بعد"


strategy_killer = StrategyKiller()


def h1_trend(symbol):
    """اتجاه الفريم الساعة: EMA20 مقابل EMA50 — أهم فلتر في استراتيجيات الذهب الناجحة."""
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 60)
        if rates is None or len(rates) < 55:
            return None
        closes = [float(r["close"]) for r in rates]

        def ema(vals, n):
            k = 2 / (n + 1)
            e = vals[0]
            for v in vals[1:]:
                e = v * k + e * (1 - k)
            return e

        e20, e50 = ema(closes, 20), ema(closes, 50)
        if e20 > e50 * 1.0003:
            return "BUY"
        if e20 < e50 * 0.9997:
            return "SELL"
        return None  # سوق عرضي — لا اتجاه واضح
    except Exception:
        return None


def london_breakout_signal(symbol):
    """استراتيجية اختراق افتتاح لندن (من أنجح استراتيجيات الذهب):
    نحسب مدى الجلسة الآسيوية (01-08 GMT)، وبعد فتح لندن (08-11 GMT)
    نتداول مع الاختراق إذا وافق اتجاه H1."""
    try:
        now_gmt = utc_now()
        if not (8 <= now_gmt.hour < 11):
            return None
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 60)
        if rates is None or len(rates) < 40:
            return None
        asian = [
            r for r in rates
            if 1 <= utc_from_timestamp(int(r["time"])).hour < 8
            and utc_from_timestamp(int(r["time"])).date() == now_gmt.date()
        ]
        if len(asian) < 12:
            return None
        hi = max(float(r["high"]) for r in asian)
        lo = min(float(r["low"]) for r in asian)
        if hi - lo > 25:  # مدى آسيوي واسع جداً — يوم متقلب، لا اختراق نظيف
            return None
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None
        if tick.bid > hi + 1.0:
            return "BUY"
        if tick.bid < lo - 1.0:
            return "SELL"
        return None
    except Exception:
        return None


def loss_autopsy(symbol, info, profit):
    """🔬 تشريح الخسارة — تحليل ذكي ودقيق لسبب خسارة الصفقة."""
    findings = []
    try:
        direction = info.get("direction", "?")
        entry = info.get("entry")
        is_buy = direction == "BUY"

        # ١) هل تداولنا ضد اتجاه الفريم الساعة؟
        trend = h1_trend(symbol)
        if trend and trend != direction:
            findings.append(
                f"⚠️ <b>ضد التيار:</b> اتجاه الساعة H1 كان "
                f"{'صاعداً 📈' if trend == 'BUY' else 'هابطاً 📉'} "
                f"وأنت دخلت {'شراء' if is_buy else 'بيع'} — أخطر خطأ في تداول الذهب"
            )
        elif trend == direction:
            findings.append("✅ الاتجاه العام كان معك — الخسارة من التوقيت وليس الاتجاه")

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 36)
        if rates is not None and len(rates) >= 12 and entry:
            closes = [float(r["close"]) for r in rates]
            highs = [float(r["high"]) for r in rates]
            lows = [float(r["low"]) for r in rates]

            # ٢) هل كان السوق متقلباً بعنف (خبر اقتصادي)؟
            recent_range = max(highs[-12:]) - min(lows[-12:])
            if recent_range > 15:
                findings.append(
                    f"💥 <b>تقلب عنيف:</b> السوق تحرك ${recent_range:.0f} خلال ساعة — "
                    f"غالباً خبر اقتصادي. الستوب الصغير لا يصمد في هذه اللحظات"
                )

            # ٣) هل ذهب السعر معنا أولاً ثم انعكس (كاد يربح)؟
            # الأصل هو ما رصده المتتبع وهي مفتوحة: قراءة الشموع تغطي
            # ساعة كاملة قد تسبق الدخول أو تلي الخروج، فكانت تنسب
            # للصفقة حركة لم تعشها وتناقض سطر "أقصى ربح" في التقرير.
            tracked_peak = info.get("peak_move")
            best = (
                float(tracked_peak)
                if tracked_peak is not None
                else (max(highs[-12:]) - entry) if is_buy
                else (entry - min(lows[-12:]))
            )
            if best > 3:
                findings.append(
                    f"😤 <b>كادت تربح:</b> السعر تحرك معك ${best:.1f} قبل أن ينعكس — "
                    f"المشكلة في الهدف البعيد، ليس في الدخول"
                )
            elif best < 1:
                findings.append(
                    "🚫 <b>دخول خاطئ من اللحظة الأولى:</b> السعر لم يتحرك معك "
                    "إطلاقاً — الإشارة كانت متأخرة أو معاكسة"
                )

            # ٤) هل دخلنا في قمة/قاع مؤقت (مطاردة السعر)؟
            if entry:
                pos_in_range = (entry - min(lows)) / max(max(highs) - min(lows), 0.01)
                if is_buy and pos_in_range > 0.85:
                    findings.append(
                        "🏔️ <b>اشتريت في القمة:</b> الدخول كان أعلى 85% من مدى "
                        "آخر 3 ساعات — مطاردة سعر بعد فوات الحركة"
                    )
                elif not is_buy and pos_in_range < 0.15:
                    findings.append(
                        "🕳️ <b>بعت في القاع:</b> الدخول كان أدنى 15% من مدى "
                        "آخر 3 ساعات — البيع بعد اكتمال الهبوط"
                    )

        # ٥) توقيت الجلسة
        gh = utc_now().hour
        if gh < 6 or gh >= 20:
            findings.append(
                "🌙 <b>توقيت ميت:</b> خارج جلسات لندن ونيويورك — سيولة ضعيفة "
                "وحركات عشوائية تصطاد الستوبات"
            )
    except Exception:
        pass
    if not findings:
        findings.append("🔍 لا سبب فني واضح — حركة سوق طبيعية ضد الصفقة")
    return "\n".join(findings)


def check_closed_trades(symbol):
    """يفحص الصفقات التي أُغلقت ويتعلم منها."""
    with _trades_lock:
        if not _open_trades:
            return
        tracked = list(_open_trades.keys())

    open_tickets = set()
    positions = mt5.positions_get(symbol=symbol)
    if positions:
        open_tickets = {p.ticket for p in positions}

    for ticket in tracked:
        if ticket in open_tickets:
            continue
        # لا نعتبرها مغلقة إلا إذا ظهرت في تاريخ الصفقات (تجنب التسجيل الخاطئ)
        deals = mt5.history_deals_get(position=ticket)
        if not deals:
            continue  # ربما لم تظهر بعد في MT5 — ننتظر الدورة القادمة
        with _trades_lock:
            info = _open_trades.pop(ticket, None)
        if info is None:
            continue
        profit = sum(d.profit for d in deals)
        channel_learner.close(ticket, profit)
        result = "✅ ربح" if profit > 0 else "❌ خسارة"
        print(f"[🧠] صفقة أُغلقت #{ticket} | {result} ${profit:.2f} — أتعلم منها...")
        trade_hour = info.get("hour", datetime.now().hour)
        learner.record_trade(
            info["source"], info["direction"], info.get("fp", ""), profit,
            hour=trade_hour,
        )
        src_ar = {
            "Pattern": "🕯️ نمط شموع",
            "TGSignal": "📌 توصية",
            "ChartPattern": "📐 نمط فني",
            "London": "🇬🇧 اختراق لندن",
            "Mimic": "🤖 المحاكي",
        }.get(info["source"], "📚 استراتيجية")

        # ⚔️ قاتل الاستراتيجيات: 3 خسائر متتالية = حذف نهائي
        if info["source"] in ("Pattern", "ChartPattern", "BookStrategy", "London", "Mimic"):
            executed = strategy_killer.record(info["source"], profit)
            if executed:
                send_tg(
                    f"☠️ <b>استراتيجية حُذفت نهائياً!</b>\n\n"
                    f"{src_ar} خسرت 3 مرات متتالية — لن تتداول مرة أخرى أبداً.\n\n"
                    f"📊 <b>سجل الاستراتيجيات:</b>\n{strategy_killer.summary_ar()}"
                )
        msg = (
            f"{'🟢' if profit > 0 else '🔴'} <b>صفقة أُغلقت</b>\n\n"
            f"{result}: <b>${profit:.2f}</b>\n"
            f"النوع: {src_ar} | {'شراء' if info['direction'] == 'BUY' else 'بيع'}\n"
        )
        if profit <= 0:
            reason = learner.loss_reason(
                info["source"], info["direction"], info.get("fp", ""), trade_hour
            )
            autopsy = loss_autopsy(symbol, info, profit)
            msg += (
                f"\n🔬 <b>تشريح الخسارة:</b>\n{autopsy}\n"
                f"\n🔎 <b>من سجل التعلم:</b>\n{reason}\n"
            )
        msg += f"\n🧠 {learner.summary()}"
        send_tg(msg)


# ═════════════════════════════════════════════
#  الجزء ٣ — تنفيذ الصفقات
# ═════════════════════════════════════════════
def open_trade(
    symbol,
    direction,
    lot,
    sl_price=0.0,
    tp_price=0.0,
    sl_pips=0,
    tp_pips=0,
    magic=MAGIC_BOOK,
    comment="MasterBot",
    fp="",
    meta=None,
    sl_usd=0.0,
    return_position=False,
):
    if not require_live_account(comment):
        return None if return_position else False
    if _channel_runtime_mode["enabled"] and not allowed_gold_symbol(symbol):
        print(f"[SYMBOL-GUARD] ⛔ رُفض التداول على {symbol} — المسموح {DEFAULT_SYMBOL} فقط")
        return None if return_position else False

    # حارس الساعات القديمة لا يدخل في وضع القنوات الأربع المعزول.
    if not _channel_runtime_mode["enabled"] and learner.is_bad_hour():
        print(f"[MT5] ⛔ ساعة محظورة — رُفض فتح صفقة {comment}")
        return False

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"[MT5] ❌ لا سعر لـ {symbol}")
        return None if return_position else False
    before_tickets = {
        getattr(position, "ticket", None)
        for position in (mt5.positions_get(symbol=symbol) or [])
    } if return_position else set()

    price = tick.ask if direction == "BUY" else tick.bid

    if sl_usd:
        sl_price = (
            round(price - float(sl_usd), 2)
            if direction == "BUY"
            else round(price + float(sl_usd), 2)
        )

    # SL بالنقاط إذا لم يعطَ سعر
    pip = 0.1
    if not sl_price and sl_pips:
        sl_price = (
            round(price - sl_pips * pip, 2)
            if direction == "BUY"
            else round(price + sl_pips * pip, 2)
        )

    # TP بالنقاط إذا لم يعطَ سعر
    if not tp_price and tp_pips:
        tp_price = (
            round(price + tp_pips * pip, 2)
            if direction == "BUY"
            else round(price - tp_pips * pip, 2)
        )

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl_price or 0.0,
        "tp": tp_price or 0.0,
        "deviation": 20,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(req)

    # بعض البروكرات لا تقبل IOC — نجرب FOK ثم RETURN تلقائياً
    if result and result.retcode == 10030:  # Unsupported filling mode
        for filling in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
            req["type_filling"] = filling
            result = mt5.order_send(req)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                break

    partial_code = getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010)
    if result and result.retcode == partial_code and return_position:
        position = resolve_new_channel_position(
            symbol,
            result,
            before_tickets,
            magic,
            direction,
        )
        cleaned = bool(position and close_channel_position(symbol, position))
        if not cleaned:
            quarantine_ids = [position.ticket] if position is not None else []
            unresolved = [] if position is not None else [{
                "order": getattr(result, "order", None),
                "deal": getattr(result, "deal", None),
                "symbol": symbol,
                "magic": magic,
                "direction": direction,
                "submitted_at": time.time(),
            }]
            if position is not None:
                with _trades_lock:
                    _open_trades[position.ticket] = {
                        "source": comment,
                        "fp": fp,
                        "direction": direction,
                        "hour": datetime.now().hour,
                        "entry": position.price_open,
                        "ticket": position.ticket,
                        "quarantined": True,
                        **(meta or {}),
                    }
            quarantine_channel_cleanup(
                (meta or {}).get("group_id", f"partial:{time.time_ns()}"),
                position_tickets=quarantine_ids,
                unresolved_fills=unresolved,
            )
            _runtime_safety["suspended"] = True
            notify_tg(
                "⛔ <b>توقف أمان</b>\n\n"
                "حدث تنفيذ جزئي لأمر سوقي وتعذر تأكيد إغلاق الكمية المنفذة. "
                f"التذاكر المحجورة: {quarantine_ids or unresolved}"
            )
        print("[MT5] ⛔ تنفيذ جزئي — أُلغيت المجموعة حمايةً للحساب")
        return None

    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        position = None
        if return_position:
            position = resolve_new_channel_position(
                symbol,
                result,
                before_tickets,
                magic,
                direction,
            )
            if position is None:
                print("[MT5] ⛔ نُفذ الأمر لكن تعذر تحديد تذكرة الصفقة الجديدة")
                unresolved_identity = {
                    "order": getattr(result, "order", None),
                    "deal": getattr(result, "deal", None),
                    "symbol": symbol,
                    "magic": magic,
                    "direction": direction,
                    "submitted_at": time.time(),
                }
                quarantine_channel_cleanup(
                    (meta or {}).get("group_id", f"unresolved:{time.time_ns()}"),
                    unresolved_fills=[unresolved_identity],
                )
                _runtime_safety["suspended"] = True
                notify_tg(
                    "⛔ <b>توقف أمان</b>\n\n"
                    "نُفذ أمر سوقي لكن تعذر ربطه بتذكرة MT5؛ أوقفت الأوامر الجديدة. "
                    f"الهوية المحجورة: {unresolved_identity}"
                )
                return None
            actual_sl = (
                (
                    float(position.price_open) - float(sl_usd)
                    if direction == "BUY"
                    else float(position.price_open) + float(sl_usd)
                )
                if sl_usd
                else float(sl_price or 0.0)
            )
            invalid_fixed_stop = bool(
                actual_sl
                and (
                    direction == "BUY" and actual_sl >= float(position.price_open)
                    or direction == "SELL" and actual_sl <= float(position.price_open)
                )
            )
            if invalid_fixed_stop:
                _last_mt5_error["text"] = (
                    f"وقف محسوب في الجهة الخطأ ({actual_sl:.2f} مقابل دخول "
                    f"{float(position.price_open):.2f})"
                )

            # الأمر أُرسل ومعه وقف محسوب من السعر المعروض، فالصفقة
            # مفتوحة محمية أصلاً. الضبط التالي يحرّكه إلى سعر التنفيذ
            # الفعلي — وهو تحسين بسنتات لا شرط بقاء.
            existing_sl = float(getattr(position, "sl", 0.0) or 0.0)
            entry_price = float(position.price_open)
            protective = bool(existing_sl) and (
                existing_sl < entry_price
                if direction == "BUY"
                else existing_sl > entry_price
            )
            already_exact = protective and abs(existing_sl - actual_sl) <= 0.011

            stop_ready = already_exact or (
                not invalid_fixed_stop
                and (
                    not actual_sl
                    or modify_channel_position(
                        symbol, position, actual_sl, tp_price
                    )
                )
            )
            if not stop_ready and protective and not invalid_fixed_stop:
                # وقف الأمر قائم وفي الجهة الصحيحة: إغلاق صفقة محمية
                # لأن الضبط تعذّر يكلّف السبريد بلا مقابل
                drift = abs(existing_sl - actual_sl)
                print(
                    f"[MT5] ⚠️ تعذر ضبط الوقف إلى {actual_sl:.2f}؛ "
                    f"أبقيت وقف الأمر {existing_sl:.2f} (فرق ${drift:.2f})"
                )
                notify_tg(
                    f"⚠️ <b>الوقف لم يُضبط بدقة — الصفقة محمية</b>\n\n"
                    f"#{position.ticket} | الدخول {entry_price:.2f}\n"
                    f"الوقف القائم: {existing_sl:.2f} بدل {actual_sl:.2f} "
                    f"(فرق ${drift:.2f})\n"
                    f"السبب: {_last_mt5_error['text'] or 'غير محدد'}"
                )
                stop_ready = True

            if not stop_ready:
                print("[MT5] ⛔ الصفقة بلا وقف صالح — إغلاقها")
                closed = close_channel_position(symbol, position)
                if not closed:
                    with _trades_lock:
                        _open_trades[position.ticket] = {
                            "source": comment,
                            "fp": fp,
                            "direction": direction,
                            "hour": datetime.now().hour,
                            "entry": position.price_open,
                            "ticket": position.ticket,
                            "quarantined": True,
                            **(meta or {}),
                        }
                    quarantine_channel_cleanup(
                        (meta or {}).get("group_id", f"stop:{time.time_ns()}"),
                        position_tickets=[position.ticket],
                    )
                    _runtime_safety["suspended"] = True
                    notify_tg(
                        "⛔ <b>توقف أمان</b>\n\n"
                        "تعذر تثبيت الوقف وتعذر إغلاق الصفقة؛ أوقفت الأوامر الجديدة. "
                        f"التذكرة المحجورة: {position.ticket}"
                    )
                return None
        ticket = position.ticket if position is not None else result.order
        actual_entry = float(position.price_open) if position is not None else price
        print(
            f"[MT5] ✅ {direction} {lot}lot @ {actual_entry:.2f} | "
            f"SL={actual_entry - sl_usd if direction == 'BUY' and sl_usd else actual_entry + sl_usd if sl_usd else float(sl_price or 0.0):.2f} "
            f"TP={tp_price or 'مفتوح'}"
        )
        with _trades_lock:
            _open_trades[ticket] = {
                "source": comment,
                "fp": fp,
                "direction": direction,
                "hour": datetime.now().hour,
                "entry": actual_entry,
                "ticket": ticket,
                "opened_at": time.time(),  # لحساب مدة الصفقة في التقرير
                "peak_move": 0.0,
                "worst_move": 0.0,
                **(meta or {}),
            }
        # درس للمحاكي: نسجل شكل الشارت عند كل صفقة قناة
        if magic in (MAGIC_WHALES, MAGIC_KINGS):
            channel_learner.add(
                ticket, (meta or {}).get("channel", "?"), direction, symbol
            )
        return position if return_position else True
    print(f"[MT5] ❌ {describe_mt5_result(result, f'أمر {comment}: ')}")
    return None if return_position else False


# الأوامر المعلقة (LIMIT) التي وضعناها وننتظر تفعيلها
_pending_meta = {}  # order_ticket -> meta (يشمل وقت الوضع)


def _load_channel_cleanup_quarantine():
    try:
        if not os.path.exists(CHANNEL_QUARANTINE_FILE):
            return {}
        with open(CHANNEL_QUARANTINE_FILE, "r", encoding="utf-8") as file:
            raw = json.load(file)
        loaded = {}
        for group_id, state in (raw or {}).items():
            loaded[str(group_id)] = {
                "orders": {int(ticket) for ticket in state.get("orders", [])},
                "positions": {
                    int(ticket) for ticket in state.get("positions", [])
                },
                "unresolved": list(state.get("unresolved", [])),
            }
        return loaded
    except Exception as exc:
        print(f"[QUARANTINE] ⛔ تعذر تحميل حالة الحجر: {exc}")
        return {"load-error": {
            "orders": set(),
            "positions": set(),
            "unresolved": [{"load_error": str(exc)}],
        }}


def _save_channel_cleanup_quarantine():
    try:
        payload = {
            group_id: {
                "orders": sorted(state.get("orders", set())),
                "positions": sorted(state.get("positions", set())),
                "unresolved": list(state.get("unresolved", [])),
            }
            for group_id, state in _channel_cleanup_quarantine.items()
        }
        tmp = CHANNEL_QUARANTINE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)
        os.replace(tmp, CHANNEL_QUARANTINE_FILE)
        return True
    except Exception as exc:
        print(f"[QUARANTINE] ⛔ تعذر حفظ حالة الحجر: {exc}")
        _runtime_safety["suspended"] = True
        return False


_channel_cleanup_quarantine = _load_channel_cleanup_quarantine()
if _channel_cleanup_quarantine:
    _runtime_safety["suspended"] = True


def quarantine_channel_cleanup(
    group_id,
    order_tickets=None,
    position_tickets=None,
    unresolved_fills=None,
):
    """يحفظ التذاكر غير المنظفة لإعادة المحاولة دون لمس مجموعات أخرى."""
    state = _channel_cleanup_quarantine.setdefault(
        group_id,
        {"orders": set(), "positions": set(), "unresolved": []},
    )
    state.setdefault("unresolved", [])
    state["orders"].update(order_tickets or [])
    state["positions"].update(position_tickets or [])
    for identity in unresolved_fills or []:
        if identity not in state["unresolved"]:
            state["unresolved"].append(identity)
    with _trades_lock:
        for ticket in state["orders"]:
            if ticket in _pending_meta:
                _pending_meta[ticket]["quarantined"] = True
        for ticket in state["positions"]:
            if ticket in _open_trades:
                _open_trades[ticket]["quarantined"] = True
    _save_channel_cleanup_quarantine()


def place_pending(
    symbol, direction, lot, entry, sl_usd, tp_price, magic, comment, meta,
    return_ticket=False,
):
    """يضع أمراً معلقاً BUY/SELL LIMIT — الستوب بمسافة دولارات من الدخول."""
    is_buy = direction == "BUY"
    sl = entry - sl_usd if is_buy else entry + sl_usd
    return place_pending_with_sl(
        symbol, direction, lot, entry, sl, tp_price, magic, comment, meta,
        return_ticket=return_ticket,
    )


def place_pending_with_sl(
    symbol, direction, lot, entry, sl, tp_price, magic, comment, meta,
    return_ticket=False,
):
    """يضع أمراً معلقاً BUY/SELL LIMIT بستوب سعري محدد."""
    if not require_live_account(comment):
        return None if return_ticket else False
    if _channel_runtime_mode["enabled"] and not allowed_gold_symbol(symbol):
        print(f"[SYMBOL-GUARD] ⛔ رُفض الأمر على {symbol} — المسموح {DEFAULT_SYMBOL} فقط")
        return None if return_ticket else False
    if not _channel_runtime_mode["enabled"] and learner.is_bad_hour():
        print(f"[MT5] ⛔ ساعة محظورة — رُفض أمر معلق {comment}")
        return False
    is_buy = direction == "BUY"
    req = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT,
        "price": round(float(entry), 2),
        "sl": round(sl, 2),
        "tp": round(float(tp_price), 2) if tp_price else 0.0,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_SPECIFIED,
        "expiration": int(time.time() + PENDING_EXPIRY_SECONDS),
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    result = mt5.order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        with _trades_lock:
            _pending_meta[result.order] = {
                "source": comment,
                "direction": direction,
                "hour": datetime.now().hour,
                "entry": float(entry),
                "placed_at": time.time(),
                **(meta or {}),
            }
        print(f"[MT5] ⏳ أمر معلق {direction} LIMIT @ {entry} | SL={sl:.2f} TP={tp_price}")
        return result.order if return_ticket else True
    print(f"[MT5] ❌ فشل الأمر المعلق: {result.retcode if result else '؟'} {result.comment if result else ''}")
    return None if return_ticket else False


def place_pending_exact(
    symbol, direction, lot, entry, sl, tp_price, magic, comment, meta,
    return_ticket=False,
):
    """يضع LIMIT أو STOP عند سعر الدخول المكتوب، حسب موقعه من السعر الحالي."""
    if not require_live_account(comment):
        return None if return_ticket else False
    if _channel_runtime_mode["enabled"] and not allowed_gold_symbol(symbol):
        print(f"[SYMBOL-GUARD] ⛔ رُفض الأمر على {symbol} — المسموح {DEFAULT_SYMBOL} فقط")
        return None if return_ticket else False
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"[MT5] ❌ لا سعر لـ {symbol}")
        return False
    is_buy = direction == "BUY"
    market_price = tick.ask if is_buy else tick.bid
    if is_buy:
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if entry < market_price else mt5.ORDER_TYPE_BUY_STOP
    else:
        order_type = mt5.ORDER_TYPE_SELL_LIMIT if entry > market_price else mt5.ORDER_TYPE_SELL_STOP
    req = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": round(float(entry), 2),
        "sl": round(float(sl), 2),
        "tp": round(float(tp_price), 2) if tp_price else 0.0,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_SPECIFIED,
        "expiration": int(time.time() + PENDING_EXPIRY_SECONDS),
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    result = mt5.order_send(req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        with _trades_lock:
            _pending_meta[result.order] = {
                "source": comment,
                "direction": direction,
                "hour": datetime.now().hour,
                "entry": float(entry),
                "placed_at": time.time(),
                **(meta or {}),
            }
        kind = "LIMIT" if order_type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_SELL_LIMIT) else "STOP"
        print(f"[MT5] ⏳ {comment} {direction} {kind} @ {entry} | SL={sl} TP={tp_price}")
        return result.order if return_ticket else True
    print(f"[MT5] ❌ فشل أمر {comment}: {result.retcode if result else '؟'}")
    return None if return_ticket else False


def channel_group_meta(channel, direction, tps=None, signal_key=None, fp="",
                       units=1, signal_sl=None, late_entry=False,
                       fixed_sl_usd=0.0, fixed_tp_usd=0.0):
    """بيانات موحدة تجعل أي قناة حالية أو مستقبلية ترث إدارة 5×0.01.

    units عدد "المرات" التي طلبتها القناة: "جدد مرتين" = وحدتان أي
    عشر صفقات، وكل شرائح الخروج تتضاعف معها."""
    group_id = f"{channel}:{signal_key or time.time_ns()}"
    units = max(1, int(units))
    return {
        "channel": channel,
        "direction": direction,
        "group_id": group_id,
        "units": units,
        # فات السعر مدى الدخول؟ نلتزم بستوب التوصية المكتوب بدل حساب
        # $6 من تنفيذ متأخر — هكذا تبقى الصفقة على خطة القناة نفسها
        "late_entry": bool(late_entry),
        "signal_sl": float(signal_sl) if signal_sl else None,
        "lot": channel_policy(channel, "position_lot"),
        "group_size": channel_policy(channel, "position_count") * units,
        # مسافتا التوصية نفسها حين تحملهما (بوت التوصيات). صفر يعني
        # ارجع إلى سياسة القناة.
        "fixed_sl_usd": float(fixed_sl_usd or 0.0),
        "fixed_tp_usd": float(fixed_tp_usd or 0.0),
        "tp1_hit": False,
        "tp2_hit": False,
        "tps": list(tps) if tps else None,
        "targets_applied": False,
        "idx": 0,
        "lock_idx": None,
        "fp": fp,
        "created_at": time.time(),
    }


def open_channel_batch(
    symbol,
    direction,
    magic,
    comment,
    meta,
    *,
    sl_usd=CHANNEL_INITIAL_SL_USD,
    fixed_sl_price=0.0,
    initial_tp_price=0.0,
):
    """يفتح صفقات القناة المنفصلة بسرعة؛ لا يضع TP قبل تأمين المجموعة.

    العدد خمس في الأساس، ويتضاعف بعدد الوحدات المطلوبة في الميتا
    ("جدد مرتين" = عشر صفقات)."""
    if not allowed_gold_symbol(symbol):
        print(f"[SYMBOL-GUARD] ⛔ المسموح {DEFAULT_SYMBOL} فقط")
        return 0
    if _channel_runtime_mode["enabled"] and not hedging_account_ready():
        print("[HEDGING-GUARD] ⛔ رُفض فتح المجموعة — الحساب ليس Hedging")
        return 0
    count = int(meta.get("group_size") or CHANNEL_POSITION_COUNT)
    lot = float(meta.get("lot") or CHANNEL_POSITION_LOT)
    opened_positions = []
    for sequence in range(count):
        item_meta = {**meta, "group_seq": sequence, "pending_batch": False}
        position = open_trade(
            symbol,
            direction,
            lot,
            sl_price=fixed_sl_price,
            tp_price=initial_tp_price,
            sl_usd=0.0 if fixed_sl_price else sl_usd,
            magic=magic,
            comment=comment,
            fp=meta.get("fp", ""),
            meta=item_meta,
            return_position=True,
        )
        if not position:
            rollback_ok = True
            for opened_position in opened_positions:
                rollback_ok = (
                    close_channel_position(symbol, opened_position) and rollback_ok
                )
            if opened_positions:
                time.sleep(0.05)
                position_rows = mt5.positions_get(symbol=symbol)
                still_open = {
                    getattr(row, "ticket", None)
                    for row in (position_rows or [])
                }
                rollback_ok = (
                    position_rows is not None
                    and
                    not any(position.ticket in still_open for position in opened_positions)
                    and rollback_ok
                )
                retained_positions = (
                    {position.ticket for position in opened_positions}
                    if position_rows is None
                    else {
                        position.ticket for position in opened_positions
                        if position.ticket in still_open
                    }
                )
                with _trades_lock:
                    for opened_position in opened_positions:
                        if opened_position.ticket not in retained_positions:
                            _open_trades.pop(opened_position.ticket, None)
                if retained_positions:
                    quarantine_channel_cleanup(
                        meta.get("group_id", f"market:{time.time_ns()}"),
                        position_tickets=retained_positions,
                    )
            if not rollback_ok:
                _runtime_safety["suspended"] = True
                notify_tg(
                    "⛔ <b>توقف أمان</b>\n\n"
                    "فشل إكمال مجموعة الصفقات الخمس وتعذر تأكيد إغلاق المجموعة الناقصة. "
                    f"التذاكر المحجورة: {sorted(retained_positions) if opened_positions else []}"
                )
            return 0
        if position is not True:
            opened_positions.append(position)
    # علامة قاطعة أن الدفعة اكتمل تسجيلها: الإدارة لا تحتاج بعدها
    # أن تنتظر أو تخمّن، وأي نقص لاحق يعني صفقة غادرت لا صفقة قادمة.
    with _trades_lock:
        for opened_position in opened_positions:
            tracked = _open_trades.get(opened_position.ticket)
            if tracked:
                tracked["batch_ready"] = True
    return count


def place_channel_pending_batch(
    symbol,
    direction,
    entry,
    magic,
    comment,
    meta,
    exact=False,
):
    """يضع خمس أوامر معلقة 0.01 بسياسة الوقف الموحدة ومن دون TP مبكر."""
    if not allowed_gold_symbol(symbol):
        print(f"[SYMBOL-GUARD] ⛔ المسموح {DEFAULT_SYMBOL} فقط")
        return 0
    if _channel_runtime_mode["enabled"] and not hedging_account_ready():
        print("[HEDGING-GUARD] ⛔ رُفضت الأوامر المعلقة — الحساب ليس Hedging")
        return 0
    placed_tickets = []
    stop = (
        float(entry) - CHANNEL_INITIAL_SL_USD
        if direction == "BUY"
        else float(entry) + CHANNEL_INITIAL_SL_USD
    )
    for sequence in range(CHANNEL_POSITION_COUNT):
        item_meta = {**meta, "group_seq": sequence, "pending_batch": True}
        if exact:
            ticket = place_pending_exact(
                symbol,
                direction,
                CHANNEL_POSITION_LOT,
                entry,
                stop,
                0.0,
                magic,
                comment,
                item_meta,
                return_ticket=True,
            )
        else:
            ticket = place_pending(
                symbol,
                direction,
                CHANNEL_POSITION_LOT,
                entry,
                CHANNEL_INITIAL_SL_USD,
                0.0,
                magic,
                comment,
                item_meta,
                return_ticket=True,
            )
        if not ticket:
            rollback_ok = True
            for placed_ticket in placed_tickets:
                result = mt5.order_send({
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": placed_ticket,
                })
                rollback_ok = bool(
                    result and result.retcode == mt5.TRADE_RETCODE_DONE
                ) and rollback_ok
            if placed_tickets:
                time.sleep(0.05)
                order_rows = mt5.orders_get(symbol=symbol)
                remaining = {
                    getattr(order, "ticket", None)
                    for order in (order_rows or [])
                }
                rollback_ok = (
                    order_rows is not None
                    and
                    not any(ticket in remaining for ticket in placed_tickets)
                    and rollback_ok
                )
                retained_orders = (
                    set(placed_tickets)
                    if order_rows is None
                    else set(placed_tickets) & remaining
                )
                with _trades_lock:
                    for placed_ticket in placed_tickets:
                        if placed_ticket not in retained_orders:
                            _pending_meta.pop(placed_ticket, None)
                if retained_orders:
                    quarantine_channel_cleanup(
                        meta.get("group_id", f"pending:{time.time_ns()}"),
                        order_tickets=retained_orders,
                    )
            if not rollback_ok:
                _runtime_safety["suspended"] = True
                notify_tg(
                    "⛔ <b>توقف أمان</b>\n\n"
                    "فشل إكمال الأوامر الخمسة وتعذر تأكيد إلغاء المجموعة الناقصة. "
                    f"التذاكر المحجورة: {sorted(retained_orders) if placed_tickets else []}"
                )
            return 0
        if ticket is not True:
            placed_tickets.append(ticket)
    return CHANNEL_POSITION_COUNT


def update_latest_channel_group_targets(channel, tps, signal_sl=None):
    """يربط تحديث الأهداف بأحدث مجموعة للقناة كلها، لا بصفقة واحدة."""
    if not tps:
        return None, 0
    with _trades_lock:
        candidates = [
            info for info in _open_trades.values()
            if info.get("channel") == channel and info.get("group_id")
        ]
        candidates.extend(
            info for info in _pending_meta.values()
            if info.get("channel") == channel and info.get("group_id")
        )
        if not candidates:
            return None, 0
        waiting = [info for info in candidates if not info.get("tps")]
        pool = waiting or candidates
        selected = max(pool, key=lambda info: float(info.get("created_at", 0.0)))
        direction = selected.get("direction")
        reference = selected.get("entry")
        if reference is None or not valid_target_ladder(
            direction, float(reference), tps
        ):
            return None, -1
        group_id = selected["group_id"]
        updated = 0
        for store in (_open_trades, _pending_meta):
            for info in store.values():
                if info.get("group_id") == group_id:
                    info["tps"] = list(tps)
                    info["targets_applied"] = False
                    if signal_sl:
                        # وصلت الأرقام: الوقف ينتقل خلف ستوب التوصية
                        info["signal_sl"] = float(signal_sl)
                    updated += 1
    return group_id, updated


def cancel_channel_pending_orders(strict_account=True):
    """يلغي كل أوامر القنوات المعلقة في الحساب الحالي، عبر جميع الرموز."""
    account = mt5.account_info()
    terminal = mt5.terminal_info()
    real_constant = getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", None)
    if strict_account:
        safe_account = live_account_ready()
    else:
        safe_account = is_live_account(
            account,
            terminal,
            real_constant,
            _channel_runtime_mode.get("account_login"),
        )
    if not safe_account:
        return False, 0
    orders = mt5.orders_get()
    if orders is None:
        print("[MT5] ⛔ تعذر فحص الأوامر المعلقة القديمة")
        return False, 0
    cancelled = 0
    for order in orders:
        if getattr(order, "magic", None) not in ACTIVE_CHANNEL_MAGICS:
            continue
        result = mt5.order_send({
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": order.ticket,
        })
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[MT5] ⛔ تعذر إلغاء الأمر القديم #{order.ticket}")
            return False, cancelled
        cancelled += 1
    return True, cancelled


def parse_limit_entry(text, direction):
    """إذا كانت التوصية LIMIT يرجع سعر الدخول، وإلا None.

    أمثلة: 'XAUUSD BUY LIMIT 4618-4619' → 4619 (الأقرب للسوق يتفعل أولاً)
           'XAUUSD BUY LIMIT 4332-4330' → 4332
           'بيع ليمت 4650' → 4650"""
    m = re.search(
        r"(?:BUY|SELL|شراء|بيع|LONG|SHORT)\s*"
        r"(?:LIMIT|ليمت)\s*[:@]?\s*"
        r"(" + PRICE + r")(?:\s*[-/]\s*(" + PRICE + r"))?",
        normalize_signal_text(text),
    )
    if not m:
        return None
    p1 = float(m.group(1))
    p2 = float(m.group(2)) if m.group(2) else p1
    # نختار الحد الأقرب للسعر الحالي (يتفعل أولاً): للشراء الأعلى، وللبيع الأدنى
    return max(p1, p2) if direction == "BUY" else min(p1, p2)


# ═════════════════════════════════════════════
#  توزيع الدخول على منطقة (Gold buy Now 4231-4226)
# ═════════════════════════════════════════════
def parse_entry_zone(text):
    """يقرأ منطقة الدخول المكتوبة على سطر الاتجاه ويرجع (الأدنى، الأعلى).

    يفهم الإنجليزية: 'Gold buy Now 4231-4226' / 'GOLD SELL ZONE 4644 - 4649'
    / 'XAUUSD LONG 4226/4231' / 'Buy 4,226-4,231'
    والعربية: 'بيع الذهب من 4644 الى 4649' / 'شراء ذهب ٤٢٢٦-٤٢٣١'

    لا يلتقط أسطر الأهداف لأنها لا تسبقها كلمة اتجاه."""
    up = normalize_signal_text(text)
    direction_words = f"(?:{BUY_WORDS}|{SELL_WORDS})"
    match = re.search(
        r"(?:" + ZONE_FILLERS + r"\s+){0,3}"
        + direction_words
        + r"(?:\s*" + ZONE_FILLERS + r"){0,4}"
        r"\s*[:@]?\s*"
        r"(" + PRICE + r")"
        r"\s*(?:-|/|الي|TO)\s*"
        r"(" + PRICE + r")",
        up,
    )
    if not match:
        return None
    first = float(match.group(1))
    second = float(match.group(2))
    if first == second:
        return None
    return (min(first, second), max(first, second))


def zone_entry_levels(direction, low, high, count=None, step=None):
    """يوزع مستويات الدخول على المنطقة بدءاً من الطرف الأفضل.

    الشراء يبدأ من أدنى المنطقة صعوداً، والبيع من أعلاها هبوطاً،
    بمسافة دولار بين كل مستويين. إذا كانت المنطقة أضيق من أن تتسع
    للمستويات بهذه المسافة نوزعها بالتساوي داخل المنطقة بدل تجاوز حدودها."""
    count = int(count or ZONE_LEVEL_COUNT)
    step = float(step or ZONE_LEVEL_STEP_USD)
    low, high = float(low), float(high)
    if count < 1 or high <= low:
        return []
    if count == 1:
        return [round(low if direction == "BUY" else high, 2)]

    width = high - low
    if width < step * (count - 1):
        step = width / (count - 1)  # منطقة ضيقة — نوزع بالتساوي داخلها

    if direction == "BUY":
        levels = [low + step * index for index in range(count)]
    else:
        levels = [high - step * index for index in range(count)]
    return [round(min(max(level, low), high), 2) for level in levels]


# مجموعات المنطقة النشطة — البوت يراقبها ويفتح صفقة عند لمس كل مستوى
_zone_groups = {}
_zone_lock = threading.Lock()


def channel_open_exposure(channel):
    """كم صفقة للقناة مفتوحة الآن أو محجوزة بانتظار لمس مستواها؟

    يجمع الصفقات الحية عند الوسيط (المصدر الموثوق) مع المستويات التي
    لم تُفتح بعد في مجموعات المنطقة النشطة، حتى لا تتجاوز القناة سقفها
    بينما نصف توصيتها ما زال ينتظر."""
    magic = CHANNEL_MAGICS.get(channel)
    live = 0
    if magic is not None:
        try:
            positions = mt5.positions_get()
            if positions is None:
                return None  # تعذر التحقق — القرار للمستدعي
            live = sum(
                1 for position in positions
                if getattr(position, "magic", None) == magic
            )
        except Exception as exc:
            print(f"[CAP] ⛔ تعذر فحص صفقات {channel}: {exc}")
            return None
    with _zone_lock:
        reserved = sum(
            1
            for group in _zone_groups.values()
            if group["channel"] == channel and not group["finished"]
            for level in group["levels"]
            if not level["filled"]
        )
    return live + reserved


def register_zone_group(
    symbol, channel, direction, magic, comment, levels, meta, mode="levels",
    zone=None,
):
    """يسجل مجموعة منطقة ليتولى المراقب فتحها عند وصول السعر.

    mode='levels' → صفقة عند لمس كل مستوى (الحيتان).
    mode='batch'  → الخمس دفعة واحدة عند دخول السعر المنطقة؛
                    المستويات هنا خانات عدّ فقط تحفظ حصة القناة."""
    with _zone_lock:
        _zone_groups[meta["group_id"]] = {
            "symbol": symbol,
            "channel": channel,
            "direction": direction,
            "magic": magic,
            "comment": comment,
            "meta": dict(meta),
            "mode": mode,
            "zone": tuple(zone) if zone else None,
            "levels": [
                {"price": price, "filled": False, "ticket": None}
                for price in levels
            ],
            "created_at": time.time(),
            "finished": False,
        }


def finish_zone_group(group_id, reason=""):
    """يوقف فتح أي مستوى متبقٍ — تُستدعى عند التأمين أو انتهاء الصلاحية."""
    with _zone_lock:
        group = _zone_groups.get(group_id)
        if not group or group["finished"]:
            return 0
        group["finished"] = True
        remaining = sum(1 for level in group["levels"] if not level["filled"])
    if remaining and reason:
        print(f"[ZONE] ⏹️ {group_id}: أُلغيت {remaining} مستويات متبقية — {reason}")
    return remaining


def zone_group_progress(group_id):
    with _zone_lock:
        group = _zone_groups.get(group_id)
        if not group:
            return 0, 0
        return (
            sum(1 for level in group["levels"] if level["filled"]),
            len(group["levels"]),
        )


def _zone_level_is_due(direction, level_price, tick):
    """هل لمس السعر هذا المستوى؟ الشراء عند بلوغ السعر صعوداً والبيع هبوطاً."""
    if direction == "BUY":
        return float(tick.ask) >= float(level_price)
    return float(tick.bid) <= float(level_price)


def open_due_zone_levels(symbol):
    """يفتح صفقة سوقية 0.01 عند كل مستوى لمسه السعر ولم يُفتح بعد.

    يرجع True إذا كانت هناك مجموعة منطقة نشطة تستحق مراقبة سريعة."""
    with _zone_lock:
        active = [
            (group_id, group)
            for group_id, group in _zone_groups.items()
            if not group["finished"] and group["symbol"] == symbol
        ]
    if not active:
        return False
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return True
    if _channel_runtime_mode["enabled"] and not hedging_account_ready():
        print("[ZONE] ⛔ الحساب ليس Hedging — لا تُفتح مستويات المنطقة")
        return True

    now = time.time()
    for group_id, group in active:
        if now - group["created_at"] > ZONE_EXPIRY_SECONDS:
            finish_zone_group(group_id, "انتهت مهلة 24 ساعة")
            continue
        direction = group["direction"]

        # وضع الانتظار: لا شيء حتى يدخل السعر المنطقة، ثم الخمس دفعة واحدة
        if group.get("mode") == "batch":
            low, high = group["zone"]
            market = float(tick.ask if direction == "BUY" else tick.bid)
            if not low <= market <= high:
                continue
            # التعارض يُعاد فحصه هنا لا عند تسجيل المنطقة فقط: قد تمر
            # دقائق قبل دخول السعر، تفتح فيها القناة الأخرى عكس اتجاهنا
            if not no_conflicting_direction(group["channel"], direction):
                finish_zone_group(group_id, "تعارض اتجاه عند دخول المنطقة")
                continue
            with _zone_lock:
                current = _zone_groups.get(group_id)
                if not current or current["finished"]:
                    continue
                current["finished"] = True  # حجز قبل الإرسال منعاً للتكرار
                for slot in current["levels"]:
                    slot["filled"] = True
            opened = open_channel_batch(
                symbol, direction, group["magic"], group["comment"],
                dict(group["meta"]),
            )
            icon, name = CHANNEL_LABELS.get(group["channel"], ("📌", group["channel"]))
            if opened:
                print(
                    f"[ZONE] ✅ {group['channel']} {direction} × {opened} "
                    f"@ {market:.2f} — دخل السعر المنطقة {low:g}-{high:g}"
                )
                notify_tg(
                    f"{icon} <b>{name} — دخل السعر المنطقة</b>\n\n"
                    f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} "
                    f"{opened} × {CHANNEL_POSITION_LOT} @ <b>{market:.2f}</b>\n"
                    f"المنطقة: {low:g} — {high:g}\n"
                    f"الوقف: ${CHANNEL_INITIAL_SL_USD:g} لكل صفقة من تنفيذها"
                )
            else:
                with _zone_lock:
                    failed = _zone_groups.get(group_id)
                    if failed:  # لم تُفتح — نعيد المحاولة عند التحديث التالي
                        failed["finished"] = False
                        for slot in failed["levels"]:
                            slot["filled"] = False
                print(f"[ZONE] ❌ تعذر فتح مجموعة {group_id} عند دخول المنطقة")
                notify_tg(
                    f"❌ <b>{name} — فشل الفتح عند دخول المنطقة</b>\n\n"
                    f"المنطقة: {low:g} — {high:g} | السوق {market:.2f}\n"
                    f"السبب: {_last_mt5_error['text'] or 'غير محدد'}\n"
                    "سأعيد المحاولة عند التحديث التالي."
                )
            continue

        # المستويات تُفتح على مدى دقائق، وقد تكون القناة الأخرى فتحت
        # عكس اتجاهنا في تلك الأثناء — نفحص مرة لكل مجموعة لا لكل مستوى
        conflict_checked = False
        for index, level in enumerate(group["levels"]):
            if level["filled"] or not _zone_level_is_due(direction, level["price"], tick):
                continue
            if not conflict_checked:
                if not no_conflicting_direction(group["channel"], direction):
                    finish_zone_group(group_id, "تعارض اتجاه مع قناة أخرى")
                    break
                conflict_checked = True
            with _zone_lock:
                current = _zone_groups.get(group_id)
                if not current or current["finished"]:
                    break
                slot = current["levels"][index]
                if slot["filled"]:
                    continue
                slot["filled"] = True  # حجز الخانة قبل الإرسال منعاً للتكرار
            position = open_trade(
                symbol,
                direction,
                CHANNEL_POSITION_LOT,
                sl_usd=CHANNEL_INITIAL_SL_USD,
                magic=group["magic"],
                comment=group["comment"],
                fp=group["meta"].get("fp", ""),
                meta={
                    **group["meta"],
                    "group_seq": index,
                    "zone_mode": True,
                    "zone_level": level["price"],
                    "pending_batch": False,
                },
                return_position=True,
            )
            if not position:
                with _zone_lock:
                    current = _zone_groups.get(group_id)
                    if current:
                        current["levels"][index]["filled"] = False  # نعيد المحاولة لاحقاً
                print(f"[ZONE] ❌ تعذر فتح المستوى {level['price']} للمجموعة {group_id}")
                break
            with _zone_lock:
                _zone_groups[group_id]["levels"][index]["ticket"] = position.ticket
            filled, total = zone_group_progress(group_id)
            print(
                f"[ZONE] ✅ {group['channel']} {direction} @ {position.price_open:.2f} "
                f"(مستوى {level['price']}) — {filled}/{total}"
            )
            # notify_tg يضع الرسالة في طابور — send_tg كان يحجز الخيط
            # على طلب HTTP فيؤخر لمس المستوى التالي.
            notify_tg(
                f"🎯 <b>دخول من المنطقة</b>\n\n"
                f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} "
                f"{CHANNEL_POSITION_LOT} @ <b>{position.price_open:.2f}</b>\n"
                f"المستوى: {level['price']} | الصفقة {filled}/{total}\n"
                f"الوقف: ${CHANNEL_INITIAL_SL_USD:g} من التنفيذ"
            )

    # ما زالت مجموعة تنتظر مستويات → أبقِ المراقبة على أسرع فاصل
    with _zone_lock:
        return any(
            not group["finished"]
            and group["symbol"] == symbol
            and any(not level["filled"] for level in group["levels"])
            for group in _zone_groups.values()
        )


# ═════════════════════════════════════════════
#  الجزء ٤ — تيليغرام (إرسال)
# ═════════════════════════════════════════════
def send_tg(text):
    """يرسل رسالة تيليغرام ويرجع True فقط عند نجاح مؤكد (HTTP 200 + ok)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code == 200 and r.json().get("ok"):
            return True
        print(f"[TG] ❌ فشل الإرسال: HTTP {r.status_code} — {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[TG] ❌ {e}")
        return False


_tg_notification_queue = queue.Queue(maxsize=500)
_tg_notification_worker_lock = threading.Lock()
_tg_notification_worker_started = False


def _telegram_notification_worker():
    while True:
        text = _tg_notification_queue.get()
        try:
            send_tg(text)
        finally:
            _tg_notification_queue.task_done()


def notify_tg(text):
    """يضع إشعار القناة في طابور منفصل كي لا يحجب مستمع Telethon."""
    global _tg_notification_worker_started
    with _tg_notification_worker_lock:
        if not _tg_notification_worker_started:
            threading.Thread(
                target=_telegram_notification_worker,
                daemon=True,
                name="telegram-notifications",
            ).start()
            _tg_notification_worker_started = True
    try:
        _tg_notification_queue.put_nowait(text)
        return True
    except queue.Full:
        print("[TG] ⚠️ طابور الإشعارات ممتلئ — تم إسقاط إشعار غير حرج")
        return False


# ═════════════════════════════════════════════
#  الجزء ٥ — قارئ التوصيات من المحادثات المثبتة
# ═════════════════════════════════════════════
BUY_WORDS = r"\b(?:BUY|BAY|LONG|BULLISH|BUYING)\b|شراء|اشتري|اشتر|ابتع|صعود"
SELL_WORDS = r"\b(?:SELL|SHORT|BEARISH|SELLING)\b|بيع|ابيع|هبوط"
# كلمات حشو تفصل الاتجاه عن الأرقام: "Gold Sell Zone 4644" / "بيع الذهب من 4644"
ZONE_FILLERS = (
    r"(?:GOLD|XAUUSD|XAU|NOW|ZONE|AREA|ENTRY|LIMIT|RANGE|"
    r"الذهب|ذهب|الان|منطقه|المنطقه|دخول|الدخول|من|عند|بين)"
)
TARGET_WORDS = (
    r"(?:TP|TAKE\s?PROFIT|TARGETS?|الاهداف|اهداف|الهدف|هدف|جني)"
)
TARGET_ORDINALS = r"(?:الاول|الاولي|الثاني|الثالث|الرابع|الخامس)"
STOP_WORDS = (
    r"(?:STOP\s?LOSS|SL|STOP|وقف\s*الخساره|الاستوب|ستوب|الوقف|وقف)"
)
PRICE = r"[0-9]{3,5}(?:\.[0-9]+)?"

# رسائل المتابعة والنتائج تحمل اتجاهاً وأرقام أهداف تماماً كالتوصية،
# فتُقرأ كتوصية جديدة وتفتح صفقات على خبر قديم. أمثلة حقيقية:
#   "140 pip running 🔥🚀"   "Buy Gold hit Tp1 4236 ✅ +70 pips"
#   "تم تحقيق الهدف الثاني 4620 بيع الذهب ✅"
NON_SIGNAL_MARKERS = re.compile(
    r"RUNNING|\bHIT\b|\bCLOSED?\b|IN\s+PROFIT|BOOKED|SECURED|BREAKEVEN|"
    r"RESULT|SUMMARY|RECAP|\bDONE\b|\bWON\b|"
    r"تم\s*تحقيق|حقق|تحقق|اغلق|اغلاق|جاري|تمت|"
    # "خساره" وحدها ممنوعة: التوصية الصحيحة تكتب "وقف الخسارة"
    r"خسرنا|خسرت|خسروا|(?:ضرب|لمس)\s*(?:ال)?(?:ستوب|استوب|وقف)"
)


# ── لغة أوامر KINGS القصيرة ──
# القناة تنفّذ بكلمة قبل أن ترسل الأرقام، والأرقام تصل متأخرة وقد
# بلغ السعر هدفه الأول. فهذه الكلمات هي الدخول الفعلي:
#   "شراء الان" · "بيع الان" · "فعل شراء" · "خد شراء الان"
#   "اشتري مرتين" · "بيع الان مرتين" · "جدد مرتين" (باتجاه آخر دخول)
# وذكر العدد وحده أمر تنفيذ: القناة لا تكتب "مرتين" إلا وهي تدخل.
# العدد يُقرأ ويُعرض في التنبيه، لكنه لا يضاعف الصفقات: صاحب الحساب
# طلب صفقة واحدة لا أكثر مهما قالت القناة (max_units في سياسة القناة).
# أما "اجهز هنبيع" فتمهيد لا يفتح شيئاً حتى تصل كلمة التنفيذ.
KINGS_PREP_MARKERS = re.compile(
    r"اجهز|استعد|جاهز|هنبيع|هنشتري|هناخد|هنعمل|هندخل|قريبا|ترقب|انتظر"
)
KINGS_RENEW_MARKERS = re.compile(r"جدد|نجدد|تجديد|نعيد|اعاده")
KINGS_INSTANT_MARKERS = re.compile(
    r"\bNOW\b|الان|فعل\s*(?:شراء|بيع)|خد\s*(?:شراء|بيع)|ادخل|نفذ|"
    r"دخول\s*(?:شراء|بيع)"
)
# ذكر عدد المرات أمر تنفيذ بذاته: "اشتري مرتين" · "مرتين لكل دخول"
KINGS_COUNT_MARKERS = re.compile(r"مرتين|مرتان|مرات|\bمره\b")
# سقف مطلق على ما تنفّذه أي قناة من "المرات". القناة تكتب حتى
# "٤ مرات"، لكن صاحب الحساب لا يريد أكثر من صفقة واحدة لكل توصية.
KINGS_MAX_UNITS = 1
_ARABIC_UNIT_WORDS = (
    ("عشر", 10), ("تسع", 9), ("ثمان", 8), ("سبع", 7), ("ست", 6),
    ("خمس", 5), ("اربع", 4), ("ثلاث", 3),
)


def parse_entry_units(text):
    """كم "مرة" طلبت القناة؟ كل مرة خمس صفقات.

    "مرتين" → 2 · "ثلاث مرات" → 3 · بلا ذكر → 1"""
    up = normalize_signal_text(text)
    if re.search(r"مرتين|مرتان|مرتي\b", up):
        return 2
    numeric = re.search(r"([0-9]+)\s*مرات", up)
    if numeric:
        return max(1, int(numeric.group(1)))
    for word, value in _ARABIC_UNIT_WORDS:
        if re.search(word + r"\w*\s*مرات", up):
            return value
    return 1


def kings_command_entry(text, last_direction=None):
    """يقرأ أوامر KINGS القصيرة ويعيد (الاتجاه، عدد الوحدات).

    يعيد (None, 0) إن لم تكن الرسالة أمر تنفيذ."""
    up = normalize_signal_text(text)
    if KINGS_PREP_MARKERS.search(up):
        return None, 0  # "اجهز هنبيع" تمهيد لا تنفيذ
    units = min(parse_entry_units(up), KINGS_MAX_UNITS)
    direction = parse_direction(text)
    renewing = bool(KINGS_RENEW_MARKERS.search(up))
    if renewing and not direction:
        # "جدد مرتين" بلا اتجاه — ترث اتجاه آخر دخول للقناة.
        # ولا يشترط أن تسبقها خسارة؛ القناة تجدد متى شاءت.
        direction = last_direction
    if not direction:
        return None, 0
    counted = bool(KINGS_COUNT_MARKERS.search(up))
    if renewing or counted or KINGS_INSTANT_MARKERS.search(up):
        return direction, units
    return None, 0


# اتجاه آخر دخول لكل قناة — تحتاجه "جدد" التي لا تحمل اتجاهاً
_last_channel_direction = {}


def is_non_signal_message(text):
    """هل الرسالة متابعة أو إعلان نتيجة لا توصية جديدة؟

    نرفض عند الشك: تفويت توصية يكلف صفقة فائتة، أما قراءة إعلان
    نتيجة كتوصية فتفتح خمس صفقات على خبر قديم وقد تكون بعكس السوق."""
    return bool(NON_SIGNAL_MARKERS.search(normalize_signal_text(text)))


UNREAD_SIGNAL_COOLDOWN_SECONDS = 600
_unread_signal_notice = {}


def looks_like_unread_signal(text):
    """رسالة تبدو توصية (اتجاه + سعران فأكثر) لكن البوت لم ينفذها.

    القنوات تغير صيغها، وأخطر ما يحدث أن تمر توصية صامتة دون أن
    يعرف صاحب الحساب. هذه تكشفها بدل أن تختفي في السجل."""
    if is_non_signal_message(text) or not parse_direction(text):
        return False
    normalized = normalize_signal_text(text)
    return len(re.findall(r"\b" + PRICE + r"\b", normalized)) >= 2


def notify_unread_signal(channel, text):
    """ينبه مرة كل عشر دقائق للقناة الواحدة حتى لا يغرق التنبيه الشاشة."""
    icon, name = CHANNEL_LABELS.get(channel, ("📌", channel))
    now = time.time()
    if now - _unread_signal_notice.get(channel, 0.0) < UNREAD_SIGNAL_COOLDOWN_SECONDS:
        return False
    _unread_signal_notice[channel] = now
    excerpt = " ".join(text.split())[:300]
    # الرسالة قد تكون مفهومة تماماً وفشل تنفيذها عند الوسيط؛ التمييز
    # بينهما ضروري وإلا اتُّهمت صيغة صحيحة بأنها غير مدعومة
    execution_error = _last_mt5_error["text"]
    if execution_error:
        headline = "قرأت التوصية لكن الوسيط رفض تنفيذها."
        footer = f"سبب الرفض: {execution_error}"
    else:
        headline = "الرسالة تبدو توصية لكن صيغتها غير مدعومة، فلم أفتح شيئاً."
        footer = "أرسل هذه الرسالة لمطوّر البوت لإضافة صيغتها."
    print(f"[TG-Reader] ⚠️ توصية لم تُنفذ من {name}: {excerpt[:100]}")
    notify_tg(
        f"⚠️ <b>توصية لم أنفذها — {name}</b> {icon}\n\n"
        f"{headline}\n\n"
        f"<code>{excerpt}</code>\n\n"
        f"{footer}"
    )
    return True


def parse_direction(text):
    """يستخرج الاتجاه، مع إعطاء الكلمة الصريحة أولوية على الرموز الزخرفية."""
    up = normalize_signal_text(text)
    explicit_buy = bool(re.search(BUY_WORDS, up))
    explicit_sell = bool(re.search(SELL_WORDS, up))

    # عند وجود كلمتي BUY وSELL معاً نرفض الرسالة بدلاً من التخمين.
    if explicit_buy and explicit_sell:
        return None
    if explicit_buy:
        return "BUY"
    if explicit_sell:
        return "SELL"

    # الرموز تستخدم فقط عندما لا توجد كلمة اتجاه صريحة.
    emoji_buy = bool(re.search(r"📈|🟢", up))
    emoji_sell = bool(re.search(r"📉|🔴", up))
    if emoji_buy and emoji_sell:
        return None
    if emoji_buy:
        return "BUY"
    if emoji_sell:
        return "SELL"
    return None


def parse_tps(text):
    """يستخرج قائمة الأهداف: أرقام + 'open' في النهاية إن وجدت.

    يفهم: Tp1 4236 / Tp 4327 / Tp4 open / TP1: 4639 / Target 1 4236
    والعربية: الهدف الأول 4639 / هدف٢ ٤٢٥٥ / الهدف مفتوح"""
    up = normalize_signal_text(text)
    # ملاحظة مهمة: رقم ترقيم الهدف (Tp1, Tp2) يُقبل فقط إذا بعده فاصل —
    # حتى لا يبتلع أول خانة من السعر ("Tp 4335" كانت تُقرأ 335!)
    raw = re.findall(
        TARGET_WORDS + r"\s*"
        r"(?:" + TARGET_ORDINALS + r"\s*[:\-]?\s*"
        r"|[0-9]\s*[:\-]\s*|[0-9]\s+|[:\-]\s*|\s+)"
        r"(" + PRICE + r"|OPEN|مفتوح)",
        up,
    )
    tps = []
    for value in raw:
        tps.append("open" if value in ("OPEN", "مفتوح") else float(value))
    return tps


def sane_tps(tps, ref_price, tolerance=100.0):
    """حماية: الأهداف يجب أن تكون قريبة من السعر المرجعي (±$100 افتراضياً)
    وإلا فهي خطأ قراءة — نرفض التوصية بدل فتح صفقة بأرقام غلط."""
    for t in tps:
        if t != "open" and abs(float(t) - ref_price) > tolerance:
            return False
    return True


def valid_target_ladder(direction, reference, targets):
    """يتأكد أن الأهداف في جهة الربح، مرتبة، وأن open لا يأتي إلا أخيراً."""
    if not targets or any(
        value == "open" and index != len(targets) - 1
        for index, value in enumerate(targets)
    ):
        return False
    numeric = [float(value) for value in targets if value != "open"]
    if not numeric:
        return False
    if direction == "BUY":
        return all(value > reference for value in numeric) and numeric == sorted(numeric)
    if direction == "SELL":
        return all(value < reference for value in numeric) and numeric == sorted(
            numeric, reverse=True
        )
    return False


def channel_of(chat_name):
    """مطابقة كاملة للأسماء الأربعة التي حددها المستخدم، بلا مطابقة جزئية."""
    normalized = " ".join((chat_name or "").strip().split()).casefold()
    return CHANNEL_TITLE_ALLOWLIST.get(normalized)


def parse_sl(text):
    """يستخرج الستوب المكتوب في التوصية (عربي أو إنجليزي)."""
    m = re.search(
        STOP_WORDS + r"\s*[:\-]?\s*(" + PRICE + r")",
        normalize_signal_text(text),
    )
    return float(m.group(1)) if m else None


# ── بوت توصيات الذهب (n8n) ──
# 🟡 توصية الذهب · القرار: SELL · الثقة: 85%
# 📍 الدخول: 4308.49
# 🛑 الوقف: 4314.78 (خطر $6.29)
# 🎯 الهدف: 4295.92 (ربح $12.57)
# سعر الدخول المكتوب لا يُستعمل إطلاقاً: بين إرسال التوصية وتنفيذها
# يتحرك السوق درجتين أو أكثر، فلو وضعنا الوقف والهدف على أرقامها
# المطلقة اختلّت المسافة. نأخذ المسافتين (خطر/ربح) ونقيسهما من سعر
# التنفيذ الفعلي، فتبقى نسبة المخاطرة كما أرادها البوت بالضبط.
_GOLDBOT_DECISION = re.compile(r"القرار\s*[:\-]?\s*(\S+)")
_GOLDBOT_HOLD = re.compile(r"HOLD|WAIT|NO\s*TRADE|NEUTRAL|انتظار|حياد|لا\s*صفقه")
_GOLDBOT_RISK = re.compile(r"خطر\s*\$?\s*([0-9]+(?:\.[0-9]+)?)")
_GOLDBOT_REWARD = re.compile(r"ربح\s*\$?\s*([0-9]+(?:\.[0-9]+)?)")
_GOLDBOT_ENTRY = re.compile(r"الدخول\s*[:\-]?\s*(" + PRICE + r")")


def parse_gold_bot_signal(text):
    """يقرأ رسالة بوت التوصيات ويعيد قرارها ومسافتي الوقف والهدف.

    يعيد None إن لم تكن الرسالة توصية بهذه الصيغة أصلاً — وهذا ما
    يجعل ترشيح أي محادثة مثبتة لهذه القناة آمناً: لا يُنفَّذ إلا ما
    حمل "القرار" ومعه وقف وهدف.

    ويعيد decision='HOLD' حين يقول البوت لا توصية، فلا يُفتح شيء."""
    up = normalize_signal_text(text)
    decisions = _GOLDBOT_DECISION.findall(up)
    if not decisions:
        return None
    stop = parse_sl(up)
    targets = [value for value in parse_tps(up) if value != "open"]
    target = float(targets[0]) if targets else None
    if stop is None or target is None:
        return None
    if any(_GOLDBOT_HOLD.search(word) for word in decisions):
        return {"decision": "HOLD"}
    # الوقف يساوي الهدف = لا توصية (هكذا يكتبها البوت في رسالة الانتظار)
    if abs(float(stop) - float(target)) < 0.01:
        return {"decision": "HOLD"}
    direction = None
    for word in decisions:
        if re.search(BUY_WORDS, word):
            direction = "BUY"
            break
        if re.search(SELL_WORDS, word):
            direction = "SELL"
            break
    if not direction:
        return None

    entry_match = _GOLDBOT_ENTRY.search(up)
    entry = float(entry_match.group(1)) if entry_match else None
    # المسافتان المكتوبتان صراحةً أولاً، وإلا حُسبتا من أرقام التوصية
    risk_match = _GOLDBOT_RISK.search(up)
    reward_match = _GOLDBOT_REWARD.search(up)
    risk = float(risk_match.group(1)) if risk_match else (
        abs(entry - stop) if entry is not None else None
    )
    reward = float(reward_match.group(1)) if reward_match else (
        abs(entry - target) if entry is not None else None
    )
    if not risk or not reward:
        return None

    # الاتجاه يجب أن يطابق موضع الوقف والهدف، وإلا فهي رسالة مشوّشة
    if direction == "BUY" and not (stop < target):
        return None
    if direction == "SELL" and not (stop > target):
        return None
    if entry is not None:
        if direction == "BUY" and not (stop < entry < target):
            return None
        if direction == "SELL" and not (target < entry < stop):
            return None
    return {
        "decision": direction,
        "direction": direction,
        "risk": round(float(risk), 2),
        "reward": round(float(reward), 2),
        "entry": entry,
        "stop": float(stop),
        "target": float(target),
    }


def normalize_arabic_digits(text):
    """يوحد الأرقام العربية والفارسية قبل قراءة مستويات السعر."""
    return (text or "").translate(str.maketrans(
        "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫",
        "01234567890123456789.",
    ))


# حروف عربية تُكتب بأشكال مختلفة لنفس الكلمة — نوحدها قبل المطابقة
_ARABIC_LETTER_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي",
    "ة": "ه",
    "ؤ": "و",
    "ـ": "",   # التطويل: بيــع → بيع
})
_ARABIC_DIACRITICS = re.compile(r"[ً-ْٰ]")
_THOUSANDS = re.compile(r"(?<=\d)[,،](?=\d{3}(?!\d))")
_DASHES = re.compile(r"[‐-―−]")


def normalize_signal_text(text):
    """يجهز نص التوصية للقراءة مهما اختلفت كتابته.

    القنوات تكتب بالعربية والإنجليزية وتخلط بينهما: أرقام عربية،
    همزات وتاء مربوطة وتطويل، فواصل آلاف، وشرطات مختلفة الشكل.
    بدون توحيدها تفشل القراءة على رسالة صحيحة تماماً."""
    if not text:
        return ""
    text = normalize_arabic_digits(text)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.translate(_ARABIC_LETTER_MAP)
    text = _THOUSANDS.sub("", text)      # 4,226 → 4226 (لا يمس 4226,5)
    text = _DASHES.sub("-", text)        # – — − → -
    text = re.sub(r"\s+", " ", text)
    return text.upper()


def usable_targets(direction, reference, targets):
    """يُسقط الأهداف التي فاتها السعر ويُبقي ما بقي أمامنا.

    القناة قد ترسل التوصية والسوق تجاوز هدفها الأول أصلاً. رفض السلم
    كله عندها يهدر خمسة أهداف صالحة، والصحيح متابعة ما لم يُبلغ بعد.

    يرجع (الأهداف الصالحة، ما أُسقط) — والأولى فارغة إن لم يبقَ شيء
    أو كان الترتيب غير صالح."""
    if not targets:
        return [], []
    kept, dropped = [], []
    for value in targets:
        if value == "open":
            continue
        ahead = (
            float(value) > reference if direction == "BUY"
            else float(value) < reference
        )
        (kept if ahead else dropped).append(float(value))
    if not kept:
        return [], dropped
    if targets[-1] == "open":
        kept.append("open")
    if not valid_target_ladder(direction, reference, kept):
        return [], dropped
    return kept, dropped


def valid_price_side(direction, entry, stop, targets):
    """يتأكد أن SL والأهداف في الجهة الصحيحة وأن سلم الأهداف مرتب."""
    if direction == "BUY":
        return stop < entry and valid_target_ladder(direction, entry, targets)
    if direction == "SELL":
        return stop > entry and valid_target_ladder(direction, entry, targets)
    return False


# آخر توصية لكل قناة — لمنع فتح صفقتين من نفس التوصية
_last_signal = {}  # channel -> (direction, timestamp)
_processed_signals_lock = threading.Lock()


def _load_processed_signals():
    try:
        if os.path.exists(PROCESSED_SIGNALS_FILE):
            with open(PROCESSED_SIGNALS_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return {str(key): float(value) for key, value in data.items()}
    except Exception as exc:
        print(f"[DEDUP] ⚠️ تعذر قراءة سجل الرسائل المنفذة: {exc}")
    return {}


_processed_signals = _load_processed_signals()


def signal_already_processed(signal_key):
    if not signal_key:
        return False
    with _processed_signals_lock:
        return str(signal_key) in _processed_signals


def mark_signal_processed(signal_key):
    """يحفظ هوية رسالة Telegram بعد نجاح التنفيذ فقط."""
    if not signal_key:
        return
    with _processed_signals_lock:
        _processed_signals[str(signal_key)] = time.time()
        if len(_processed_signals) > 5000:
            oldest = sorted(_processed_signals, key=_processed_signals.get)[:-4000]
            for key in oldest:
                _processed_signals.pop(key, None)
        try:
            tmp = PROCESSED_SIGNALS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as file:
                json.dump(_processed_signals, file, ensure_ascii=False)
            os.replace(tmp, PROCESSED_SIGNALS_FILE)
        except Exception as exc:
            print(f"[DEDUP] ⚠️ تعذر حفظ سجل الرسائل المنفذة: {exc}")


def duplicate_entry(channel, fingerprint, signal_key):
    if signal_key:
        return signal_already_processed(signal_key)
    return _duplicate_signal(channel, fingerprint)


def _duplicate_signal(channel, fingerprint, window=600):
    """هل هذه نفس التوصية مكررة خلال آخر 10 دقائق؟
    fingerprint = الاتجاه + الأهداف — توصية مختلفة تمر حتى لو نفس الاتجاه."""
    last = _last_signal.get(channel)
    now = time.time()
    if last and last[0] == fingerprint and now - last[1] < window:
        return True
    _last_signal[channel] = (fingerprint, now)
    return False


CHANNEL_LABELS = {
    "whales": ("🐋", "الحيتان"),
    "kings": ("👑", "KINGS"),
    "goldbot": ("🤖", "بوت التوصيات"),
    "manual": ("✋", "صفقة يدوية"),  # ليس قناة — لتسمية التقارير فقط
}


def opposite_exposure(direction):
    """هل توجد صفقات قنوات مفتوحة بعكس هذا الاتجاه؟

    يرجع (العدد، اسم القناة) — أو (0, None) إن لا تعارض. القنوات
    تتناقض أحياناً: شراء من قناة وبيع من أخرى في اللحظة نفسها، فتتعادل
    الصفقتان ولا يبقى إلا السبريد والعمولة."""
    magic_to_channel = {magic: name for name, magic in CHANNEL_MAGICS.items()}
    opposite_type = (
        mt5.POSITION_TYPE_SELL if direction == "BUY" else mt5.POSITION_TYPE_BUY
    )
    try:
        positions = mt5.positions_get()
        if positions is None:
            return None, None  # تعذر الفحص — القرار للمستدعي
    except Exception as exc:
        print(f"[CONFLICT] ⛔ تعذر فحص الصفقات المفتوحة: {exc}")
        return None, None
    clashing = [
        position for position in positions
        if getattr(position, "magic", None) in magic_to_channel
        and getattr(position, "type", None) == opposite_type
    ]
    if not clashing:
        return 0, None
    owners = {
        magic_to_channel.get(getattr(position, "magic", None))
        for position in clashing
    }
    return len(clashing), " و".join(
        CHANNEL_LABELS.get(owner, ("", owner))[1] for owner in sorted(filter(None, owners))
    )


def no_conflicting_direction(channel, direction):
    """يمنع فتح اتجاه معاكس لصفقات قنوات مفتوحة الآن."""
    icon, name = CHANNEL_LABELS.get(channel, ("📌", channel))
    count, owners = opposite_exposure(direction)
    if count is None:
        print(f"[{name}] ⛔ تعذر التحقق من تعارض الاتجاه — رُفضت التوصية")
        notify_tg(
            f"⚠️ توصية {name} رُفضت لأن البوت لم يتمكن من فحص "
            "الصفقات المفتوحة عند الوسيط"
        )
        return False
    if not count:
        return True
    opposite_ar = "بيع" if direction == "BUY" else "شراء"
    wanted_ar = "شراء" if direction == "BUY" else "بيع"
    print(
        f"[{name}] ⛔ تعارض اتجاه: {count} صفقة {opposite_ar} مفتوحة "
        f"({owners}) — رُفضت توصية ال{wanted_ar}"
    )
    notify_tg(
        f"⛔ <b>رُفضت توصية {name} — تعارض اتجاه</b> {icon}\n\n"
        f"التوصية <b>{wanted_ar}</b>، لكن لديك <b>{count}</b> صفقة "
        f"<b>{opposite_ar}</b> مفتوحة من {owners}.\n"
        "لا أفتح اتجاهين متعاكسين معاً — تتعادل الصفقتان ويبقى السبريد.\n"
        f"⏳ سأقبل ال{wanted_ar} بعد إغلاق صفقات ال{opposite_ar}."
    )
    return False


def channel_cap_allows(channel, needed, detail="", cap=None):
    """هل تتسع القناة لعدد الصفقات المطلوب تحت سقفها؟

    يرفض أيضاً عند تعذر قراءة الصفقات من MT5 — الفتح على معلومة
    ناقصة أسوأ من تفويت التوصية."""
    icon, name = CHANNEL_LABELS.get(channel, ("📌", channel))
    exposure = channel_open_exposure(channel)
    if exposure is None:
        print(f"[{name}] ⛔ تعذر التحقق من صفقات القناة — رُفضت التوصية")
        notify_tg(
            f"⚠️ توصية {name} رُفضت لأن البوت لم يتمكن من التحقق من "
            "الصفقات المفتوحة عند الوسيط"
        )
        return False
    cap = int(cap or CHANNEL_MAX_OPEN_POSITIONS)
    if exposure + needed <= cap:
        return True
    print(
        f"[{name}] ⛔ السقف {cap}: "
        f"مفتوح/محجوز {exposure} — رُفضت التوصية"
    )
    notify_tg(
        f"🚫 <b>تُخطّيت توصية {name}</b> {icon}\n\n"
        f"القناة لديها <b>{exposure}</b> صفقة مفتوحة أو منتظرة، "
        f"وهذه التوصية تحتاج {needed} أخرى.\n"
        f"السقف {cap} صفقات للقناة — "
        "لم أفتح شيئاً حمايةً لحسابك."
        + (f"\nالمتخطّى: {detail}" if detail else "")
    )
    return False


def open_channel_zone(
    symbol, channel, direction, tps, zone, signal_key, magic, comment
):
    """يسجل منطقة دخول القناة ويفتح فوراً كل مستوى فاته السعر.

    سياسة موحدة ترثها كل قناة ترسل منطقة دخول: خمسة مستويات بمسافة
    دولار من الطرف الأفضل، دخول سوقي عند لمس كل مستوى، بلا أوامر معلقة.

    يرجع True إذا اعتُمدت المنطقة (نجاحاً أو رفضاً)، وFalse لترك
    المعالجة للمسار القديم."""
    icon, name = CHANNEL_LABELS.get(channel, ("📌", channel))
    low, high = zone
    levels = zone_entry_levels(direction, low, high)
    if not levels:
        return False

    # أبعد مستوى هو أسوأ دخول — نتحقق أن كل الأهداف خلفه في جهة الربح
    worst_entry = levels[-1]
    if not valid_target_ladder(direction, worst_entry, tps):
        print(f"[{name}] ⛔ الأهداف ليست في جهة الربح أو ليست مرتبة")
        notify_tg(f"⚠️ توصية {name} رُفضت لأن اتجاه أو ترتيب الأهداف غير صالح")
        return True

    fingerprint = f"{direction}|zone|{low}-{high}|{tps}"
    if duplicate_entry(channel, fingerprint, signal_key):
        print(f"[{name}] ⏭️ نفس منطقة التوصية مكررة — تجاهل")
        return True

    if not no_conflicting_direction(channel, direction):
        return True
    if not channel_cap_allows(channel, len(levels), f"المنطقة {low:g} — {high:g}"):
        return True

    meta = channel_group_meta(
        channel,
        direction,
        tps=tps,
        signal_key=signal_key,
        fp=fingerprint,
    )
    meta.update({
        "zone_mode": True,
        "zone_low": low,
        "zone_high": high,
        "group_size": len(levels),
    })
    register_zone_group(
        symbol, channel, direction, magic, comment, levels, meta
    )
    mark_signal_processed(signal_key)

    tick = mt5.symbol_info_tick(symbol)
    market = (tick.ask if direction == "BUY" else tick.bid) if tick else None
    due = (
        sum(1 for level in levels if _zone_level_is_due(direction, level, tick))
        if tick
        else 0
    )
    open_due_zone_levels(symbol)  # المستويات التي فاتها السعر تُفتح الآن
    filled, total = zone_group_progress(meta["group_id"])

    notify_tg(
        f"{icon} <b>توصية {name} — توزيع على المنطقة</b>\n\n"
        f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} — {symbol}\n"
        f"المنطقة: <b>{low:g} — {high:g}</b>"
        f"{f' | السوق الآن {market:.2f}' if market else ''}\n"
        f"المستويات: {' · '.join(f'{level:g}' for level in levels)}\n"
        f"فُتح الآن: <b>{filled}</b> من {total} "
        f"(المستويات التي فاتها السعر: {due})\n"
        f"الباقي يُفتح تلقائياً عند لمس كل مستوى — بلا أوامر معلقة\n"
        f"الوقف: "
        f"${channel_policy(channel, 'fixed_sl_usd') or CHANNEL_INITIAL_SL_USD:g}"
        f" لكل صفقة من تنفيذها الفعلي\n"
        f"الأهداف: {' / '.join(str(value) for value in tps)}\n"
        + exit_plan_line(channel)
    )
    return True


def handle_whales_message(symbol, text, signal_key=None):
    """قناة WHALES VIP الحيتان:
    ١- رسالة 'Buy/Sell Gold Now' بدون أرقام → لا تفتح شيئاً، ننتظر الأرقام
    ٢- رسالة المنطقة والأرقام → توزيع 5 مستويات على المنطقة (دخول سوقي عند اللمس)
    ٣- رسالة أرقام لاحقة → ربط سلم الأهداف بالمجموعة القائمة دون صفقة جديدة"""
    if is_non_signal_message(text):
        print("[الحيتان] ⏭️ رسالة متابعة/نتيجة — ليست توصية")
        return
    direction = parse_direction(text)
    tps = parse_tps(text)

    # رسالة أرقام بدون اتجاه؟ نأخذ الاتجاه من صفقة الحيتان المفتوحة المنتظرة
    if not direction and tps:
        with _trades_lock:
            for info in _open_trades.values():
                if info.get("channel") == "whales" and info.get("tps") is None:
                    direction = info["direction"]
                    break
    if not direction:
        return
    if signal_already_processed(signal_key):
        print("[الحيتان] ⏭️ رسالة Telegram منفذة سابقاً — تجاهل")
        return

    if not tps:
        # رسالة الاتجاه وحدها ('Buy Gold Now / Scalping Setup') لا تفتح صفقات.
        # الدخول كله من رسالة المنطقة والأرقام التي تصل بعدها.
        print("[الحيتان] ⏳ رسالة اتجاه بلا أرقام — بانتظار رسالة المنطقة")
        notify_tg(
            f"🐋 <b>تنبيه الحيتان</b>\n\n"
            f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} قادم — {symbol}\n"
            f"⏳ لم أفتح شيئاً؛ أنتظر رسالة المنطقة والأرقام"
        )
        return

    # رسالة الأرقام — نبحث عن صفقة حيتان مفتوحة بلا سلم أهداف
    numeric_tps = [t for t in tps if t != "open"]
    if not numeric_tps:
        return
    zone = parse_entry_zone(text)
    _t = mt5.symbol_info_tick(symbol)
    sanity_reference = (
        (zone[0] + zone[1]) / 2 if zone else (_t.bid if _t else None)
    )
    if sanity_reference is not None and not sane_tps(
        tps, sanity_reference, ZONE_TP_SANITY_USD
    ):
        print("[الحيتان] ⚠️ أهداف غير منطقية (خطأ قراءة؟) — تجاهل")
        notify_tg("⚠️ توصية الحيتان فيها أرقام غير منطقية — تجاهلتها حمايةً لحسابك")
        return

    # منطقة دخول مكتوبة (مثال: Gold buy Now 4231-4226) → توزيع خمسة مستويات
    if zone and channel_policy(
        "whales", "entry_mode"
    ) == "zone_levels" and open_channel_zone(
        symbol, "whales", direction, tps, zone, signal_key, MAGIC_WHALES, "Whales"
    ):
        return

    group_id, updated = update_latest_channel_group_targets("whales", tps)
    if updated == -1:
        print("[الحيتان] ⛔ اتجاه أو ترتيب الأهداف لا يطابق المجموعة المفتوحة")
        notify_tg("⚠️ أرقام الحيتان رُفضت لأن اتجاه أو ترتيب الأهداف غير صالح")
        return
    if group_id:
        if updated:
            mark_signal_processed(signal_key)
        notify_tg(
            f"🐋 <b>وصلت أرقام الحيتان</b>\n\n"
            f"الأهداف: {' / '.join(str(t) for t in tps)}\n"
            f"✅ سُجّلت على المجموعة ({updated} صفقة/أمر)\n"
            + exit_plan_line("whales")
        )
        return

    # لا توجد صفقة مفتوحة (البوت اشتغل متأخراً؟) — نفتح واحدة الآن
    if duplicate_entry("whales", f"{direction}|{tps}", signal_key):
        return

    # هذا المسار الاحتياطي كان يفتح خمس صفقات بلا حارس تعارض ولا سقف:
    # رسالة أرقام لا تُقرأ كمنطقة (سعر واحد أو صيغة غريبة) كانت تفتح
    # بيعاً بينما الشراء مفتوح من القناة الأخرى.
    if not no_conflicting_direction("whales", direction):
        return
    if not channel_cap_allows(
        "whales", CHANNEL_POSITION_COUNT, f"{direction} بلا منطقة"
    ):
        return

    # توصية LIMIT؟ → أمر معلق عند المنطقة
    limit_entry = parse_limit_entry(text, direction)
    reference = limit_entry
    if reference is None:
        current_tick = mt5.symbol_info_tick(symbol)
        reference = (
            current_tick.ask if direction == "BUY" else current_tick.bid
        ) if current_tick else None
    if reference is None or not valid_target_ladder(direction, reference, tps):
        print("[الحيتان] ⛔ الأهداف ليست في جهة الربح أو ليست مرتبة")
        notify_tg("⚠️ توصية الحيتان رُفضت لأن اتجاه أو ترتيب الأهداف غير صالح")
        return
    if limit_entry:
        meta = channel_group_meta(
            "whales",
            direction,
            tps=tps,
            signal_key=signal_key,
            fp=f"{direction}|{tps}",
        )
        placed = place_channel_pending_batch(
            symbol, direction, limit_entry, MAGIC_WHALES, "Whales", meta
        )
        if placed:
            mark_signal_processed(signal_key)
        notify_tg(
            f"🐋 <b>توصية الحيتان — أمر معلق (LIMIT)</b>\n\n"
            f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} عند {limit_entry} — {symbol}\n"
            f"الأوامر: {placed}/{CHANNEL_POSITION_COUNT} × {CHANNEL_POSITION_LOT} | "
            f"ستوب: ${CHANNEL_INITIAL_SL_USD:g}\n"
            f"الأهداف: {' / '.join(str(t) for t in tps)}\n"
            f"⏳ ينتظر وصول السعر للمنطقة (يُلغى تلقائياً بعد 24 ساعة)\n\n"
            f"{'✅ وُضعت المجموعة' if placed else '❌ فشل وضع المجموعة'}"
        )
        return

    meta = channel_group_meta(
        "whales",
        direction,
        tps=tps,
        signal_key=signal_key,
        fp=f"{direction}|{tps}",
    )
    opened = open_channel_batch(symbol, direction, MAGIC_WHALES, "Whales", meta)
    if opened:
        mark_signal_processed(signal_key)
    notify_tg(
        f"🐋 <b>توصية الحيتان (كاملة)</b>\n\n"
        f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} — {symbol}\n"
        f"الصفقات: {opened}/{CHANNEL_POSITION_COUNT} × {CHANNEL_POSITION_LOT} | "
        f"ستوب: ${CHANNEL_INITIAL_SL_USD:g}\n"
        f"الأهداف: {' / '.join(str(t) for t in tps)}\n\n"
        + (
            "✅ نُفذت المجموعة"
            if opened
            else "❌ <b>فشل فتح المجموعة</b>\n"
            f"السبب: {_last_mt5_error['text'] or 'غير محدد'}"
        )
    )


def open_direction_only(symbol, direction, signal_key, channel, magic, comment,
                        units=1, renewed=False):
    """دخول فوري على كلمة التنفيذ وحدها، والأهداف تُربط حين تصل.

    KINGS ترسل "خد شراء الان" أو "جدد مرتين" ثم الأرقام بعدها بدقائق،
    وقد يكون السعر بلغ هدفه الأول قبل وصولها. فالكلمة هي الدخول."""
    icon, name = CHANNEL_LABELS.get(channel, ("📌", channel))
    # القناة قد تكتب "مرتين" أو "ثلاث مرات"، وسقف القناة يحسم العدد
    units = max(1, min(int(units), int(channel_policy(channel, "max_units"))))
    per_unit = channel_policy(channel, "position_count")
    lot = channel_policy(channel, "position_lot")
    needed = per_unit * units
    if duplicate_entry(channel, f"{direction}|instant|{units}", signal_key):
        print(f"[{name}] ⏭️ نفس دخول الاتجاه مكرر — تجاهل")
        return
    if not no_conflicting_direction(channel, direction):
        return
    # السقف يتسع لهذه التوصية وحدها: "جدد مرتين" تحتاج عشراً فارغة
    if not channel_cap_allows(
        channel, needed, f"{direction} فوري ×{units}", cap=needed
    ):
        return

    tick = mt5.symbol_info_tick(symbol)
    market = float(tick.ask if direction == "BUY" else tick.bid) if tick else 0.0
    meta = channel_group_meta(
        channel, direction, signal_key=signal_key,
        fp=f"{direction}|instant|{units}", units=units,
    )
    _last_mt5_error["text"] = ""
    opened = open_channel_batch(symbol, direction, magic, comment, meta)
    if opened:
        mark_signal_processed(signal_key)
        _last_channel_direction[channel] = direction
    notify_tg(
        f"{icon} <b>{name} — دخول فوري على الأمر</b>\n\n"
        + ("♻️ <b>تجديد</b> باتجاه آخر دخول\n" if renewed else "")
        + f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} — {symbol}\n"
        f"التنفيذ: سوقي فوري @ {market:.2f}\n"
        + (f"عدد المرات: <b>{units}</b>\n" if units > 1 else "")
        + f"الصفقات: {opened}/{needed} × {lot} | "
        f"ستوب: ${CHANNEL_INITIAL_SL_USD:g}\n"
        f"⏳ بانتظار رسالة الأرقام لربط سلم الأهداف\n\n"
        + (
            "✅ نُفذت المجموعة"
            if opened
            else "❌ <b>فشل تنفيذ المجموعة</b>\n"
            f"السبب: {_last_mt5_error['text'] or 'غير محدد'}"
        )
    )


def handle_direct_signal(symbol, text, signal_key, channel, magic, comment):
    """قناة ترسل توصية كاملة في رسالة واحدة (KINGS ومن يشبهها).

    KINGS:
        XAUUSD BUY NOW 4634-4635        XAUUSD BUY LIMIT 4618-4619
        Sl 4630                         Sl 4613
        Tp 4640 ... Tp 4670             Tp 4623 ... Tp 4643

    المدى المكتوب إشارة دخول لا منطقة توزيع: خمس صفقات سوقية فوراً
    في نفس المكان. وLIMIT إن كُتبت تصير خمسة أوامر معلقة.

    KINGS تنفّذ على رسالة الاتجاه ("خد شراء الان") قبل وصول الأرقام،
    ثم تُربط الأرقام بالمجموعة المفتوحة."""
    icon, name = CHANNEL_LABELS.get(channel, ("📌", channel))
    instant_ready = channel_policy(channel, "opens_on_direction")
    last_direction = _last_channel_direction.get(channel)
    command_direction, command_units = (
        kings_command_entry(text, last_direction)
        if instant_ready
        else (None, 0)
    )
    # أمر التنفيذ الصريح يتقدّم على حارس رسائل النتائج: القناة قد
    # تكتب "لمس استوب جدد مرتين" في رسالة واحدة
    if is_non_signal_message(text) and not command_direction:
        print(f"[{name}] ⏭️ رسالة متابعة/نتيجة — ليست توصية")
        return
    direction = parse_direction(text) or command_direction
    renewing = bool(KINGS_RENEW_MARKERS.search(normalize_signal_text(text)))
    if not direction:
        if instant_ready and renewing:
            # "جدد مرتين" بلا ذاكرة اتجاه — لا نخمّن على مال حقيقي
            print(f"[{name}] ⛔ أمر تجديد بلا اتجاه معروف — تجاهل")
            notify_tg(
                f"⚠️ <b>{name}: أمر تجديد بلا اتجاه</b>\n\n"
                "الرسالة تطلب التجديد ولا أعرف اتجاه آخر دخول "
                "(لم يفتح البوت شيئاً بعد). لم أفتح شيئاً."
            )
        return
    if signal_already_processed(signal_key):
        print(f"[{name}] ⏭️ رسالة Telegram منفذة سابقاً — تجاهل")
        return

    tps = parse_tps(text)
    if not [target for target in tps if target != "open"]:
        if not instant_ready:
            print(f"[{name}] ⏳ تمهيد بلا أرقام — بانتظار التوصية")
            notify_tg(
                f"{icon} <b>تنبيه {name}</b>\n\n"
                f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} قادم — {symbol}\n"
                f"⏳ لم أفتح شيئاً؛ أنتظر رسالة الأرقام"
            )
            return
        # الكلمة وحدها هي الدخول: "شراء الان" · "فعل بيع" · "جدد مرتين".
        # وما كان تمهيداً ("اجهز هنبيع") لا يفتح شيئاً.
        if not command_direction:
            print(f"[{name}] ⏭️ كلام بلا أمر تنفيذ وبلا أرقام — تجاهل")
            return
        open_direction_only(
            symbol, command_direction, signal_key, channel, magic, comment,
            units=command_units, renewed=renewing,
        )
        return

    # مجموعة مفتوحة من رسالة الاتجاه تنتظر أهدافها؟ نربطها ولا نفتح ثانية.
    # الشرط أن تكون بلا أهداف فعلاً — وإلا أعادت توصية جديدة ربط سلم
    # مجموعة قائمة بأرقام لا تخصها.
    with _trades_lock:
        awaiting_targets = any(
            info.get("channel") == channel and not info.get("tps")
            for store in (_open_trades, _pending_meta)
            for info in store.values()
        )
    group_id, updated = (
        update_latest_channel_group_targets(channel, tps, parse_sl(text))
        if awaiting_targets
        else (None, 0)
    )
    if group_id and updated > 0:
        mark_signal_processed(signal_key)
        print(f"[{name}] 🎯 رُبط سلم الأهداف بـ {updated} صفقة مفتوحة")
        notify_tg(
            f"{icon} <b>{name} — وصلت الأرقام</b>\n\n"
            f"رُبطت الأرقام بـ <b>{updated}</b> صفقة مفتوحة\n"
            f"الأهداف: {' / '.join(str(value) for value in tps)}\n"
            + exit_plan_line(channel)
        )
        return

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"[{name}] ⛔ لا سعر متاح — رُفضت التوصية")
        return
    market = float(tick.ask if direction == "BUY" else tick.bid)

    limit_entry = parse_limit_entry(text, direction)
    zone = parse_entry_zone(text)
    entry_mode = channel_policy(channel, "entry_mode")
    zone_based = (
        zone is not None
        and limit_entry is None
        and entry_mode in ("zone_wait", "zone_levels")
    )
    waits_for_zone = zone_based and entry_mode == "zone_wait"

    if limit_entry is not None:
        reference = limit_entry
    elif zone_based:
        # الدخول سيقع داخل المنطقة لا عند سعر السوق الحالي، فنتحقق من
        # الأهداف مقابل أسوأ دخول ممكن فيها — وإلا رُفضت توصية صحيحة
        # لمجرد أن السوق ما زال بعيداً عن المنطقة.
        reference = zone[1] if direction == "BUY" else zone[0]
    else:
        reference = market

    if not sane_tps(tps, reference, ZONE_TP_SANITY_USD):
        print(f"[{name}] ⚠️ أهداف غير منطقية (خطأ قراءة؟) — تجاهل")
        notify_tg(f"⚠️ توصية {name} فيها أرقام غير منطقية — تجاهلتها حمايةً لحسابك")
        return

    # السوق قد يكون تجاوز الأهداف الأولى قبل وصول التوصية. إلغاؤها
    # كاملة يهدر أهدافاً ما زالت أمامنا، فنُسقط ما فات ونكمل بالباقي.
    tps, dropped = usable_targets(direction, reference, tps)
    if not tps:
        print(f"[{name}] ⛔ كل الأهداف خلف السعر أو ترتيبها غير صالح")
        notify_tg(
            f"⚠️ <b>رُفضت توصية {name}</b>\n\n"
            "كل الأهداف صارت خلف السعر أو ترتيبها غير صالح."
        )
        return
    if dropped:
        print(f"[{name}] ℹ️ أُسقط {len(dropped)} هدفاً فاتها السعر: {dropped}")

    # قناة توزّع على المنطقة (الحيتان): صفقة عند لمس كل مستوى
    if (
        zone is not None
        and limit_entry is None
        and channel_policy(channel, "entry_mode") == "zone_levels"
        and open_channel_zone(
            symbol, channel, direction, tps, zone, signal_key, magic, comment
        )
    ):
        return

    kind = "LIMIT" if limit_entry is not None else "NOW"
    # رسالة الأرقام نفسها قد تحمل العدد ("مرتين لكل دخول")
    units = (
        min(parse_entry_units(text), int(channel_policy(channel, "max_units")))
        if instant_ready
        else 1
    )
    per_unit = channel_policy(channel, "position_count")
    channel_lot = channel_policy(channel, "position_lot")
    needed = per_unit * units
    fingerprint = f"{direction}|{kind}|{reference}|{tps}|{units}"
    if duplicate_entry(channel, fingerprint, signal_key):
        print(f"[{name}] ⏭️ نفس التوصية مكررة — تجاهل")
        return
    if not no_conflicting_direction(channel, direction):
        return
    if not channel_cap_allows(
        channel, needed, f"{direction} {kind} @ {reference:g} ×{units}",
        cap=needed,
    ):
        return

    # فات السعر مدى الدخول المكتوب؟ نفتح ونلتزم بستوب التوصية.
    # حساب $6 من تنفيذ متأخر يضع الوقف في مكان لا تعرفه القناة.
    signal_sl = parse_sl(text)
    late = (
        limit_entry is None
        and entry_passed(direction, zone, market)
        and signal_sl is not None
        and valid_signal_stop(direction, market, signal_sl)
    )
    # قناة تلتزم بستوب التوصية دائماً (KINGS) تأخذه مع الأرقام فوراً،
    # وغيرها لا يأخذه إلا حين يفوت السعر مدى الدخول
    sl_buffer = channel_policy(channel, "signal_sl_buffer_usd")
    follows_signal_stop = sl_buffer > 0
    # قناة وقفها مسافة ثابتة (الحيتان: ست درجات) لا تأخذ ستوب التوصية
    # أصلاً، وإلا كُتب وقف ثم أعادته الإدارة بعد ربع ثانية
    fixed_levels = bool(channel_policy(channel, "fixed_tp_usd"))
    keep_signal_sl = (
        signal_sl
        if signal_sl and (late or follows_signal_stop) and not fixed_levels
        else None
    )
    entry_sign = 1.0 if direction == "BUY" else -1.0
    entry_sl_price = (
        round(float(keep_signal_sl) - entry_sign * sl_buffer, 2)
        if keep_signal_sl
        else 0.0
    )
    if entry_sl_price and not valid_signal_stop(
        direction, market, entry_sl_price
    ):
        keep_signal_sl, entry_sl_price = None, 0.0
    meta = channel_group_meta(
        channel, direction, tps=tps, signal_key=signal_key, fp=fingerprint,
        units=units, signal_sl=keep_signal_sl, late_entry=late,
    )
    _last_mt5_error["text"] = ""  # خطأ توصية سابقة لا يُنسب لهذه
    inside = False  # هل كان السعر داخل المنطقة وقت وصول التوصية؟
    if limit_entry is not None:
        completed = place_channel_pending_batch(
            symbol, direction, limit_entry, magic, comment, meta
        )
        execution = f"أمر معلق عند {limit_entry:g}"
    elif waits_for_zone:
        # لا نفتح قبل أن يدخل السعر المنطقة — "Do not rush your entries"
        low, high = zone
        meta.update({"zone_mode": True, "zone_low": low, "zone_high": high})
        register_zone_group(
            symbol, channel, direction, magic, comment,
            [low] * needed, meta, mode="batch", zone=zone,
        )
        mark_signal_processed(signal_key)
        inside = low <= market <= high
        open_due_zone_levels(symbol)  # داخل المنطقة أصلاً؟ يفتح الآن
        filled, total = zone_group_progress(meta["group_id"])
        completed = filled
        execution = (
            f"دخول سوقي فوري @ {market:.2f} (السعر داخل المنطقة)"
            if inside
            else f"بانتظار دخول السعر المنطقة {low:g} — {high:g} "
                 f"(السوق الآن {market:.2f})"
        )
    else:
        completed = open_channel_batch(
            symbol, direction, magic, comment, meta,
            fixed_sl_price=entry_sl_price,
        )
        execution = f"دخول سوقي فوري @ {market:.2f}"
        if late and zone:
            execution += f" — فات المدى {zone[0]:g}-{zone[1]:g}"
    if completed:
        mark_signal_processed(signal_key)
        _last_channel_direction[channel] = direction

    # الانتظار الحقيقي هو ألا يكون السعر قد دخل المنطقة بعد؛ أما محاولة
    # فاشلة داخل المنطقة فهي فشل لا انتظار
    waiting = waits_for_zone and not completed and not inside
    if waiting:
        status = "⏳ لم أفتح شيئاً بعد — أراقب المنطقة"
        volume = f"عند الوصول: {needed} × {channel_lot}"
    else:
        status = (
            "✅ نُفذت المجموعة"
            if completed
            else "❌ <b>فشل تنفيذ المجموعة</b>\n"
            f"السبب: {_last_mt5_error['text'] or 'غير محدد'}"
        )
        volume = (
            f"الصفقات: {completed}/{needed} × {channel_lot}"
            + (f" ({units} مرات)" if units > 1 else "")
        )
    notify_tg(
        f"{icon} <b>توصية {name} — {kind}</b>\n\n"
        f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} — {symbol}\n"
        f"التنفيذ: {execution}\n"
        f"{volume} | ستوب: "
        + (f"{entry_sl_price:g} (ستوب التوصية {keep_signal_sl:g}"
           + (f" وخلفه ${sl_buffer:g}" if sl_buffer else "") + ")"
           if entry_sl_price
           else f"${channel_policy(channel, 'fixed_sl_usd') or CHANNEL_INITIAL_SL_USD:g}")
        + f"\n"
        f"الأهداف: {' / '.join(str(value) for value in tps)}\n"
        + exit_plan_line(channel)
        + f"\n{status}"
    )


def handle_kings_message(symbol, text, signal_key=None):
    """KINGS EL GOLD VIP — توصية كاملة، دخول فوري أو LIMIT."""
    handle_direct_signal(symbol, text, signal_key, "kings", MAGIC_KINGS, "Kings")


def handle_goldbot_message(symbol, text, signal_key=None):
    """بوت توصيات الذهب (n8n): صفقة واحدة 0.05 فوراً بستوب وهدف التوصية.

    ولا يُفتح شيء على رسالة HOLD — البوت نفسه يقول لا توصية."""
    channel, magic, comment = "goldbot", MAGIC_GOLDBOT, "GoldBot"
    icon, name = CHANNEL_LABELS[channel]
    signal = parse_gold_bot_signal(text)
    if not signal:
        return  # ليست رسالة توصية بهذه الصيغة — لا شأن لنا بها
    if signal["decision"] == "HOLD":
        print(f"[{name}] ⏭️ HOLD — لا توصية، لم أفتح شيئاً")
        return
    if signal_already_processed(signal_key):
        print(f"[{name}] ⏭️ رسالة Telegram منفذة سابقاً — تجاهل")
        return

    direction = signal["direction"]
    risk, reward = signal["risk"], signal["reward"]
    if not GOLDBOT_MIN_RISK_USD <= risk <= GOLDBOT_MAX_RISK_USD:
        print(f"[{name}] ⛔ مسافة وقف غير مقبولة ${risk:g} — رُفضت التوصية")
        notify_tg(
            f"⚠️ <b>رُفضت توصية {name}</b> {icon}\n\n"
            f"مسافة الوقف ${risk:g} خارج المدى المسموح "
            f"(${GOLDBOT_MIN_RISK_USD:g} — ${GOLDBOT_MAX_RISK_USD:g})."
        )
        return
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"[{name}] ⛔ لا سعر متاح — رُفضت التوصية")
        return
    market = float(tick.ask if direction == "BUY" else tick.bid)

    fingerprint = f"{direction}|{signal['stop']}|{signal['target']}"
    if duplicate_entry(channel, fingerprint, signal_key):
        print(f"[{name}] ⏭️ نفس التوصية مكررة — تجاهل")
        return
    if not no_conflicting_direction(channel, direction):
        return
    needed = channel_policy(channel, "position_count")
    if not channel_cap_allows(
        channel, needed, f"{direction} @ {market:.2f}", cap=needed
    ):
        return

    meta = channel_group_meta(
        channel, direction, signal_key=signal_key, fp=fingerprint,
        fixed_sl_usd=risk, fixed_tp_usd=reward,
    )
    sign = 1.0 if direction == "BUY" else -1.0
    _last_mt5_error["text"] = ""
    opened = open_channel_batch(
        symbol, direction, magic, comment, meta, sl_usd=risk,
    )
    if opened:
        mark_signal_processed(signal_key)
        _last_channel_direction[channel] = direction
    # الأرقام المعروضة تقديرية بسعر اللحظة؛ الإدارة تكتبها من التنفيذ الفعلي
    notify_tg(
        f"{icon} <b>توصية {name}</b>\n\n"
        f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} — {symbol}\n"
        f"التنفيذ: سوقي فوري @ {market:.2f}\n"
        f"الصفقات: {opened}/{needed} × {channel_policy(channel, 'position_lot')}\n"
        f"🛑 الوقف: ${risk:g} من الدخول (≈ {market - sign * risk:.2f})\n"
        f"🎯 الهدف: ${reward:g} من الدخول (≈ {market + sign * reward:.2f})\n"
        f"ℹ️ المسافتان من التوصية، مقيستان من سعر التنفيذ لا من سعرها المكتوب\n\n"
        + (
            "✅ نُفذت"
            if opened
            else "❌ <b>فشل التنفيذ</b>\n"
            f"السبب: {_last_mt5_error['text'] or 'غير محدد'}"
        )
    )


def telegram_listener_thread(symbol):
    """يعمل في Thread منفصل — يراقب المحادثات المثبتة."""
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        print("[TG-Reader] ⚠️ API_ID/API_HASH غير مضبوطين في config.py")
        print("            احصل عليهم من: https://my.telegram.org/apps")
        print("            (نظام التوصيات معطل — باقي الأنظمة تعمل)")
        return

    async def run():
        from telethon import TelegramClient, events

        client = TelegramClient("master_session", TELEGRAM_API_ID, TELEGRAM_API_HASH)
        if TELEGRAM_PHONE:
            await client.start(phone=TELEGRAM_PHONE)
        else:
            await client.start()
        me = await client.get_me()
        print(f"[TG-Reader] ✅ متصل كـ {me.first_name}")

        # جلب المحادثات المثبتة
        pinned_ids = []
        pinned_names = []
        async for dialog in client.iter_dialogs():
            if dialog.pinned:
                pinned_ids.append(dialog.id)
                pinned_names.append(dialog.name)

        if not pinned_ids:
            print("[TG-Reader] ⚠️ لا محادثات مثبتة")
            send_tg("⚠️ البوت يعمل، لكن لا توجد محادثات Telegram مثبتة")
            return

        id2name = dict(zip(pinned_ids, pinned_names))
        watched = {
            cid: channel_of(name)
            for cid, name in id2name.items()
            if channel_of(name)
        }
        # قناة بوت التوصيات قد يختلف اسمها. أي محادثة مثبتة أخرى
        # تُرشَّح لها، ولا يُنفَّذ منها إلا ما كان بصيغة التوصية
        # بالضبط (القرار + الوقف + الهدف) — فما عداه يمرّ صامتاً.
        probed = []
        if FALLBACK_CHANNEL not in watched.values():
            for cid, chat_name in id2name.items():
                if cid not in watched:
                    watched[cid] = FALLBACK_CHANNEL
                    probed.append(chat_name)

        def ch_label(key):
            icon, name = CHANNEL_LABELS.get(key, ("📌", key))
            return f"{icon} {name}"

        print(f"[TG-Reader] 📌 أراقب قنوات التوصيات فقط:")
        for cid, ch in watched.items():
            print(f"            • {id2name[cid]} → {ch_label(ch)}")
        if probed:
            print(
                "[TG-Reader] 🤖 محادثات مثبتة غير معروفة — تُقرأ كبوت "
                "توصيات ولا تُنفَّذ إلا بصيغة التوصية: "
                + "، ".join(probed)
            )

        required = set(REQUIRED_CHANNELS)
        missing = required - set(watched.values())
        if missing:
            titles = {
                key: title
                for title, key in CHANNEL_TITLE_ALLOWLIST.items()
            }
            missing_titles = "\n".join(f"• {titles[key]}" for key in sorted(missing))
            print("[TG-Reader] ⛔ قنوات مطلوبة غير مثبتة بأسمائها الكاملة:")
            print(missing_titles)
            send_tg(
                "⛔ <b>توقف قارئ القنوات</b>\n\n"
                f"لم أجد {len(missing)} من {len(required)} قنوات مثبتة "
                "بأسمائها الكاملة:\n"
                f"{missing_titles}"
            )
            return

        handlers = {
            "whales": handle_whales_message,
            "kings": handle_kings_message,
            "goldbot": handle_goldbot_message,
        }

        def process(channel, text, signal_key, tag="رسالة"):
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n[TG-Reader {now}] 📩 {tag} من {channel}:")
            print(f"   {text[:120]}")
            handler = handlers.get(channel)
            if not handler:
                return
            try:
                handler(symbol, text, signal_key)
            except Exception as e:
                print(f"[TG-Reader] ❌ خطأ معالجة: {e}")
                return
            # التنفيذ الناجح يسجل هوية الرسالة؛ غيابها مع رسالة تبدو
            # توصية يعني صيغة غير مدعومة — ننبه بدل أن تمر صامتة.
            # وقناة بوت التوصيات قد تكون محادثة مثبتة مرشَّحة لا أكثر،
            # فلا ننبه منها إلا على رسالة تحمل "القرار" فعلاً.
            if channel == FALLBACK_CHANNEL and "القرار" not in text:
                return
            if not signal_already_processed(signal_key) and looks_like_unread_signal(
                text
            ):
                notify_unread_signal(channel, text)

        @client.on(events.NewMessage(chats=list(watched.keys())))
        async def handler(event):
            text = event.message.text or ""
            if not text.strip():
                return
            process(
                watched.get(event.chat_id),
                text,
                f"{event.chat_id}:{event.message.id}",
            )

        # القنوات تعدّل رسائلها كثيراً — نعالج التعديلات أيضاً
        # (منع التكرار يضمن عدم فتح صفقتين لنفس التوصية)
        @client.on(events.MessageEdited(chats=list(watched.keys())))
        async def edit_handler(event):
            text = event.message.text or ""
            if not text.strip():
                return
            process(
                watched.get(event.chat_id),
                text,
                f"{event.chat_id}:{event.message.id}",
                tag="رسالة معدّلة",
            )

        # نسجّل المستمعين أولاً، ثم نقرأ التاريخ حتى لا تضيع رسالة أثناء بدء التشغيل.
        try:
            from datetime import timezone
            cutoff = datetime.now(timezone.utc).timestamp() - 30 * 60  # آخر 30 دقيقة
            for cid, ch in watched.items():
                recent = []
                async for msg in client.iter_messages(cid, limit=5):
                    if msg.text and msg.date and msg.date.timestamp() > cutoff:
                        recent.append((msg.text, f"{cid}:{msg.id}"))
                for text, signal_key in reversed(recent):  # من الأقدم للأحدث
                    process(ch, text, signal_key, tag="رسالة سابقة (قبل التشغيل)")
        except Exception as e:
            print(f"[TG-Reader] ⚠️ تعذر قراءة الرسائل السابقة: {e}")

        await client.run_until_disconnected()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run())
    except Exception as e:
        print(f"[TG-Reader] ❌ {e}")


# ═════════════════════════════════════════════
#  الجزء ٦ — استراتيجيات الكتاب
# ═════════════════════════════════════════════
def run_book_strategies(symbol):
    """يشغل استراتيجيات كتاب أحمد حسن الـ18+ ويعيد الإشارة النهائية."""
    try:
        from strategy_manager import run_all_strategies
        from signal_engine import resolve_signal

        report, dominant_trend, zone_report = run_all_strategies(symbol)
        signal = resolve_signal(report, dominant_trend)
        return signal
    except Exception as e:
        print(f"[Book] ❌ خطأ: {e}")
        return None




def resolve_new_channel_position(
    symbol, trade_result, before_tickets, magic, direction
):
    """يربط نتيجة أمر السوق بصفقة Hedging الفعلية دون افتراض تطابق order/ticket."""
    expected_type = (
        mt5.POSITION_TYPE_BUY if direction == "BUY" else mt5.POSITION_TYPE_SELL
    )
    result_order = getattr(trade_result, "order", None)
    result_deal = getattr(trade_result, "deal", None)
    position_id = None
    if result_deal:
        try:
            rows = mt5.history_deals_get(ticket=result_deal) or []
            if rows:
                position_id = getattr(rows[0], "position_id", None)
        except Exception:
            position_id = None

    for _ in range(10):
        positions = mt5.positions_get(symbol=symbol) or []
        exact = [
            position for position in positions
            if getattr(position, "ticket", None) in (result_order, position_id)
            or getattr(position, "identifier", None) in (result_order, position_id)
        ]
        if exact:
            return exact[0]
        candidates = [
            position for position in positions
            if getattr(position, "ticket", None) not in before_tickets
            and getattr(position, "magic", None) == magic
            and getattr(position, "type", None) == expected_type
        ]
        if len(candidates) == 1:
            return candidates[0]
        time.sleep(0.05)
    return None


def close_channel_position(symbol, position, allow_suspended=False):
    """يغلق تذكرة قناة كاملة بسعر السوق مع حماية Demo."""
    if not require_demo_account(
        "channel partial close", allow_suspended=allow_suspended
    ):
        return False
    partial_code = getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010)
    identity = {
        getattr(position, "ticket", None),
        getattr(position, "identifier", None),
    }
    current = position
    for _ in range(4):
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return False
        is_buy = current.type == mt5.POSITION_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": current.ticket,
            "symbol": symbol,
            "volume": current.volume,
            "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "price": tick.bid if is_buy else tick.ask,
            "deviation": 20,
            "magic": current.magic,
            "comment": "ChannelPartial",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == 10030:
            for filling in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN):
                request["type_filling"] = filling
                result = mt5.order_send(request)
                if result and result.retcode in (
                    mt5.TRADE_RETCODE_DONE,
                    partial_code,
                ):
                    break
        if not result or result.retcode not in (
            mt5.TRADE_RETCODE_DONE,
            partial_code,
        ):
            return False
        time.sleep(0.05)
        rows = mt5.positions_get(symbol=symbol)
        if rows is None:
            continue
        remaining = [
            row for row in rows
            if getattr(row, "ticket", None) in identity
            or getattr(row, "identifier", None) in identity
        ]
        if not remaining:
            return True
        current = remaining[0]
    return False


MT5_RETCODE_NAMES = {
    10004: "إعادة تسعير (Requote)",
    10006: "رُفض الطلب",
    10013: "طلب غير صالح",
    10014: "حجم غير صالح",
    10015: "سعر غير صالح",
    10016: "وقف/هدف غير صالح — قريب جداً من السعر",
    10018: "السوق مغلق",
    10019: "لا سيولة كافية",
    10021: "لا أسعار متاحة",
    10025: "لا تغيير في الطلب",
    10027: "التداول الآلي معطّل في المنصة",
    10028: "التداول الآلي معطّل من الوسيط",
    10030: "وضع التعبئة غير مدعوم",
    10031: "لا اتصال بالخادم",
    10034: "تجاوز حد الحجم أو عدد الأوامر",
}
# آخر سبب فشل من MT5 — يُرفق بالتنبيه حتى يُعرف السبب من تيليغرام
# لا من النافذة السوداء وحدها
_last_mt5_error = {"text": ""}


def describe_mt5_result(result, prefix=""):
    """وصف مقروء لنتيجة MT5 مع رقم الخطأ وتعليق الخادم."""
    if result is None:
        code, comment = mt5.last_error(), ""
        text = f"لا استجابة من MT5 ({code})"
    else:
        code = getattr(result, "retcode", None)
        comment = (getattr(result, "comment", "") or "").strip()
        text = f"{MT5_RETCODE_NAMES.get(code, 'خطأ')} [{code}]"
        if comment:
            text += f" — {comment}"
    full = f"{prefix}{text}" if prefix else text
    _last_mt5_error["text"] = full
    return full


def modify_channel_position(symbol, position, sl, tp, attempts=3):
    """يعدّل SL/TP لتذكرة واحدة، مع إعادة محاولة قصيرة.

    الصفقة الجديدة قد لا تكون جاهزة للتعديل في اللحظة الأولى بعد
    تنفيذها، فرفض واحد لا يعني استحالة تثبيت الوقف."""
    if not require_demo_account("channel position management"):
        return False
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "symbol": symbol,
        "sl": round(float(sl), 2) if sl else 0.0,
        "tp": round(float(tp), 2) if tp else 0.0,
    }
    no_change = getattr(mt5, "TRADE_RETCODE_NO_CHANGES", 10025)
    for attempt in range(attempts):
        result = mt5.order_send(request)
        code = getattr(result, "retcode", None) if result else None
        if code == mt5.TRADE_RETCODE_DONE or code == no_change:
            return True
        detail = describe_mt5_result(
            result, f"تعديل وقف #{position.ticket} @ {request['sl']}: "
        )
        print(f"[MT5] ⚠️ محاولة {attempt + 1}/{attempts} — {detail}")
        if attempt + 1 < attempts:
            time.sleep(0.15)
    return False


def _improved_stop(position, candidate):
    if not candidate:
        return float(position.sl or 0.0)
    current = float(position.sl or 0.0)
    is_buy = position.type == mt5.POSITION_TYPE_BUY
    if not current or (is_buy and candidate > current) or (not is_buy and candidate < current):
        return float(candidate)
    return current


def recover_quarantined_channel_cleanup(symbol):
    """يعيد تنظيف التذاكر المحجورة، ولا يستأنف إلا بعد تحقق MT5."""
    if not _channel_cleanup_quarantine or not demo_account_ready():
        return False
    order_rows = mt5.orders_get()
    position_rows = mt5.positions_get()
    if order_rows is None or position_rows is None:
        return False
    orders_by_ticket = {
        getattr(order, "ticket", None): order for order in order_rows
    }
    positions_by_ticket = {}
    for position in position_rows:
        positions_by_ticket[getattr(position, "ticket", None)] = position
        positions_by_ticket[getattr(position, "identifier", None)] = position

    for state in list(_channel_cleanup_quarantine.values()):
        state.setdefault("unresolved", [])
        still_unresolved = []
        for identity in state["unresolved"]:
            deals = None
            try:
                deal_ticket = identity.get("deal")
                if deal_ticket:
                    deals = mt5.history_deals_get(ticket=deal_ticket)
                if not deals and identity.get("order"):
                    history = mt5.history_deals_get(
                        datetime.fromtimestamp(
                            float(identity.get("submitted_at", time.time())) - 60
                        ),
                        datetime.now() + timedelta(minutes=1),
                    )
                    if history is not None:
                        deals = [
                            deal for deal in history
                            if getattr(deal, "order", None) == identity.get("order")
                        ]
            except Exception:
                deals = None
            if not deals:
                still_unresolved.append(identity)
                continue
            position_id = next(
                (
                    getattr(deal, "position_id", None)
                    for deal in deals
                    if getattr(deal, "position_id", None)
                ),
                None,
            )
            if position_id is None:
                still_unresolved.append(identity)
                continue
            position = positions_by_ticket.get(position_id)
            if position is not None:
                state["positions"].add(position.ticket)
            # وجود deal+position_id يحسم الهوية؛ غيابها من positions يعني أنها مغلقة.
        state["unresolved"] = still_unresolved

        for ticket in list(state["orders"]):
            if ticket not in orders_by_ticket:
                continue
            mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket,
            })
        for ticket in list(state["positions"]):
            position = positions_by_ticket.get(ticket)
            if position is not None:
                close_channel_position(
                    getattr(position, "symbol", symbol),
                    position,
                    allow_suspended=True,
                )

    time.sleep(0.05)
    order_rows = mt5.orders_get()
    position_rows = mt5.positions_get()
    if order_rows is None or position_rows is None:
        return False
    remaining_orders = {
        getattr(order, "ticket", None) for order in order_rows
    }
    remaining_positions = set()
    for position in position_rows:
        remaining_positions.add(getattr(position, "ticket", None))
        remaining_positions.add(getattr(position, "identifier", None))

    with _trades_lock:
        for group_id, state in list(_channel_cleanup_quarantine.items()):
            cleared_orders = state["orders"] - remaining_orders
            cleared_positions = state["positions"] - remaining_positions
            for ticket in cleared_orders:
                _pending_meta.pop(ticket, None)
            for ticket in cleared_positions:
                _open_trades.pop(ticket, None)
            state["orders"].intersection_update(remaining_orders)
            state["positions"].intersection_update(remaining_positions)
            if (
                not state["orders"]
                and not state["positions"]
                and not state.get("unresolved")
            ):
                _channel_cleanup_quarantine.pop(group_id, None)
    _save_channel_cleanup_quarantine()

    if not _channel_cleanup_quarantine:
        _runtime_safety["suspended"] = False
        notify_tg(
            "✅ اكتمل تنظيف تذاكر الحماية المحجورة وتأكد MT5 من اختفائها؛ "
            "تم استئناف إدارة القنوات."
        )
        return True
    return False


def reconcile_startup_channel_exposure(symbol):
    """يفشل مغلقاً ويزيل أي تعرض قديم للقنوات قبل تشغيل المستمع."""
    positions = mt5.positions_get()
    if positions is None:
        print("[STARTUP-SAFETY] ⛔ تعذر فحص الصفقات المفتوحة")
        return False
    for position in positions:
        if getattr(position, "magic", None) not in ACTIVE_CHANNEL_MAGICS:
            continue
        quarantine_channel_cleanup(
            f"startup-position:{position.ticket}",
            position_tickets=[position.ticket],
        )
    if not _channel_cleanup_quarantine:
        return True
    _runtime_safety["suspended"] = True
    return recover_quarantined_channel_cleanup(symbol)


def resume_channel_runtime_if_verified(symbol):
    """المسار الوحيد لرفع التعليق بعد تحقق Demo وتنظيف كل حجر."""
    if not demo_account_ready():
        return False
    if _channel_cleanup_quarantine:
        return recover_quarantined_channel_cleanup(symbol)
    _runtime_safety["suspended"] = False
    return True


def _adopt_activated_channel_orders(symbol):
    """ينقل بيانات الأوامر المعلقة إلى الصفقات بعد تفعيلها."""
    with _trades_lock:
        pending_items = list(_pending_meta.items())
    if not pending_items:
        return
    open_order_tickets = {order.ticket for order in (mt5.orders_get(symbol=symbol) or [])}
    positions = mt5.positions_get(symbol=symbol) or []
    positions_by_id = {}
    for position in positions:
        positions_by_id[getattr(position, "ticket", None)] = position
        positions_by_id[getattr(position, "identifier", None)] = position

    missing_tickets = [
        ticket for ticket, _ in pending_items if ticket not in open_order_tickets
    ]
    if missing_tickets:
        try:
            deals = mt5.history_deals_get(
                datetime.now() - timedelta(days=2),
                datetime.now() + timedelta(minutes=1),
            ) or []
        except Exception:
            deals = []
        for deal in deals:
            order_ticket = getattr(deal, "order", None)
            position_id = getattr(deal, "position_id", None)
            if order_ticket in missing_tickets and position_id in positions_by_id:
                positions_by_id[order_ticket] = positions_by_id[position_id]

    for order_ticket, meta in pending_items:
        if order_ticket in open_order_tickets:
            continue
        position = positions_by_id.get(order_ticket)
        if position is not None:
            direction = meta.get("direction")
            actual_sl = (
                float(position.price_open) - CHANNEL_INITIAL_SL_USD
                if direction == "BUY"
                else float(position.price_open) + CHANNEL_INITIAL_SL_USD
            )
            protected = modify_channel_position(symbol, position, actual_sl, 0.0)
            if not protected:
                closed = close_channel_position(symbol, position)
                if closed:
                    with _trades_lock:
                        _pending_meta.pop(order_ticket, None)
                else:
                    with _trades_lock:
                        _pending_meta.pop(order_ticket, None)
                        _open_trades[position.ticket] = {
                            **meta,
                            "ticket": position.ticket,
                            "entry": position.price_open,
                            "activated_at": time.time(),
                            # مدة الصفقة تُحسب من لحظة التفعيل لا من وقت
                            # التوصية؛ الأمر المعلق قد ينتظر ساعات
                            "opened_at": time.time(),
                            "peak_move": 0.0,
                            "worst_move": 0.0,
                            "quarantined": True,
                        }
                    quarantine_channel_cleanup(
                        meta.get("group_id", f"pending:{order_ticket}"),
                        position_tickets=[position.ticket],
                    )
                    _runtime_safety["suspended"] = True
                    notify_tg(
                        "⛔ <b>توقف أمان</b>\n\n"
                        "تفعّل أمر معلق لكن تعذر تثبيت وقف $6 أو تأكيد إغلاقه. "
                        f"التذكرة المحجورة: {position.ticket}"
                    )
                continue
            with _trades_lock:
                _pending_meta.pop(order_ticket, None)
                _open_trades[position.ticket] = {
                    **meta,
                    "ticket": position.ticket,
                    "entry": position.price_open,
                    "activated_at": time.time(),
                    # مدة الصفقة من لحظة التفعيل لا من وقت التوصية
                    "opened_at": time.time(),
                    "peak_move": 0.0,
                    "worst_move": 0.0,
                }
        elif time.time() - float(meta.get("placed_at", time.time())) > PENDING_EXPIRY_SECONDS:
            with _trades_lock:
                _pending_meta.pop(order_ticket, None)


def _abort_incomplete_pending_group(symbol, group_id, items, pending_items):
    """يلغي المجموعة المختلطة التي لم تكتمل خلال مهلة التفعيل."""
    cleanup_ok = True
    pending_tickets = [ticket for ticket, _ in pending_items]
    active_tickets = [position.ticket for position, _ in items]

    for order_ticket in pending_tickets:
        result = mt5.order_send({
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": order_ticket,
        })
        cleanup_ok = bool(
            result and result.retcode == mt5.TRADE_RETCODE_DONE
        ) and cleanup_ok
    for position, _ in items:
        cleanup_ok = close_channel_position(symbol, position) and cleanup_ok

    time.sleep(0.05)
    order_rows = mt5.orders_get(symbol=symbol)
    position_rows = mt5.positions_get(symbol=symbol)
    remaining_orders = {
        getattr(order, "ticket", None) for order in (order_rows or [])
    }
    remaining_positions = {
        getattr(position, "ticket", None) for position in (position_rows or [])
    }
    cleanup_ok = (
        cleanup_ok
        and order_rows is not None
        and position_rows is not None
        and not any(ticket in remaining_orders for ticket in pending_tickets)
        and not any(ticket in remaining_positions for ticket in active_tickets)
    )

    retained_orders = (
        set(pending_tickets)
        if order_rows is None
        else set(pending_tickets) & remaining_orders
    )
    retained_positions = (
        set(active_tickets)
        if position_rows is None
        else set(active_tickets) & remaining_positions
    )
    with _trades_lock:
        for ticket in set(pending_tickets) - retained_orders:
            _pending_meta.pop(ticket, None)
        for ticket in set(active_tickets) - retained_positions:
            _open_trades.pop(ticket, None)
    if retained_orders or retained_positions:
        quarantine_channel_cleanup(
            group_id,
            order_tickets=retained_orders,
            position_tickets=retained_positions,
        )
    _runtime_safety["suspended"] = True
    retained = sorted(retained_orders | retained_positions)
    notify_tg(
        "⛔ <b>توقف أمان</b>\n\n"
        f"لم يكتمل تفعيل الصفقات الخمس للمجموعة {group_id} خلال "
        f"{CHANNEL_PENDING_MIXED_GRACE_SECONDS:g} ثوانٍ؛ "
        f"{'أُغلقت وأُلغيت بالكامل' if cleanup_ok else 'تعذر تأكيد تنظيفها بالكامل'}."
        f"{f' التذاكر المحجورة: {retained}' if retained else ''}"
    )
    return cleanup_ok


def track_channel_excursions(symbol):
    """يسجل أقصى ربح وأقصى خسارة مرّا بكل صفقة وهي مفتوحة.

    بدون هذا لا يعرف التقرير إن كانت الصفقة كادت تربح ثم انعكست، أو
    لم تتحرك معك أصلاً — وهو أهم ما يميز الخسارة السيئة من سوء الحظ."""
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return
    now = time.time()
    with _trades_lock:
        for position in positions:
            info = _open_trades.get(position.ticket)
            if not info:
                continue
            entry = float(info.get("entry") or position.price_open)
            is_buy = position.type == mt5.POSITION_TYPE_BUY
            market = float(tick.bid if is_buy else tick.ask)
            move = market - entry if is_buy else entry - market
            if move > float(info.get("peak_move", -1e9)):
                info["peak_move"] = round(move, 2)
                info["peak_at"] = now
            if move < float(info.get("worst_move", 1e9)):
                info["worst_move"] = round(move, 2)
            info["last_market"] = round(market, 2)


def manage_manual_positions(symbol):
    """يضبط وقف وهدف كل صفقة يدوية، وينقل وقفها للدخول عند الربح.

    اليدوية هي ما لا يحمل Magic البوت — يفتحها صاحب الحساب في المنصة.
    كانت تمر دون حماية إطلاقاً: البوت يرشّح كل شيء بـ Magic قنواته."""
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return
    bot_magics = set(CHANNEL_MAGICS.values()) | {
        MAGIC_BOOK, MAGIC_PATTERN, MAGIC_SIGNAL, MAGIC_CHART,
        MAGIC_MIMIC, MAGIC_LONDON,
    }
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return

    for position in positions:
        if getattr(position, "magic", None) in bot_magics:
            continue
        ticket = position.ticket
        entry = float(position.price_open)
        is_buy = position.type == mt5.POSITION_TYPE_BUY
        sign = 1.0 if is_buy else -1.0
        current_sl = float(position.sl or 0.0)
        current_tp = float(position.tp or 0.0)

        # السجل أولاً: منه يعرف البوت آخر وقف كتبه هو، فيميّز تحريك
        # صاحب الحساب اليدوي ولا يعيده إلى مكانه
        first_time = ticket not in _open_trades
        with _trades_lock:
            info = _open_trades.setdefault(ticket, {
                "source": "Manual",
                "channel": "manual",
                "direction": "BUY" if is_buy else "SELL",
                "entry": entry,
                "ticket": ticket,
                "hour": datetime.now().hour,
                "opened_at": time.time(),
                "peak_move": 0.0,
                "worst_move": 0.0,
                "group_id": f"manual:{ticket}",
                "fp": "manual",
            })
            info["manual"] = True
            # صفقة فتحتها أنت ومعها وقف أو هدف: هما من وضعك، لا من
            # سياسة البوت. لا يمسّهما — أنت أدرى بصفقتك.
            if first_time:
                if current_sl:
                    info["manual_sl"] = True
                    info["bot_sl"] = round(current_sl, 2)
                if current_tp:
                    info["manual_tp"] = True
                    info["bot_tp"] = round(current_tp, 2)

        desired_sl = round(entry - sign * MANUAL_SL_USD, 2)
        desired_tp = round(entry + sign * MANUAL_TP_USD, 2)

        # بلغ ربح التأمين؟ الوقف ينتقل إلى الدخول فتصير بلا خسارة
        market = float(tick.bid if is_buy else tick.ask)
        reached_breakeven = (market - entry) * sign >= MANUAL_BREAKEVEN_USD
        if reached_breakeven:
            desired_sl = round(entry, 2)

        # أول مرة نراها: لا نتراجع بوقف أضيق وضعه صاحب الحساب عند الفتح
        if info.get("bot_sl") is None:
            desired_sl = _better_stop(position, desired_sl, is_buy)

        if not _apply_levels(
            symbol, position, info, desired_sl, desired_tp,
            respect_manual_tp=True,
        ):
            print(f"[MANUAL] ⚠️ تعذر ضبط الصفقة اليدوية #{ticket}")
            continue
        desired_sl = float(info.get("bot_sl") or desired_sl)
        desired_tp = float(info.get("bot_tp") or desired_tp)
        moved_to_entry = abs(desired_sl - entry) <= 0.011
        # لا نطبع ولا نُعلم في كل دورة — فقط حين يتغيّر شيء فعلاً
        if (
            not first_time
            and abs(current_sl - desired_sl) <= 0.011
            and abs(current_tp - desired_tp) <= 0.011
        ):
            continue
        print(
            f"[MANUAL] ✅ #{ticket} {'شراء' if is_buy else 'بيع'} @ {entry:.2f} "
            f"| SL={desired_sl} TP={desired_tp}"
            + (" (وقف عند الدخول)" if moved_to_entry else "")
        )
        if first_time:
            # المسافة تُحسب من الأرقام الفعلية: الوقف أو الهدف قد
            # يكون من وضعك أنت لا من سياسة البوت، فلا نلصق به رقمنا
            sl_gap = abs(desired_sl - entry)
            tp_gap = abs(desired_tp - entry)
            kept_tp = bool(info.get("manual_tp"))
            kept_sl = bool(info.get("manual_sl"))
            notify_tg(
                f"✋ <b>صفقة يدوية — ضُبطت</b>\n\n"
                f"{'📈 شراء' if is_buy else '📉 بيع'} "
                f"{position.volume} @ <b>{entry:.2f}</b>\n"
                f"الوقف: {desired_sl} (${sl_gap:.2f})"
                + (" — وقفك أنت، لم يُغيَّر\n" if kept_sl else "\n")
                + f"الهدف: {desired_tp} (${tp_gap:.2f})"
                + (" — هدفك أنت، لم يُغيَّر\n" if kept_tp else "\n")
                + f"🔒 عند +${MANUAL_BREAKEVEN_USD:g} ينتقل الوقف إلى الدخول\n"
                "✋ وإن حرّكت الوقف أو الهدف بيدك تركهما البوت مكانهما "
                "ولم يعد يلمسهما — ولا حتى عند التأمين"
            )
        elif moved_to_entry and not info.get("be_notified"):
            info["be_notified"] = True
            notify_tg(
                f"🔒 <b>صفقة يدوية — وقف عند الدخول</b>\n\n"
                f"#{ticket} | الدخول {entry:.2f}\n"
                f"وصل الربح +${MANUAL_BREAKEVEN_USD:g} — الصفقة بلا خسارة الآن"
            )


def assign_exit_stages(items):
    """يوزّع أدوار الخروج على صفقات المجموعة.

    صفقتان تخرجان عند الهدف الأول، وصفقتان عند الثاني، والأخيرة
    تركب سلم الأهداف.

    الدور مشتق من رقم الصفقة في الدفعة (group_seq) لا من موضعها في
    القائمة الحالية: لو اشتُق من القائمة لتغيّر دور الباقيات كلما
    خرجت واحدة، فتنتقل صفقة من هدف ثانٍ إلى هدف أول بعد أن كُتب
    هدفها عند الوسيط."""
    stages = {}
    if items and channel_policy(
        items[0][1].get("channel", "channel"), "exit_all_at_tp1"
    ):
        # قناة تخرج كلها عند الهدف الأول — لا تدرّج ولا سلّم
        return {position.ticket: 0 for position, _ in items}
    units = max(1, int((items[0][1].get("units") if items else 1) or 1))
    tp1_end = CHANNEL_TP1_EXIT_COUNT * units
    tp2_end = tp1_end + CHANNEL_TP2_EXIT_COUNT * units
    for index, (position, info) in enumerate(items):
        seq = int(info.get("group_seq", index))
        if seq < tp1_end:
            stages[position.ticket] = 0
        elif seq < tp2_end:
            stages[position.ticket] = 1
        else:
            stages[position.ticket] = None
    return stages


# أقصى ما نقبله بين التنفيذ وستوب التوصية حين نتأخر. أبعد من ذلك
# تكون خسارة الصفقة الواحدة أكبر مما يحتمله الحساب.
LATE_ENTRY_MAX_SL_USD = 15.0


def valid_signal_stop(direction, market_price, stop_price):
    """ستوب التوصية صالح إن كان خلف السعر وبمسافة يحتملها الحساب."""
    if not stop_price:
        return False
    distance = (
        market_price - stop_price if direction == "BUY"
        else stop_price - market_price
    )
    return 0.5 <= distance <= LATE_ENTRY_MAX_SL_USD


def entry_passed(direction, zone, market_price):
    """هل تجاوز السعر مدى الدخول المكتوب قبل أن تصل التوصية؟

    الشراء يفوت حين يصعد فوق أعلى المدى، والبيع حين يهبط تحت أدناه."""
    if not zone:
        return False
    low, high = float(zone[0]), float(zone[1])
    return market_price > high if direction == "BUY" else market_price < low


def _target_reached(market_price, target, is_buy):
    if target is None:
        return False
    return market_price >= target if is_buy else market_price <= target


def _better_stop(position, candidate, is_buy):
    """الأفضل بين الوقف القائم والمرشّح — لا نتراجع بوقف أبداً."""
    current = float(position.sl or 0.0)
    if candidate is None:
        return current
    candidate = float(candidate)
    if not current:
        return candidate
    return candidate if (
        candidate > current if is_buy else candidate < current
    ) else current


# فرق يتجاوز رقّة تقريب الوسيط ويقلّ عن أصغر تحريك يدوي معقول
MANUAL_STOP_TOLERANCE = 0.10

# آخر نص تحديث سلم أُرسل لكل مجموعة — منعاً لتكرار الرسالة نفسها
_ladder_notices = {}


def _apply_levels(symbol, position, info, desired_sl, desired_tp,
                  respect_manual_tp=False):
    """يكتب الوقف والهدف، ويترك ما حرّكه صاحب الحساب بيده.

    البوت يتذكر آخر وقف وهدف كتبهما هو. فإن وجد أحدهما عند الوسيط
    مختلفاً عنه فذلك تعديلك أنت — ولا يعيده ولا يزيحه بعدها أبداً.

    ولا استثناء: ولا حتى محطات التأمين (نقل الوقف إلى الدخول عند
    بلوغ الهدف أو عند ربح التأمين). ما لمسته بيدك صار لك وحدك —
    في صفقات القنوات والصفقات اليدوية سواء."""
    is_buy = position.type == mt5.POSITION_TYPE_BUY
    current_sl = float(position.sl or 0.0)
    remembered = info.get("bot_sl")
    if (
        remembered is not None
        and abs(current_sl - float(remembered)) > MANUAL_STOP_TOLERANCE
    ):
        icon, name = CHANNEL_LABELS.get(
            info.get("channel", "channel"), ("📌", info.get("channel", "؟"))
        )
        print(
            f"[CHANNELS] ✋ #{position.ticket}: وقف يدوي {current_sl} "
            f"(كان البوت كتب {remembered}) — يبقى مكانه"
        )
        notify_tg(
            f"✋ <b>وقف يدوي — تركه البوت</b> {icon}\n\n"
            f"صفقة {name} #{position.ticket}\n"
            f"حرّكت الوقف إلى <b>{current_sl}</b> — لن يعيده البوت.\n"
            "🔒 ولا يزيحه بعد اليوم مهما بلغت الأهداف — وقفك لك وحدك."
        )
        info["manual_sl"] = True

    if info.get("manual_sl"):
        # وقفك لا يُزاح ولا للأمام: أنت أدرى بصفقتك
        desired_sl = current_sl

    # وكذلك الهدف، في صفقات القنوات والصفقات اليدوية سواء: البوت يضع
    # هدفه أول مرة، فإن حرّكته بيدك بعدها تركه ولم يعد يكتبه أبداً.
    current_tp = float(position.tp or 0.0)
    if respect_manual_tp:
        remembered_tp = info.get("bot_tp")
        if (
            remembered_tp is not None
            and abs(current_tp - float(remembered_tp)) > MANUAL_STOP_TOLERANCE
            and not info.get("manual_tp")
        ):
            info["manual_tp"] = True
            icon, name = CHANNEL_LABELS.get(
                info.get("channel", "channel"), ("📌", info.get("channel", "؟"))
            )
            print(
                f"[CHANNELS] ✋ #{position.ticket}: هدف يدوي {current_tp} "
                f"(كان البوت كتب {remembered_tp}) — يبقى مكانه"
            )
            notify_tg(
                f"✋ <b>هدف يدوي — تركه البوت</b> {icon}\n\n"
                f"صفقة {name} #{position.ticket}\n"
                f"حرّكت الهدف إلى <b>{current_tp}</b> — لن يعيده البوت."
            )
        if info.get("manual_tp"):
            desired_tp = current_tp

    ok = _write_if_changed(symbol, position, desired_sl, desired_tp)
    if ok:
        info["bot_sl"] = round(float(desired_sl), 2)
        if respect_manual_tp:
            info["bot_tp"] = round(float(desired_tp), 2)
    return ok


def _write_if_changed(symbol, position, sl, tp):
    """لا نرسل أمر تعديل ما لم يتغير شيء فعلاً."""
    if (
        abs(float(position.sl or 0.0) - float(sl)) <= 0.011
        and abs(float(position.tp or 0.0) - float(tp)) <= 0.011
    ):
        return True
    return modify_channel_position(symbol, position, sl, tp)


def apply_channel_target_ladder(symbol, group_id, items, first_info,
                                is_buy, market_price, base_sl=None,
                                base_exact=False):
    """يكتب الهدف الحالي والوقف المقفول على صفقات المجموعة.

    يعمل قبل التأمين وبعده: قناة قد يكون هدفها الأول أقرب من حد
    التأمين (KINGS: +$2.79 مقابل +$3)، فلو انتظرنا التأمين بقيت
    الصفقات بلا TP عند الوسيط ولم يُبلغ الهدف أبداً."""
    tps = first_info.get("tps") or []
    if not tps:
        return
    idx = int(first_info.get("idx", 0))
    targets_applied = bool(first_info.get("targets_applied"))
    numeric = [float(value) for value in tps if value != "open"]
    if not numeric:
        return

    next_tp = None
    next_sl = None
    new_idx = idx
    new_lock_idx = first_info.get("lock_idx")
    updates = []

    channel = first_info.get("channel", "channel")
    approach_usd = channel_policy(channel, "target_approach_usd")
    lock_usd = channel_policy(channel, "target_lock_usd")

    while new_idx < len(tps) and tps[new_idx] != "open":
        active = float(tps[new_idx])
        near = (
            market_price >= active - approach_usd
            if is_buy
            else market_price <= active + approach_usd
        )
        if not near or new_idx + 1 >= len(tps):
            break
        new_idx += 1

    # الهدف المكتوب عند الوسيط ليس الهدف الفعّال بل الذي يليه.
    # السبب: قاعدة القناة تنقل الهدف إلى التالي عند الاقتراب منه
    # بدولار، أي أننا لا ننوي الخروج عند الهدف الحالي أصلاً. ولو
    # تركناه مكتوباً عند الوسيط وقفز السعر فوقه بين دورتين، أغلقه
    # الوسيط عند هدف كنا سنتجاوزه — وهذا ما لا نريده.
    # آخر هدف رقمي يُكتب كما هو لأنه مخرج التوصية الحقيقي.
    broker_idx = new_idx
    if (
        new_idx + 1 < len(tps)
        and tps[new_idx] != "open"
        and tps[new_idx + 1] != "open"
    ):
        broker_idx = new_idx + 1

    active_target = tps[broker_idx] if broker_idx < len(tps) else "open"
    if active_target == "open":
        desired_tp = 0.0
    else:
        desired_tp = float(active_target)
        still_ahead = (
            desired_tp > market_price if is_buy else desired_tp < market_price
        )
        if not still_ahead:
            desired_tp = 0.0

    if not targets_applied or new_idx != idx:
        next_tp = desired_tp
        if desired_tp == 0.0:
            updates.append("الهدف → مفتوح")
        elif broker_idx != new_idx:
            updates.append(
                f"الهدف → TP{new_idx + 1} {tps[new_idx]} "
                f"(المكتوب عند الوسيط TP{broker_idx + 1} {desired_tp})"
            )
        else:
            updates.append(f"الهدف → TP{new_idx + 1} {desired_tp}")

    previous_indices = [
        index for index in range(min(new_idx, len(tps)))
        if tps[index] != "open"
    ]
    passed_indices = []
    for index in previous_indices:
        target = float(tps[index])
        passed = (
            market_price >= target + lock_usd
            if is_buy
            else market_price <= target - lock_usd
        )
        if passed:
            passed_indices.append(index)
    if passed_indices:
        locked_index = max(passed_indices)
        next_sl = float(tps[locked_index])
        updates.append(f"الستوب → الهدف السابق {next_sl}")

    # نفد السلم؟ الوقف يتتبع أعلى سعر بلغته كل صفقة ويبقى تحته
    # بمسافة ثابتة. بدون هذا يقف الوقف عند آخر هدف مهما صعد السعر
    # فوقه، فترتد الصفقة وتُعيد ما ربحته كله.
    trail_usd = channel_policy(channel, "trail_after_last_usd")
    ladder_exhausted = new_idx >= len(tps) or tps[new_idx] == "open"
    trail_stops = {}
    if trail_usd and ladder_exhausted:
        for position, info in items:
            entry = float(info.get("entry") or position.price_open)
            reach = max(
                float(info.get("peak_move", 0.0) or 0.0),
                market_price - entry if is_buy else entry - market_price,
            )
            if reach <= trail_usd:
                continue  # لم تبتعد بما يكفي لترك مسافة التتبع
            candidate = round(
                entry + reach - trail_usd if is_buy
                else entry - reach + trail_usd,
                2,
            )
            improved = _improved_stop(position, candidate)
            if abs(improved - float(position.sl or 0.0)) >= CHANNEL_TRAIL_STEP_USD:
                trail_stops[position.ticket] = improved
    if trail_stops and not first_info.get("trail_started"):
        updates.append(f"الوقف بدأ يتتبع القمة بمسافة ${trail_usd:g}")

    pending_lock = new_idx - 1 if new_idx > 0 and tps[new_idx - 1] != "open" else None
    if pending_lock is not None and pending_lock in passed_indices:
        pending_lock = None
    new_lock_idx = pending_lock

    changed = True
    for position, info in items:
        tp_value = float(position.tp or 0.0) if next_tp is None else next_tp
        # الوقف الابتدائي يُكتب بالضبط، وما بعده لا يتراجع أبداً:
        # الأفضل بين أرضية المرحلة والقفل على هدف سابق والتتبع
        trail = trail_stops.get(position.ticket)
        if base_exact and base_sl is not None:
            sl_value = float(base_sl)
        else:
            sl_value = _better_stop(position, base_sl, is_buy)
        for candidate in (next_sl, trail):
            sl_value = _better_stop(
                types.SimpleNamespace(sl=sl_value), candidate, is_buy
            )
        changed = (
            _apply_levels(symbol, position, info, sl_value, tp_value,
                          respect_manual_tp=True)
            and changed
        )
    if not changed:
        print(f"[CHANNELS] ⚠️ المجموعة {group_id}: تعذر تعديل السلم بالكامل")
        return
    with _trades_lock:
        for position, _ in items:
            tracked = _open_trades.get(position.ticket)
            if tracked:
                tracked.update({
                    "targets_applied": True,
                    "idx": new_idx,
                    "lock_idx": new_lock_idx,
                })
                if trail_stops:
                    tracked["trail_started"] = True
    if trail_stops:
        # التتبع يتكرر مع كل صعود — نطبعه ولا نغرق التلجرام برسائله
        print(
            f"[CHANNELS] 🪜 {channel}: الوقف يتتبع القمة بمسافة "
            f"${trail_usd:g} → {sorted(set(trail_stops.values()))}"
        )
    if not updates:
        return
    # حزام أمان أخير ضد التكرار: لا نرسل نفس نص التحديث مرتين
    # للمجموعة نفسها مهما كان سبب إعادة الحساب
    line = " | ".join(updates)
    if _ladder_notices.get(group_id) == line:
        return
    _ladder_notices[group_id] = line
    send_tg(
        f"⚙️ <b>تحديث سلم الأهداف</b>\n\n"
        f"{first_info.get('channel', 'channel')}: {line}"
    )




def fixed_group_levels(info):
    """مسافتا الوقف والهدف الثابتتان لهذه المجموعة، أو (0, 0).

    الأولوية لما جاء في التوصية نفسها (بوت التوصيات يكتب خطره وربحه)،
    ثم لسياسة القناة (الحيتان: هدف $5 ووقف $6 لكل صفقة)."""
    channel = info.get("channel", "channel")
    tp_usd = float(info.get("fixed_tp_usd") or 0.0) or float(
        channel_policy(channel, "fixed_tp_usd") or 0.0
    )
    if not tp_usd:
        return 0.0, 0.0
    sl_usd = float(info.get("fixed_sl_usd") or 0.0) or float(
        channel_policy(channel, "fixed_sl_usd") or 0.0
    ) or float(channel_policy(channel, "initial_sl_usd"))
    return sl_usd, tp_usd


def manage_fixed_level_group(symbol, items, is_buy):
    """يضبط لكل صفقة وقفها وهدفها بمسافتيهما من دخولها هي.

    يعيد True إن كانت المجموعة من هذا النوع فتُترك الإدارة هنا، ولا
    يمسّ وقفاً أو هدفاً حرّكه صاحب الحساب بيده."""
    sl_usd, tp_usd = fixed_group_levels(items[0][1])
    if not tp_usd:
        return False
    sign = 1.0 if is_buy else -1.0
    for position, info in items:
        entry = float(info.get("entry") or position.price_open)
        _apply_levels(
            symbol, position, info,
            round(entry - sign * sl_usd, 2),
            round(entry + sign * tp_usd, 2),
            respect_manual_tp=True,
        )
    return True


def manage_unified_channel_groups(symbol):
    """إدارة مركزية ترثها كل قناة تستخدم channel_group_meta."""
    if _runtime_safety["suspended"]:
        if _channel_cleanup_quarantine:
            recover_quarantined_channel_cleanup(symbol)
        if _runtime_safety["suspended"]:
            return
    if not require_demo_account("unified channel manager"):
        return
    _adopt_activated_channel_orders(symbol)

    positions = mt5.positions_get(symbol=symbol) or []
    groups = {}
    pending_by_group = {}
    with _trades_lock:
        for position in positions:
            info = _open_trades.get(position.ticket)
            if not info or not info.get("group_id"):
                continue
            groups.setdefault(info["group_id"], []).append((position, info))
        for ticket, info in _pending_meta.items():
            if info.get("group_id"):
                pending_by_group.setdefault(info["group_id"], []).append((ticket, info))

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return

    for group_id, items in groups.items():
        items.sort(key=lambda item: item[1].get("group_seq", 0))
        first_position, first_info = items[0]
        is_buy = first_position.type == mt5.POSITION_TYPE_BUY
        market_price = tick.bid if is_buy else tick.ask

        # ── صفقات تُدار كل واحدة وحدها بمسافتين ثابتتين ──
        # الحيتان: هدف $5 ووقف $6 لكل صفقة من الخمس.
        # بوت التوصيات: مسافتا التوصية نفسها من سعر التنفيذ الفعلي.
        # لا سلم أهداف ولا إغلاق جزئي ولا تتبع — كل صفقة مستقلة.
        if manage_fixed_level_group(symbol, items, is_buy):
            continue

        stages = assign_exit_stages(items)
        tps = first_info.get("tps") or []
        numeric = [float(value) for value in tps if value != "open"]
        tp1 = numeric[0] if numeric else None
        tp2 = numeric[1] if len(numeric) > 1 else None
        sign = 1.0 if is_buy else -1.0

        zone_mode = bool(first_info.get("zone_mode"))
        outstanding_pending = pending_by_group.get(group_id, [])
        pending_origin = any(
            info.get("pending_batch") for _, info in items
        ) or any(info.get("pending_batch") for _, info in outstanding_pending)
        # مجموعة المنطقة تدخل مستوى بعد مستوى — النقص فيها طبيعي ولا يُلغيها.
        # والنقص لا يوقف الإدارة أبداً: الانتظار فقط لأمر معلّق لم يُفعّل،
        # أو لثوانٍ معدودة ريثما تُسجَّل الدفعة كاملة.
        group_size = int(first_info.get("group_size") or CHANNEL_POSITION_COUNT)
        still_filling = (
            len(items) < group_size
            and not any(info.get("batch_ready") for _, info in items)
            and time.time() - float(first_info.get("created_at") or 0.0)
            < CHANNEL_GROUP_FILL_GRACE_SECONDS
        )
        scaling_started = any(info.get("tp1_hit") for _, info in items)
        if not zone_mode and not scaling_started and (
            outstanding_pending or still_filling
        ):
            activated = [
                float(info.get("activated_at"))
                for _, info in items
                if info.get("activated_at")
            ]
            if (
                pending_origin
                and activated
                and time.time() - min(activated)
                >= CHANNEL_PENDING_MIXED_GRACE_SECONDS
            ):
                _abort_incomplete_pending_group(
                    symbol, group_id, items, outstanding_pending
                )
            continue

        # بلوغ الهدف يُسجَّل مرة ولا يُنسى: الوسيط يغلق شرائح الخروج
        # عند هدفها بنفسه، فلا يبقى في المجموعة من يشهد على بلوغه.
        tp1_hit = any(info.get("tp1_hit") for _, info in items) or _target_reached(
            market_price, tp1, is_buy
        )
        tp2_hit = any(info.get("tp2_hit") for _, info in items) or _target_reached(
            market_price, tp2, is_buy
        )
        newly_hit = []
        if tp1_hit and not any(info.get("tp1_hit") for _, info in items):
            newly_hit.append(("الهدف الأول", tp1))
        if tp2_hit and not any(info.get("tp2_hit") for _, info in items):
            newly_hit.append(("الهدف الثاني", tp2))
        if newly_hit:
            with _trades_lock:
                for position, _ in items:
                    tracked = _open_trades.get(position.ticket)
                    if tracked:
                        tracked["tp1_hit"] = tp1_hit
                        tracked["tp2_hit"] = tp2_hit
            if zone_mode and tp1_hit:
                # بلغت التوصية هدفها — لا نفتح مستويات جديدة عليها
                finish_zone_group(group_id, "بلغت التوصية هدفها الأول")

        # وقف الأرضية المشترك: $6 تحت الدخول، ثم الدخول بعد الهدف الأول.
        # وإن كان الدخول متأخراً بعد فوات المدى فالأرضية ستوب التوصية
        # نفسه — لا نُقرّبه ولا نُبعده.
        group_signal_sl = first_info.get("signal_sl")
        sl_buffer = channel_policy(
            first_info.get("channel", "channel"), "signal_sl_buffer_usd"
        )

        def floor_stop(position):
            entry = float(position.price_open)
            if tp1_hit:
                return round(entry, 2)
            if group_signal_sl:
                # ستوب التوصية، ومعه هامش درجة خلفه حتى لا يصطادنا
                # فتيل يلمس رقم القناة ثم يرتد
                candidate = round(float(group_signal_sl) - sign * sl_buffer, 2)
                if valid_signal_stop(
                    "BUY" if is_buy else "SELL", entry, candidate
                ):
                    return candidate
            return round(entry - sign * CHANNEL_INITIAL_SL_USD, 2)

        # لم تصل أرقام القناة بعد؟ نضبط الوقف، وإن طال الانتظار
        # وضعنا هدفاً احتياطياً حتى لا تبقى الصفقة بلا مخرج
        if not numeric:
            waited = time.time() - float(
                first_info.get("created_at") or time.time()
            )
            use_fallback = waited >= CHANNEL_TARGETLESS_GRACE_SECONDS
            announced = any(info.get("fallback_tp") for _, info in items)
            for position, info in items:
                desired_tp = float(position.tp or 0.0)
                if use_fallback and not desired_tp:
                    desired_tp = round(
                        float(position.price_open)
                        + sign * CHANNEL_FALLBACK_TP_USD,
                        2,
                    )
                    info["fallback_tp"] = True
                _apply_levels(
                    symbol, position, info, floor_stop(position), desired_tp,
                    respect_manual_tp=True,
                )
            if use_fallback and not announced:
                send_tg(
                    f"🛟 <b>{first_info.get('channel', 'channel')}: هدف "
                    f"احتياطي</b>\n\n"
                    "الدخول تمّ على كلمة القناة قبل أرقامها.\n"
                    f"🎯 وُضع هدف ${CHANNEL_FALLBACK_TP_USD:g} من الدخول "
                    "حتى لا تبقى الصفقة بلا مخرج.\n"
                    "وحين تصل الأرقام يحلّ هدف التوصية محله."
                )
            continue

        runner_items = []
        for position, info in items:
            stage = stages.get(position.ticket)
            if stage is None:
                runner_items.append((position, info))
                continue
            # شريحة خروج: هدفها ثابت عند الوسيط فيغلقها هو بالضبط
            target = tp1 if stage == 0 else tp2
            if target is None:
                runner_items.append((position, info))  # لا هدف ثانٍ — تركب السلم
                continue
            desired_tp = round(float(target), 2)
            # قبل الهدف الأول الوقف يُكتب بالضبط $6 من التنفيذ الفعلي:
            # "الأفضل بينهما" كان يُبقي وقفاً جاء أضيق من الأمر بسبب
            # الانزلاق، فتفتح الصفقة بخمس درجات بدل ست.
            desired_sl = (
                _better_stop(position, floor_stop(position), is_buy)
                if tp1_hit
                else floor_stop(position)
            )
            # بلوغ الهدف الأول محطة متفق عليها: تسري فوق الوقف اليدوي
            _apply_levels(symbol, position, info, desired_sl, desired_tp,
                          respect_manual_tp=True)

        if runner_items:
            base_sl = floor_stop(runner_items[0][0])
            if tp2_hit and tp1 is not None:
                # بعد الهدف الثاني: وقف الصفقة الأخيرة على الهدف الأول
                base_sl = round(float(tp1), 2)
            # حالة السلم (idx و targets_applied) تُقرأ من الصفقة التي
            # تركب السلم نفسها. تمرير first_info كان يقرأ حالة صفقة
            # أخرى لا تُحدَّث أبداً، فيُعاد إرسال "تحديث سلم الأهداف"
            # في كل دورة — أكثر من ستين رسالة في الدقيقة.
            apply_channel_target_ladder(
                symbol, group_id, runner_items, runner_items[0][1], is_buy,
                market_price, base_sl=base_sl, base_exact=not tp1_hit,
            )

        for label, value in newly_hit:
            send_tg(
                f"🎯 <b>{first_info.get('channel', 'channel')}: بلغت "
                f"{label} {value:g}</b>\n\n"
                + (
                    "أُغلقت صفقتان عنده\n🔒 وقف الباقيات عند الدخول"
                    if label == "الهدف الأول"
                    else "أُغلقت صفقتان عنده\n"
                    f"🔒 وقف الصفقة الأخيرة على الهدف الأول {tp1:g}\n"
                    "🪜 وبدأ سلم الأهداف"
                )
            )


def _format_duration(seconds):
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds} ثانية"
    if seconds < 3600:
        return f"{seconds // 60} دقيقة و{seconds % 60} ثانية"
    return f"{seconds // 3600} ساعة و{(seconds % 3600) // 60} دقيقة"


def _closing_cause(info, deals, profit):
    """يستنتج ما الذي أغلق الصفقة فعلاً من بيانات الصفقة والصفقات."""
    reasons = {getattr(deal, "reason", None) for deal in deals}
    sl_reason = getattr(mt5, "DEAL_REASON_SL", 4)
    tp_reason = getattr(mt5, "DEAL_REASON_TP", 5)
    if sl_reason in reasons:
        if profit > 0 and info.get("trail_started"):
            return "🪜 خرجت بالوقف المتتبع بعد أن تجاوزت آخر هدف"
        if profit > 0:
            return "🔒 خرجت بالوقف المقفول على هدف سابق"
        if info.get("tp1_hit"):
            return "🔒 ضرب الوقف بعد نقله للدخول — خرجت بلا خسارة تقريباً"
        return "🛑 ضرب وقف الخسارة"
    if tp_reason in reasons:
        return "🎯 وصل الهدف"
    return "📤 أُغلقت بأمر من البوت"


def build_trade_report(symbol, info, position_ticket, deals, profit):
    """تقرير مفصل عن صفقة واحدة: ماذا جرى فيها من الدخول للخروج."""
    channel = info.get("channel", "?")
    icon, name = CHANNEL_LABELS.get(channel, ("📌", channel))
    direction = info.get("direction", "?")
    entry = float(info.get("entry") or 0.0)
    exit_price = next(
        (
            float(getattr(deal, "price", 0.0))
            for deal in reversed(deals)
            if getattr(deal, "price", 0.0)
        ),
        0.0,
    )
    opened_at = float(info.get("opened_at") or info.get("created_at") or time.time())
    peak = float(info.get("peak_move", 0.0))
    worst = float(info.get("worst_move", 0.0))
    won = profit > 0

    lines = [
        f"{'🟢' if won else '🔴'} <b>أُغلقت صفقة {name}</b> {icon}",
        "",
        f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} "
        f"{CHANNEL_POSITION_LOT} — {symbol}",
        f"الدخول: <b>{entry:.2f}</b> ← الخروج: <b>{exit_price:.2f}</b>",
        f"النتيجة: <b>{'+' if won else ''}${profit:.2f}</b>",
        f"المدة: {_format_duration(time.time() - opened_at)}",
        "",
        f"<b>ماذا جرى:</b>",
        f"• {_closing_cause(info, deals, profit)}",
    ]

    if info.get("zone_level") is not None:
        lines.append(
            f"• مستوى المنطقة: {float(info['zone_level']):g} "
            f"(دخلت فعلياً عند {entry:.2f})"
        )

    if peak or worst:
        lines.append(
            f"• أقصى ربح مرّ بها: <b>+${max(peak, 0):.2f}</b> | "
            f"أقصى تراجع: <b>-${abs(min(worst, 0)):.2f}</b>"
        )

    # القراءة الذكية: لماذا انتهت هكذا؟
    if won:
        if peak > profit + 1.5:
            lines.append(
                f"• 💡 كانت رابحة +${peak:.2f} قبل الخروج بـ ${profit:.2f} — "
                "السلم خرج مبكراً عن القمة"
            )
        if abs(min(worst, 0)) > 2:
            lines.append(
                f"• 💡 تراجعت -${abs(worst):.2f} قبل أن تربح — "
                "الدخول كان مبكراً لكن الاتجاه صح"
            )
    else:
        if peak >= REPORT_NEAR_WIN_USD:
            lines.append(
                f"• ⚠️ وصلت +${peak:.2f} ثم انعكست قبل أن تبلغ الهدف الأول — "
                "الهدف كان أبعد مما احتملته الحركة"
            )
        elif peak > 1:
            lines.append(
                f"• 😤 تحركت معك +${peak:.2f} فقط ثم انعكست — "
                "دخول متأخر بعد فوات الحركة"
            )
        else:
            lines.append(
                "• 🚫 لم تتحرك معك إطلاقاً — التوصية كانت معاكسة للسوق "
                "من اللحظة الأولى"
            )
        lines.append("")
        lines.append("<b>🔬 تشريح الخسارة:</b>")
        lines.append(loss_autopsy(symbol, info, profit))

    group_id = info.get("group_id")
    if group_id:
        remaining = sum(
            1 for tracked in _open_trades.values()
            if tracked.get("group_id") == group_id
        )
        lines.append("")
        lines.append(f"باقي من هذه التوصية: <b>{remaining}</b> صفقة مفتوحة")
    return "\n".join(lines)


# نتائج صفقات كل توصية حتى تُغلق آخر صفقة فيها فيُرسل التقرير الختامي
_group_results = {}


def _recommendation_finished(group_id):
    """هل انتهت التوصية فعلاً؟ لا صفقة مفتوحة ولا مستوى ينتظر."""
    with _trades_lock:
        if any(
            info.get("group_id") == group_id for info in _open_trades.values()
        ):
            return False
    with _zone_lock:
        for group in _zone_groups.values():
            if group["meta"].get("group_id") != group_id or group["finished"]:
                continue
            if any(not level["filled"] for level in group["levels"]):
                return False  # ما زال ينتظر لمس مستوى
    return True


def build_recommendation_summary(symbol, group_id, record):
    """التقرير الختامي للتوصية كاملة بعد إغلاق آخر صفقة فيها."""
    channel = record.get("channel", "?")
    icon, name = CHANNEL_LABELS.get(channel, ("📌", channel))
    trades = record["trades"]
    net = sum(trade["profit"] for trade in trades)
    wins = [trade for trade in trades if trade["profit"] > 0]
    losses = [trade for trade in trades if trade["profit"] <= 0]
    best = max(trades, key=lambda t: t["profit"])
    worst = min(trades, key=lambda t: t["profit"])
    duration = time.time() - record["started"]
    won = net > 0

    lines = [
        f"{'🏆' if won else '📕'} <b>انتهت توصية {name}</b> {icon}",
        "",
        f"{'📈 شراء' if record.get('direction') == 'BUY' else '📉 بيع'} — {symbol}",
    ]
    if record.get("zone"):
        low, high = record["zone"]
        lines.append(f"المنطقة: {low:g} — {high:g}")
    lines += [
        f"الصفقات: {len(trades)} | رابحة {len(wins)} · خاسرة {len(losses)}",
        f"مدة التوصية: {_format_duration(duration)}",
        "",
        f"<b>الصافي: {'+' if won else ''}${net:.2f}</b>",
        f"أفضل صفقة: +${best['profit']:.2f} | أسوأ صفقة: ${worst['profit']:.2f}",
    ]

    peaks = [trade.get("peak", 0.0) for trade in trades]
    if peaks:
        lines.append(
            f"أقصى ربح وصلته التوصية: +${max(peaks):.2f} للصفقة الواحدة"
        )

    lines.append("")
    lines.append("<b>الخلاصة:</b>")
    if won and not losses:
        lines.append("✅ توصية نظيفة — كل الصفقات رابحة")
    elif won:
        lines.append(
            f"✅ التوصية رابحة رغم {len(losses)} صفقة خاسرة — "
            "التأمين الجزئي أدى دوره"
        )
    elif net == 0:
        lines.append("➖ خرجت بلا ربح ولا خسارة")
    else:
        unprotected = [
            trade for trade in trades
            if trade["profit"] <= 0 and trade.get("peak", 0) >= REPORT_NEAR_WIN_USD
        ]
        if unprotected:
            lines.append(
                f"❌ خاسرة — و{len(unprotected)} صفقة كانت رابحة "
                f"+${REPORT_NEAR_WIN_USD:g} أو أكثر قبل أن تنعكس"
            )
        elif max(peaks or [0]) < 1:
            lines.append("❌ خاسرة — التوصية عاكست السوق من البداية")
        else:
            lines.append("❌ خاسرة — السوق لم يعطِ المسافة الكافية للتأمين")

    risked = len(trades) * CHANNEL_INITIAL_SL_USD
    lines.append(f"المخاطرة التي دخلتها: ${risked:.0f} | النتيجة: ${net:.2f}")
    return "\n".join(lines)


def build_group_close_report(symbol, closures):
    """تقرير واحد لعدة صفقات أُغلقت معاً من نفس التوصية.

    الخمس كانت تخرج في ثانية واحدة فيصل خمس رسائل متطابقة تقريباً،
    وفيها تشريح خسارة مكرر حرفياً خمس مرات. هذا يجمعها في رسالة
    واحدة تحتفظ بتفصيل كل صفقة ويكتب التشريح مرة."""
    first = closures[0][1]
    channel = first.get("channel", "?")
    icon, name = CHANNEL_LABELS.get(channel, ("📌", channel))
    direction = first.get("direction", "?")
    net = sum(item[3] for item in closures)
    won = net > 0

    lines = [
        f"{'🟢' if won else '🔴'} <b>أُغلقت {len(closures)} صفقات "
        f"{name}</b> {icon}",
        "",
        f"{'📈 شراء' if direction == 'BUY' else '📉 بيع'} — {symbol}",
        f"الصافي: <b>{'+' if won else ''}${net:.2f}</b>",
        "",
    ]
    for ticket, info, deals, profit in closures:
        entry = float(info.get("entry") or 0.0)
        exit_price = next(
            (
                float(getattr(deal, "price", 0.0))
                for deal in reversed(deals)
                if getattr(deal, "price", 0.0)
            ),
            0.0,
        )
        peak = float(info.get("peak_move", 0.0))
        worst = float(info.get("worst_move", 0.0))
        lines.append(
            f"• {entry:.2f} ← {exit_price:.2f} | "
            f"<b>{'+' if profit > 0 else ''}${profit:.2f}</b> | "
            f"{_closing_cause(info, deals, profit)}"
        )
        if peak or worst:
            lines.append(
                f"   أقصى ربح +${max(peak, 0):.2f} · "
                f"أقصى تراجع -${abs(min(worst, 0)):.2f}"
            )

    losers = [item for item in closures if item[3] <= 0]
    if losers:
        # التشريح واحد للمجموعة: نفس الرمز ونفس الاتجاه ونفس اللحظة
        lines.append("")
        lines.append("<b>🔬 تشريح الخسارة:</b>")
        lines.append(loss_autopsy(symbol, losers[0][1], losers[0][3]))

    group_id = first.get("group_id")
    if group_id:
        remaining = sum(
            1 for tracked in _open_trades.values()
            if tracked.get("group_id") == group_id
        )
        lines.append("")
        lines.append(f"باقي من هذه التوصية: <b>{remaining}</b> صفقة مفتوحة")
    return "\n".join(lines)


def report_closed_channel_trades(symbol):
    """يرصد صفقات القنوات التي أُغلقت ويرسل تقريرها.

    ما أُغلق في الدورة نفسها من توصية واحدة يُجمع في رسالة واحدة:
    خمس رسائل في ثانية واحدة كانت تغرق التلجرام بلا فائدة."""
    with _trades_lock:
        tracked = [
            (ticket, dict(info)) for ticket, info in _open_trades.items()
            if info.get("channel")
        ]
    if not tracked:
        return
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return  # تعذر الفحص — لا نفترض الإغلاق
    open_tickets = {position.ticket for position in positions}

    closures = []
    for ticket, info in tracked:
        if ticket in open_tickets:
            continue
        deals = mt5.history_deals_get(position=ticket)
        if not deals:
            continue  # لم تظهر بعد في تاريخ MT5 — ننتظر الدورة القادمة
        with _trades_lock:
            live = _open_trades.pop(ticket, None)
        if live is None:
            continue
        info.update(live)
        profit = sum(
            float(getattr(deal, "profit", 0.0))
            + float(getattr(deal, "swap", 0.0))
            + float(getattr(deal, "commission", 0.0))
            for deal in deals
        )
        closures.append((ticket, info, deals, profit))
        try:
            channel_learner.close(ticket, profit)
            learner.record_trade(
                info.get("channel", "channel"),
                info.get("direction", "?"),
                info.get("fp", ""),
                profit,
                hour=info.get("hour", datetime.now().hour),
            )
        except Exception as exc:
            print(f"[REPORT] ⚠️ تعذر تسجيل التعلم #{ticket}: {exc}")
        print(
            f"[REPORT] {'🟢' if profit > 0 else '🔴'} أُغلقت #{ticket} "
            f"({info.get('channel')}) ${profit:.2f}"
        )

    if not closures:
        return

    by_group = {}
    for item in closures:
        key = item[1].get("group_id") or f"solo:{item[0]}"
        by_group.setdefault(key, []).append(item)

    for key, group_closures in by_group.items():
        try:
            if len(group_closures) == 1:
                ticket, info, deals, profit = group_closures[0]
                notify_tg(build_trade_report(symbol, info, ticket, deals, profit))
            else:
                notify_tg(build_group_close_report(symbol, group_closures))
        except Exception as exc:
            print(f"[REPORT] ❌ تعذر بناء تقرير {key}: {exc}")

        group_id = group_closures[0][1].get("group_id")
        if not group_id:
            continue
        for ticket, info, _, profit in group_closures:
            record = _group_results.setdefault(group_id, {
                "channel": info.get("channel"),
                "direction": info.get("direction"),
                "zone": (
                    (info["zone_low"], info["zone_high"])
                    if info.get("zone_low") is not None
                    else None
                ),
                "started": float(info.get("opened_at") or time.time()),
                "trades": [],
            })
            record["started"] = min(
                record["started"], float(info.get("opened_at") or time.time())
            )
            record["trades"].append({
                "ticket": ticket,
                "profit": profit,
                "peak": float(info.get("peak_move", 0.0)),
                "worst": float(info.get("worst_move", 0.0)),
            })
        if _recommendation_finished(group_id):
            finished = _group_results.pop(group_id, None)
            if finished and finished["trades"]:
                try:
                    notify_tg(
                        build_recommendation_summary(symbol, group_id, finished)
                    )
                except Exception as exc:
                    print(f"[REPORT] ❌ تعذر بناء تقرير التوصية {group_id}: {exc}")
            with _zone_lock:
                stale = [
                    zkey for zkey, group in _zone_groups.items()
                    if group["meta"].get("group_id") == group_id
                ]
                for zkey in stale:
                    _zone_groups.pop(zkey, None)


def manager_thread(symbol):
    """إدارة سريعة موحدة لقناتي KINGS والحيتان."""
    while True:
        try:
            track_channel_excursions(symbol)  # قبل الإدارة: التقط حالة السوق
        except Exception as e:
            print(f"[Track] ❌ {e}")
        try:
            manage_unified_channel_groups(symbol)
        except Exception as e:
            print(f"[Manager] ❌ {e}")
        try:
            manage_manual_positions(symbol)
        except Exception as e:
            print(f"[Manual] ❌ {e}")
        try:
            report_closed_channel_trades(symbol)
        except Exception as e:
            print(f"[Report] ❌ {e}")
        time.sleep(CHANNEL_MANAGER_INTERVAL_SECONDS)


def zone_watcher_thread(symbol):
    """خيط مستقل لا يفعل شيئاً سوى فتح مستويات المنطقة عند لمس السعر.

    فُصل عن خيط الإدارة لأن الإدارة تستعلم عن الصفقات والأوامر وتعدلها،
    فكان لمس المستوى ينتظرها. هنا لا شيء بين قراءة السعر وإرسال الأمر."""
    while True:
        try:
            busy = open_due_zone_levels(symbol)
        except Exception as e:
            print(f"[ZONE] ❌ {e}")
            busy = False
        time.sleep(
            ZONE_WATCH_INTERVAL_SECONDS if busy else ZONE_IDLE_INTERVAL_SECONDS
        )


# ═════════════════════════════════════════════
#  الجزء ٦.٥ — الأنماط الفنية الكلاسيكية
#  (قمة/قاع مزدوج، رأس وكتفين، مثلثات)
# ═════════════════════════════════════════════
def _find_swings(rates, lookback=2):
    """يجد القمم والقيعان المحلية في الشموع."""
    highs = [r["high"] for r in rates]
    lows = [r["low"] for r in rates]
    swings = []  # (index, price, 'H' أو 'L')
    for i in range(lookback, len(rates) - lookback):
        if highs[i] == max(highs[i - lookback : i + lookback + 1]):
            swings.append((i, highs[i], "H"))
        elif lows[i] == min(lows[i - lookback : i + lookback + 1]):
            swings.append((i, lows[i], "L"))
    return swings


def detect_chart_pattern(symbol):
    """يبحث عن أنماط فنية كلاسيكية على فريم M15.
    يعيد (اسم النمط بالعربي، الاتجاه) أو None."""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 120)
    if rates is None or len(rates) < 60:
        return None

    swings = _find_swings(rates)
    if len(swings) < 5:
        return None

    price = rates[-1]["close"]
    tol = price * 0.0006  # سماحية التطابق (~0.06%)

    # آخر 7 تأرجحات بترتيبها الزمني (قمم وقيعان متداخلة)
    seq = swings[-7:]

    def between_low(i1, i2):
        return min(r["low"] for r in rates[i1 : i2 + 1])

    def between_high(i1, i2):
        return max(r["high"] for r in rates[i1 : i2 + 1])

    # ── قمة مزدوجة → بيع: قمة، قاع بينهما، قمة مساوية، ثم كسر القاع ──
    for k in range(len(seq) - 2):
        a, b, c = seq[k], seq[k + 1], seq[k + 2]
        if a[2] == "H" and b[2] == "L" and c[2] == "H":
            if abs(a[1] - c[1]) < tol and price < b[1]:
                return ("قمة مزدوجة Double Top", "SELL")
        if a[2] == "L" and b[2] == "H" and c[2] == "L":
            if abs(a[1] - c[1]) < tol and price > b[1]:
                return ("قاع مزدوج Double Bottom", "BUY")

    # ── رأس وكتفين → بيع: قمة/قاع/قمة أعلى/قاع/قمة، ثم كسر خط العنق ──
    for k in range(len(seq) - 4):
        p5 = seq[k : k + 5]
        types = "".join(s[2] for s in p5)
        if types == "HLHLH":
            ls, t1, hd, t2, rs = p5
            if (
                hd[1] > ls[1] + tol
                and hd[1] > rs[1] + tol
                and abs(ls[1] - rs[1]) < tol * 2
            ):
                neck = min(t1[1], t2[1])
                if price < neck:
                    return ("رأس وكتفين Head & Shoulders", "SELL")
        if types == "LHLHL":
            ls, t1, hd, t2, rs = p5
            if (
                hd[1] < ls[1] - tol
                and hd[1] < rs[1] - tol
                and abs(ls[1] - rs[1]) < tol * 2
            ):
                neck = max(t1[1], t2[1])
                if price > neck:
                    return ("رأس وكتفين معكوس Inv H&S", "BUY")

    # ── مثلثات: قمتان وقاعان متعاقبان زمنياً ──
    for k in range(len(seq) - 3):
        p4 = seq[k : k + 4]
        types = "".join(s[2] for s in p4)
        if types == "HLHL":
            h1, l1, h2, l2 = p4
            # مثلث صاعد: قمم متساوية + قيعان ترتفع + كسر لأعلى
            if abs(h1[1] - h2[1]) < tol and l2[1] > l1[1] + tol and price > h2[1]:
                return ("مثلث صاعد Ascending Triangle", "BUY")
        if types == "LHLH":
            l1, h1, l2, h2 = p4
            # مثلث هابط: قيعان متساوية + قمم تنخفض + كسر لأسفل
            if abs(l1[1] - l2[1]) < tol and h2[1] < h1[1] - tol and price < l2[1]:
                return ("مثلث هابط Descending Triangle", "SELL")

    return None


# ═════════════════════════════════════════════
#  الجزء ٧ — الحلقة الرئيسية
# ═════════════════════════════════════════════
# وضع المحاكي: يُفعّل بـ --solo أو تلقائياً إذا لم توجد قنوات مثبتة
_solo = {"on": False}


_STRAT_MAGICS = (MAGIC_PATTERN, MAGIC_CHART, MAGIC_BOOK, MAGIC_MIMIC, MAGIC_LONDON)


def _strategy_conflict(symbol, direction):
    """هل توجد صفقة استراتيجية مفتوحة بالاتجاه المعاكس؟
    يمنع فتح شراء وبيع ضد بعضهما في نفس الوقت."""
    try:
        want_buy = direction == "BUY"
        for p in mt5.positions_get(symbol=symbol) or []:
            if p.magic in _STRAT_MAGICS:
                is_buy = p.type == mt5.POSITION_TYPE_BUY
                if is_buy != want_buy:
                    return True
    except Exception:
        return True  # عند الشك لا نفتح
    return False


def _recent_mimic(symbol, hours=2):
    """هل توجد صفقة محاكي مفتوحة أو أُغلقت خلال آخر ساعتين؟
    (حماية من تكرار الصفقات بعد إعادة تشغيل البوت)"""
    try:
        for p in mt5.positions_get(symbol=symbol) or []:
            if p.magic == MAGIC_MIMIC:
                return True
        frm = datetime.now() - timedelta(hours=hours)
        for d in mt5.history_deals_get(frm, datetime.now()) or []:
            if d.magic == MAGIC_MIMIC:
                return True
    except Exception:
        return True  # عند الشك لا نفتح
    return False
# ═════════════════════════════════════════════
#  الجزء ٦.٥ — التقرير اليومي على تيليغرام
# ═════════════════════════════════════════════
MAGIC_NAMES = {
    MAGIC_BOOK: "📚 استراتيجيات الكتاب",
    MAGIC_PATTERN: "🕯️ أنماط الشموع",
    MAGIC_SIGNAL: "📌 التوصيات",
    MAGIC_CHART: "📐 الأنماط الفنية",
    MAGIC_WHALES: "🐋 قناة WHALES",
    MAGIC_KINGS: "👑 قناة KINGS",
    MAGIC_GOLDBOT: "🤖 بوت التوصيات",
    MAGIC_MIMIC: "🤖 المحاكي",
    MAGIC_LONDON: "🇬🇧 اختراق لندن",
}


def build_daily_report(symbol):
    """يبني تقرير اليوم من تاريخ صفقات MT5 مقسماً حسب magic numbers.
    يرجع None إذا فشلت قراءة التاريخ."""
    day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    deals = mt5.history_deals_get(day_start, day_end)
    if deals is None:
        return None

    # نجمع صفقات الإغلاق فقط (entry=OUT) الخاصة بالبوت
    stats = {}  # magic -> {"profit": x, "wins": n, "losses": n}
    for d in deals:
        if d.magic not in MAGIC_NAMES:
            continue
        if d.entry != mt5.DEAL_ENTRY_OUT:
            continue
        net = d.profit + d.commission + d.swap
        s = stats.setdefault(d.magic, {"profit": 0.0, "wins": 0, "losses": 0})
        s["profit"] += net
        if net > 0:
            s["wins"] += 1
        else:
            s["losses"] += 1

    date_str = day_start.strftime("%Y-%m-%d")
    if not stats:
        return (
            f"📅 <b>التقرير اليومي — {date_str}</b>\n\n"
            f"لا توجد صفقات مغلقة اليوم.\n\n"
            f"📊 <b>سجل الاستراتيجيات:</b>\n{strategy_killer.summary_ar()}"
        )

    total = sum(s["profit"] for s in stats.values())
    total_wins = sum(s["wins"] for s in stats.values())
    total_losses = sum(s["losses"] for s in stats.values())

    lines = []
    for magic, s in sorted(stats.items(), key=lambda kv: kv[1]["profit"], reverse=True):
        icon = "🟢" if s["profit"] > 0 else ("🔴" if s["profit"] < 0 else "⚪")
        lines.append(
            f"{icon} {MAGIC_NAMES[magic]}: <b>${s['profit']:+.2f}</b> "
            f"(ربح {s['wins']} / خسارة {s['losses']})"
        )

    total_icon = "🟢" if total > 0 else ("🔴" if total < 0 else "⚪")
    return (
        f"📅 <b>التقرير اليومي — {date_str}</b>\n\n"
        f"{total_icon} <b>الصافي: ${total:+.2f}</b> "
        f"({total_wins + total_losses} صفقة: {total_wins} ربح / {total_losses} خسارة)\n\n"
        f"📋 <b>حسب النظام:</b>\n" + "\n".join(lines) + "\n\n"
        f"📊 <b>سجل الاستراتيجيات:</b>\n{strategy_killer.summary_ar()}"
    )


DAILY_REPORT_FILE = "daily_report_state.json"  # يحفظ آخر يوم أُرسل تقريره (يمنع التكرار بعد إعادة التشغيل)


def _load_daily_report_state():
    try:
        if os.path.exists(DAILY_REPORT_FILE):
            with open(DAILY_REPORT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def _save_daily_report_state(state):
    try:
        tmp = DAILY_REPORT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp, DAILY_REPORT_FILE)
    except Exception as e:
        print(f"[📅] ⚠️ فشل حفظ حالة التقرير: {e}")


def maybe_send_daily_report(symbol, state):
    """يرسل التقرير مرة واحدة يومياً بعد الساعة 23:00.
    الحالة محفوظة على القرص فلا يتكرر التقرير بعد إعادة التشغيل."""
    now = datetime.now()
    if now.hour < 23:
        return
    today = now.strftime("%Y-%m-%d")
    if state.get("last_day") == today:
        return
    report = build_daily_report(symbol)
    if report is None:
        return  # تاريخ MT5 غير متاح الآن — نحاول في الدورة القادمة
    if not send_tg(report):
        return  # فشل الإرسال — لا نسجل اليوم حتى نعيد المحاولة في الدورة القادمة
    state["last_day"] = today
    _save_daily_report_state(state)
    print(f"[📅] أُرسل التقرير اليومي ({today})")


def main_loop(symbol, lot, pattern_lookup, solo=False):
    if solo:
        _solo["on"] = True
    _daily_report_state = _load_daily_report_state()
    last_fp, last_fp_time = "", 0
    last_book_time = 0
    last_chart_name, last_chart_time = "", 0
    last_chart_scan = 0
    last_mimic_scan = 0
    last_mimic_trade = 0
    last_london_scan = 0
    last_london_day = ""
    london_count_today = 0
    last_london_trade = 0
    bad_hour_notified = -1
    cycle = 0

    print(f"\n{'═' * 55}")
    print(f"  🐋 MASTER BOT يعمل — القناتان + الاستراتيجيات (لوت {STRAT_LOT})")
    if solo:
        print(f"  🤖 وضع المحاكي مفعّل — يتداول من دروس القنوات")
    print(f"{'═' * 55}\n")

    start_ts = int(time.time())

    while True:
        try:
            cycle += 1
            now_ts = int(time.time())
            # فترة إحماء: أول 10 دقائق بعد التشغيل بدون صفقات استراتيجيات
            # (حتى لا يفتح البوت صفقات فورية على إشارات قديمة لحظة التشغيل)
            warmed_up = (now_ts - start_ts) > 600
            now_str = datetime.now().strftime("%H:%M:%S")
            tick = mt5.symbol_info_tick(symbol)
            price = tick.bid if tick else 0

            # ── ١: فحص الصفقات المغلقة (تعلم) ──
            check_closed_trades(symbol)

            # ── التقرير اليومي (قبل أي حارس يوقف الحلقة — يعمل حتى في الساعات المحظورة) ──
            maybe_send_daily_report(symbol, _daily_report_state)

            # ── حارس الساعات الخاسرة (من التعلم الذاتي) ──
            cur_hour = datetime.now().hour
            if learner.is_bad_hour(cur_hour):
                if bad_hour_notified != cur_hour:
                    bad_hour_notified = cur_hour
                    print(f"[{now_str}] ⛔ الساعة {cur_hour}:00 محظورة — لا صفقات جديدة")
                    send_tg(
                        f"⏸️ <b>توقف مؤقت</b>\n\n"
                        f"الساعة {cur_hour}:00 محظورة — البوت خسر فيها كثيراً سابقاً.\n"
                        f"سيستأنف التداول في الساعة القادمة."
                    )
                time.sleep(SCAN_INTERVAL)
                continue

            # ── فلتر الاتجاه العام (H1) — نتداول مع التيار فقط ──
            trend = h1_trend(symbol) if warmed_up else None

            # ── ٢: فحص الأنماط ──
            live_fp = (
                get_live_fingerprint(symbol)
                if warmed_up and strategy_killer.alive("Pattern")
                else ""
            )
            if live_fp in pattern_lookup and not learner.is_blocked(live_fp):
                match = pattern_lookup[live_fp]
                fresh = live_fp != last_fp or (now_ts - last_fp_time) > 1800
                if fresh and match["direction"] != trend:
                    print(f"[{now_str}] 🌊 نمط {match['direction']} ضد اتجاه H1 — تجاهل")
                    last_fp, last_fp_time = live_fp, now_ts
                    fresh = False
                if fresh and _strategy_conflict(symbol, match["direction"]):
                    print(f"[{now_str}] ⚔️ نمط {match['direction']} يعارض صفقة استراتيجية مفتوحة — تجاهل")
                    last_fp, last_fp_time = live_fp, now_ts
                    fresh = False
                if fresh:
                    d_ar = "📈 صعود" if match["direction"] == "BUY" else "📉 هبوط"
                    print(f"[{now_str}] 🎯 نمط متكرر! {d_ar} | {match['rate']:.0f}%")
                    # TP ثابت 30 نقطة (بطلب المستخدم)
                    pattern_tp = 30
                    ok = open_trade(
                        symbol,
                        match["direction"],
                        STRAT_LOT,
                        sl_pips=STRAT_SL_PIPS,
                        tp_pips=STRAT_TP_PIPS,
                        magic=MAGIC_PATTERN,
                        comment="Pattern",
                        fp=live_fp,
                    )
                    send_tg(
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🐋 <b>نمط متكرر — {symbol}</b>\n━━━━━━━━━━━━━━━━━━\n\n"
                        f"<b>{d_ar}</b> | السعر: {price:.2f}\n\n"
                        f"📊 <b>الشموع:</b>\n{fp_arabic(live_fp)}\n\n"
                        f"📈 تكرر {match['total']}x | نجاح {match['rate']:.0f}% | "
                        f"متوسط {match['avg']:.0f}p\n"
                        f"🎯 ستوب: $5 | هدف: $10\n\n"
                        f"{'✅ صفقة مفتوحة' if ok else '❌ لم تفتح'}"
                    )
                    last_fp, last_fp_time = live_fp, now_ts

            # ── ٢.٥: الأنماط الفنية الكلاسيكية (فحص كل 5 دقائق) ──
            if warmed_up and strategy_killer.alive("ChartPattern") and now_ts - last_chart_scan > 300:
                last_chart_scan = now_ts
                chart = detect_chart_pattern(symbol)
                if chart:
                    name_ar, cdir = chart
                    # لا نكرر نفس النمط خلال ساعتين + لا نعارض صفقة استراتيجية مفتوحة
                    if cdir != trend:
                        print(f"[{now_str}] 🌊 نمط فني {cdir} ضد اتجاه H1 — تجاهل")
                    elif _strategy_conflict(symbol, cdir):
                        print(f"[{now_str}] ⚔️ نمط فني {cdir} يعارض صفقة مفتوحة — تجاهل")
                    elif not (
                        name_ar == last_chart_name
                        and now_ts - last_chart_time < 7200
                    ):
                        print(f"[{now_str}] 📐 نمط فني: {name_ar} → {cdir}")
                        ok = open_trade(
                            symbol,
                            cdir,
                            STRAT_LOT,
                            sl_pips=STRAT_SL_PIPS,
                            tp_pips=STRAT_TP_PIPS,
                            magic=MAGIC_CHART,
                            comment="ChartPattern",
                        )
                        send_tg(
                            f"📐 <b>نمط فني كلاسيكي — {symbol}</b>\n\n"
                            f"النمط: <b>{name_ar}</b>\n"
                            f"{'📈 شراء' if cdir == 'BUY' else '📉 بيع'} | "
                            f"السعر: {price:.2f}\n"
                            f"🎯 ستوب: $5 | هدف: $10\n\n"
                            f"{'✅ صفقة مفتوحة' if ok else '❌ لم تفتح'}"
                        )
                        if ok:
                            last_chart_name, last_chart_time = name_ar, now_ts

            # ── ٣: استراتيجيات الكتاب (كل 5 دقائق) ──
            if warmed_up and strategy_killer.alive("BookStrategy") and now_ts - last_book_time > 300:
                last_book_time = now_ts
                sig = run_book_strategies(symbol)
                if sig and sig.action != "NO TRADE":
                    min_score = learner.get_min_score()
                    if sig.action != trend:
                        print(f"[{now_str}] 🌊 إشارة كتاب {sig.action} ضد اتجاه H1 — تجاهل")
                    elif _strategy_conflict(symbol, sig.action):
                        print(f"[{now_str}] ⚔️ إشارة كتاب {sig.action} تعارض صفقة مفتوحة — تجاهل")
                    elif sig.confidence_score >= min_score:
                        print(
                            f"[{now_str}] 📚 إشارة كتاب: {sig.action} | نقاط: {sig.confidence_score}"
                        )
                        ok = open_trade(
                            symbol,
                            sig.action,
                            STRAT_LOT,
                            sl_pips=STRAT_SL_PIPS,
                            tp_pips=STRAT_TP_PIPS,
                            magic=MAGIC_BOOK,
                            comment="BookStrategy",
                        )
                        if ok:
                            send_tg(
                                f"📚 <b>إشارة استراتيجيات الكتاب</b>\n\n"
                                f"{'📈 شراء' if sig.action == 'BUY' else '📉 بيع'} — {symbol}\n"
                                f"النقاط: {sig.confidence_score} | الثقة: {sig.confidence_pct:.0f}%\n"
                                f"الاستراتيجيات: {len(sig.active_strategies)}\n"
                                f"✅ صفقة مفتوحة"
                            )
                    else:
                        print(
                            f"[{now_str}] 📚 {sig.action} نقاط {sig.confidence_score} < الحد {min_score} — تجاهل"
                        )

            # ── ٣.٢: اختراق افتتاح لندن (كل 5 دقائق، صفقة واحدة يومياً) ──
            if (
                warmed_up
                and strategy_killer.alive("London")
                and now_ts - last_london_scan > 300
            ):
                last_london_scan = now_ts
                today = utc_now().date().isoformat()
                if last_london_day != today:
                    last_london_day = today
                    london_count_today = 0
                # حتى 3 صفقات لندن يومياً بفاصل ساعة بينها
                if london_count_today < 3 and now_ts - last_london_trade > 3600:
                    ldir = london_breakout_signal(symbol)
                    if ldir and ldir == trend and not _strategy_conflict(symbol, ldir):
                        print(f"[{now_str}] 🇬🇧 اختراق لندن: {ldir}")
                        ok = open_trade(
                            symbol,
                            ldir,
                            STRAT_LOT,
                            sl_pips=STRAT_SL_PIPS,
                            tp_pips=STRAT_TP_PIPS,
                            magic=MAGIC_LONDON,
                            comment="London",
                        )
                        if ok:
                            london_count_today += 1
                            last_london_trade = now_ts
                            send_tg(
                                f"🇬🇧 <b>اختراق افتتاح لندن — {symbol}</b>\n\n"
                                f"{'📈 شراء' if ldir == 'BUY' else '📉 بيع'} | السعر: {price:.2f}\n"
                                f"السعر اخترق مدى الجلسة الآسيوية مع اتجاه H1\n"
                                f"🎯 ستوب: $5 | هدف: $10\n\n"
                                f"✅ صفقة مفتوحة (لندن {london_count_today}/3 اليوم)"
                            )

            # ── ٣.٥: المحاكي — يتداول من دروس القنوات (--solo أو غياب القنوات) ──
            if _solo["on"] and strategy_killer.alive("Mimic") and now_ts - last_mimic_scan > 300:
                last_mimic_scan = now_ts
                sug = channel_learner.suggest(symbol)
                # صفقة محاكي واحدة كحد أقصى كل ساعتين (حتى بعد إعادة التشغيل)
                if sug and now_ts - last_mimic_trade > 7200 and not _recent_mimic(symbol):
                    d = sug["direction"]
                    t2 = mt5.symbol_info_tick(symbol)
                    if t2:
                        p2 = t2.ask if d == "BUY" else t2.bid
                        slm = p2 - MIMIC_SL_USD if d == "BUY" else p2 + MIMIC_SL_USD
                        tpm = p2 + MIMIC_TP_USD if d == "BUY" else p2 - MIMIC_TP_USD
                        ok = open_trade(
                            symbol, d, MIMIC_LOT,
                            sl_price=round(slm, 2), tp_price=round(tpm, 2),
                            magic=MAGIC_MIMIC, comment="Mimic",
                        )
                        if ok:
                            last_mimic_trade = now_ts
                            send_tg(
                                f"🤖 <b>صفقة المحاكي (تعلمتها من القنوات)</b>\n\n"
                                f"{'📈 شراء' if d == 'BUY' else '📉 بيع'} — {symbol}\n"
                                f"الشارت الآن يشبه {sug['count']} توصية سابقة "
                                f"نجحت بنسبة {sug['rate']:.0f}%\n"
                                f"اللوت: {MIMIC_LOT} | ستوب: $5 | هدف: $10"
                            )

            # ── ٤: تقرير كل 30 دورة ──
            if cycle % 30 == 0:
                print(f"[{now_str}] 🧠 {learner.summary()}")
            else:
                print(f"[{now_str}] 🔍 السعر: {price:.2f} | دورة {cycle}")

            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\n[⛔] إيقاف البوت.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(30)


def self_test(symbol):
    """يفحص كل أنظمة البوت ويطبع قائمة ✅/❌ ويرسلها على تيليغرام."""
    print(f"\n{'═' * 55}")
    print(f"  🩺 الفحص الذاتي — MASTER BOT")
    print(f"{'═' * 55}\n")

    results = []  # (ok, name, detail)

    def add(ok, name, detail=""):
        icon = "✅" if ok else "❌"
        line = f"{icon} {name}" + (f" — {detail}" if detail else "")
        print(line)
        results.append((ok, name, detail))

    # ── ١: اتصال MT5 ──
    mt5_ok = mt5.initialize()
    if not mt5_ok:
        add(False, "الاتصال بـ MT5", f"غير متصل! افتح منصة MT5 أولاً ({mt5.last_error()})")
    else:
        acc = mt5.account_info()
        if acc:
            add(True, "الاتصال بـ MT5", f"حساب {acc.login} | رصيد ${acc.balance:.2f}")
        else:
            add(False, "الاتصال بـ MT5", "متصل لكن لا يوجد حساب مسجّل دخول!")

    # ── ٢: التداول الآلي (Algo Trading) — يكشف خطأ 10027 مسبقاً ──
    if mt5_ok:
        term = mt5.terminal_info()
        if term and term.trade_allowed:
            add(True, "التداول الآلي (Algo Trading)", "مفعّل")
        else:
            add(
                False,
                "التداول الآلي (Algo Trading)",
                "معطّل! اضغط زر 'Algo Trading' الأخضر في شريط MT5 العلوي "
                "(هذا سبب خطأ 10027)",
            )

        # ── ٣: الرمز ──
        sym = mt5.symbol_info(symbol)
        if sym is None:
            # نحاول اقتراح رمز مشابه
            similar = [
                s.name for s in (mt5.symbols_get("*XAU*") or [])
            ][:5]
            hint = f"جرّب: {', '.join(similar)}" if similar else "تأكد من اسم الرمز عند وسيطك"
            add(False, f"الرمز {symbol}", f"غير موجود! {hint}")
        else:
            if not sym.visible:
                mt5.symbol_select(symbol, True)
            tick = mt5.symbol_info_tick(symbol)
            if tick and tick.bid > 0:
                add(True, f"الرمز {symbol}", f"السعر الحالي: {tick.bid:.2f}")
            else:
                add(False, f"الرمز {symbol}", "موجود لكن لا يصل سعر (السوق مغلق؟)")
    else:
        add(False, "التداول الآلي (Algo Trading)", "تخطي — MT5 غير متصل")
        add(False, f"الرمز {symbol}", "تخطي — MT5 غير متصل")

    # ── ٤: بوت تيليغرام (الإرسال) ──
    tg_ok = False
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        add(False, "بوت تيليغرام (الإرسال)", "TOKEN أو CHAT_ID غير مضبوطين في config.py")
    else:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", timeout=10
            )
            if r.ok and r.json().get("ok"):
                bot_name = r.json()["result"].get("username", "؟")
                r2 = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": "🩺 اختبار إرسال — الفحص الذاتي"},
                    timeout=10,
                )
                if r2.ok and r2.json().get("ok"):
                    tg_ok = True
                    add(True, "بوت تيليغرام (الإرسال)", f"@{bot_name} — وصلتك رسالة اختبار")
                else:
                    desc = r2.json().get("description", r2.text[:80])
                    add(False, "بوت تيليغرام (الإرسال)", f"البوت صحيح لكن الإرسال فشل: {desc}")
            else:
                add(False, "بوت تيليغرام (الإرسال)", "TOKEN غير صحيح")
        except Exception as e:
            add(False, "بوت تيليغرام (الإرسال)", f"خطأ شبكة: {e}")

    # ── ٥: قارئ التوصيات (Telethon) ──
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        add(
            False,
            "قارئ التوصيات (Telethon)",
            "API_ID/API_HASH غير مضبوطين — احصل عليهم من my.telegram.org/apps",
        )
    else:
        client = None
        try:
            from telethon.sync import TelegramClient

            # فحص غير تفاعلي: connect() فقط — لا نستخدم start() حتى لا يطلب
            # رقم الهاتف/رمز التحقق ويعلّق الفحص إذا كانت الجلسة غير مفعّلة
            client = TelegramClient(
                "master_session", TELEGRAM_API_ID, TELEGRAM_API_HASH
            )
            client.connect()
            if client.is_user_authorized():
                me = client.get_me()
                pinned = [d.name for d in client.iter_dialogs() if d.pinned]
                if pinned:
                    add(
                        True,
                        "قارئ التوصيات (Telethon)",
                        f"متصل كـ {me.first_name} | محادثات مثبتة: {len(pinned)}",
                    )
                else:
                    add(
                        False,
                        "قارئ التوصيات (Telethon)",
                        f"متصل كـ {me.first_name} لكن لا توجد محادثات مثبتة! "
                        "ثبّت قناة التوصيات في تيليغرام",
                    )
            else:
                add(
                    False,
                    "قارئ التوصيات (Telethon)",
                    "الجلسة غير مفعّلة — شغّل البوت مرة عادية لإدخال رمز التحقق",
                )
        except ImportError:
            add(False, "قارئ التوصيات (Telethon)", "مكتبة telethon غير مثبتة: pip install telethon")
        except Exception as e:
            add(False, "قارئ التوصيات (Telethon)", f"خطأ: {e}")
        finally:
            if client is not None:
                try:
                    client.disconnect()
                except Exception:
                    pass

    # ── ٦: ملفات الاستراتيجيات ──
    try:
        import strategy_manager  # noqa: F401
        import signal_engine  # noqa: F401

        add(True, "استراتيجيات الكتاب", "strategy_manager + signal_engine موجودة")
    except Exception as e:
        add(False, "استراتيجيات الكتاب", f"خطأ استيراد: {e}")

    # ── ٧: ذاكرة التعلم ──
    add(True, "التعلم الذاتي", learner.summary())

    # ── النتيجة النهائية ──
    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    all_ok = passed == total

    print(f"\n{'─' * 55}")
    if all_ok:
        print(f"🎉 كل الأنظمة تعمل! ({passed}/{total})")
    else:
        print(f"⚠️ {passed}/{total} أنظمة تعمل — راجع ❌ أعلاه")
    print(f"{'─' * 55}\n")

    # إرسال التقرير على تيليغرام
    if tg_ok:
        lines = []
        for ok, name, detail in results:
            icon = "✅" if ok else "❌"
            lines.append(f"{icon} <b>{name}</b>" + (f"\n     {detail}" if detail else ""))
        header = "🎉 كل الأنظمة تعمل!" if all_ok else f"⚠️ {passed}/{total} أنظمة تعمل"
        send_tg(
            f"🩺 <b>تقرير الفحص الذاتي — MASTER BOT</b>\n"
            f"{'━' * 20}\n\n" + "\n\n".join(lines) + f"\n\n{'━' * 20}\n<b>{header}</b>"
        )

    if mt5_ok:
        mt5.shutdown()
    return all_ok


# ═════════════════════════════════════════════
#  🚀 التشغيل
# ═════════════════════════════════════════════
async def telegram_reader_diagnostic(allow_login=False):
    """يفحص جلسة Telethon والقنوات المثبتة دون انتظار رسائل أو تنفيذ صفقات."""
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        return False, "API_ID/API_HASH غير مضبوطين", []
    try:
        from telethon import TelegramClient
    except ImportError:
        return False, "مكتبة telethon غير مثبتة", []

    client = TelegramClient("master_session", TELEGRAM_API_ID, TELEGRAM_API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            if not allow_login:
                return False, "جلسة Telethon غير مفعّلة بعد", []
            await client.start(phone=TELEGRAM_PHONE or None)
            if not await client.is_user_authorized():
                return False, "فشل تفعيل جلسة Telethon", []
        pinned = []
        recognized = {}
        async for dialog in client.iter_dialogs():
            if dialog.pinned:
                name = dialog.name or ""
                pinned.append(name)
                code = channel_of(name)
                if code:
                    recognized[dialog.id] = code
        codes = list(recognized.values())
        required = set(REQUIRED_CHANNELS)
        missing = sorted(required - set(codes))
        # محادثتان بنفس الاسم المعتمد تعنيان أن إحداهما ليست القناة
        duplicated = sorted({code for code in codes if codes.count(code) > 1})
        if missing or duplicated:
            labels = {key: CHANNEL_LABELS.get(key, ("", key))[1]
                      for key in required | set(codes)}
            detail = (
                "قنوات مثبتة مفقودة: "
                + ", ".join(labels[item] for item in missing)
                if missing
                else "محادثتان مثبتتان بنفس الاسم: "
                + ", ".join(labels[item] for item in duplicated)
            )
            return False, detail, pinned
        return True, "الجلسة مفعّلة والقنوات المطلوبة مثبتة", pinned
    except Exception as exc:
        return False, f"خطأ Telethon: {exc}", []
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def channels_self_test(symbol):
    """فحص آمن لمسار القنوات فقط، دون إرسال أي أمر تداول."""
    checks = []

    def add(ok, name, detail=""):
        checks.append((bool(ok), name, detail))
        print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""))

    print(f"\n{'═' * 55}")
    print("  🩺 فحص القناتين — بدون تداول")
    print(f"{'═' * 55}\n")

    live_price = None
    mt5_ok = bool(mt5.initialize())
    add(mt5_ok, "اتصال MT5", "متصل" if mt5_ok else "افتح منصة MT5 أولاً")
    if mt5_ok:
        try:
            _channel_runtime_mode["enabled"] = True
            _channel_runtime_mode["symbol"] = symbol
            account = mt5.account_info()
            _channel_runtime_mode["account_login"] = getattr(account, "login", None)
            demo_ok = _channel_runtime_mode.get("allow_demo")
            mode_name = {
                getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", None): "حقيقي",
                getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None): "تجريبي",
            }.get(getattr(account, "trade_mode", None), "غير معروف")
            add(
                live_account_ready(),
                ("حساب حقيقي أو تجريبي" if demo_ok else "حساب حقيقي")
                + " + Algo Trading",
                f"الحساب {mode_name}"
                + ("" if demo_ok else " — أضف --demo لتجربة الحساب التجريبي"),
            )
            add(
                hedging_account_ready(account),
                "نوع الحساب Retail Hedging",
                "لازم للخمس صفقات المنفصلة؛ Netting غير مدعوم",
            )
            selected = bool(mt5.symbol_select(symbol, True))
            hint = ""
            if not selected:
                # الرمز يختلف بين الوسطاء (XAUUSD / XAUUSD.vnw / GOLD)؛
                # نبحث عن البدائل المتاحة بدل ترك المستخدم يخمّن
                try:
                    found = [
                        getattr(row, "name", "")
                        for row in (mt5.symbols_get() or [])
                        if "XAU" in getattr(row, "name", "").upper()
                        or "GOLD" in getattr(row, "name", "").upper()
                    ][:5]
                except Exception:
                    found = []
                hint = (
                    f"المتاح عندك: {' · '.join(found)} — شغّل بـ --symbol <الرمز>"
                    if found
                    else "لم أجد رمز ذهب في هذا الحساب"
                )
            add(selected, f"الرمز {symbol}", hint)
            tick = mt5.symbol_info_tick(symbol) if selected else None
            add(bool(tick), "السعر المباشر", f"{tick.bid:.2f}" if tick else "غير متاح")
            if tick:
                live_price = float(tick.bid)
                balance = getattr(account, "balance", 0.0) or 0.0
                worst_loss = CHANNEL_POSITION_COUNT * CHANNEL_INITIAL_SL_USD
                add(
                    balance > worst_loss * 3,
                    "الرصيد يحتمل مخاطرة التوصية",
                    f"الرصيد ${balance:.2f} | أقصى خسارة للتوصية ${worst_loss:.0f}",
                )
        finally:
            mt5.shutdown()
    else:
        for name in (
            "حساب حقيقي + Algo Trading",
            "نوع الحساب Retail Hedging",
            f"الرمز {symbol}",
            "السعر المباشر",
            "الرصيد يحتمل مخاطرة التوصية",
        ):
            add(False, name, "تعذر الفحص بلا اتصال MT5")

    expected = {
        "KINGS EL GOLD VIP": "kings",
        "WHALES VIP | الحيتان": "whales",
    }
    mapping_ok = all(channel_of(name) == code for name, code in expected.items())
    scalp_ignored = channel_of("KINGS EL GOLD SCALPING") is None
    add(mapping_ok and scalp_ignored, "تمييز القنوات", "SCALPING متجاهلة")

    # بوت التوصيات: نتأكد أن القراءة تفهم توصيته وترفض رسالة HOLD
    goldbot_sample = (
        "🟡 توصية الذهب\n\nالقرار: SELL\nالثقة: 85%\n\n"
        "📍 الدخول: 4308.49\n🛑 الوقف: 4314.78 (خطر $6.29)\n"
        "🎯 الهدف: 4295.92 (ربح $12.57)"
    )
    parsed_gold = parse_gold_bot_signal(goldbot_sample) or {}
    hold_sample = parse_gold_bot_signal(
        "🟡 توصية الذهب\n\nالقرار: HOLD\n🎯 الهدف: 4450.09\n🛑 الوقف: 4450.09"
    ) or {}
    add(
        parsed_gold.get("decision") == "SELL"
        and parsed_gold.get("risk") == 6.29
        and parsed_gold.get("reward") == 12.57
        and hold_sample.get("decision") == "HOLD",
        "قراءة بوت التوصيات",
        "بيع بوقف $6.29 وهدف $12.57 · وHOLD لا يفتح شيئاً",
    )

    # ── قراءة توصية نموذجية وعرض ما كان البوت سيفعله (بلا أي أمر) ──
    sample = (
        "بسم الله\nGold buy Now 4231-4226\n"
        "* Tp1 4236\n* Tp2 4255\n* Tp3 4315\n* Tp4 open\nSL 4221"
    )
    sample_direction = parse_direction(sample)
    sample_zone = parse_entry_zone(sample)
    sample_tps = parse_tps(sample)
    sample_levels = (
        zone_entry_levels(sample_direction, *sample_zone)
        if sample_direction and sample_zone
        else []
    )
    add(
        sample_direction == "BUY"
        and sample_zone == (4226.0, 4231.0)
        and sample_levels == [4226.0, 4227.0, 4228.0, 4229.0, 4230.0]
        and sample_tps == [4236.0, 4255.0, 4315.0, "open"],
        "قراءة رسالة المنطقة",
        f"اتجاه {sample_direction} | منطقة {sample_zone} | "
        f"{len(sample_levels)} مستويات",
    )
    add(
        bool(sample_levels)
        and sum(
            1
            for level in sample_levels
            if _zone_level_is_due("BUY", level, types.SimpleNamespace(ask=4228.0, bid=4228.0))
        ) == 3,
        "توزيع المستويات عند سعر تجريبي 4228",
        "٣ صفقات فوراً ثم واحدة عند كل مستوى أعلى",
    )
    add(
        not _zone_groups,
        "لا مجموعات منطقة عالقة",
        "الفحص لم يسجل أي مجموعة ولم يرسل أمراً",
    )
    if live_price:
        print(
            f"ℹ️  لو وصلت هذه التوصية الآن والسعر {live_price:.2f}: "
            f"كان سيفتح فوراً "
            f"{sum(1 for lv in sample_levels if lv <= live_price)} من "
            f"{len(sample_levels)} (أرقام التوصية تجريبية)"
        )

    reader_ok, reader_detail, pinned = asyncio.run(
        telegram_reader_diagnostic(allow_login=True)
    )
    add(reader_ok, "جلسة Telegram والقنوات المثبتة", reader_detail)

    notification_configured = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    if notification_configured:
        notification_ok = send_tg(
            "🩺 <b>اختبار بوت القنوات</b>\n\n"
            "✅ اتصال إشعارات Telegram يعمل.\n"
            "هذا فحص فقط — لم تُفتح أي صفقة."
        )
    else:
        notification_ok = False
    add(
        notification_ok,
        "إشعارات Telegram",
        "وصلت رسالة الاختبار" if notification_ok else "تحقق من Bot Token وChat ID",
    )

    if pinned:
        recognized = [name for name in pinned if channel_of(name)]
        print("📌 القنوات المعروفة المثبتة:")
        for name in recognized:
            print(f"   • {name}")

    passed = sum(1 for ok, _, _ in checks if ok)
    print(f"\nالنتيجة: {passed}/{len(checks)} فحوص ناجحة")
    return passed == len(checks)


def channels_only_loop():
    """يبقي البوت حياً ويراقب استمرار الحساب الحقيقي نفسه."""
    last_guard_notice = False
    cycle = 0
    print("\n[CHANNELS] ✅ يراقب القناتين فقط. اضغط Ctrl+C للإيقاف.\n")
    while True:
        try:
            cycle += 1
            safe = live_account_ready()
            if not safe and not last_guard_notice:
                last_guard_notice = True
                _runtime_safety["suspended"] = True
                cancelled_ok, cancelled = cancel_channel_pending_orders(
                    strict_account=False
                )
                if cancelled_ok:
                    print(
                        "[LIVE-GUARD] ⛔ عُلّق التنفيذ وأُلغيت "
                        f"{cancelled} أوامر قناة معلقة"
                    )
                    send_tg(
                        "⛔ <b>توقف أمان</b>\n\n"
                        "فقد البوت الحساب الحقيقي المحدد أو Algo Trading.\n"
                        f"أُلغيت أوامر القنوات المعلقة: {cancelled}.\n"
                        "لن تُرسل أوامر جديدة حتى نجاح فحص الاستعادة."
                    )
                else:
                    print("[LIVE-GUARD] 🚨 تعذر الوصول للأوامر المعلقة لإلغائها")
                    send_tg(
                        "🚨 <b>تنبيه حرج</b>\n\n"
                        "فقد البوت تحقق الحساب وتعذر إلغاء الأوامر المعلقة بسبب "
                        "الاتصال/الصلاحيات. قد تبقى أوامر سابقة لدى الوسيط حتى انتهاء "
                        "صلاحيتها (24 ساعة). التنفيذ الجديد معلّق."
                    )
            elif safe:
                if last_guard_notice:
                    cleanup_ok, cancelled = cancel_channel_pending_orders(
                        strict_account=True
                    )
                    if not cleanup_ok:
                        print("[LIVE-GUARD] ⛔ فشل تنظيف الأوامر بعد عودة الاتصال")
                        time.sleep(30)
                        continue
                    if not resume_channel_runtime_if_verified(DEFAULT_SYMBOL):
                        print(
                            "[LIVE-GUARD] ⛔ عاد الاتصال لكن حجر التنفيذ "
                            "لم يُنظف بعد"
                        )
                        time.sleep(30)
                        continue
                    send_tg(
                        "✅ عاد اتصال الحساب الحقيقي المحدد واكتمل فحص الاستعادة"
                        + (
                            f" — أُلغي {cancelled} أمر معلق قديم."
                            if cancelled
                            else "."
                        )
                    )
                last_guard_notice = False
                if cycle % 2 == 0:
                    # نبضة اطمئنان فقط — لا علاقة لها بسرعة العمل. تذكر
                    # الفواصل الفعلية حتى لا تُقرأ وكأن البوت يفحص كل دقيقة
                    symbol = _channel_runtime_mode.get("symbol") or DEFAULT_SYMBOL
                    open_count = len(mt5.positions_get(symbol=symbol) or [])
                    with _zone_lock:
                        pending_levels = sum(
                            1
                            for group in _zone_groups.values()
                            if not group["finished"]
                            for level in group["levels"]
                            if not level["filled"]
                        )
                    print(
                        f"[CHANNELS {datetime.now():%H:%M:%S}] حيّ | "
                        f"تيليغرام: فوري · المستويات: "
                        f"{ZONE_WATCH_INTERVAL_SECONDS * 1000:.0f}ms · "
                        f"الإدارة: {CHANNEL_MANAGER_INTERVAL_SECONDS * 1000:.0f}ms"
                        f" | مفتوح: {open_count} · بانتظار مستوى: {pending_levels}"
                    )
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n[⛔] إيقاف بوت القنوات.")
            break
        except Exception as exc:
            print(f"[CHANNELS] ❌ {exc}")
            time.sleep(30)


def main():
    parser = argparse.ArgumentParser(
        description="بوت XAUUSD — KINGS والحيتان"
    )
    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help=f"رمز الذهب عند وسيطك (الافتراضي {DEFAULT_SYMBOL})",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="فحص اتصال MT5 وTelegram وتمييز القنوات دون فتح صفقات",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="السماح بالحساب التجريبي للتجربة قبل المال الحقيقي",
    )
    args = parser.parse_args()

    _channel_runtime_mode["allow_demo"] = bool(args.demo)
    if args.demo:
        print("[DEMO] ⚠️ وضع التجربة: الحساب التجريبي مسموح في هذه الجلسة")

    if args.test:
        channels_self_test(args.symbol)
        return

    print(f"\n{'═' * 55}")
    print(
        f"  🐋 بوت القنوات — نسخة {BOT_VERSION} — "
        + ("حساب تجريبي (تجربة)" if args.demo else "حساب حقيقي")
    )
    print(f"  {args.symbol} | KINGS + WHALES")
    print("  🚫 رجائي/الذكاء/SCALPING/الاستراتيجيات القديمة: متوقفة")
    print(f"{'═' * 55}\n")

    if not mt5.initialize():
        print("[ERROR] MT5 غير مفتوح!")
        return
    _channel_runtime_mode["enabled"] = True
    _channel_runtime_mode["symbol"] = args.symbol
    account = mt5.account_info()
    _channel_runtime_mode["account_login"] = getattr(account, "login", None)
    if not live_account_ready():
        print(
            "[LIVE-GUARD] ⛔ يجب فتح حساب MT5 "
            + ("حقيقي أو تجريبي" if args.demo else "حقيقي")
            + " وتفعيل Algo Trading"
        )
        send_tg(
            "⛔ <b>لم يبدأ بوت القنوات</b>\n\n"
            "الحساب غير مطابق، أو الاتصال/Algo Trading غير مسموح."
        )
        mt5.shutdown()
        return
    account = mt5.account_info()
    if not hedging_account_ready(account):
        print("[HEDGING-GUARD] ⛔ يلزم حساب MT5 من نوع Retail Hedging")
        send_tg(
            "⛔ <b>لم يبدأ بوت القنوات</b>\n\n"
            "السياسة تتطلب خمس صفقات منفصلة، لذلك يلزم حساب من نوع "
            "Retail Hedging. حساب Netting غير مدعوم."
        )
        mt5.shutdown()
        return
    if not mt5.symbol_select(args.symbol, True):
        print(f"[MT5] ⛔ تعذر تفعيل الرمز {args.symbol}")
        mt5.shutdown()
        return
    reader_ok, reader_detail, _ = asyncio.run(
        telegram_reader_diagnostic(allow_login=True)
    )
    if not reader_ok:
        print(f"[TG-Reader] ⛔ {reader_detail}")
        send_tg(
            "⛔ <b>لم يبدأ بوت القنوات</b>\n\n"
            f"{reader_detail}\n"
            "يجب تثبيت اسمَي KINGS والحيتان كاملين ثم تشغيل أداة الفحص."
        )
        mt5.shutdown()
        return
    pending_ok, cancelled = cancel_channel_pending_orders(strict_account=True)
    if not pending_ok:
        print("[MT5] ⛔ توقف التشغيل لأن تنظيف الأوامر المعلقة القديمة لم ينجح")
        mt5.shutdown()
        return
    if cancelled:
        send_tg(
            f"🗑️ أُلغي {cancelled} أمر معلق من تشغيل سابق قبل بدء المراقبة الجديدة."
        )
    if not reconcile_startup_channel_exposure(args.symbol):
        print(
            "[STARTUP-SAFETY] ⛔ لم يبدأ المستمع لأن تعرضاً قديماً "
            "لم يُنظف أو لم تُحسم هويته"
        )
        send_tg(
            "⛔ <b>لم يبدأ بوت القنوات</b>\n\n"
            "توجد صفقة قديمة أو هوية تنفيذ محجورة لم يؤكد MT5 تنظيفها."
        )
        mt5.shutdown()
        return
    if not resume_channel_runtime_if_verified(args.symbol):
        print("[STARTUP-SAFETY] ⛔ تعذر رفع تعليق الأمان بعد فحص الاستعادة")
        mt5.shutdown()
        return
    info = mt5.account_info()
    # نوع الحساب يُقرأ من MT5 لا من الوسيط المكتوب، فلا تدّعي الرسالة
    # حساباً حقيقياً والتشغيل على تجريبي أو العكس
    real_constant = getattr(mt5, "ACCOUNT_TRADE_MODE_REAL", None)
    is_real = getattr(info, "trade_mode", None) == real_constant
    account_kind = "حقيقي" if is_real else "تجريبي"
    print(
        f"[MT5] ✅ حساب {account_kind} Retail Hedging | "
        f"#{getattr(info, 'login', '?')} | رصيد: ${info.balance:.2f}"
    )

    tg_thread = threading.Thread(
        target=telegram_listener_thread, args=(args.symbol,), daemon=True
    )
    tg_thread.start()
    mgr_thread = threading.Thread(
        target=manager_thread, args=(args.symbol,), daemon=True
    )
    mgr_thread.start()
    zone_thread = threading.Thread(
        target=zone_watcher_thread, args=(args.symbol,), daemon=True
    )
    zone_thread.start()
    time.sleep(3)
    send_tg(
        f"{'🔴' if is_real else '🧪'} <b>بوت القنوات جاهز — "
        f"حساب {account_kind} — {args.symbol}</b>\n\n"
        + (
            "" if is_real else
            "⚠️ <b>هذه تجربة على حساب تجريبي — المال وهمي.</b>\n\n"
        )
        + f"<b>نسخة البوت: {BOT_VERSION}</b>\n"
        f"({BOT_FEATURES})\n\n"
        f"الحساب: #{getattr(info, 'login', '?')} | "
        f"رصيد: ${info.balance:.2f}\n"
        f"🐋 الحيتان: {channel_policy('whales', 'position_count')} صفقات × "
        f"{channel_policy('whales', 'position_lot')} — لكل صفقة هدف "
        f"${channel_policy('whales', 'fixed_tp_usd'):g} ووقف "
        f"${channel_policy('whales', 'fixed_sl_usd'):g} من دخولها\n"
        f"👑 KINGS: صفقة واحدة × {channel_policy('kings', 'position_lot')} — "
        f"وقف $6 حتى تصل الأرقام ثم درجة خلف ستوب التوصية، "
        f"والخروج عند الهدف الأول\n"
        f"🤖 بوت التوصيات: صفقة واحدة × "
        f"{channel_policy('goldbot', 'position_lot')} — الوقف والهدف "
        f"بمسافتَي التوصية، وHOLD لا يفتح شيئاً\n"
        f"✋ ما تحرّكه بيدك — وقفاً أو هدفاً — لا يلمسه البوت بعدها "
        f"أبداً، ولا حتى عند بلوغ الأهداف\n"
        f"نوع الحساب: Retail Hedging\n\n"
        "🚫 رجائي واستراتيجية الذكاء وSCALPING وجميع الاستراتيجيات القديمة متوقفة."
    )
    channels_only_loop()
    mt5.shutdown()


if __name__ == "__main__":
    main()
