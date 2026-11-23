"""قارئ قناة XAU Pro Operator.

صيغتها رسالةٌ واحدة مكتملة، بخلاف VEY التي تُفرّق التوصية على رسائل:

    XAUUSD Short ALERT 🚨
    🔻 Sell : 3854.00
    🛑 SL: 3866.00
    🎯 TP1: 3848 | TP2: 3841 | TP3: 3832.00

فلا حاجة إلى حفظ اتجاهٍ بين الرسائل، ولا إلى مهلةٍ يسقط بعدها. وهذا
يجعلها أدقّ في القياس: الدخول معلومٌ برقمه، والوقف كذلك، والأهداف
الثلاثة معلومة — فنعرف بعد كل توصية كم درجةً ربحت وكم خسرت بالضبط.

والنقطة عندهم عُشر الدولار: من 3854 إلى 3848 ستُّ درجات، وقد سمّوها
«60+PIPS».
"""
import re

# ─────────────────────────────────────────────
# التوحيد: تُحذف الزخارف ويبقى ما يُقرأ
# ─────────────────────────────────────────────
_STRIP = re.compile(r"[*_`~]+")
_SPACES = re.compile(r"[ \t ]+")


def normalize(text):
    """نصٌّ نظيفٌ بحروفٍ صغيرة، تُحفظ فيه الأسطر."""
    low = _STRIP.sub(" ", str(text or ""))
    low = low.replace("：", ":").replace("|", " | ")
    low = low.replace("\u2019", "'").replace("\u02bc", "'")
    low = _SPACES.sub(" ", low.lower())
    return "\n".join(line.strip() for line in low.splitlines()).strip()


_PRICE = r"\d{3,5}(?:\.\d{1,2})?"

# الاتجاه: من ترويسة التنبيه أو من سطر الدخول
_SHORT = re.compile(r"\b(?:short|sell)\b")
_LONG = re.compile(r"\b(?:long|buy)\b")

# سطر الدخول: «Sell : 3854.00» أو «Buy 3854»
_ENTRY = re.compile(rf"\b(?:sell|buy|short|long)\b[^0-9\n]{{0,12}}({_PRICE})")
# «SL: 3866.00» أو «S/L 3866» أو «stop loss 3866»
_SL = re.compile(rf"\b(?:sl|s\s*/\s*l|stop\s*loss|stoploss)\b"
                 rf"[^0-9\n]{{0,12}}({_PRICE})")
# «TP1: 3848» — يُلتقط رقم الهدف وسعره معاً
_TP = re.compile(rf"\btp\s*(\d)?\b[^0-9\n]{{0,12}}({_PRICE})")

# «TP same» — أهدافُ التوصية السابقة نفسها، لا أهدافَ جديدة
_SAME_TP = re.compile(r"\btps?\s*same\b|\bsame\s*tps?\b"
                      r"|\bsame\s*targets?\b|\bnafs\b")
# ما يصل بعد التوصية
_TP_HIT = re.compile(r"\btp\s*(\d)?\s*(?:hit|reached|done|✅)")
_SL_HIT = re.compile(r"\b(?:sl|stop\s*loss)\s*(?:hit|reached)"
                     r"|\bstopped\s*out\b")
_BE = re.compile(r"\b(?:sl|stop)\s*(?:to|at)\s*(?:be|b/e|entry|breakeven)\b"
                 r"|\bbreak\s*even\b|\bmove\s*(?:to\s*)?be\b"
                 r"|\brisk\s*free\b|\bsecure\s*(?:the\s*)?(?:trade|position)\b")
# «Close Buy All» و«Close All Sell» و«Close the trade» — وبينهما
# كلمةُ الاتجاه أحياناً، كما كتبوها يوم 18 نوفمبر
_CLOSE = re.compile(r"\bclose\s+(?:the\s+)?(?:buy|sell|long|short)?\s*"
                    r"(?:trade|position|all|it|now)\b"
                    r"|\bclose\s+all\b"
                    r"|\bexit\s+(?:the\s+)?(?:trade|position|now)\b"
                    r"|\bcancel\s+(?:the\s+)?(?:trade|signal|order)\b"
                    r"|\bbook\s+(?:the\s+)?profit\b")
# «Please don't close it» و«No closing yet» ليسا أمرَ إغلاق. والنفيُ
# يسبق الفعل بكلمةٍ أو كلمتين، فيُفتَّش عنه فيما قبله — وإغلاقٌ
# بالخطأ يُخرج صفقةً رابحة بأمرٍ لم يُعطَ.
_NO_CLOSE = re.compile(
    r"(?:\bdon'?t\b|\bdo\s+not\b|\bnever\b|\bnot\b|\bno\b"
    r"|\bavoid\b|\bwon'?t\b|\bwill\s+not\b|\bcan'?t\b"
    r"|\bcannot\b|\bwithout\b)"
    r"(?:\W+\w+){0,2}\W+clos")


def _action(name, why, **extra):
    out = {"action": name, "why": why}
    out.update(extra)
    return out


def interpret(text):
    """رسالةٌ واحدة → فعلٌ واحد. و«NONE» لما ليس أمراً."""
    raw = (text or "").strip()
    if not raw:
        return _action("NONE", "")
    low = normalize(raw)
    if not low:
        return _action("NONE", "")

    # ── ١) التوصية المكتملة: اتجاهٌ وسعرُ دخول ──
    entry = _ENTRY.search(low)
    if entry:
        # الترويسة أولى بالاتجاه من كلمةٍ عابرة في آخر الرسالة
        head = low.splitlines()[0] if low.splitlines() else low
        direction = None
        for scope in (head, low):
            if _SHORT.search(scope):
                direction = "SELL"
                break
            if _LONG.search(scope):
                direction = "BUY"
                break
        if direction:
            # رقمُ الهدف أولى من موضعه في النص: TP1 هو الأول وإن
            # كُتب بعد TP3. يوم 23 نوفمبر قُرئت أهدافُ توصيةٍ
            # بترتيب النص فصار «TP1» عند 3508 — ألفاً وتسعين نقطة —
            # بينما هدفُهم الأول 3600، فمضى السعر إليه ولم تُغلق.
            found = []
            for order, price in _TP.findall(low):
                price = float(price)
                if price not in [x for _, x in found]:
                    found.append((int(order) if order else 0, price))
            if all(n for n, _ in found):
                found.sort(key=lambda one: one[0])
            tps = [price for _, price in found]
            stop = _SL.search(low)
            # «Gold Sell Again Now 3867_69» دخولُها 3867؛ وما بعد
            # الشرطة زخرفةٌ في كتابتهم لا رقمُ دخولٍ ثانٍ
            at = float(entry.group(1))
            found = _action(
                "SIGNAL",
                f"{direction} من {at:g}",
                direction=direction,
                entry=at,
                sl=float(stop.group(1)) if stop else 0.0,
                tps=tps,
                same_tp=bool(_SAME_TP.search(low)))
            if _sane(found):
                return found

    # ── ٢) ما يتبع التوصية ──
    hit = _TP_HIT.search(low)
    if hit:
        return _action("TP_HIT", f"هدفٌ تحقق: {raw[:50]}",
                       level=int(hit.group(1)) if hit.group(1) else 1)
    if _SL_HIT.search(low):
        return _action("SL_HIT", f"ضُرب الوقف: {raw[:50]}")
    if _BE.search(low):
        return _action("BREAKEVEN", f"تأمين: {raw[:50]}")
    if _CLOSE.search(low) and not _NO_CLOSE.search(low):
        return _action("CLOSE", f"أمر خروج: {raw[:50]}")
    return _action("NONE", "")


def _sane(found):
    """توصيةٌ أرقامُها متناقضة ليست توصية.

    الوقف فوق الدخول في البيع وتحته في الشراء، والأهداف في الجهة
    الأخرى. ورسالةٌ تحكي عن صفقةٍ ماضية قد تحمل أرقاماً بلا هذا
    الترتيب — فتُردّ ولا تُحسب توصيةً جديدة."""
    entry = float(found["entry"])
    stop = float(found.get("sl") or 0.0)
    sell = found["direction"] == "SELL"
    if stop:
        if sell and stop <= entry:
            return False
        if not sell and stop >= entry:
            return False
    for tp in found.get("tps") or []:
        if sell and tp >= entry:
            return False
        if not sell and tp <= entry:
            return False
    return True


def interpret_all(text, pending_direction=None):
    """الواجهة نفسها التي يستعملها البوت لباقي القنوات."""
    found = interpret(text)
    return [] if found["action"] == "NONE" else [found]
