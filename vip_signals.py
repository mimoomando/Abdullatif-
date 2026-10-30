"""vip_signals.py
────────────────
قراءة توصيات قناة بشرية تكتب بالعامية، رسالةً رسالة.

القناة لا ترسل التوصية في رسالة واحدة، بل تفرّقها:

    اجهز  →  بيع  →  الان  →  4004  →  ستوبك على 4007  →  هدفك 4000

فهذا الملف لا "يحلل رسالة" بل يترجمها إلى **فعل واحد** يفهمه البوت،
وعلى المستدعي أن يحتفظ بحالة الصفقة بين الرسائل.

ولا شيء هنا يلمس MT5 ولا تيليغرام: منطق خالص يُختبر وحده.
"""

import re

# ═════════════════════════════════════════════
# توحيد النص العربي
# ═════════════════════════════════════════════

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"

# الأرقام العربية-الهندية ← اللاتينية
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize(text):
    """يوحّد الحروف والأرقام ويُذيب المطّ.

    القناة تكتب «خروووججج» و«بقووة» و«حبايبي» — والمدّ عشوائي، فلا
    يستقيم البحث عن «خروج» إلا بعد ضغط الحرف المكرر إلى حرفين.
    نضغط إلى حرفين لا إلى حرف واحد كي لا نُفسد كلمات أصلها مشدّد.
    """
    s = (text or "").translate(_DIGITS)
    s = _TASHKEEL.sub("", s).replace(_TATWEEL, "")
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و")
    # الحروف وحدها تُضغط. لولا استثناء الأرقام لصارت 4000 ← 400
    # ولوُضع الهدف في مكان آخر تماماً.
    s = re.sub(r"([^\W\d_])\1{2,}", r"\1\1", s)   # خروووججج → خرووججج
    s = re.sub(r"[^\w\s$%.\-]", " ", s)            # الرموز والإيموجي
    return " ".join(s.split()).casefold()


def words(text):
    return normalize(text).split()


# ═════════════════════════════════════════════
# الأرقام الناقصة
# ═════════════════════════════════════════════

_NUM = re.compile(r"\d+(?:\.\d+)?")


def complete_price(partial, reference):
    """«ستوبك 96» والسعر 4002 → 3996، لا 4096.

    القناة تحذف المقدّمة وتكتب آخر رقمين أو ثلاثة. نبني كل الاحتمالات
    بإبدال آخر خانات السعر المرجعي، ونختار الأقرب إليه — لأن توصية
    حيّة لا تبعد مئات الدولارات عن السوق."""
    if partial is None or reference is None:
        return None
    text = str(partial)
    digits = len(text.split(".")[0])
    value = float(text)
    if digits >= 4:                 # رقم كامل، لا شيء يُكمَّل
        return value
    step = 10 ** digits
    base = int(float(reference) // step) * step
    best = None
    for shift in (-2, -1, 0, 1, 2):
        candidate = base + shift * step + value
        if candidate <= 0:
            continue
        if best is None or abs(candidate - reference) < abs(best - reference):
            best = candidate
    return best


def numbers_in(text, reference=None):
    """كل الأرقام في الرسالة، مكتملةً إن أُعطي سعر مرجعي."""
    out = []
    for raw in _NUM.findall(normalize(text)):
        value = complete_price(raw, reference) if reference else float(raw)
        if value is not None:
            out.append(value)
    return out


# ═════════════════════════════════════════════
# المفردات
# ═════════════════════════════════════════════

_BUY = ("شراء", "اشتري", "تشتري", "نشتري", "buy")
_SELL = ("بيع", "نبيع", "تبيع", "bيع", "sell")

# كلمات تُحوّل الأمر إلى كلام: شرط أو نية أو وصف
_NOT_COMMAND = ("رح", "لو", "اذا", "بامكانك", "يمكنك", "ممكن", "الي",
                "مناطق", "منطقه", "يعني", "بتقدر", "كان", "راح")

_OPEN_MAX_WORDS = 4        # أمر الفتح: أربع كلمات فأقل
_CLOSE_MAX_WORDS = 3       # أمر الإغلاق: ثلاث كلمات فأقل


# بادئات عربية تلتصق بالكلمة فتُفسد المطابقة: «لهدف» و«بستوبك» و«والهدف»
_PREFIXES = ("وال", "بال", "فال", "لل", "ال", "و", "ف", "ب", "ل")


def _bare(word):
    """يجرّد الكلمة من بادئاتها: «لهدف» → «هدف»."""
    for pre in _PREFIXES:
        if word.startswith(pre) and len(word) > len(pre) + 1:
            return word[len(pre):]
    return word


def _has(tokens, vocab):
    return any(w in vocab or _bare(w) in vocab for w in tokens)


def _starts_with(tokens, vocab):
    if not tokens:
        return False
    return tokens[0] in vocab or _bare(tokens[0]) in vocab


# ═════════════════════════════════════════════
# الترجمة: رسالة → فعل
# ═════════════════════════════════════════════
#
# الفعل قاموس فيه "action" وما يلزمه. والأفعال:
#
#   OPEN            فتح صفقة جديدة (direction)
#   SET_STOP        ستوب القناة يحلّ محل المؤقت (price)
#   SET_TP1         هدف أول (price)
#   SET_TP2         هدف ثانٍ (price)
#   BREAKEVEN       الوقف ينتقل إلى الدخول
#   CLOSE_HALF      يغلق نصف الصفقات وينقل وقف الباقي للدخول
#   CLOSE_ALL       يغلق كل المفتوح
#   CLOSE_NO_REOPEN يغلق ولا يفتح مجدداً حتى توصية جديدة
#   REENTRY_IF_HIT  يفتح فقط إن كان الوقف قد ضُرب (direction)
#   NONE            كلام لا فعل فيه
#
# وكل فعل يحمل "why" — سطر عربي يُطبع في السجل ويُرسل لصاحب الحساب،
# فلا يبقى قرار بلا تفسير.


def _action(name, why, **extra):
    out = {"action": name, "why": why}
    out.update(extra)
    return out


NONE = {"action": "NONE", "why": ""}


def interpret(text, reference_price=None, has_open_trade=False,
              stop_was_hit=False):
    """يترجم رسالة واحدة إلى فعل واحد.

    reference_price  سعر الذهب الآن — يُكمل به الأرقام الناقصة
    has_open_trade   هل للبوت صفقات مفتوحة الآن؟
    stop_was_hit     هل ضُرب وقف الصفقة السابقة؟ (لرسائل «لو ضربك»)
    """
    raw = (text or "").strip()
    if not raw:
        return NONE

    tok = words(raw)
    if not tok:
        return NONE
    joined = " ".join(tok)
    n = len(tok)

    # ── ١) الإغلاق أولاً: أسلم أن يُغلق قبل أن يُفتح ──
    # «انتهت» خبر بأن الصفقة انتهت عندهم، فنغلق ما بقي عندنا.
    if "انتهت" in tok:
        if "تفعل" in tok:          # انتهت لا تفعل
            return _action("CLOSE_NO_REOPEN",
                           "انتهت ولا تفتح مجدداً")
        return _action("CLOSE_ALL", "انتهت — يُغلق ما بقي مفتوحاً")

    # «خروج» بكل مدّاتها
    if any(w.startswith("خرو") for w in tok):
        return _action("CLOSE_ALL", "خروج")

    if _starts_with(tok, ("اغلق", "اقفل", "سكر")):
        if n <= _CLOSE_MAX_WORDS:
            return _action("CLOSE_ALL", f"أمر إغلاق: {joined}")
        # «اغلق 3 استمر بدخول 5» ليست أمر إغلاق بل إعادة دخول لمن فاته
        return _action("NONE",
                       f"فيها «اغلق» لكنها {n} كلمات — ليست أمر إغلاق")

    # ── ٢) حجز نصف الربح ──
    if "احجز" in tok and ("نص" in tok or "نصف" in tok):
        return _action("CLOSE_HALF", "احجز نص — يغلق النصف وينقل الوقف للدخول")

    # ── ٣) التأمين: الوقف إلى الدخول ──
    # «ستوب» و«دخول» معاً = تأمين، ولو حملت الجملة رقماً آخر.
    # «ترا في خبر بعد 10 دقايق يعني ستوبك دخولك» كانت تُقرأ ستوباً
    # عند 10 — والرقم فيها دقائق لا سعراً.
    if _has(tok, ("تامين", "امن")) or (
            _has(tok, ("ستوبك", "ستوب", "وقفك", "وقف"))
            and _has(tok, ("دخولك", "دخول"))):
        return _action("BREAKEVEN", "تأمين — الوقف إلى سعر الدخول")

    nums = numbers_in(raw, reference_price)

    # ── ٤) الهدف ──
    if _has(tok, ("هدفك", "هدف", "الهدف", "اهداف", "tp")):
        if not nums:
            return _action("NONE", "ذكر الهدف بلا رقم")
        second = _has(tok, ("ثاني", "ثانى", "الثاني", "2", "tp2"))
        return _action("SET_TP2" if second else "SET_TP1",
                       ("هدف ثانٍ" if second else "هدف أول") + f" {nums[0]:g}",
                       price=nums[0])

    # ── ٥) الستوب ──
    if _has(tok, ("ستوبك", "ستوب", "الستوب", "وقفك", "وقف", "sl")):
        if not nums:
            return _action("NONE", "ذكر الستوب بلا رقم")
        return _action("SET_STOP", f"ستوب القناة {nums[0]:g}", price=nums[0])

    # ── ٦) الدخول المشروط: «لو ضربك تشتري من 22» ──
    conditional = _has(tok, ("لو", "اذا")) and _has(tok, ("ضربك", "ضرب"))
    if conditional:
        direction = ("BUY" if _has(tok, _BUY)
                     else "SELL" if _has(tok, _SELL) else None)
        if not direction:
            return _action("NONE", "شرط بلا اتجاه")
        if not stop_was_hit:
            return _action("NONE", "شرط «لو ضربك» ولم يُضرب الوقف")
        if has_open_trade:
            return _action("NONE", "شرط «لو ضربك» وهناك صفقة مفتوحة")
        return _action("REENTRY_IF_HIT", f"الوقف ضُرب — إعادة دخول {direction}",
                       direction=direction)

    # ── ٧) التجديد: «جدد من 25» ──
    if _starts_with(tok, ("جدد", "جددد")):
        if has_open_trade:
            return _action("NONE", "تجديد وهناك صفقة مفتوحة")
        return _action("RENEW", "جدد — يفتح من جديد بنفس الاتجاه")

    # ── ٨) الفتح ──
    direction = ("BUY" if _starts_with(tok, _BUY)
                 else "SELL" if _starts_with(tok, _SELL) else None)
    if direction:
        if _has(tok, _NOT_COMMAND):
            return _action("NONE", f"تمهيد أو شرط لا أمر: {joined}")
        if n > _OPEN_MAX_WORDS:
            return _action("NONE", f"جملة من {n} كلمات — ليست أمر فتح")
        if has_open_trade:
            return _action("NONE", "أمر فتح وهناك صفقة مفتوحة — صفقة واحدة فقط")
        return _action("OPEN", f"أمر فتح {direction}: {joined}",
                       direction=direction)

    # كلمة الاتجاه في وسط الجملة: وصف لا أمر
    if _has(tok, _BUY) or _has(tok, _SELL):
        return _action("NONE", "كلمة الاتجاه داخل جملة — وصف لا أمر")

    return NONE
