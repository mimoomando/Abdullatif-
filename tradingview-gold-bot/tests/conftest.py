import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app.brokers.paper import PaperBroker
from app.config import Settings
from app.trader import Trader

GOLD = {
    "digits": 2, "point": 0.01,
    "volume_min": 0.01, "volume_step": 0.01, "volume_max": 100.0,
    "value_per_price_unit": 100.0, "stops_distance": 0.0,
}


@pytest.fixture
def settings():
    s = Settings()
    s.webhook_secret = "tv-bridge-test-secret-0123456789"
    s.symbol = "XAUUSD"
    s.symbol_map = {"XAUUSD": "XAUUSD"}
    s.lot = 0.01
    s.max_risk_usd = 50.0
    s.min_stop_distance = 0.5
    s.max_stop_distance = 100.0
    s.dry_run = True
    s.validate()
    return s


@pytest.fixture
def broker():
    return PaperBroker(balance=10000.0, spread=0.30,
                       symbol_defaults={"XAUUSD": GOLD})


@pytest.fixture
def trader(settings, broker):
    return Trader(settings, broker)


def buy_alert(secret="tv-bridge-test-secret-0123456789", **over):
    payload = {
        "secret": secret, "signal": "BUY", "ticker": "OANDA:XAUUSD",
        "entry": 4293.50, "sl": 4278.98,
        "tp1": 4303.66, "tp2": 4313.83, "tp3": 4323.99,
        "id": "bar-1",
    }
    payload.update(over)
    return payload
