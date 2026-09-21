import json

import pytest
from fastapi.testclient import TestClient

from app.server import create_app
from tests.conftest import buy_alert

SECRET = "tv-bridge-test-secret-0123456789"


@pytest.fixture
def client(settings, trader):
    return TestClient(create_app(settings, trader))


def post(client, payload):
    return client.post("/webhook", content=json.dumps(payload).encode("utf-8"))


def test_الصحة_تُظهر_الوضع(client):
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["dry_run"] is True
    assert body["broker"] == "paper"


def test_تنبيه_سليم_يفتح_صفقة(client, broker):
    response = post(client, buy_alert())
    assert response.status_code == 200
    assert response.json()["status"] == "opened"
    assert len(broker.positions(symbol="XAUUSD")) == 1


def test_كلمة_سر_خاطئة_تُردّ_ولا_تفتح_شيئاً(client, broker):
    response = post(client, buy_alert(secret="خطأ"))
    assert response.status_code == 401
    assert broker.positions(symbol="XAUUSD") == []


def test_بلا_كلمة_سر_تُردّ(client, broker):
    payload = buy_alert()
    payload.pop("secret")
    assert post(client, payload).status_code == 401
    assert broker.positions(symbol="XAUUSD") == []


def test_كلمة_السر_تُقبل_من_الترويسة_أيضاً(client, broker):
    payload = buy_alert()
    payload.pop("secret")
    response = client.post("/webhook", content=json.dumps(payload).encode("utf-8"),
                           headers={"x-webhook-secret": SECRET})
    assert response.status_code == 200
    assert len(broker.positions(symbol="XAUUSD")) == 1


def test_رسالة_غير_مفهومة_تُردّ_بأربعمئة(client):
    response = client.post("/webhook", content=b"buy gold")
    assert response.status_code == 400


def test_صفقة_تتجاوز_الحدود_تُردّ_بلا_عطب(settings, client, broker):
    settings.lot = 0.50
    response = post(client, buy_alert())
    assert response.status_code == 422
    assert "الحد المسموح" in response.text
    assert broker.positions(symbol="XAUUSD") == []


def test_سجل_آخر_التنبيهات_محمي_بكلمة_السر(client):
    post(client, buy_alert())
    assert client.get("/recent").status_code == 401
    body = client.get("/recent", params={"secret": SECRET}).json()
    assert body["count"] == 1
    assert body["alerts"][0]["kind"] == "BUY"


class _Watchdog:
    """حارس صامت يُحصي ما يُغذّى به، لا أكثر."""

    def __init__(self):
        self.fed = 0

    def signal_received(self):
        self.fed += 1

    def status(self):
        return {"enabled": True, "quiet_hours": 0.0,
                "threshold_hours": 48.0, "warned": False}


def test_حالة_الحارس_تظهر_في_الصحة(settings, trader):
    client = TestClient(create_app(settings, trader, _Watchdog()))
    body = client.get("/health").json()
    assert body["silence_watch"]["enabled"] is True
    assert body["silence_watch"]["threshold_hours"] == 48.0


def test_كل_تنبيه_مقبول_يغذّي_الحارس(settings, trader):
    watchdog = _Watchdog()
    client = TestClient(create_app(settings, trader, watchdog))

    client.post("/webhook", content=json.dumps(buy_alert()).encode("utf-8"))
    assert watchdog.fed == 1


def test_كلمة_السر_الخاطئة_لا_تغذّي_الحارس(settings, trader):
    watchdog = _Watchdog()
    client = TestClient(create_app(settings, trader, watchdog))

    client.post("/webhook",
                content=json.dumps(buy_alert(secret="خطأ")).encode("utf-8"))
    assert watchdog.fed == 0


def test_تنبيه_مردود_لتجاوز_الحدود_يغذّي_الحارس(settings, trader):
    # القناة حية وإن رُدّت الصفقة: هذا هو المقصود بقياس الصمت
    settings.lot = 0.50
    watchdog = _Watchdog()
    client = TestClient(create_app(settings, trader, watchdog))

    response = client.post("/webhook",
                           content=json.dumps(buy_alert()).encode("utf-8"))
    assert response.status_code == 422
    assert watchdog.fed == 1
