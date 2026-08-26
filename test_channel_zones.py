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
    "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", "TRADE_ACTION_SLTP",
    "POSITION_TYPE_SELL",
]):
    setattr(_fake, _name, _i + 1)
_fake.TRADE_RETCODE_NO_CHANGES = 10025
_fake.last_error = lambda: (-1, "no connection")
_fake.copy_rates_from_pos = lambda *a, **k: None
_fake.copy_rates_from = lambda *a, **k: None
_fake.symbol_info_tick = lambda *a, **k: None
_fake.positions_get = lambda *a, **k: []
_fake.orders_get = lambda *a, **k: []
_fake.account_info = lambda: None
_fake.terminal_info = lambda: None
_fake.history_deals_get = lambda *a, **k: []
_fake.order_send = lambda *a, **k: None
_fake.symbols_get = lambda *a, **k: []
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

print("\n[١.٨] كشف التوصيات التي لم يفهمها البوت")
for label, message, expected in [
    ("صيغة مجهولة",
     "KINGS GOLD BUY\nEntry area 4226 to 4231\nFirst 4236\nRisk 4221", True),
    ("أهداف بالنقاط", "Gold Sell 4644\nTp1 +30 pips\nTp2 +60 pips\nSL 4654", True),
    ("متابعة أرباح", "140 pip running 🔥🚀 130 pip running", False),
    ("دردشة", "الذهب عرضي ممل في انتظار حركه", False),
    ("اتجاه بلا أرقام", "Buy Gold Now\nScalping Setup", False),
]:
    check(f"{label} → {'تُكشف' if expected else 'تُتجاهل'}",
          B.looks_like_unread_signal(message), expected)

B._unread_signal_notice.clear()
unknown = "KINGS GOLD BUY\nEntry area 4226 to 4231\nFirst 4236\nRisk 4221"
check("التنبيه يُرسل أول مرة", B.notify_unread_signal("kings", unknown), True)
check("ولا يتكرر خلال التبريد", B.notify_unread_signal("kings", unknown), False)
check("وكل قناة مستقلة", B.notify_unread_signal("sunny", unknown), True)

print("\n[١.٩] صيغة KINGS الحقيقية")
KINGS_NOW = """XAUUSD BUY NOW 4634-4635
Sl 4630

Tp 4640
Tp 4645
Tp 4650
Tp 4655
Tp 4660
Tp 4665
Tp 4670
Tp open"""
KINGS_LIMIT = """XAUUSD BUY LIMIT 4618-4619
Sl 4613
Tp 4623
Tp 4628
Tp 4633
Tp 4638
Tp 4643
Tp open"""
KINGS_SELL_LIMIT = """XAUUSD SELL LIMIT 4650-4651
Sl 4657
Tp 4645
Tp 4640
Tp open"""

check("BUY NOW: الاتجاه", B.parse_direction(KINGS_NOW), "BUY")
check("BUY NOW: سبعة أهداف + open", B.parse_tps(KINGS_NOW),
      [4640.0, 4645.0, 4650.0, 4655.0, 4660.0, 4665.0, 4670.0, "open"])
check("BUY NOW: الستوب", B.parse_sl(KINGS_NOW), 4630.0)
check("BUY NOW: ليست LIMIT", B.parse_limit_entry(KINGS_NOW, "BUY"), None)

check("BUY LIMIT: يقرأ سعر الدخول", B.parse_limit_entry(KINGS_LIMIT, "BUY"), 4619.0)
check("BUY LIMIT: الأهداف", B.parse_tps(KINGS_LIMIT),
      [4623.0, 4628.0, 4633.0, 4638.0, 4643.0, "open"])
check("SELL LIMIT: يقرأ سعر الدخول",
      B.parse_limit_entry(KINGS_SELL_LIMIT, "SELL"), 4650.0)
check("SELL LIMIT: الاتجاه", B.parse_direction(KINGS_SELL_LIMIT), "SELL")

check("KINGS يقفل الوقف عند $3", B.channel_policy("kings", "target_lock_usd"), 3.0)
check("الحيتان تقفل عند $2", B.channel_policy("whales", "target_lock_usd"), 2.0)
check("KINGS تدخل فوراً", B.channel_policy("kings", "entry_mode"), "immediate")
check("KINGS تفتح على رسالة الاتجاه",
      B.channel_policy("kings", "opens_on_direction"), True)
check("الحيتان لا تفتح على الاتجاه",
      B.channel_policy("whales", "opens_on_direction"), False)
check("الحيتان توزع على المنطقة",
      B.channel_policy("whales", "entry_mode"), "zone_levels")
check("الاقتراب $1 للجميع", B.channel_policy("kings", "target_approach_usd"), 1.0)

print("\n[٢.٠] صيغة Gold Trader Sunny الحقيقية")
SUNNY_BUY = """Buy Gold @4652-4642

Sl :4637

Tp1: 4656.5
Tp2: 4660

Enter Slowly-Layer with proper money management

Do not rush your entries"""
SUNNY_SELL = """Gold Short Zone:4636-4646

Stop: 4650

Target 1: 4632
Target 2: 4627

Ease in — layer your entries with proper risk management.

Don't rush it"""
SUNNY_TEASER = "Scalping buy gold slowly high risk\n\n(scalping)"
SUNNY_RESULT = ("Round 1 INSTANT 60PIPS✅\n\nLet's CLOSE our trade now and "
                "set breakeven if you wish to hold now‼️")

check("Buy Gold @: الاتجاه", B.parse_direction(SUNNY_BUY), "BUY")
check("Buy Gold @: هدف بكسر عشري", B.parse_tps(SUNNY_BUY), [4656.5, 4660.0])
check("Buy Gold @: 'Sl :4637'", B.parse_sl(SUNNY_BUY), 4637.0)
check("Short Zone: الاتجاه", B.parse_direction(SUNNY_SELL), "SELL")
check("Short Zone: 'Target 1:'", B.parse_tps(SUNNY_SELL), [4632.0, 4627.0])
check("Short Zone: 'Stop:'", B.parse_sl(SUNNY_SELL), 4650.0)
check("توصيتا Sunny ليستا نتيجة",
      B.is_non_signal_message(SUNNY_BUY) or B.is_non_signal_message(SUNNY_SELL),
      False)
check("رسالة 'CLOSE/breakeven' تُرفض", B.is_non_signal_message(SUNNY_RESULT), True)
check("Sunny توزّع على المنطقة",
      B.channel_policy("sunny", "entry_mode"), "zone_levels")
check("Sunny تقفل عند $3", B.channel_policy("sunny", "target_lock_usd"), 3.0)

print("\n[٢.١] حارسا الحساب والرمز")
B.mt5.ACCOUNT_TRADE_MODE_REAL = 100
B.mt5.ACCOUNT_TRADE_MODE_DEMO = 101
B.mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 200
_demo_acct = types.SimpleNamespace(trade_mode=101, login=111672224,
                                   trade_allowed=True, margin_mode=200,
                                   balance=100000.0)
_real_acct = types.SimpleNamespace(trade_mode=100, login=555,
                                   trade_allowed=True, margin_mode=200,
                                   balance=1000.0)
_terminal = types.SimpleNamespace(connected=True, trade_allowed=True)
_saved_terminal = B.mt5.terminal_info
_saved_account = B.mt5.account_info
B.mt5.terminal_info = lambda: _terminal
for label, acct, allow_demo, expected in [
    ("تجريبي بلا --demo → مرفوض", _demo_acct, False, False),
    ("تجريبي مع --demo → مسموح", _demo_acct, True, True),
    ("حقيقي بلا --demo → مسموح", _real_acct, False, True),
    ("حقيقي مع --demo → مسموح", _real_acct, True, True),
]:
    B.mt5.account_info = lambda a=acct: a
    B._channel_runtime_mode["allow_demo"] = allow_demo
    B._channel_runtime_mode["account_login"] = acct.login
    check(label, B.live_account_ready(), expected)
B.mt5.terminal_info = _saved_terminal
B.mt5.account_info = _saved_account
B._channel_runtime_mode["allow_demo"] = False
B._channel_runtime_mode["account_login"] = None

B._channel_runtime_mode["enabled"] = True
for session_symbol, traded, expected in [
    ("XAUUSD", "XAUUSD", True),
    ("XAUUSD", "XAUUSD.vnw", False),
    ("XAUUSD.vnw", "XAUUSD.vnw", True),
    ("XAUUSD", "EURUSD", False),
]:
    B._channel_runtime_mode["symbol"] = session_symbol
    check(f"جلسة {session_symbol} وتداول {traded}",
          B.allowed_gold_symbol(traded), expected)
B._channel_runtime_mode["enabled"] = False
B._channel_runtime_mode["symbol"] = None

print("\n[٢.٢] أسباب فشل التنفيذ تصل بدل أن تبقى في السجل")
for code, comment, fragment in [
    (10016, "Invalid stops", "وقف/هدف غير صالح"),
    (10018, "", "السوق مغلق"),
    (10027, "AutoTrading disabled", "التداول الآلي معطّل"),
    (10030, "Unsupported filling", "وضع التعبئة غير مدعوم"),
]:
    described = B.describe_mt5_result(
        types.SimpleNamespace(retcode=code, comment=comment))
    check(f"خطأ {code} مشروح بالعربية", fragment in described, True)
    check(f"خطأ {code} يذكر رقمه", str(code) in described, True)

_saved_send = B.mt5.order_send
_attempts = {"n": 0}


def _flaky_sltp(request):
    _attempts["n"] += 1
    # الصفقة الجديدة قد ترفض التعديل في اللحظة الأولى ثم تقبله
    return types.SimpleNamespace(
        retcode=(B.mt5.TRADE_RETCODE_DONE if _attempts["n"] >= 3 else 10016),
        comment="Invalid stops")


B.mt5.order_send = _flaky_sltp
_pos = types.SimpleNamespace(ticket=555)
check("تثبيت الوقف ينجح بعد إعادة المحاولة",
      B.modify_channel_position("XAUUSD", _pos, 4621.92, 0.0), True)
check("استغرق ثلاث محاولات", _attempts["n"], 3)

B.mt5.order_send = lambda r: types.SimpleNamespace(
    retcode=10018, comment="Market closed")
check("رفض دائم يفشل نهائياً",
      B.modify_channel_position("XAUUSD", _pos, 4621.92, 0.0), False)
check("وسُجّل سببه", "السوق مغلق" in B._last_mt5_error["text"], True)
B.mt5.order_send = _saved_send

B._unread_signal_notice.clear()
_notices = []
_saved_notify = B.notify_tg
B.notify_tg = lambda t: _notices.append(t)
B.notify_unread_signal("kings", "XAUUSD BUY NOW 4625-4626 Sl 4620 Tp 4630")
check("فشل التنفيذ → 'الوسيط رفض تنفيذها'",
      "رفض تنفيذها" in _notices[-1], True)
check("مع ذكر السبب", "السوق مغلق" in _notices[-1], True)

B._unread_signal_notice.clear()
B._last_mt5_error["text"] = ""
B.notify_unread_signal("kings", "KINGS GOLD BUY Entry area 4226 to 4231")
check("صيغة مجهولة → 'غير مدعومة'", "غير مدعومة" in _notices[-1], True)
B.notify_tg = _saved_notify

print("\n[٢.٣] صفقة عليها وقف صالح لا تُغلق لتعذر ضبطه")
_saved = {
    "resolve": B.resolve_new_channel_position,
    "close": B.close_channel_position,
    "modify": B.modify_channel_position,
    "send": B.mt5.order_send,
    "positions": B.mt5.positions_get,
    "tick": B.mt5.symbol_info_tick,
    "notify": B.notify_tg,
}
_closed = []
_alerts = []
B.mt5.symbol_info_tick = lambda *a, **k: Tick(4627.92)
B.mt5.order_send = lambda r: types.SimpleNamespace(
    retcode=B.mt5.TRADE_RETCODE_DONE, order=999, deal=888, comment="ok")
B.mt5.positions_get = lambda *a, **k: []
B.close_channel_position = lambda s, p, **k: (_closed.append(p.ticket), True)[1]
B.modify_channel_position = lambda *a, **k: False  # الوسيط يرفض الضبط
B.notify_tg = lambda t: _alerts.append(t)

# الحالة الحقيقية: أُرسل الأمر بوقف 4621.92 ونُفّذ عند 4627.84
_protected = types.SimpleNamespace(ticket=777, price_open=4627.84,
                                   sl=4621.92, tp=0.0)
B.resolve_new_channel_position = lambda *a, **k: _protected
_result = B.open_trade("XAUUSD", "BUY", 0.01, sl_usd=6.0, magic=1,
                       comment="Kings", meta={"channel": "kings"},
                       return_position=True)
check("الصفقة المحمية لم تُغلق", _closed, [])
check("وأُرجعت للمجموعة", bool(_result), True)
check("ووصل تنبيه بفارق الوقف",
      any("لم يُضبط بدقة" in a for a in _alerts), True)

# وصفقة بلا أي وقف يجب أن تُغلق
_closed.clear()
_bare = types.SimpleNamespace(ticket=778, price_open=4627.84, sl=0.0, tp=0.0)
B.resolve_new_channel_position = lambda *a, **k: _bare
_result = B.open_trade("XAUUSD", "BUY", 0.01, sl_usd=6.0, magic=1,
                       comment="Kings", meta={"channel": "kings"},
                       return_position=True)
check("الصفقة بلا وقف تُغلق", _closed, [778])
check("ولا تُرجع للمجموعة", _result, None)

B.resolve_new_channel_position = _saved["resolve"]
B.close_channel_position = _saved["close"]
B.modify_channel_position = _saved["modify"]
B.mt5.order_send = _saved["send"]
B.mt5.positions_get = _saved["positions"]
B.mt5.symbol_info_tick = _saved["tick"]
B.notify_tg = _saved["notify"]
B._open_trades.clear()

print("\n[٢.٤] منع التناقض: لا شراء وبيع معاً من قنوات مختلفة")
_saved_positions = B.mt5.positions_get
_buy_pos = types.SimpleNamespace(ticket=1, magic=B.MAGIC_WHALES,
                                 type=B.mt5.POSITION_TYPE_BUY)
_sell_pos = types.SimpleNamespace(ticket=2, magic=B.MAGIC_KINGS,
                                  type=B.mt5.POSITION_TYPE_SELL)

B.mt5.positions_get = lambda *a, **k: []
check("لا صفقات مفتوحة → الشراء مسموح",
      B.no_conflicting_direction("kings", "BUY"), True)
check("لا صفقات مفتوحة → البيع مسموح",
      B.no_conflicting_direction("kings", "SELL"), True)

B.mt5.positions_get = lambda *a, **k: [_buy_pos]
check("شراء مفتوح من الحيتان → بيع KINGS يُرفض",
      B.no_conflicting_direction("kings", "SELL"), False)
check("شراء مفتوح → شراء آخر مسموح",
      B.no_conflicting_direction("kings", "BUY"), True)

B.mt5.positions_get = lambda *a, **k: [_sell_pos]
check("بيع مفتوح من KINGS → شراء Sunny يُرفض",
      B.no_conflicting_direction("sunny", "BUY"), False)
check("بيع مفتوح → بيع آخر مسموح",
      B.no_conflicting_direction("sunny", "SELL"), True)

# صفقة من استراتيجية قديمة (Magic غير قناة) لا تمنع
_other = types.SimpleNamespace(ticket=3, magic=B.MAGIC_BOOK,
                               type=B.mt5.POSITION_TYPE_BUY)
B.mt5.positions_get = lambda *a, **k: [_other]
check("صفقة خارج القنوات لا تمنع البيع",
      B.no_conflicting_direction("kings", "SELL"), True)

B.mt5.positions_get = lambda *a, **k: None  # تعذر الفحص
check("تعذر قراءة الصفقات → رفض احتياطي",
      B.no_conflicting_direction("kings", "BUY"), False)
B.mt5.positions_get = _saved_positions

print("\n[٢.٥] الأهداف التي فاتها السعر تُسقط ويُكمل بالباقي")
KINGS_TPS = [4625.0, 4630.0, 4635.0, 4640.0, "open"]
check("السوق 4620 → كل الأهداف باقية",
      B.usable_targets("BUY", 4620.0, KINGS_TPS)[0], KINGS_TPS)
check("السوق 4627 → يسقط 4625 ويكمل",
      B.usable_targets("BUY", 4627.0, KINGS_TPS)[0],
      [4630.0, 4635.0, 4640.0, "open"])
check("ويذكر ما أُسقط",
      B.usable_targets("BUY", 4627.0, KINGS_TPS)[1], [4625.0])
check("السوق 4636 → يبقى هدف واحد",
      B.usable_targets("BUY", 4636.0, KINGS_TPS)[0], [4640.0, "open"])
check("السوق 4645 → لا شيء يبقى",
      B.usable_targets("BUY", 4645.0, KINGS_TPS)[0], [])
SELL_TPS = [4632.0, 4627.0, "open"]
check("بيع: السوق 4630 → يسقط 4632",
      B.usable_targets("SELL", 4630.0, SELL_TPS)[0], [4627.0, "open"])

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

print("\n[٧] رسالة الاتجاه وحدها — الحيتان تنتظر وKINGS تدخل فوراً")
fills.clear()
B.handle_whales_message("XAUUSD.vnw", "بسم الله\nBuy Gold Now\nScalping Setup", "w:1")
check("الحيتان: تنتظر الأرقام ولا تفتح", fills, [])

fills.clear()
B.handle_sunny_message("XAUUSD.vnw", "Scalping buy gold slowly high risk", "s:1")
check("Sunny: تمهيد السكالبينج لا يفتح", fills, [])

# KINGS تنفّذ على "خد شراء الان" قبل وصول الأرقام
fills.clear()
B.handle_kings_message("XAUUSD.vnw", "خد شراء الان", "k:1")
check("KINGS: تفتح فوراً على الاتجاه", fills, [{"batch": True}])

fills.clear()
B.handle_kings_message("XAUUSD.vnw", "حضوووور 🌟", "k:2")
check("KINGS: كلام بلا اتجاه لا يفتح", fills, [])

fills.clear()
B.handle_kings_message("XAUUSD.vnw", "الشراء افضل من البيع اليوم", "k:3")
check("KINGS: اتجاه بلا 'الآن' لا يفتح", fills, [])

print("\n[٨] الحيتان توزع على المنطقة، وKINGS وSunny تدخلان فوراً")
# الحيتان وحدها قناة منطقة
B._zone_groups.clear()
fills.clear()
price["p"] = 4228.0
B.handle_whales_message("XAUUSD.vnw", BUY_MSG, "w:10")
check("الحيتان: 3 صفقات عند 4228", len(fills), 3)
check("الحيتان: الصفقات منسوبة للقناة",
      {f["channel"] for f in fills}, {"whales"})
check("الحيتان: ستوب $6 من التنفيذ",
      all(round(abs(f["entry"] - f["sl"]), 2) == 6.0 for f in fills), True)

# KINGS وSunny: دخول سوقي فوري أو أمر معلق — بلا توزيع
kings_actions = []
_real_batch, _real_pending = B.open_channel_batch, B.place_channel_pending_batch
B.open_channel_batch = (
    lambda s, d, m, c, meta, **k: kings_actions.append(("MARKET", d)) or 5
)
B.place_channel_pending_batch = (
    lambda s, d, e, m, c, meta, **k: kings_actions.append(("PENDING", d, e)) or 5
)
B._zone_groups.clear()
price["p"] = 4636.0
B.handle_kings_message("XAUUSD.vnw", KINGS_NOW, "k:now")
check("KINGS NOW → دخول سوقي للخمسة", kings_actions, [("MARKET", "BUY")])

kings_actions.clear()
price["p"] = 4625.0
B.handle_kings_message("XAUUSD.vnw", KINGS_LIMIT, "k:limit")
check("KINGS LIMIT → أوامر معلقة عند 4619",
      kings_actions, [("PENDING", "BUY", 4619.0)])

kings_actions.clear()
price["p"] = 4640.0
B.handle_kings_message("XAUUSD.vnw", KINGS_SELL_LIMIT, "k:sell")
check("KINGS SELL LIMIT → معلق عند 4650",
      kings_actions, [("PENDING", "SELL", 4650.0)])

kings_actions.clear()
B.handle_kings_message("XAUUSD.vnw", "ناخد شراء الان على الهادي", "k:teaser")
check("KINGS: 'شراء الان' يفتح فوراً بلا انتظار أرقام",
      kings_actions, [("MARKET", "BUY")])

B._zone_groups.clear()
kings_actions.clear()
B.open_channel_batch, B.place_channel_pending_batch = _real_batch, _real_pending

# Sunny — توزّع على المنطقة مثل الحيتان، صفقة عند لمس كل مستوى
# منطقة الشراء 4642-4652 → المستويات 4642·4643·4644·4645·4646
B._zone_groups.clear()
B._processed_signals.clear()
B._last_signal.clear()
fills.clear()
price["p"] = 4644.0  # ثلاثة مستويات فاتها السعر
B.handle_sunny_message("XAUUSD.vnw", SUNNY_BUY, "s:zone")
check("Sunny: توزّع كالحيتان — 3 مستويات فاتها السعر", len(fills), 3)
check("Sunny: الصفقات منسوبة للقناة",
      {f["channel"] for f in fills}, {"sunny"})
check("Sunny: ستوب $6 من التنفيذ",
      all(round(abs(f["entry"] - f["sl"]), 2) == 6.0 for f in fills), True)

price["p"] = 4645.0
B.open_due_zone_levels("XAUUSD.vnw")
check("Sunny: المستوى الرابع عند لمسه", len(fills), 4)

price["p"] = 4646.0
B.open_due_zone_levels("XAUUSD.vnw")
check("Sunny: المستوى الخامس", len(fills), 5)

price["p"] = 4650.0
B.open_due_zone_levels("XAUUSD.vnw")
check("Sunny: لا سادسة", len(fills), 5)

B._zone_groups.clear()
kings_actions.clear()
B.open_channel_batch = (
    lambda s, d, m, c, meta, **k: kings_actions.append(("MARKET", d)) or 5
)
B.place_channel_pending_batch = (
    lambda s, d, e, m, c, meta, **k: kings_actions.append(("PENDING", d, e)) or 5
)
B.handle_sunny_message("XAUUSD.vnw", SUNNY_TEASER, "s:teaser")
check("Sunny: تمهيد سكالبينج لا يفتح شيئاً", kings_actions, [])

kings_actions.clear()
B.handle_sunny_message("XAUUSD.vnw", SUNNY_RESULT, "s:result")
check("Sunny: إعلان نتيجة لا يفتح شيئاً", kings_actions, [])
B.open_channel_batch, B.place_channel_pending_batch = _real_batch, _real_pending

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

print("\n[١٢.٥] التقرير يصل من القنوات الثلاث جميعاً")
B.mt5.DEAL_REASON_SL, B.mt5.DEAL_REASON_TP = 4, 5
B.mt5.copy_rates_from_pos = lambda *a, **k: None
for channel, magic, label, entry, deal_price, reason, profit in [
    ("whales", B.MAGIC_WHALES, "الحيتان", 4228.0, 4222.0, 4, -6.0),
    ("kings", B.MAGIC_KINGS, "KINGS", 4634.5, 4640.0, 5, 5.5),
    ("sunny", B.MAGIC_SUNNY, "Gold Trader Sunny", 4646.0, 4649.2, 3, 3.2),
]:
    B._open_trades.clear()
    B._group_results.clear()
    B._zone_groups.clear()
    ticket = 6000
    B._open_trades[ticket] = {
        "channel": channel, "direction": "BUY", "entry": entry,
        "ticket": ticket, "opened_at": time.time() - 540,
        "peak_move": 0.0, "worst_move": 0.0,
        "group_id": f"{channel}:g", "hour": 14, "fp": "BUY",
    }
    live = types.SimpleNamespace(ticket=ticket, magic=magic, type=1,
                                 price_open=entry, sl=0.0, tp=0.0)
    B.mt5.positions_get = lambda *a, **k: [live]
    price["p"] = deal_price
    B.track_channel_excursions("XAUUSD.vnw")
    B.mt5.positions_get = lambda *a, **k: []
    B.mt5.history_deals_get = lambda *a, **k: [types.SimpleNamespace(
        price=deal_price, reason=reason, profit=profit, swap=0.0, commission=-0.02)]
    notices.clear()
    B.report_closed_channel_trades("XAUUSD.vnw")
    check(f"{label}: وصل تقرير الصفقة + الختامي", len(notices), 2)
    check(f"{label}: التقرير باسم القناة", label in notices[0], True)
    check(f"{label}: يذكر سعر الدخول", f"{entry:.2f}" in notices[0], True)
    check(f"{label}: يذكر سعر الخروج", f"{deal_price:.2f}" in notices[0], True)
    check(f"{label}: يذكر ماذا جرى", "ماذا جرى" in notices[0], True)

print("\n[١٢.٦] الأمر المعلق يسجل لحظة تفعيله لا وقت التوصية")
B._pending_meta.clear()
B._open_trades.clear()
signal_time = time.time() - 7200  # التوصية قبل ساعتين
B._pending_meta[7777] = {
    "channel": "kings", "direction": "BUY", "group_id": "kings:p",
    "created_at": signal_time, "placed_at": signal_time, "entry": 4619.0,
}
filled = types.SimpleNamespace(ticket=8888, identifier=8888, magic=B.MAGIC_KINGS,
                               type=1, price_open=4619.0, sl=0.0, tp=0.0)
B.mt5.orders_get = lambda *a, **k: []
B.mt5.positions_get = lambda *a, **k: [filled]
B.mt5.history_deals_get = lambda *a, **k: [
    types.SimpleNamespace(order=7777, position_id=8888)
]
B.modify_channel_position = lambda *a, **k: True
B._adopt_activated_channel_orders("XAUUSD.vnw")
adopted = B._open_trades.get(8888, {})
check("الأمر المفعّل انتقل للتتبع", bool(adopted), True)
check("سجّل لحظة التفعيل لا وقت التوصية",
      adopted.get("opened_at", 0) - signal_time > 3000, True)
check("جهّز تتبع أقصى ربح", adopted.get("peak_move"), 0.0)

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
