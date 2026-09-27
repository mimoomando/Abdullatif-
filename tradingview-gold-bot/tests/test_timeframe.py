"""
حارس الفريم.

المؤشر الواحد يعطي إشارات مختلفة على كل فريم، والمقصود فريمٌ بعينه.
والتنبيه في تيرادينغ فيو مربوط بفريم شارته، لكن تنبيهاً أُنشئ سهواً
على شارت آخر لا يردّه شيء في المنصة. فهذا حارسه في البريدج.
"""

import json

import pytest

from app import signals
from app.config import _parse_timeframes
from tests.conftest import buy_alert


def sig(**over):
    return signals.parse(json.dumps(buy_alert(**over)))


# ── تطبيع الفريم ──

@pytest.mark.parametrize("raw,minutes", [
    ("1", 1), ("5", 5), ("15", 15), ("60", 60), ("240", 240),
    ("D", 1440), ("W", 10080), ("M", 43200),
    ("M1", 1), ("M15", 15), ("H1", 60), ("H4", 240), ("D1", 1440),
    ("1m", 1), ("5m", 5), ("1h", 60), ("1d", 1440),
    ("15min", 15), ("4hour", 240),
])
def test_يقرأ_صيغ_الفريم_المختلفة(raw, minutes):
    assert signals.normalize_timeframe(raw) == minutes


def test_حالة_الحرف_تفرّق_بين_الدقيقة_والشهر():
    # تيرادينغ فيو تكتب الشهر «1M»، والناس يكتبون الدقيقة «1m»
    assert signals.normalize_timeframe("1M") == 43200
    assert signals.normalize_timeframe("1m") == 1
    # والميتاتريدر لا يعني بالميم البادئة إلا الدقيقة
    assert signals.normalize_timeframe("M1") == 1


@pytest.mark.parametrize("raw", ["", None, "abc", "{{interval}}", "   "])
def test_ما_لا_يُفهم_يعود_لا_شيء(raw):
    assert signals.normalize_timeframe(raw) is None


# ── قراءة الفريم من التنبيه ──

def test_يقرأ_الفريم_من_حقول_مختلفة():
    assert sig(tf="1").timeframe == 1
    assert sig(interval="15").timeframe == 15
    assert sig(timeframe="H1").timeframe == 60


def test_تنبيه_بلا_فريم_يبقى_مقروءاً():
    s = sig()
    assert s.timeframe is None
    assert s.kind == signals.BUY


# ── قراءة الإعداد ──

def test_يقرأ_قائمة_الفريمات():
    assert _parse_timeframes("1") == {1}
    assert _parse_timeframes("1,5,15") == {1, 5, 15}
    assert _parse_timeframes("M1, H1") == {1, 60}
    assert _parse_timeframes("") == set()


def test_يرفض_فريماً_غير_مفهوم_في_الإعداد():
    with pytest.raises(ValueError, match="غير مفهوم"):
        _parse_timeframes("1,abc")


# ── الحارس أثناء التنفيذ ──

def test_يفتح_إن_وافق_الفريم(settings, trader, broker):
    settings.allowed_timeframes = {1}
    assert trader.handle(sig(tf="1"))["status"] == "opened"


def test_يردّ_فريماً_غير_مسموح_ولا_يفتح(settings, trader, broker):
    settings.allowed_timeframes = {1}
    result = trader.handle(sig(tf="15"))

    assert result["status"] == "skipped"
    assert "غير مسموح" in result["reason"]
    assert broker.positions(symbol="XAUUSD") == []


def test_يردّ_تنبيهاً_بلا_فريم_ويقول_ما_ينقص(settings, trader, broker):
    settings.allowed_timeframes = {1}
    result = trader.handle(sig())

    assert result["status"] == "skipped"
    assert "tf" in result["reason"] and "interval" in result["reason"]
    assert broker.positions(symbol="XAUUSD") == []


def test_الفراغ_يقبل_كل_فريم(settings, trader):
    settings.allowed_timeframes = set()
    assert trader.handle(sig(tf="240"))["status"] == "opened"


def test_الحارس_يسري_على_تنبيهات_الإدارة_أيضاً(settings, trader, broker):
    # هدفٌ بلغه فريم آخر لا يدير صفقة هذا الفريم
    settings.allowed_timeframes = {1}
    trader.handle(sig(tf="1"))
    opened = broker.positions(symbol="XAUUSD")[0]

    result = trader.handle(signals.parse(json.dumps(
        {"secret": "x", "signal": "TP1 Hit", "ticker": "OANDA:XAUUSD", "tf": "15"})))

    assert result["status"] == "skipped"
    assert broker.positions(symbol="XAUUSD")[0].sl == opened.sl


def test_الفريم_المردود_لا_يُحسب_مكرراً(settings, trader, broker):
    """يُردّ قبل حارس التكرار، فإصلاح الفريم وإعادة الإرسال تنجح."""
    settings.allowed_timeframes = {1}
    assert trader.handle(sig(tf="15"))["status"] == "skipped"

    settings.allowed_timeframes = {1, 15}
    assert trader.handle(sig(tf="15"))["status"] == "opened"
