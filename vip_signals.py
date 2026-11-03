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
    # النقطة تبقى بين رقمين وحدها: «خذ. من 4000» كانت تجعل الكلمة
    # «خذ.» فلا تُطابق «خذ»، فيضيع أمر الدخول كلّه
    s = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", s)
    return " ".join(s.split()).casefold()


def words(text):
    return normalize(text).split()


# ═════════════════════════════════════════════
# الأرقام الناقصة
# ═════════════════════════════════════════════

_NUM = re.compile(r"\d+(?:\.\d+)?")

# أبعد ما يُقبل بين السعر المكتوب والسعر المرجعي: 2% منه. أهداف
# القناة وأوقافها في حدود عشرات الدولارات، وغلطة خانة الألوف ألف —
# فالفاصل بينهما واسع ولا يلتبس.
MAX_PRICE_DRIFT = 0.02

# رسالةٌ كلها أرقام: «3947» أو «46» أو «4917-4918». بعد الفتح هي
# سعر دخول المدرّب لا كلام.
_ONLY_NUMBERS = re.compile(r"^\d[\d\s.\-]*$")

# «على 57» أو «عند 3957» — موضعُ الوقف. و«من» ليست منها: «ولو ضربك
# بتفعل من 64» سعرُ دخولٍ جديد لا موضعُ وقف، ولو قُرئت وقفاً لنُقل
# الوقف إلى سعر صفقةٍ أخرى لم تُفتح بعد.
_AT_PRICE = re.compile(r"\b(?:علي|عند)\s+(\d+(?:\.\d+)?)")

# حرف الجرّ وحده، والرقم قد يتأخر عنه: «ستوبك على دخولك 8»
_AT_WORD = re.compile(r"\b(?:علي|عند)\b")

# «من 50» أو «من 64-65» — سعر دخولٍ صريح يطلبه المدرّب
_FROM_PRICE = re.compile(r"\bمن\s+(\d+(?:\.\d+)?)")


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
    if digits >= 4:
        # رقم كامل — إلا أن يكون بعيداً بما لا يُعقل. المدرّب كتب
        # «هدف اول 4903» والذهب عند 3897: غلطةٌ في خانة الألوف،
        # ولو قُبلت لوُضع هدفٌ لا تبلغه الصفقة أبداً. نعيد بناءه من
        # آخر ثلاث خانات، ولا نقبل البديل إلا إن وقع قريباً.
        if reference and abs(value - float(reference)) > (
                float(reference) * MAX_PRICE_DRIFT):
            whole, _, frac = text.partition(".")
            # ثلاث خانات ثم خانتان: «4903» غلطتها في خانة الألوف
            # فتصلحها الثلاث، و«4360» والذهب 3952 غلطتها في خانة
            # المئات فلا يصلحها إلا آخر خانتين (60 ← 3960).
            for keep in (3, 2):
                tail = whole[-keep:] + (("." + frac) if frac else "")
                rebuilt = complete_price(tail, reference)
                if rebuilt is not None and abs(
                        rebuilt - float(reference)) <= (
                        float(reference) * MAX_PRICE_DRIFT):
                    return rebuilt
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

# وصف حجم الصفقة: يُفهم منه النصف، ولا يُعَدّ من كلمات الأمر.
# «شراء من 52 بلوت بسيط» خمس كلمات، وكلمتان منها وصفُ حجم — ولولا
# استثناؤهما لتجاوز الحدَّ فسقط أمر الفتح كلّه، وهو ما وقع فعلاً.
_SIZE_WORDS = ("بلوت", "لوت", "اللوت", "لوتك", "بسيط", "خفيف",
               "صغير", "خفف")

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
    # «انتهت» و«انتهى» خبرٌ بانتهاء الصفقة عندهم، فنغلق ما بقي عندنا.
    # و«انت تأمين» مثلها: الصفقة خرجت على التأمين، لا أمرٌ بنقل وقف.
    # والفرق بينها وبين «ستوبك دخولك» أنّ هذه خبرُ نهاية وتلك أمرُ
    # تثبيت — ولو خُلطتا لبقيت صفقةٌ مفتوحة بعد أن أُعلن انتهاؤها.
    ended = ("انتهت" in tok or "انتهي" in tok
             or ("انت" in tok and _has(tok, ("تامين", "التامين"))))
    if ended:
        if "تفعل" in tok or "تجدد" in tok:   # لا تفعل / لا تجدد
            return [_action("CLOSE_NO_REOPEN",
                            f"انتهت ولا تفتح مجدداً: {joined}")]
        return [_action("CLOSE_ALL", f"انتهت — يُغلق ما بقي: {joined}")]

    # «خروج» و«اخرجلي» و«اخرجو» و«خرجنا ستوب» — كلها إغلاق
    if any(w.startswith(_EXIT_PREFIX) or _bare(w).startswith(_EXIT_PREFIX)
           for w in tok):
        return [_action("CLOSE_ALL", f"أمر خروج: {joined}")]

    # «اغلق دخول 13-14 واستمر بدخول 8»: إغلاقٌ جزئي بحسب سعر الدخول.
    # ما قبل «واستمر» يُغلق وما بعدها يبقى — ولولا الفصل لأُغلق كل
    # شيء أو لم يُغلق شيء، وكلاهما خلاف أمر المدرّب.
    if _starts_with(tok, _CLOSE_START) and _has(tok, ("دخول", "دخولك")):
        cut_at = len(tok)
        for i, w in enumerate(tok):
            if _bare(w).startswith(("استمر", "ابق", "خلي", "كمل")):
                cut_at = i
                break
        head_nums = numbers_in(" ".join(tok[:cut_at]), reference_price)
        keep_nums = numbers_in(" ".join(tok[cut_at:]), reference_price)
        if head_nums:
            return [_action("CLOSE_ENTRIES",
                            "إغلاق دخول "
                            + " و".join(f"{p:g}" for p in head_nums)
                            + (" والاستمرار بـ"
                               + " و".join(f"{p:g}" for p in keep_nums)
                               if keep_nums else ""),
                            prices=head_nums, keep=keep_nums)]

    if _starts_with(tok, _CLOSE_START):
        # «اغلاق دخول بمجرد مايوصل دخولك»: إغلاقٌ حين يعود السعر إلى
        # الدخول، لا الآن. ووقفٌ عند الدخول يفعل ذلك بعينه، ويترك
        # الصفقة تمضي إن لم تعد — بخلاف إغلاقٍ فوريّ يُنهي الرابحة.
        if (_has(tok, ("بمجرد", "مايوصل", "يوصل", "لما"))
                and _has(tok, ("دخولك", "دخول"))):
            return [_action("BREAKEVEN",
                            f"إغلاق عند الدخول — وقفٌ عنده: {joined}")]
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
    # «افتح دخول جديد من 3908 على نفس الستوب» فيها «ستوب» و«دخول»
    # فكانت تُقرأ تأميناً — وهي أمرُ فتحٍ صريح، أي عكسُ المطلوب
    # تماماً: بدل أن يفتح كان ينقل الوقف إلى الدخول.
    opening = _has(tok, ("افتح", "اضف", "زيد")) or _has(tok, _TAKE)
    if opening and _FROM_PRICE.search(" ".join(tok)):
        return _added_entry(tok, raw, reference_price)

    if _has(tok, ("تامين", "امن")) or (
            _has(tok, _STOP_WORDS) and _has(tok, ("دخولك", "دخول"))):
        # «ستوبك دخولك على 57» يعطي السعر صراحةً، فهو أولى من تخمينه.
        # ولا يُؤخذ أيّ رقم: «بعد 10 دقايق يعني ستوبك دخولك» رقمها
        # دقائق لا سعراً — فيُشترط حرفُ جرٍّ قبله.
        # «على» أو «عند» تدلّ على موضع الوقف، والرقم قد يتأخر عنها
        # بكلمة: «ستوبك على دخولك 8». فمتى وُجد حرف الجرّ أُخذ آخر
        # رقم في الجملة. وبدونه لا يُؤخذ شيء — «بعد 10 دقايق يعني
        # ستوبك دخولك» رقمها دقائق لا سعراً.
        joined_tok = " ".join(tok)
        price = None
        if _AT_WORD.search(joined_tok):
            nums = _NUM.findall(joined_tok)
            if nums:
                price = (complete_price(nums[-1], reference_price)
                         if reference_price else float(nums[-1]))
        out = [_action("BREAKEVEN",
                       f"تأمين — الوقف إلى {price:g} (دخول المدرّب)",
                       price=price)
               if price is not None else
               _action("BREAKEVEN", "تأمين — الوقف إلى سعر الدخول")]
        # «حط ستوبك دخولك ولو ضربك بتفعل من 64» تحمل أمرين: تأميناً
        # ودخولاً من 64. وبفعلٍ واحد كان الثاني يضيع كلّه.
        out += _added_entry(tok, raw, reference_price)
        return out

    # ── ٤) أمر الفتح، ومعه ستوبه إن جاء في السطر نفسه ──
    # يُفصل الستوب قبل عدّ الكلمات: «شراء من 62 ستوبك 60» خمس كلمات
    # لكنها أمرُ فتحٍ من ثلاث وذيلُ ستوب.
    cut = _stop_index(tok)
    head_tok = tok[:cut] if cut > 0 else list(tok)
    tail_tok = tok[cut:] if cut > 0 else []
    core = _strip_filler(head_tok)
    core = [w for w in core if _bare(w) not in _SIZE_WORDS]

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
            # أمرٌ بسعرٍ صريح («يلا بيع من 50») دخولٌ إضافي يريده
            # صاحب الحساب ولو بقيت صفقات. وأمرٌ مجرّد («بيع الان»)
            # يبقى ممنوعاً: مجموعةٌ واحدة للتوصية المجرّدة.
            added = _added_entry(head_tok, raw, reference_price)
            if added:
                if direction:
                    added[0]["direction"] = direction
                if stop is not None:
                    added.append(_action("SET_STOP",
                                         f"ستوب التوصية {stop:g}",
                                         price=stop))
                return added
            # لا صفقات أكثر من أمرٍ مجرّد — لكن الستوب يمرّ: المدرّب
            # يتكلم عن التوصية الحيّة، ووقفه آخر ما قاله عنها.
            if stop is None:
                return []
            return [_action("SET_STOP", f"ستوب التوصية {stop:g} "
                            "(أمر الفتح مُنع — صفقة قائمة)", price=stop)]
        half_size = _has(head_tok, ("بسيط", "خفف", "خفيف", "صغير")) or (
            _has(head_tok, ("شويه", "شوية")) and _has(head_tok, ("خطر",)))
        # «شراء من 3903» يحمل سعر دخول المدرّب، والبوت ينفّذ بعده
        # بلحظة فيدخل أسوأ منه. ولولا حفظُه هنا لنُقل الوقف عند
        # «ستوبك دخولك» إلى دخول البوت — أضيق بدرجتين.
        at_from = _FROM_PRICE.search(" ".join(head_tok))
        coach = (complete_price(at_from.group(1), reference_price)
                 if at_from and reference_price
                 else float(at_from.group(1)) if at_from else None)
        out = [_action("OPEN",
                       f"أمر فتح {direction or 'بنفس الاتجاه'}: {joined}"
                       + (" (لوت بسيط)" if half_size else ""),
                       direction=direction,
                       coach_price=coach,
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

    # ── ٧) «لو ضربك خذ من 50» ──
    # كانت لا تُنفَّذ إلا إن كان الوقف قد ضُرب فعلاً وقت وصولها —
    # والمدرّب يرسلها قبل أن يُضرب، فكانت تضيع دائماً. وقرّر صاحب
    # الحساب أن تُفتح فوراً ولو بقيت صفقاتٌ مفتوحة.
    conditional = _has(tok, ("لو", "اذا")) and _has(tok, ("ضربك", "ضرب"))
    if conditional:
        added = _added_entry(tok, raw, reference_price)
        return added

    # ── ٨) التجديد: «جدد من 25» ──
    if _starts_with(tok, ("جدد", "جددد")):
        if has_open_trade:
            return []
        return [_action("RENEW", "جدد — يفتح من جديد بنفس الاتجاه")]

    # «حبايي صفقة بيها شوية خطر خفف لوتك» — تخفيف بلا أمر فتح
    if _has(tok, ("خفف",)) and _has(tok, ("لوتك", "لوت", "اللوت")):
        return [_action("REDUCE_SIZE", f"تخفيف اللوت: {joined}")]

    # ── ٩) سعر دخول المدرّب ──
    # بعد «بيع الان» يرسل «46» ثم «3946» ثم «3947»: أسعار دخوله هو.
    # كانت تُتجاهل، فإذا قال «ستوبك دخولك» نُقل الوقف إلى دخول البوت
    # وهو أسوأ بدرجة لأن التنفيذ يتأخر لحظة — فيُضرب وقفك وحدك ثم
    # تمضي الصفقة إلى هدف المدرّب. تُحفظ الآن ليُبنى عليها التأمين.
    if has_open_trade and _ONLY_NUMBERS.match(joined):
        prices = numbers_in(raw, reference_price)
        if prices:
            return [_action("QUOTE",
                            "سعر دخول المدرّب "
                            + " و".join(f"{p:g}" for p in prices),
                            prices=prices)]

    return []


def _added_entry(tok, raw, reference_price):
    """دخولٌ إضافي من سعرٍ صريح: «خذ من 50» أو «بتفعل من 64».

    يعيد قائمةً فيها فعلٌ واحد أو فارغة. الاتجاه قد يكون None فيأخذه
    المستدعي من الصفقة الجارية: المدرّب لا يعيد ذكره وهو يتكلم عن
    التوصية نفسها."""
    found = _FROM_PRICE.search(" ".join(tok))
    if not found:
        return []
    wants = (_has(tok, _TAKE) or _has(tok, ("تفعل", "بتفعل", "فعل"))
             or _has(tok, ("افتح", "اضف", "زيد"))
             or _has(tok, _BUY) or _has(tok, _SELL))
    if not wants:
        return []
    direction = ("BUY" if _has(tok, _BUY)
                 else "SELL" if _has(tok, _SELL) else None)
    price = complete_price(found.group(1), reference_price) \
        if reference_price else float(found.group(1))
    return [_action("ADD_ENTRY",
                    f"دخول إضافي من {price:g}"
                    + (f" {direction}" if direction else " بنفس الاتجاه"),
                    direction=direction, price=price, size="FULL")]


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


_OPENS = ("OPEN", "RENEW", "REENTRY_IF_HIT", "ADD_ENTRY")
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
