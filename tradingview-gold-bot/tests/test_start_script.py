"""
حارس على ملف التشغيل.

عربيٌّ واحد في ملف ‎.bat‎ يكسره كله: ويندوز يقرأ الملف بالترميز
القديم قبل أن يعمل ‎chcp 65001‎، فتنقسم بايتات UTF-8 إلى كلمات لا
معنى لها ويسقط كل سطر بعدها بـ "is not recognized as an internal
or external command". وقع هذا فعلاً، فصار له اختبار.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
START = ROOT / "start.bat"


def test_ملف_التشغيل_موجود():
    assert START.is_file()


def test_ملف_التشغيل_لاتيني_بالكامل():
    raw = START.read_bytes()
    if raw.isascii():
        return
    text = raw.decode("utf-8", "replace")
    bad = [
        f"سطر {n}: {line.strip()}"
        for n, line in enumerate(text.splitlines(), start=1)
        if not line.isascii()
    ]
    raise AssertionError(
        "ملف الباتش فيه محارف غير لاتينية، وهي تكسره على ويندوز:\n"
        + "\n".join(bad)
    )


def test_يشغّل_الجسر_والنفق_معاً():
    text = START.read_text(encoding="ascii")
    assert 'start "TV Bridge"' in text
    assert 'start "TV Tunnel"' in text
    assert "python run.py" in text


def test_يتحقق_مما_يلزمه_قبل_التشغيل():
    text = START.read_text(encoding="ascii")
    assert "cloudflared.exe" in text
    assert ".env" in text
