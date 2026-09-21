"""
الخادم الذي تطرقه تيرادينغ فيو.

تيرادينغ فيو لا ترسل إلا إلى المنفذ 80 أو 443، وترسل نصاً خاماً في
جسم الطلب لا استمارة. فالقراءة هنا من الجسم كما وصل، ثم كلمة السر،
ثم التنفيذ. وما لم تُقبل كلمة السر لا يُقرأ الباقي أصلاً.
"""

import hmac
import logging
import time
from collections import deque

from fastapi import FastAPI, Request, Response

from app.signals import SignalError, parse
from app.brokers.base import BrokerError
from app.risk import RiskError

log = logging.getLogger("bridge.server")


def create_app(settings, trader):
    app = FastAPI(title="جسر تيرادينغ فيو ← ميتاتريدر", docs_url=None, redoc_url=None)
    recent = deque(maxlen=20)

    @app.get("/health")
    def health():
        return {
            "ok": True,
            "dry_run": settings.dry_run,
            "enabled": settings.enabled,
            "symbol": settings.symbol,
            "broker": trader.broker.name,
        }

    @app.post(settings.webhook_path)
    async def webhook(request: Request):
        raw = (await request.body()).decode("utf-8", "replace").strip()
        received_at = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            signal = parse(raw)
        except SignalError as exc:
            # كلمة السر داخل الرسالة، فما لم تُقرأ الرسالة لم تُعرف.
            # لا يُسجَّل النص كاملاً كيلا يُكتب سرٌّ في السجل.
            log.warning("رسالة مرفوضة: %s", exc)
            recent.append({"at": received_at, "status": "rejected", "reason": str(exc)})
            return Response(f"رسالة غير مفهومة: {exc}", status_code=400)

        if not _secret_ok(settings.webhook_secret, signal.secret, request):
            log.warning("كلمة سر خاطئة من %s", request.client.host if request.client else "?")
            recent.append({"at": received_at, "status": "unauthorized"})
            return Response("كلمة السر خاطئة", status_code=401)

        entry = {"at": received_at, "kind": signal.kind, "ticker": signal.ticker,
                 "entry": signal.entry, "sl": signal.sl, "tps": signal.tps}
        try:
            result = trader.handle(signal)
        except (RiskError, BrokerError) as exc:
            log.error("لم تُنفَّذ [%s]: %s", signal.kind, exc)
            entry.update(status="failed", reason=str(exc))
            recent.append(entry)
            if trader.notifier:
                trader.notifier.send(f"⚠️ لم تُنفَّذ إشارة {signal.kind}\n{exc}")
            return Response(f"لم تُنفَّذ: {exc}", status_code=422)
        except Exception as exc:                        # noqa: BLE001
            log.exception("عطب غير متوقع أثناء تنفيذ %s", signal.kind)
            entry.update(status="error", reason=str(exc))
            recent.append(entry)
            if trader.notifier:
                trader.notifier.send(f"🛑 عطب أثناء تنفيذ {signal.kind}\n{exc}")
            return Response("عطب داخلي", status_code=500)

        entry.update(status=result.get("status"), result=result)
        recent.append(entry)
        return result

    @app.get("/recent")
    def recent_alerts(secret: str = ""):
        """آخر ما وصل من تنبيهات — لمعرفة صيغة رسالة المؤشر وتصحيحها."""
        if not _constant_equal(settings.webhook_secret, secret):
            return Response("كلمة السر خاطئة", status_code=401)
        return {"count": len(recent), "alerts": list(recent)}

    return app


def _secret_ok(expected, from_body, request):
    if _constant_equal(expected, from_body):
        return True
    header = request.headers.get("x-webhook-secret", "")
    return _constant_equal(expected, header)


def _constant_equal(expected, given):
    """
    مقارنة لا يتغيّر زمنها بعدد الحروف المتطابقة.

    تُقارن البايتات لا النصوص: ``compare_digest`` ترفع خطأً على أي
    حرف غير لاتيني، فكلمة سر عربية كانت تُسقط الخادم عند كل تنبيه.
    """
    if not expected or not given:
        return False
    return hmac.compare_digest(str(expected).encode("utf-8"),
                               str(given).encode("utf-8"))
