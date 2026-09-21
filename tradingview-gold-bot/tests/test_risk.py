import json

import pytest

from app import risk, signals
from tests.conftest import buy_alert


def test_الوقف_يُقاس_من_سعر_التنفيذ_لا_من_سعر_التوصية():
    # المؤشر: دخول 4293.50 ووقف 4278.98 ← مسافة 14.52
    # التنفيذ الحقيقي جاء عند 4296.00، فالوقف يتبعه لا يبقى مكانه
    stop, target = risk.stop_and_target("buy", 4296.00, 14.52, 10.16, digits=2)
    assert stop == 4281.48
    assert target == 4306.16
    assert round(4296.00 - stop, 2) == 14.52


def test_البيع_يعكس_الجهتين():
    stop, target = risk.stop_and_target("sell", 4300.00, 15.0, 10.0, digits=2)
    assert stop == 4315.00
    assert target == 4290.00


def test_يبعد_الوقف_إلى_حد_الوسيط_إن_كان_أقرب_مما_يقبل():
    stop, _ = risk.stop_and_target("buy", 4300.0, 0.10, None,
                                   digits=2, broker_min_distance=1.50)
    assert stop == 4298.50


def test_يرفض_مسافة_أضيق_أو_أوسع_من_المسموح():
    with pytest.raises(risk.RiskError, match="أضيق"):
        risk.check_distance(0.2, 0.5, 100.0)
    with pytest.raises(risk.RiskError, match="أوسع"):
        risk.check_distance(150.0, 0.5, 100.0)
    risk.check_distance(14.52, 0.5, 100.0)


def test_يحسب_خسارة_الوقف_بالدولار():
    # الذهب: درجة واحدة تساوي مئة دولار للوت الواحد
    assert risk.money_at_risk(14.52, 0.01, 100.0) == pytest.approx(14.52)
    assert risk.money_at_risk(14.52, 0.10, 100.0) == pytest.approx(145.2)


def test_يردّ_صفقة_تتجاوز_سقف_الخسارة():
    with pytest.raises(risk.RiskError, match="والحد المسموح"):
        risk.check_money_at_risk(14.52, 0.10, 100.0, max_risk_usd=50.0)
    assert risk.check_money_at_risk(14.52, 0.01, 100.0, 50.0) == pytest.approx(14.52)


def test_حجم_الصفقة_من_نسبة_المخاطرة():
    # رصيد 10000 ومخاطرة 1% ← 100 دولار ÷ (14.52 × 100) = 0.0688 ← 0.06
    lot = risk.lot_for_risk(10000.0, 1.0, 14.52, 100.0)
    assert lot == 0.06
    assert risk.money_at_risk(14.52, lot, 100.0) <= 100.0


def test_التقريب_إلى_الأسفل_لا_يتجاوز_النسبة_أبداً():
    # رصيد 5000 ومخاطرة 1% ← 50 دولاراً. المحسوب 0.0344 يُقرَّب إلى
    # 0.03 لا إلى 0.04، فتبقى الخسارة تحت الميزانية لا فوقها.
    lot = risk.lot_for_risk(5000.0, 1.0, 14.52, 100.0)
    assert lot == 0.03
    assert risk.money_at_risk(14.52, lot, 100.0) <= 50.0


def test_لا_صفقة_إن_لم_تبلغ_المخاطرة_أصغر_حجم_مقبول():
    with pytest.raises(risk.RiskError, match="أصغر حجم"):
        risk.lot_for_risk(100.0, 0.5, 50.0, 100.0)


def test_يختار_الهدف_المطلوب_وإلا_أقرب_موجود():
    s = signals.parse(json.dumps(buy_alert()))
    assert round(risk.pick_reward_distance(s, 2), 2) == 20.33
    only_two = signals.parse(json.dumps({
        "signal": "BUY", "entry": 100.0, "sl": 95.0, "tp1": 110.0}))
    assert risk.pick_reward_distance(only_two, 3) == pytest.approx(10.0)


def test_وقف_التأمين_عند_سعر_الدخول():
    assert risk.breakeven_stop("buy", 4296.00) == 4296.00
    assert risk.breakeven_stop("sell", 4296.00, cushion=0.20) == 4295.80
