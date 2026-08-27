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

print("\n" + "═" * 60)
print("  [٩] KINGS — وقف الباقيتين درجة تحت الدخول ثم عند الدخول")
print("═" * 60)
# مثال صاحب الحساب حرفياً: توصية 4600، وعند 4603 تُغلق ثلاث وتبقى
# اثنتان بوقف 4599، ولا يصعد الوقف إلى 4600 إلا عند اقتراب الهدف الأول.
NEAR_SIGNAL = """XAUUSD BUY NOW 4600
Sl 4594

Tp 4610
Tp 4615
Tp open"""

reset(4599.9)
B.handle_kings_message(SYMBOL, NEAR_SIGNAL, "flow:runner")
pump()
_entry = bot_positions(B.MAGIC_KINGS)[0].price_open
check("فُتحت الخمس", len(bot_positions(B.MAGIC_KINGS)), 5)
check("الوقف $6 تحت الدخول",
      {round(_entry - p.sl, 2) for p in bot_positions(B.MAGIC_KINGS)}, {6.0})

broker.move(round(_entry + 3.0, 2))  # +$3 → التأمين
pump()
_runners = bot_positions(B.MAGIC_KINGS)
check("أُغلقت ثلاث وبقيت اثنتان", len(_runners), 2)
check("وقف الباقيتين درجة تحت الدخول لا عنده",
      {round(p.price_open - p.sl, 2) for p in _runners}, {1.0})
check("ولم يصل الهدف الأول بعد — السلم لم يتحرك",
      all(p.tp == 4615.0 for p in _runners), True)
print(f"     الدخول {_entry} | وقف الباقيتين {_runners[0].sl}")

broker.move(4606.5)  # ما زال بعيداً عن الهدف الأول 4610
pump()
check("بعيداً عن الهدف الأول يبقى الوقف تحت الدخول",
      {round(p.price_open - p.sl, 2) for p in bot_positions(B.MAGIC_KINGS)},
      {1.0})

broker.move(4609.2)  # اقترب بدولار من الهدف الأول 4610
pump()
_after = bot_positions(B.MAGIC_KINGS)
check("عند اقتراب الهدف الأول → الوقف عند الدخول",
      {round(p.sl - p.price_open, 2) for p in _after}, {0.0})
check("ويتفعل السلم — الهدف تجاوز الأول",
      all(p.tp > 4610.0 for p in _after), True)
print(f"     الوقف {_after[0].sl} | الهدف {_after[0].tp}")

broker.move(4613.0)  # تجاوز الهدف الأول بـ$3 → الوقف يقفل عليه
pump()
check("تجاوز الهدف الأول بـ$3 → الوقف يقفل على 4610",
      {p.sl for p in bot_positions(B.MAGIC_KINGS)}, {4610.0})

print("\n" + "═" * 60)
print("  [١٠] آخر هدف في السلم — الهدف يُفتح والوقف يقفل عليه")
print("═" * 60)
LAST_TP_SIGNAL = """XAUUSD BUY NOW 4600
Sl 4594

Tp 4610
Tp 4615
Tp 4620
Tp open"""

reset(4599.9)
B.handle_kings_message(SYMBOL, LAST_TP_SIGNAL, "flow:lasttp")
pump()
_e = bot_positions(B.MAGIC_KINGS)[0].price_open

for _p in (4603.1, 4609.2, 4613.0, 4618.0):  # التأمين ثم صعود السلم
    broker.move(_p)
    broker.sweep()
    pump()
_mid = bot_positions(B.MAGIC_KINGS)
check("قبل آخر هدف: الهدف مكتوب والوقف على الهدف السابق",
      (_mid[0].tp, _mid[0].sl), (4620.0, 4615.0))

broker.move(4619.2)  # اقترب بدولار من آخر هدف رقمي
broker.sweep()
pump()
check("عند آخر هدف → الهدف يصبح مفتوحاً",
      {p.tp for p in bot_positions(B.MAGIC_KINGS)}, {0.0})

broker.move(4623.0)  # تجاوز آخر هدف بـ$3
broker.sweep()
pump()
_run = bot_positions(B.MAGIC_KINGS)
check("والوقف يقفل على آخر هدف", {p.sl for p in _run}, {4620.0})
check("والصفقتان ما زالتا مفتوحتين", len(_run), 2)

broker.move(4645.0)  # صعود بعيد — لا هدف يوقفها
broker.sweep()
pump()
_far = bot_positions(B.MAGIC_KINGS)
check("تكمل صعودها بلا هدف يغلقها", len(_far), 2)
check("والوقف يتتبع القمة بدل الوقوف عند آخر هدف",
      {p.sl for p in _far}, {4640.0})
print(f"     السعر 4645 | الوقف {_far[0].sl} | الهدف مفتوح")

# توصية بلا "open": آخر هدف هو المخرج فعلاً
CLOSED_LADDER = """XAUUSD BUY NOW 4600
Sl 4594

Tp 4610
Tp 4615"""
reset(4599.9)
B.handle_kings_message(SYMBOL, CLOSED_LADDER, "flow:closedladder")
pump()
for _p in (4603.1, 4609.2, 4614.5):
    broker.move(_p)
    broker.sweep()
    pump()
check("قبل آخر هدف تبقى مفتوحة بهدف مكتوب",
      {p.tp for p in bot_positions(B.MAGIC_KINGS)}, {4615.0})
broker.move(4615.0)
broker.sweep()
pump()
check("سلم بلا مفتوح → تخرج عند آخر هدف",
      len(bot_positions(B.MAGIC_KINGS)), 0)
check("والخروج على 4615",
      {broker.deals[t][0].price for t, _ in broker.closed[-2:]}, {4615.0})

print("\n" + "═" * 60)
print("  [١١] السلّم نفسه للحيتان وSunny — لا تختلف إلا في الدخول")
print("═" * 60)
LADDER_CASES = [
    ("whales", B.MAGIC_WHALES, B.handle_whales_message, """بسم الله
Gold buy Now 4600-4600
* Tp1 4610
* Tp2 4615
* Tp3 open
SL 4594"""),
    ("sunny", B.MAGIC_SUNNY, B.handle_sunny_message, """Gold Buy Zone: 4600-4600

Stop: 4594

Target 1: 4610
Target 2: 4615
Target 3: open"""),
]

for _name, _magic, _handler, _text in LADDER_CASES:
    reset(4600.1)
    _handler(SYMBOL, _text, f"ladder:{_name}")
    pump()
    _rows = bot_positions(_magic)
    check(f"{_name}: فُتحت الخمس", len(_rows), 5)
    _entry = _rows[0].price_open

    broker.move(round(_entry + 3.0, 2))  # التأمين عند +$3
    broker.sweep()
    pump()
    _runners = bot_positions(_magic)
    check(f"{_name}: بقيت اثنتان", len(_runners), 2)
    check(f"{_name}: وقفهما درجة تحت الدخول",
          {round(p.price_open - p.sl, 2) for p in _runners}, {1.0})

    broker.move(4609.2)  # اقترب بدولار من الهدف الأول 4610
    broker.sweep()
    pump()
    check(f"{_name}: عند اقتراب الهدف الأول → الوقف عند الدخول",
          {round(p.sl - p.price_open, 2) for p in bot_positions(_magic)}, {0.0})

    broker.move(4613.0)  # تجاوز الهدف الأول بـ$3
    broker.sweep()
    pump()
    check(f"{_name}: تجاوزه بـ$3 → الوقف يقفل على 4610",
          {p.sl for p in bot_positions(_magic)}, {4610.0})

    broker.move(4614.2)  # اقترب من آخر هدف رقمي 4615
    broker.sweep()
    pump()
    check(f"{_name}: عند آخر هدف → الهدف يصبح مفتوحاً",
          {p.tp for p in bot_positions(_magic)}, {0.0})

    broker.move(4618.0)  # تجاوز آخر هدف بـ$3
    broker.sweep()
    pump()
    _far = bot_positions(_magic)
    check(f"{_name}: والوقف يقفل على آخر هدف", {p.sl for p in _far}, {4615.0})
    check(f"{_name}: وتبقى مفتوحة تكمل صعودها", len(_far), 2)

print("\n" + "═" * 60)
print("  [١٢] بعد آخر هدف — الوقف يتتبع القمة")
print("═" * 60)
reset(4599.9)
B.handle_kings_message(SYMBOL, LAST_TP_SIGNAL, "flow:trail")  # آخر هدف 4620
pump()
for _p in (4603.1, 4609.2, 4613.0, 4618.0, 4619.2, 4623.0):
    broker.move(_p)
    broker.sweep()
    pump()
check("الوقف مقفول على آخر هدف قبل التتبع",
      {p.sl for p in bot_positions(B.MAGIC_KINGS)}, {4620.0})

broker.move(4624.0)  # +$4 فوق آخر هدف — أقل من مسافة التتبع
broker.sweep()
pump()
check("لم تبتعد بما يكفي → الوقف كما هو",
      {p.sl for p in bot_positions(B.MAGIC_KINGS)}, {4620.0})

broker.move(4630.0)  # القمة 4630 → الوقف 4625
broker.sweep()
pump()
check("القمة 4630 → الوقف يتتبع إلى 4625",
      {p.sl for p in bot_positions(B.MAGIC_KINGS)}, {4625.0})

broker.move(4645.0)  # القمة 4645 → الوقف 4640
broker.sweep()
pump()
check("القمة 4645 → الوقف 4640",
      {p.sl for p in bot_positions(B.MAGIC_KINGS)}, {4640.0})

broker.move(4642.0)  # تراجع — الوقف لا ينزل معه
broker.sweep()
pump()
check("التراجع لا يُنزل الوقف",
      {p.sl for p in bot_positions(B.MAGIC_KINGS)}, {4640.0})

broker.move(4639.5)  # ضرب الوقف المتتبع
broker.sweep()
pump()
check("ضرب الوقف المتتبع فخرجت", len(bot_positions(B.MAGIC_KINGS)), 0)
_last = [profit for _, profit in broker.closed[-2:]]
check("وخرجت برِبح قريب من $40", all(profit > 38 for profit in _last), True)
check("والتقرير يذكر الوقف المتتبع",
      any("الوقف المتتبع" in a for a in alerts), True)
print(f"     الخروج 4640 من قمة 4645 | ربح {_last}")

# البيع بنفس المنطق معكوساً
SELL_TRAIL = """XAUUSD SELL NOW 4600
Sl 4606

Tp 4590
Tp 4585
Tp open"""
reset(4600.1)
B.handle_kings_message(SYMBOL, SELL_TRAIL, "flow:trailsell")
pump()
for _p in (4596.9, 4590.8, 4589.0, 4585.5, 4583.0, 4578.0):
    broker.move(_p)
    broker.sweep()
    pump()
_sell = bot_positions(B.MAGIC_KINGS)
check("بيع: الهدف مفتوح بعد آخر هدف", {p.tp for p in _sell}, {0.0})
# القاع الذي بلغته الصفقة هو سعر الشراء عند 4578
check("بيع: الوقف يبقى $5 فوق القاع",
      {round(p.sl - broker.ask, 2) for p in _sell}, {5.0})
print(f"     القاع {broker.ask} | الوقف {_sell[0].sl}")

print(f"\n{'─' * 60}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
