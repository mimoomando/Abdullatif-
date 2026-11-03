"""
master_bot.py
-------------
البوت الشامل — واحة جولد 🐋
يجمع 4 أنظمة في ملف واحد:

  ١- استراتيجيات كتاب أحمد حسن (18+ استراتيجية من strategy_manager)
  ٢- تحليل أشكال الشموع على M1+M5+M15+M30+H1 (الأنماط المتكررة)
  ٣- قراءة قناة تيليغرام واحدة مثبتة → فتح صفقة من التوصية
  ٤- التعلم من الصفقات السابقة والأخطاء (يعدل نفسه تلقائياً)

الاستخدام:
  python master_bot.py --channel "اسم القناة" --symbol XAUUSD
  python master_bot.py --test          ← فحص آمن دون فتح صفقات

المتطلبات:
  pip install MetaTrader5 telethon requests
"""

import MetaTrader5 as mt5
import requests
import vip_signals
import vey_signals
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

# ═════════════════════════════════════════════
# 📌 القناة الواحدة — إلزامية
# ═════════════════════════════════════════════
# البوت يقرأ من محادثة مثبتة واحدة فقط، تحددها أنت بالاسم.
# بلا اسم لا يعمل إطلاقاً: لا يقرأ المثبتة كلها ولا يخمّن.
#
# يُضبط بإحدى طريقتين:
#   python master_bot.py --channel "اسم القناة"
#   أو SIGNAL_CHANNEL_NAME = "اسم القناة"  في config.py
#
# يكفي جزء مميز من الاسم: «GOLDEN ELITE» يطابق «🥇GOLDEN ELITE | XAU».
# وإن طابق الجزءُ محادثتين توقّف البوت وطلب اسماً أدق — لا يخمّن أيّهما.
try:
    from config import SIGNAL_CHANNEL_NAME
except Exception:
    SIGNAL_CHANNEL_NAME = os.environ.get("SIGNAL_CHANNEL_NAME", "")

_only_channel = {"name": SIGNAL_CHANNEL_NAME}

# ── بيانات دخول المنصّة ──
# أربع نسخ MT5 مفتوحة على الجهاز نفسه، و--mt5-path وحده لا يكفي:
# المكتبة تصل إلى أيّها صادف. فتمرير الحساب وكلمته والخادم إلى
# initialize يُلزم المنصّة بالحساب المطلوب بدل أن نتمنّى أن تصادفه.
# وكلمة المرور لا تُكتب في سطر الأوامر أبداً — السطر يُحفظ في سجلّ
# النافذة ويظهر لكل من مرّ بالجهاز.
try:
    from config import MT5_PASSWORD
except Exception:
    MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
try:
    from config import MT5_SERVER
except Exception:
    MT5_SERVER = os.environ.get("MT5_SERVER", "")


def mt5_start(path="", login=0, server="", password="", portable=False):
    """يبدأ المنصّة ويُلزمها بالحساب المطلوب إن أُعطيت بياناته.

    يعيد (نجح، وصف المحاولة) — والوصف يُطبع كي يُعرف أيّ طريق سُلك
    حين يقع الاتصال على حساب غير المطلوب."""
    kwargs = {}
    if path:
        kwargs["path"] = path
    if portable:
        kwargs["portable"] = True
    if login and password:
        kwargs.update(login=int(login), password=password,
                      server=server or None)
        how = f"بالحساب {login}" + (f" على {server}" if server else "")
    elif path:
        how = "بالمسار وحده (بلا بيانات دخول)"
    else:
        how = "بلا مسار ولا بيانات — أيّ منصّة مفتوحة"
    try:
        ok = bool(mt5.initialize(**kwargs))
    except Exception as exc:
        return False, f"{how} — فشل: {exc}"
    if not ok:
        return False, f"{how} — فشل: {mt5.last_error()}"
    return True, how


def selected_channel_name():
    """اسم القناة المختارة كما كتبه صاحب الحساب."""
    return (_only_channel.get("name") or "").strip()


def normalize_channel_name(name):
    """توحيد المسافات وحالة الأحرف ليستقيم التطابق."""
    return " ".join((name or "").strip().split()).casefold()


def pick_selected_dialog(id2name):
    """يطابق كل قناةٍ مضبوطة بمحادثةٍ مثبتة.

    يعيد (المختارة، سبب الرفض). المختارة {معرّف المحادثة: القناة}.
    ولا "خيار افتراضي": بلا اسم محدد يُرفض التشغيل، فلا يفتح البوت
    صفقة من قناة لم تخترها. واسمٌ يطابق محادثتين يُرفض أيضاً — لا
    يُخمَّن أيّهما."""
    # قناةٌ بلا اسم في قائمتها تأخذ الاسم المضبوط عامّةً، فيبقى
    # التشغيل بقناة واحدة يُكتب باسمها وحده كما كان.
    wanted_names = [(ch.get("name") or "").strip() or selected_channel_name()
                    for ch in _channels]
    if not any(wanted_names):
        return {}, ("لم تُحدَّد قناة — شغّل بـ --channel \"اسم القناة\" "
                    "أو اضبط SIGNAL_CHANNEL_NAME في config.py")
    chosen = {}
    for ch, wanted in zip(_channels, wanted_names):
        if not wanted:
            continue
        needle = normalize_channel_name(wanted)
        matched = {cid: nm for cid, nm in id2name.items()
                   if needle in normalize_channel_name(nm)}
        if not matched:
            return {}, f"لا محادثة مثبتة يطابق اسمها «{wanted}»"
        if len(matched) > 1:
            found = "، ".join(matched.values())
            return {}, (f"«{wanted}» يطابق أكثر من محادثة ({found}) — "
                        "اكتب اسماً أدق")
        cid, real = next(iter(matched.items()))
        if cid in chosen:
            return {}, (f"«{wanted}» و«{chosen[cid]['name']}» يشيران إلى "
                        f"المحادثة نفسها ({real})")
        ch["chat_name"] = real
        chosen[cid] = ch
    return chosen, None

# بصمة النسخة: تُطبع عند الإقلاع وتُرسل على التلجرام، فلا يبقى شك
# في أي ملف يعمل فعلاً حين نتفحّص سلوكاً على الحساب الحقيقي.
BOT_VERSION = "2026-11-03.5"
# وصفٌ عام بلا أرقام: كل رقمٍ هنا يخصّ قناةً بعينها وجلسةً بعينها،
# وقد كُتبت فيه أرقامٌ قديمة فناقض ما تحته في الرسالة نفسها —
# ونصٌّ يطمئن على غير الواقع أسوأ من لا نص. الأرقام تحته لكل قناة.
BOT_FEATURES = (
    "قنوات يختارها صاحب الحساب بالاسم (--channel) ولا يُقرأ سواها · "
    "لكل قناة لوتها وعددها ووقفها وهدفها، وصفقاتها منفصلة عن الأخرى · "
    "التوصية تُفتح فوراً · وقفٌ وهدفٌ مؤقتان حتى يرسل المدرب وقفه "
    "وهدفه، ثم يحلّان محلّهما · «احجز نص» يغلق النصف وينقل الوقف "
    "للدخول · «خروج» أو «أغلق» أو «انتهت» تغلق صفقات قناتها · "
    "حدّ خسارة يومي على الحساب كله يغلق كل شيء ويوقف البوت · "
    "وما تحرّكه بيدك لا يلمسه البوت"
)

# رمز الذهب عند وسيط صاحب الحساب (كما يظهر في نافذة New Order)
DEFAULT_SYMBOL = "XAUUSD.m"
MAGIC_GOLDBOT = 20260816  # صفقات بوت توصيات الذهب (n8n) — القناة الوحيدة

# ── بوت توصيات الذهب (n8n) — القناة الوحيدة التي يعمل عليها البوت ──
# رسالة واحدة مكتملة: القرار والدخول والوقف والهدف. سعر الدخول
# المكتوب لا يُستعمل إطلاقاً — بين إرسال التوصية وتنفيذها يتحرك
# السوق درجتين أو أكثر — بل نأخذ المسافتين (خطر/ربح) ونقيسهما من
# سعر التنفيذ الفعلي، فتبقى نسبة المخاطرة كما أرادها البوت.
GOLDBOT_CHANNEL = "goldbot"
GOLDBOT_LOT = 0.03
GOLDBOT_MAX_RISK_USD = 20.0   # أبعد من ذلك: خطأ قراءة أو توصية لا يحتملها الحساب
GOLDBOT_MIN_RISK_USD = 0.5
GOLDBOT_MAX_REWARD_USD = 60.0

# أسماء معروفة للقناة. وإن اختلف الاسم فالقارئ يقرأ المحادثات المثبتة
# كلها ولا ينفّذ إلا ما كان بصيغة التوصية بالضبط.
CHANNEL_TITLE_ALLOWLIST = {
    "booooooootttttt": GOLDBOT_CHANNEL,
    "توصية الذهب": GOLDBOT_CHANNEL,
    "gold signal bot": GOLDBOT_CHANNEL,
}
ACTIVE_CHANNEL_MAGICS = {MAGIC_GOLDBOT}  # تُوسَّع في set_channels
CHANNEL_MAGICS = {GOLDBOT_CHANNEL: MAGIC_GOLDBOT}
# لا حارس يمنع توصية: بوت التوصيات لا يرسل الجديدة إلا بعد انتهاء
# السابقة، وصاحب الحساب لا يريد أن يُرفض شيء وصل منه.

# عتبة وصفية في التقارير وحدها: كم يُعدّ الربح الذي مرّت به الصفقة
# ثم أضاعته "قريباً من الربح". لا تحرّك وقفاً ولا تغلق صفقة.
REPORT_NEAR_WIN_USD = 3.0
CHANNEL_MANAGER_INTERVAL_SECONDS = 0.25
# مهلة قصيرة تكفي لتسجيل الصفقة عند فتحها قبل أن تبدأ إدارتها
CHANNEL_GROUP_FILL_GRACE_SECONDS = 2.0

# ── الصفقات اليدوية ──
# ما يفتحه صاحب الحساب بنفسه في MT5 (بلا Magic البوت). يضبط لها البوت
# وقفاً وهدفاً فور رؤيتها، وينقل الوقف إلى الدخول عند بلوغ ربح التأمين.
# وما يحرّكه بيده بعد ذلك — أو يفتح الصفقة به — لا يلمسه البوت أبداً.
MANUAL_SL_USD = 6.0
MANUAL_TP_USD = 5.0
MANUAL_BREAKEVEN_USD = 4.0

CHANNEL_POLICIES = {
    GOLDBOT_CHANNEL: {
        "position_count": 1,
        "position_lot": GOLDBOT_LOT,
    },
}


def channel_policy(channel, key):
    """قيمة القناة إن خالفت الأساس، وإلا القيمة الموحدة."""
    defaults = {
        "position_count": 1,
        "position_lot": GOLDBOT_LOT,
        # مسافتا الوقف والهدف لكل صفقة على حدة. صفر يعني أن المسافتين
        # تأتيان من التوصية نفسها (fixed_*_usd في بيانات المجموعة).
        "fixed_tp_usd": 0.0,
        "fixed_sl_usd": 0.0,
    }
    return CHANNEL_POLICIES.get(channel, {}).get(key, defaults[key])


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
















def h1_trend(symbol):
    """اتجاه فريم الساعة — يستعمله تشريح الخسارة في تقرير الإغلاق."""
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50)
        if rates is None or len(rates) < 21:
            return None
        closes = [float(rate["close"]) for rate in rates]
        fast = sum(closes[-10:]) / 10
        slow = sum(closes[-20:]) / 20
        if abs(fast - slow) < 0.5:
            return None          # لا اتجاه واضح
        return "BUY" if fast > slow else "SELL"
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
    magic=MAGIC_GOLDBOT,
    comment="MasterBot",
    fp="",
    meta=None,
    sl_usd=0.0,
    return_position=False,
):
    if not require_live_account(comment):
        return None if return_position else False
    if _channel_runtime_mode["enabled"] and not allowed_gold_symbol(symbol):
        print(
            f"[SYMBOL-GUARD] ⛔ رُفض التداول على {symbol} — المسموح "
            f"{_channel_runtime_mode.get('symbol') or DEFAULT_SYMBOL} فقط"
        )
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
    sl_usd=0.0,
    fixed_sl_price=0.0,
    initial_tp_price=0.0,
):
    """يفتح صفقات القناة المنفصلة بسرعة؛ لا يضع TP قبل تأمين المجموعة.

    العدد خمس في الأساس، ويتضاعف بعدد الوحدات المطلوبة في الميتا
    ("جدد مرتين" = عشر صفقات)."""
    if not allowed_gold_symbol(symbol):
        print(
            "[SYMBOL-GUARD] ⛔ المسموح "
            f"{_channel_runtime_mode.get('symbol') or DEFAULT_SYMBOL} فقط"
        )
        return 0
    if _channel_runtime_mode["enabled"] and not hedging_account_ready():
        print("[HEDGING-GUARD] ⛔ رُفض فتح المجموعة — الحساب ليس Hedging")
        return 0
    count = int(meta.get("group_size") or 1)
    lot = float(meta.get("lot") or GOLDBOT_LOT)
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
    keep = {ch["magic"] for ch in _channels if ch.get("keep_pending")}
    for order in orders:
        if getattr(order, "magic", None) not in ACTIVE_CHANNEL_MAGICS:
            continue
        if getattr(order, "magic", None) in keep:
            # قناةٌ تعمل على مناطق سيولة: أوامرها تنتظر ارتداداً قد
            # يأتي بعد أيام، فحذفها عند كل تشغيل يُفسد خطتها كلها
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


UNREAD_SIGNAL_COOLDOWN_SECONDS = 600
_unread_signal_notice = {}


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
    GOLDBOT_CHANNEL: ("🤖", "بوت التوصيات"),
    "manual": ("✋", "صفقة يدوية"),  # ليس قناة — لتسمية التقارير فقط
}


















def handle_goldbot_message(symbol, text, signal_key=None):
    """القناة الوحيدة: صفقة واحدة تُفتح فوراً بمسافتَي التوصية.

    الوقف على بُعد "خطر $X" من سعر التنفيذ، والهدف على بُعد "ربح $Y".
    سعر التوصية المكتوب لا يُنظر إليه إطلاقاً — السوق يتحرك بين
    إرسالها وتنفيذها. ورسالة HOLD لا تفتح شيئاً."""
    channel, magic, comment = GOLDBOT_CHANNEL, MAGIC_GOLDBOT, "GoldBot"
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
    if not 0 < reward <= GOLDBOT_MAX_REWARD_USD:
        print(f"[{name}] ⛔ مسافة هدف غير مقبولة ${reward:g} — رُفضت التوصية")
        notify_tg(
            f"⚠️ <b>رُفضت توصية {name}</b> {icon}\n\n"
            f"مسافة الهدف ${reward:g} خارج المدى المسموح "
            f"(حتى ${GOLDBOT_MAX_REWARD_USD:g})."
        )
        return
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"[{name}] ⛔ لا سعر متاح — رُفضت التوصية")
        return
    # المقارنة بسعر الشارت (bid) لا بسعر التنفيذ: القناة تكتب أرقام
    # الشارت، وفرقُ السعر (spread) كان يجعل «السعر عند 4010» يُقرأ
    # 4010.20 فلا يُعدّ بالغاً الرقم، فيُعلَّق ما كان يجب أن يُفتح.
    market = float(tick.bid)

    fingerprint = f"{direction}|{signal['stop']}|{signal['target']}"
    if duplicate_entry(channel, fingerprint, signal_key):
        print(f"[{name}] ⏭️ نفس التوصية مكررة — تجاهل")
        return
    needed = channel_policy(channel, "position_count")

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

        # القنوات المضبوطة لا غير. ما عداها لا يُقرأ ولا يُفتح منه شيء.
        all_pinned = dict(zip(pinned_ids, pinned_names))
        watched, reject = pick_selected_dialog(all_pinned)
        if reject:
            print(f"[TG-Reader] ❌ {reject}")
            print("[TG-Reader]    المحادثات المثبتة عندك:")
            for name in pinned_names:
                print(f"            • {name}")
            send_tg("❌ <b>البوت لم يعمل — القناة غير محددة</b>\n\n"
                    f"{reject}")
            return

        read_names = [ch.get("chat_name", ch["name"])
                      for ch in watched.values()]

        icon, label = CHANNEL_LABELS[GOLDBOT_CHANNEL]
        for ch in watched.values():
            print(f"[TG-Reader] 📌 {icon} {label} — "
                  f"{ch.get('chat_name', ch['name'])} · "
                  + ("صفقة لكل رقم × " if ch.get("parser") == "en"
                     else f"{vip_full(ch)}×")
                  + f"{ch['lot']:g}")
        ignored = [n for n in pinned_names if n not in read_names]
        if ignored:
            # العدد وحده لا الأسماء: صاحب الحساب يريد أن يرى قناته
            # هو، ويكفيه أن يعرف كم محادثةً استُبعدت
            print(f"[TG-Reader]    🚫 واستُبعدت {len(ignored)} "
                  f"محادثة مثبتة أخرى")

        def process(ch, text, signal_key, tag="رسالة"):
            """كل رسالة تمرّ على المترجم؛ هو وحده يقرر أهي أمر أم كلام.

            القناة البشرية لا تكتب كلمة مفتاحية ثابتة، فلا يصحّ
            ترشيحها قبل الترجمة — «بيع» أمر، و«رح نبيع» ليس."""
            now = datetime.now().strftime("%H:%M:%S")
            try:
                route_message(symbol, text, signal_key, ch)
            except Exception as e:
                print(f"\n[TG-Reader {now}] ❌ خطأ معالجة: {e}")
                print(f"   {text[:120]}")

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
    # لا يدخل None في الهوية: وسيط لا يعطي identifier يجعلها
    # {ticket, None}، فتُطابق كل صفقة أخرى identifier عندها None —
    # فيُغلق النصف المطلوب ثم تُغلق بقية المجموعة معه.
    identity = {
        value for value in (
            getattr(position, "ticket", None),
            getattr(position, "identifier", None),
        )
        if value is not None
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
            if (getattr(row, "ticket", None) is not None
                and getattr(row, "ticket", None) in identity)
            or (getattr(row, "identifier", None) is not None
                and getattr(row, "identifier", None) in identity)
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
    bot_magics = set(CHANNEL_MAGICS.values())
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




# أقصى ما نقبله بين التنفيذ وستوب التوصية حين نتأخر. أبعد من ذلك
# تكون خسارة الصفقة الواحدة أكبر مما يحتمله الحساب.
LATE_ENTRY_MAX_SL_USD = 15.0








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






def fixed_group_levels(info):
    """مسافتا الوقف والهدف الثابتتان لهذه المجموعة، أو (0, 0).

    الأولوية لما جاء في التوصية نفسها (بوت التوصيات يكتب خطره وربحه)،
    ثم لسياسة القناة إن حدّدت مسافتين ثابتتين."""
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
    """يضبط وقف وهدف كل صفقة قناة بمسافتَي توصيتها من دخولها.

    لم تعد هناك مجموعات ولا سلم أهداف: التوصية صفقة واحدة، ومسافتاها
    مكتوبتان في التوصية نفسها (خطر/ربح)، فتُقاسان من سعر التنفيذ
    الفعلي. وما يحرّكه صاحب الحساب بيده لا يُكتب فوقه أبداً."""
    if _runtime_safety["suspended"]:
        if _channel_cleanup_quarantine:
            recover_quarantined_channel_cleanup(symbol)
        if _runtime_safety["suspended"]:
            return
    if not require_demo_account("channel manager"):
        return

    positions = mt5.positions_get(symbol=symbol) or []
    groups = {}
    with _trades_lock:
        for position in positions:
            # صفقات القناة وحدها. الصفقة اليدوية لها group_id في سجلها
            # (لتقاريرها) فكانت تدخل هنا أيضاً ويديرها مديران، فيتنازعان
            # أمرَي تعديل كل ربع ثانية ما دامت مفتوحة.
            if getattr(position, "magic", None) not in ACTIVE_CHANNEL_MAGICS:
                continue
            info = _open_trades.get(position.ticket)
            if not info or not info.get("group_id"):
                continue
            groups.setdefault(info["group_id"], []).append((position, info))

    if not mt5.symbol_info_tick(symbol):
        return
    for items in groups.values():
        is_buy = items[0][0].type == mt5.POSITION_TYPE_BUY
        manage_fixed_level_group(symbol, items, is_buy)


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
        f"{info.get('lot', GOLDBOT_LOT)} — {symbol}",
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
    """هل انتهت التوصية فعلاً؟ لا صفقة مفتوحة منها."""
    with _trades_lock:
        return not any(
            info.get("group_id") == group_id for info in _open_trades.values()
        )


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

    lines.append(f"النتيجة: ${net:.2f}")
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


def manager_thread(symbol):
    """إدارة سريعة لصفقات القناة والصفقات اليدوية."""
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
            vip_chase(symbol)
        except Exception as e:
            print(f"[VIP-CHASE] ❌ {e}")
        try:
            # التأمين التلقائي قبل الصفقات اليدوية: صفقات القناة أولى
            # بالحماية، ولا ينتظر رسالةً قد تتأخر أو لا تصل
            vip_auto_breakeven(symbol)
        except Exception as e:
            print(f"[VIP-BE] ❌ {e}")
        try:
            manage_manual_positions(symbol)
        except Exception as e:
            print(f"[Manual] ❌ {e}")
        try:
            report_closed_channel_trades(symbol)
        except Exception as e:
            print(f"[Report] ❌ {e}")
        time.sleep(CHANNEL_MANAGER_INTERVAL_SECONDS)








# ═════════════════════════════════════════════
#  الجزء ٧ — الحلقة الرئيسية
# ═════════════════════════════════════════════




# ═════════════════════════════════════════════
#  الجزء ٦.٥ — التقرير اليومي على تيليغرام
# ═════════════════════════════════════════════
MAGIC_NAMES = {MAGIC_GOLDBOT: "🤖 بوت التوصيات"}


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
            f"لا توجد صفقات مغلقة اليوم."
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
        f"📋 <b>حسب النظام:</b>\n" + "\n".join(lines)
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
        dialogs = []
        async for dialog in client.iter_dialogs():
            if dialog.pinned:
                name = dialog.name or ""
                pinned.append(name)
                dialogs.append((dialog.id, name))
        if not pinned:
            return False, "لا توجد محادثات مثبتة في تيليغرام", pinned

        # القناة الواحدة: الفحص يفشل صراحةً إن لم تُحدَّد أو لم تُوجد،
        # فلا يُقال "جاهز" والبوت لا يعرف من أين يقرأ.
        all_pinned = dict(dialogs)
        chosen_map, reject = pick_selected_dialog(all_pinned)
        if reject:
            detail = reject + "\n            المثبتة: " + "، ".join(pinned)
            return False, detail, pinned
        dialogs = [(cid, name) for cid, name in dialogs if cid in chosen_map]

        # آخر توصية وصلت من كل محادثة — الدليل القاطع أن الربط سليم
        # وأن البوت يرى ما ترسله القناة فعلاً
        lines = []
        for cid, name in dialogs:
            mark = "✅ القناة المختارة"
            last = None
            try:
                async for msg in client.iter_messages(cid, limit=20):
                    if msg.text and "القرار" in msg.text:
                        minutes = int(
                            (datetime.now(timezone.utc) - msg.date).total_seconds()
                            // 60
                        )
                        decision = (parse_gold_bot_signal(msg.text) or {}).get(
                            "decision", "صيغة غير مقروءة"
                        )
                        last = f"آخر توصية {decision} قبل {minutes} دقيقة"
                        break
            except Exception as exc:
                last = f"تعذّرت قراءة الرسائل ({exc})"
            lines.append(f"{mark} {name}" + (f" — {last}" if last else " — بلا توصيات"))
        read = [name for _, name in dialogs]
        only_name = "، ".join(read)
        ignored = [n for n in pinned if n not in read]
        # ما يُعاد هو المقروء فعلاً. لو أعدنا كل المثبتة لقالت رسالة
        # البدء إنها تقرأ خمس قنوات وهي تقرأ واحدة — وذلك كذب مُطَمئِن.
        pinned = read or pinned
        detail = (
            f"القنوات: {only_name}"
            + (f" · لا تُقرأ: {len(ignored)} محادثة أخرى" if ignored else "")
            + "\n            " + "\n            ".join(lines)
        )
        return True, detail, pinned
    except Exception as exc:
        return False, f"خطأ Telethon: {exc}", []
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def channels_self_test(symbol, expected_login=None, mt5_path=None,
                       mt5_server="", mt5_portable=False):
    """فحص آمن لمسار القنوات فقط، دون إرسال أي أمر تداول."""
    checks = []

    def add(ok, name, detail=""):
        checks.append((bool(ok), name, detail))
        print(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""))

    print(f"\n{'═' * 55}")
    print("  🩺 فحص القناة — بدون تداول")
    print(f"{'═' * 55}\n")

    live_price = None
    mt5_ok, how = mt5_start(mt5_path, expected_login or 0, mt5_server,
                            MT5_PASSWORD, mt5_portable)
    add(mt5_ok, "اتصال MT5", how if mt5_ok else f"لم يتصل — {how}")
    if mt5_ok:
        try:
            _channel_runtime_mode["enabled"] = True
            _channel_runtime_mode["symbol"] = symbol
            account = mt5.account_info()
            connected_login = getattr(account, "login", None)
            # نسختان من MT5 مفتوحتان؟ الفحص يقول على أيّهما وقع الاتصال
            if expected_login:
                _channel_runtime_mode["account_login"] = expected_login
                add(connected_login == expected_login,
                    f"الحساب المطلوب {expected_login}",
                    f"الاتصال وقع على {connected_login}"
                    + ("" if connected_login == expected_login
                       else " — أغلق نسخة MT5 الأخرى أو حدّد --mt5-path"))
            else:
                _channel_runtime_mode["account_login"] = connected_login
                add(True, f"الحساب {connected_login}",
                    "بلا --account: البوت يعمل على ما صادفه الاتصال")
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
            if selected:
                # اللوت يُفحص هنا لا عند أول توصية: الوسيط الجديد قد
                # يرفض 0.01، فيُعرف ذلك قبل السوق لا في أثنائه
                for ch in _channels:
                    lot_ok, lot_detail = vip_lot_ok(symbol, ch)
                    add(lot_ok,
                        f"اللوت {ch['lot']:g}"
                        + (f" ({ch['name']})" if len(_channels) > 1 else ""),
                        lot_detail)
            tick = mt5.symbol_info_tick(symbol) if selected else None
            add(bool(tick), "السعر المباشر", f"{tick.bid:.2f}" if tick else "غير متاح")
            if tick:
                live_price = float(tick.bid)
                balance = getattr(account, "balance", 0.0) or 0.0
                # بأرقام التشغيل نفسها لا بثوابت قديمة: الرقم الذي
                # يقرؤه صاحب الحساب هنا هو ما سيخسره فعلاً
                per = sum(
                    (vip_points_to_money(symbol, ch["temp_sl"], ch=ch) or 0.0)
                    * vip_full(ch) for ch in _channels) or None
                worst = per or 0.0
                share = (worst / balance * 100) if balance else 0.0
                detail = (
                    f"الرصيد ${balance:.2f} | "
                    + "، ".join(
                        f"{vip_full(ch)}×{ch['lot']:g} بوقف "
                        f"{ch['temp_sl']:g}" for ch in _channels)
                    + f" = ${worst:.0f} "
                    f"({share:.0f}% من الحساب)"
                    if per else "تعذّر حساب المخاطرة من بيانات الوسيط"
                )
                add(
                    bool(per) and balance > worst * 3,
                    "الرصيد يحتمل ثلاث توصيات خاسرة",
                    detail,
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

    mapping_ok = channel_of("booooooootttttt") == GOLDBOT_CHANNEL
    add(mapping_ok, "تمييز اسم القناة", "booooooootttttt")

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

    # ── ماذا كان سيفعل لو وصلت هذه التوصية الآن؟ (بلا أي أمر) ──
    if live_price and parsed_gold:
        risk, reward = parsed_gold["risk"], parsed_gold["reward"]
        print(
            f"ℹ️  لو وصلت التوصية النموذجية الآن والسعر {live_price:.2f}: "
            f"بيع {GOLDBOT_LOT} | الوقف {live_price + risk:.2f} "
            f"(${risk:g}) | الهدف {live_price - reward:.2f} (${reward:g}) "
            "— سعر التوصية المكتوب لا يُستعمل"
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
    print("\n[CHANNELS] ✅ يراقب قناة التوصيات فقط. اضغط Ctrl+C للإيقاف.\n")
    symbol = _channel_runtime_mode.get("symbol") or DEFAULT_SYMBOL
    while True:
        try:
            # حدّ الخسارة أولاً: يُغلق ويتوقف قبل أي شيء آخر
            if vip_loss_guard(symbol):
                print("[CHANNELS] ⛔ توقف البوت — شغّله يدوياً بعد المراجعة")
                return
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
                    print(
                        f"[CHANNELS {datetime.now():%H:%M:%S}] حيّ | "
                        f"تيليغرام: فوري · الإدارة: "
                        f"{CHANNEL_MANAGER_INTERVAL_SECONDS * 1000:.0f}ms"
                        f" | مفتوح: {open_count}"
                    )
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n[⛔] إيقاف بوت القنوات.")
            break
        except Exception as exc:
            print(f"[CHANNELS] ❌ {exc}")
            time.sleep(30)



# ═════════════════════════════════════════════
# 🗣️ القناة البشرية: من الرسالة إلى الصفقة
# ═════════════════════════════════════════════
# القناة تكتب بالعامية وتفرّق التوصية على رسائل. vip_signals يترجم
# كل رسالة إلى فعل واحد، وهذا القسم ينفّذه على MT5.

VIP_POSITIONS_FULL = 4     # «بيع» عادية
VIP_POSITIONS_HALF = 2     # «شراء بلوت بسيط»
VIP_LOT = 0.01
VIP_TEMP_SL_USD = 5.0      # وقف مؤقت حتى يصل ستوب القناة
VIP_AUTO_BE_USD = 5.0      # تأمين تلقائي إن لم تأمر القناة
VIP_MAX_LOSS_USD = 150.0   # حدّ الخسارة اليومي — يصفّر كل يوم

def new_channel(name="", magic=MAGIC_GOLDBOT):
    """قناة واحدة: إعداداتها وحالتها معاً.

    لكل قناة رقم سحرٍ (magic) خاص توسم به صفقاتها في MT5، فصفقات
    الواحدة لا تُرى من الأخرى أصلاً. وبه يتحقق الفصل الذي طلبه صاحب
    الحساب: «خروج» من قناةٍ لا يغلق صفقة قناةٍ أخرى، ولكلٍّ لوتها."""
    return {
        "name": name,
        "magic": magic,
        "direction": None,      # اتجاه آخر مجموعة — تحتاجه «جدد»
        "no_reopen": False,     # «انتهت لا تفعل»
        "stop_was_hit": False,  # تحتاجه «لو ضربك تشتري»
        "lot": VIP_LOT,         # حجم الصفقة الواحدة — يضبطه --lot
        "one_target": False,    # هدف واحد للكل — يضبطه --one-target
        "positions": VIP_POSITIONS_FULL,   # عدد الصفقات — --positions
        "temp_sl": VIP_TEMP_SL_USD,        # الوقف المؤقت؛ صفرٌ = بلا وقف
        "fixed_tp": 0.0,        # هدف ثابت بالنقاط؛ صفرٌ = هدف القناة
        "parser": "ar",         # لهجة القناة: ar = VIP AN، en = VEY GOLD
        "keep_pending": False,  # تُبقي أوامرها المعلّقة عبر التشغيلات
        "default_sl": 0.0,      # وقفٌ افتراضي بالدرجات خلف أبعد رقم
        "pending_direction": None,  # اتجاهٌ أُعلن وتُنتظر أرقامه
        "quoted": [],           # أسعار دخول المدرّب لهذه التوصية
        "temp_tp": 0.0,         # هدف مؤقت بالدرجات حتى يرسل المدرّب هدفه
        "sl_pad": 0.0,          # درجاتٌ خلف وقف المدرّب — مجالٌ زائد
        "auto_be": VIP_AUTO_BE_USD,  # تأمين تلقائي؛ صفرٌ = لا يتحرك
        "chase": True,          # ملاحقة سعر المدرّب حين يتأخر التنفيذ
        "chasing": None,        # خطة الملاحقة الجارية
    }


_channels = [new_channel()]
# القناة الأولى. كل ما كُتب حين كانت القناة واحدة يبقى عاملاً عليها.
_vip_state = _channels[0]

# حارس الخسارة على **الحساب** لا على القناة: المال واحد مهما تعددت
# القنوات، فبلوغ الحد يوقفها جميعاً.
_guard_state = {
    "start_equity": None,   # حقوق الملكية عند أول فحص في اليوم
    "max_loss": VIP_MAX_LOSS_USD,
    "halted": False,
    "day": None,            # يوم العدّ — يصفّر الحدّ عند تغيّره
}


def set_channels(channels):
    """يثبّت قائمة القنوات ويجعل الأولى هي _vip_state.

    ويضمّ أرقام سحرها إلى الحُرّاس: ما لم تُضَمّ لعُدّت صفقات القناة
    الثانية «صفقةً يدوية» فتُدار بسياسة الصفقات اليدوية، أو لحُذفت
    أوامرها المعلّقة عند التنظيف."""
    global _channels, _vip_state
    _channels = list(channels) or [new_channel()]
    _vip_state = _channels[0]
    for ch in _channels:
        ACTIVE_CHANNEL_MAGICS.add(ch["magic"])
        MAGIC_NAMES.setdefault(
            ch["magic"],
            f"🤖 {ch['name']}" if ch.get("name") else "🤖 بوت التوصيات")
    return _channels


def parse_channel_spec(spec, index, defaults):
    """«VIP AN | lot=0.05 | pos=1 | sl=5 | tp=5 | one» → قناة.

    الاسم أولاً، ثم ما شئت من الإعدادات مفصولةً بـ |. وما لم يُذكر
    يأخذ قيمة الإعداد العام، فقناةٌ واحدة تبقى تُكتب باسمها وحده.
    رقم السحر من الترتيب: لكل قناة رقمها الثابت ما دام ترتيبها ثابتاً."""
    parts = [piece.strip() for piece in str(spec or "").split("|")]
    ch = new_channel(parts[0], MAGIC_GOLDBOT + index)
    ch.update({k: v for k, v in defaults.items() if k in ch})
    for piece in parts[1:]:
        if not piece:
            continue
        key, _, value = piece.partition("=")
        key = key.strip().lower().replace("-", "_")
        value = value.strip()
        try:
            if key == "lot":
                ch["lot"] = float(value)
            elif key in ("pos", "positions"):
                ch["positions"] = max(1, int(float(value)))
            elif key in ("sl", "temp_sl"):
                ch["temp_sl"] = max(0.0, float(value))
            elif key in ("tp", "fixed_tp"):
                ch["fixed_tp"] = max(0.0, float(value))
            elif key in ("one", "one_target"):
                ch["one_target"] = value.lower() not in ("0", "no", "false")
            elif key in ("two", "two_targets"):
                ch["one_target"] = False
            elif key in ("parser", "lang"):
                ch["parser"] = "en" if value.lower().startswith("e") else "ar"
                if ch["parser"] == "en":
                    # قناة مناطق السيولة: أوامرها تنتظر أياماً
                    ch["keep_pending"] = True
                    ch["default_sl"] = ch["default_sl"] or 10.0
                    ch["fixed_tp"] = ch["fixed_tp"] or 10.0
                    # صفقة عند كل رقم، والقناة ترسل رقمين دائماً.
                    # لولا ضبطه لبقي أربعاً فقال العرضُ وحسابُ
                    # المخاطرة ضِعف ما يُفتح فعلاً.
                    ch["positions"] = 2
            elif key in ("ttp", "temp_tp"):
                ch["temp_tp"] = max(0.0, float(value))
            elif key in ("chase",):
                ch["chase"] = value.lower() not in ("0", "no", "false")
            elif key in ("abe", "auto_be"):
                ch["auto_be"] = max(0.0, float(value))
            elif key in ("pad", "sl_pad"):
                ch["sl_pad"] = max(0.0, float(value))
            elif key in ("dsl", "default_sl"):
                ch["default_sl"] = max(0.0, float(value))
            elif key in ("keep", "keep_pending"):
                ch["keep_pending"] = value.lower() not in ("0", "no", "false")
            else:
                print(f"[CHANNELS] ⚠️ إعداد مجهول «{key}» في «{spec}»")
        except ValueError:
            print(f"[CHANNELS] ⚠️ قيمة غير مفهومة «{piece}» في «{spec}»")
    return ch


def build_channels(specs, defaults):
    """قائمة القنوات من وسائط التشغيل."""
    specs = [sp for sp in (specs or []) if str(sp or "").strip()]
    if not specs:
        specs = [SIGNAL_CHANNEL_NAME] if SIGNAL_CHANNEL_NAME else [""]
    return [parse_channel_spec(sp, i, defaults)
            for i, sp in enumerate(specs)]


def channel_by_magic(magic):
    for ch in _channels:
        if ch["magic"] == magic:
            return ch
    return _vip_state


def vip_points_to_money(symbol, distance, lot=None, ch=None):
    """يحوّل مسافة السعر إلى مبلغ بالدولار عند لوت معيّن.

    «الوقف 5» مسافةُ سعرٍ لا مبلغ: تساوي $5 عند لوت 0.01 و$50 عند
    0.10. فكتابة «وقف $5» في الرسائل صحيحةٌ عند لوت واحد وكاذبة عند
    غيره — وصاحب الحساب يقرؤها فيظنّ مخاطرته عُشر ما هي.

    المبلغ من بيانات الوسيط (قيمة التك وحجمها) لا من ثابت مكتوب:
    حجم العقد يختلف بين وسيط وآخر. ويعيد None إن تعذّر الحساب، فتذكر
    الرسالة المسافة وحدها بدل رقم مخترع."""
    lot = float((ch or _vip_state)["lot"] if lot is None else lot)
    info = mt5.symbol_info(symbol)
    if not info:
        return None
    tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
    tick_value = float(getattr(info, "trade_tick_value", 0.0) or 0.0)
    if tick_size <= 0 or tick_value <= 0 or lot <= 0:
        return None
    return (float(distance) / tick_size) * tick_value * lot


def vip_risk_text(symbol, distance, group=False, ch=None):
    """«5 نقاط ≈ $50 للصفقة» — أو المسافة وحدها إن تعذّر التحويل."""
    ch = ch or _vip_state
    money = vip_points_to_money(symbol, distance, ch=ch)
    if money is None:
        return f"{float(distance):g} نقاط"
    if not group:
        return f"{float(distance):g} نقاط ≈ ${money:.0f} للصفقة"
    return (f"{float(distance):g} نقاط ≈ ${money:.0f} للصفقة · "
            f"${money * vip_full(ch):.0f} للمجموعة ({vip_full(ch)})")


def vip_lot_ok(symbol, ch=None):
    """هل يقبل الوسيط هذا اللوت؟

    وسيطان مختلفان ليسا سواءً: قد يكون أدنى لوت للذهب عند أحدهما
    0.01 وعند الآخر 0.1، وقد تختلف الخطوة. بلا هذا الفحص يبدأ البوت
    سليماً في الظاهر ثم يفشل كل أمر بصمت عند أول توصية.

    يعيد (صالح، السبب)."""
    lot = float((ch or _vip_state).get("lot") or 0.0)
    if lot <= 0:
        return False, "اللوت يجب أن يكون أكبر من صفر"
    info = mt5.symbol_info(symbol)
    if not info:
        return False, f"تعذّرت قراءة بيانات الرمز {symbol}"
    low = float(getattr(info, "volume_min", 0.0) or 0.0)
    high = float(getattr(info, "volume_max", 0.0) or 0.0)
    step = float(getattr(info, "volume_step", 0.0) or 0.0)
    if low and lot < low:
        return False, (f"أدنى لوت عند وسيطك لـ{symbol} هو {low:g} "
                       f"وأنت طلبت {lot:g}")
    if high and lot > high:
        return False, (f"أعلى لوت عند وسيطك لـ{symbol} هو {high:g} "
                       f"وأنت طلبت {lot:g}")
    if step > 0:
        # المقارنة بالأعداد الصحيحة: 0.3/0.1 تساوي 2.9999… بالعشرية
        units = round(lot / step)
        if abs(units * step - lot) > 1e-9:
            return False, (f"خطوة اللوت عند وسيطك {step:g}، "
                           f"و{lot:g} ليست من مضاعفاتها")
    return True, (f"اللوت {lot:g} مقبول (الأدنى {low:g} · "
                  f"الخطوة {step:g})")


def vip_today():
    """تاريخ اليوم بتوقيت الجهاز — عليه يُقاس حدّ الخسارة."""
    return datetime.now().strftime("%Y-%m-%d")


def vip_loss_guard(symbol):
    """حدّ خسارة **يومي**: يغلق كل شيء ويوقف البوت عند بلوغه.

    يصفّر مع كل يوم جديد ولا يُجمَع: خسارة الأمس لا تقيّد اليوم.
    والمقياس حقوق الملكية لا الرصيد — الخسارة العائمة خسارة ولو لم
    تُغلق الصفقة بعد، ولو انتظرنا الرصيد لمرّت كاملةً قبل أن ينتبه
    الحارس."""
    limit = float(_guard_state.get("max_loss") or 0.0)
    if limit <= 0:
        return False
    info = mt5.account_info()
    if not info:
        return False
    equity = float(getattr(info, "equity", 0.0) or 0.0)

    # يوم جديد: نقطة الأساس تُعاد إلى حقوق الملكية الآن
    today = vip_today()
    if _guard_state.get("day") != today:
        _guard_state["day"] = today
        _guard_state["start_equity"] = equity
        print(f"[LOSS-GUARD] 🗓️ يوم جديد {today} — "
              f"العدّ يبدأ من ${equity:.2f}")
        return False

    start = _guard_state.get("start_equity")
    if start is None:
        _guard_state["start_equity"] = equity
        return False
    drop = float(start) - equity
    if drop < limit:
        return False

    closed = sum(vip_close_all(symbol, f"حدّ الخسارة ${limit:g}", ch)
                 for ch in _channels)
    _guard_state["halted"] = True
    for ch in _channels:
        ch["no_reopen"] = True
    print(f"[LOSS-GUARD] ⛔ خسارة اليوم ${drop:.2f} بلغت الحد "
          f"${limit:g} — توقف")
    send_tg(
        "⛔ <b>توقف البوت — بلغ حدّ الخسارة اليومي</b>\n\n"
        f"خسارة اليوم {vip_today()}:\n"
        f"من ${float(start):.2f} إلى ${equity:.2f} = <b>−${drop:.2f}</b>\n"
        f"الحد اليومي: ${limit:g}\n\n"
        f"أُغلقت {closed} صفقة، ولن يفتح شيئاً.\n"
        "لن يعمل حتى تشغّله أنت من جديد."
    )
    return True


def vip_positions(symbol, ch=None):
    """صفقات **هذه القناة** وحدها، الأقدم أولاً فالقسمة ثابتة.

    التمييز برقم السحر: صفقات قناةٍ لا تظهر لقناةٍ أخرى، فلا يغلق
    «خروج» إحداهما ما فتحته الأخرى."""
    ch = ch or _vip_state
    rows = mt5.positions_get(symbol=symbol) or []
    mine = [p for p in rows
            if getattr(p, "magic", None) == ch["magic"]]
    return sorted(mine, key=lambda p: getattr(p, "ticket", 0))


def vip_full(ch=None):
    """عدد صفقات التوصية الواحدة."""
    ch = ch or _vip_state
    return max(1, int(ch.get("positions") or VIP_POSITIONS_FULL))


def vip_half_count(ch=None):
    """نصف المجموعة — وصفرٌ حين تكون صفقةً واحدة لا تُنصَّف."""
    return vip_full(ch) // 2


def _vip_half(rows):
    """كم صفقةً يُغلق عند «احجز نص».

    مجموعةٌ من صفقة واحدة لا تُنصَّف: إغلاقها يُنهي التوصية كلها،
    و«احجز نص» أمرُ تثبيتٍ لا أمرُ خروج. فتبقى، وينتقل وقفها للدخول."""
    if not rows:
        return 0
    if len(rows) <= 1:
        return 0
    return max(1, len(rows) // 2)


def vip_open(symbol, direction, size="FULL", ch=None):
    """يفتح المجموعة فوراً بسعر السوق ووقف مؤقت."""
    ch = ch or _vip_state
    if _guard_state.get("halted"):
        print("[VIP] ⛔ البوت موقوف عند حدّ الخسارة — لا يفتح شيئاً")
        journal("رفض", ch.get("name", ""), "OPEN",
                "البوت موقوف عند حدّ الخسارة")
        return 0
    if ch["no_reopen"]:
        print("[VIP] ⛔ «انتهت لا تفعل» — لا يفتح حتى توصية جديدة")
        journal("رفض", ch.get("name", ""), "OPEN",
                "«انتهت لا تفعل» سارية")
        return 0
    count = (max(1, vip_half_count(ch)) if size == "HALF" else vip_full(ch))
    meta = channel_group_meta(
        GOLDBOT_CHANNEL, direction,
        signal_key=f"vip:{time.time_ns()}",
        fixed_sl_usd=ch["temp_sl"],
    )
    meta["group_size"] = count
    meta["lot"] = ch["lot"]
    opened = open_channel_batch(
        symbol, direction, ch["magic"], "VIP", meta,
        sl_usd=ch["temp_sl"],
    )
    if opened:
        ch["direction"] = direction
        ch["stop_was_hit"] = False
        vip_fixed_target(symbol, ch)
        vip_temp_target(symbol, ch)
    return opened


def vip_arm_chase(symbol, ch, coach_price, direction):
    """يُسلّح ملاحقة سعر المدرّب حين يدخل البوت أسوأ منه.

    المدرّب يشتري من 3903 والبوت ينفّذ عند 3905: درجتان ضائعتان في
    كل صفقة. فإن عاد السعر إلى 3903 فُتحت مجموعةٌ هناك، وإن عاد بعدها
    إلى 3905 أُغلقت القديمة بصفر — فيبقى الدخول عند سعر المدرّب."""
    if not ch.get("chase") or not coach_price:
        return
    rows = vip_positions(symbol, ch)
    if not rows:
        return
    entry = round(float(rows[0].price_open), 2)
    coach_price = round(float(coach_price), 2)
    worse = (entry > coach_price if direction == "BUY"
             else entry < coach_price)
    if not worse:
        ch["chasing"] = None
        return
    ch["chasing"] = {
        "price": coach_price, "direction": direction, "entry": entry,
        "old": [int(getattr(p, "ticket", 0)) for p in rows],
        "opened": False,
    }
    print(f"[VIP] 🎯 ملاحقة: دخول البوت {entry:g} ودخول المدرّب "
          f"{coach_price:g} — ننتظر عودته")
    journal("ملاحقة", ch.get("name", ""),
            f"دخول البوت {entry:g} · المدرّب {coach_price:g}",
            "تُفتح مجموعة عند سعر المدرّب إن عاد إليه")


def vip_chase(symbol):
    """خطوتا الملاحقة: الفتح عند سعر المدرّب، ثم إغلاق القديم بصفر."""
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return
    price = float(tick.bid)
    for ch in _channels:
        plan = ch.get("chasing")
        if not plan:
            continue
        is_buy = plan["direction"] == "BUY"
        rows = vip_positions(symbol, ch)
        if not rows:
            ch["chasing"] = None      # أُغلقت المجموعة — لا ملاحقة
            continue

        if not plan["opened"]:
            # بلغ السعرُ سعرَ المدرّب؟ (أو تجاوزه إلى الأفضل)
            reached = price <= plan["price"] if is_buy else \
                price >= plan["price"]
            if not reached:
                continue
            sl = float(getattr(rows[0], "sl", 0.0) or 0.0)
            tp = float(getattr(rows[0], "tp", 0.0) or 0.0)
            opened = vip_open(symbol, plan["direction"], "FULL", ch)
            if not opened:
                ch["chasing"] = None
                continue
            # المجموعة الجديدة تأخذ وقف القديمة وهدفها: أمرُ المدرّب
            # واحدٌ لهما، والجديدة أولى به لأنها عند سعره
            fresh = [p for p in vip_positions(symbol, ch)
                     if int(getattr(p, "ticket", 0)) not in plan["old"]]
            for position in fresh:
                modify_channel_position(symbol, position, sl, tp)
            plan["opened"] = True
            print(f"[VIP] 🎯 بلغ السعر {plan['price']:g} — فُتحت "
                  f"{opened} عند سعر المدرّب")
            journal("ملاحقة", ch.get("name", ""),
                    f"فُتحت {opened} عند {plan['price']:g}",
                    f"تُغلق القديمة بصفر عند عودة السعر "
                    f"إلى {plan['entry']:g}")
            notify_tg(f"🎯 <b>ملاحقة سعر المدرّب</b>\n\n"
                      f"بلغ السعر {plan['price']:g} — فُتحت {opened} "
                      f"صفقة هناك\n"
                      f"وتُغلق القديمة بصفر عند عودته "
                      f"إلى {plan['entry']:g}")
            continue

        # عاد السعر إلى دخول المجموعة القديمة؟ تُغلق بصفر
        back = price >= plan["entry"] if is_buy else price <= plan["entry"]
        if not back:
            continue
        closed = 0
        for position in rows:
            if int(getattr(position, "ticket", 0)) in plan["old"]:
                if close_channel_position(symbol, position):
                    closed += 1
        ch["chasing"] = None
        if closed:
            print(f"[VIP] 🎯 عاد السعر إلى {plan['entry']:g} — "
                  f"أُغلقت {closed} بصفر")
            journal("ملاحقة", ch.get("name", ""),
                    f"أُغلقت {closed} بصفر عند {plan['entry']:g}",
                    "بقي الدخول عند سعر المدرّب وحده")
            notify_tg(f"🎯 <b>اكتملت الملاحقة</b>\n\n"
                      f"عاد السعر إلى {plan['entry']:g} — أُغلقت "
                      f"{closed} صفقة بصفر\n"
                      f"وبقي دخولك عند سعر المدرّب "
                      f"{plan['price']:g}")


def vip_temp_target(symbol, ch=None):
    """هدف مؤقت من دخول كل صفقة حتى يرسل المدرّب هدفه.

    لا يُكتب فوق هدفٍ موضوع: الهدف الثابت أو هدف المدرّب أولى منه،
    وهذا بديلٌ عن لا شيء لا بديلٌ عنهما."""
    ch = ch or _vip_state
    points = float(ch.get("temp_tp") or 0.0)
    if points <= 0:
        return 0
    done = 0
    for position in vip_positions(symbol, ch):
        if float(getattr(position, "tp", 0.0) or 0.0):
            continue
        sign = 1 if position.type == mt5.POSITION_TYPE_BUY else -1
        target = round(float(position.price_open) + sign * points, 2)
        if modify_channel_position(
                symbol, position,
                float(getattr(position, "sl", 0.0) or 0.0), target):
            done += 1
    if done:
        print(f"[VIP] 🎯 هدف مؤقت +{points:g} درجات على {done} صفقة")
    return done


def vip_fixed_target(symbol, ch=None):
    """هدف ثابت على بُعد نقاطٍ معلومة من **دخول كل صفقة**.

    لا من سعرٍ واحد للمجموعة: الصفقات تُنفَّذ بأسعار متفاوتة قليلاً،
    فهدفٌ واحد يعطي بعضها أقلّ من المطلوب وبعضها أكثر.
    وحين يُضبط هذا الهدف تُتجاهل أهداف القناة كلها."""
    ch = ch or _vip_state
    points = float(ch.get("fixed_tp") or 0.0)
    if points <= 0:
        return 0
    done = 0
    for position in vip_positions(symbol, ch):
        entry = float(position.price_open)
        sign = 1 if position.type == mt5.POSITION_TYPE_BUY else -1
        target = round(entry + sign * points, 2)
        if modify_channel_position(
                symbol, position,
                float(getattr(position, "sl", 0.0) or 0.0), target):
            done += 1
    if done:
        print(f"[VIP] 🎯 هدف ثابت +{points:g} نقاط على {done} صفقة")
    return done


def padded_stop(ch, direction, price):
    """وقف المدرّب مزاحاً بعيداً بمقدار sl_pad.

    البوت يدخل متأخراً بلحظة، فوقفٌ عند رقم المدرّب تماماً يُضرب
    قبل وقفه. والدرجة الزائدة هي الفرق بين الخروج وحدك والبقاء معه."""
    pad = float((ch or {}).get("sl_pad") or 0.0)
    price = float(price)
    if pad <= 0 or not direction:
        return round(price, 2)
    return round(price - pad if direction == "BUY" else price + pad, 2)


def vip_set_stop(symbol, price, ch=None, direction=None):
    """ستوب القناة يحلّ محل المؤقت على كل الصفقات."""
    rows = vip_positions(symbol, ch)
    if direction is None and rows:
        direction = ("BUY" if rows[0].type == mt5.POSITION_TYPE_BUY
                     else "SELL")
    at = padded_stop(ch, direction, price)
    done = 0
    for position in rows:
        if modify_channel_position(symbol, position, at,
                                   float(getattr(position, "tp", 0.0) or 0.0)):
            done += 1
    return done


def vip_set_target(symbol, price, which, ch=None):
    """الهدف الأول لنصف المجموعة، والثاني للنصف الآخر.

    وفي وضع «هدف واحد» (--one-target) الهدف الأول يشمل كل الصفقات،
    والثاني يُتجاهل: المجموعة كلها تُغلق عند أول هدف أو عند «خروج»."""
    ch = ch or _vip_state
    rows = vip_positions(symbol, ch)
    if not rows:
        return 0
    if ch.get("one_target"):
        if which == 2:
            print("[VIP] ⏭️ وضع الهدف الواحد — الهدف الثاني يُتجاهل")
            return 0
        chosen = rows
    else:
        half = _vip_half(rows)
        chosen = rows[:half] if which == 1 else rows[half:]
    done = 0
    for position in chosen:
        if modify_channel_position(symbol, position,
                                   float(getattr(position, "sl", 0.0) or 0.0),
                                   round(float(price), 2)):
            done += 1
    return done


def coach_entry(ch, direction):
    """سعر دخول المدرّب لهذه التوصية، أو None إن لم يرسله.

    حين يرسل رقمين يُؤخذ الأوسع مدى: الأعلى في البيع والأدنى في
    الشراء. فالبوت دخل متأخراً بدرجة، والغرض أن يبقى وقفه حيث وضعه
    المدرّب لا أضيق منه — وضيقُ درجةٍ واحدة هو ما كان يُخرجه من
    صفقةٍ تمضي بعدها إلى الهدف."""
    quoted = [float(p) for p in (ch or {}).get("quoted") or []]
    if not quoted:
        return None
    return max(quoted) if direction == "SELL" else min(quoted)


def vip_breakeven(symbol, rows=None, ch=None, price=None):
    """الوقف إلى سعر الدخول — لكل صفقة دخولها هي، أو سعرٌ واحد
    يُمرَّر لها جميعاً حين يكون دخول المدرّب معلوماً."""
    done = 0
    for position in (rows if rows is not None
                     else vip_positions(symbol, ch)):
        entry = (round(float(price), 2) if price
                 else round(float(position.price_open), 2))
        if modify_channel_position(symbol, position, entry,
                                   float(getattr(position, "tp", 0.0) or 0.0)):
            done += 1
    return done


def vip_close_all(symbol, reason="", ch=None):
    closed = 0
    for position in vip_positions(symbol, ch):
        if close_channel_position(symbol, position):
            closed += 1
    if closed:
        print(f"[VIP] 🔻 أُغلقت {closed} صفقة — {reason}")
    return closed


def vip_close_half(symbol, ch=None):
    """يغلق النصف، ووقف الباقي ينتقل إلى الدخول."""
    rows = vip_positions(symbol, ch)
    if not rows:
        return 0, 0
    half = _vip_half(rows)
    closed = sum(1 for p in rows[:half]
                 if close_channel_position(symbol, p))
    secured = vip_breakeven(symbol, rows[half:], ch)
    return closed, secured


def vip_reduce(symbol, ch=None):
    """«خفف لوتك» بعد الفتح: يُنزل العدد إلى النصف المطلوب."""
    rows = vip_positions(symbol, ch)
    extra = len(rows) - max(1, vip_half_count(ch))
    if extra <= 0:
        return 0
    return sum(1 for p in rows[:extra] if close_channel_position(symbol, p))


def vip_auto_breakeven(symbol):
    """تأمين تلقائي عند +$5 إن لم تأمر القناة.

    لا ينتظر رسالة: إن تأخرت أو انقطع الاتصال تبقى الصفقة محمية."""
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return 0
    done = 0
    # لكل قناة عتبتها: قناةٌ أطفأه صاحب الحساب فيها لا يتحرك وقفها
    # إلا بأمر المدرّب — لأن تأميناً عند دخول البوت، وهو أسوأ بدرجة
    # من دخول المدرّب، كان يُخرجه وحده من صفقةٍ تمضي إلى الهدف.
    rows = [(ch, p) for ch in _channels
            if float(ch.get("auto_be") or 0.0) > 0
            for p in vip_positions(symbol, ch)]
    for ch, position in rows:
        is_buy = position.type == mt5.POSITION_TYPE_BUY
        entry = float(position.price_open)
        market = float(tick.bid if is_buy else tick.ask)
        gain = (market - entry) if is_buy else (entry - market)
        if gain < float(ch["auto_be"]):
            continue
        current = float(getattr(position, "sl", 0.0) or 0.0)
        # رقم المدرّب أولى من دخول البوت متى عُرف
        target = round(coach_entry(ch, ch.get("direction")) or entry, 2)
        # الوقف عند الدخول أو أفضل منه؟ لا نتراجع به
        if current and ((is_buy and current >= target)
                        or (not is_buy and current <= target)):
            continue
        if modify_channel_position(symbol, position, target,
                                   float(getattr(position, "tp", 0.0) or 0.0)):
            done += 1
    if done:
        print(f"[VIP] 🛡️ تأمين تلقائي — {done} صفقة")
    return done


# ═════════════════════════════════════════════
# 🇬🇧 قناة VEY GOLD VIP — صفقة عند كل رقم
# ═════════════════════════════════════════════
# ترسل رقمين لكل توصية: «BUY NOW» ثم «4005-4010». فصفقتان، واحدة
# عند كل رقم. ما بلغه السعر يُفتح سوقاً، وما لم يبلغه يصير أمراً
# معلّقاً ينتظره — وقد ينتظر أياماً، فالمدرّب يعمل على مناطق سيولة.

VEY_DEFAULT_SL_POINTS = 10.0   # خلف أبعد رقم حين لا يرسل المدرّب وقفاً
VEY_FIXED_TP_POINTS = 10.0     # هدف كل صفقة من دخولها هي


def vey_default_stop(direction, levels, points):
    """الوقف خلف أبعد رقم: تحت الأدنى شراءً، وفوق الأعلى بيعاً.

    واحدٌ لكل صفقات التوصية لا لكلٍّ وقفها: المدرّب يرى المنطقة
    كلها، فبطلانها يبطل الدخولين معاً."""
    if not levels:
        return 0.0
    if direction == "BUY":
        return round(min(levels) - points, 2)
    return round(max(levels) + points, 2)


def vey_open_levels(symbol, ch, direction, levels, stop=0.0):
    """صفقة عند كل رقم — سوقاً إن بلغه السعر، ومعلّقةً إن لم يبلغه.

    يعيد (ما فُتح سوقاً، ما عُلّق، سبب الرفض إن رُفض)."""
    if _guard_state.get("halted"):
        return 0, 0, "البوت موقوف عند حدّ الخسارة"
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return 0, 0, "لا سعر مباشر"
    # المقارنة بسعر الشارت (bid) لا بسعر التنفيذ: القناة تكتب أرقام
    # الشارت، وفرقُ السعر (spread) كان يجعل «السعر عند 4010» يُقرأ
    # 4010.20 فلا يُعدّ بالغاً الرقم، فيُعلَّق ما كان يجب أن يُفتح.
    market = float(tick.bid)
    points = float(ch.get("default_sl") or VEY_DEFAULT_SL_POINTS)
    stop = float(stop or vey_default_stop(direction, levels, points))

    # السعر تجاوز الوقف قبل أن تصل الرسالة: الفكرة ماتت، ودخولٌ
    # هناك خسارةٌ مضمونة لا احتمالها
    if ((direction == "BUY" and market <= stop)
            or (direction == "SELL" and market >= stop)):
        return 0, 0, (f"السعر {market:.2f} تجاوز الوقف {stop:.2f} — "
                      f"لم يُفتح شيء")

    tp_points = float(ch.get("fixed_tp") or VEY_FIXED_TP_POINTS)
    sign = 1 if direction == "BUY" else -1
    lot = float(ch["lot"])
    opened = placed = 0
    for level in levels:
        level = round(float(level), 2)
        target = round(level + sign * tp_points, 2)
        reached = (market <= level) if direction == "BUY" else (market >= level)
        meta = channel_group_meta(
            GOLDBOT_CHANNEL, direction,
            signal_key=f"vey:{time.time_ns()}:{level}",
        )
        meta["lot"] = lot
        if reached:
            # السعر عند الرقم أو أفضل منه: الهدف من دخولنا الفعلي
            position = open_trade(
                symbol, direction, lot,
                sl_price=stop, tp_price=0.0,
                magic=ch["magic"], comment="VEY", meta=meta,
                return_position=True)
            if position:
                entry = round(float(position.price_open), 2)
                modify_channel_position(
                    symbol, position, stop,
                    round(entry + sign * tp_points, 2))
                opened += 1
        elif place_pending(symbol, direction, lot, level, stop, target,
                           ch["magic"], "VEY", meta):
            placed += 1
    return opened, placed, None


def place_pending(symbol, direction, lot, price, sl, tp, magic, comment,
                  meta=None):
    """أمر معلّق عند سعرٍ لم يبلغه السوق بعد."""
    if not require_live_account(comment):
        return False
    if _channel_runtime_mode["enabled"] and not allowed_gold_symbol(symbol):
        print(f"[SYMBOL-GUARD] ⛔ رُفض التعليق على {symbol}")
        return False
    order_type = (mt5.ORDER_TYPE_BUY_LIMIT if direction == "BUY"
                  else mt5.ORDER_TYPE_SELL_LIMIT)
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": float(lot),
        "type": order_type,
        "price": round(float(price), 2),
        "sl": round(float(sl), 2) if sl else 0.0,
        "tp": round(float(tp), 2) if tp else 0.0,
        "magic": int(magic),
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    result = mt5.order_send(request)
    done = bool(result and getattr(result, "retcode", None)
                == mt5.TRADE_RETCODE_DONE)
    if done:
        ticket = getattr(result, "order", 0)
        _pending_meta[ticket] = dict(meta or {}, price=request["price"])
        print(f"[MT5] ⏳ {direction} LIMIT {lot}lot @ {request['price']:.2f} "
              f"| SL={request['sl']:.2f} TP={request['tp']:.2f}")
    else:
        code = getattr(result, "retcode", "?") if result else mt5.last_error()
        print(f"[MT5] ⛔ تعذّر تعليق {direction} @ {request['price']:.2f} "
              f"— {code}")
    return done


def vey_pending(symbol, ch):
    """أوامر هذه القناة المعلّقة."""
    orders = mt5.orders_get(symbol=symbol) or []
    return [o for o in orders if getattr(o, "magic", None) == ch["magic"]]


def handle_vey_message(symbol, text, signal_key=None, ch=None):
    """رسالة من القناة الإنجليزية → ما تحمله من أفعال.

    الاتجاه يصل في رسالة والأرقام في التي تليها، فيُحفظ الاتجاه في
    القناة حتى تأتي أرقامه."""
    ch = ch or _vip_state
    if signal_already_processed(signal_key):
        return
    acts = vey_signals.interpret_all(text, ch.get("pending_direction"))
    if not acts:
        journal("تجاهل", ch.get("name", ""), text, "لا أمر فيها")
        return
    mark_signal_processed(signal_key)
    for act in acts:
        vey_apply(symbol, act, ch)


def vey_apply(symbol, act, ch):
    name = act["action"]
    why = act.get("why", "")
    tag = f" ({ch['name']})" if ch.get("name") else ""
    print(f"[VEY]{tag} {name} — {why}")
    journal("قرار", ch.get("name", ""), name, why)
    head = f"🗣️ <b>{name}</b>{tag}\n{why}\n\n"

    if name == "SIGNAL":
        ch["pending_direction"] = act["direction"]
        notify_tg(head + "⏸️ تُنتظر أرقام الدخول")

    elif name == "LEVELS":
        direction = act["direction"]
        ch["pending_direction"] = None
        opened, placed, reject = vey_open_levels(
            symbol, ch, direction, act["levels"])
        if reject:
            notify_tg(head + f"⚠️ {reject}")
            return
        ch["direction"] = direction
        ch["stop_was_hit"] = False
        stop = vey_default_stop(
            direction, act["levels"],
            float(ch.get("default_sl") or VEY_DEFAULT_SL_POINTS))
        notify_tg(head + (
            f"✅ فُتحت {opened} سوقاً · ⏳ عُلّق {placed}\n"
            f"لوت {ch['lot']:g} لكل رقم\n"
            f"🛑 وقف {stop:g} (افتراضي حتى يرسل المدرّب وقفه)\n"
            f"🎯 هدف كل صفقة +"
            f"{float(ch.get('fixed_tp') or VEY_FIXED_TP_POINTS):g} درجات "
            f"من دخولها"))

    elif name == "SET_STOP":
        price = round(float(act["price"]), 2)
        done = vip_set_stop(symbol, price, ch)
        waiting = 0
        for order in vey_pending(symbol, ch):
            if modify_pending_stop(symbol, order, price):
                waiting += 1
        notify_tg(head + f"🛑 الوقف {price:g} على {done} صفقة"
                  + (f" و{waiting} أمراً معلّقاً" if waiting else ""))

    elif name == "BREAKEVEN":
        done = vip_breakeven(symbol, None, ch)
        notify_tg(head + (f"🛡️ الوقف إلى الدخول على {done} صفقة"
                          if done else "⚠️ لا صفقات مفتوحة"))

    elif name == "CLOSE_ALL":
        closed = vip_close_all(symbol, why, ch)
        ch["stop_was_hit"] = True
        # الأوامر المعلّقة تبقى: المدرّب يعمل على مناطق سيولة ينتظر
        # ارتدادها، وإلغاؤها عند كل إغلاق يُفسد خطته
        notify_tg(head + f"🔻 أُغلقت {closed} صفقة"
                  + (f"\n⏳ و{len(vey_pending(symbol, ch))} أمراً معلّقاً "
                     f"باقية كما هي"
                     if vey_pending(symbol, ch) else ""))

    if name != "SIGNAL":
        journal_account(symbol, f"بعد {name}")


def modify_pending_stop(symbol, order, sl):
    """يغيّر وقف أمرٍ معلّق دون تحريك سعره."""
    if not require_live_account("VEY pending sl"):
        return False
    result = mt5.order_send({
        "action": mt5.TRADE_ACTION_MODIFY,
        "order": order.ticket,
        "price": float(order.price_open),
        "sl": round(float(sl), 2),
        "tp": float(getattr(order, "tp", 0.0) or 0.0),
    })
    return bool(result and getattr(result, "retcode", None)
                == mt5.TRADE_RETCODE_DONE)


# ═════════════════════════════════════════════
# 📓 السجلّ اليومي — بين القناة والحساب
# ═════════════════════════════════════════════
# ملفٌ لكل يوم فيه كل رسالة وصلت، وما قرّره البوت فيها، وما نفّذه،
# وسببُ كل رفض. لأن الخطأ في منتصف يوم تداول لا يُكتشف بالتخمين:
# إمّا أن يكون مكتوباً، أو يضيع.

JOURNAL_DIR = "journal"


def journal_path(day=None):
    day = day or datetime.now().strftime("%Y-%m-%d")
    return os.path.join(JOURNAL_DIR, f"{day}.txt")


def journal(kind, channel="", text="", detail=""):
    """سطرٌ في سجلّ اليوم. لا يرفع استثناءً أبداً.

    السجلّ أداة تشخيص لا جزءٌ من التنفيذ: لو عطب القرص أو امتلأ،
    يجب أن يستمر البوت في إدارة صفقاتٍ مفتوحة بمال حقيقي."""
    try:
        os.makedirs(JOURNAL_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%H:%M:%S")
        one = " ".join(str(text or "").split())
        if len(one) > 300:
            one = one[:297] + "..."
        why = " ".join(str(detail or "").split())
        line = f"{stamp}  {kind:<8}  {(channel or '-'):<14}  {one}"
        if why:
            line += f"   ← {why}"
        with open(journal_path(), "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def journal_account(symbol, note=""):
    """لقطة حالة الحساب: الرصيد وما هو مفتوح ومعلّق لكل قناة."""
    try:
        info = mt5.account_info()
        if info:
            journal("حساب", "-",
                    f"رصيد ${float(getattr(info, 'balance', 0) or 0):.2f} · "
                    f"حقوق ${float(getattr(info, 'equity', 0) or 0):.2f}",
                    note)
        for ch in _channels:
            rows = vip_positions(symbol, ch)
            waiting = []
            try:
                waiting = vey_pending(symbol, ch)
            except Exception:
                pass
            if not rows and not waiting:
                continue
            for p in rows:
                side = "شراء" if p.type == mt5.POSITION_TYPE_BUY else "بيع"
                journal("مفتوحة", ch.get("name", ""),
                        f"{side} {p.volume} دخول {p.price_open:.2f} "
                        f"وقف {float(p.sl or 0):.2f} "
                        f"هدف {float(p.tp or 0):.2f} "
                        f"ربح {float(getattr(p, 'profit', 0) or 0):+.2f}")
            for o in waiting:
                journal("معلّق", ch.get("name", ""),
                        f"{o.volume} عند {o.price_open:.2f} "
                        f"وقف {float(o.sl or 0):.2f} "
                        f"هدف {float(o.tp or 0):.2f}")
    except Exception:
        pass


def route_message(symbol, text, signal_key=None, ch=None):
    """يسلّم الرسالة إلى مترجم لهجتها، ويكتب كليهما في السجلّ."""
    ch = ch or _vip_state
    journal("رسالة", ch.get("name", ""), text)
    if ch.get("parser") == "en":
        return handle_vey_message(symbol, text, signal_key, ch)
    return handle_vip_message(symbol, text, signal_key, ch)


def handle_vip_message(symbol, text, signal_key=None, ch=None):
    """الرسالة الواحدة → كل ما تحمله من أفعال، بالترتيب.

    رسالةٌ واحدة قد تحمل فعلين: «شراء من 62 ستوبك 60» فتحٌ وستوب،
    و«هدف اول 70 / هدف ثاني 75» هدفان. وبفعلٍ واحد لكل رسالة كان
    الثاني يضيع، أو يحلّ أحدهما محلّ الآخر."""
    ch = ch or _vip_state
    if signal_already_processed(signal_key):
        return
    tick = mt5.symbol_info_tick(symbol)
    reference = float(tick.bid) if tick else None
    rows = vip_positions(symbol, ch)

    acts = vip_signals.interpret_all(
        text, reference_price=reference,
        has_open_trade=bool(rows),
        stop_was_hit=ch["stop_was_hit"],
    )
    if not acts:
        journal("تجاهل", ch.get("name", ""), text,
                f"لا أمر فيها (مفتوحة: {len(rows)})")
        return

    mark_signal_processed(signal_key)
    for act in acts:
        vip_apply(symbol, act, ch)


def vip_apply(symbol, act, ch=None):
    """ينفّذ فعلاً واحداً على **قناة** واحدة."""
    ch = ch or _vip_state
    name = act["action"]
    if name == "NONE":
        return
    why = act.get("why", "")
    tag = f" ({ch['name']})" if ch.get("name") and len(_channels) > 1 else ""
    print(f"[VIP]{tag} {name} — {why}")
    journal("قرار", ch.get("name", ""), name, why)
    head = f"🗣️ <b>{name}</b>{tag}\n{why}\n\n"

    if name == "ADD_ENTRY":
        # دخولٌ إضافي بسعرٍ صريح: لا يُلغي ما هو مفتوح ولا يرفع
        # المنع. والاتجاه من التوصية الجارية حين لا يذكره المدرّب.
        direction = act.get("direction") or ch["direction"]
        if not direction:
            notify_tg(head + "⚠️ لا اتجاه معروف — لم يُفتح شيء")
            return
        before = len(vip_positions(symbol, ch))
        opened = vip_open(symbol, direction, act.get("size", "FULL"), ch)
        notify_tg(head + (
            f"➕ أُضيفت {opened} صفقة × {ch['lot']} "
            f"({'شراء' if direction == 'BUY' else 'بيع'})\n"
            f"المجموع {before + opened}"
            if opened else "❌ لم تُفتح أي صفقة"))

    elif name in ("OPEN", "REENTRY_IF_HIT", "RENEW"):
        direction = act.get("direction") or ch["direction"]
        if not direction:
            notify_tg(head + "⚠️ لا اتجاه معروف — لم يُفتح شيء")
            return
        if name == "OPEN":
            ch["no_reopen"] = False
            ch["quoted"] = []   # توصية جديدة: أسعار القديمة لا تخصّها
            # «شراء من 3903» يحمل سعر المدرّب، والبوت ينفّذ بعده
            # بلحظة. ولولا حفظه لنُقل الوقف عند «ستوبك دخولك» إلى
            # دخول البوت — أسوأ بدرجتين من دخول المدرّب.
            if act.get("coach_price"):
                ch["quoted"] = [float(act["coach_price"])]
        ch["chasing"] = None
        opened = vip_open(symbol, direction, act.get("size", "FULL"), ch)
        if opened and name == "OPEN" and act.get("coach_price"):
            vip_arm_chase(symbol, ch, act["coach_price"], direction)
        notify_tg(head + (
            f"✅ فُتحت {opened} صفقة × {ch['lot']} "
            f"({'شراء' if direction == 'BUY' else 'بيع'})\n"
            + (f"🛑 وقف مؤقت "
               f"{vip_risk_text(symbol, ch['temp_sl'], ch=ch)} "
               f"حتى يصل ستوب القناة"
               if ch["temp_sl"] > 0 else
               "⚠️ <b>بلا وقف</b> — حتى يرسل المدرّب وقفه")
            if opened else "❌ لم تُفتح أي صفقة"))

    elif name == "SET_STOP":
        at = padded_stop(ch, ch.get("direction"), act["price"])
        done = vip_set_stop(symbol, act["price"], ch, ch.get("direction"))
        notify_tg(head + (
            f"🛑 الوقف {at:g} على {done} صفقة"
            + (f" (وقف المدرّب {act['price']:g} "
               f"+{ch['sl_pad']:g} مجال)" if ch.get("sl_pad") else "")
            if done else "⚠️ لا صفقات مفتوحة"))

    elif name in ("SET_TP1", "SET_TP2"):
        which = 1 if name == "SET_TP1" else 2
        if ch.get("fixed_tp", 0) > 0:
            # هدف الحساب ثابت بقراره، فهدف القناة لا يُكتب فوقه
            notify_tg(head + f"⏭️ الهدف ثابت "
                             f"+{ch['fixed_tp']:g} نقاط — "
                             f"هدف القناة يُتجاهل")
            return
        done = vip_set_target(symbol, act["price"], which, ch)
        if which == 2 and ch.get("one_target"):
            notify_tg(head + "⏭️ وضع الهدف الواحد — لا هدف ثانٍ")
        else:
            notify_tg(head + (f"🎯 الهدف {act['price']:g} على {done} صفقة"
                              if done else "⚠️ لا صفقات مفتوحة"))

    elif name == "QUOTE":
        ch["quoted"] = sorted(set(ch.get("quoted") or [])
                              | set(act["prices"]))
        print(f"[VIP]{tag} 📝 دخول المدرّب: "
              + "، ".join(f"{p:g}" for p in ch["quoted"]))

    elif name == "BREAKEVEN":
        # الرقم الصريح في الرسالة أولى من المحفوظ: «ستوبك دخولك على
        # 57» قالها المدرّب نصّاً، فلا يُخمَّن ما صرّح به
        at = act.get("price") or coach_entry(ch, ch.get("direction"))
        done = vip_breakeven(symbol, None, ch, at)
        notify_tg(head + (
            (f"🛡️ الوقف إلى {at:g} — دخول المدرّب"
             if at else "🛡️ الوقف إلى الدخول")
            + f" على {done} صفقة"
            if done else "⚠️ لا صفقات مفتوحة"))

    elif name == "CLOSE_HALF":
        closed, secured = vip_close_half(symbol, ch)
        notify_tg(head + f"💰 أُغلقت {closed}، ووقف {secured} إلى الدخول")

    elif name in ("CLOSE_ALL", "CLOSE_NO_REOPEN"):
        closed = vip_close_all(symbol, why, ch)
        ch["stop_was_hit"] = True
        if name == "CLOSE_NO_REOPEN":
            ch["no_reopen"] = True
        notify_tg(head + f"🔻 أُغلقت {closed} صفقة"
                  + ("\n🚫 ولا يفتح مجدداً حتى توصية جديدة"
                     if name == "CLOSE_NO_REOPEN" else ""))

    elif name == "REDUCE_SIZE":
        closed = vip_reduce(symbol, ch)
        notify_tg(head + (f"📉 أُغلقت {closed} لتخفيف اللوت"
                          if closed else "العدد مخفّف أصلاً"))

    if name != "QUOTE":
        journal_account(symbol, f"بعد {name}")


def channel_lines(symbol, ch):
    """وصف قناةٍ واحدة في رسالة البدء."""
    if ch.get("parser") == "en":
        out = [f"صفقة × {ch['lot']:g} عند كل رقم من رقمَي التوصية\n",
               "ما بلغه السعر يُفتح فوراً، وما لم يبلغه يبقى أمراً "
               "معلّقاً ينتظره\n"]
    else:
        out = [f"{vip_full(ch)} صفقة × {ch['lot']:g} "
               f"تُفتح فور وصول التوصية\n"]
    if ch["temp_sl"] > 0:
        out.append(f"🛑 وقف مؤقت "
                   f"{vip_risk_text(symbol, ch['temp_sl'], True, ch)}\n"
                   f"   حتى يرسل المدرب وقفه\n")
    else:
        out.append("⚠️ <b>بلا وقف مؤقت</b> — الصفقة مكشوفة حتى "
                   "يرسل المدرّب وقفه\n")
    if float(ch.get("auto_be") or 0.0) > 0:
        out.append(f"🛡️ تأمين تلقائي عند +{ch['auto_be']:g} نقاط "
                   f"إن لم يرسل «تأمين»\n")
    else:
        out.append("🛡️ لا تأمين تلقائي — الوقف لا يتحرك إلا بأمر "
                   "المدرّب\n")
    if ch["fixed_tp"] > 0:
        out.append(f"🎯 <b>هدف ثابت +{ch['fixed_tp']:g} نقاط</b> "
                   f"من سعر الدخول — وأهداف القناة تُتجاهل\n")
    elif ch["one_target"]:
        out.append("🎯 <b>هدف واحد</b>: الهدف الأول على كل الصفقات، "
                   "ولا هدف ثانٍ\n")
    else:
        out.append(f"🎯 الهدف الأول على {vip_half_count(ch)}، "
                   f"والثاني على الباقي\n")
    if vip_half_count(ch) == 0:
        out.append("✂️ «احجز نص» ينقل الوقف للدخول "
                   "(صفقة واحدة لا تُنصَّف)\n")
    else:
        out.append(f"✂️ «احجز نص» يغلق {vip_half_count(ch)} "
                   f"وينقل الوقف للدخول\n")
    out.append("⛔ «خروج» أو «أغلق» أو «انتهت» تغلق صفقات هذه "
               "القناة وحدها\n")
    return out


def startup_message(symbol, login, balance, is_real, account_kind,
                    watched_names):
    """نص رسالة البدء.

    دالةٌ مستقلة لا سطورٌ داخل main: بُنيت أولاً بسلسلة «+» متشعّبة،
    وكل سطر شرطيّ أضاف قوساً حتى انكسرت الجملة وتعطّل التشغيل عند
    أول تحديث — ولم يكشفه فحصٌ لأن أياً منها لا يبلغ main."""
    parts = [
        f"{'🔴' if is_real else '🧪'} <b>بوت القنوات جاهز — "
        f"حساب {account_kind} — {symbol}</b>\n\n",
    ]
    if not is_real:
        parts.append(
            "⚠️ <b>هذه تجربة على حساب تجريبي — المال وهمي.</b>\n\n")
    parts += [
        f"<b>نسخة البوت: {BOT_VERSION}</b>\n",
        f"({BOT_FEATURES})\n\n",
        f"الحساب: #{login} | رصيد: ${balance:.2f}\n\n",
    ]
    for ch in _channels:
        name = ch.get("chat_name") or ch.get("name") or watched_names or "؟"
        parts.append(f"🤖 <b>{name}</b>\n")
        parts += channel_lines(symbol, ch)
        parts.append("\n")
    if len(_channels) > 1:
        parts.append("🔒 القناتان منفصلتان تماماً: أمرُ إحداهما لا يمسّ "
                     "صفقات الأخرى\n\n")
    # الرقم المعروض هو المعمول به فعلاً لا الافتراضي: قد يغيّره
    # --max-loss أو يعطّله صفر
    if _guard_state["max_loss"] > 0:
        parts.append(
            f"🚨 <b>حدّ الخسارة اليومي: "
            f"${_guard_state['max_loss']:g}</b> (على الحساب كله)\n"
            f"عند بلوغه يغلق كل الصفقات ويتوقف حتى تشغّله أنت\n"
            f"ويصفّر مع كل يوم جديد — خسارة الأمس لا تُحسب على "
            f"اليوم\n\n")
    else:
        parts.append("🚨 <b>حدّ الخسارة اليومي: معطّل</b>\n"
                     "لن يوقف البوت نفسه مهما خسر الحساب\n\n")

    parts += [
        f"✋ <b>صفقاتك اليدوية</b>: وقف ${MANUAL_SL_USD:g} وهدف "
        f"${MANUAL_TP_USD:g}، والوقف ينتقل للدخول عند "
        f"+${MANUAL_BREAKEVEN_USD:g}\n",
        "وما تحرّكه بيدك — وقفاً أو هدفاً — لا يلمسه البوت بعدها "
        "أبداً\n\n",
        "نوع الحساب: Retail Hedging\n",
        f"📌 أقرأ من: {watched_names or 'لا شيء'}\n",
        "🚫 لا أقرأ أي محادثة أخرى مهما كانت مثبتة.",
    ]
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="بوت XAUUSD — قناة توصيات الذهب"
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
    parser.add_argument(
        "--channel",
        action="append",
        default=[],
        help="قناة يُقرأ منها؛ كرّره لعدة قنوات. ويقبل إعدادات خاصة "
             "بها: \"VIP AN|lot=0.05|pos=1|sl=5|tp=5|one\" — وما لم "
             "يُذكر يأخذ الإعداد العام",
    )
    parser.add_argument(
        "--account",
        type=int,
        default=0,
        help="رقم حساب MT5 المسموح — يرفض البوت العمل على غيره",
    )
    parser.add_argument(
        "--mt5-path",
        default="",
        help="مسار terminal64.exe حين تكون أكثر من نسخة MT5 مفتوحة",
    )
    parser.add_argument(
        "--lot",
        type=float,
        default=VIP_LOT,
        help=f"حجم الصفقة الواحدة (الافتراضي {VIP_LOT:g}؛ "
             f"تُفتح {VIP_POSITIONS_FULL} منها لكل توصية "
             f"ما لم يُضبط --positions)",
    )
    parser.add_argument(
        "--mt5-server",
        default="",
        help="اسم خادم الوسيط — يُمرَّر مع الحساب لإلزام المنصّة به",
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="المنصّة تعمل بوضع portable (مجلّد بيانات خاص بها)",
    )
    parser.add_argument(
        "--temp-sl",
        type=float,
        default=VIP_TEMP_SL_USD,
        help=f"الوقف المؤقت بالنقاط حتى يصل وقف المدرّب "
             f"(الافتراضي {VIP_TEMP_SL_USD:g}، وصفر = بلا وقف)",
    )
    parser.add_argument(
        "--fixed-tp",
        type=float,
        default=0.0,
        help="هدف ثابت بالنقاط من سعر الدخول؛ وعنده تُتجاهل أهداف "
             "القناة (صفر = يتبع القناة)",
    )
    parser.add_argument(
        "--positions",
        type=int,
        default=VIP_POSITIONS_FULL,
        help=f"عدد صفقات التوصية الواحدة (الافتراضي {VIP_POSITIONS_FULL})",
    )
    parser.add_argument(
        "--one-target",
        action="store_true",
        help="هدف واحد لكل الصفقات عند الهدف الأول، ويُتجاهل الهدف الثاني",
    )
    parser.add_argument(
        "--max-loss",
        type=float,
        default=VIP_MAX_LOSS_USD,
        help=f"حدّ الخسارة اليومي بالدولار؛ عنده يُغلق كل شيء ويتوقف "
             f"(الافتراضي {VIP_MAX_LOSS_USD:g}، وصفر يعطّله)",
    )
    args = parser.parse_args()

    # سطر الأوامر يسبق config.py، فتستطيع تبديل القناة بلا تعديل ملف
    if args.channel:
        _only_channel["name"] = args.channel[0].split("|")[0].strip()

    set_channels(build_channels(args.channel, {
        "lot": float(args.lot or 0.0),
        "one_target": bool(args.one_target),
        "positions": max(1, int(args.positions or 1)),
        "temp_sl": max(0.0, float(args.temp_sl or 0.0)),
        "fixed_tp": max(0.0, float(args.fixed_tp or 0.0)),
    }))

    _channel_runtime_mode["allow_demo"] = bool(args.demo)
    if args.demo:
        print("[DEMO] ⚠️ وضع التجربة: الحساب التجريبي مسموح في هذه الجلسة")

    if args.test:
        channels_self_test(args.symbol, expected_login=args.account or None,
                           mt5_path=args.mt5_path or None,
                           mt5_server=args.mt5_server or MT5_SERVER,
                           mt5_portable=args.portable)
        return

    print(f"\n{'═' * 55}")
    print(
        f"  🐋 بوت القنوات — نسخة {BOT_VERSION} — "
        + ("حساب تجريبي (تجربة)" if args.demo else "حساب حقيقي")
    )
    print(f"  {args.symbol}")
    for ch in _channels:
        print(f"  📌 {ch['name'] or '(غير محددة!)'} — "
              + ("صفقة عند كل رقم × " if ch.get("parser") == "en"
                 else f"{vip_full(ch)} صفقة × ")
              + f"{ch['lot']:g}"
              + (f" · وقف {ch['temp_sl']:g}" if ch["temp_sl"] else " · بلا وقف")
              + (f" · هدف ثابت {ch['fixed_tp']:g}" if ch["fixed_tp"] else ""))
    print("  🚫 لا قنوات أخرى ولا استراتيجيات — هذه القنوات وحدها")
    print(f"{'═' * 55}\n")

    # نسختان من MT5 على الجهاز نفسه؟ مكتبة بايثون تتصل بواحدة، ولا
    # ضمان أنها الصحيحة. --mt5-path يثبّت النسخة، و--account يرفض
    # العمل إن وجد البوت نفسه على حساب آخر — فلا تُفتح صفقة بمال
    # حساب لم يُقصد.
    started, how = mt5_start(args.mt5_path, args.account,
                             args.mt5_server or MT5_SERVER,
                             MT5_PASSWORD, args.portable)
    print(f"[MT5] محاولة الاتصال {how}")
    if not started:
        print("[ERROR] MT5 غير مفتوح!")
        if args.mt5_path:
            print(f"        المسار المطلوب: {args.mt5_path}")
        return
    _channel_runtime_mode["enabled"] = True
    _channel_runtime_mode["symbol"] = args.symbol

    account = mt5.account_info()
    connected_login = getattr(account, "login", None)
    if args.account:
        # الرقم الذي حدّده صاحب الحساب هو المرجع، لا ما صادفه الاتصال
        _channel_runtime_mode["account_login"] = args.account
        if connected_login != args.account:
            print(f"[ACCOUNT-GUARD] ⛔ البوت متصل بالحساب "
                  f"{connected_login} والمطلوب {args.account}")
            print(f"                 جرى الاتصال {how}")
            cure = ("أغلق نسخ MT5 الأخرى"
                    if MT5_PASSWORD else
                    "ضع MT5_PASSWORD و MT5_SERVER في config.py — "
                    "المسار وحده لا يكفي مع عدة نسخ MT5")
            print(f"                 {cure}")
            send_tg(
                "⛔ <b>لم يبدأ البوت — حساب خاطئ</b>\n\n"
                f"الاتصال وقع على <b>{connected_login}</b> "
                f"والمطلوب <b>{args.account}</b>.\n"
                f"جرى الاتصال {how}.\n\n"
                f"{cure}"
            )
            mt5.shutdown()
            return
        print(f"[ACCOUNT-GUARD] ✅ الحساب {connected_login} كما حُدِّد")
    else:
        _channel_runtime_mode["account_login"] = connected_login
        print(f"[ACCOUNT-GUARD] ⚠️ بلا --account: البوت سيعمل على "
              f"{connected_login} — وهو ما صادفه الاتصال")

    # نقطة الأساس لحدّ الخسارة: حقوق الملكية لحظة التشغيل
    _guard_state["max_loss"] = float(args.max_loss or 0.0)
    _guard_state["halted"] = False
    _guard_state["day"] = vip_today()
    _guard_state["start_equity"] = float(
        getattr(account, "equity", None)
        or getattr(account, "balance", 0.0) or 0.0
    )
    if _guard_state["max_loss"] > 0:
        floor = _guard_state["start_equity"] - _guard_state["max_loss"]
        print(f"[LOSS-GUARD] 🛡️ حدّ يومي ${_guard_state['max_loss']:g} — "
              f"يتوقف اليوم عند ${floor:.2f} "
              f"(من ${_guard_state['start_equity']:.2f})")
        print("[LOSS-GUARD]    ويصفّر مع كل يوم جديد")
    else:
        print("[LOSS-GUARD] ⚠️ معطّل — لا حدّ للخسارة")
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
    lot_ok, lot_detail = vip_lot_ok(args.symbol)
    if not lot_ok:
        print(f"[LOT-GUARD] ⛔ {lot_detail}")
        send_tg(
            "⛔ <b>لم يبدأ بوت القنوات</b>\n\n"
            f"{lot_detail}\n"
            "شغّله بـ --lot ولوت يقبله وسيطك."
        )
        mt5.shutdown()
        return
    print(f"[LOT-GUARD] ✅ {lot_detail}")
    reader_ok, reader_detail, pinned_names = asyncio.run(
        telegram_reader_diagnostic(allow_login=True)
    )
    watched_names = "، ".join(pinned_names)
    if not reader_ok:
        print(f"[TG-Reader] ⛔ {reader_detail}")
        send_tg(
            "⛔ <b>لم يبدأ بوت القنوات</b>\n\n"
            f"{reader_detail}\n"
            "ثبّت قناة التوصيات في تيليغرام ثم شغّل أداة الفحص."
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
    time.sleep(3)
    journal("بدء", "-", f"نسخة {BOT_VERSION} · حساب "
            f"{getattr(info, 'login', '?')} · {args.symbol}",
            "، ".join(f"{c['name']} {vip_full(c)}×{c['lot']:g}"
                      for c in _channels))
    journal_account(args.symbol, "عند التشغيل")
    send_tg(startup_message(
        args.symbol, getattr(info, "login", "?"), info.balance,
        is_real, account_kind, watched_names))
    channels_only_loop()
    mt5.shutdown()


if __name__ == "__main__":
    main()
