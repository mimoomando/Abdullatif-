"""اختبار توزيع دخول الحيتان على المنطقة.

يشغَّل بلا MetaTrader5 ولا اتصال بالوسيط:
    python3 test_whales_zone.py

يوثّق المواصفة المتفق عليها:
  • رسالة الاتجاه وحدها ('Buy Gold Now') لا تفتح أي صفقة
  • رسالة المنطقة توزع 5 مستويات بمسافة دولار من الطرف الأفضل
  • كل مستوى فاته السعر يُفتح سوقياً فوراً، والباقي عند لمس السعر
  • لا أوامر معلقة عند الوسيط
  • ستوب $6 لكل صفقة من سعر تنفيذها الفعلي
"""
import sys, types
fake = types.ModuleType("MetaTrader5")
for i, name in enumerate([
    "TIMEFRAME_M1","TIMEFRAME_M5","TIMEFRAME_M15","TIMEFRAME_M30","TIMEFRAME_H1",
    "TRADE_ACTION_DEAL","TRADE_ACTION_PENDING","TRADE_ACTION_REMOVE",
    "ORDER_TYPE_BUY","ORDER_TYPE_SELL","ORDER_TYPE_BUY_LIMIT","ORDER_TYPE_SELL_LIMIT",
    "ORDER_TYPE_BUY_STOP","ORDER_TYPE_SELL_STOP","ORDER_TIME_GTC","ORDER_TIME_SPECIFIED",
    "ORDER_FILLING_IOC","ORDER_FILLING_FOK","ORDER_FILLING_RETURN","TRADE_RETCODE_DONE",
    "POSITION_TYPE_BUY","ACCOUNT_TRADE_MODE_REAL","ACCOUNT_MARGIN_MODE_RETAIL_HEDGING",
]):
    setattr(fake, name, i + 1)
fake.copy_rates_from_pos = lambda *a, **k: None
fake.copy_rates_from = lambda *a, **k: None
fake.symbol_info_tick = lambda *a, **k: None
fake.positions_get = lambda *a, **k: []
fake.orders_get = lambda *a, **k: []
fake.account_info = lambda: None
fake.terminal_info = lambda: None
fake.history_deals_get = lambda *a, **k: []
sys.modules["MetaTrader5"] = fake
sys.modules["requests"] = types.ModuleType("requests")
sys.path.insert(0, "/home/user/Abdullatif-")

import master_bot as B

Tick = lambda p: types.SimpleNamespace(ask=p, bid=p)
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

print("\n[٤] مثالك: منطقة 4226→4231 والسعر 4228 → ثلاث صفقات")
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

print("\n[٧] رسالة الاتجاه وحدها لا تفتح صفقات")
opened = []
B.open_channel_batch = lambda *a, **k: opened.append(a) or 5
B.notify_tg = lambda *a, **k: None
B.send_tg = lambda *a, **k: None
B.handle_whales_message("XAUUSD", "بسم الله\nBuy Gold Now\nScalping Setup", "t:1")
check("لم تُفتح أي مجموعة", opened, [])


print("\n" + "=" * 58)
print("  محاكاة كاملة")
print("=" * 58)

Tick = lambda p: types.SimpleNamespace(ask=p, bid=p)
price = {"p": 4228.0}
B.mt5.symbol_info_tick = lambda *a, **k: Tick(price["p"])
B._channel_runtime_mode["enabled"] = False
B.notify_tg = lambda *a, **k: None
B.send_tg = lambda *a, **k: None

fills = []
_ticket = {"n": 5000}


def fake_open_trade(symbol, direction, lot, **kw):
    _ticket["n"] += 1
    entry = price["p"]
    fills.append({
        "ticket": _ticket["n"], "dir": direction, "lot": lot,
        "entry": entry, "level": kw["meta"]["zone_level"],
        "sl": round(entry - kw["sl_usd"] if direction == "BUY" else entry + kw["sl_usd"], 2),
    })
    return types.SimpleNamespace(ticket=_ticket["n"], price_open=entry)


B.open_trade = fake_open_trade

MSG = """بسم الله
Gold buy Now 4231-4226
* Tp1 4236
* Tp2 4255
* Tp3 4315
* Tp4 open
SL 4221"""

print("\n" + "=" * 58)
print("  توصية شراء | المنطقة 4226-4231 | السعر عند الوصول 4228")
print("=" * 58)

B.handle_whales_message("XAUUSD.vnw", MSG, "whales:101")
print(f"\n▶ عند وصول التوصية (السوق {price['p']:g}):")
for f in fills:
    print(f"   • مستوى {f['level']:g} → دخول {f['entry']:g} | ستوب {f['sl']:g} | {f['lot']} لوت")
assert len(fills) == 3, f"المتوقع 3 صفقات، الناتج {len(fills)}"

for new_price, note in [
    (4228.9, "ارتفاع طفيف — لم يبلغ 4229"),
    (4229.0, "بلغ 4229"),
    (4229.5, "بين المستويين"),
    (4230.0, "بلغ 4230"),
    (4232.0, "تجاوز المنطقة"),
]:
    before = len(fills)
    price["p"] = new_price
    B.open_due_zone_levels("XAUUSD.vnw")
    new = fills[before:]
    print(f"\n▶ السعر {new_price:g} ({note}):")
    if new:
        for f in new:
            print(f"   • مستوى {f['level']:g} → دخول {f['entry']:g} | ستوب {f['sl']:g}")
    else:
        print("   — لا صفقة جديدة")

total = len(fills)
print(f"\n{'─' * 58}")
print(f"إجمالي الصفقات: {total} × 0.01 = {total * 0.01:.2f} لوت")
print(f"أقصى مخاطرة: ${total * B.CHANNEL_INITIAL_SL_USD:.0f}")
assert total == 5, f"المتوقع 5 صفقات إجمالاً، الناتج {total}"
assert all(f["lot"] == 0.01 for f in fills), "لوت غير صحيح"
assert all(round(abs(f["entry"] - f["sl"]), 2) == 6.0 for f in fills), "ستوب غير $6"
assert len({f["level"] for f in fills}) == 5, "تكرار في المستويات"

# تكرار نفس الرسالة يجب ألا يفتح شيئاً
before = len(fills)
B.handle_whales_message("XAUUSD.vnw", MSG, "whales:101")
assert len(fills) == before, "الرسالة المكررة فتحت صفقات!"
print("✅ الرسالة المكررة لم تفتح شيئاً")

# بعد التأمين لا تُفتح مستويات جديدة
gid = next(iter(B._zone_groups))
B._zone_groups[gid]["levels"][4]["filled"] = False
B.finish_zone_group(gid, "اختبار التأمين")
before = len(fills)
price["p"] = 4230.0
B.open_due_zone_levels("XAUUSD.vnw")
assert len(fills) == before, "فُتح مستوى بعد إنهاء المجموعة!"
print("✅ بعد بدء التأمين لا تُفتح مستويات جديدة")

print("\n🎉 المحاكاة الكاملة نجحت\n")

print(f"\n{'─' * 58}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
