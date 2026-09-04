"""فحص الدوال منفردة — بلا MetaTrader5 ولا اتصال بالوسيط:

    python3 test_channel_zones.py

يوثّق المواصفة المتفق عليها للبوت:
  • قناة واحدة: بوت توصيات الذهب (n8n)
  • كل توصية تفتح صفقة واحدة 0.10 فوراً
  • الوقف على بُعد «خطر $X» والهدف على بُعد «ربح $Y» من سعر التنفيذ
    الفعلي — سعر التوصية المكتوب لا يُستعمل إطلاقاً
  • رسالة HOLD لا تفتح شيئاً
  • الصفقة اليدوية: وقف $6 وهدف $5، والوقف ينتقل للدخول عند +$4
  • وما يحرّكه صاحب الحساب بيده لا يلمسه البوت أبداً
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


SELL_REC = """🟡 توصية الذهب

القرار: SELL
الثقة: 82%

📍 الدخول: 4289.82
🛑 الوقف: 4297.82 (خطر $8.00)
🎯 الهدف: 4273.82 (ربح $16.00)

📊 التحليل:
اتجاه هبوطي قوي على 5m و15m.

This message was sent automatically with n8n"""

HOLD_REC = """🟡 توصية الذهب

القرار: HOLD
الثقة: 65%

🎯 الهدف: 4450.09
🛑 الوقف: 4450.09

القرار: انتظار (لا صفقة)"""

print("\n[١] قراءة توصية البيع")
g = B.parse_gold_bot_signal(SELL_REC)
check("القرار بيع", g["decision"], "SELL")
check("مسافة الخطر $8", g["risk"], 8.0)
check("مسافة الربح $16", g["reward"], 16.0)
check("الوقف والهدف مقروءان", (g["stop"], g["target"]), (4297.82, 4273.82))
check("وسعر الدخول مقروء للتحقق فقط", g["entry"], 4289.82)

print("\n[٢] رسائل لا تفتح شيئاً")
check("HOLD", B.parse_gold_bot_signal(HOLD_REC)["decision"], "HOLD")
check("'انتظار' وحدها",
      B.parse_gold_bot_signal(
          "القرار: انتظار\nالوقف: 4300\nالهدف: 4310")["decision"], "HOLD")
check("الهدف = الوقف",
      B.parse_gold_bot_signal(
          "القرار: SELL\nالوقف: 4300\nالهدف: 4300")["decision"], "HOLD")
check("كلام عادي", B.parse_gold_bot_signal("صباح الخير 4300 4310"), None)
check("توصية بلا وقف",
      B.parse_gold_bot_signal("القرار: BUY\nالهدف: 4310"), None)
check("توصية بلا هدف",
      B.parse_gold_bot_signal("القرار: BUY\nالوقف: 4290"), None)
check("اتجاه يخالف موضع الوقف",
      B.parse_gold_bot_signal(
          "القرار: BUY\nالدخول: 4300\nالوقف: 4310\nالهدف: 4290"), None)
check("دخول خارج ما بين الوقف والهدف",
      B.parse_gold_bot_signal(
          "القرار: BUY\nالدخول: 4320\nالوقف: 4294\nالهدف: 4312"), None)

print("\n[٣] المسافتان حين لا تُكتبان صراحةً")
_d = B.parse_gold_bot_signal(
    "القرار: BUY\nالدخول: 4300\nالوقف: 4294\nالهدف: 4312")
check("تُحسبان من أرقام التوصية", (_d["risk"], _d["reward"]), (6.0, 12.0))
check("والأرقام العربية تُقرأ",
      B.parse_gold_bot_signal(
          "القرار: SELL\nالدخول: ٤٣٠٠\nالوقف: ٤٣٠٦\nالهدف: ٤٢٩٠"
      )["risk"], 6.0)
check("والشراء يُقرأ بالعربية",
      B.parse_gold_bot_signal(
          "القرار: شراء\nالدخول: 4300\nالوقف: 4294\nالهدف: 4312"
      )["decision"], "BUY")

print("\n[٤] الرسالة المزدوجة — التوصية مكتوبة مرتين في رسالة واحدة")
DOUBLE = (
    "🟡 توصية الذهب  القرار: SELL\nالثقة: 82%\n\n"
    "🎯 الهدف: 4273.82\n🛑 الوقف: 4297.82\n\n"
    "📊 التحليل: اتجاه هبوطي.\n"
    "🟡 توصية الذهب\n\nالقرار: SELL\nالثقة: 82%\n\n"
    "📍 الدخول: 4289.82\n🛑 الوقف: 4297.82 (خطر $8.00)\n"
    "🎯 الهدف: 4273.82 (ربح $16.00)"
)
_dbl = B.parse_gold_bot_signal(DOUBLE)
check("تُقرأ توصية واحدة", _dbl["decision"], "SELL")
check("بالمسافتين الصحيحتين", (_dbl["risk"], _dbl["reward"]), (8.0, 16.0))

print("\n[٥] سياسة القناة")
check("قناة واحدة", list(B.CHANNEL_MAGICS), [B.GOLDBOT_CHANNEL])
check("صفقة واحدة",
      B.channel_policy(B.GOLDBOT_CHANNEL, "position_count"), 1)
check("بلوت 0.03", B.channel_policy(B.GOLDBOT_CHANNEL, "position_lot"), 0.03)
check("ولا حارس سقف يمنع توصية",
      hasattr(B, "channel_cap_allows") or hasattr(B, "no_conflicting_direction"),
      False)
check("اسم القناة معروف",
      B.channel_of("booooooootttttt"), B.GOLDBOT_CHANNEL)
check("والاسم غير المعروف لا يُطابَق", B.channel_of("قناة أخرى"), None)
check("حد الخطر الأعلى", B.GOLDBOT_MAX_RISK_USD, 20.0)
check("وحد الربح الأعلى", B.GOLDBOT_MAX_REWARD_USD, 60.0)

print("\n[٦] مسافتا الصفقة")
check("من التوصية نفسها",
      B.fixed_group_levels({"channel": B.GOLDBOT_CHANNEL,
                            "fixed_sl_usd": 8.0, "fixed_tp_usd": 16.0}),
      (8.0, 16.0))
check("وبلا مسافتين لا تُدار",
      B.fixed_group_levels({"channel": B.GOLDBOT_CHANNEL}), (0.0, 0.0))

print("\n[٧] الصفقة اليدوية")
check("وقف $6", B.MANUAL_SL_USD, 6.0)
check("هدف $5", B.MANUAL_TP_USD, 5.0)
check("والتأمين عند +$4", B.MANUAL_BREAKEVEN_USD, 4.0)

print("\n[٨] تطبيع النص العربي")
check("الأرقام العربية", B.normalize_arabic_digits("٤٣٠٠"), "4300")
check("فواصل الآلاف", B.normalize_signal_text("4,300"), "4300")
check("التاء المربوطة والهمزات",
      B.normalize_signal_text("توصيّة"), "توصيه")
check("الشرطات المختلفة", B.normalize_signal_text("4300–4290"),
      "4300-4290")

print("\n[٩] اتجاه الرسالة")
check("بيع", B.parse_direction("القرار: SELL"), "SELL")
check("شراء", B.parse_direction("القرار: BUY"), "BUY")
check("الاثنان معاً يُرفضان", B.parse_direction("BUY SELL"), None)
check("ولا اتجاه", B.parse_direction("الثقة 82%"), None)

print("\n[١٠] الوقف الأفضل لا يتراجع")
_p = types.SimpleNamespace(sl=4594.0, type=B.mt5.POSITION_TYPE_BUY)
check("شراء: الأعلى أفضل", B._better_stop(_p, 4598.0, True), 4598.0)
check("ولا يتراجع", B._better_stop(_p, 4590.0, True), 4594.0)
_s = types.SimpleNamespace(sl=4606.0, type=B.mt5.POSITION_TYPE_SELL)
check("بيع: الأدنى أفضل", B._better_stop(_s, 4602.0, False), 4602.0)
check("ولا يتراجع", B._better_stop(_s, 4610.0, False), 4606.0)

print("\n[١١] منع التوصية المكررة")
B._last_signal.clear()
check("أول مرة تمر", B._duplicate_signal("goldbot", "SELL|4297|4273"), False)
check("والثانية تُرفض", B._duplicate_signal("goldbot", "SELL|4297|4273"), True)
check("وتوصية مختلفة تمر",
      B._duplicate_signal("goldbot", "SELL|4300|4270"), False)

print(f"\n{'─' * 52}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
