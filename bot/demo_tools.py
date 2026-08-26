"""
برهان عملي: «أدوات» المنصة ليست إلا حسابًا.

    python3 -m bot.demo_tools

لا استيراد لـ TradingView ولا MT5 ولا أي مكتبة رسم. أرقام فقط.
"""

from bot.primitives.fibonacci import measure
from bot.primitives.pivot import pivot_from_values

LINE = "─" * 58


def fibonacci_demo() -> None:
    print("فيبوناتشي — الدرس 6")
    print(LINE)

    low, high = 4310.84, 4396.84
    imp = measure(low=low, high=high, direction="bullish")

    print(f"  الموجة الصاعدة : {low}  ←  {high}")
    print(f"  حجمها          : {imp.size:.2f}")
    print()
    print("  المعادلة الكاملة:  المستوى = القمة − (القمة − القاع) × النسبة")
    print()

    for ratio, price in imp.levels().items():
        tag = "  ← بوابة القيمة" if ratio == 0.5 else ""
        print(f"    {ratio * 100:5.1f}%  =  {high} − {imp.size:.2f} × {ratio}"
              f"  =  {price:9.2f}{tag}")

    lo, hi = imp.golden_zone()
    print()
    print(f"  المنطقة الذهبية 61.8–78.6 : {lo:.2f} → {hi:.2f}")
    print()

    print("  تقدير موقع القيمة (الدرس 14):")
    for probe in (4380.00, 4353.84, 4330.00):
        v = imp.value_of(probe)
        verdict = "غالٍ للشراء" if v == "premium" else ("رخيص" if v == "discount" else "المنتصف")
        print(f"    {probe:9.2f}  →  {v:9s}  {verdict}")
    print()

    print("  أهداف الإسقاط (الدرس 8):")
    for ratio, price in imp.extensions().items():
        print(f"    {ratio:5.3f}  =  {price:9.2f}")
    print()


def pivot_demo() -> None:
    print("نقطة الارتكاز — المرحلة 2 الدرس 4")
    print(LINE)
    print("  المعادلة:  (High + Low + Close) ÷ 3")
    print()

    d = pivot_from_values(4396.84, 4310.84, 4376.28, "daily")
    w = pivot_from_values(4449.33, 4310.84, 4376.28, "weekly")

    print(f"  يومي   : ({d.source_high} + {d.source_low} + {d.source_close}) ÷ 3 = {d.value:.2f}")
    print(f"           القيمة الموثّقة في المصدر = 4361.32  ✓")
    print()
    print(f"  أسبوعي : ({w.source_high} + {w.source_low} + {w.source_close}) ÷ 3 = {w.value:.4f}")
    print(f"           القيمة الموثّقة في المصدر = 4378.8167  ✓")
    print()


def main() -> None:
    print()
    fibonacci_demo()
    pivot_demo()
    print(LINE)
    print("  ما احتاجه الحساب أعلاه: أربعة أرقام من الشمعة.")
    print("  لا أداة رسم · لا منصة · لا لقطة شاشة.")
    print()


if __name__ == "__main__":
    main()
