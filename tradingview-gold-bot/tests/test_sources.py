"""
أكثر من مؤشر على الأداة نفسها.

الجسر لا يرى إلا رمز الأداة، فلولا بصمةٌ تفرّق لأغلق تنبيهُ مؤشرٍ
صفقةَ مؤشرٍ آخر. فصار لكل مصدر في ‎SOURCES‎ حجمه ووقفه وهدفه
وبصمته، ولا يلمس تنبيهه إلا صفقاته.
"""

import json

import pytest

from app import signals
from app.config import Settings, _parse_sources

SECRET = "tv-bridge-test-secret-0123456789"


def alert(kind="BUY", src=None, **over):
    payload = {"secret": SECRET, "signal": kind, "ticker": "OANDA:XAUUSD"}
    if src:
        payload["src"] = src
    payload.update(over)
    return signals.parse(json.dumps(payload), require_prices=False)


@pytest.fixture
def two_sources(settings):
    settings.sl_distance = 12.0        # المؤشر العام: وقفه اثنتا عشرة
    settings.lot = 0.04
    settings.sources = _parse_sources("lux:lot=0.05,sl=5,tp=5", settings.magic)
    settings.validate()
    return settings


# ── القراءة ──

def test_الرسالة_تسمّي_مصدرها():
    assert alert(src="LUX").source == "lux"


def test_ما_لم_يسمّ_مصدره_فلا_مصدر_له():
    assert alert().source == ""


def test_إشارتان_من_مؤشرين_ليستا_تكراراً():
    assert alert(src="lux").fingerprint() != alert().fingerprint()


# ── الفتح ──

def test_كل_مؤشر_بحجمه_ووقفه(two_sources, trader, broker):
    broker.set_price("XAUUSD", 4128.60)

    general = trader.handle(alert())["legs"][0]
    lux = trader.handle(alert(src="lux"))["legs"][0]

    assert general["lot"] == 0.04
    assert round(general["fill"] - general["sl"], 2) == 12.0

    assert lux["lot"] == 0.05
    assert round(lux["fill"] - lux["sl"], 2) == 5.0


def test_هدف_المؤشر_الثاني_عند_الوسيط(two_sources, trader, broker):
    """لا تنبيه خروج له، فهدفه يُحفظ عند الوسيط ليغلقه هو."""
    broker.set_price("XAUUSD", 4128.60)

    lux = trader.handle(alert(src="lux"))["legs"][0]
    assert round(lux["tp"] - lux["fill"], 2) == 5.0


def test_المؤشر_العام_بلا_هدف_عند_الوسيط(two_sources, trader, broker):
    broker.set_price("XAUUSD", 4128.60)
    assert trader.handle(alert())["legs"][0]["tp"] is None


def test_بصمتان_مختلفتان(two_sources, trader, broker):
    broker.set_price("XAUUSD", 4128.60)
    trader.handle(alert())
    trader.handle(alert(src="lux"))

    magics = {p.magic for p in broker.positions(symbol="XAUUSD")}
    assert len(magics) == 2
    assert two_sources.magic in magics
    assert two_sources.sources["lux"].magic in magics


def test_حدّ_المفتوحة_يُحسب_لكل_مؤشر_وحده(two_sources, trader, broker):
    """صفقة لكلٍّ منهما لا تتجاوز حدّ الواحدة: الحدّ على صفقاته هو."""
    broker.set_price("XAUUSD", 4128.60)
    two_sources.max_open_positions = 1

    assert trader.handle(alert())["status"] == "opened"
    assert trader.handle(alert(src="lux"))["status"] == "opened"
    assert len(broker.positions(symbol="XAUUSD")) == 2


# ── العزل عند الخروج ──

def test_تنبيه_خروج_لا_يلمس_صفقة_غيره(two_sources, trader, broker):
    broker.set_price("XAUUSD", 4128.60)
    two_sources.tp1_close_percent = 100.0
    trader.handle(alert())
    trader.handle(alert(src="lux"))

    trader.handle(alert("TP1 Hit", id="x1"))

    left = broker.positions(symbol="XAUUSD")
    assert len(left) == 1
    assert left[0].magic == two_sources.sources["lux"].magic


def test_إشارة_معاكسة_تغلق_صفقة_مصدرها_وحدها(two_sources, trader, broker):
    broker.set_price("XAUUSD", 4128.60)
    trader.handle(alert())
    trader.handle(alert(src="lux"))

    trader.handle(alert("SELL", src="lux"))

    left = broker.positions(symbol="XAUUSD")
    sides = {(p.magic, p.side) for p in left}
    assert (two_sources.magic, "buy") in sides
    assert (two_sources.sources["lux"].magic, "sell") in sides
    assert len(left) == 2


# ── الإعداد ──

def test_يقرأ_مصدراً():
    src = _parse_sources("lux:lot=0.05,sl=5,tp=5", 26092101)["lux"]
    assert (src.lot, src.sl_distance, src.tp_distance) == (0.05, 5.0, 5.0)


def test_البصمة_ثابتة_على_الاسم():
    first = _parse_sources("lux:lot=0.05,sl=5", 26092101)["lux"].magic
    again = _parse_sources("lux:lot=0.09,sl=7", 26092101)["lux"].magic
    assert first == again


def test_بصمتان_متساويتان_تُرفضان():
    s = Settings()
    s.webhook_secret = "x" * 20
    s.sources = _parse_sources("a:lot=0.01,sl=5;b:lot=0.01,sl=5", s.magic)
    s.sources["b"].magic = s.sources["a"].magic
    with pytest.raises(ValueError, match="بصمتهما واحدة"):
        s.validate()


def test_بصمة_مصدر_تساوي_العامة_تُرفض():
    s = Settings()
    s.webhook_secret = "x" * 20
    s.sources = _parse_sources("a:lot=0.01,sl=5", s.magic)
    s.sources["a"].magic = s.magic
    with pytest.raises(ValueError, match="البصمة العامة"):
        s.validate()


def test_مصدر_بلا_وقف_يُرفض():
    s = Settings()
    s.webhook_secret = "x" * 20
    s.sources = _parse_sources("a:lot=0.01", s.magic)
    with pytest.raises(ValueError, match="وقف «a»"):
        s.validate()


@pytest.mark.parametrize("bad,why", [
    ("lux", "اسم:lot"), ("lux:lot", "مفتاح=قيمة"),
    ("lux:lot=x", "رقم غير مفهوم"), ("lux:zz=1", "لا يُعرف"),
    ("a:lot=1,sl=5;a:lot=2,sl=5", "مكرّر"),
])
def test_يرفض_إعداداً_معطوباً(bad, why):
    with pytest.raises(ValueError, match=why):
        _parse_sources(bad, 26092101)
