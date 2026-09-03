"""محاكاة كاملة للبوت من وصول التوصية حتى إغلاق الصفقة.

البوت صار قناة واحدة: بوت توصيات الذهب (n8n). التوصية تفتح صفقة
واحدة فوراً، ووقفها وهدفها مسافتان مكتوبتان في التوصية (خطر/ربح)
تُقاسان من سعر التنفيذ الفعلي لا من سعر التوصية المكتوب.

    python3 test_full_flow.py

الفرق عن test_channel_zones.py: هذا لا يفحص الدوال منفردة، بل يبني
وسيطاً وهمياً كاملاً (MT5 fake broker) يحفظ الصفقات ويطبّق الأوامر،
ثم يشغّل البوت عليه ويتحقق من **كل حقل على كل صفقة عند الوسيط**:
اللوت، الاتجاه، سعر الدخول، الوقف، الهدف، والعدد.

سبب وجوده: أخطاء ظهرت على حساب حقيقي رغم نجاح فحوص الوحدات —
صفقات فُتحت بلا هدف، وأخرى أُغلقت لحظة فتحها. تلك أخطاء لا يكشفها
إلا فحص الحالة النهائية عند الوسيط.
"""
import os
import sys
import tempfile
import time
import types

# ── وسيط وهمي كامل: يحفظ الصفقات وينفّذ الأوامر عليها ──
DONE = 10009
NO_CHANGES = 10025


class FakeBroker:
    def __init__(self, price=4610.0, spread=0.20):
        self.bid = price
        self.spread = spread
        self.positions = {}
        self.orders = {}
        self.deals = {}
        self.next_ticket = 5000
        self.closed = []
        self.reject_sltp = False
        self.sltp_calls = 0        # كم أمر تعديل وقف/هدف وصل الوسيط

    # ── أسعار ──
    @property
    def ask(self):
        return round(self.bid + self.spread, 2)

    def move(self, price):
        self.bid = round(price, 2)

    def tick(self, *a, **k):
        return types.SimpleNamespace(bid=self.bid, ask=self.ask)

    # ── استعلامات ──
    def positions_get(self, symbol=None, **k):
        return list(self.positions.values())

    def orders_get(self, symbol=None, **k):
        return list(self.orders.values())

    def history_deals_get(self, *a, position=None, **k):
        if position is not None:
            return self.deals.get(position, [])
        return [d for group in self.deals.values() for d in group]

    def symbols_get(self, *a, **k):
        return []

    # ── تنفيذ الأوامر ──
    def order_send(self, request):
        action = request.get("action")
        if action == ACTION_DEAL:
            return self._deal(request)
        if action == ACTION_SLTP:
            return self._sltp(request)
        if action == ACTION_REMOVE:
            self.orders.pop(request.get("order"), None)
            return types.SimpleNamespace(retcode=DONE, comment="removed")
        return types.SimpleNamespace(retcode=10013, comment="unsupported")

    def _deal(self, request):
        is_buy = request["type"] == TYPE_BUY
        closing = request.get("position")
        if closing:  # إغلاق صفقة قائمة
            position = self.positions.pop(closing, None)
            if position is None:
                return types.SimpleNamespace(retcode=10013, comment="no position")
            exit_price = self.bid if position.type == TYPE_BUY else self.ask
            profit = (exit_price - position.price_open) * (
                1 if position.type == TYPE_BUY else -1
            ) * (position.volume / 0.01)
            self.deals[closing] = [types.SimpleNamespace(
                price=exit_price, reason=3, profit=round(profit, 2),
                swap=0.0, commission=0.0, order=closing, position_id=closing)]
            self.closed.append((closing, round(profit, 2)))
            return types.SimpleNamespace(retcode=DONE, order=closing, deal=closing,
                                         comment="closed")
        self.next_ticket += 1
        ticket = self.next_ticket
        price = self.ask if is_buy else self.bid
        self.positions[ticket] = types.SimpleNamespace(
            ticket=ticket, identifier=ticket, magic=request.get("magic", 0),
            type=TYPE_BUY if is_buy else TYPE_SELL, volume=request["volume"],
            price_open=price, sl=float(request.get("sl") or 0.0),
            tp=float(request.get("tp") or 0.0), comment=request.get("comment", ""))
        return types.SimpleNamespace(retcode=DONE, order=ticket, deal=ticket,
                                     comment="filled")

    def _sltp(self, request):
        self.sltp_calls += 1
        position = self.positions.get(request["position"])
        if position is None:
            return types.SimpleNamespace(retcode=10013, comment="no position")
        if self.reject_sltp:
            return types.SimpleNamespace(retcode=10016, comment="Invalid stops")
        new_sl = float(request.get("sl") or 0.0)
        new_tp = float(request.get("tp") or 0.0)
        if abs(position.sl - new_sl) < 0.001 and abs(position.tp - new_tp) < 0.001:
            return types.SimpleNamespace(retcode=NO_CHANGES, comment="no changes")
        position.sl, position.tp = new_sl, new_tp
        return types.SimpleNamespace(retcode=DONE, comment="modified")

    # ── الوسيط ينفّذ الوقف والهدف بنفسه ──
    # نقص هذا هو ما أخفى خطأ حساب حقيقي: توصية صعدت $40 أُغلقت كلها
    # عند هدفها الأول لأن الاختبار لم يكن يغلق شيئاً عند لمس الهدف.
    def sweep(self):
        for ticket, position in list(self.positions.items()):
            is_buy = position.type == TYPE_BUY
            price = self.bid if is_buy else self.ask
            hit_tp = position.tp and (
                price >= position.tp if is_buy else price <= position.tp)
            hit_sl = position.sl and (
                price <= position.sl if is_buy else price >= position.sl)
            if not (hit_tp or hit_sl):
                continue
            exit_price = float(position.tp if hit_tp else position.sl)
            profit = (exit_price - position.price_open) * (1 if is_buy else -1)
            profit *= position.volume / 0.01
            self.positions.pop(ticket)
            self.deals[ticket] = [types.SimpleNamespace(
                price=exit_price, reason=5 if hit_tp else 4,
                profit=round(profit, 2), swap=0.0, commission=0.0,
                order=ticket, position_id=ticket)]
            self.closed.append((ticket, round(profit, 2)))

    # ── ما يفتحه صاحب الحساب بنفسه ──
    def manual_buy(self, volume=0.10):
        self.next_ticket += 1
        ticket = self.next_ticket
        self.positions[ticket] = types.SimpleNamespace(
            ticket=ticket, identifier=ticket, magic=0, type=TYPE_BUY,
            volume=volume, price_open=self.ask, sl=0.0, tp=0.0, comment="manual")
        return ticket


_fake = types.ModuleType("MetaTrader5")
_names = [
    "TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15", "TIMEFRAME_M30",
    "TIMEFRAME_H1", "ORDER_TIME_GTC", "ORDER_TIME_SPECIFIED",
    "ORDER_FILLING_IOC", "ORDER_FILLING_FOK", "ORDER_FILLING_RETURN",
    "ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT",
    "ORDER_TYPE_BUY_STOP", "ORDER_TYPE_SELL_STOP",
    "ACCOUNT_TRADE_MODE_REAL", "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING",
]
for _i, _name in enumerate(_names):
    setattr(_fake, _name, 100 + _i)
ACTION_DEAL, ACTION_SLTP, ACTION_PENDING, ACTION_REMOVE = 1, 2, 3, 4
TYPE_BUY, TYPE_SELL = 0, 1
_fake.TRADE_ACTION_DEAL = ACTION_DEAL
_fake.TRADE_ACTION_SLTP = ACTION_SLTP
_fake.TRADE_ACTION_PENDING = ACTION_PENDING
_fake.TRADE_ACTION_REMOVE = ACTION_REMOVE
_fake.ORDER_TYPE_BUY = TYPE_BUY
_fake.ORDER_TYPE_SELL = TYPE_SELL
_fake.POSITION_TYPE_BUY = TYPE_BUY
_fake.POSITION_TYPE_SELL = TYPE_SELL
_fake.TRADE_RETCODE_DONE = DONE
_fake.TRADE_RETCODE_NO_CHANGES = NO_CHANGES
_fake.DEAL_REASON_SL, _fake.DEAL_REASON_TP = 4, 5
_fake.last_error = lambda: (-1, "fake")
_fake.copy_rates_from_pos = lambda *a, **k: None
_fake.copy_rates_from = lambda *a, **k: None
_fake.account_info = lambda: None
_fake.terminal_info = lambda: None
sys.modules["MetaTrader5"] = _fake
sys.modules["requests"] = types.ModuleType("requests")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(tempfile.mkdtemp())

import master_bot as B  # noqa: E402

SYMBOL = "XAUUSD"
broker = FakeBroker()
_fake.symbol_info_tick = broker.tick
_fake.positions_get = broker.positions_get
_fake.orders_get = broker.orders_get
_fake.history_deals_get = broker.history_deals_get
_fake.order_send = broker.order_send
_fake.symbols_get = broker.symbols_get

B._channel_runtime_mode.update({"enabled": False, "symbol": SYMBOL})
alerts = []
B.notify_tg = lambda text: alerts.append(text)
B.send_tg = lambda text: alerts.append(text)

ok = fails = 0


def check(name, got, want):
    global ok, fails
    if got == want:
        ok += 1
        print(f"  ✅ {name}")
    else:
        fails += 1
        print(f"  ❌ {name}\n       المتوقع: {want}\n       الناتج : {got}")


def reset(price=4610.0):
    broker.positions.clear()
    broker.orders.clear()
    broker.deals.clear()
    broker.closed.clear()
    broker.reject_sltp = False
    broker.sltp_calls = 0
    broker.move(price)
    B._open_trades.clear()
    B._pending_meta.clear()
    B._group_results.clear()
    B._processed_signals.clear()
    B._last_signal.clear()
    B._unread_signal_notice.clear()
    B.learner.data["bad_hours"] = []
    B.learner.data["blocked_patterns"] = []
    alerts.clear()


def bot_positions(magic=None):
    return [
        p for p in broker.positions.values()
        if magic is None or p.magic == magic
    ]


def pump(times=3):
    """يشغّل دورات الإدارة كما يفعل خيط الإدارة الحقيقي."""
    for _ in range(times):
        B.track_channel_excursions(SYMBOL)
        B.manage_unified_channel_groups(SYMBOL)
        B.manage_manual_positions(SYMBOL)
        B.report_closed_channel_trades(SYMBOL)


GOLD = B.MAGIC_GOLDBOT


def rec(decision="SELL", entry=4289.82, stop=4297.82, target=4273.82,
        risk="8.00", reward="16.00", confidence=82):
    """توصية بصيغة البوت الحقيقية."""
    return (
        f"🟡 توصية الذهب\n\n"
        f"القرار: {decision}\n"
        f"الثقة: {confidence}%\n\n"
        f"📍 الدخول: {entry}\n"
        f"🛑 الوقف: {stop} (خطر ${risk})\n"
        f"🎯 الهدف: {target} (ربح ${reward})\n\n"
        f"📊 التحليل:\nاتجاه هبوطي على 5m و15m.\n\n"
        f"This message was sent automatically with n8n"
    )


print("\n" + "═" * 60)
print("  [١] توصية بيع — الحالة النهائية عند الوسيط")
print("═" * 60)
# السوق عند 4306 والتوصية كُتبت عند 4289.82: الفارق لا يعنينا،
# المهم أن تكون المسافتان $8 و$16 من سعر التنفيذ الفعلي.
reset(4306.0)
B.handle_goldbot_message(SYMBOL, rec(), "flow:sell")
pump()
rows = bot_positions(GOLD)
check("فُتحت صفقة واحدة", len(rows), 1)
check("بلوت 0.10", rows[0].volume, 0.10)
check("وهي بيع", rows[0].type, TYPE_SELL)
_entry = rows[0].price_open
check("الوقف $8 فوق التنفيذ", round(rows[0].sl - _entry, 2), 8.0)
check("والهدف $16 تحته", round(_entry - rows[0].tp, 2), 16.0)
check("ولم يُستعمل سعر التوصية المكتوب 4289.82",
      abs(_entry - 4289.82) > 1.0, True)
check("ووصل تنبيه بالتنفيذ", any("توصية بوت التوصيات" in a for a in alerts), True)
print(f"     الدخول {_entry} | الوقف {rows[0].sl} | الهدف {rows[0].tp}")

for _ in range(10):
    pump()
check("والإدارة لا تعبث بهما",
      (round(bot_positions(GOLD)[0].sl - _entry, 2),
       round(_entry - bot_positions(GOLD)[0].tp, 2)), (8.0, 16.0))
check("ولا أوامر تعديل بعد الاستقرار", broker.sltp_calls <= 1, True)

print("\n" + "═" * 60)
print("  [٢] الوصول إلى الهدف — والتقرير")
print("═" * 60)
alerts.clear()
broker.move(round(_entry - 16.0, 2) - 0.2)
broker.sweep()
pump()
check("أُغلقت عند الهدف", len(bot_positions(GOLD)), 0)
check("والربح $160 (0.10 لوت × 16 درجة)",
      round(broker.closed[0][1], 2), 160.0)
check("ووصل تقرير الإغلاق", any("أُغلقت" in a for a in alerts), True)

print("\n" + "═" * 60)
print("  [٣] ضرب الوقف")
print("═" * 60)
reset(4306.0)
B.handle_goldbot_message(SYMBOL, rec(), "flow:sl")
pump()
_e = bot_positions(GOLD)[0].price_open
broker.move(round(_e + 8.0, 2) + 0.2)
broker.sweep()
pump()
check("أُغلقت عند الوقف", len(bot_positions(GOLD)), 0)
check("والخسارة $80", round(broker.closed[0][1], 2), -80.0)

print("\n" + "═" * 60)
print("  [٤] توصية شراء")
print("═" * 60)
reset(4300.0)
B.handle_goldbot_message(
    SYMBOL,
    rec(decision="BUY", entry=4300.0, stop=4294.0, target=4312.0,
        risk="6.00", reward="12.00"),
    "flow:buy")
pump()
b = bot_positions(GOLD)
check("صفقة شراء واحدة", (len(b), b[0].type), (1, TYPE_BUY))
check("الوقف $6 تحت التنفيذ", round(b[0].price_open - b[0].sl, 2), 6.0)
check("والهدف $12 فوقه", round(b[0].tp - b[0].price_open, 2), 12.0)

print("\n" + "═" * 60)
print("  [٥] HOLD لا يفتح شيئاً")
print("═" * 60)
reset(4306.0)
alerts.clear()
HOLD = (
    "🟡 توصية الذهب\n\nالقرار: HOLD\nالثقة: 65%\n\n"
    "🎯 الهدف: 4450.09\n🛑 الوقف: 4450.09\n\nالقرار: انتظار (لا صفقة)"
)
B.handle_goldbot_message(SYMBOL, HOLD, "flow:hold")
pump()
check("لم تُفتح صفقة", len(bot_positions(GOLD)), 0)
check("ولا رسالة", alerts, [])

print("\n" + "═" * 60)
print("  [٦] الرسالة المزدوجة — البوت يرسل التوصية مرتين في رسالة واحدة")
print("═" * 60)
# صورة حقيقية من القناة: كتلة بلا دخول ثم الكتلة الكاملة بعدها
DOUBLE = (
    "🟡 توصية الذهب  القرار: SELL\nالثقة: 82%\n\n"
    "🎯 الهدف: 4273.82\n🛑 الوقف: 4297.82\n\n"
    "📊 التحليل:\nاتجاه هبوطي قوي.\n"
    "🟡 توصية الذهب\n\nالقرار: SELL\nالثقة: 82%\n\n"
    "📍 الدخول: 4289.82\n🛑 الوقف: 4297.82 (خطر $8.00)\n"
    "🎯 الهدف: 4273.82 (ربح $16.00)\n\n"
    "This message was sent automatically with n8n"
)
reset(4306.0)
B.handle_goldbot_message(SYMBOL, DOUBLE, "flow:double")
pump()
d = bot_positions(GOLD)
check("صفقة واحدة لا اثنتان", len(d), 1)
check("بالمسافتين الصحيحتين",
      (round(d[0].sl - d[0].price_open, 2),
       round(d[0].price_open - d[0].tp, 2)), (8.0, 16.0))

print("\n" + "═" * 60)
print("  [٧] لا تتراكم الصفقات")
print("═" * 60)
alerts.clear()
B.handle_goldbot_message(SYMBOL, rec(target=4272.0, reward="17.00"),
                         "flow:second")
pump()
check("توصية ثانية والأولى مفتوحة → لا تُفتح", len(bot_positions(GOLD)), 1)
check("ووصل تنبيه بالتخطي", any("تُخطّيت" in a for a in alerts), True)

print("\n" + "═" * 60)
print("  [٨] نفس التوصية مكررة")
print("═" * 60)
reset(4306.0)
B.handle_goldbot_message(SYMBOL, rec(), "flow:dup")
pump()
B.handle_goldbot_message(SYMBOL, rec(), "flow:dup")   # نفس هوية الرسالة
pump()
check("لا تُفتح مرتين", len(bot_positions(GOLD)), 1)

print("\n" + "═" * 60)
print("  [٩] توصيات لا يقبلها البوت")
print("═" * 60)
reset(4306.0)
B.handle_goldbot_message(SYMBOL, "صباح الخير يا شباب 4300 4310", "bad:chat")
pump()
check("كلام عادي لا يفتح شيئاً", len(bot_positions(GOLD)), 0)

alerts.clear()
B.handle_goldbot_message(
    SYMBOL, rec(stop=4400.0, risk="110.00"), "bad:risk")
pump()
check("وقف بعيد جداً يُرفض", len(bot_positions(GOLD)), 0)
check("ووصل تنبيه بالرفض", any("رُفضت" in a for a in alerts), True)

alerts.clear()
B.handle_goldbot_message(
    SYMBOL, rec(target=4100.0, reward="190.00"), "bad:reward")
pump()
check("هدف بعيد جداً يُرفض", len(bot_positions(GOLD)), 0)

B.handle_goldbot_message(
    SYMBOL,
    "🟡 توصية الذهب\n\nالقرار: BUY\n📍 الدخول: 4300\n"
    "🛑 الوقف: 4310\n🎯 الهدف: 4290",
    "bad:side")
pump()
check("اتجاه يخالف موضع الوقف يُرفض", len(bot_positions(GOLD)), 0)

print("\n" + "═" * 60)
print("  [١٠] وقفك وهدفك اليدويان على صفقة القناة")
print("═" * 60)
reset(4306.0)
alerts.clear()
B.handle_goldbot_message(SYMBOL, rec(), "flow:manualedit")
pump()
_t = bot_positions(GOLD)[0].ticket
broker.positions[_t].sl = 4330.0
broker.positions[_t].tp = 4260.0
for _ in range(10):
    pump()
check("وقفك بقي", bot_positions(GOLD)[0].sl, 4330.0)
check("وهدفك بقي", bot_positions(GOLD)[0].tp, 4260.0)
check("ووصل تنبيه بأن البوت تركهما",
      (any("وقف يدوي" in a for a in alerts),
       any("هدف يدوي" in a for a in alerts)), (True, True))
_calls = broker.sltp_calls
for _ in range(10):
    pump()
check("ولا يحاول إعادتهما", broker.sltp_calls - _calls, 0)

print("\n" + "═" * 60)
print("  [١١] الصفقة اليدوية")
print("═" * 60)
reset(4600.0)
manual = broker.manual_buy(volume=0.10)
pump()
position = broker.positions[manual]
check("ضُبط وقفها $6", round(position.price_open - position.sl, 2), 6.0)
check("وهدفها $5", round(position.tp - position.price_open, 2), 5.0)
check("ولم تُمس أحجامها", position.volume, 0.10)
check("ووصل تنبيه", any("صفقة يدوية" in a for a in alerts), True)

broker.move(4603.0)   # +$2.8 — دون التأمين
pump()
check("دون +$4 لا ينتقل الوقف",
      round(position.price_open - broker.positions[manual].sl, 2), 6.0)

broker.move(4604.5)   # +$4.3
pump()
check("وعند +$4 ينتقل الوقف إلى الدخول",
      abs(broker.positions[manual].sl - position.price_open) < 0.05, True)
check("والهدف يبقى $5",
      round(broker.positions[manual].tp - position.price_open, 2), 5.0)

_sltp = broker.sltp_calls
for _ in range(15):
    pump()
check("ولا أوامر تعديل بعد الاستقرار", broker.sltp_calls - _sltp, 0)

print("\n" + "═" * 60)
print("  [١٢] الصفقة اليدوية — تعديلك أنت")
print("═" * 60)
reset(4600.0)
_m = broker.manual_buy(volume=0.02)
pump()
broker.positions[_m].sl = 4570.0
broker.positions[_m].tp = 4700.0
for _ in range(8):
    pump()
check("وقفك بقي", broker.positions[_m].sl, 4570.0)
check("وهدفك بقي", broker.positions[_m].tp, 4700.0)
broker.move(4605.0)   # +$4.8 — التأمين لا يزيح تعديلك
for _ in range(5):
    pump()
check("ولا يزيحه التأمين", broker.positions[_m].sl, 4570.0)

# وصفقة تفتحها ومعها وقفك وهدفك: لا يمسّهما أصلاً
reset(4600.0)
_m2 = broker.next_ticket + 1
broker.next_ticket = _m2
broker.positions[_m2] = types.SimpleNamespace(
    ticket=_m2, identifier=_m2, magic=0, type=TYPE_BUY, volume=0.01,
    price_open=4600.0, sl=4560.0, tp=4680.0, comment="mine")
for _ in range(6):
    pump()
check("فتحتها بوقفك — بقي", broker.positions[_m2].sl, 4560.0)
check("وبهدفك — بقي", broker.positions[_m2].tp, 4680.0)

print("\n" + "═" * 60)
print("  [١٣] البوت لا يخلط صفقة القناة بصفقتك اليدوية")
print("═" * 60)
reset(4306.0)
B.handle_goldbot_message(SYMBOL, rec(), "mix:gold")
pump()
_mine = broker.manual_buy(volume=0.01)
pump()
check("صفقة القناة واحدة", len(bot_positions(GOLD)), 1)
check("وصفقتك اليدوية ضُبطت $6/$5",
      (round(broker.positions[_mine].price_open
             - broker.positions[_mine].sl, 2),
       round(broker.positions[_mine].tp
             - broker.positions[_mine].price_open, 2)), (6.0, 5.0))
check("وصفقة القناة على مسافتَي توصيتها",
      (round(bot_positions(GOLD)[0].sl
             - bot_positions(GOLD)[0].price_open, 2),
       round(bot_positions(GOLD)[0].price_open
             - bot_positions(GOLD)[0].tp, 2)), (8.0, 16.0))

print("\n" + "═" * 60)
print("  [١٤] رفض الوسيط لتعديل الوقف لا يُغلق صفقة محمية")
print("═" * 60)
reset(4306.0)
broker.reject_sltp = True
B.handle_goldbot_message(SYMBOL, rec(), "flow:reject")
pump()
survived = bot_positions(GOLD)
check("الصفقة بقيت رغم رفض التعديل", len(survived), 1)
check("وبوقف من الأمر نفسه", round(survived[0].sl - survived[0].price_open, 2),
      8.0)
broker.reject_sltp = False

print(f"\n{'─' * 60}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
