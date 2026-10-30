"""فحص قارئ توصيات القناة — برسائلها الحقيقية كما وصلت:

    python3 test_vip_signals.py

كل سطر هنا رسالة منقولة حرفياً من قناة VIP AN، لا مخترعة. فما نجح
هنا نجح على ما تكتبه القناة فعلاً، وما فشل أخطأ على مالٍ حقيقي.
"""
import sys
import vip_signals as V

ok = fails = 0


def check(message, want, **kw):
    """يترجم الرسالة ويقارن الفعل بالمتوقع."""
    global ok, fails
    got = V.interpret(message, **kw)
    name = got["action"]
    price = got.get("price")
    direction = got.get("direction")
    actual = name
    if price is not None:
        actual += f" {price:g}"
    if direction:
        actual += f" {direction}"
    if got.get("size") == "HALF":
        actual += " HALF"
    short = message if len(message) <= 42 else message[:40] + "…"
    if actual == want:
        ok += 1
        print(f"  ✅ «{short}» → {actual}")
    else:
        fails += 1
        print(f"  ❌ «{short}» → {actual}   (المتوقع {want})")
        if got.get("why"):
            print(f"       السبب: {got['why']}")


REF = 4002.0   # سعر الذهب المرجعي في معظم الأمثلة

print("[١] أوامر الفتح — تُنفَّذ")
check("بيع", "OPEN SELL")
check("بيع الان", "OPEN SELL")
check("شراء", "OPEN BUY")
check("شراء الان", "OPEN BUY")
check("بيع من 27", "OPEN SELL")
check("شراء من 90", "OPEN BUY")
check("بيع من 4009", "OPEN SELL")

print("\n[٢] ليست أوامر فتح — تُتجاهل")
check("رح نبيع من 4009-4008", "NONE")
check("مناطق الشراء 24-25-26 كلها ضمن النطاق", "NONE")
check("بامكانك تحجز ربح هدف اول وتستمر بنصه هدف ثاني", "NONE")
check("يعني بامكانك تحجز ربح هدف اول", "NONE")
check("الي يضرب عنده لا يجدد الا باشارة", "NONE")
check("اغلاق CRT يدعمنا بقووة", "NONE")
check("اغلاق الدقيقة والخمسة والربع كله يشير للهبوط بأذن الله", "NONE")

print("\n[٣] صفقة مفتوحة — لا يفتح ثانية")
check("بيع", "NONE", has_open_trade=True)
check("شراء الان", "NONE", has_open_trade=True)
check("خذ من 5 متاح", "NONE", has_open_trade=True)
check("يلا خذ. من 4000", "NONE", has_open_trade=True)

print("\n[٤] الستوب — بالأرقام الكاملة والناقصة")
check("ستوبك على 4007", "SET_STOP 4007", reference_price=REF)
check("ستوبك 4007", "SET_STOP 4007", reference_price=REF)
check("ستوبك 96", "SET_STOP 3996", reference_price=REF)
check("ستوبك 19", "SET_STOP 4019", reference_price=4024.0)
check("ستوبك 32", "SET_STOP 4032", reference_price=4028.0)
check("ستوبك 12", "SET_STOP 4012", reference_price=4018.0)

print("\n[٥] الأهداف")
check("هدفك 4000", "SET_TP1 4000", reference_price=REF)
check("هدفك 20", "SET_TP1 4020", reference_price=4027.0)
check("هدفك 26", "SET_TP1 4026", reference_price=4022.0)
check("هدفك 4035", "SET_TP1 4035", reference_price=4030.0)
check("هدف ثاني 4092", "SET_TP2 4092", reference_price=4050.0)
check("شباب الصفقة هذي فيها هدف ثاني 4092", "SET_TP2 4092",
      reference_price=4050.0)
check("بامكانك تخلي شي بسيط لهدف ثاني على 12", "SET_TP2 4012",
      reference_price=4018.0)
check("هدف ثاني", "NONE")

print("\n[٦] التأمين")
check("تأمين", "BREAKEVEN")
check("ضربنا تأمين", "BREAKEVEN")
check("تأمين دخولك", "BREAKEVEN")
check("ستوبك دخولك", "BREAKEVEN")
check("يلا ستوبك دخولك الان", "BREAKEVEN")
check("اهم شي ستوبك دخولك", "BREAKEVEN")
check("ستوبك على دخول 22 الان", "BREAKEVEN", reference_price=4023.0)
check("ترا في خبر بعد 10 دقايق يعني ستوبك دخولك انتبهلي كويس حبيبي",
      "BREAKEVEN", reference_price=4023.0)
check("الان ستوبك على 4004 يعني على الدخول", "BREAKEVEN",
      reference_price=4004.0)

print("\n[٧] حجز النصف")
check("احجز نص واستمر بنص", "CLOSE_HALF")
check("الاول تم احجز نص من ربحك", "CLOSE_HALF")

print("\n[٨] الإغلاق")
check("اغلق", "CLOSE_ALL")
check("اغلق دخول", "CLOSE_ALL")
check("خروج", "CLOSE_ALL")
check("خروووججج", "CLOSE_ALL")
check("خرووووججج", "CLOSE_ALL")
check("انتهت", "CLOSE_ALL")
check("انتهت حبايبي", "CLOSE_ALL")
check("تأمين انتهت", "CLOSE_ALL")
check("انتهت لا تفعل", "CLOSE_NO_REOPEN")

print("\n[٩] «اغلق» داخل جملة طويلة — ليست أمر إغلاق")
check("اغلق 3 استمر بدخول 5 بتقدر الان", "NONE")

print("\n[١٠] الدخول المشروط «لو ضربك»")
check("لو ضربك دخول تشتري من 22", "NONE")
check("لو ضربك دخول تشتري من 22", "NONE", has_open_trade=True,
      stop_was_hit=True)
check("لو ضربك دخول تشتري من 22", "REENTRY_IF_HIT BUY", stop_was_hit=True)
check("لو ضربك تبيع من 30", "REENTRY_IF_HIT SELL", stop_was_hit=True)

print("\n[١١] التجديد")
check("جدد من 25", "RENEW")
check("جدد", "RENEW")
check("جدد من 25", "NONE", has_open_trade=True)

print("\n[١٢] كلام لا فعل فيه")
for noise in [
    "اجهز", "الان", "4004", "من 4004-4003", "من 3-4", "طمنوني حبايي",
    "جمعة مباركة", "صباح الخير", "شباب", "لو حابب", "كم واحد فعل معي",
    "مستمرين حبايي", "بدي اشوف كل الارباح يلا", "@Bigboos1010",
    "نموذج ابتلاعي قوي بمنطقتنا", "الجميع مركز معي يلا وخلك سريع",
    "يهدى السوق ونفوت حبايي اليوم الجمعة اسوء يوم للشغل",
    "لان موجود معنا نموذج SNR تشكل على الشارت وابتلاعي",
    "بالنانو متر مربع ياحبيبي السوق كله يوقف على دخولي",
    "حبايبي خليكم ملتزمين بدون مخاطرة معي", "",
]:
    check(noise, "NONE")

print("\n[١٣] إكمال الأرقام مباشرةً")
for partial, ref, want in [
    ("96", 4002, 3996), ("20", 4027, 4020), ("27", 4030, 4027),
    ("8", 4006, 4008), ("4007", 4002, 4007), ("12", 4018, 4012),
    ("92", 4050, 4092), ("35", 4030, 4035),
]:
    got = V.complete_price(partial, ref)
    if got == want:
        ok += 1
        print(f"  ✅ «{partial}» والسعر {ref} → {got:g}")
    else:
        fails += 1
        print(f"  ❌ «{partial}» والسعر {ref} → {got}  (المتوقع {want})")

print("\n[١٤] صيغ الخروج كلها تغلق")
check("اخرج", "CLOSE_ALL")
check("اخرجو", "CLOSE_ALL")
check("اخراج", "CLOSE_ALL")
check("اخرجلي", "CLOSE_ALL")
check("اخرجلي من البيع على ربح", "CLOSE_ALL")
check("اخرجلي من الشراء على ربح", "CLOSE_ALL")
check("خرووووججججج، شلال زيرو انعكاس", "CLOSE_ALL")
check("خرجنا ستوب", "CLOSE_ALL")

print("\n[١٥] السؤال ليس أمراً — ولو حمل كلمة خروج")
check("خرجتو من البيع على ربح؟", "NONE")
check("خرجتو من البيع على ربح", "NONE")
check("كم واحد فعل معي", "NONE")

print("\n[١٦] حجز النصف — ثلاث صيغ بمعنى واحد")
check("الاول تم احجز نص من ربحك", "CLOSE_HALF")
check("شلاااااال الاول تم 80 pip افتتاح مبارك", "CLOSE_HALF")
check("احجز نص الارباح", "CLOSE_HALF")
check("احجز نص واستمر بنص", "CLOSE_HALF")

print("\n[١٧] اللوت البسيط — صفقتان بدل أربع")
check("شراء بلوت بسيط", "OPEN BUY HALF")
check("بيع بلوت بسيط", "OPEN SELL HALF")
check("شراء", "OPEN BUY")
check("حبايي صفقة بيها شوية خطر خفف لوتك", "REDUCE_SIZE")

print("\n[١٨] حذف الحشو قبل عدّ الكلمات")
check("يلا فعلي شراء من 14", "OPEN BUY")
check("واشتري الان يلا", "OPEN BUY")
check("يلا بيع الان", "OPEN SELL")
check("شباب شراء من 20", "OPEN BUY")
# والمحجوب يبقى محجوباً
check("رح نبيع من 4009-4008", "NONE")
check("مناطق الشراء 24-25-26 كلها ضمن النطاق", "NONE")
check("لو ضربك دخول تشتري من 22", "NONE")

print("\n[١٩] أمثلة القناة الأخيرة كاملةً")
check("خذ كمان دخول من 96", "NONE", has_open_trade=True)
check("15 ممكن برضو", "NONE", has_open_trade=True)
check("مبروكك حبايبي", "NONE")
check("افتتاح مبارك", "NONE")
check("وستوبك ثابت للجميع 13", "SET_STOP 4013", reference_price=4012.0)
check("يلا ستوبك دخولك الان", "BREAKEVEN")

print(f"\n{'─' * 56}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
