"""
إقلاع البريدج.

    python run.py

يقرأ الإعدادات، ويختار الوسيط: الورقي ما دام DRY_RUN=true، وميتاتريدر
حين يُطفأ. ويطبع عند الإقلاع ما يكفي لمعرفة أي وضع يعمل، فلا يبقى شك
حين تُفحص صفقة على حساب حقيقي.
"""

import logging
import sys

import uvicorn

from app.brokers.paper import PaperBroker
from app.config import Settings
from app.notify import Telegram
from app.server import create_app
from app.trader import Trader
from app.watchdog import SilenceWatchdog


def build_logger(log_file):
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def build_broker(settings):
    if settings.dry_run:
        return PaperBroker(
            symbol_defaults={settings.symbol: {
                "digits": 2, "point": 0.01,
                "volume_min": 0.01, "volume_step": 0.01, "volume_max": 100.0,
                "value_per_price_unit": 100.0, "stops_distance": 0.0,
            }},
        )
    from app.brokers.mt5 import MT5Broker

    return MT5Broker(
        login=settings.mt5_login,
        password=settings.mt5_password,
        server=settings.mt5_server,
        path=settings.mt5_path,
        slippage_points=settings.slippage_points,
        magic=settings.magic,
    )


def main():
    try:
        settings = Settings.load()
    except ValueError as exc:
        print(f"خطأ في الإعدادات: {exc}", file=sys.stderr)
        return 2

    build_logger(settings.log_file)
    log = logging.getLogger("bridge")

    broker = build_broker(settings)
    account = broker.connect()

    mode = "🧪 تجريبي — لا تُفتح صفقات حقيقية" if settings.dry_run else "🔴 حقيقي"
    log.info("الوضع: %s", mode)
    log.info("الوسيط: %s · الرمز: %s · اللوت: %s", broker.name, settings.symbol, settings.lot)
    if account is not True and account is not None:
        log.info("الحساب: %s · الرصيد: %s", getattr(account, "login", "?"),
                 getattr(account, "balance", "?"))
    log.info("ينصت على %s:%s%s", settings.host, settings.port, settings.webhook_path)

    notifier = Telegram(settings.telegram_token, settings.telegram_chat_id)
    if notifier.enabled:
        notifier.send(f"البريدج يعمل\n{mode}\nالرمز {settings.symbol} · اللوت {settings.lot}")

    watchdog = SilenceWatchdog(settings, broker, notifier)
    if watchdog.start():
        log.info("حارس الصمت: ينبّه بعد %s ساعة بلا إشارة والسوق يتحرك",
                 settings.silence_hours)

    app = create_app(settings, Trader(settings, broker, notifier), watchdog)
    try:
        uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
    finally:
        watchdog.stop()
        broker.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
