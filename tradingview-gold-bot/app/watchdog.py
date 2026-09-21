"""
حارس الصمت.

نظام آلي يتوقف بصمت أسوأ من نظام يعطب بصوت: تنبيهات تيرادينغ فيو
على خطة Essential تنتهي صلاحيتها بعد شهرين، فتسكت القناة ويبقى
البريدج يعمل وينصت، وصاحب الحساب يحسبه يتداول وهو لا يتداول.

فيراقب هذا الحارس متى وصل آخر تنبيه. وإن طال السكوت نبّه على
تيليغرام.

وأهم ما فيه أنه يفرّق بين سكوتين:

  السوق مقفل   → أسعار الوسيط متجمدة، ولا تنبيه يُنتظر أصلاً. صمت
                  طبيعي لا يُنبَّه عليه، وإلا صاح كل نهاية أسبوع
                  حتى يُتعوَّد عليه فيضيع الغرض منه كله.

  السوق يتحرك  → الأسعار تتغير والتنبيهات لا تصل. هذا هو العطب.

ولا يقارن زمن الوسيط بساعتنا — بين الساعتين فرق — بل يقارن زمن
الوسيط بنفسه: إن لم يتقدم مدةً فالسوق مقفل.
"""

import logging
import threading
import time

log = logging.getLogger("bridge.watchdog")


class SilenceWatchdog:
    def __init__(self, settings, broker, notifier=None, clock=time.time):
        self.settings = settings
        self.broker = broker
        self.notifier = notifier
        self.clock = clock

        self.silence_seconds = settings.silence_hours * 3600.0
        self.repeat_seconds = settings.silence_repeat_hours * 3600.0
        self.stale_quote_seconds = settings.stale_quote_minutes * 60.0
        self.interval_seconds = settings.silence_check_minutes * 60.0

        now = self.clock()
        self._last_signal_at = now
        self._warned_at = None
        self._last_quote = None
        self._last_quote_moved_at = None

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    @property
    def enabled(self):
        return self.silence_seconds > 0

    # ── ما يغذّيه ──

    def signal_received(self):
        """يُنادى عند كل تنبيه تجاوز كلمة السر، نُفِّذ أو رُدّ.

        فالمقصود قياس حياة القناة لا نجاح الصفقة: تنبيه وصل ورُدّ
        لتجاوزه حدود المخاطرة دليلٌ أن تيرادينغ فيو ما زالت تتكلم.
        """
        with self._lock:
            was_warned = self._warned_at is not None
            self._last_signal_at = self.clock()
            self._warned_at = None
        if was_warned:
            self._announce("✅ عادت الإشارات تصل — القناة تعمل من جديد.")
            log.info("عادت الإشارات بعد انقطاع")

    # ── الفحص ──

    def check(self):
        """فحصة واحدة. يعيد ما فعله وسببه."""
        if not self.enabled:
            return {"state": "disabled"}

        now = self.clock()

        # يُرصد السعر في كل فحصة لا عند الحاجة وحدها: لو أُجِّل الرصد
        # إلى ما بعد تجاوز حد الصمت لما كان للحارس تاريخٌ يقارن به،
        # فيظن السوق متحركاً وينبّه في أول نهاية أسبوع.
        quotes_frozen = self._observe_quote(now)

        with self._lock:
            quiet_for = now - self._last_signal_at
            warned_at = self._warned_at

        if quiet_for < self.silence_seconds:
            return {"state": "ok", "quiet_hours": round(quiet_for / 3600.0, 2)}

        if quotes_frozen:
            return {"state": "market_closed",
                    "quiet_hours": round(quiet_for / 3600.0, 2)}

        if warned_at is not None and (now - warned_at) < self.repeat_seconds:
            return {"state": "already_warned",
                    "quiet_hours": round(quiet_for / 3600.0, 2)}

        with self._lock:
            self._warned_at = now

        hours = quiet_for / 3600.0
        self._announce(
            f"⚠️ ما وصلت أي إشارة منذ {hours:.0f} ساعة، والسوق يتحرك.\n"
            f"راجع تنبيهات تيرادينغ فيو — قد تكون انتهت صلاحيتها.\n"
            f"الرمز: {self.settings.symbol}"
        )
        log.warning("صمت %.1f ساعة والسوق يتحرك — أُرسل تنبيه", hours)
        return {"state": "warned", "quiet_hours": round(hours, 2)}

    def _observe_quote(self, now):
        """
        يرصد زمن آخر سعر، ويعيد: أمتجمدة الأسعار مدةً تكفي؟

        يُقارن زمن الوسيط بنفسه لا بساعتنا، فلا يفسده فرق الساعات.
        وإن تعذّرت معرفته حُمل الأمر على أن السوق مفتوح، فالتنبيه
        في غير محله أهون من حارس لا ينبّه أبداً.
        """
        try:
            quote = self.broker.quote_time(self.settings.symbol)
        except Exception as exc:                        # noqa: BLE001
            log.debug("تعذّرت قراءة زمن السعر: %s", exc)
            return False

        if quote is None:
            return False

        if quote != self._last_quote:
            self._last_quote = quote
            self._last_quote_moved_at = now
            return False

        if self._last_quote_moved_at is None:
            self._last_quote_moved_at = now
            return False

        return (now - self._last_quote_moved_at) >= self.stale_quote_seconds

    # ── الحالة والخيط ──

    def status(self):
        with self._lock:
            quiet_for = self.clock() - self._last_signal_at
            return {
                "enabled": self.enabled,
                "quiet_hours": round(quiet_for / 3600.0, 2),
                "threshold_hours": self.settings.silence_hours,
                "warned": self._warned_at is not None,
            }

    def start(self):
        if not self.enabled or self._thread is not None:
            return False
        self._thread = threading.Thread(
            target=self._loop, name="silence-watchdog", daemon=True
        )
        self._thread.start()
        log.info("حارس الصمت يعمل: ينبّه بعد %s ساعة صمت",
                 self.settings.silence_hours)
        return True

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(self.interval_seconds):
            try:
                self.check()
            except Exception:                           # noqa: BLE001
                # الحارس لا يُسقط البريدج بحال: عطبه يُسجَّل ويُمضى
                log.exception("عطب في حارس الصمت")

    def _announce(self, text):
        if self.notifier:
            self.notifier.send(text)
