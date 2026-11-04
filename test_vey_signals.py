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

print("\n[٨] من أرشيف 29/10 إلى 4/11 — رسائلٌ حقيقية كشفت ثغرات")
# ★ إعلانُ اتجاهٍ بلا كلمة now: «Sell with minimum risk» ثم
# «3934-3939» بعد 37 ثانية. وبلا هذا ضاعت التوصية كلها.
check("**Sell with minimum risk**", "SIGNAL SELL")
check("**BUY WITH MIN RISK**", "SIGNAL BUY")
check("**BUY**", "SIGNAL BUY")
check("**3934-3939**", "LEVELS SELL 3934/3939", pending="SELL")

# ★ واتجاهان في جملةٍ واحدة ليسا إعلاناً
check("**__SELL AND BUY IN THEIR PLACE 🫵__**", "NONE")
# وجملةٌ طويلة ليست إعلاناً ولو حملت اتجاهاً
check("**I'LL GIVE YOU A ZONE, ONLY WITH A SLIVE, DON'T BREAK IT, "
      "MINRISK OKAY 🫵**", "NONE")
check("**THE PRICE IS MUCH HIGHER THAN OUR AREA ✈️**", "NONE")

# ★ التأمين بصيغتَيه القصيرتين
check("**HIT BE**", "BREAKEVEN")
check("**BE OKAY**", "BREAKEVEN")

# ★ رقمٌ عشري في الدخول — «3951.5-3944» وصلت فعلاً
check("**3951.5-3944**", "LEVELS BUY 3944/3951.5", pending="BUY")
# ★ و«SELL Z» بادئةٌ لا تمنع القراءة
check("**SELL Z 3943-3949**", "LEVELS SELL 3943/3949")
# ★ والاتجاه والأرقام في رسالةٍ واحدة
check("**»» BUY NOW «« **\n**3925-3920**", "LEVELS BUY 3920/3925")
check("3956-3964", "LEVELS SELL 3956/3964", pending="SELL")

# ★★ رسالةُ نتائجَ فيها زوجا أرقامٍ وكلمةُ Buy — ليست توصية.
# وحدها تُهمل؛ وخطرُها أن تلتقط اتجاهاً معلناً قديماً، وذلك ما
# يمنعه سقوطُ الإعلان بعد عشر دقائق في master_bot.
check("Cell 4005-4010\n**__+460 pips ✅__**\n\n"
      "**__Buy 3979-3976 __**\n**__+330 pips ✅__**", "NONE")

# ★ وأمرُ الخروج التام يُفرَّق عن الهدف
check("WE ARE CLOSING THE DEALS OPENED ABOVE ✖️\n"
      "WE WILL DISINFECT THE TRANSACTIONS OPENED BELOW ✔️", "CLOSE_ALL")
check("**sl 3933**", "SET_STOP 3933")
check("**sl**", "NONE")

print(f"\n{'─' * 56}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
