import json

import pytest

from app import signals
from app.risk import RiskError
from tests.conftest import buy_alert


def sig(**over):
    return signals.parse(json.dumps(buy_alert(**over)))


def sell_sig(**over):
    payload = dict(signal="SELL", entry=4296.0, sl=4310.0,
                   tp1=4286.0, tp2=4276.0, tp3=4266.0, id="bar-sell")
    payload.update(over)
    return signals.parse(json.dumps(buy_alert(**payload)))


def test_يفتح_الصفقة_ويقيس_وقفها_من_سعر_التنفيذ(trader, broker):
    result = trader.handle(sig())

    assert result["status"] == "opened"
    assert result["side"] == "buy"
    # السعر الورقي: منتصفه سعر التوصية، والشراء عند الطلب 4293.65
    assert result["fill"] == 4293.65
    # وقف المؤشر 14.52 مقيساً من التنفيذ لا من 4293.50
    assert result["sl"] == 4279.13
    assert round(result["fill"] - result["sl"], 2) == 14.52
    assert result["tp"] == 4303.81
    assert result["risk_usd"] == pytest.approx(14.52, abs=0.01)

    open_now = broker.positions(symbol="XAUUSD")
    assert len(open_now) == 1
    assert open_now[0].volume == 0.01


def test_التنبيه_المكرر_لا_يفتح_صفقة_ثانية(trader, broker):
    assert trader.handle(sig())["status"] == "opened"
    again = trader.handle(sig())
    assert again["status"] == "skipped"
    assert "مكرر" in again["reason"]
    assert len(broker.positions(symbol="XAUUSD")) == 1


def test_إشارة_بنفس_الاتجاه_لا_تضاعف_الصفقة(trader, broker):
    trader.handle(sig())
    second = trader.handle(sig(id="bar-2", entry=4295.0, sl=4280.0,
                               tp1=4305.0, tp2=4315.0, tp3=4325.0))
    assert second["status"] == "skipped"
    assert "مفتوحة أصلاً" in second["reason"]
    assert len(broker.positions(symbol="XAUUSD")) == 1


def test_الإشارة_المعاكسة_تغلق_القديمة_وتفتح_الجديدة(trader, broker):
    trader.handle(sig())
    result = trader.handle(sell_sig())

    assert result["status"] == "opened"
    assert result["side"] == "sell"
    open_now = broker.positions(symbol="XAUUSD")
    assert len(open_now) == 1
    assert open_now[0].side == "sell"


def test_يُبقي_القديمة_إن_مُنع_العكس(settings, trader, broker):
    settings.reverse_on_opposite = False
    trader.handle(sig())
    result = trader.handle(sell_sig())

    assert result["status"] == "skipped"
    assert broker.positions(symbol="XAUUSD")[0].side == "buy"


def test_يردّ_صفقة_تتجاوز_سقف_الخسارة(settings, trader, broker):
    settings.lot = 0.10          # 14.52 × 0.10 × 100 = 145 دولاراً
    with pytest.raises(RiskError, match="والحد المسموح"):
        trader.handle(sig())
    assert broker.positions(symbol="XAUUSD") == []


def test_يردّ_مسافة_وقف_خارج_الحدود(trader, broker):
    with pytest.raises(RiskError, match="أوسع"):
        trader.handle(sig(id="wide", entry=4300.0, sl=4100.0,
                          tp1=4320.0, tp2=4340.0, tp3=4360.0))
    assert broker.positions(symbol="XAUUSD") == []


def test_الهدف_الأول_ينقل_الوقف_إلى_الدخول(trader, broker):
    trader.handle(sig())
    position = broker.positions(symbol="XAUUSD")[0]
    assert position.sl < position.price_open

    result = trader.handle(signals.parse(json.dumps(
        {"secret": "x", "signal": "TP1 Hit", "ticker": "OANDA:XAUUSD"})))

    assert result["status"] == "managed"
    assert broker.positions(symbol="XAUUSD")[0].sl == position.price_open


def test_الهدف_الأول_يغلق_جزءاً_إن_طُلب(settings, trader, broker):
    settings.lot = 0.04
    settings.max_risk_usd = 100.0
    settings.tp1_close_percent = 50.0
    trader.handle(sig())

    trader.handle(signals.parse(json.dumps(
        {"secret": "x", "signal": "TP1 Hit", "ticker": "OANDA:XAUUSD"})))

    remaining = broker.positions(symbol="XAUUSD")[0]
    assert remaining.volume == 0.02
    assert remaining.sl == remaining.price_open


def test_الهدف_الثالث_يغلق_الصفقة(trader, broker):
    trader.handle(sig())
    result = trader.handle(signals.parse(json.dumps(
        {"secret": "x", "signal": "TP3 Hit", "ticker": "OANDA:XAUUSD"})))

    assert result["status"] == "closed"
    assert broker.positions(symbol="XAUUSD") == []


def test_تنبيه_الوقف_بلا_صفقة_لا_يفعل_شيئاً(trader):
    result = trader.handle(signals.parse(json.dumps(
        {"secret": "x", "signal": "SL Hit", "ticker": "OANDA:XAUUSD"})))
    assert result["status"] == "noop"


def test_تنبيه_الوقف_يغلق_صفقة_بقيت_مفتوحة(trader, broker):
    trader.handle(sig())
    result = trader.handle(signals.parse(json.dumps(
        {"secret": "x", "signal": "SL Hit", "ticker": "OANDA:XAUUSD"})))
    assert result["status"] == "closed"
    assert broker.positions(symbol="XAUUSD") == []


def test_مفتاح_الإيقاف_يمنع_كل_شيء(settings, trader, broker):
    settings.enabled = False
    result = trader.handle(sig())
    assert result["status"] == "skipped"
    assert broker.positions(symbol="XAUUSD") == []


def test_الرمز_يُترجم_من_رمز_الشارت_إلى_رمز_الوسيط(settings, trader, broker):
    settings.symbol = "XAUUSD.m"
    settings.symbol_map = {"XAUUSD": "XAUUSD.m"}
    broker._defaults["XAUUSD.m"] = broker._defaults["XAUUSD"]

    result = trader.handle(sig())
    assert result["symbol"] == "XAUUSD.m"
    assert broker.positions(symbol="XAUUSD.m")
