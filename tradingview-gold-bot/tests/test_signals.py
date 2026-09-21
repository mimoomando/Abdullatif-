import json

import pytest

from app import signals
from tests.conftest import buy_alert


def test_يقرأ_توصية_شراء_كاملة():
    s = signals.parse(json.dumps(buy_alert()))
    assert s.kind == signals.BUY
    assert s.side == "buy"
    assert s.entry == 4293.50
    assert s.tps == [4303.66, 4313.83, 4323.99]
    assert round(s.risk_distance, 2) == 14.52
    assert round(s.reward_distance(1), 2) == 10.16


def test_الاتجاه_يُستنتج_من_موضع_الوقف():
    sell = signals.parse(json.dumps(buy_alert(
        signal="SELL", entry=4300.0, sl=4315.0, tp1=4290.0, tp2=4280.0, tp3=4270.0)))
    assert sell.side == "sell"


def test_يرفض_رسالة_يناقض_وقفها_اتجاهها():
    # يقول شراء والوقف فوق الدخول: أحدهما خطأ ولا يُخمَّن أيّهما
    with pytest.raises(signals.SignalError, match="موضع الوقف"):
        signals.parse(json.dumps(buy_alert(entry=4293.50, sl=4310.0)))


def test_يرفض_قالباً_لم_تستبدله_تيرادينغ_فيو():
    with pytest.raises(signals.SignalError, match="قالب"):
        signals.parse(json.dumps(buy_alert(entry='{{plot("ENTRY")}}')))


def test_يرفض_هدفاً_في_الجهة_الخاطئة():
    with pytest.raises(signals.SignalError, match="ليس فوق الدخول"):
        signals.parse(json.dumps(buy_alert(tp1=4200.0)))


def test_يرفض_دخولاً_بلا_وقف():
    payload = buy_alert()
    payload.pop("sl")
    with pytest.raises(signals.SignalError, match="بلا وقف"):
        signals.parse(json.dumps(payload))


def test_يقبل_أسماء_حقول_مختلفة_وأرقاماً_بفواصل():
    s = signals.parse(json.dumps({
        "secret": "x", "action": "long", "symbol": "XAUUSD",
        "price": "4,293.50", "stop_loss": "4,278.98", "take_profit_1": "4,303.66",
    }))
    assert s.kind == signals.BUY
    assert s.entry == 4293.50
    assert s.sl == 4278.98


def test_يفهم_تنبيهات_الأهداف_والوقف():
    for word, expected in (("TP1 Hit", signals.TP1), ("TP Hit (Any)", signals.TP_ANY),
                           ("SL Hit", signals.SL_HIT), ("close", signals.CLOSE)):
        assert signals.parse(json.dumps({"signal": word})).kind == expected


def test_تنبيه_الهدف_لا_يحتاج_أرقاماً():
    s = signals.parse(json.dumps({"secret": "x", "signal": "TP1 Hit"}))
    assert s.kind == signals.TP1
    assert s.entry is None


def test_البصمة_تتكرر_لنفس_التنبيه_وتختلف_لغيره():
    one = signals.parse(json.dumps(buy_alert()))
    same = signals.parse(json.dumps(buy_alert()))
    other = signals.parse(json.dumps(buy_alert(id="bar-2")))
    assert one.fingerprint() == same.fingerprint()
    assert one.fingerprint() != other.fingerprint()


def test_يرفض_ما_ليس_جيسون():
    with pytest.raises(signals.SignalError, match="JSON"):
        signals.parse("buy gold now")
