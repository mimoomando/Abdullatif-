"""محاكاة كاملة للبوت من وصول التوصية حتى إغلاق الصفقة.

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
    broker.move(price)
    B._open_trades.clear()
    B._pending_meta.clear()
    B._zone_groups.clear()
    B._group_results.clear()
    B._processed_signals.clear()
    B._last_signal.clear()
    B._unread_signal_notice.clear()
    # نظام التعلم القديم يحظر الساعة بعد خسائر متتالية؛ خسائر قسم
    # سابق يجب ألا تمنع القسم التالي من الفتح
    B.learner.data["bad_hours"] = []
    B.learner.data["blocked_patterns"] = []
    B.strategy_killer.data.clear()
    alerts.clear()


def bot_positions(magic=None):
    return [
        p for p in broker.positions.values()
        if magic is None or p.magic == magic
    ]


def pump(times=3):
    """يشغّل دورات الإدارة كما تفعل الخيوط الحقيقية."""
    for _ in range(times):
        B.open_due_zone_levels(SYMBOL)
        B.track_channel_excursions(SYMBOL)
        B.manage_unified_channel_groups(SYMBOL)
        B.manage_manual_positions(SYMBOL)
        B.report_closed_channel_trades(SYMBOL)


KINGS_SIGNAL = """XAUUSD BUY NOW 4609-4610
Sl 4604

Tp 4613
Tp 4618
Tp 4623
Tp open"""

WHALES_SIGNAL = """بسم الله
Gold buy Now 4612-4608
* Tp1 4620
* Tp2 4630
* Tp3 open
SL 4602"""

SUNNY_SELL = """Gold Short Zone:4612-4616

Stop: 4620

Target 1: 4604
Target 2: 4598"""


print("\n" + "═" * 60)
print("  [١] توصية KINGS — الحالة النهائية عند الوسيط")
print("═" * 60)
reset(4610.0)
B.handle_kings_message(SYMBOL, KINGS_SIGNAL, "flow:kings")
pump()
kings = bot_positions(B.MAGIC_KINGS)
check("فُتحت خمس صفقات", len(kings), 5)
check("كلها 0.01 لوت", {p.volume for p in kings}, {0.01})
check("كلها شراء", {p.type for p in kings}, {TYPE_BUY})
check("كلها بوقف", all(p.sl > 0 for p in kings), True)
check("الوقف $6 تحت الدخول",
      {round(p.price_open - p.sl, 2) for p in kings}, {6.0})
check("كلها بهدف — لا صفقة بلا TP", all(p.tp > 0 for p in kings), True)
# الهدف المكتوب عند الوسيط هو الذي يلي الهدف الفعّال: القناة تنقل
# الهدف عند الاقتراب منه بدولار، فلا يصح أن يغلقنا الوسيط عند هدف
# ننوي تجاوزه لو قفز السعر فوقه بين دورتين.
check("الهدف المكتوب هو TP2 لا TP1", {p.tp for p in kings}, {4618.0})
print(f"     الدخول {kings[0].price_open} | SL {kings[0].sl} | TP {kings[0].tp}")

print("\n" + "═" * 60)
print("  [٢] السعر يتحرك — السلّم والتأمين")
print("═" * 60)
broker.move(4612.2)  # اقتراب دولار من TP1
pump()
check("اقترب من TP1 → الهدف الفعّال TP2 والمكتوب TP3",
      {p.tp for p in bot_positions(B.MAGIC_KINGS)}, {4623.0})
check("قفزة فوق TP1 لا تُغلق شيئاً — لم يعد هدفاً عند الوسيط",
      any(p.tp <= 4613.0 for p in bot_positions(B.MAGIC_KINGS)), False)

broker.move(4613.5)  # ربح +$3 من الدخول
pump()
after = bot_positions(B.MAGIC_KINGS)
check("عند +$3 أُغلقت ثلاث وبقيت اثنتان", len(after), 2)
check("الباقيتان على وقف الدخول",
      all(abs(p.sl - p.price_open) < 0.05 for p in after), True)
check("وأُغلقت الثلاث بربح",
      all(profit > 0 for _, profit in broker.closed), True)
print(f"     أُغلق {len(broker.closed)} بربح "
      f"{sum(p for _, p in broker.closed):.2f}$")

broker.move(4616.5)  # تجاوز TP1 بثلاث درجات
pump()
check("تجاوز TP1 بـ$3 → الوقف يقفل عليه",
      {p.sl for p in bot_positions(B.MAGIC_KINGS)}, {4613.0})

print("\n" + "═" * 60)
print("  [٣] الحيتان — التوزيع على المنطقة")
print("═" * 60)
reset(4610.0)
B.handle_whales_message(SYMBOL, WHALES_SIGNAL, "flow:whales")
pump()
whales = bot_positions(B.MAGIC_WHALES)
check("ثلاثة مستويات فاتها السعر فُتحت", len(whales), 3)
check("كل صفقة بوقف $6",
      {round(p.price_open - p.sl, 2) for p in whales}, {6.0})
check("وكلها بهدف", all(p.tp > 0 for p in whales), True)

broker.move(4611.0)
pump()
check("المستوى الرابع عند لمسه", len(bot_positions(B.MAGIC_WHALES)), 4)
broker.move(4612.0)
pump()
check("والخامس", len(bot_positions(B.MAGIC_WHALES)), 5)
check("لا سادسة", len(bot_positions(B.MAGIC_WHALES)), 5)

print("\n" + "═" * 60)
print("  [٤] منع التعارض — بيع بينما الشراء مفتوح")
print("═" * 60)
alerts.clear()
B.handle_sunny_message(SYMBOL, SUNNY_SELL, "flow:sunny")
pump()
check("لم تُفتح صفقة بيع", len(bot_positions(B.MAGIC_SUNNY)), 0)
check("ووصل تنبيه التعارض",
      any("تعارض اتجاه" in a for a in alerts), True)

print("\n" + "═" * 60)
print("  [٥] الصفقة اليدوية")
print("═" * 60)
reset(4610.0)
manual = broker.manual_buy(volume=0.10)
pump()
position = broker.positions[manual]
check("ضُبط وقفها", round(position.price_open - position.sl, 2), 6.0)
check("وضُبط هدفها", round(position.tp - position.price_open, 2), 12.0)
check("ولم تُمس أحجامها", position.volume, 0.10)
check("ووصل تنبيه", any("صفقة يدوية" in a for a in alerts), True)
print(f"     الدخول {position.price_open} | SL {position.sl} | TP {position.tp}")

broker.move(4613.5)  # +$3 ربح
pump()
check("عند +$3 الوقف ينتقل للدخول",
      abs(broker.positions[manual].sl - position.price_open) < 0.05, True)
check("والهدف يبقى أبعد فتكمل الصفقة",
      round(broker.positions[manual].tp - position.price_open, 2), 12.0)

# وقف حسّنه صاحب الحساب بنفسه لا يُتراجع عنه
broker.positions[manual].sl = 4612.0
pump()
check("لا يتراجع عن وقف أفضل وضعه صاحب الحساب",
      broker.positions[manual].sl, 4612.0)

print("\n" + "═" * 60)
print("  [٦] تقرير الإغلاق")
print("═" * 60)
reset(4610.0)
B.handle_kings_message(SYMBOL, KINGS_SIGNAL, "flow:close")
pump()
opened = bot_positions(B.MAGIC_KINGS)
check("فُتحت المجموعة", len(opened), 5)
alerts.clear()
broker.move(4604.0)  # ضرب الوقف
for position in list(opened):
    broker.order_send({"action": ACTION_DEAL, "position": position.ticket,
                       "type": TYPE_SELL, "volume": position.volume,
                       "symbol": SYMBOL})
pump()
reports = [a for a in alerts if "أُغلقت صفقة" in a]
check("وصل تقرير لكل صفقة", len(reports), 5)
check("والتقرير الختامي", any("انتهت توصية" in a for a in alerts), True)
check("لا صفقات متبقية", len(bot_positions(B.MAGIC_KINGS)), 0)

print("\n" + "═" * 60)
print("  [٧] رفض الوسيط لتعديل الوقف لا يُغلق صفقة محمية")
print("═" * 60)
reset(4610.0)
broker.reject_sltp = True
B.handle_kings_message(SYMBOL, KINGS_SIGNAL, "flow:reject")
pump()
survived = bot_positions(B.MAGIC_KINGS)
check("الصفقات بقيت رغم رفض التعديل", len(survived), 5)
check("وكلها بوقف من الأمر نفسه", all(p.sl > 0 for p in survived), True)

print("\n" + "═" * 60)
print("  [٨] توصية صاعدة طويلة — والمجموعة ناقصة صفقة")
print("═" * 60)
# نسخة طبق الأصل من توصية KINGS التي أُغلقت كلها عند هدفها الأول:
# صعد الذهب من 4602 إلى 4643 وخرجت التوصية بـ$18 بدل $75.
LONG_SIGNAL = """XAUUSD BUY NOW 4601-4602
Sl 4596
Tp 4607
Tp 4612
Tp 4617
Tp 4622
Tp 4627
Tp 4632
Tp 4637
Tp 4647
Tp open"""

reset(4602.4)
B.handle_kings_message(SYMBOL, LONG_SIGNAL, "flow:long")
pump(2)
check("فُتحت الخمس", len(bot_positions(B.MAGIC_KINGS)), 5)

# صفقة تغادر المجموعة (أُغلقت من المنصة) — كان هذا يجمّد الإدارة كلها
_victim = sorted(broker.positions)[0]
broker.positions.pop(_victim)
broker.deals[_victim] = [types.SimpleNamespace(
    price=broker.bid, reason=3, profit=0.0, swap=0.0, commission=0.0,
    order=_victim, position_id=_victim)]
broker.closed.append((_victim, 0.0))
check("بقيت أربع", len(bot_positions(B.MAGIC_KINGS)), 4)

_path = [4602.4 + i * 0.1 for i in range(410)] + [4643.3 - i * 0.2 for i in range(60)]
for _price in _path:
    broker.move(_price)
    broker.sweep()
    pump(1)
    if not bot_positions(B.MAGIC_KINGS):
        break

_exits = sorted(profit for ticket, profit in broker.closed if ticket != _victim)
check("أُغلقت الأربع", len(_exits), 4)
check("اثنتان مؤمَّنتان عند +$3", _exits[:2], [3.0, 3.0])
check("واثنتان ركبتا الصعود لا عند الهدف الأول",
      all(profit > 30 for profit in _exits[2:]), True)
check("مجموع التوصية أكبر من $70", sum(_exits) > 70, True)
_closing = [a for a in alerts if "أُغلقت صفقة" in a]
check("ووصل تقرير لكل صفقة بما فيها المؤمَّنة", len(_closing), 5)
print(f"     النتائج: {_exits} → {sum(_exits):+.2f}$")

print(f"\n{'─' * 60}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
