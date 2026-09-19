"""
قفلُ النسخة الواحدة — **نسختان تكتبان سجلًّا واحدًا تُفسدانه.**

╔══════════════════════════════════════════════════════════════════╗
║  والعطب وقع فعلًا (2026-09-19):                                   ║
║                                                                  ║
║  حدّث المستخدم الكود وشغّل البوت في نافذةٍ جديدة — و**النافذة      ║
║  القديمة ما زالت تعمل**. فصار مسجّلان يُلحقان في                  ║
║  `runs/decisions.jsonl` معًا، وأحدُهما يشغّل الكود **قبل**         ║
║  إصلاح جدول الامتدادات.                                          ║
║                                                                  ║
║  ⇒ سطورٌ متداخلة، وقراراتٌ مكرّرة، ونصفُ السجلّ محسوبٌ بخطأ.        ║
╚══════════════════════════════════════════════════════════════════╝

وهو انتبه وسأل. **ولا يصحّ أن يعتمد الأمرُ على انتباهه** — فالنافذتان
تبدوان سواءً، والسجلّ لا يشكو.

⭐ **ولماذا قفلُ نظامٍ لا ملفُّ PID؟** لأنّ ملفّ الـPID يبقى بعد
انقطاع الكهرباء فيمنع التشغيل بلا سبب، ويحتاج فحصَ «هل العمليّة حيّة»
— و`os.kill(pid, 0)` على ويندوز **يقتل العمليّة** لا يسأل عنها.
وقفلُ النظام يُطلَق تلقائيًّا حين تموت العمليّة، كيفما ماتت.
"""

from __future__ import annotations

import os
from typing import Optional

# بايتُ القفل واحد، وما بعده وصفٌ يقرؤه القادمُ المرفوض.
_LOCK_BYTE = 1


class AlreadyRunning(RuntimeError):
    """نسخةٌ أخرى تمسك القفل — ومعها وصفُها إن أمكن قراءته."""


class SingleInstance:
    """
    قفلٌ يُمسَك ما دامت العمليّة حيّة، ويُطلَق حين تموت — كيفما ماتت.

    يُستعمل مديرَ سياق:

        with SingleInstance(path):
            ...
    """

    def __init__(self, path: str):
        self.path = path
        self._fd: Optional[int] = None

    # ─────────────────────────── النظام ───────────────────────────

    @staticmethod
    def _lock(fd: int) -> None:
        """يقفل البايت الأوّل — أو يرفع استثناءً إن كان مقفولًا."""
        try:                                   # ويندوز
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, _LOCK_BYTE)
            return
        except ImportError:
            pass
        import fcntl                            # لينكس وماك
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(fd: int) -> None:
        try:
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, _LOCK_BYTE)
            return
        except ImportError:
            pass
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)

    # ─────────────────────────── الواجهة ───────────────────────────

    def note(self) -> str:
        """وصفُ من يمسك القفل — أو نصٌّ فارغ إن تعذّر."""
        try:
            with open(self.path, "rb") as fh:
                fh.seek(_LOCK_BYTE)
                return fh.read(200).decode("utf-8", "replace").strip()
        except OSError:
            return ""

    def acquire(self, note: str = "") -> None:
        """
        يمسك القفل — أو يرفع `AlreadyRunning`.

        ⚠️ ويُقرأ الوصفُ **قبل** الرفع، لأنّ الرسالة بلا «متى بدأت
        الأخرى» لا تدلّ المستخدم على أيّ نافذةٍ يغلق.
        """
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)

        # ⚠️ البايتُ الأوّل يُكتب **قبل** القفل: قفلُ ويندوز على مدًى
        # لا وجود له سلوكٌ لا يُعتمد عليه.
        if os.fstat(fd).st_size < _LOCK_BYTE:
            os.write(fd, b"#")

        try:
            self._lock(fd)
        except OSError:
            held = self.note()
            os.close(fd)
            raise AlreadyRunning(held) from None

        # والوصفُ بعده — ولا تُمَسّ البايتُ الأوّل، فالقفل عليها.
        blob = note.encode("utf-8")[:200]
        os.lseek(fd, _LOCK_BYTE, os.SEEK_SET)
        os.write(fd, blob)
        os.ftruncate(fd, _LOCK_BYTE + len(blob))
        self._fd = fd

    def release(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            self._unlock(fd)
        except OSError:
            pass                                # الموتُ يُطلقه على كلّ حال
        try:
            os.close(fd)
        except OSError:
            pass

    def __enter__(self) -> "SingleInstance":
        return self

    def __exit__(self, *exc) -> None:
        self.release()
