"""اختبار توزيع دخول القنوات على المنطقة.

يشغَّل بلا MetaTrader5 ولا اتصال بالوسيط:
    python3 test_channel_zones.py

يوثّق المواصفة المتفق عليها لكل قنوات التوصيات:
  • رسالة الاتجاه وحدها ('Buy Gold Now') لا تفتح أي صفقة
  • رسالة المنطقة توزع 5 مستويات بمسافة دولار من الطرف الأفضل
    (الشراء من أدنى المنطقة صعوداً، والبيع من أعلاها هبوطاً)
  • كل مستوى فاته السعر يُفتح سوقياً فوراً، والباقي عند لمس السعر
  • لا أوامر معلقة عند الوسيط
  • ستوب $6 لكل صفقة من سعر تنفيذها الفعلي
  • عند +$3 تُغلق الزائدة ويبقى اثنتان على وقف الدخول
"""
import os
import sys
import tempfile
import time
import types

# ── MT5 وهمي: يسمح باستيراد البوت دون تثبيت المكتبة ──
_fake = types.ModuleType("MetaTrader5")
for _i, _name in enumerate([
    "TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15", "TIMEFRAME_M30",
    "TIMEFRAME_H1", "TRADE_ACTION_DEAL", "TRADE_ACTION_PENDING",
    "TRADE_ACTION_REMOVE", "ORDER_TYPE_BUY", "ORDER_TYPE_SELL",
    "ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT", "ORDER_TYPE_BUY_STOP",
    "ORDER_TYPE_SELL_STOP", "ORDER_TIME_GTC", "ORDER_TIME_SPECIFIED",
    "ORDER_FILLING_IOC", "ORDER_FILLING_FOK", "ORDER_FILLING_RETURN",
    "TRADE_RETCODE_DONE", "POSITION_TYPE_BUY", "ACCOUNT_TRADE_MODE_REAL",
    "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING",
]):
    setattr(_fake, _name, _i + 1)
_fake.copy_rates_from_pos = lambda *a, **k: None
_fake.copy_rates_from = lambda *a, **k: None
_fake.symbol_info_tick = lambda *a, **k: None
_fake.positions_get = lambda *a, **k: []
_fake.orders_get = lambda *a, **k: []
_fake.account_info = lambda: None
_fake.terminal_info = lambda: None
_fake.history_deals_get = lambda *a, **k: []
sys.modules["MetaTrader5"] = _fake
sys.modules["requests"] = types.ModuleType("requests")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(tempfile.mkdtemp())  # عزل ملفات الحالة عن المستودع

import master_bot as B  # noqa: E402

Tick = lambda p: types.SimpleNamespace(ask=p, bid=p)
B.notify_tg = lambda *a, **k: None
B.send_tg = lambda *a, **k: None
B._channel_runtime_mode["enabled"] = False

ok = fails = 0


def check(name, got, want):
    global ok, fails
    if got == want:
        ok += 1
        print(f"  ✅ {name}")
    else:
        fails += 1
        print(f"  ❌ {name}\n       المتوقع: {want}\n       الناتج : {got}")


BUY_MSG = """بسم الله
Gold buy Now 4231-4226
* Tp1 4236
* Tp2 4255
* Tp3 4315
* Tp4 open
SL 4221"""

SELL_MSG = """بسم الله
Gold Sell Now 4644-4649
* Tp1 4639
* Tp2 4620
* Tp3 4600
* Tp4 open
Sl 4654"""

print("\n[١] قراءة المنطقة من رسالة القناة")
check("شراء 4231-4226", B.parse_entry_zone(BUY_MSG), (4226.0, 4231.0))
check("بيع 4644-4649", B.parse_entry_zone(SELL_MSG), (4644.0, 4649.0))
check("رسالة الاتجاه وحدها", B.parse_entry_zone("Buy Gold Now\nScalping Setup"), None)
check("لا تلتقط سطر الأهداف", B.parse_entry_zone("* Tp1 4236\n* Tp2 4255"), None)

print("\n[١.٥] فهم العربية والإنجليزية بصيغها المختلفة")
LANG_CASES = [
    ("عربي كامل", "SELL", (4644.0, 4649.0),
     "بيع الذهب من 4644 الى 4649\nالهدف الأول 4639\n"
     "الهدف الثاني 4620\nوقف الخسارة 4654"),
    ("أرقام عربية ٤٥٦", "BUY", (4226.0, 4231.0),
     "شراء ذهب ٤٢٢٦-٤٢٣١\nهدف١ ٤٢٣٦\nهدف٢ ٤٢٥٥\nستوب ٤٢٢١"),
    ("اشتري", "BUY", (4226.0, 4231.0),
     "اشتري الذهب 4226-4231\nTp1 4236\nSL 4221"),
    ("فاصلة آلاف 4,226", "BUY", (4226.0, 4231.0),
     "Gold Buy Now 4,226-4,231\nTp1 4,236\nSL 4,221"),
    ("SELL ZONE", "SELL", (4644.0, 4649.0),
     "GOLD SELL ZONE 4644 - 4649\nTP1: 4639\nTP2: 4620\nSTOP LOSS: 4654"),
    ("LONG بشرطة مائلة", "BUY", (4226.0, 4231.0),
     "XAUUSD LONG 4226/4231\nTarget 1 4236\nStop 4221"),
    ("همزات وتطويل", "SELL", (4644.0, 4649.0),
     "بيــع الذهــب مـن ٤٦٤٤ إلى ٤٦٤٩\nالهدف ٤٦٣٩\nالوقف ٤٦٥٤"),
]
for label, want_dir, want_zone, message in LANG_CASES:
    check(f"{label}: الاتجاه", B.parse_direction(message), want_dir)
    check(f"{label}: المنطقة", B.parse_entry_zone(message), want_zone)
    check(f"{label}: قرأ أهدافاً", len(B.parse_tps(message)) >= 1, True)
    check(f"{label}: قرأ الستوب", B.parse_sl(message) is not None, True)

print("\n[١.٦] لا يلتقط ما ليس توصية")
for label, message in [
    ("دردشة عن السوق", "الذهب عرضي ممل، في انتظار حركه للدخول"),
    ("اتجاه بلا أرقام", "Sell Gold Now 🔥\nScalping Setup"),
    ("سطر أهداف وحده", "* Tp1 4236\n* Tp2 4255"),
    ("إعلان نتيجة", "تم تحقيق الهدف الأول 4639 ✅ 70 pip"),
]:
    check(f"{label} → لا منطقة", B.parse_entry_zone(message), None)

print("\n[١.٧] رسائل المتابعة والنتائج لا تفتح صفقات")
NON_SIGNALS = [
    ("متابعة أرباح", "140 pip running 🔥🚀🚀 130 pip running 🔥🚀🚀"),
    ("إعلان هدف باتجاه", "Buy Gold hit Tp1 4236 ✅ +70 pips 🚀"),
    ("إغلاق بربح", "SELL GOLD CLOSED IN PROFIT Tp2 4620 ✅"),
    ("تحديث جارٍ", "Gold buy running +140 pip 🔥 هدف 4236 قادم"),
    ("تم تحقيق", "تم تحقيق الهدف الثاني 4620 بيع الذهب ✅"),
    ("ملخص يومي", "Daily Recap: Buy 4226 Tp1 4236 DONE"),
]
for label, message in NON_SIGNALS:
    check(f"{label} → تُرفض", B.is_non_signal_message(message), True)

# والأهم: ألا يبتلع الحارس التوصيات الحقيقية
for label, _, _, message in LANG_CASES:
    check(f"توصية {label} تمر", B.is_non_signal_message(message), False)
check("توصية الحيتان الأصلية تمر", B.is_non_signal_message(BUY_MSG), False)
check("توصية البيع الأصلية تمر", B.is_non_signal_message(SELL_MSG), False)

print("\n[٢] الاتجاه والأهداف")
check("اتجاه الشراء", B.parse_direction(BUY_MSG), "BUY")
check("اتجاه البيع", B.parse_direction(SELL_MSG), "SELL")
check("أهداف الشراء", B.parse_tps(BUY_MSG), [4236.0, 4255.0, 4315.0, "open"])
check("أهداف البيع", B.parse_tps(SELL_MSG), [4639.0, 4620.0, 4600.0, "open"])

print("\n[٣] توزيع المستويات الخمسة")
buy_levels = B.zone_entry_levels("BUY", 4226, 4231)
sell_levels = B.zone_entry_levels("SELL", 4644, 4649)
check("شراء: يبدأ من الأدنى صعوداً", buy_levels, [4226.0, 4227.0, 4228.0, 4229.0, 4230.0])
check("بيع: يبدأ من الأعلى هبوطاً", sell_levels, [4649.0, 4648.0, 4647.0, 4646.0, 4645.0])
check("منطقة ضيقة $2 تبقى داخل حدودها",
      B.zone_entry_levels("BUY", 4226, 4228), [4226.0, 4226.5, 4227.0, 4227.5, 4228.0])

print("\n[٤] مثال الشراء: منطقة 4226→4231 والسعر 4228 → ثلاث صفقات")
due = lambda lv, d, p: sum(1 for x in lv if B._zone_level_is_due(d, x, Tick(p)))
check("السعر 4228 → 3 صفقات فوراً", due(buy_levels, "BUY", 4228), 3)
check("ثم 4229 → صفقة رابعة", due(buy_levels, "BUY", 4229), 4)
check("ثم 4230 → صفقة خامسة", due(buy_levels, "BUY", 4230), 5)
check("السعر 4231 (فات الكل) → الخمسة فوراً", due(buy_levels, "BUY", 4231), 5)
check("السعر 4225 (لم يصل) → لا شيء", due(buy_levels, "BUY", 4225), 0)

print("\n[٥] الجهة المعاكسة للبيع")
check("السعر 4647 → 3 صفقات", due(sell_levels, "SELL", 4647), 3)
check("السعر 4644 (فات الكل) → الخمسة", due(sell_levels, "SELL", 4644), 5)
check("السعر 4655 (لم يصل) → لا شيء", due(sell_levels, "SELL", 4655), 0)

print("\n[٦] فحوص السلامة")
check("سلم أهداف الشراء صالح من أسوأ دخول 4230",
      B.valid_target_ladder("BUY", 4230.0, [4236.0, 4255.0, 4315.0, "open"]), True)
check("سلم أهداف البيع صالح من أسوأ دخول 4645",
      B.valid_target_ladder("SELL", 4645.0, [4639.0, 4620.0, 4600.0, "open"]), True)
check("أهداف في الجهة الخطأ تُرفض",
      B.valid_target_ladder("BUY", 4230.0, [4220.0, 4210.0]), False)
check("Tp3 البعيد (+$89) يمر بسماحية المنطقة",
      B.sane_tps([4236.0, 4255.0, 4315.0, "open"], 4228.5, B.ZONE_TP_SANITY_USD), True)
check("رقم شاذ (+$500) يُرفض",
      B.sane_tps([4236.0, 4800.0], 4228.5, B.ZONE_TP_SANITY_USD), False)

# ── تجهيز محاكاة التنفيذ ──
price = {"p": 4228.0}
B.mt5.symbol_info_tick = lambda *a, **k: Tick(price["p"])
fills = []
_ticket = {"n": 5000}


def fake_open_trade(symbol, direction, lot, **kw):
    _ticket["n"] += 1
    entry = price["p"]
    fills.append({
        "ticket": _ticket["n"], "dir": direction, "lot": lot, "entry": entry,
        "level": kw["meta"]["zone_level"], "channel": kw["meta"]["channel"],
        "sl": round(entry - kw["sl_usd"] if direction == "BUY" else entry + kw["sl_usd"], 2),
    })
    return types.SimpleNamespace(ticket=_ticket["n"], price_open=entry)


B.open_trade = fake_open_trade
B.open_channel_batch = lambda *a, **k: fills.append({"batch": True}) or 5

print("\n[٧] رسالة الاتجاه وحدها لا تفتح صفقات — في كل القنوات")
for label, handler, key in [
    ("الحيتان", B.handle_whales_message, "w:1"),
    ("KINGS", B.handle_kings_message, "k:1"),
]:
    fills.clear()
    handler("XAUUSD.vnw", "بسم الله\nBuy Gold Now\nScalping Setup", key)
    check(f"{label}: لم تُفتح صفقات", fills, [])

print("\n[٨] كل قناة ترث توزيع المنطقة")
for label, handler, channel, key in [
    ("الحيتان", B.handle_whales_message, "whales", "w:10"),
    ("KINGS", B.handle_kings_message, "kings", "k:10"),
    ("Sunny", B.handle_sunny_message, "sunny", "s:10"),
]:
    B._zone_groups.clear()  # كل قناة تُختبر وحدها
    fills.clear()
    price["p"] = 4228.0
    handler("XAUUSD.vnw", BUY_MSG, key)
    check(f"{label}: 3 صفقات عند 4228", len(fills), 3)
    check(f"{label}: الصفقات منسوبة للقناة",
          {f["channel"] for f in fills}, {channel})
    check(f"{label}: ستوب $6 من التنفيذ",
          all(round(abs(f["entry"] - f["sl"]), 2) == 6.0 for f in fills), True)

print("\n[٩] محاكاة كاملة لتحرك السعر عبر المنطقة (الحيتان)")
B._zone_groups.clear()  # عزل: مجموعات القسم السابق لا تتداخل مع المحاكاة
fills.clear()
price["p"] = 4228.0
B.handle_whales_message("XAUUSD.vnw", BUY_MSG, "whales:sim")
print(f"   عند وصول التوصية (السوق {price['p']:g}):")
for f in fills:
    print(f"      • مستوى {f['level']:g} → دخول {f['entry']:g} | ستوب {f['sl']:g}")
check("فُتحت 3 فوراً", len(fills), 3)

for new_price, note, expect in [
    (4228.9, "لم يبلغ 4229", 3),
    (4229.0, "بلغ 4229", 4),
    (4229.5, "بين المستويين", 4),
    (4230.0, "بلغ 4230", 5),
    (4232.0, "تجاوز المنطقة", 5),
]:
    price["p"] = new_price
    B.open_due_zone_levels("XAUUSD.vnw")
    check(f"السعر {new_price:g} ({note}) → {expect} صفقات", len(fills), expect)

check("الإجمالي 5 × 0.01", len(fills), 5)
check("كل الألوات 0.01", all(f["lot"] == 0.01 for f in fills), True)
check("لا تكرار في المستويات", len({f["level"] for f in fills}), 5)
print(f"   أقصى مخاطرة: ${len(fills) * B.CHANNEL_INITIAL_SL_USD:.0f}")

print("\n[١٠] الحماية")
before = len(fills)
B.handle_whales_message("XAUUSD.vnw", BUY_MSG, "whales:sim")
check("الرسالة المكررة لا تفتح شيئاً", len(fills), before)

gid = next(g for g in B._zone_groups if B._zone_groups[g]["channel"] == "whales")
B._zone_groups[gid]["levels"][4]["filled"] = False
B.finish_zone_group(gid, "اختبار التأمين")
price["p"] = 4230.0
B.open_due_zone_levels("XAUUSD.vnw")
check("بعد بدء التأمين لا تُفتح مستويات", len(fills), before)

print("\n[١١] سقف القناة — توصية ثانية لا تضاعف الصفقات")
B._zone_groups.clear()
B._open_trades.clear()
fills.clear()
live_positions = []
B.mt5.positions_get = lambda *a, **k: list(live_positions)
B.mt5.POSITION_TYPE_BUY = 1


def capped_open(symbol, direction, lot, **kw):
    ticket = 7000 + len(live_positions)
    live_positions.append(types.SimpleNamespace(
        ticket=ticket, magic=kw["magic"], type=1,
        price_open=price["p"], sl=0.0, tp=0.0))
    return types.SimpleNamespace(ticket=ticket, price_open=price["p"])


B.open_trade = capped_open
notices = []
B.notify_tg = lambda t: notices.append(t)

MSG_B = ("Gold buy Now 4240-4235\nTp1 4246\nTp2 4255\nTp3 4265\n"
         "Tp4 open\nSL 4230")
price["p"] = 4228.0
B.handle_whales_message("XAUUSD.vnw", BUY_MSG, "cap:a")
check("التوصية الأولى: 3 مفتوحة + 2 محجوزة = 5",
      B.channel_open_exposure("whales"), 5)

price["p"] = 4238.0
B.open_due_zone_levels("XAUUSD.vnw")
check("اكتملت الخمسة", len(live_positions), 5)

notices.clear()
B.handle_whales_message("XAUUSD.vnw", MSG_B, "cap:b")
check("التوصية الثانية لم تفتح شيئاً", len(live_positions), 5)
check("وصل تنبيه التخطي", any("تُخطّيت" in n for n in notices), True)

del live_positions[:3]  # أُغلقت ثلاث
check("بقيت صفقتان", B.channel_open_exposure("whales"), 2)
notices.clear()
B.handle_whales_message("XAUUSD.vnw", MSG_B, "cap:c")
check("توصية تحتاج 5 والمتاح 3 → تُرفض", len(live_positions), 2)

print("\n[١٢] تقرير الإغلاق المفصل")
B._open_trades.clear()
B._open_trades[8001] = {
    "channel": "whales", "direction": "BUY", "entry": 4228.0, "ticket": 8001,
    "opened_at": time.time() - 425, "peak_move": 0.0, "worst_move": 0.0,
    "group_id": "whales:x", "hour": 14, "fp": "BUY|zone", "zone_level": 4227.0,
}
pos = types.SimpleNamespace(ticket=8001, magic=B.MAGIC_WHALES, type=1,
                            price_open=4228.0, sl=0.0, tp=0.0)
B.mt5.positions_get = lambda *a, **k: [pos]
for p in (4229.0, 4233.0, 4230.0, 4222.0):
    price["p"] = p
    B.track_channel_excursions("XAUUSD.vnw")
info = B._open_trades[8001]
check("سجّل أقصى ربح مرّ بالصفقة", info["peak_move"], 5.0)
check("سجّل أقصى تراجع", info["worst_move"], -6.0)

B.mt5.positions_get = lambda *a, **k: []
B.mt5.DEAL_REASON_SL, B.mt5.DEAL_REASON_TP = 4, 5
B.mt5.history_deals_get = lambda *a, **k: [
    types.SimpleNamespace(price=4222.0, reason=4, profit=-6.0, swap=0.0, commission=0.0)
]
notices.clear()
B.report_closed_channel_trades("XAUUSD.vnw")
# صفقة واحدة تُنهي توصيتها → تقرير الصفقة ثم التقرير الختامي
check("تقرير الصفقة + الختامي", len(notices), 2)
report = notices[0] if notices else ""
for fragment, label in [
    ("أُغلقت صفقة الحيتان", "اسم القناة"),
    ("4228.00", "سعر الدخول"),
    ("4222.00", "سعر الخروج"),
    ("ضرب وقف الخسارة", "سبب الإغلاق"),
    ("+$5.00", "أقصى ربح"),
    ("تشريح الخسارة", "التشريح"),
    ("دقيقة", "المدة"),
]:
    check(f"التقرير يذكر {label}", fragment in report, True)
check("أُزيلت الصفقة من التتبع", 8001 in B._open_trades, False)

print("\n[١٣] التقرير الختامي يُرسل بعد آخر صفقة فقط")
B._open_trades.clear()
B._zone_groups.clear()
B._group_results.clear()
B.mt5.copy_rates_from_pos = lambda *a, **k: None
GID = "whales:sig1"
group_positions = {}
for i in range(5):
    tk = 9000 + i
    B._open_trades[tk] = {
        "channel": "whales", "direction": "BUY", "entry": 4228.0 + i * 0.5,
        "ticket": tk, "opened_at": time.time() - 900,
        "peak_move": 4.0 + i, "worst_move": -1.0, "group_id": GID,
        "hour": 14, "fp": "BUY|zone", "zone_level": 4226.0 + i,
        "zone_low": 4226.0, "zone_high": 4231.0, "partial_close_started": True,
    }
    group_positions[tk] = types.SimpleNamespace(
        ticket=tk, magic=B.MAGIC_WHALES, type=1,
        price_open=4228.0 + i * 0.5, sl=0.0, tp=0.0)

shut = {}
B.mt5.positions_get = lambda *a, **k: [
    p for t, p in group_positions.items() if t not in shut
]
B.mt5.history_deals_get = lambda position=None, **k: ([
    types.SimpleNamespace(price=shut[position][0], reason=shut[position][1],
                          profit=shut[position][2], swap=0.0, commission=-0.02)
] if position in shut else [])

for tk in (9000, 9001, 9002):
    shut[tk] = (4231.2, 3, 3.2)
notices.clear()
B.report_closed_channel_trades("XAUUSD.vnw")
check("٣ تقارير صفقات بلا ختامي", len(notices), 3)
check("لا تقرير ختامي بعد",
      any("انتهت توصية" in n for n in notices), False)

shut[9003] = (4236.0, 5, 8.0)
shut[9004] = (4222.0, 4, -6.0)
notices.clear()
B.report_closed_channel_trades("XAUUSD.vnw")
check("صفقتان + التقرير الختامي", len(notices), 3)
summary = notices[-1]
check("الختامي يعلن انتهاء التوصية", "انتهت توصية" in summary, True)
check("الختامي يذكر الصافي", "الصافي" in summary, True)
check("الختامي يذكر المنطقة", "4226 — 4231" in summary, True)
check("الختامي يذكر المخاطرة", "$30" in summary, True)
check("الصافي محسوب مع العمولة", "+$11.50" in summary, True)
check("نُظفت نتائج التوصية", GID in B._group_results, False)

print(f"\n{'─' * 52}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
