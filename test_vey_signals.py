"""فحص قارئ قناة VEY GOLD VIP — برسائلها الحقيقية كما وصلت:

    python3 test_vey_signals.py

كل سطر هنا رسالة منقولة حرفياً من صور القناة، لا مخترعة.
"""
import sys
import vey_signals as V

ok = fails = 0


def check(message, want, pending=None):
    global ok, fails
    acts = V.interpret_all(message, pending)
    parts = []
    for a in acts:
        one = a["action"]
        if a.get("direction"):
            one += f" {a['direction']}"
        if a.get("levels"):
            one += " " + "/".join(f"{x:g}" for x in a["levels"])
        if a.get("price") is not None:
            one += f" {a['price']:g}"
        parts.append(one)
    actual = " + ".join(parts) if parts else "NONE"
    short = message.replace("\n", " / ")
    short = short if len(short) <= 44 else short[:42] + "…"
    if actual == want:
        ok += 1
        print(f"  ✅ «{short}» → {actual}")
    else:
        fails += 1
        print(f"  ❌ «{short}» → {actual}   (المتوقع {want})")


print("[١] إعلان الاتجاه — الأرقام تأتي بعده")
check("»» BUY NOW ««", "SIGNAL BUY")
check("»» SELL NOW ««", "SIGNAL SELL")
check("BUY NOW", "SIGNAL BUY")

print("\n[٢] الأرقام — صفقة عند كل واحد")
check("4005-4010", "LEVELS BUY 4005/4010", pending="BUY")
check("4021-4026", "LEVELS SELL 4021/4026", pending="SELL")
check("4000-3995", "LEVELS BUY 3995/4000", pending="BUY")
check("4136-4141", "LEVELS SELL 4136/4141", pending="SELL")
# ترتيبها تصاعدي دائماً مهما كُتبت
check("4070-4065", "LEVELS BUY 4065/4070", pending="BUY")
# بلا اتجاه سابق: أرقامٌ وحدها لا تفتح شيئاً
check("4005-4010", "NONE")

print("\n[٣] الأوامر المعلّقة — كل شيء في رسالة واحدة")
check("BUY LIMIT 4000-3995", "LEVELS BUY 3995/4000")
check("SELL LIMIT 4110-4115", "LEVELS SELL 4110/4115")
check("sell 4110-4115", "LEVELS SELL 4110/4115")

print("\n[٤] الوقف")
check("SL 3986.1", "SET_STOP 3986.1")
check("sl 4054", "SET_STOP 4054")
check("sl 4050", "SET_STOP 4050")
check("We moved the sl to 3983 due to the unfavorable closing "
      "of the h1 candle", "SET_STOP 3983")
# بلا رقم لا وقف — وإلا وُضع وقفٌ من رقمٍ لا علاقة له
check("WE ARE WAITING FOR TP OR SL", "NONE")
check("WE CHANGED SL TO ACCOUNT FOR VOLATILITY", "NONE")

print("\n[٥] التأمين — علامة الزائد تفصل الحدث عن الخطة")
check("+70 PIPS B/E ✅\n (we will neutralize) ✅", "BREAKEVEN")
check("TP HIT 📌 ✅\n+50 PIPS B/E ✅\n (destroy) ✅", "BREAKEVEN")
check("+BE OKAY", "BREAKEVEN")
# ★ رسالة الأهداف تحمل B/E وهي خطة لا حدث: تصل قبل أي ربح
check("🔥Tp 50-70 PIPS B/E ✅\n🔥Tp1 100PIPS 📌✅\n"
      "🔥Tp2 150PIPS 📌✅\n🔥Tp3 200PIPS 📌✅\n🔥Tp4 OPEN 📌✅", "NONE")

print("\n[٦] الإغلاق")
check("TP 1 HIT 🎯 100PIPS\n\nWE CLOSE 60-70% OF THE DEALS AND KEEP "
      "THE REMAINING PART TO THE SAVE PRICE✅", "CLOSE_ALL")
check("TP1 HIT", "CLOSE_ALL")
check("CLOSE 60-70% OF POSITIONS WE WILL DO THE REST AS BE AND "
      "WAIT FOR TP4✅", "CLOSE_ALL")
# «TP1 150P OKAY» تعليمات لا إغلاق
check("TP1 150P OKAY", "NONE")
check("TP 1 AT LEAST 100PIPIS OKAY", "NONE")

print("\n[٧] الكلام الذي يجب أن يبقى صامتاً")
for quiet in (
    "WE ARE GETTING READY.......",
    "shall we begin",
    "Please read this note👊",
    "RE-ENTRY WILL BE GIVEN TO THOSE WHO MISSED",
    "IT'S THREE NOW",
    "+ 70 PIPS 📌 ✅",
    "+ 300 PIPS ✅",
    "Today's candle will close in green, God willing✍️",
    "Today the daily candle will close in blue, InshaAllah 🤲",
    "Friends, another reminder: this is not a random channel, "
    "it's a stable channel, don't risk your money, I'm tired of "
    "telling you",
    "+BE OKAY" if False else "😮‍💨",
):
    check(quiet, "NONE")

print(f"\n{'─' * 56}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
