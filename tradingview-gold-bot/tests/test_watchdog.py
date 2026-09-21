import pytest

from app.watchdog import SilenceWatchdog

HOUR = 3600.0


class FakeClock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, hours):
        self.now += hours * HOUR


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)
        return True


class FakeQuotes:
    """وسيط لا يعرف إلا زمن آخر سعر — وهو كل ما يحتاجه الحارس."""

    name = "fake"

    def __init__(self, quote=100.0, raises=False):
        self.quote = quote
        self.raises = raises

    def quote_time(self, symbol):
        if self.raises:
            raise RuntimeError("لا اتصال بالوسيط")
        return self.quote


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def notifier():
    return FakeNotifier()


def build(settings, clock, notifier, broker=None, hours=48.0):
    settings.silence_hours = hours
    settings.silence_repeat_hours = 24.0
    settings.stale_quote_minutes = 10.0
    return SilenceWatchdog(settings, broker or FakeQuotes(), notifier, clock=clock)


def moving(watchdog, clock, broker):
    """يُقدّم السوق: سعر جديد مع مرور الوقت، فلا يُحسب مقفلاً."""
    broker.quote += 1
    return watchdog.check()


def test_الصمت_القصير_لا_ينبّه(settings, clock, notifier):
    w = build(settings, clock, notifier)
    clock.advance(10)
    assert w.check()["state"] == "ok"
    assert notifier.sent == []


def test_ينبّه_بعد_طول_الصمت_والسوق_يتحرك(settings, clock, notifier):
    broker = FakeQuotes()
    w = build(settings, clock, notifier, broker)

    clock.advance(20)
    moving(w, clock, broker)          # السوق يتحرك ولا صمت بعد

    clock.advance(30)                 # المجموع خمسون ساعة
    result = moving(w, clock, broker)

    assert result["state"] == "warned"
    assert len(notifier.sent) == 1
    assert "ما وصلت أي إشارة" in notifier.sent[0]
    assert "GOLD" in notifier.sent[0] or settings.symbol in notifier.sent[0]


def test_السوق_المقفل_لا_يُنبَّه_عليه(settings, clock, notifier):
    # أسعار الوسيط متجمدة: نهاية أسبوع لا عطب
    broker = FakeQuotes(quote=4300.0)
    w = build(settings, clock, notifier, broker)

    w.check()                         # أول رصد للسعر
    clock.advance(60)                 # ستون ساعة والسعر لم يتحرك

    result = w.check()
    assert result["state"] == "market_closed"
    assert notifier.sent == []


def test_ينبّه_بعد_إقفال_طويل_إن_تحرك_السوق_ولم_تصل_إشارة(settings, clock, notifier):
    broker = FakeQuotes(quote=4300.0)
    w = build(settings, clock, notifier, broker)

    w.check()
    clock.advance(60)
    assert w.check()["state"] == "market_closed"

    # فُتح السوق وتحرّك السعر، والإشارات ما زالت غائبة
    clock.advance(1)
    assert moving(w, clock, broker)["state"] == "warned"
    assert len(notifier.sent) == 1


def test_لا_يكرر_التنبيه_قبل_مدة_التكرار(settings, clock, notifier):
    broker = FakeQuotes()
    w = build(settings, clock, notifier, broker)

    clock.advance(50)
    assert moving(w, clock, broker)["state"] == "warned"

    clock.advance(5)
    assert moving(w, clock, broker)["state"] == "already_warned"
    assert len(notifier.sent) == 1


def test_يكرر_التنبيه_بعد_مضي_مدة_التكرار(settings, clock, notifier):
    broker = FakeQuotes()
    w = build(settings, clock, notifier, broker)

    clock.advance(50)
    moving(w, clock, broker)

    clock.advance(25)                 # تجاوزت الأربع والعشرين
    assert moving(w, clock, broker)["state"] == "warned"
    assert len(notifier.sent) == 2


def test_وصول_إشارة_يصمت_الحارس_ويبشّر_بالعودة(settings, clock, notifier):
    broker = FakeQuotes()
    w = build(settings, clock, notifier, broker)

    clock.advance(50)
    moving(w, clock, broker)
    assert len(notifier.sent) == 1

    w.signal_received()
    assert len(notifier.sent) == 2
    assert "عادت الإشارات" in notifier.sent[1]

    clock.advance(10)
    assert moving(w, clock, broker)["state"] == "ok"


def test_وصول_إشارة_بلا_سابق_تنبيه_لا_يرسل_شيئاً(settings, clock, notifier):
    w = build(settings, clock, notifier)
    w.signal_received()
    assert notifier.sent == []


def test_صفر_ساعات_يطفئ_الحارس(settings, clock, notifier):
    w = build(settings, clock, notifier, hours=0)
    clock.advance(500)
    assert w.check()["state"] == "disabled"
    assert w.enabled is False
    assert notifier.sent == []
    assert w.start() is False


def test_وسيط_لا_يعرف_زمن_السعر_يُحمل_على_أن_السوق_مفتوح(settings, clock, notifier):
    class Unknown:
        name = "unknown"

        def quote_time(self, symbol):
            return None

    w = build(settings, clock, notifier, Unknown())
    clock.advance(50)
    assert w.check()["state"] == "warned"


def test_عطب_الوسيط_لا_يُسقط_الحارس(settings, clock, notifier):
    w = build(settings, clock, notifier, FakeQuotes(raises=True))
    clock.advance(50)
    # يُحمل على أن السوق مفتوح فيُنبَّه، ولا يرتفع الاستثناء
    assert w.check()["state"] == "warned"
    assert len(notifier.sent) == 1


def test_الحالة_تُعرض_للفحص(settings, clock, notifier):
    w = build(settings, clock, notifier)
    clock.advance(6)
    state = w.status()
    assert state["enabled"] is True
    assert state["quiet_hours"] == 6.0
    assert state["threshold_hours"] == 48.0
    assert state["warned"] is False
