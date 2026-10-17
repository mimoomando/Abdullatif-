"""
أداةُ تجريبِ الحُرّاس — **تُعيد العطبَ وتسأل: أيصيح الطقم؟**

╔══════════════════════════════════════════════════════════════════╗
║  ⛔⛔⛔ **ولمَ صارت ملفًّا في المستودع — 2026-10-17.**               ║
║                                                                  ║
║  كانت تُكتب في مجلّدٍ مؤقّتٍ كلَّ مرّة، **وأهلكت العملَ ثلاثًا**:      ║
║                                                                  ║
║    10-13  `git checkout -- bot/` بعد كلّ تجربة **والعملُ غيرُ      ║
║           مودَع** ⇒ مُحيت الإضافة، **وثلاثُ تجارب بعدها قالت       ║
║           [سليم] عن حارسٍ غيرِ موجود.**                           ║
║    10-16  وبقايا `__pycache__` قالت [فاشل] عن شجرةٍ نظيفة.        ║
║    10-17  **وأسوأُها**: شُغّلت **في الخلفيّة وأنا أحرّر** ⇒          ║
║           فمحا `checkout` الوسطيُّ وصلَ `observer` كلَّه،            ║
║           **وكان الطقمُ أخضرَ قبلها بثانية.**                      ║
║                                                                  ║
║  ⇒ ⭐⭐⭐ **فصار الدرسُ محروسًا بالكود لا مكتوبًا**: ترفض الأداةُ    ║
║  العملَ على شجرةٍ غيرِ نظيفة، **فلا تُشغَّل إلّا وكلُّ شيءٍ مودَع.**   ║
║  ⚠️ **ولا تُشغَّل في الخلفيّة** — فالتحريرُ أثناءها هو العطبُ نفسُه. ║
╚══════════════════════════════════════════════════════════════════╝

    python tools/trial_guards.py cases.json

وملفُّ الحالات قائمةٌ من `{"name", "file", "old", "new"}`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _clean() -> bool:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    if out:
        print("⛔⛔⛔ الشجرةُ غيرُ نظيفة — **ويُودَع العملُ قبل أن "
              "يُجرَّب العطب.**\n"
              "   فهذه الأداةُ تعمل `git checkout -- .` بين الحالات، "
              "**فتمحو كلَّ غيرِ مودَع.**\n")
        print(out)
        return False
    return True


def _pycache() -> None:
    subprocess.run("find . -name __pycache__ -type d -exec rm -rf {} + "
                   "2>/dev/null", cwd=ROOT, shell=True)


def _suite_passes() -> bool:
    p = subprocess.run([sys.executable, "-m", "unittest", "discover",
                        "-s", "bot/tests", "-q"],
                       cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0


def _plant(rel: str, old: str, new: str) -> bool:
    """
    يزرع العطبَ — **ويرفض الهدفَ غيرَ الوحيد.**

    ⛔ **ولمَ الوحدانيّة شرط؟** جُرِّب `BD_TOLERANCE = 0.0` فصمت
    الطقمُ — **والزرعُ كان قد وقع في التعليق** الذي يشرح القيمة، لا
    في الكود. ⇒ **فهدفٌ يتكرّر عطبٌ في التجريب لا في الحارس.**
    """
    f = ROOT / rel
    s = f.read_text(encoding="utf-8")
    if s.count(old) != 1:
        return False
    f.write_text(s.replace(old, new, 1), encoding="utf-8")
    return True


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__)
        return 1
    cases = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    if not _clean():
        return 1

    silent = []
    for case in cases:
        subprocess.run(["git", "checkout", "--", "."], cwd=ROOT, check=True)
        _pycache()
        if not _plant(case["file"], case["old"], case["new"]):
            print(f"لم يُزرع (لا موضعَ وحيد): {case['name']}")
            continue
        if _suite_passes():
            print(f"⛔⛔ صمت: {case['name']}")
            silent.append(case["name"])
        else:
            print(f"✅ صاح: {case['name']}")

    subprocess.run(["git", "checkout", "--", "."], cwd=ROOT, check=True)
    _pycache()
    print(f"\n⇒ {len(cases) - len(silent)} من {len(cases)} صاحت")
    if silent:
        print("⛔ والصامتةُ تُعالَج أو يُقال لماذا هي ليست عطبًا:")
        for name in silent:
            print(f"   • {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
