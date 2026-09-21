"""
إشعار تيليغرام.

لا يُسمح لعطبٍ هنا أن يُسقط صفقة: الإشعار خبر عن التنفيذ لا جزء
منه، فكل خطأ فيه يُبتلع ويُسجَّل.
"""

import logging

log = logging.getLogger("bridge.notify")


class Telegram:
    def __init__(self, token="", chat_id="", timeout=10):
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    @property
    def enabled(self):
        return bool(self.token and self.chat_id)

    def send(self, text):
        if not self.enabled:
            return False
        try:
            import requests

            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                log.warning("تيليغرام ردّ %s: %s", response.status_code, response.text[:200])
                return False
            return True
        except Exception as exc:                      # noqa: BLE001
            log.warning("تعذّر إرسال إشعار تيليغرام: %s", exc)
            return False
