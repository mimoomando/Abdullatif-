"""
حساب الوقف والهدف وحجم الصفقة.

المبدأ الذي يحكم الملف كله: أرقام المؤشر آتية من شارت أواندا،
والصفقة تُفتح عند جست ماركتس، وبين السعرين فرق. فلا يُنقل سعر
الوقف كما كُتب، بل تُؤخذ **المسافة** بين الدخول والوقف وتُقاس من
سعر التنفيذ الفعلي. فتبقى المخاطرة كما أرادها المؤشر مهما تحرّك
السوق بين إرسال التنبيه وتنفيذه.
"""

from app.signals import BUY


class RiskError(ValueError):
    """صفقة لا تُفتح: مخاطرتها خارج ما يحتمله الحساب أو الوسيط."""


def stop_and_target(side, fill_price, risk_distance, reward_distance,
                    digits=2, broker_min_distance=0.0):
    """
    سعرا الوقف والهدف مقيسين من سعر التنفيذ.

    ``broker_min_distance`` أقل بُعد يقبله الوسيط بين السعر والوقف
    (stops level). ما دون ذلك يرفضه الخادم، فنُبعده إلى الحد الأدنى
    بدل أن تُفتح صفقة بلا وقف أصلاً.
    """
    if fill_price <= 0:
        raise RiskError("سعر تنفيذ غير صالح.")
    if risk_distance is None or risk_distance <= 0:
        raise RiskError("مسافة الوقف غير معروفة.")

    risk = max(risk_distance, broker_min_distance)
    stop = fill_price - risk if side == "buy" else fill_price + risk

    target = None
    if reward_distance and reward_distance > 0:
        reward = max(reward_distance, broker_min_distance)
        target = fill_price + reward if side == "buy" else fill_price - reward
        target = round(target, digits)

    stop = round(stop, digits)
    if stop <= 0:
        raise RiskError("الوقف المحسوب صفر أو أقل.")
    return stop, target


def check_distance(risk_distance, min_distance, max_distance):
    """
    حارس بين المؤشر والحساب.

    مسافة أضيق من اللازم تعني قراءة خاطئة أو سعراً مشوّشاً، وأوسع
    من اللازم تعني صفقة لا يحتملها الحساب. وكلاهما يُردّ قبل الفتح
    لا بعده.
    """
    if risk_distance is None or risk_distance <= 0:
        raise RiskError("لا مسافة وقف: الصفقة لا تُفتح بلا مخاطرة معلومة.")
    if risk_distance < min_distance:
        raise RiskError(
            f"مسافة الوقف {risk_distance:.2f} أضيق من الحد الأدنى {min_distance:.2f}."
        )
    if risk_distance > max_distance:
        raise RiskError(
            f"مسافة الوقف {risk_distance:.2f} أوسع من الحد الأعلى {max_distance:.2f}."
        )


def money_at_risk(risk_distance, lot, value_per_price_unit):
    """
    كم دولاراً تخسر الصفقة إن ضُرب وقفها.

    ``value_per_price_unit`` قيمة تحرّك السعر درجة واحدة للوت
    الواحد: تُشتق من بيانات الرمز عند الوسيط (tick_value ÷ tick_size)،
    وتساوي مئة للذهب عند أكثر الوسطاء.
    """
    return abs(risk_distance) * lot * value_per_price_unit


def check_money_at_risk(risk_distance, lot, value_per_price_unit, max_risk_usd):
    risk = money_at_risk(risk_distance, lot, value_per_price_unit)
    if risk > max_risk_usd:
        raise RiskError(
            f"خسارة الصفقة عند وقفها {risk:.2f} دولاراً، "
            f"والحد المسموح {max_risk_usd:.2f}."
        )
    return risk


def lot_for_risk(balance, risk_percent, risk_distance, value_per_price_unit,
                 volume_step=0.01, volume_min=0.01, volume_max=100.0):
    """
    حجم الصفقة الذي يجعل خسارتها عند الوقف نسبةً من الرصيد.

    يُقرَّب إلى الأسفل دائماً: تجاوز النسبة المطلوبة أسوأ من التقصير
    عنها. وإن لم يبلغ المحسوب أصغر حجم يقبله الوسيط فلا صفقة، لأن
    فتحها بأصغر حجم يعني تجاوز الحد الذي وضعه صاحب الحساب.
    """
    if balance <= 0:
        raise RiskError("رصيد غير صالح.")
    if risk_percent <= 0:
        raise RiskError("نسبة المخاطرة صفر أو أقل.")
    if risk_distance is None or risk_distance <= 0:
        raise RiskError("مسافة الوقف غير معروفة.")
    if value_per_price_unit <= 0:
        raise RiskError("قيمة الدرجة غير معروفة عند الوسيط.")

    budget = balance * risk_percent / 100.0
    raw = budget / (risk_distance * value_per_price_unit)

    steps = int(raw / volume_step)          # تقريب إلى الأسفل
    lot = round(steps * volume_step, 8)

    if lot < volume_min:
        raise RiskError(
            f"المخاطرة المطلوبة ({budget:.2f} دولاراً) لا تبلغ أصغر حجم "
            f"يقبله الوسيط ({volume_min}). وسّع النسبة أو اترك الصفقة."
        )
    return min(lot, volume_max)


def normalize_lot(lot, volume_step=0.01, volume_min=0.01, volume_max=100.0):
    """تقريب الحجم إلى ما يقبله الوسيط، إلى الأسفل ثم داخل حدوده."""
    if lot <= 0:
        raise RiskError("حجم الصفقة صفر أو أقل.")
    steps = int(round(lot / volume_step, 8))
    normalized = round(max(steps, 1) * volume_step, 8)
    if normalized > volume_max:
        normalized = volume_max
    if normalized < volume_min:
        normalized = volume_min
    return normalized


def breakeven_stop(side, entry_price, digits=2, cushion=0.0):
    """وقف عند سعر الدخول، مع هامش يغطي العمولة إن طُلب."""
    if side == "buy":
        return round(entry_price + cushion, digits)
    return round(entry_price - cushion, digits)


def pick_reward_distance(signal, target_tp):
    """
    مسافة الهدف المطلوب، وإن لم يرسله المؤشر فأقرب هدف أرسله.

    صفقة بلا هدف تبقى مفتوحة على الوقف وحده، وهذا مقبول: المؤشر
    يرسل تنبيه بلوغ الهدف فتُدار عنده. أما بلا وقف فلا تُفتح.
    """
    distance = signal.reward_distance(target_tp)
    if distance:
        return distance
    for index in range(1, 4):
        distance = signal.reward_distance(index)
        if distance:
            return distance
    return None


def side_of(signal):
    return "buy" if signal.kind == BUY else "sell"
