"""
إشارة بلا أرقام.

بعض المؤشرات ترسم الدخول والوقف والأهداف رسماً على الشاشة لا قيماً
تُقرأ، فتصل تنبيهاتها بلا رقم واحد. والأصل حينئذ أن تُرفض: صفقة
بوقف مجهول أسوأ من إشارة ضائعة. فإن ضُبطت ‎SL_DISTANCE‎ صار الوقف
عندنا — مسافةً تُقاس من سعر التنفيذ — ولا هدف عند الوسيط، بل يُنتظر
تنبيه «TP1 Hit» من المؤشر نفسه.
"""

import json

import pytest

from app import signals
from app.config import Settings
from tests.conftest import buy_alert

BLIND = {"entry": None, "sl": None, "tp1": None, "tp2": None, "tp3": None}


def blind(**over):
    payload = buy_alert(**BLIND)
    payload.update(over)
    return signals.parse(json.dumps(payload), require_prices=False)


@pytest.fixture
def blind_settings(settings):
    settings.sl_distance = 11.0
    settings.lot = 0.04
    return settings


# ── القراءة ──

def test_الأصل_رفض_إشارة_بلا_أرقام():
    with pytest.raises(signals.SignalError, match="بلا سعر دخول"):
        signals.parse(json.dumps(buy_alert(**BLIND)))


def test_تُقبل_حين_يكون_الوقف_عندنا():
    signal = blind()
    assert signal.kind == signals.BUY
    assert signal.risk_distance is None


def test_ما_أرسله_المؤشر_يبقى_مفحوصاً():
    # وقف الشراء فوق دخوله تناقض، ولا يُغتفر لمجرد أن الأرقام اختيارية
    with pytest.raises(signals.SignalError, match="موضع الوقف"):
        signals.parse(
            json.dumps(buy_alert(entry=4293.50, sl=4300.0)), require_prices=False
        )


# ── الفتح ──

def test_الوقف_مسافة_الإعداد_من_التنفيذ(blind_settings, trader, broker):
    broker.set_price("XAUUSD", 4300.0)

    result = trader.handle(blind())

    assert result["status"] == "opened"
    leg = result["legs"][0]
    assert round(leg["fill"] - leg["sl"], 2) == 11.0
    assert leg["lot"] == 0.04


def test_لا_هدف_عند_الوسيط(blind_settings, trader, broker):
    """الخروج بتنبيه المؤشر، فهدفٌ نخترعه نحن يغلق الصفقة في غير موضعها."""
    broker.set_price("XAUUSD", 4300.0)

    leg = trader.handle(blind())["legs"][0]
    assert leg["tp"] is None


def test_البيع_وقفه_فوق_التنفيذ(blind_settings, trader, broker):
    broker.set_price("XAUUSD", 4300.0)

    leg = trader.handle(blind(signal="SELL"))["legs"][0]
    assert round(leg["sl"] - leg["fill"], 2) == 11.0


def test_أرقام_المؤشر_أولى_حين_يرسلها(blind_settings, trader, broker):
    """‎SL_DISTANCE‎ بديلٌ عند الغياب، لا بديلٌ عن المؤشر."""
    blind_settings.max_risk_usd = 100.0
    signal = signals.parse(json.dumps(buy_alert()), require_prices=False)

    leg = trader.handle(signal)["legs"][0]
    assert round(leg["fill"] - leg["sl"], 2) == 14.52


def test_الخسارة_المحسوبة_تُفحص_على_مسافتنا(blind_settings, trader, broker):
    broker.set_price("XAUUSD", 4300.0)
    # ١١ دولاراً × ٠٫٠٤ لوت × ١٠٠ = ٤٤ دولاراً
    blind_settings.max_risk_usd = 40.0

    from app.risk import RiskError
    with pytest.raises(RiskError, match="خسارة الصفقة"):
        trader.handle(blind())


# ── الخروج بالتنبيه ──

def test_تنبيه_الهدف_الأول_يغلق_الصفقة_كاملة(blind_settings, trader, broker):
    broker.set_price("XAUUSD", 4300.0)
    blind_settings.tp1_close_percent = 100.0

    trader.handle(blind())
    assert len(broker.positions(symbol="XAUUSD")) == 1

    hit = signals.parse(json.dumps({
        "secret": blind_settings.webhook_secret, "signal": "TP1 Hit",
        "ticker": "OANDA:XAUUSD", "id": "bar-2",
    }))
    result = trader.handle(hit)

    assert result["status"] == "managed"
    assert broker.positions(symbol="XAUUSD") == []


def test_تنبيه_الوقف_يغلق_ما_تبقى(blind_settings, trader, broker):
    broker.set_price("XAUUSD", 4300.0)
    trader.handle(blind())

    hit = signals.parse(json.dumps({
        "secret": blind_settings.webhook_secret, "signal": "SL Hit",
        "ticker": "OANDA:XAUUSD", "id": "bar-3",
    }))
    trader.handle(hit)

    assert broker.positions(symbol="XAUUSD") == []


# ── الإعداد ──

def test_المسافة_لا_تجتمع_مع_الأرجل():
    s = Settings()
    s.webhook_secret = "x" * 20
    s.sl_distance = 11.0
    s.legs = [(1, 0.02), (3, 0.02)]
    with pytest.raises(ValueError, match="لا يجتمعان"):
        s.validate()


def test_مسافة_سالبة_تُرفض():
    s = Settings()
    s.webhook_secret = "x" * 20
    s.sl_distance = -1.0
    with pytest.raises(ValueError, match="SL_DISTANCE"):
        s.validate()
