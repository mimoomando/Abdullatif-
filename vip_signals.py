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

# حشو تبدأ به القناة رسائلها: يُحذف قبل عدّ الكلمات
# «يلا فعلي شراء من 14» ← «شراء من 14» ← أمر فتح
_FILLER = ("يلا", "فعلي", "شباب", "حبايبي", "حبايي", "طيب", "و", "ف")

# صيغ السؤال: «خرجتو من البيع على ربح؟» سؤال لا أمر، ولو حمل
# كلمة خروج. وإغلاقٌ بناءً على سؤال يُنهي صفقة رابحة بلا سبب.
_QUESTION = ("خرجتو", "خرجت", "خرجتم", "شو", "كم", "مين", "هل")

# الخروج: كل صيغه تغلق. «خرجنا ستوب» خبر بأن الوقف ضُرب فنغلق ما بقي.
_EXIT_PREFIX = ("خرو", "اخرج", "اخرا", "خرجنا")

# الإغلاق: «اغلاق دخول» و«اغلق» و«قفل» — صيغة الفعل وصيغة المصدر
_CLOSE_START = ("اغلق", "اغلاق", "اقفل", "قفل", "غلق", "سكر")

# أمر فتحٍ بلا اتجاه: «يلا خذ من 64» — الاتجاه من الصفقة الجارية،
# فالمدرّب لا يعيد ذكره وهو يتكلم عن التوصية نفسها.
_TAKE = ("خذ", "خد")
_TAKE_MAX_WORDS = 5        # «خذ كمان دخول من 96»

# الستوب بكل صيغه — يُبحث عنه ليُفصل عن أمر الفتح في السطر نفسه
_STOP_WORDS = ("ستوبك", "ستوب", "الستوب", "وقفك", "وقف", "sl")

# وحدات المسافة: الرقم بعدها عدد نقاطٍ لا سعر.
# «يعني ستوبك pip 20 فقط انتبه» شرحٌ لضيق الوقف، ولو قُرئ سعراً
# لانتقل الوقف عشرات الدولارات بعيداً.
_DISTANCE = ("pip", "pips", "بيب", "نقطه", "نقاط", "دقايق", "دقيقه")

# «يعني» تسبق الشرح لا الأمر: «يعني ستوبك 20 فقط» وصفٌ لضيق الوقف.
# وحدها هنا لا كل كلمات _NOT_COMMAND: المدرّب يقول «بامكانك تخلي شي
# بسيط لهدف ثاني على 12» وهي أمر هدفٍ مهذَّب لا كلام عنه.
_COMMENTARY = ("يعني",)


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


def _stop_index(tokens):
    """موضع أول كلمة ستوب، أو -1."""
    for i, w in enumerate(tokens):
        if w in _STOP_WORDS or _bare(w) in _STOP_WORDS:
            return i
    return -1


def _strip_filler(tokens):
    out = list(tokens)
    while out and (out[0] in _FILLER or _bare(out[0]) in _FILLER):
        out.pop(0)
    return out


def _line_actions(text, reference_price=None, has_open_trade=False,
                  stop_was_hit=False):
    """يترجم **سطراً واحداً** إلى قائمة أفعال (قد تكون فارغة).

    سطرٌ واحد قد يحمل فعلين: «شراء من 62 ستوبك 60» أمر فتحٍ ومعه
    ستوبه. وكانت تُقرأ ستوباً وحده عند 3962 — أي أن توصيةً جديدة
    كانت تمرّ بلا صفقة، ويتحرّك وقفُ ما سبقها إلى سعر دخولها.
    """
    raw = (text or "").strip()
    if not raw:
        return []

    tok = words(raw)
    if not tok:
        return []
    joined = " ".join(tok)
    n = len(tok)

    # سؤال؟ لا يُنفَّذ منه شيء مهما حمل من كلمات الأوامر
    if "؟" in raw or "?" in raw or _has(tok, _QUESTION):
        return []

    # ── ١) الإغلاق أولاً: أسلم أن يُغلق قبل أن يُفتح ──
    if "انتهت" in tok:
        if "تفعل" in tok:          # انتهت لا تفعل
            return [_action("CLOSE_NO_REOPEN", "انتهت ولا تفتح مجدداً")]
        return [_action("CLOSE_ALL", "انتهت — يُغلق ما بقي مفتوحاً")]

    # «خروج» و«اخرجلي» و«اخرجو» و«خرجنا ستوب» — كلها إغلاق
    if any(w.startswith(_EXIT_PREFIX) or _bare(w).startswith(_EXIT_PREFIX)
           for w in tok):
        return [_action("CLOSE_ALL", f"أمر خروج: {joined}")]

    if _starts_with(tok, _CLOSE_START):
        if n <= _CLOSE_MAX_WORDS:
            return [_action("CLOSE_ALL", f"أمر إغلاق: {joined}")]
        # «اغلق 3 استمر بدخول 5» ليست أمر إغلاق بل إعادة دخول لمن فاته
        return []

    # ── ٢) حجز نصف الربح — ثلاث صيغ بمعنى واحد ──
    half = (
        ("احجز" in tok and ("نص" in tok or "نصف" in tok))
        or ("الاول" in tok and "تم" in tok)
        or (("نص" in tok or "نصف" in tok) and _has(tok, ("الارباح", "ارباح")))
    )
    if half:
        return [_action("CLOSE_HALF",
                        f"حجز النصف: {joined} — يغلق النصف والوقف للدخول")]

    # ── ٣) التأمين: الوقف إلى الدخول ──
    # «ستوب» و«دخول» معاً = تأمين، ولو حملت الجملة رقماً آخر.
    if _has(tok, ("تامين", "امن")) or (
            _has(tok, _STOP_WORDS) and _has(tok, ("دخولك", "دخول"))):
        return [_action("BREAKEVEN", "تأمين — الوقف إلى سعر الدخول")]

    # ── ٤) أمر الفتح، ومعه ستوبه إن جاء في السطر نفسه ──
    # يُفصل الستوب قبل عدّ الكلمات: «شراء من 62 ستوبك 60» خمس كلمات
    # لكنها أمرُ فتحٍ من ثلاث وذيلُ ستوب.
    cut = _stop_index(tok)
    head_tok = tok[:cut] if cut > 0 else list(tok)
    tail_tok = tok[cut:] if cut > 0 else []
    core = _strip_filler(head_tok)

    direction = ("BUY" if _starts_with(core, _BUY)
                 else "SELL" if _starts_with(core, _SELL) else None)
    takes = _starts_with(core, _TAKE)

    if direction or takes:
        limit = _TAKE_MAX_WORDS if takes and not direction else _OPEN_MAX_WORDS
        if _has(head_tok, _NOT_COMMAND):
            return []
        if len(core) > limit:
            return []
        stop = _price_from(tail_tok, raw, reference_price) if tail_tok else None
        if has_open_trade:
            # لا صفقات أكثر ما دامت واحدة قائمة — لكن الستوب يمرّ:
            # المدرّب يتكلم عن التوصية الحيّة، ووقفه آخر ما قاله عنها،
            # فإسقاطه مع أمر الفتح يترك الصفقة على وقفٍ أقدم.
            if stop is None:
                return []
            return [_action("SET_STOP", f"ستوب التوصية {stop:g} "
                            "(أمر الفتح مُنع — صفقة قائمة)", price=stop)]
        half_size = _has(head_tok, ("بسيط", "خفف", "خفيف", "صغير")) or (
            _has(head_tok, ("شويه", "شوية")) and _has(head_tok, ("خطر",)))
        out = [_action("OPEN",
                       f"أمر فتح {direction or 'بنفس الاتجاه'}: {joined}"
                       + (" (لوت بسيط)" if half_size else ""),
                       direction=direction,
                       size="HALF" if half_size else "FULL")]
        if stop is not None:
            out.append(_action("SET_STOP", f"ستوب التوصية {stop:g}",
                               price=stop))
        return out

    nums = numbers_in(raw, reference_price)

    # ── ٥) الهدف ──
    if _has(tok, ("هدفك", "هدف", "الهدف", "اهداف", "tp")):
        if not nums or _has(tok, _DISTANCE) or _has(tok, _COMMENTARY):
            return []
        second = _has(tok, ("ثاني", "ثانى", "الثاني", "2", "tp2"))
        return [_action("SET_TP2" if second else "SET_TP1",
                        ("هدف ثانٍ" if second else "هدف أول")
                        + f" {nums[0]:g}", price=nums[0])]

    # ── ٦) الستوب ──
    if _has(tok, _STOP_WORDS):
        # «يعني ستوبك pip 20 فقط انتبه» شرحٌ لا أمر: الرقم عدد نقاط،
        # ولو قُرئ سعراً لقفز الوقف عشرات الدولارات.
        if not nums or _has(tok, _DISTANCE) or _has(tok, _COMMENTARY):
            return []
        return [_action("SET_STOP", f"ستوب القناة {nums[0]:g}",
                        price=nums[0])]

    # ── ٧) الدخول المشروط: «لو ضربك تشتري من 22» ──
    conditional = _has(tok, ("لو", "اذا")) and _has(tok, ("ضربك", "ضرب"))
    if conditional:
        direction = ("BUY" if _has(tok, _BUY)
                     else "SELL" if _has(tok, _SELL) else None)
        if not direction or not stop_was_hit or has_open_trade:
            return []
        return [_action("REENTRY_IF_HIT",
                        f"الوقف ضُرب — إعادة دخول {direction}",
                        direction=direction)]

    # ── ٨) التجديد: «جدد من 25» ──
    if _starts_with(tok, ("جدد", "جددد")):
        if has_open_trade:
            return []
        return [_action("RENEW", "جدد — يفتح من جديد بنفس الاتجاه")]

    # «حبايي صفقة بيها شوية خطر خفف لوتك» — تخفيف بلا أمر فتح
    if _has(tok, ("خفف",)) and _has(tok, ("لوتك", "لوت", "اللوت")):
        return [_action("REDUCE_SIZE", f"تخفيف اللوت: {joined}")]

    return []


def _price_from(tokens, raw, reference_price):
    """أول سعر في مقطعٍ من الكلمات، مكتملاً بالسعر المرجعي."""
    for w in tokens:
        found = _NUM.findall(w)
        if not found:
            continue
        value = (complete_price(found[0], reference_price)
                 if reference_price else float(found[0]))
        if value is not None:
            return value
    return None


_OPENS = ("OPEN", "RENEW", "REENTRY_IF_HIT")
_CLOSES = ("CLOSE_ALL", "CLOSE_NO_REOPEN")


def interpret_all(text, reference_price=None, has_open_trade=False,
                  stop_was_hit=False):
    """يترجم رسالة إلى قائمة أفعال، سطراً سطراً.

    القناة تجمع هدفين في رسالة واحدة على سطرين:

        هدف اول 70
        هدف ثاني 75

    وقراءة الرسالة ككتلة واحدة كانت تُخرج هدفاً واحداً بسعر الأول
    موسوماً بأنه الثاني — فيضيع هدفٌ ويوضع الآخر في غير موضعه.
    لذلك يُقرأ كل سطر وحده، وتُتابَع حالة «هل هناك صفقة» بين السطور
    كي لا يُفتح في السطر الثاني ما مُنع في الأول.
    """
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if len(lines) > 1:
        out = []
        open_now = has_open_trade
        for line in lines:
            for act in _line_actions(line, reference_price, open_now,
                                     stop_was_hit):
                out.append(act)
                if act["action"] in _OPENS:
                    open_now = True
                elif act["action"] in _CLOSES:
                    open_now = False
        if out:
            return out
        # لم تُعطِ السطور شيئاً: قد تكون جملةً واحدة كُسرت على سطرين
    return _line_actions(text, reference_price, has_open_trade, stop_was_hit)


def interpret(text, reference_price=None, has_open_trade=False,
              stop_was_hit=False):
    """الفعل الأول وحده — يبقى لمن يريد قراراً واحداً.

    reference_price  سعر الذهب الآن — يُكمل به الأرقام الناقصة
    has_open_trade   هل للبوت صفقات مفتوحة الآن؟
    stop_was_hit     هل ضُرب وقف الصفقة السابقة؟ (لرسائل «لو ضربك»)
    """
    found = interpret_all(text, reference_price, has_open_trade, stop_was_hit)
    return found[0] if found else NONE
