"""vey_signals.py
────────────────
قراءة قناة VEY GOLD VIP — إنجليزية، وأسلوبها غير أسلوب VIP AN.

القناة تفرّق التوصية على رسالتين:

    »» BUY NOW ««   ثم   4005-4010

فالاتجاه في رسالة والسعران في التي تليها. ولأنها ترسل رقمين دائماً،
كل توصية صفقتان: واحدة عند كل رقم.

ولا شيء هنا يلمس MT5 ولا تيليغرام: منطق خالص يُختبر وحده.
"""

import re

# ═════════════════════════════════════════════
# توحيد النص
# ═════════════════════════════════════════════

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize(text):
    """حروف صغيرة، ورموز الزينة تُزال، والمسافات تُوحَّد.

    تُحفظ + و/ و- و. لأنها تميّز المعنى: «+70 PIPS B/E» حدثٌ وقع،
    و«Tp 50-70 PIPS B/E» خطةٌ معلنة، والفرق بينهما علامةُ زائد."""
    s = (text or "").translate(_DIGITS)
    s = re.sub(r"[^\w\s+/.\-]", " ", s)
    return " ".join(s.split()).lower()


# ═════════════════════════════════════════════
# المفردات
# ═════════════════════════════════════════════

# رقم سعر الذهب: أربع خانات، بكسر عشري أو بلا
_PRICE = r"\d{4}(?:\.\d+)?"
# «4005-4010» أو «4005 - 4010»
_RANGE = re.compile(rf"({_PRICE})\s*-\s*({_PRICE})")
_ANY_PRICE = re.compile(_PRICE)

_BUY = re.compile(r"\bbuy\b")
_SELL = re.compile(r"\bsell\b")
_LIMIT = re.compile(r"\blimits?\b")
_NOW = re.compile(r"\bnow\b")
_SIGNAL_MAX_WORDS = 4   # «BUY NOW» إعلانٌ، والجملةُ حديث

# الإغلاق: «TP 1 HIT» أو «WE CLOSE 60-70%» — الهدف الأول تحقق
# علامة النسبة تسقط في التوحيد، فلا يُعتمد عليها: «CLOSE 60-70»
# يكفيها مدى بعد الفعل. و«TP1 150P OKAY» ليس فيها hit فلا تُغلق.
_CLOSE = re.compile(
    r"\btp\s*\d+\s*hit\b"        # TP 1 HIT
    r"|\bwe\s+close\b"            # WE CLOSE 60-70% ...
    r"|\bclose\s+\d+\s*-\s*\d+"   # CLOSE 60-70% OF POSITIONS
)

# التأمين: علامة الزائد تفصل الحدث عن الخطة.
# «+70 PIPS B/E» وقع، و«Tp 50-70 PIPS B/E» خطةٌ في رسالة الأهداف.
_BE = re.compile(r"\+\s*\d*\s*(?:pips?\s*)?b\s*/?\s*e\b")

# الوقف: الكلمة ومعها رقم. «WE ARE WAITING FOR TP OR SL» بلا رقم فلا شيء.
_SL = re.compile(r"\bsl\b|\bstop\s*loss\b")


def _action(name, why, **extra):
    out = {"action": name, "why": why}
    out.update(extra)
    return out


def levels_in(text):
    """السعران اللذان ترسلهما القناة، مرتّبين تصاعدياً."""
    found = _RANGE.search(normalize(text))
    if not found:
        return []
    return sorted((float(found.group(1)), float(found.group(2))))


def interpret_all(text, pending_direction=None):
    """يترجم رسالة إلى قائمة أفعال.

    pending_direction  اتجاه «BUY NOW» الذي وصل قبل الأرقام، إن وُجد.

    الأفعال:
      SIGNAL      أُعلن الاتجاه وتُنتظر الأرقام (direction)
      LEVELS      سعرا الدخول (direction, levels)
      SET_STOP    وقف من القناة (price)
      BREAKEVEN   الوقف إلى الدخول
      CLOSE_ALL   يغلق كل صفقات هذه القناة
    """
    raw = (text or "").strip()
    if not raw:
        return []
    low = normalize(raw)
    if not low:
        return []

    # ── ١) الإغلاق أولاً: أسلم أن يُغلق قبل أن يُفتح ──
    if _CLOSE.search(low):
        return [_action("CLOSE_ALL", f"الهدف الأول تحقق: {raw[:60]}")]

    # ── ٢) التأمين ──
    if _BE.search(low):
        return [_action("BREAKEVEN", f"تأمين: {raw[:60]}")]

    # ── ٣) الوقف — الكلمة ومعها رقم ──
    if _SL.search(low):
        # الرقم الذي يلي كلمة الوقف هو المقصود، لا أول رقم في الجملة
        tail = low[_SL.search(low).end():]
        found = _ANY_PRICE.search(tail) or _ANY_PRICE.search(low)
        if found:
            return [_action("SET_STOP", f"وقف القناة {found.group(0)}",
                            price=float(found.group(0)))]
        return []

    # ── ٤) الاتجاه والأرقام ──
    direction = ("BUY" if _BUY.search(low)
                 else "SELL" if _SELL.search(low) else None)
    levels = levels_in(low)

    if direction and levels:
        # «BUY LIMIT 4000-3995» — كل شيء في رسالة واحدة
        return [_action("LEVELS",
                        f"{direction} عند {levels[0]:g} و{levels[1]:g}",
                        direction=direction, levels=levels,
                        limit=bool(_LIMIT.search(low)))]

    if direction and (_NOW.search(low) or _LIMIT.search(low)):
        # «»» BUY NOW ««» — الأرقام في الرسالة التالية.
        # وإعلانُ الاتجاه قصيرٌ دائماً. أما «I set the buy limits» فجملةُ
        # حديثٍ فيها «buy» و«limits»، ولو قُرئت إعلاناً لصار أولُ رقمين
        # يمرّان بعدها — ولو في كلامٍ آخر — توصيةَ شراء.
        if len(low.split()) <= _SIGNAL_MAX_WORDS or "»" in raw or "«" in raw:
            return [_action("SIGNAL", f"أُعلن {direction} — تُنتظر الأرقام",
                            direction=direction,
                            limit=bool(_LIMIT.search(low)))]
        return []

    if levels and pending_direction:
        return [_action("LEVELS",
                        f"{pending_direction} عند {levels[0]:g} "
                        f"و{levels[1]:g}",
                        direction=pending_direction, levels=levels,
                        limit=False)]

    return []


def interpret(text, pending_direction=None):
    """الفعل الأول وحده."""
    found = interpret_all(text, pending_direction)
    return found[0] if found else {"action": "NONE", "why": ""}
