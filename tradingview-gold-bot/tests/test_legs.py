"""
أرجل الصفقة.

الإشارة الواحدة تُفتح على أكثر من صفقة، لكل واحدة هدفها: واحدة
تُجنى عند الهدف الأول وأخرى تُترك تجري إلى الثالث. والخروج كله عند
الوسيط — كل رجل تحمل هدفها ووقفها — فلا يُنتظر تنبيه ولا يُخشى
انقطاع.
"""

import json

import pytest

from app import signals
from app.config import Settings, _parse_legs
from app.risk import RiskError
from tests.conftest import buy_alert


def sig(**over):
    return signals.parse(json.dumps(buy_alert(**over)))


# ── قراءة الإعداد ──

def test_يقرأ_رجلين():
    assert _parse_legs("1:0.01,3:0.01") == [(1, 0.01), (3, 0.01)]


def test_يقرأ_أحجاماً_مختلفة():
    assert _parse_legs("1:0.02, 3:0.05") == [(1, 0.02), (3, 0.05)]


def test_الفراغ_يعني_صفقة_واحدة():
    assert _parse_legs("") == []


@pytest.mark.parametrize("bad,why", [
    ("1", "هدف:حجم"), ("9:0.01", "الهدف"), ("1:0", "أكبر من صفر"),
    ("x:0.01", "رقم غير مفهوم"),
])
def test_يرفض_إعداداً_معطوباً(bad, why):
    with pytest.raises(ValueError, match=why):
        _parse_legs(bad)


def test_الأرجل_لا_تجتمع_مع_نسبة_المخاطرة():
    s = Settings()
    s.webhook_secret = "x" * 20
    s.legs = [(1, 0.01)]
    s.risk_percent = 1.0
    with pytest.raises(ValueError, match="لا يجتمعان"):
        s.validate()


# ── الفتح ──

def test_يفتح_رجلين_بهدفين_مختلفين(settings, trader, broker):
    settings.legs = [(1, 0.01), (3, 0.01)]
    settings.max_open_positions = 2

    result = trader.handle(sig())
    assert result["status"] == "opened"
    assert len(result["legs"]) == 2

    first, second = result["legs"]
    assert (first["target_tp"], second["target_tp"]) == (1, 3)
    # التنفيذ واحد، والوقف واحد، والهدفان مختلفان
    assert first["fill"] == second["fill"]
    assert first["sl"] == second["sl"]
    assert first["tp"] != second["tp"]
    assert second["tp"] > first["tp"]

    assert len(broker.positions(symbol="XAUUSD")) == 2


def test_وقف_الرجلين_بمسافة_المؤشر_من_التنفيذ(settings, trader, broker):
    settings.legs = [(1, 0.01), (3, 0.01)]
    settings.max_open_positions = 2

    result = trader.handle(sig())
    for leg in result["legs"]:
        assert round(leg["fill"] - leg["sl"], 2) == 14.52


def test_هدف_كل_رجل_بمسافة_هدفها(settings, trader, broker):
    # التوصية: دخول 4293.50 · TP1 4303.66 · TP3 4323.99
    settings.legs = [(1, 0.01), (3, 0.01)]
    settings.max_open_positions = 2

    legs = trader.handle(sig())["legs"]
    assert round(legs[0]["tp"] - legs[0]["fill"], 2) == 10.16
    assert round(legs[1]["tp"] - legs[1]["fill"], 2) == 30.49


def test_الخسارة_تُحسب_على_المجموع(settings, trader):
    settings.legs = [(1, 0.01), (3, 0.01)]
    settings.max_open_positions = 2

    # 14.52 × 0.02 × 100 = 29.04 للرجلين معاً
    assert trader.handle(sig())["risk_usd"] == pytest.approx(29.04, abs=0.01)


def test_يردّ_الرجلين_إن_تجاوز_مجموعهما_السقف(settings, trader, broker):
    # كل رجل وحدها تمرّ، ومجموعهما لا
    settings.legs = [(1, 0.01), (3, 0.01)]
    settings.max_open_positions = 2
    settings.max_risk_usd = 20.0

    with pytest.raises(RiskError, match="والحد المسموح"):
        trader.handle(sig())
    assert broker.positions(symbol="XAUUSD") == []


def test_يردّ_إن_تجاوزت_الأرجل_حد_الصفقات(settings, trader, broker):
    settings.legs = [(1, 0.01), (3, 0.01)]
    settings.max_open_positions = 1

    result = trader.handle(sig())
    assert result["status"] == "skipped"
    assert "حد المفتوحة" in result["reason"]
    assert broker.positions(symbol="XAUUSD") == []


def test_الانعكاس_يغلق_الرجلين_ويفتح_رجلين(settings, trader, broker):
    settings.legs = [(1, 0.01), (3, 0.01)]
    settings.max_open_positions = 2
    trader.handle(sig())

    result = trader.handle(signals.parse(json.dumps(buy_alert(
        signal="SELL", entry=4296.0, sl=4310.0,
        tp1=4286.0, tp2=4276.0, tp3=4266.0, id="bar-sell"))))

    assert result["status"] == "opened"
    positions = broker.positions(symbol="XAUUSD")
    assert len(positions) == 2
    assert all(p.side == "sell" for p in positions)


# ── الخروج بيد الوسيط ──

@pytest.mark.parametrize("word", ["TP1 Hit", "TP3 Hit", "SL Hit", "TP Hit (Any)"])
def test_تنبيهات_الخروج_تُردّ_ما_دامت_الأرجل_مضبوطة(settings, trader, broker, word):
    settings.legs = [(1, 0.01), (3, 0.01)]
    settings.max_open_positions = 2
    trader.handle(sig())
    before = [(p.ticket, p.sl, p.tp, p.volume)
              for p in broker.positions(symbol="XAUUSD")]

    result = trader.handle(signals.parse(json.dumps(
        {"secret": "x", "signal": word, "ticker": "OANDA:XAUUSD"})))

    assert result["status"] == "skipped"
    assert "الوسيط" in result["reason"]
    # ولا تُمسّ صفقة: الرجل الثانية تُترك تجري إلى هدفها الأبعد
    after = [(p.ticket, p.sl, p.tp, p.volume)
             for p in broker.positions(symbol="XAUUSD")]
    assert after == before


def test_تنبيهات_الخروج_تعمل_حين_لا_أرجل(settings, trader, broker):
    # بلا أرجل يبقى السلوك القديم: التنبيه يدير الصفقة
    settings.legs = []
    settings.tp1_move_to_breakeven = True
    trader.handle(sig())
    position = broker.positions(symbol="XAUUSD")[0]

    trader.handle(signals.parse(json.dumps(
        {"secret": "x", "signal": "TP1 Hit", "ticker": "OANDA:XAUUSD"})))

    assert broker.positions(symbol="XAUUSD")[0].sl == position.price_open


def test_أمر_الإغلاق_يعمل_مع_الأرجل(settings, trader, broker):
    # الإغلاق اليدوي يبقى بيد صاحب الحساب مهما كان الإعداد
    settings.legs = [(1, 0.01), (3, 0.01)]
    settings.max_open_positions = 2
    trader.handle(sig())

    result = trader.handle(signals.parse(json.dumps(
        {"secret": "x", "signal": "close", "ticker": "OANDA:XAUUSD"})))

    assert result["status"] == "closed"
    assert broker.positions(symbol="XAUUSD") == []
