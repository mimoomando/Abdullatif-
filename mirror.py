"""مرآةُ حسابٍ آخر: تقرأ ولا تلمس.

تراقب حساباً يتداول فيه غيرُك، وتجيب عن أربعة أسئلة لا يجيب عنها
كشفُ الحساب:

  ١ — ماذا فتح؟ كم صفقة، وبأيّ حجم، ومن أيّ سعر — وأين وضع وقفَه
      وهدفَه، وهل نقلهما بعد الفتح.

  ٢ — هل بلغ السعرُ الهدفَ أو الوقفَ قبل أن يُغلق؟

  ٣ — ولماذا أغلقها؟ تُلتقط حالةُ السوق في اللحظة نفسها: شمعةُ
      الدقيقة، أانقلبت ضده؟ وكم شمعةً متتالية؟ وهل خرج عند قمّة
      الحركة أم بعد تراجعٍ عنها؟ ثم تُجمع الأسبابُ عبر الصفقات،
      فيُعرف ما الذي يُخرجه عادةً — لا ما نظنّه.

  ٤ — وماذا جرى بعد خروجه؟ يبقى السعرُ تحت العين نصفَ ساعة: هل
      استمرّ في اتجاهه فترك ربحاً وراءه، أم انعكس فأنقذه خروجه؟
      ويُحفظ الحكمُ ويُجمع: «خرج مبكراً ٧ من ١٠، ومتوسطُ ما يتركه
      كذا درجة».

ومع ذلك كلّه مراقبةٌ للحساب نفسه: الرصيد وحقوق الملكية والهامش
والعويم، وتنبيهٌ حين يضيق الهامش أو يثقل العويم.

لا تفتح صفقةً ولا تغلقها ولا تعدّل واحدة. أمرُ التنفيذ مُستبدَلٌ
برفضٍ صريح قبل أيّ اتصال، فلا طريقَ — قديمٌ أو جديد — يبلغ الوسيط.

    python mirror.py --account 1234567 ^
      --mt5-path "C:\\Program Files\\JustMarkets MetaTrader 5\\terminal64.exe"
"""
import argparse
import json
import os
import time
import types
from datetime import datetime

import MetaTrader5 as mt5

try:
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
except Exception:
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

try:
    import requests
except Exception:                                    # pragma: no cover
    requests = None


VERSION = "2026-11-27.3"
POLL = 0.25             # ثانيةُ النبض — ربعُ ثانية تكفي لسكالبر
BASKET_GAP = 5.0        # ما فُتح خلالها معاً سلّةٌ واحدة
WINDOW_MIN = 30.0       # دقائقُ الحكم على الخروج بعد الإغلاق
AFTER_HOURS = 24.0      # ساعاتُ انتظار الهدف المتروك
NEAR = 0.50             # قُربٌ من الرقم يُحسب بلوغاً له
PEAK_NEAR = 0.30        # قُربٌ من قمّة الحركة يُحسب خروجاً عندها
TAIL_SECONDS = 180.0    # ذيلُ الأسعار المحفوظ لقراءة لحظة الخروج
RANGE_BARS = 20         # شموعُ المدى الذي يُقاس عليه موضعُ الدخول
ROUND_NEAR = 0.15       # قُربٌ من دولارٍ صحيح يُحسب دخولاً عنده
TOL_CAP = 1.50          # أقصى سماحيةٍ تُحسب قُرباً من مستوى
ACCOUNT_EVERY = 10.0    # ثوانٍ بين لقطتَي حساب
STRESS_FLOAT = 5.0      # % من الرصيد: عويمٌ سالب أثقل منه تنبيه
STRESS_MARGIN = 300.0   # % أدنى مستوى هامشٍ قبل التنبيه
STORE = "mirror"        # مجلّد السجلّات

# ★ المحاكاة الورقية: صفقةٌ واحدة عند كل دخولٍ له، بلا خروجٍ مبكر.
# وكلُّ خطّةٍ تُجرَّب معاً في الوقت نفسه، فلا يُعاد التشغيل لتجربة
# غيرها. ولا مالَ فيها ولا أمرَ يخرج إلى وسيط.
PAPER_LOT = 0.10
PAPER_PLANS = ((3, 8), (5, 8), (5, 10), (8, 10),
               (10, 15), (15, 10), (20, 15))
PAPER_HOURS = 6.0       # تُحسم بعدها بسعر السوق مهما كان

_rows = {}              # تذكرة → صفقةٌ مفتوحة
_baskets = {}           # مفتاح السلّة → سلّة
_after = []             # سلالٌ أُغلقت والعينُ عليها
_tail = {}              # رمز → [(وقت، عرض، طلب)] لآخر دقائق
_acct = {"at": 0.0, "balance": None, "told": 0.0}
_only = {"symbol": ""}     # رمزٌ واحد إن طُلب حصرُ المراقبة فيه
_paper = []                # صفقاتٌ ورقية مفتوحة — محاكاةٌ لا مال
_last_shut = {"at": 0.0}   # متى أُغلقت آخرُ سلّة — للفاصل بين الدخولات
_sent = []              # ما أُرسل — للفحص


# ─────────────────────────────────────────────
# أدواتٌ صغيرة
# ─────────────────────────────────────────────
def stamp(when=None):
    at = datetime.fromtimestamp(when) if when else datetime.now()
    return at.strftime("%Y-%m-%d %H:%M:%S")


def times(n):
    n = int(n)
    return {1: "مرة", 2: "مرتين"}.get(n, f"{n} مرات")


def refuse_orders():
    """يُبدّل أمرَ التنفيذ برفض.

    حارسٌ واحدٌ في مكانٍ واحد: ما دام order_send نفسُه يرفض، فلا
    يبلغ الوسيطَ أمرٌ مهما تغيّرت الشيفرة أو نُسي مسار."""
    def refuse(request=None, *a, **k):
        what = (request or {}).get("action", "?")
        print(f"[MIRROR] ⛔ مرآةٌ تقرأ ولا تنفّذ — رُفض أمر ({what})")
        log(f"رفض أمر تنفيذ ({what})")
        return types.SimpleNamespace(retcode=-1, comment="mirror-only",
                                     order=0, deal=0, price=0.0)
    mt5.order_send = refuse


def store_file(name):
    os.makedirs(STORE, exist_ok=True)
    return os.path.join(STORE, name)


def log(text):
    """سطرٌ في سجلّ اليوم. لا يرفع استثناءً أبداً."""
    try:
        day = datetime.now().strftime("%Y-%m-%d")
        line = f"{datetime.now():%H:%M:%S}  {' '.join(str(text).split())}"
        with open(store_file(f"{day}.txt"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def keep(name, record):
    """سطرُ JSON في ملفٍ — سجلٌّ يُقرأ بعدُ بالأرقام."""
    try:
        day = datetime.now().strftime("%Y-%m-%d")
        with open(store_file(f"{name}-{day}.jsonl"), "a",
                  encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def tally(name, keys):
    """عدّادٌ تراكمي يبقى بين التشغيلات — به يُعرف النمط لا الحالة."""
    path = store_file(f"{name}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        data = {}
    for key in keys:
        data[key] = float(data.get(key, 0)) + 1
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return data


def add_up(name, field, value):
    """مجموعٌ تراكمي — لحساب المتوسطات."""
    path = store_file(f"{name}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        data = {}
    data[field] = round(float(data.get(field, 0)) + float(value), 2)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return data


def tg(text):
    """يرسل إلى تيليغرام، ويحفظ المرسَل للفحص."""
    _sent.append(text)
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and requests):
        return False
    try:
        reply = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text,
                  "parse_mode": "HTML"}, timeout=10)
        return reply.status_code == 200
    except Exception as exc:
        print(f"[TG] ⚠️ {exc}")
        return False


def say(text):
    """يُرسل ويُسجّل — فما ضاع من تيليغرام يبقى على القرص."""
    tg(text)
    for line in text.replace("<b>", "").replace("</b>", "").splitlines():
        if line.strip():
            log(line.strip())


# ─────────────────────────────────────────────
# السعر: الصفقة تُغلق بالجهة المقابلة لفتحها
# ─────────────────────────────────────────────
def shut_price(buy, bid, ask):
    """السعرُ الذي تُغلق به صفقةٌ الآن: الشراء على العرض والبيع على
    الطلب. وبه يُقاس بلوغُ الهدف والوقف كما يقيسه الوسيط."""
    return bid if buy else ask


def gain(buy, entry, price):
    """ربحٌ بالدرجات من سعرٍ إلى سعر."""
    return round((price - entry) if buy else (entry - price), 2)


def reached(buy, price, mark):
    """هل بلغ السعرُ هذا الرقم في جهة الربح؟"""
    return bool(mark) and ((price >= mark) if buy else (price <= mark))


def struck(buy, price, mark):
    """هل بلغ السعرُ هذا الرقم في جهة الخسارة؟"""
    return bool(mark) and ((price <= mark) if buy else (price >= mark))


def tail_push(symbol, bid, ask):
    """ذيلُ الأسعار: دقائقُ قليلة تكفي لقراءة لحظة الخروج."""
    now = time.time()
    row = _tail.setdefault(symbol, [])
    row.append((now, bid, ask))
    edge = now - TAIL_SECONDS
    while row and row[0][0] < edge:
        row.pop(0)


# ─────────────────────────────────────────────
# الشموع: ماذا كان السوق يفعل لحظةَ خروجه
# ─────────────────────────────────────────────
def bar_at(bar, key):
    try:
        return float(bar[key])
    except Exception:
        return float(getattr(bar, key, 0.0) or 0.0)


def bars(symbol, frame, count):
    try:
        rows = mt5.copy_rates_from_pos(symbol, frame, 0, count)
    except Exception:
        rows = None
    try:
        return list(rows) if rows is not None and len(rows) else []
    except Exception:
        return []


def bar_way(bar):
    """اتجاهُ شمعة: صاعدةٌ أم هابطة."""
    shut, start = bar_at(bar, "close"), bar_at(bar, "open")
    return "up" if shut > start else "down" if shut < start else ""


def candle_facts(symbol, buy):
    """حالةُ الشموع الآن — بلغة «معه» و«ضده»."""
    mine = "up" if buy else "down"
    out = {}
    m1 = bars(symbol, getattr(mt5, "TIMEFRAME_M1", 1), 7)
    if m1:
        out["m1_now"] = bar_way(m1[-1])
        if len(m1) >= 2:
            out["m1_last"] = bar_way(m1[-2])
        against = 0
        for bar in reversed(m1[:-1]):
            way = bar_way(bar)
            if way and way != mine:
                against += 1
            else:
                break
        out["m1_against"] = against
    m5 = bars(symbol, getattr(mt5, "TIMEFRAME_M5", 5), 2)
    if m5:
        out["m5_now"] = bar_way(m5[-1])
    out["mine"] = mine
    return out


def shape_of(bar):
    """شكلُ الشمعة بلغةٍ تُقرأ: جسمُها وذيلاها."""
    top = bar_at(bar, "high")
    low = bar_at(bar, "low")
    start = bar_at(bar, "open")
    shut = bar_at(bar, "close")
    span = top - low
    if span <= 0:
        return "بلا مدى"
    body = abs(shut - start) / span
    up_tail = (top - max(start, shut)) / span
    dn_tail = (min(start, shut) - low) / span
    if body < 0.15:
        return "دوجي"
    if body > 0.70:
        return "جسمٌ كامل"
    if up_tail > 0.50:
        return "ذيلٌ علوي طويل"
    if dn_tail > 0.50:
        return "ذيلٌ سفلي طويل"
    return "شمعةٌ عادية"


def run_length(rows, way):
    """كم شمعةً متتاليةً في هذا الاتجاه قبل الآن."""
    count = 0
    for bar in reversed(rows):
        if bar_way(bar) == way:
            count += 1
        else:
            break
    return count


def swings(rows, reach=2):
    """قممٌ وقيعان: شمعةٌ أعلى (أو أدنى) ممّا حولها من الجانبين.

    وهذه هي المستوياتُ التي يراها المتداول على شاشته — لا رقمٌ
    نخترعه نحن."""
    tops, bottoms = [], []
    for i in range(reach, len(rows) - reach):
        near = range(i - reach, i + reach + 1)
        high = bar_at(rows[i], "high")
        low = bar_at(rows[i], "low")
        if all(high >= bar_at(rows[j], "high") for j in near):
            tops.append(high)
        if all(low <= bar_at(rows[j], "low") for j in near):
            bottoms.append(low)
    return tops, bottoms


def levels(marks, tol):
    """ما تقارب من القمم مستوىً واحد — وعددُ لمساته قوّتُه."""
    out = []
    for mark in sorted(marks):
        if out and abs(mark - out[-1]["at"]) <= tol:
            spot = out[-1]
            spot["touch"] += 1
            spot["at"] = round(
                (spot["at"] * (spot["touch"] - 1) + mark) / spot["touch"], 2)
        else:
            out.append({"at": round(mark, 2), "touch": 1})
    return out


LEVEL_FRAMES = (
    ("h1", "TIMEFRAME_H1", 16385, 120, "الساعة"),
    ("m15", "TIMEFRAME_M15", 15, 96, "ربع الساعة"),
    ("m5", "TIMEFRAME_M5", 5, 80, "خمس دقائق"),
)


def frame_levels(rows, buy, price):
    """مستوياتُ فريمٍ واحد، وموضعُ الدخول منها.

    البيعُ عند مقاومةٍ والشراءُ عند دعمٍ ارتدادٌ عن المستوى. والبيعُ
    تحت دعمٍ والشراءُ فوق مقاومةٍ اختراقٌ له. وهما طريقتان
    متعاكستان، فيُقاس أيُّهما يفعل."""
    out = {}
    if len(rows) < 12:
        return out
    closed = rows[:-1]
    spans = [bar_at(b, "high") - bar_at(b, "low") for b in closed]
    width = sum(spans) / len(spans) if spans else 1.0
    # سماحيةٌ تتبع مدى الشمعة، لكن لها سقف: على فريم الساعة في
    # الذهب بلغت ±8.32 درجة، فصار «عند المستوى» يعني «في المنطقة»
    # وقال التقريرُ 88% وهي لا تعني شيئاً. وبسقفِ درجةٍ ونصفٍ
    # صارت 16% — وهذا هو الواقع.
    tol = min(max(0.30, round(width * 0.35, 2)), TOL_CAP)
    out["tol"] = tol
    tops, bottoms = swings(closed)
    all_marks = levels(sorted(tops + bottoms), tol)
    out["cover"] = cover_of(all_marks, price - 30.0, price + 30.0, tol)
    above = [one for one in levels(tops, tol) if one["at"] >= price - tol]
    below = [one for one in levels(bottoms, tol) if one["at"] <= price + tol]
    res = min(above, key=lambda one: one["at"] - price) if above else None
    sup = max(below, key=lambda one: one["at"]) if below else None
    if res:
        out.update(res=res["at"], res_touch=res["touch"],
                   to_res=round(abs(res["at"] - price), 2))
    if sup:
        out.update(sup=sup["at"], sup_touch=sup["touch"],
                   to_sup=round(abs(price - sup["at"]), 2))

    # ★ المستوى الذي يواجهه: البائعُ يواجه المقاومة والمشتري الدعم
    face = sup if buy else res
    back = res if buy else sup
    if face:
        out["to_level"] = round(abs(face["at"] - price), 2)
        out["level_touch"] = face["touch"]
        out["at_level"] = out["to_level"] <= tol
    if back:
        gap = round(abs(back["at"] - price), 2)
        # اختراقٌ: تجاوز المستوى الذي خلفه ثم دخل في جهته
        passed = (price > back["at"]) if buy else (price < back["at"])
        out["broke"] = bool(passed and gap <= tol * 2)
    return out


OLD_BARS = 1500        # شمعةَ أربعِ ساعات ≈ سنةٌ من التاريخ
OLD_TOL = 2.0          # قُربٌ من مستوىً قديمٍ يُحسب وقوفاً عليه
OLD_SPAN = 60.0        # المدى الذي تُقارَن فيه المستويات حوله


def old_level_facts(symbol, price):
    """مستوياتٌ من سنةٍ مضت — ومعها خطُّ أساسٍ يمنع خداعَ النفس.

    على سنةٍ من التاريخ تكون المستوياتُ كثيفةً حتى يكاد كلُّ سعرٍ
    يقع قرب واحدٍ منها. فلو اكتفينا بـ«وقع على مستوى قديم» لقلنا
    نعم دائماً ولو كان دخولُه عشوائياً.

    فيُقاس معه المعتادُ حوله: كم لمسةً للمستوى الوسط في ستين درجة
    من سعره. فإن كان مستواه أقوى من المعتاد بوضوح، فهو يختاره.
    وإن ساواه، فالقربُ صدفةٌ لا اختيار."""
    rows = bars(symbol, getattr(mt5, "TIMEFRAME_H4", 16388), OLD_BARS)
    if len(rows) < 100:
        return {}
    tops, bottoms = swings(rows[:-1], reach=3)
    marks = levels(sorted(tops + bottoms), OLD_TOL)
    near = [one for one in marks if abs(one["at"] - price) <= OLD_SPAN]
    if not near:
        return {}
    mine = min(near, key=lambda one: abs(one["at"] - price))
    hits = sorted(one["touch"] for one in near)
    return {
        "old": mine["at"],
        "old_touch": mine["touch"],
        "to_old": round(abs(mine["at"] - price), 2),
        "at_old": abs(mine["at"] - price) <= OLD_TOL,
        # خطُّ الأساس: لمساتُ المستوى الوسط حوله، وكم مستوىً حوله
        "old_typical": hits[len(hits) // 2],
        "old_around": len(near),
    }


def cover_of(marks, lo, hi, tol):
    """كم من المدى يقع قرب مستوى؟ — خطُّ أساس المستويات.

    لو كان تسعون في المئة من المدى قربَ مستوى، فوقوعُ دخولاته
    قربَ مستوىً في تسعين في المئة منها لا يعني شيئاً. ولا يُعرف
    ذلك إلا بقياس التغطية."""
    if hi <= lo:
        return 0.0
    spans = []
    for one in marks:
        a = max(one["at"] - tol, lo)
        b = min(one["at"] + tol, hi)
        if b > a:
            spans.append((a, b))
    spans.sort()
    total, edge = 0.0, lo
    for a, b in spans:
        if b <= edge:
            continue
        total += b - max(a, edge)
        edge = max(edge, b)
    return round(total / (hi - lo), 3)


def level_facts(symbol, buy, price):
    """المستويات على ثلاثة فريمات — فأيُّها يحترمه يُعرف بالأرقام.

    مستوى الخمس دقائق غيرُ مستوى الساعة: قمّةٌ تُرى على فريمٍ لا
    تُرى على آخر. فلو قِست على فريمٍ واحد لقِست ما لا يراه هو.
    تُقاس الثلاثة معاً، ويقول التقريرُ بعد أسبوعٍ أيُّها أقربُ إلى
    دخولاته — ولا يُفترض فريمٌ سلفاً."""
    out = {}
    found = []
    for tag, name, number, count, _ in LEVEL_FRAMES:
        one = frame_levels(bars(symbol, getattr(mt5, name, number), count),
                           buy, price)
        if not one:
            continue
        found.append((tag, one))
        for key, value in one.items():
            out[f"{key}_{tag}"] = value
    if not found:
        return out
    on = [(tag, one) for tag, one in found if one.get("at_level")]
    # أقواها لمساتٍ إن وقع على مستوى، وإلا أقربُها ليُعرف كم بَعُد
    tag, one = (max(on, key=lambda p: p[1].get("level_touch", 0)) if on
                else min(found,
                         key=lambda p: p[1].get("to_level", 9e9)))
    out["frame"] = tag
    out["at_level"] = bool(on)
    for key in ("to_level", "level_touch", "broke", "tol", "cover",
                "res", "res_touch", "to_res",
                "sup", "sup_touch", "to_sup"):
        if key in one:
            out[key] = one[key]
    return out


# ─────────────────────────────────────────────
# المؤشّرات: حسابُها هنا لا استيرادُها — فلا تبعية
# ─────────────────────────────────────────────
def ema_of(values, span):
    """متوسطٌ أُسّي."""
    if len(values) < span:
        return 0.0
    weight = 2.0 / (span + 1)
    out = sum(values[:span]) / span
    for one in values[span:]:
        out = one * weight + out * (1 - weight)
    return round(out, 2)


def rsi_of(values, span=14):
    """قوّةٌ نسبية بطريقة وايلدر."""
    if len(values) < span + 1:
        return 0.0
    ups, downs = [], []
    for a, b in zip(values, values[1:]):
        step = b - a
        ups.append(max(step, 0.0))
        downs.append(max(-step, 0.0))
    up = sum(ups[:span]) / span
    down = sum(downs[:span]) / span
    for u, d in zip(ups[span:], downs[span:]):
        up = (up * (span - 1) + u) / span
        down = (down * (span - 1) + d) / span
    if down == 0:
        return 100.0
    return round(100 - 100 / (1 + up / down), 1)


def atr_of(rows, span=14):
    """مدىً حقيقيٌّ متوسط — به تُقاس الحركةُ بمقياس السوق نفسه."""
    if len(rows) < span + 1:
        return 0.0
    spans = []
    for prev, now in zip(rows, rows[1:]):
        high, low = bar_at(now, "high"), bar_at(now, "low")
        shut = bar_at(prev, "close")
        spans.append(max(high - low, abs(high - shut), abs(low - shut)))
    return round(sum(spans[-span:]) / span, 2)


def tool_facts(symbol, buy, price):
    """أين سعرُ دخوله من المتوسطات ومن القوّة النسبية."""
    out = {}
    for tag, name, number in (("m5", "TIMEFRAME_M5", 5),
                              ("m15", "TIMEFRAME_M15", 15)):
        rows = bars(symbol, getattr(mt5, name, number), 260)
        if len(rows) < 60:
            continue
        closed = rows[:-1]
        shuts = [bar_at(one, "close") for one in closed]
        for span in (20, 50, 200):
            if len(shuts) < span:
                continue
            line = ema_of(shuts, span)
            if not line:
                continue
            out[f"ema{span}_{tag}"] = line
            # «معه» أي فوق المتوسط في شراءٍ وتحته في بيع
            out[f"with_ema{span}_{tag}"] = (price > line) == buy
            out[f"to_ema{span}_{tag}"] = round(abs(price - line), 2)
        power = rsi_of(shuts)
        if power:
            out[f"rsi_{tag}"] = power
            out[f"rsi_hot_{tag}"] = power >= 70
            out[f"rsi_cold_{tag}"] = power <= 30
            # بيعٌ عند تشبّعٍ شرائي أو شراءٌ عند تشبّعٍ بيعي
            out[f"rsi_fade_{tag}"] = (power >= 70) != buy and (
                power >= 70 or power <= 30)
        width = atr_of(closed)
        if width:
            out[f"atr_{tag}"] = width
    return out


def impulse_facts(symbol, buy, price):
    """أجاء بعد حركةٍ حادّة؟ ومعها أم ضدّها؟

    صورُ M15 تُظهر تجمّعاتِه عند أطراف حركاتٍ حادّة. وهذا يُقاس:
    كم تحرّك السعرُ في الدقائق الخمس والخمسَ عشرةَ والثلاثين قبله،
    وكم ذلك بمقياس مدى الشمعة نفسه."""
    out = {}
    m1 = bars(symbol, getattr(mt5, "TIMEFRAME_M1", 1), 40)
    if len(m1) < 32:
        return out
    closed = m1[:-1]
    width = atr_of(closed)
    for span in (5, 15, 30):
        if len(closed) < span:
            continue
        start = bar_at(closed[-span], "open")
        move = round(price - start, 2)
        out[f"move{span}"] = move
        if abs(move) > 0.20:
            out[f"with_move{span}"] = (move > 0) == buy
    if width and "move5" in out:
        # قفزةٌ: حركةُ خمس دقائق مقيسةً بمدى الدقيقة المعتاد
        out["jump"] = round(abs(out["move5"]) / width, 2)
        out["after_jump"] = out["jump"] >= 3.0
    return out


def session_facts(symbol, price):
    """موضعُه من اليوم: فتحُه وقمّتُه وقاعُه، وقممُ أمسِ وقيعانُه."""
    out = {}
    d1 = bars(symbol, getattr(mt5, "TIMEFRAME_D1", 16408), 3)
    if len(d1) < 2:
        return out
    today, before = d1[-1], d1[-2]
    start = bar_at(today, "open")
    out["day_open"] = round(start, 2)
    out["from_open"] = round(price - start, 2)
    high, low = bar_at(today, "high"), bar_at(today, "low")
    if high > low:
        out["day_place"] = round((price - low) / (high - low) * 100)
        out["to_day_high"] = round(high - price, 2)
        out["to_day_low"] = round(price - low, 2)
    for name, key in (("high", "prev_high"), ("low", "prev_low"),
                      ("close", "prev_close")):
        mark = round(bar_at(before, name), 2)
        out[key] = mark
        out[f"to_{key}"] = round(abs(price - mark), 2)
    out["near_prev"] = min(out.get("to_prev_high", 999),
                           out.get("to_prev_low", 999),
                           out.get("to_prev_close", 999)) <= 2.0
    return out


def entry_facts(symbol, buy, price):
    """ماذا كان السوق يفعل لحظةَ دخوله.

    وقائعُ تُقاس ولا تُفسَّر هنا: الشكلُ والاتجاهُ والموضعُ من المدى
    والساعةُ والفاصلُ عن السلّة السابقة. والتفسيرُ يأتي بعد أسبوع
    حين تُجمع، فما تكرّر في ثلاثة أرباع دخولاته استراتيجيةٌ لا
    صدفة."""
    mine = "up" if buy else "down"
    out = {"mine": mine, "price": round(price, 2),
           "hour": int(datetime.now().strftime("%H"))}
    m1 = bars(symbol, getattr(mt5, "TIMEFRAME_M1", 1), RANGE_BARS + 2)
    if m1:
        closed = m1[:-1]
        if closed:
            last = closed[-1]
            out["m1_shape"] = shape_of(last)
            way = bar_way(last)
            out["m1_way"] = way
            out["m1_with"] = (way == mine) if way else None
            out["m1_run"] = run_length(closed, way) if way else 0
            spans = [bar_at(b, "high") - bar_at(b, "low") for b in closed]
            out["m1_range"] = round(sum(spans) / len(spans), 2)
        tall = [bar_at(b, "high") for b in closed[-RANGE_BARS:]]
        deep = [bar_at(b, "low") for b in closed[-RANGE_BARS:]]
        if tall and deep and max(tall) > min(deep):
            span = max(tall) - min(deep)
            out["span"] = round(span, 2)
            # 100 = قمّةُ المدى · 0 = قاعُه
            out["place"] = round((price - min(deep)) / span * 100)
            out["new_high"] = bool(closed) and bar_at(
                closed[-1], "high") >= max(tall) - 0.01
            out["new_low"] = bool(closed) and bar_at(
                closed[-1], "low") <= min(deep) + 0.01
    m5 = bars(symbol, getattr(mt5, "TIMEFRAME_M5", 5), 3)
    if m5 and len(m5) >= 2:
        way = bar_way(m5[-2])
        out["m5_way"] = way
        out["m5_with"] = (way == mine) if way else None
    # الأرقامُ المستديرة: الدولارُ الصحيح وحده. ولو قِست إلى نصف
    # الدولار أيضاً لما بَعُد سعرٌ عن أقربها أكثر من 0.25 درجة —
    # فأيُّ عتبةٍ فوقها تتحقق دائماً، والقياسُ يصير فارغاً.
    out["to_round"] = round(abs(price - round(price)), 2)
    out["on_round"] = out["to_round"] <= ROUND_NEAR
    # وخطُّ أساسه معلومٌ بالحساب: المسافةُ موزَّعةٌ على نصف دولار
    out["round_chance"] = round(min(1.0, ROUND_NEAR * 2), 3)
    if _last_shut["at"]:
        out["since_last"] = round((time.time() - _last_shut["at"]) / 60, 1)
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        out["spread"] = round(float(tick.ask) - float(tick.bid), 2)
    try:
        out.update(level_facts(symbol, buy, price))
    except Exception:
        pass
    for more in (old_level_facts, tool_facts, impulse_facts,
                 session_facts):
        try:
            got = (more(symbol, price) if more in
                   (old_level_facts, session_facts)
                   else more(symbol, buy, price))
            out.update(got)
        except Exception:
            pass
    return out


def exit_reasons(row, price):
    """لماذا أغلقها؟ أسبابٌ مقروءةٌ من السوق لا من الظن.

    لا تُدّعى نيّةٌ: تُسجَّل الوقائع التي سبقت الخروج، ثم تُجمع عبر
    الصفقات. فإن تكرّر «شمعة الدقيقة انقلبت ضده» في تسعٍ من عشر،
    عُرف ما يُخرجه."""
    facts = candle_facts(row["symbol"], row["buy"])
    mine = facts.get("mine")
    why = []

    last = facts.get("m1_last")
    if last and last != mine:
        count = int(facts.get("m1_against") or 1)
        why.append("شمعة الدقيقة انقلبت ضده"
                   + (f" ({count} متتالية)" if count > 1 else ""))
    now_way = facts.get("m1_now")
    if now_way and now_way != mine:
        why.append("والشمعة الجارية ضده")
    if facts.get("m5_now") and facts["m5_now"] != mine:
        why.append("وشمعة الخمس دقائق ضده")

    # القمّة: أخرج عندها أم بعد تراجعٍ عنها؟
    peak = float(row.get("best") or 0.0)
    took = gain(row["buy"], row["open_price"], price)
    back = round(peak - took, 2)
    if peak > 0 and back <= PEAK_NEAR:
        why.append("خرج عند قمّة الحركة")
    elif back > PEAK_NEAR:
        why.append("تراجع عن قمّته قبل الخروج"
                   f" ({back:g} درجة)")

    if not why:
        why.append("بلا إشارةٍ ظاهرة في الشموع")
    return why, facts, back


# ─────────────────────────────────────────────
# السلّة: ما فُتح معاً يُقرأ معاً
# ─────────────────────────────────────────────
def basket_for(row):
    """سلّةُ هذه الصفقة: ما فُتح باتجاهها على رمزها خلال ثوانٍ.

    صاحبُ الحساب يفتح أربعاً إلى عشر صفقاتٍ في الثانية نفسها ثم
    يغلقها كلها معاً. فتقريرٌ لكل صفقةٍ على حدة عشرُ رسائل عن حدثٍ
    واحد — والسلّة هي الحدث."""
    for key, basket in _baskets.items():
        if basket["shut"]:
            continue
        if (basket["symbol"], basket["buy"]) != (row["symbol"], row["buy"]):
            continue
        if abs(row["open_at"] - basket["last_open"]) <= BASKET_GAP:
            basket["last_open"] = max(basket["last_open"], row["open_at"])
            return key
    key = f"{row['symbol']}-{'B' if row['buy'] else 'S'}-{row['ticket']}"
    _baskets[key] = {
        "key": key, "symbol": row["symbol"], "buy": row["buy"],
        "opened": row["open_at"], "last_open": row["open_at"],
        "shut": False,
    }
    return key


# ─────────────────────────────────────────────
# فتحٌ · متابعة · إغلاق
# ─────────────────────────────────────────────
def on_open(position, bid, ask):
    """صفقةٌ جديدة ظهرت على الحساب."""
    buy = int(position.type) == 0
    row = {
        "ticket": int(position.ticket),
        "symbol": str(position.symbol),
        "buy": buy,
        "lot": float(position.volume),
        "open_at": float(position.time),
        "open_price": round(float(position.price_open), 2),
        "sl": round(float(position.sl or 0.0), 2),
        "tp": round(float(position.tp or 0.0), 2),
        "sl_first": round(float(position.sl or 0.0), 2),
        "tp_first": round(float(position.tp or 0.0), 2),
        "moves": [], "best": 0.0, "worst": 0.0, "best_at": "",
        "hit_tp": "", "hit_sl": "", "state": "مفتوحة",
    }
    row["basket"] = basket_for(row)
    spot = _baskets[row["basket"]]
    if "entry" not in spot:
        spot["entry"] = entry_facts(row["symbol"], buy, row["open_price"])
        paper_open(row["symbol"], buy, bid, ask)
        seen = spot["entry"]
        log(f"دخول سلّة {row['basket']}: "
            f"شمعة {seen.get('m1_shape', '؟')} · "
            f"{'معه' if seen.get('m1_with') else 'ضده'} · "
            f"موضعه {seen.get('place', '؟')}% من المدى")
    _rows[row["ticket"]] = row
    log(f"فتح #{row['ticket']} {'شراء' if buy else 'بيع'} {row['lot']:g} "
        f"عند {row['open_price']:g} · وقف {row['sl']:g} · "
        f"هدف {row['tp']:g}")
    touch(row, bid, ask)
    return row


def touch(row, bid, ask):
    """نبضةٌ على صفقةٍ مفتوحة: أقصى ربحٍ وخسارة، وبلوغُ الرقمين."""
    price = shut_price(row["buy"], bid, ask)
    move = gain(row["buy"], row["open_price"], price)
    if move > row["best"]:
        row["best"] = move
        row["best_at"] = stamp()
    if move < row["worst"]:
        row["worst"] = move
    if not row["hit_tp"] and reached(row["buy"], price, row["tp"]):
        row["hit_tp"] = stamp()
        log(f"#{row['ticket']} بلغ هدفه {row['tp']:g}")
    if not row["hit_sl"] and struck(row["buy"], price, row["sl"]):
        row["hit_sl"] = stamp()
        log(f"#{row['ticket']} بلغ وقفه {row['sl']:g}")


def watch_moves(row, position):
    """تغييرُ الوقف أو الهدف بعد الفتح يُسجَّل بوقته."""
    sl = round(float(position.sl or 0.0), 2)
    tp = round(float(position.tp or 0.0), 2)
    if sl == row["sl"] and tp == row["tp"]:
        return
    row["moves"].append({"at": stamp(), "sl": sl, "tp": tp,
                         "was_sl": row["sl"], "was_tp": row["tp"]})
    log(f"#{row['ticket']} نُقل: وقف {row['sl']:g}→{sl:g} · "
        f"هدف {row['tp']:g}→{tp:g}")
    row["sl"], row["tp"] = sl, tp


def exit_info(ticket):
    """سعرُ الخروج وربحُه من سجلّ الصفقات."""
    try:
        deals = mt5.history_deals_get(position=ticket) or ()
    except Exception:
        deals = ()
    out = [d for d in deals if int(getattr(d, "entry", 0)) == 1]
    if not out:
        return 0.0, 0.0, 0.0
    price = round(float(getattr(out[-1], "price", 0.0) or 0.0), 2)
    money = round(sum(float(getattr(d, "profit", 0.0) or 0.0)
                      + float(getattr(d, "swap", 0.0) or 0.0)
                      + float(getattr(d, "commission", 0.0) or 0.0)
                      for d in out), 2)
    when = float(getattr(out[-1], "time", 0.0) or 0.0)
    return price, money, when


def why_shut(row, price):
    """بأيّ شيءٍ خرجت: هدفُها أم وقفُها أم يدُه."""
    tp, sl = row["tp"], row["sl"]
    if tp and abs(price - tp) <= NEAR:
        return "بلغت هدفها"
    if sl and abs(price - sl) <= NEAR:
        return "ضُرب وقفها"
    if tp and not reached(row["buy"], price, tp):
        return "أغلقها بيده قبل الهدف"
    return "أغلقها بيده"


def on_shut(row, bid, ask):
    """صفقةٌ اختفت من الحساب: تُحسم ويُقرأ سببُها من السوق."""
    price, money, when = exit_info(row["ticket"])
    if not price:
        price = shut_price(row["buy"], bid, ask)
    row["shut_price"] = price
    row["shut_at"] = stamp(when) if when else stamp()
    row["points"] = gain(row["buy"], row["open_price"], price)
    row["money"] = money
    row["held"] = round((when or time.time()) - row["open_at"], 1)
    row["why"] = why_shut(row, price)
    row["state"] = "مُغلقة"
    log(f"إغلاق #{row['ticket']} عند {price:g} · {row['points']:+.2f} درجة "
        f"({money:+.2f}$) · {row['why']} · بعد {row['held']:g} ثانية")
    return row


# ─────────────────────────────────────────────
# تقرير السلّة
# ─────────────────────────────────────────────
def basket_rows(key):
    return [r for r in _rows.values() if r.get("basket") == key]


def first_target(rows):
    """أقربُ هدفٍ تركه — هو أولُ ما كان السعر سيبلغه."""
    entry = rows[0]["open_price"]
    marks = [r["tp"] for r in rows if r["tp"]]
    return min(marks, key=lambda t: abs(t - entry)) if marks else 0.0


def basket_report(key, reasons, seen):
    """تقريرُ سلّةٍ أُغلقت كاملةً — رسالةٌ واحدة عن الحدث كله."""
    rows = sorted(basket_rows(key), key=lambda r: r["ticket"])
    if not rows:
        return ""
    one = rows[0]
    side = "شراء" if one["buy"] else "بيع"
    lots = round(sum(r["lot"] for r in rows), 2)
    money = round(sum(r.get("money") or 0.0 for r in rows), 2)
    pts = [r["points"] for r in rows]
    held = max(r.get("held") or 0 for r in rows)
    opens = [r["open_price"] for r in rows]
    shuts = [r["shut_price"] for r in rows]
    tps = sorted({r["tp"] for r in rows if r["tp"]})
    sls = sorted({r["sl"] for r in rows if r["sl"]})
    moved = sum(len(r["moves"]) for r in rows)
    whys = {}
    for r in rows:
        whys[r["why"]] = whys.get(r["why"], 0) + 1

    def span(values):
        lo, hi = min(values), max(values)
        return f"{lo:g}" + (f"–{hi:g}" if hi != lo else "")

    out = [f"📋 <b>سلّة أُغلقت — {one['symbol']}</b>\n\n",
           f"{side} <b>{len(rows)}</b> صفقة · {lots:g} لوت\n",
           f"الدخول {span(opens)} ← الخروج {span(shuts)}\n",
           "🛑 وقفه: " + (" · ".join(f"{s:g}" for s in sls)
                          if sls else "<b>بلا وقف</b>") + "\n",
           "🎯 هدفه: " + (" · ".join(f"{t:g}" for t in tps)
                          if tps else "<b>بلا هدف</b>") + "\n"]
    if moved:
        out.append(f"✏️ نقل وقفه أو هدفه {times(moved)}\n")
    out.append(f"⏱️ بقيت <b>{held:g}</b> ثانية\n\n")

    for why, count in sorted(whys.items(), key=lambda kv: -kv[1]):
        mark = ("🎯" if why == "بلغت هدفها" else
                "🛑" if why == "ضُرب وقفها" else "✋")
        out.append(f"{mark} {why} — {times(count)}\n")

    out.append(f"\n{'🟢' if money >= 0 else '🔴'} <b>{money:+.2f}$</b> · "
               f"{min(pts):+.2f} إلى {max(pts):+.2f} درجة\n")
    out.append(f"📈 أقصى ربحٍ مرّ بها {max(r['best'] for r in rows):+.2f} "
               "درجة\n")
    out.append(f"📉 وأقصى عكسٍ {min(r['worst'] for r in rows):+.2f} درجة\n")

    # ★ لماذا أغلقها — وقائعُ اللحظة، ثم تكرارُها عبر الصفقات
    if reasons:
        out.append("\n🔍 <b>لماذا أغلقها — ما كان يفعله السوق:</b>\n")
        for one_why in reasons:
            count = int(seen.get(one_why.split(" (")[0], 0))
            total = int(seen.get("_سلال", 0))
            share = (f"  ← تكرّر {int(count)} من {total}"
                     if total > 1 and count > 1 else "")
            out.append(f"   • {one_why}{share}\n")

    early = [r for r in rows if "قبل الهدف" in r["why"]]
    if early:
        mark = first_target(early)
        away = round(abs(mark - early[0]["shut_price"]), 2)
        out.append(f"\n🎯 <b>أغلقها قبل هدفه {mark:g}</b> — "
                   f"بقي عليه {away:g} درجة ({away * 10:.0f} نقطة)\n")
    out.append(f"\n👁️ والعينُ على السعر {WINDOW_MIN:g} دقيقة — "
               "سأخبرك ماذا جرى بعد خروجه.")
    return "".join(out)


def shut_basket(key):
    """تُحسم السلّة: تقريرٌ واحد، ثم تبقى العينُ على ما بعدها."""
    basket = _baskets.get(key)
    rows = basket_rows(key)
    if not basket or basket["shut"] or not rows:
        return
    if any(r["state"] == "مفتوحة" for r in rows):
        return
    basket["shut"] = True
    one = sorted(rows, key=lambda r: r["ticket"])[0]
    reasons, facts, back = exit_reasons(one, one["shut_price"])
    seen = tally("why", [w.split(" (")[0] for w in reasons] + ["_سلال"])
    text = basket_report(key, reasons, seen)
    if text:
        say(text)
    purse = mt5.account_info()
    balance = round(float(getattr(purse, "balance", 0.0) or 0.0), 2)
    money = round(sum(r.get("money") or 0.0 for r in rows), 2)
    keep("baskets", {"basket": key, "at": stamp(), "why": reasons,
                     "candles": facts, "off_peak": back,
                     "entry": basket.get("entry") or {},
                     "dd": round(float(basket.get("dd", 0.0)), 2),
                     "peak": round(float(basket.get("peak", 0.0)), 2),
                     "balance": balance,
                     "cut_pct": (round(money / balance * 100, 3)
                                 if balance else 0.0),
                     "peak_pct": (round(float(basket.get("peak", 0.0))
                                        / balance * 100, 3)
                                  if balance else 0.0),
                     "rows": [dict(r) for r in
                              sorted(rows, key=lambda r: r["ticket"])]})
    _last_shut["at"] = time.time()
    _after.append({
        "key": key, "symbol": one["symbol"], "buy": one["buy"],
        "tp": first_target(rows),
        "shut_price": one["shut_price"],
        "took": round(sum(r["points"] for r in rows) / len(rows), 2),
        "money": round(sum(r.get("money") or 0.0 for r in rows), 2),
        "count": len(rows), "lot": round(sum(r["lot"] for r in rows), 2),
        "from": stamp(), "at": time.time(),
        "best": 0.0, "worst": 0.0, "end": "", "why": "",
        "tp_hit": "", "tp_watch": bool(first_target(rows)),
    })
    for row in rows:
        _rows.pop(row["ticket"], None)


# ─────────────────────────────────────────────
# ما بعد الإغلاق: أترك ربحاً وراءه أم أنقذه خروجه؟
# ─────────────────────────────────────────────
def verdict_of(watch):
    """حكمٌ على الخروج بالأرقام لا بالرأي."""
    left, back = watch["best"], watch["worst"]
    if left >= 1.0 and left > abs(back):
        return "خرج مبكراً"
    if back <= -1.0 and abs(back) > left:
        return "خروجه أنقذه"
    return "خرج في وقته"


def after_word(watch, score):
    side = "شراء" if watch["buy"] else "بيع"
    left, back = watch["best"], watch["worst"]
    mark = {"خرج مبكراً": "😤", "خروجه أنقذه": "🛡️",
            "خرج في وقته": "⚖️"}.get(score, "⚖️")
    out = [f"👁️ <b>ما بعد الإغلاق — {watch['symbol']}</b>\n\n",
           f"{side} {times(watch['count'])} · {watch['lot']:g} لوت\n",
           f"خرج عند <b>{watch['shut_price']:g}</b> بـ "
           f"<b>{watch['took']:+.2f} درجة</b> ({watch['money']:+.2f}$)\n\n",
           f"<b>خلال {WINDOW_MIN:g} دقيقة بعد خروجه:</b>\n",
           f"📈 استمرّ في اتجاهه <b>{left:+.2f} درجة</b> "
           f"({left * 10:+.0f} نقطة)\n",
           f"📉 وعكس <b>{back:+.2f} درجة</b> ({back * 10:+.0f} نقطة)\n\n",
           f"{mark} <b>{score}</b>\n"]
    if score == "خرج مبكراً":
        more = round(left * watch["lot"] * 100, 2)
        out.append(f"   ترك <b>{left:g} درجة</b> وراءه — "
                   f"نحو <b>{more:+.2f}$</b> على حجمه\n")
    elif score == "خروجه أنقذه":
        saved = round(abs(back) * watch["lot"] * 100, 2)
        out.append(f"   لو بقي لعكس عليه نحو <b>{saved:.2f}$</b>\n")
    if watch["tp"]:
        out.append("🎯 هدفه المتروك "
                   + (f"<b>بلغه السوق</b> — {watch['tp_hit']}\n"
                      if watch["tp_hit"] else
                      f"{watch['tp']:g} — لم يبلغه بعد\n"))

    board = tally("verdict", [score, "_كل"])
    total = int(board.get("_كل", 0))
    if total >= 3:
        bank = add_up("verdict", "درجات_متروكة", max(left, 0.0))
        mean = round(float(bank.get("درجات_متروكة", 0)) / total, 2)
        out.append(f"\n📊 <b>حتى الآن ({total} سلّة):</b>\n")
        for name in ("خرج مبكراً", "خرج في وقته", "خروجه أنقذه"):
            got = int(board.get(name, 0))
            if got:
                out.append(f"   {name}: <b>{got}</b> "
                           f"({got * 100 // total}%)\n")
        out.append(f"   متوسط ما يتركه وراءه: <b>{mean:g} درجة</b>\n")
    else:
        add_up("verdict", "درجات_متروكة", max(left, 0.0))
    return "".join(out)


def after_scan(prices):
    """العينُ على ما بعد الخروج: نصفُ ساعةٍ للحكم، ويومٌ للهدف."""
    for watch in list(_after):
        pair = prices.get(watch["symbol"])
        if not pair:
            continue
        bid, ask = pair
        price = shut_price(watch["buy"], bid, ask)
        move = gain(watch["buy"], watch["shut_price"], price)
        if not watch["end"]:
            watch["best"] = max(watch["best"], move)
            watch["worst"] = min(watch["worst"], move)
        if (not watch["tp_hit"] and watch["tp"]
                and reached(watch["buy"], price, watch["tp"])):
            watch["tp_hit"] = stamp()
        age = time.time() - watch["at"]
        if not watch["end"] and age >= WINDOW_MIN * 60:
            watch["end"] = stamp()
            score = verdict_of(watch)
            watch["verdict"] = score
            say(after_word(watch, score))
            keep("after", dict(watch))
            if not (watch["tp"] and not watch["tp_hit"]):
                _after.remove(watch)
            continue
        # ★ هدفٌ بلغه السوق بعد نافذة الحكم: سطرٌ واحد ثم ينتهي
        if watch["end"] and watch["tp_hit"]:
            left = round(abs(watch["tp"] - watch["shut_price"]), 2)
            say(f"🎯 <b>هدفه المتروك بلغه السوق</b> — "
                f"{watch['symbol']}\n\n"
                f"خرج عند {watch['shut_price']:g} وهدفُه "
                f"{watch['tp']:g}\n"
                f"بلغه في {watch['tp_hit']}\n"
                f"فتعجّلُه كلّفه <b>{left:g} درجة</b> "
                f"({left * 10:.0f} نقطة)")
            keep("after", dict(watch))
            _after.remove(watch)
        elif watch["end"] and age >= AFTER_HOURS * 3600:
            keep("after", dict(watch))
            _after.remove(watch)


# ─────────────────────────────────────────────
# تقرير الأسبوع: هل له استراتيجية؟
# ─────────────────────────────────────────────
def read_baskets():
    """كلُّ ما حُفظ من سلال، من كل أيام السجلّ."""
    out = []
    try:
        names = sorted(os.listdir(STORE))
    except Exception:
        return out
    for name in names:
        if not (name.startswith("baskets-") and name.endswith(".jsonl")):
            continue
        try:
            with open(os.path.join(STORE, name), encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        except Exception:
            continue
    return out


def share(count, total):
    return f"{count} من {total} ({count * 100 // total}%)" if total else "-"


def stands_out(count, total, floor=70):
    """نمطٌ لا صدفة: ثلاثةُ أرباعٍ فأكثر، وعلى خمسِ سلالٍ فأكثر."""
    return total >= 5 and count * 100 // total >= floor


def group(items):
    out = {}
    for one in items:
        out[one] = out.get(one, 0) + 1
    return sorted(out.items(), key=lambda kv: -kv[1])


def report_text():
    """تقريرُ الأسبوع: ما تكرّر في دخولاته وخروجه — وما لم يتكرّر.

    لا يُقال «استراتيجيته كذا» من سلّةٍ أو سلّتين. ما بلغ ثلاثةَ
    أرباع دخولاته على خمسٍ فأكثر يُعرض نمطاً، وما دونه يُعرض عدداً
    ولا يُسمّى نمطاً."""
    rows = read_baskets()
    if not rows:
        return "📊 لا سلالَ مسجّلةً بعد."
    total = len(rows)
    days = len({str(r.get("at", ""))[:10] for r in rows if r.get("at")})
    out = [f"📊 <b>تحليل الحساب المراقَب</b>\n\n",
           f"{total} سلّة في {days} يوم\n\n"]

    def entries(key):
        return [r["entry"][key] for r in rows
                if isinstance(r.get("entry"), dict)
                and r["entry"].get(key) is not None]

    # ★ الاتجاه
    ways = [("شراء" if r.get("entry", {}).get("mine") == "up" else "بيع")
            for r in rows if r.get("entry", {}).get("mine")]
    if ways:
        out.append("<b>الاتجاه</b>\n")
        for name, count in group(ways):
            out.append(f"   {name}: {share(count, len(ways))}\n")
        out.append("\n")

    # ★ شمعةُ الدقيقة قبل دخوله
    withs = entries("m1_with")
    if withs:
        against = sum(1 for one in withs if one is False)
        out.append("🕯️ <b>شمعة الدقيقة قبل دخوله</b>\n")
        out.append(f"   عكس اتجاه صفقته: {share(against, len(withs))}\n")
        out.append(f"   مع اتجاهها: "
                   f"{share(len(withs) - against, len(withs))}\n")
        if stands_out(against, len(withs)):
            out.append("   ← <b>يدخل عكس الشمعة — ارتداد لا استمرار</b>\n")
        elif stands_out(len(withs) - against, len(withs)):
            out.append("   ← <b>يدخل مع الشمعة — استمرارٌ لا ارتداد</b>\n")
        out.append("\n")

    # ★ شكلُ الشمعة
    shapes = entries("m1_shape")
    if shapes:
        out.append("🔎 <b>شكل الشمعة قبل دخوله</b>\n")
        for name, count in group(shapes)[:4]:
            out.append(f"   {name}: {share(count, len(shapes))}\n")
        top, count = group(shapes)[0]
        if stands_out(count, len(shapes), 60):
            out.append(f"   ← <b>أكثرُ دخولاته بعد «{top}»</b>\n")
        out.append("\n")

    # ★ عددُ الشموع المتتالية
    runs = entries("m1_run")
    if runs:
        out.append("📐 <b>شموعٌ متتالية قبل دخوله</b>\n")
        for name, count in group(runs)[:4]:
            out.append(f"   {name} شمعة: {share(count, len(runs))}\n")
        out.append(f"   المتوسط: "
                   f"<b>{sum(runs) / len(runs):.1f}</b> شمعة\n\n")

    # ★ موضعُه من المدى
    place = entries("place")
    if place:
        high = sum(1 for one in place if one >= 70)
        low = sum(1 for one in place if one <= 30)
        out.append(f"📏 <b>موضع دخوله من مدى {RANGE_BARS} شمعة</b>\n")
        out.append(f"   أعلى المدى: {share(high, len(place))}\n")
        out.append(f"   أسفل المدى: {share(low, len(place))}\n")
        out.append(f"   المتوسط: <b>{sum(place) / len(place):.0f}%</b>\n")
        if stands_out(high, len(place), 60):
            out.append("   ← <b>يدخل عند القمم</b>\n")
        elif stands_out(low, len(place), 60):
            out.append("   ← <b>يدخل عند القيعان</b>\n")
        out.append("\n")

    # ★ المقاومةُ والدعم — وهذا ما سأله صاحبُ الحساب بعينه
    faced = entries("at_level")
    if faced:
        on = sum(1 for one in faced if one)
        out.append("🧱 <b>المستويات — مقاومةٌ ودعم</b>\n")
        out.append(f"   دخل عند المستوى الذي يواجهه: "
                   f"{share(on, len(faced))}\n")
        gaps = entries("to_level")
        if gaps:
            out.append(f"   متوسط بُعده عنه: "
                       f"<b>{sum(gaps) / len(gaps):.2f} درجة</b>\n")
        hits = entries("level_touch")
        if hits:
            out.append(f"   ومتوسط لمسات المستوى: "
                       f"<b>{sum(hits) / len(hits):.1f}</b>\n")
        # ★ خطُّ الأساس: كم من المدى أصلاً قربَ مستوى؟ فلو كان
        # معظمُه كذلك لم يكن وقوعُه قربَه اختياراً.
        cover = entries("cover")
        base = sum(cover) / len(cover) if cover else 0.0
        if cover:
            out.append(f"   والمعتاد أن يقع قربَ مستوى: "
                       f"<b>{base * 100:.0f}%</b> من المدى\n")
        share_on = on / len(faced)
        if stands_out(on, len(faced)) and share_on >= base + 0.20:
            ways = [r.get("entry", {}).get("mine") for r in rows]
            sells = sum(1 for one in ways if one == "down")
            what = ("<b>يبيع عند المقاومة</b>"
                    if sells > len(ways) / 2 else
                    "<b>يشتري عند الدعم</b>")
            out.append(f"   ← {what} — ارتدادٌ عن المستوى\n")
        elif stands_out(on, len(faced)):
            out.append("   ← لكنّ المستوياتِ كثيفةٌ هنا، فالوقوعُ "
                       "قربَها <b>صدفةٌ لا اختيار</b>\n")
        # ★ وعلى أيّ فريم؟ مستوى الساعة غيرُ مستوى الخمس دقائق
        picks = []
        for tag, _n, _v, _c, name in LEVEL_FRAMES:
            got = entries(f"at_level_{tag}")
            if got:
                yes = sum(1 for one in got if one)
                picks.append((yes, len(got), name))
        if picks:
            out.append("   وعلى أيّ فريم:\n")
            for yes, many, name in sorted(picks, key=lambda p: -p[0]):
                out.append(f"      {name}: {share(yes, many)}\n")
            top = max(picks, key=lambda p: p[0])
            rest = [p for p in picks if p is not top]
            if (stands_out(top[0], top[1], 60)
                    and all(top[0] > p[0] for p in rest)):
                out.append(f"   ← <b>مستوياتُ {top[2]} أقربُ إلى "
                           "دخولاته</b>\n")
        broke = entries("broke")
        if broke:
            did = sum(1 for one in broke if one)
            out.append(f"   ومع اختراق المستوى: "
                       f"{share(did, len(broke))}\n")
            if stands_out(did, len(broke)):
                out.append("   ← <b>يدخل مع الاختراق لا مع الارتداد</b>\n")
        out.append("\n")

    # ★ مستوياتُ سنةٍ مضت — ولا تُصدَّق إلا بخطّ أساسها
    olds = entries("at_old")
    if olds:
        on = sum(1 for one in olds if one)
        out.append("🏛️ <b>مستوياتٌ قديمة (أربع ساعات — سنة)</b>\n")
        out.append(f"   دخل على مستوىً قديم: {share(on, len(olds))}\n")
        his = entries("old_touch")
        usual = entries("old_typical")
        if his and usual:
            mine = sum(his) / len(his)
            norm = sum(usual) / len(usual)
            out.append(f"   لمساتُ مستواه: <b>{mine:.1f}</b> في المتوسط\n")
            out.append(f"   ولمساتُ المستوى المعتاد حوله: "
                       f"<b>{norm:.1f}</b>\n")
            # ★ القربُ وحده لا يكفي: لا بدّ أن يكون مستواه أقوى
            if stands_out(on, len(olds)) and mine >= norm * 1.5:
                out.append("   ← <b>يختار مستوياتٍ أقوى من "
                           "المعتاد</b>\n")
            elif stands_out(on, len(olds)):
                out.append("   ← قريبٌ من مستوىً قديم، لكن مستواه "
                           "كالمعتاد — <b>قربٌ لا اختيار</b>\n")
        gaps = entries("to_old")
        if gaps:
            out.append(f"   متوسط بُعده عنه: "
                       f"<b>{sum(gaps) / len(gaps):.2f} درجة</b>\n")
        out.append("\n")

    # ★ الأرقام المستديرة
    rounds = entries("on_round")
    if rounds:
        on = sum(1 for one in rounds if one)
        odds = entries("round_chance")
        base = (sum(odds) / len(odds)) if odds else ROUND_NEAR * 2
        out.append("🔢 <b>الأرقام المستديرة</b>\n")
        out.append(f"   دخل على بُعد {ROUND_NEAR:g} درجة أو أقل من "
                   f"دولارٍ صحيح: {share(on, len(rounds))}\n")
        out.append(f"   والصدفةُ وحدها تضع: <b>{base * 100:.0f}%</b>\n")
        if stands_out(on, len(rounds)) and on / len(rounds) >= base + 0.20:
            out.append("   ← <b>يدخل على الأرقام المستديرة</b>\n")
        elif stands_out(on, len(rounds)):
            out.append("   ← لكنّه ليس أكثرَ ممّا تعطيه الصدفة\n")
        out.append("\n")

    # ★ الساعات
    hours = entries("hour")
    if hours:
        out.append("⏰ <b>ساعاتُ دخوله</b>\n")
        for name, count in group(hours)[:5]:
            out.append(f"   {int(name):02d}:00 — {share(count, len(hours))}"
                       "\n")
        out.append("\n")

    # ★ المؤشّرات: أين سعرُه منها
    out.append("📉 <b>المتوسطات والقوّة النسبية</b>\n")
    showed = False
    for tag, name in (("m5", "خمس دقائق"), ("m15", "ربع الساعة")):
        for span in (20, 50, 200):
            got = entries(f"with_ema{span}_{tag}")
            if len(got) < 5:
                continue
            yes = sum(1 for one in got if one)
            line = (f"   EMA{span} ({name}): دخل في جهته "
                    f"{share(yes, len(got))}")
            if stands_out(yes, len(got)):
                line += "  ← <b>مع المتوسط</b>"
            elif stands_out(len(got) - yes, len(got)):
                line += "  ← <b>عكس المتوسط</b>"
            out.append(line + "\n")
            showed = True
        power = entries(f"rsi_{tag}")
        if power:
            out.append(f"   RSI ({name}): المتوسط "
                       f"<b>{sum(power) / len(power):.0f}</b>\n")
            fade = entries(f"rsi_fade_{tag}")
            if fade:
                yes = sum(1 for one in fade if one)
                out.append(f"      ودخل عكس التشبّع: "
                           f"{share(yes, len(fade))}\n")
            showed = True
    if not showed:
        out.pop()
    else:
        out.append("\n")

    # ★ الحركةُ قبله: أينضمّ إلى اندفاعٍ أم يقف أمامه؟
    out.append("⚡ <b>الحركة قبل دخوله</b>\n")
    showed = False
    for span, name in ((5, "خمس دقائق"), (15, "ربع ساعة"),
                       (30, "نصف ساعة")):
        got = entries(f"with_move{span}")
        if len(got) < 5:
            continue
        yes = sum(1 for one in got if one)
        line = f"   حركة {name}: دخل في جهتها {share(yes, len(got))}"
        if stands_out(yes, len(got)):
            line += "  ← <b>ينضمّ إليها</b>"
        elif stands_out(len(got) - yes, len(got)):
            line += "  ← <b>يقف أمامها</b>"
        out.append(line + "\n")
        showed = True
    jumps = entries("after_jump")
    if jumps:
        yes = sum(1 for one in jumps if one)
        out.append(f"   بعد قفزةٍ حادّة (3× مدى الدقيقة): "
                   f"{share(yes, len(jumps))}\n")
        if stands_out(yes, len(jumps)):
            out.append("   ← <b>يدخل بعد القفزات</b>\n")
        showed = True
    if not showed:
        out.pop()
    else:
        out.append("\n")

    # ★ موضعُه من اليوم
    place = entries("day_place")
    if place:
        high = sum(1 for one in place if one >= 70)
        low = sum(1 for one in place if one <= 30)
        out.append("🌅 <b>موضعه من مدى اليوم</b>\n")
        out.append(f"   أعلى اليوم: {share(high, len(place))} · "
                   f"أسفله: {share(low, len(place))}\n")
        if stands_out(high, len(place), 60):
            out.append("   ← <b>يدخل قرب قمّة اليوم</b>\n")
        elif stands_out(low, len(place), 60):
            out.append("   ← <b>يدخل قرب قاع اليوم</b>\n")
        near = entries("near_prev")
        if near:
            yes = sum(1 for one in near if one)
            out.append(f"   وقرب قمّة أمسِ أو قاعها أو إغلاقها: "
                       f"{share(yes, len(near))}\n")
            if stands_out(yes, len(near)):
                out.append("   ← <b>يحترم أرقام أمس</b>\n")
        out.append("\n")

    # ★ وهل يُغلق عند مبلغٍ ثابت؟ — فرضيةُ السلّة تُختبر هنا
    cuts = [r.get("cut_pct") for r in rows
            if isinstance(r.get("cut_pct"), (int, float)) and r["cut_pct"]]
    dips = [r.get("dd") for r in rows
            if isinstance(r.get("dd"), (int, float))]
    if cuts:
        wins = sorted(one for one in cuts if one > 0)
        out.append("💰 <b>متى يُغلق — بالمال</b>\n")
        if wins:
            mid = wins[len(wins) // 2]
            tight = sum(1 for one in wins if abs(one - mid) <= mid * 0.35)
            out.append(f"   ربحُه من الرصيد: الوسيط "
                       f"<b>{mid:.2f}%</b>\n")
            out.append(f"   وضمن ثلث الوسيط: {share(tight, len(wins))}\n")
            if stands_out(tight, len(wins), 60):
                out.append("   ← <b>يُغلق عند مبلغٍ شبه ثابت — "
                           "سلّةٌ لا إشارة</b>\n")
        if dips:
            worst = min(dips)
            out.append(f"   وأسوأُ عويمٍ احتملته سلّة: "
                       f"<b>{worst:,.2f}$</b>\n")
        out.append("\n")

    # ★ ولو دخلنا معه بلا خروجٍ مبكر
    out.append(paper_text())

    # ★ ولماذا يخرج
    whys = []
    for row in rows:
        for one in (row.get("why") or []):
            whys.append(str(one).split(" (")[0])
    if whys:
        out.append("🚪 <b>ما يسبق خروجه</b>\n")
        for name, count in group(whys)[:5]:
            out.append(f"   {name}: {share(count, total)}\n")
        out.append("\n")

    # ★ وماذا جرى بعده
    board = {}
    try:
        with open(store_file("verdict.json"), encoding="utf-8") as fh:
            board = json.load(fh)
    except Exception:
        pass
    judged = int(board.get("_كل", 0))
    if judged:
        out.append(f"👁️ <b>ما بعد خروجه ({judged} سلّة)</b>\n")
        for name in ("خرج مبكراً", "خرج في وقته", "خروجه أنقذه"):
            got = int(board.get(name, 0))
            if got:
                out.append(f"   {name}: {share(got, judged)}\n")
        left = float(board.get("درجات_متروكة", 0))
        out.append(f"   متوسط ما يتركه وراءه: "
                   f"<b>{left / judged:.2f} درجة</b>\n\n")

    # ★ مسحٌ عام: ما تكرّر ولم أتوقّعه. لا يُفترض أنّي أحصيتُ كل
    # ما يُحصى — فكلُّ واقعةٍ نعم/لا تُمسح، وما بلغ ثلاثةَ أرباعٍ
    # يُعرض وإن لم يكن له بابٌ أعلاه.
    known = {"m1_with", "on_round", "at_level", "broke",
             "new_high", "new_low"}
    extra = []
    flags = set()
    for row in rows:
        for key, value in (row.get("entry") or {}).items():
            if isinstance(value, bool):
                flags.add(key)
    for key in sorted(flags - known):
        got = entries(key)
        yes = sum(1 for one in got if one)
        if stands_out(yes, len(got), 75):
            extra.append(f"   {key}: {share(yes, len(got))}\n")
        elif stands_out(len(got) - yes, len(got), 75):
            extra.append(f"   ليس {key}: "
                         f"{share(len(got) - yes, len(got))}\n")
    for key in ("new_high", "new_low"):
        got = entries(key)
        yes = sum(1 for one in got if one)
        if stands_out(yes, len(got), 60):
            what = ("قمّةً جديدة" if key == "new_high" else "قاعاً جديداً")
            extra.append(f"   دخل بعد أن صنع السعرُ {what}: "
                         f"{share(yes, len(got))}\n")
    if extra:
        out.append("🔬 <b>وممّا تكرّر أيضاً</b>\n")
        out += extra
        out.append("\n")

    if total < 5:
        out.append("⚠️ <b>أقلُّ من خمس سلال</b> — الأرقام تُقرأ ولا "
                   "يُبنى عليها حكم. انتظر أسبوعاً.")
    return "".join(out)


# ─────────────────────────────────────────────
# المحاكاة الورقية: لو دخلنا معه ولم نخرج مبكراً
# ─────────────────────────────────────────────
def paper_open(symbol, buy, bid, ask):
    """صفقةٌ ورقية عند كل دخولٍ له — بكل خطّةٍ معاً.

    دخولُه جيّدٌ وخروجُه مبكر: يأخذ نصفَ درجةٍ ويترك عشرين. فهذه
    تدخل معه بسعر السوق لحظةَ رؤيته، وتخرج بهدفٍ ووقفٍ لا بعجلة.
    وسعرُ الدخول هو ما كنّا سندفعه فعلاً — الطلبُ في الشراء
    والعرضُ في البيع — فالتأخيرُ والسبريد محسوبان لا مُتجاهلان."""
    price = ask if buy else bid
    for tp, sl in PAPER_PLANS:
        _paper.append({
            "plan": f"{tp}/{sl}", "tp": float(tp), "sl": float(sl),
            "symbol": symbol, "buy": buy,
            "open_price": round(float(price), 2),
            "at": time.time(), "from": stamp(),
            "best": 0.0, "worst": 0.0,
        })


def paper_track(prices):
    """نبضةُ الورق: ما بلغ هدفَه أو وقفَه يُحسم ويُسجَّل."""
    for one in list(_paper):
        pair = prices.get(one["symbol"])
        if not pair:
            continue
        bid, ask = pair
        price = shut_price(one["buy"], bid, ask)
        move = gain(one["buy"], one["open_price"], price)
        one["best"] = max(one["best"], move)
        one["worst"] = min(one["worst"], move)
        if move >= one["tp"]:
            why, points = "هدف", one["tp"]
        elif move <= -one["sl"]:
            why, points = "وقف", -one["sl"]
        elif time.time() - one["at"] >= PAPER_HOURS * 3600:
            why, points = "انقضت المدّة", move
        else:
            continue
        one["end"] = stamp()
        one["why"] = why
        one["points"] = round(points, 2)
        one["money"] = round(points * PAPER_LOT * 100, 2)
        keep("paper", one)
        tally("paper", [f"{one['plan']}|{why}", f"{one['plan']}|كل"])
        add_up("paper", f"{one['plan']}|مال", one["money"])
        _paper.remove(one)


def paper_text():
    """جدولُ الخطط: أيُّ هدفٍ ووقفٍ كان أفضل لو دخلنا معه."""
    try:
        with open(store_file("paper.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return ""
    lines = []
    for tp, sl in PAPER_PLANS:
        plan = f"{tp}/{sl}"
        total = int(data.get(f"{plan}|كل", 0))
        if not total:
            continue
        got = int(data.get(f"{plan}|هدف", 0))
        cut = int(data.get(f"{plan}|وقف", 0))
        late = int(data.get(f"{plan}|انقضت المدّة", 0))
        money = float(data.get(f"{plan}|مال", 0.0))
        lines.append((money, plan, got, cut, late, total))
    if not lines:
        return ""
    out = [f"🧪 <b>لو دخلتَ معه بصفقة {PAPER_LOT:g} ولم تخرج "
           "مبكراً</b>\n",
           f"   (محاكاةٌ على الورق — لا مال فيها)\n\n",
           f"   {'خطة':<9}{'هدف':>5}{'وقف':>6}{'مدّة':>6}"
           f"{'النتيجة':>12}\n"]
    for money, plan, got, cut, late, total in sorted(
            lines, key=lambda one: -one[0]):
        out.append(f"   {plan:<9}{got:>5}{cut:>6}{late:>6}"
                   f"{money:>+11.0f}$\n")
    money, plan, got, cut, late, total = max(lines,
                                             key=lambda one: one[0])
    if total >= 10:
        out.append(f"\n   ← أفضلها <b>هدف {plan.split('/')[0]} ووقف "
                   f"{plan.split('/')[1]}</b> — "
                   f"{got} من {total} ({got * 100 // total}%)\n")
    else:
        out.append(f"\n   ⚠️ <b>{total} صفقةً فقط</b> — "
                   "تُقرأ ولا يُبنى عليها حكم\n")
    return "".join(out) + "\n"


# ─────────────────────────────────────────────
# مراقبةُ الحساب نفسه
# ─────────────────────────────────────────────
def account_pulse():
    """لقطةُ حساب: الرصيد وحقوق الملكية والهامش والعويم.

    تُحفظ كل لقطة، ويُنبَّه عند ما يُنذر: عويمٌ ثقيل أو هامشٌ ضيّق
    أو رصيدٌ تغيّر بلا صفقةٍ أُغلقت (إيداعٌ أو سحب)."""
    now = time.time()
    if now - _acct["at"] < ACCOUNT_EVERY:
        return
    _acct["at"] = now
    info = mt5.account_info()
    if not info:
        return
    balance = round(float(info.balance), 2)
    equity = round(float(info.equity), 2)
    margin = round(float(getattr(info, "margin", 0.0) or 0.0), 2)
    free = round(float(getattr(info, "margin_free", 0.0) or 0.0), 2)
    level = round(float(getattr(info, "margin_level", 0.0) or 0.0), 2)
    live = mt5.positions_get() or ()
    lots = round(sum(float(p.volume) for p in live), 2)
    floating = round(equity - balance, 2)
    keep("account", {"at": stamp(), "balance": balance, "equity": equity,
                     "margin": margin, "free": free, "level": level,
                     "open": len(live), "lots": lots,
                     "floating": floating})

    was = _acct["balance"]
    _acct["balance"] = balance
    if was is not None and abs(balance - was) > 0.001 and not _rows:
        say(f"💰 <b>تغيّر الرصيد بلا صفقة</b>\n\n"
            f"{was:,.2f}$ ← <b>{balance:,.2f}$</b> "
            f"({balance - was:+,.2f}$)\n"
            "إيداعٌ أو سحبٌ على الأرجح.")

    if now - _acct["told"] < 600:
        return
    heavy = balance and floating < 0 and abs(floating) >= (
        balance * STRESS_FLOAT / 100.0)
    tight = bool(live) and 0 < level < STRESS_MARGIN
    if heavy or tight:
        _acct["told"] = now
        say("⚠️ <b>الحساب تحت ضغط</b>\n\n"
            f"الرصيد {balance:,.2f}$ · حقوق الملكية "
            f"<b>{equity:,.2f}$</b>\n"
            f"العويم <b>{floating:+,.2f}$</b>"
            + (f" — {abs(floating) / balance * 100:.1f}% من الرصيد\n"
               if balance else "\n")
            + f"مفتوحٌ الآن {len(live)} صفقة · {lots:g} لوت\n"
            + (f"مستوى الهامش <b>{level:.0f}%</b>\n" if level else ""))


# ─────────────────────────────────────────────
# النبضة
# ─────────────────────────────────────────────
def prices_for(names):
    out = {}
    for name in names:
        tick = mt5.symbol_info_tick(name)
        if tick:
            bid = round(float(tick.bid), 2)
            ask = round(float(tick.ask), 2)
            out[name] = (bid, ask)
            tail_push(name, bid, ask)
    return out


def scan():
    """نبضةٌ واحدة: ما فُتح يُسجَّل، وما بقي يُتابَع، وما اختفى يُحسم."""
    live = mt5.positions_get() or ()
    # ‎--symbol يَعِد بحصر المراقبة في رمز، فليحصرها فعلاً: وَعدٌ
    # يُطبع ولا يُنفَّذ أسوأ من ألّا يكون
    if _only["symbol"]:
        live = tuple(p for p in live
                     if str(p.symbol) == _only["symbol"])
    seen = {int(p.ticket): p for p in live}
    names = {str(p.symbol) for p in live}
    names |= {r["symbol"] for r in _rows.values()}
    names |= {w["symbol"] for w in _after}
    prices = prices_for(names)

    for ticket, position in seen.items():
        pair = prices.get(str(position.symbol))
        if not pair:
            continue
        row = _rows.get(ticket)
        if row is None:
            on_open(position, *pair)
            continue
        watch_moves(row, position)
        touch(row, *pair)

    # عويمُ كل سلّةٍ مفتوحة: كم احتملت قبل أن تُغلق، وكم بلغت.
    # به يُعرف أتُغلق عند مبلغٍ ثابت أم عند إشارةٍ في السوق.
    for key, basket in _baskets.items():
        if basket.get("shut"):
            continue
        pair = prices.get(basket["symbol"])
        if not pair:
            continue
        bid, ask = pair
        mine = [r for r in _rows.values()
                if r.get("basket") == key and r["state"] == "مفتوحة"]
        if not mine:
            continue
        money = round(sum(
            gain(r["buy"], r["open_price"],
                 shut_price(r["buy"], bid, ask)) * r["lot"] * 100
            for r in mine), 2)
        basket["dd"] = min(float(basket.get("dd", 0.0)), money)
        basket["peak"] = max(float(basket.get("peak", 0.0)), money)

    done = set()
    for ticket, row in list(_rows.items()):
        if ticket in seen or row["state"] != "مفتوحة":
            continue
        on_shut(row, *(prices.get(row["symbol"]) or (0.0, 0.0)))
        done.add(row["basket"])
    for key in done:
        shut_basket(key)

    after_scan(prices)
    paper_track(prices)
    account_pulse()


# ─────────────────────────────────────────────
# التشغيل
# ─────────────────────────────────────────────
def hello(account, balance, server, watched):
    return (
        f"👁️ <b>مرآةُ الحساب جاهزة</b> — نسخة {VERSION}\n\n"
        f"الحساب المراقَب: <b>#{account}</b> · {server}\n"
        f"الرصيد: <b>${balance:,.2f}</b>\n\n"
        "🔒 <b>تقرأ ولا تلمس</b> — لا تفتح صفقةً ولا تغلقها ولا "
        "تعدّل واحدة\n\n"
        "<b>عن كل سلّة تُغلق:</b>\n"
        "• كم صفقة وبأيّ حجم ومن أين إلى أين\n"
        "• أين وقفُه وهدفُه — وهل نقلهما\n"
        "• ولماذا خرج: بلغ هدفه · ضُرب وقفه · أم أغلقها بيده\n"
        "🔍 • وماذا كانت الشموع تفعل لحظةَ خروجه\n\n"
        f"👁️ <b>وبعد خروجه بـ {WINDOW_MIN:g} دقيقة:</b>\n"
        "   هل استمرّ السعر فترك ربحاً، أم انعكس فأنقذه خروجه\n"
        "   وحكمٌ يتراكم: «خرج مبكراً ٧ من ١٠» ومتوسطُ ما يتركه\n\n"
        "💰 ومراقبةٌ للحساب: الرصيد والعويم والهامش، وتنبيهٌ عند "
        "الضغط\n\n"
        + (f"📌 {watched}" if watched else ""))


def main():
    ap = argparse.ArgumentParser(
        description="مرآةُ حسابٍ آخر — تقرأ ولا تلمس")
    ap.add_argument("--account", type=int, default=0,
                    help="رقم الحساب المراقَب — يرفض البرنامج غيره")
    ap.add_argument("--mt5-path", default="",
                    help="مسار terminal64.exe للمنصّة المسجَّل فيها")
    ap.add_argument("--symbol", default="",
                    help="رمزٌ واحد إن أردت حصرَ المراقبة فيه")
    ap.add_argument("--poll", type=float, default=POLL,
                    help="ثانيةُ النبض")
    ap.add_argument("--report", action="store_true",
                    help="يقرأ ما سُجّل ويطبع تحليلَه — بلا اتصالٍ "
                         "بالمنصّة. شغّله بعد أسبوع")
    args = ap.parse_args()

    if args.report:
        text = report_text()
        print(text.replace("<b>", "").replace("</b>", ""))
        tg(text)
        return

    if not args.account:
        print("[MIRROR] ⛔ لا بدّ من --account: الحساب المراقَب")
        return

    # الرفضُ أولاً: قبل أيّ اتصال، لا سبيلَ لأمرٍ أن يخرج
    refuse_orders()

    kw = {"path": args.mt5_path} if args.mt5_path else {}
    if not mt5.initialize(**kw):
        print(f"[MT5] ❌ لم تُفتح المنصّة — {mt5.last_error()}")
        if args.mt5_path:
            print(f"      المسار: {args.mt5_path}")
        return
    info = mt5.account_info()
    if not info:
        print("[MT5] ❌ لا معلوماتِ حساب")
        return
    if int(info.login) != args.account:
        print(f"[GUARD] ⛔ المنصّة على الحساب {info.login} "
              f"والمطلوب {args.account}")
        print("        سجّل دخول المنصّة على الحساب المراقَب "
              "(كلمة المستثمر تكفي)")
        return

    _only["symbol"] = args.symbol.strip()
    watched = args.symbol or "كل الرموز"
    print(f"[MIRROR] ✅ نسخة {VERSION}")
    print(f"[GUARD]  ✅ الحساب {info.login} — {info.server}")
    print("[MIRROR] 🔒 تقرأ ولا تلمس: أمرُ التنفيذ مرفوضٌ أصلاً")
    print(f"[MIRROR] 👁️ تراقب: {watched} · نبضة {args.poll:g} ثانية")
    log(f"بدأت المراقبة — حساب {info.login} · {watched}")
    say(hello(info.login, float(info.balance), info.server, watched))

    print("[MIRROR] اضغط Ctrl+C للإيقاف.")
    try:
        while True:
            try:
                scan()
            except Exception as exc:
                print(f"[MIRROR] ⚠️ {exc}")
                log(f"خطأ في النبضة: {exc}")
            time.sleep(max(0.05, args.poll))
    except KeyboardInterrupt:
        print("\n[MIRROR] توقفت.")
        log("توقفت المراقبة")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
