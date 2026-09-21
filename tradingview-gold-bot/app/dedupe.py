"""
حارس التكرار.

تيرادينغ فيو تعيد إرسال التنبيه إن لم يصلها ردّ سريع، وقد يصل
التنبيه الواحد مرتين. وفتح الصفقة مرتين خسارة مضاعفة، فيُحفظ أثر
كل تنبيه نُفِّذ مدةً، ويُردّ ما تكرّر خلالها.
"""

import threading
import time


class Dedupe:
    def __init__(self, ttl_seconds=300, max_entries=500):
        self.ttl = float(ttl_seconds)
        self.max_entries = int(max_entries)
        self._seen = {}
        self._lock = threading.Lock()

    def check_and_add(self, fingerprint, now=None):
        """صحيح إن كان جديداً فسُجّل، وخطأ إن سبق تنفيذه."""
        now = time.time() if now is None else now
        with self._lock:
            self._evict(now)
            if fingerprint in self._seen:
                return False
            self._seen[fingerprint] = now
            if len(self._seen) > self.max_entries:
                oldest = sorted(self._seen.items(), key=lambda kv: kv[1])
                for key, _ in oldest[: len(self._seen) - self.max_entries]:
                    self._seen.pop(key, None)
            return True

    def _evict(self, now):
        expired = [k for k, seen_at in self._seen.items() if now - seen_at > self.ttl]
        for key in expired:
            self._seen.pop(key, None)

    def clear(self):
        with self._lock:
            self._seen.clear()
