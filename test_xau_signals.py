"""فحص قارئ قناة XAU Pro Operator — برسائلها الحقيقية كما وصلت:

    python3 test_xau_signals.py

كل سطر هنا رسالة منقولة حرفياً من صور القناة، لا مخترعة.
"""
import sys

import xau_signals as X

ok = fails = 0


def check(message, want):
    global ok, fails
    found = X.interpret(message)
    one = found["action"]
    if found.get("direction"):
        one += f" {found['direction']}"
    if found.get("entry"):
        one += f" {found['entry']:g}"
    if found.get("sl"):
        one += f" sl{found['sl']:g}"
    if found.get("tps"):
        one += " tp" + "/".join(f"{x:g}" for x in found["tps"])
    if found.get("level"):
        one += f" {found['level']}"
    short = message.replace("\n", " / ")
    short = short if len(short) <= 46 else short[:44] + "…"
    if one == want:
        ok += 1
        print(f"  ✅ «{short}» → {one}")
    else:
        fails += 1
        print(f"  ❌ «{short}» → {one}   (المتوقع {want})")


print("═" * 58)
print("  قارئ XAU Pro Operator")
print("═" * 58)

print("\n[١] التوصية كما تصل — رسالة واحدة مكتملة")
check("XAUUSD Short ALERT 🚨\n\n🔻 Sell : 3854.00\n\n"
      "🛑 SL: 3866.00\n\n🎯 TP1: 3848 | TP2: 3841 | TP3: 3832.00",
      "SIGNAL SELL 3854 sl3866 tp3848/3841/3832")
# من صورة 11 نوفمبر — ولاحظ أن سهم الترويسة أحمر والكلمة buy،
# فالكلمة هي الحَكَم لا السهم
check("XAUUSD Long ALERT 🚨\n\n🔻 buy : 4028.00\n\n"
      "🛑 SL: 4017.00\n\n🎯 TP1: 4034 | TP2: 4042 | TP3: 4055.00",
      "SIGNAL BUY 4028 sl4017 tp4034/4042/4055")
# وبلا زخرفة
check("XAUUSD Short ALERT\nSell 3854\nSL 3866\nTP1 3848",
      "SIGNAL SELL 3854 sl3866 tp3848")

print("\n[٢] ما يتبع التوصية")
check("TP1 Hit ‼️💯👏", "TP_HIT 1")
check("TP1 Hit ‼️💯💯", "TP_HIT 1")
check("TP2 Hit ✅", "TP_HIT 2")
check("TP3 Hit 🎯", "TP_HIT 3")
check("SL Hit", "SL_HIT")
check("Stopped out", "SL_HIT")
check("Move SL to BE", "BREAKEVEN")
check("SL to entry", "BREAKEVEN")
check("Risk free now 👍", "BREAKEVEN")
check("Close the trade", "CLOSE")
check("Exit now", "CLOSE")
check("Book the profit", "CLOSE")

print("\n[٢ب] أوامر الإغلاق كما يكتبونها — والنفيُ لا يُغلق")
# «Close Buy All» وصلت يوم 18 نوفمبر فلم تُفهم. وكلمةُ الاتجاه
# تتوسّط الجملة عندهم، فلا بدّ من قبولها.
for order in ("Close Buy All 🚀👑", "Close All Sell", "Close it now",
              "Close all", "Close position", "close buy all now"):
    check(order, "CLOSE")
# ★ والنفيُ أخطرُ من الجهل: إغلاقٌ لم يُؤمر به يُخرج صفقةً رابحة
for quiet in ("Please don't close it 🙏", "Please don’t close it",
              "Do not close the trade", "Never close it",
              "I will not close the trade", "No closing",
              "Hold, do not close position", "I will close soon"):
    check(quiet, "NONE")

print("\n[٣] الكلام الذي يجب أن يبقى صامتاً")
for quiet in (
    "Hi good morning",
    "Hi",
    "Get ready",
    "60+PIPS 🔥💯🔥",
    "I am Done 🚀 Before CPI",
    "Account management services available DM now @Mariusz_TRD",
    "Only 2 New accounts will manage.",
    "ACCOUNT MANAGEMENT OPEN 📊 Discipline...",
    "",
):
    check(quiet, "NONE")

print("\n[٤] أرقامٌ متناقضة ليست توصية")
# رسالةٌ تحكي عن صفقةٍ ماضية: الوقف تحت الدخول في بيع — مستحيل
check("Sell 3854 SL 3840 TP1 3860", "NONE")
# وهدفٌ فوق الدخول في بيع كذلك
check("XAUUSD Short ALERT\nSell : 3854.00\nSL: 3866.00\nTP1: 3870",
      "NONE")
# أما الشراء فعكسها، وهذه سليمة
check("XAUUSD Long ALERT\nBuy : 3854.00\nSL: 3840.00\nTP1: 3870",
      "SIGNAL BUY 3854 sl3840 tp3870")

print(f"\n{'─' * 58}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
