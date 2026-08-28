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


LADDER_SIGNAL = """Gold buy Now 4609-4609
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

CONFLICT_SELL = """XAUUSD SELL NOW 4612
Sl 4618

Tp 4604
Tp 4598
Tp open"""


print("\n" + "═" * 60)
print("  [١] توصية الحيتان — الحالة النهائية عند الوسيط")
print("═" * 60)
reset(4610.0)
B.handle_whales_message(SYMBOL, LADDER_SIGNAL, "flow:whales2")
pump()
kings = bot_positions(B.MAGIC_WHALES)
check("فُتحت خمس صفقات", len(kings), 5)
check("كلها 0.01 لوت", {p.volume for p in kings}, {0.01})
check("كلها شراء", {p.type for p in kings}, {TYPE_BUY})
check("كلها بوقف", all(p.sl > 0 for p in kings), True)
check("الوقف $6 من التنفيذ",
      {round(p.price_open - p.sl, 2) for p in kings}, {6.0})
check("كلها بهدف — لا صفقة بلا TP", all(p.tp > 0 for p in kings), True)
# التدرّج: صفقتان هدفهما TP1 عند الوسيط ليغلقهما هو بالضبط، وصفقتان
# TP2، والأخيرة تركب السلم فهدفها يسبق هدفها الفعّال بخطوة.
_by_tp = sorted(p.tp for p in kings)
check("صفقتان هدفهما TP1", _by_tp[:2], [4613.0, 4613.0])
check("والباقيات على TP2 فما بعده",
      all(tp >= 4618.0 for tp in _by_tp[2:]), True)
print(f"     الدخول {kings[0].price_open} | SL {kings[0].sl} | الأهداف {_by_tp}")

print("\n" + "═" * 60)
print("  [٢] السعر يتحرك — التدرّج في الخروج")
print("═" * 60)
broker.move(4613.0)  # بلغ الهدف الأول
broker.sweep()
pump()
after = bot_positions(B.MAGIC_WHALES)
check("عند الهدف الأول خرجت صفقتان وبقيت ثلاث", len(after), 3)
check("وخرجتا عند الهدف بالضبط",
      {broker.deals[t][0].price for t, _ in broker.closed}, {4613.0})
check("والثلاث الباقيات وقفهن عند الدخول",
      all(abs(p.sl - p.price_open) < 0.05 for p in after), True)

broker.move(4618.0)  # بلغ الهدف الثاني
broker.sweep()
pump()
last = bot_positions(B.MAGIC_WHALES)
check("عند الهدف الثاني خرجت صفقتان وبقيت واحدة", len(last), 1)
check("والباقية وقفها على الهدف الأول", {p.sl for p in last}, {4613.0})
print(f"     أُغلق {len(broker.closed)} بربح "
      f"{sum(p for _, p in broker.closed):.2f}$ | الباقية وقفها {last[0].sl}")

broker.move(4621.0)  # تجاوز الهدف الثاني بـ$3
broker.sweep()
pump()
check("ثم السلم: تجاوز الثاني بـ$3 → الوقف يقفل عليه",
      {p.sl for p in bot_positions(B.MAGIC_WHALES)}, {4618.0})

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
# البيع من القناة الأخرى بينما شراء الحيتان مفتوح
B.handle_kings_message(SYMBOL, CONFLICT_SELL, "flow:conflict")
pump()
check("لم تُفتح صفقة بيع", len(bot_positions(B.MAGIC_KINGS)), 0)
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
check("وضُبط هدفها $5", round(position.tp - position.price_open, 2), 5.0)
check("ولم تُمس أحجامها", position.volume, 0.10)
check("ووصل تنبيه", any("صفقة يدوية" in a for a in alerts), True)
print(f"     الدخول {position.price_open} | SL {position.sl} | TP {position.tp}")

broker.move(4613.5)  # +$3 ربح
pump()
check("عند +$3 الوقف ينتقل للدخول",
      abs(broker.positions[manual].sl - position.price_open) < 0.05, True)
check("والهدف يبقى $5 فتكمل الصفقة إليه",
      round(broker.positions[manual].tp - position.price_open, 2), 5.0)

# وقف حسّنه صاحب الحساب بنفسه لا يُتراجع عنه
broker.positions[manual].sl = 4612.0
pump()
check("لا يتراجع عن وقف أفضل وضعه صاحب الحساب",
      broker.positions[manual].sl, 4612.0)

print("\n" + "═" * 60)
print("  [٦] تقرير الإغلاق")
print("═" * 60)
reset(4610.0)
B.handle_whales_message(SYMBOL, LADDER_SIGNAL, "flow:close")
pump()
opened = bot_positions(B.MAGIC_WHALES)
check("فُتحت المجموعة", len(opened), 5)
alerts.clear()
broker.move(4604.0)  # ضرب الوقف
for position in list(opened):
    broker.order_send({"action": ACTION_DEAL, "position": position.ticket,
                       "type": TYPE_SELL, "volume": position.volume,
                       "symbol": SYMBOL})
pump()
# الخمس أُغلقت في اللحظة نفسها: رسالة واحدة تجمعها بدل خمس متطابقة
grouped = [a for a in alerts if "أُغلقت 5 صفقات" in a]
check("رسالة واحدة تجمع الخمس", len(grouped), 1)
check("وفيها سطر لكل صفقة", grouped[0].count("←"), 5)
check("والتشريح مكتوب مرة واحدة", grouped[0].count("تشريح الخسارة"), 1)
check("ولا رسالة منفردة لأي صفقة",
      any("أُغلقت صفقة" in a for a in alerts), False)
check("والتقرير الختامي", any("انتهت توصية" in a for a in alerts), True)
check("لا صفقات متبقية", len(bot_positions(B.MAGIC_WHALES)), 0)

print("\n" + "═" * 60)
print("  [٧] رفض الوسيط لتعديل الوقف لا يُغلق صفقة محمية")
print("═" * 60)
reset(4610.0)
broker.reject_sltp = True
B.handle_whales_message(SYMBOL, LADDER_SIGNAL, "flow:reject")
pump()
survived = bot_positions(B.MAGIC_WHALES)
check("الصفقات بقيت رغم رفض التعديل", len(survived), 5)
check("وكلها بوقف من الأمر نفسه", all(p.sl > 0 for p in survived), True)

print("\n" + "═" * 60)
print("  [٨] توصية صاعدة طويلة — والمجموعة ناقصة صفقة")
print("═" * 60)
# نسخة طبق الأصل من توصية الحيتان التي أُغلقت كلها عند هدفها الأول:
# صعد الذهب من 4602 إلى 4643 وخرجت التوصية بـ$18 بدل $75.
LONG_SIGNAL = """Gold buy Now 4601-4601
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
B.handle_whales_message(SYMBOL, LONG_SIGNAL, "flow:long")
pump(2)
check("فُتحت الخمس", len(bot_positions(B.MAGIC_WHALES)), 5)

# صفقة تغادر المجموعة (أُغلقت من المنصة) — كان هذا يجمّد الإدارة كلها
_victim = sorted(broker.positions)[0]
broker.positions.pop(_victim)
broker.deals[_victim] = [types.SimpleNamespace(
    price=broker.bid, reason=3, profit=0.0, swap=0.0, commission=0.0,
    order=_victim, position_id=_victim)]
broker.closed.append((_victim, 0.0))
check("بقيت أربع", len(bot_positions(B.MAGIC_WHALES)), 4)

_path = [4602.4 + i * 0.1 for i in range(410)] + [4643.3 - i * 0.2 for i in range(60)]
for _price in _path:
    broker.move(_price)
    broker.sweep()
    pump(1)
    if not bot_positions(B.MAGIC_WHALES):
        break

_exits = sorted(profit for ticket, profit in broker.closed if ticket != _victim)
check("أُغلقت الأربع", len(_exits), 4)
check("واحدة عند الهدف الأول +$4.4", _exits[:1], [4.4])
check("واثنتان عند الهدف الثاني +$9.4", _exits[1:3], [9.4, 9.4])
check("والأخيرة ركبت الصعود", _exits[3] > 30, True)
check("مجموع التوصية أكبر من $50", sum(_exits) > 50, True)
_reported = sum(
    a.count("←") for a in alerts
    if "أُغلقت صفقة" in a or "أُغلقت" in a and "صفقات" in a
)
check("وكل صفقة ذُكرت في تقرير", _reported >= 5, True)
print(f"     النتائج: {_exits} → {sum(_exits):+.2f}$")

print("\n" + "═" * 60)
print("  [٩] التدرّج الكامل — من الفتح حتى آخر صفقة")
print("═" * 60)
# مثال صاحب الحساب: توصية 4600 بخمسة أهداف.
#   الهدف الأول → تخرج صفقتان وتبقى ثلاث بوقف عند الدخول
#   الهدف الثاني → تخرج صفقتان وتبقى واحدة بوقف على الهدف الأول
#   ثم يبدأ سلم الأهداف على تلك الصفقة
SCALE_SIGNAL = """Gold buy Now 4600-4600
Sl 4594

Tp 4610
Tp 4615
Tp 4620
Tp 4625
Tp open"""

reset(4599.9)
B.handle_whales_message(SYMBOL, SCALE_SIGNAL, "flow:scale")
pump()
_rows = bot_positions(B.MAGIC_WHALES)
_entry = _rows[0].price_open
check("فُتحت الخمس", len(_rows), 5)
check("كلها بوقف $6", {round(_entry - p.sl, 2) for p in _rows}, {6.0})
check("صفقتان هدفهما الهدف الأول",
      sorted(p.tp for p in _rows)[:2], [4610.0, 4610.0])

broker.move(4605.0)  # دون الهدف الأول
broker.sweep()
pump()
check("دون الهدف الأول لا يخرج شيء", len(bot_positions(B.MAGIC_WHALES)), 5)
check("والوقف ما زال $6 تحت الدخول",
      {round(_entry - p.sl, 2) for p in bot_positions(B.MAGIC_WHALES)}, {6.0})

broker.move(4610.0)  # الهدف الأول
broker.sweep()
pump()
_after_tp1 = bot_positions(B.MAGIC_WHALES)
check("الهدف الأول → خرجت صفقتان وبقيت ثلاث", len(_after_tp1), 3)
check("وخرجتا عند الهدف بالضبط",
      {broker.deals[t][0].price for t, _ in broker.closed}, {4610.0})
check("والثلاث وقفهن عند الدخول",
      {round(p.sl - _entry, 2) for p in _after_tp1}, {0.0})
print(f"     الدخول {_entry} | الباقيات {len(_after_tp1)} بوقف {_after_tp1[0].sl}")

broker.move(4615.0)  # الهدف الثاني
broker.sweep()
pump()
_runner = bot_positions(B.MAGIC_WHALES)
check("الهدف الثاني → خرجت صفقتان وبقيت واحدة", len(_runner), 1)
check("والباقية وقفها على الهدف الأول", {p.sl for p in _runner}, {4610.0})
check("وأربع خرجن بربح",
      all(profit > 0 for _, profit in broker.closed) and len(broker.closed) == 4,
      True)

broker.move(4619.2)  # اقترب من الهدف الثالث
broker.sweep()
pump()
check("ثم السلم: تجاوز الثاني بـ$3 → الوقف يقفل عليه",
      {p.sl for p in bot_positions(B.MAGIC_WHALES)}, {4615.0})

broker.move(4624.5)  # اقترب من آخر هدف رقمي
broker.sweep()
pump()
check("عند آخر هدف → الهدف يصبح مفتوحاً",
      {p.tp for p in bot_positions(B.MAGIC_WHALES)}, {0.0})

broker.move(4632.0)  # صعود حر
broker.sweep()
pump()
check("والوقف يتتبع القمة بمسافة $5",
      {p.sl for p in bot_positions(B.MAGIC_WHALES)}, {4627.0})
print(f"     الصافي حتى الآن: "
      f"{sum(profit for _, profit in broker.closed):+.2f}$")

print("\n" + "═" * 60)
print("  [١٠] الحيتان — نفس التدرّج تماماً")
print("═" * 60)
WHALES_SCALE = """بسم الله
Gold buy Now 4600-4600
* Tp1 4610
* Tp2 4615
* Tp3 4620
* Tp4 open
SL 4594"""
reset(4599.9)
B.handle_whales_message(SYMBOL, WHALES_SCALE, "flow:wscale")
pump()
_w = bot_positions(B.MAGIC_WHALES)
_wentry = _w[0].price_open
check("whales: فُتحت الخمس", len(_w), 5)

broker.move(4610.0)
broker.sweep()
pump()
check("whales: الهدف الأول → بقيت ثلاث",
      len(bot_positions(B.MAGIC_WHALES)), 3)
check("whales: وقفهن عند الدخول",
      {round(p.sl - _wentry, 2) for p in bot_positions(B.MAGIC_WHALES)}, {0.0})

broker.move(4615.0)
broker.sweep()
pump()
_wr = bot_positions(B.MAGIC_WHALES)
check("whales: الهدف الثاني → بقيت واحدة", len(_wr), 1)
check("whales: وقفها على الهدف الأول", {p.sl for p in _wr}, {4610.0})

broker.move(4619.2)
broker.sweep()
pump()
check("whales: ثم السلم يعمل",
      {p.sl for p in bot_positions(B.MAGIC_WHALES)}, {4615.0})

print("\n" + "═" * 60)
print("  [١١] البيع — التدرّج معكوساً")
print("═" * 60)
SELL_SCALE = """Gold sell Now 4600-4600
Sl 4606

Tp 4590
Tp 4585
Tp 4580
Tp open"""
reset(4600.1)
B.handle_whales_message(SYMBOL, SELL_SCALE, "flow:sellscale")
pump()
_s = bot_positions(B.MAGIC_WHALES)
_sentry = _s[0].price_open
check("بيع: فُتحت الخمس", len(_s), 5)
check("بيع: الوقف $6 فوق الدخول",
      {round(p.sl - _sentry, 2) for p in _s}, {6.0})

broker.move(4589.8)  # الهدف الأول للبيع (ask = 4590.0)
broker.sweep()
pump()
check("بيع: الهدف الأول → بقيت ثلاث", len(bot_positions(B.MAGIC_WHALES)), 3)
check("بيع: وقفهن عند الدخول",
      {round(p.sl - _sentry, 2) for p in bot_positions(B.MAGIC_WHALES)}, {0.0})

broker.move(4584.8)  # الهدف الثاني
broker.sweep()
pump()
_sr = bot_positions(B.MAGIC_WHALES)
check("بيع: الهدف الثاني → بقيت واحدة", len(_sr), 1)
check("بيع: وقفها على الهدف الأول", {p.sl for p in _sr}, {4590.0})

print("\n" + "═" * 60)
print("  [١٢] تقرير واحد لعدة صفقات تُغلق معاً")
print("═" * 60)
reset(4599.9)
alerts.clear()
B.handle_whales_message(SYMBOL, SCALE_SIGNAL, "flow:report")
pump()
broker.move(4594.0)  # ضرب الوقف على الخمس دفعة واحدة
broker.sweep()
pump()
_msgs = [a for a in alerts if "أُغلقت" in a and "صفقات" in a]
check("رسالة واحدة لا خمس", len(_msgs), 1)
check("وفيها سطر لكل صفقة", _msgs[0].count("←"), 5)
check("والتشريح مرة واحدة", _msgs[0].count("تشريح الخسارة"), 1)
check("والصافي مذكور", "الصافي" in _msgs[0], True)
check("ثم التقرير الختامي", any("انتهت توصية" in a for a in alerts), True)
_all_close_msgs = [a for a in alerts if "أُغلقت" in a]
check("مجموع رسائل الإغلاق رسالتان فقط", len(_all_close_msgs), 1)
print(f"     رسائل الإغلاق: {len(_all_close_msgs)} بدل 5")

print("\n" + "═" * 60)
print("  [١٣] حراسة المسارات الجانبية قبل المال الحقيقي")
print("═" * 60)
# رسالة أرقام لا تُقرأ كمنطقة (سعر واحد) كانت تسقط لمسار احتياطي
# يفتح خمس صفقات بلا حارس تعارض ولا سقف
reset(4599.9)
B.handle_kings_message(SYMBOL, """XAUUSD BUY NOW 4600
Sl 4594
Tp 4610
Tp open""", "guard:buy")
pump()
check("شراء KINGS مفتوح", len(bot_positions(B.MAGIC_KINGS)), 1)
alerts.clear()
B.handle_whales_message(SYMBOL, """بسم الله
Gold Sell Now 4600-4600
* Tp1 4590
* Tp2 open
SL 4606""", "guard:sell")
pump()
check("بيع الحيتان بلا منطقة صالحة يُرفض",
      len(bot_positions(B.MAGIC_WHALES)), 0)
check("ووصل تنبيه التعارض",
      any("تعارض اتجاه" in a for a in alerts), True)

# مستويات المنطقة تُفتح لاحقاً — التعارض يُعاد فحصه عندها لا عند التسجيل
reset(4620.0)   # فوق منطقة البيع: لا مستوى مستحق بعد
B.handle_whales_message(SYMBOL, """بسم الله
Gold Sell Now 4610-4614
* Tp1 4600
* Tp2 open
SL 4620""", "guard:zone")
pump()
check("لم يلمس السعر أي مستوى بعد",
      len(bot_positions(B.MAGIC_WHALES)), 0)
B.handle_kings_message(SYMBOL, """XAUUSD BUY NOW 4620
Sl 4614
Tp 4630
Tp open""", "guard:kbuy")
pump()
check("KINGS فتحت شراء بينما الحيتان تنتظر",
      len(bot_positions(B.MAGIC_KINGS)), 1)
broker.move(4614.0)  # صار كل مستوى بيع مستحقاً
pump()
check("مستويات البيع لا تُفتح ضد الشراء المفتوح",
      len(bot_positions(B.MAGIC_WHALES)), 0)

# توصية بلا أهداف: KINGS تدخل على الاتجاه ولا تنهار
reset(4599.9)
B.handle_kings_message(SYMBOL, "خد شراء الان", "guard:dironly")
pump()
_d = bot_positions(B.MAGIC_KINGS)
check("دخول على الاتجاه وحده — صفقة واحدة 0.07", len(_d), 1)
check("باللوت الكبير", {p.volume for p in _d}, {0.07})
check("بوقف $6 رغم غياب الأهداف",
      {round(p.price_open - p.sl, 2) for p in _d}, {6.0})
broker.move(4605.0)
broker.sweep()
pump()
check("ولا تنهار الإدارة بلا أهداف", len(bot_positions(B.MAGIC_KINGS)), 1)

print("\n" + "═" * 60)
print("  [١٤] ثلاث علل ظهرت على الحساب الحقيقي")
print("═" * 60)
LIVE_SIGNAL = """XAUUSD BUY NOW 4600
Sl 4594

Tp 4606
Tp 4611
Tp 4616
Tp open"""

# (١) الأمر نُفّذ بانزلاق فجاء الوقف $5 من التنفيذ الفعلي لا $6.
#     البوت لم يكتب وقفاً بعد، فعليه أن يصحّحه إلى $6 بالضبط —
#     "الأفضل بين الوقفين" كان يُبقي الأضيق لأنه الأقرب للسعر.
reset(4599.9)
B.handle_kings_message(SYMBOL, LIVE_SIGNAL, "live:sl")
for _p in broker.positions.values():
    _p.sl = round(_p.price_open - 5.0, 2)      # كما جاء من الوسيط
pump()
# KINGS مع الأرقام: الوقف درجة خلف ستوب التوصية 4594 → 4593
check("وقف جاء بالانزلاق يُصحَّح إلى ستوب التوصية",
      {p.sl for p in bot_positions(B.MAGIC_KINGS)}, {4593.0})

# (٢) وقف حرّكه صاحب الحساب بيده يبقى مكانه — لكن المحطات
#     المتفق عليها تسري فوقه، ولا تتراجع عن وقف أفضل وضعه هو
alerts.clear()
_hand = sorted(broker.positions)[-1]           # الصفقة التي تركب السلم
broker.positions[_hand].sl = 4590.0            # تحريك يدوي في المنصة
pump()
check("الوقف اليدوي بقي مكانه", broker.positions[_hand].sl, 4590.0)
check("ووصل تنبيه بأن البوت تركه",
      any("وقف يدوي" in a for a in alerts), True)
for _ in range(6):
    pump()
check("ولا يعيده بعد دورات كثيرة", broker.positions[_hand].sl, 4590.0)
check("ولا صفقة أخرى تأثرت",
      [p.sl for t, p in broker.positions.items() if t != _hand], [])
check("والهدف ما زال يُدار على الصفقة اليدوية",
      broker.positions[_hand].tp > 0, True)

# المحطات (الوقف للدخول ثم القفل على الهدف) على مجموعة الحيتان
WHALES_LIVE = """بسم الله
Gold buy Now 4600-4600
* Tp1 4606
* Tp2 4611
* Tp3 open
SL 4594"""
reset(4599.9)
B.handle_whales_message(SYMBOL, WHALES_LIVE, "live:milestones")
pump()
_hand = sorted(broker.positions)[-1]
_entry_hand = broker.positions[_hand].price_open
broker.positions[_hand].sl = 4590.0            # تحريك يدوي
pump()
check("الوقف اليدوي على مجموعة الحيتان يبقى",
      broker.positions[_hand].sl, 4590.0)
broker.move(4606.0)     # الهدف الأول: الوقف ينتقل للدخول كما اتفقنا
broker.sweep()
pump()
check("عند الهدف الأول ينتقل الوقف للدخول رغم التحريك اليدوي",
      broker.positions[_hand].sl, round(_entry_hand, 2))

broker.move(4609.0)     # تجاوز الهدف الأول بـ$3 → الوقف يقفل عليه
broker.sweep()
pump()
check("وبعد تجاوزه بـ$3 يقفل الوقف على الهدف الأول",
      broker.positions[_hand].sl, 4606.0)

# ولا يتراجع عن وقف أفضل وضعه صاحب الحساب بنفسه
reset(4599.9)
B.handle_whales_message(SYMBOL, WHALES_LIVE, "live:better")
pump()
_hand2 = sorted(broker.positions)[-1]
broker.positions[_hand2].sl = 4602.0           # أفضل من الدخول 4600.1
broker.move(4606.5)                            # يبلغ الهدف الأول
broker.sweep()
pump()
check("لا يتراجع عن وقف أفضل وضعته أنت",
      broker.positions[_hand2].sl, 4602.0)

# (٣) رسالة "تحديث سلم الأهداف" لا تتكرر كل دورة
reset(4599.9)
alerts.clear()
B.handle_whales_message(SYMBOL, WHALES_LIVE, "live:spam")
for _ in range(40):
    pump()
_ladder = [a for a in alerts if "تحديث سلم الأهداف" in a]
check("رسالة سلم واحدة لا أربعون", len(_ladder), 1)

broker.move(4605.2)   # اقترب من الهدف الأول → تغيّر حقيقي
for _ in range(20):
    pump()
_ladder2 = [a for a in alerts if "تحديث سلم الأهداف" in a]
check("وتحديث جديد يصل عند تغيّر حقيقي فقط", len(_ladder2), 2)
print(f"     رسائل السلم بعد 60 دورة: {len(_ladder2)}")

print("\n" + "═" * 60)
print("  [١٥] الصفقة اليدوية — وقفك أنت لا يُعاد")
print("═" * 60)
# حالة حقيقية: بيع يدوي عند 4589.88، البوت وضع وقفاً 4595.88،
# وصاحب الحساب وسّعه إلى 4597 فأعاده البوت خلال أقل من ثانية.
reset(4590.0)
alerts.clear()
_mt = broker.next_ticket + 1
broker.next_ticket = _mt
broker.positions[_mt] = types.SimpleNamespace(
    ticket=_mt, identifier=_mt, magic=0, type=TYPE_SELL, volume=0.01,
    price_open=4589.88, sl=0.0, tp=0.0, comment="manual-sell")
pump()
check("البوت ضبط وقف $6 فوق الدخول", broker.positions[_mt].sl, 4595.88)
check("وهدفاً $5 تحته", broker.positions[_mt].tp, 4584.88)
check("ووصل تنبيه", any("صفقة يدوية — ضُبطت" in a for a in alerts), True)

alerts.clear()
broker.positions[_mt].sl = 4597.0          # توسيع يدوي في المنصة
for _ in range(8):
    pump()
check("الوقف اليدوي الأوسع بقي 4597", broker.positions[_mt].sl, 4597.0)
check("ووصل تنبيه بأن البوت تركه",
      any("وقف يدوي" in a for a in alerts), True)

# وأضيق أيضاً — أي تحريك منك يُحترم
alerts.clear()
broker.positions[_mt].sl = 4592.0
for _ in range(5):
    pump()
check("والوقف اليدوي الأضيق كذلك", broker.positions[_mt].sl, 4592.0)

# لكن التأمين عند +$3 يسري للأمام: بيع من 4589.88 عند 4586.88
broker.move(4586.5)
pump()
check("وعند +$3 ينتقل الوقف للدخول (محطة متفق عليها)",
      broker.positions[_mt].sl, 4589.88)

# ولا يتراجع عن وقف أفضل وضعته أنت
_mt2 = broker.next_ticket + 1
broker.next_ticket = _mt2
broker.positions[_mt2] = types.SimpleNamespace(
    ticket=_mt2, identifier=_mt2, magic=0, type=TYPE_SELL, volume=0.01,
    price_open=4589.88, sl=0.0, tp=0.0, comment="manual-2")
pump()
broker.positions[_mt2].sl = 4588.0         # أفضل من الدخول
broker.move(4586.5)
for _ in range(4):
    pump()
check("لا يتراجع عن وقف أفضل منك", broker.positions[_mt2].sl, 4588.0)

# الهدف $5 دائماً — حتى لو فتحتَ الصفقة بهدف من عندك
_mt3 = broker.next_ticket + 1
broker.next_ticket = _mt3
broker.positions[_mt3] = types.SimpleNamespace(
    ticket=_mt3, identifier=_mt3, magic=0, type=TYPE_BUY, volume=0.01,
    price_open=4590.00, sl=0.0, tp=4620.0, comment="manual-tp")
pump()
check("الهدف يصير $5 دائماً", broker.positions[_mt3].tp, 4595.0)
check("والوقف $6", broker.positions[_mt3].sl, 4584.0)

# لكن إن حرّكتَ الهدف بيدك بعدها تركه
broker.positions[_mt3].tp = 4599.0
for _ in range(5):
    pump()
check("وهدفك اليدوي بعد الضبط يبقى", broker.positions[_mt3].tp, 4599.0)
print(f"     الوقف والهدف اليدويان محفوظان · التأمين يعمل")

print("\n" + "═" * 60)
print("  [١٦] توصية KINGS الحقيقية 4601-4602 والسعر تجاوزها")
print("═" * 60)
# الرسالة كما وصلت من القناة، والسعر عند 4603.5 أي فوق المدى المكتوب
REAL_KINGS = """XAUUSD BUY NOW 4601-4602
Sl 4597

Tp 4607
Tp 4612
Tp 4617
Tp 4622
Tp 4627
Tp 4632
Tp open"""
check("'خد شراء الان على الهادي' يفتح فوراً",
      B.kings_command_entry("خد شراء الان على الهادي", None), ("BUY", 1))
check("'خد شراء الان مرتين' → وحدتان",
      B.kings_command_entry("خد شراء الان مرتين", None), ("BUY", 2))
check("'علق دي عندك' لا يفتح",
      B.kings_command_entry("علق دي عندك", "BUY"), (None, 0))

reset(4603.3)
B.handle_kings_message(SYMBOL, REAL_KINGS, "real:kings")
pump()
_r = sorted(bot_positions(B.MAGIC_KINGS), key=lambda p: p.ticket)
check("صفقة واحدة 0.07", (len(_r), _r[0].volume), (1, 0.07))
check("الوقف درجة خلف ستوب التوصية 4597", {p.sl for p in _r}, {4596.0})
# الأهم: الهدف من القناة نفسها لا رقم من عند البوت
check("الهدف 4607 — هدف القناة الأول", [p.tp for p in _r], [4607.0])
print(f"     الدخول {_r[0].price_open} | الأهداف {[p.tp for p in _r]}")

broker.move(4607.0)
broker.sweep()
pump()
check("عند 4607 خرجت الصفقة كلها", len(bot_positions(B.MAGIC_KINGS)), 0)

print("\n" + "═" * 60)
print("  [١٧] فات السعر مدى الدخول → ستوب التوصية لا حساب البوت")
print("═" * 60)
LATE_SIG = """XAUUSD BUY NOW 4601-4602
Sl 4597

Tp 4607
Tp 4612
Tp 4617
Tp open"""

# (أ) السعر داخل المدى — السلوك المعتاد: $6 من التنفيذ
reset(4601.3)                      # ask 4601.5 داخل 4601-4602
B.handle_kings_message(SYMBOL, LATE_SIG, "late:inside")
pump()
_in = bot_positions(B.MAGIC_KINGS)
# KINGS يلتزم بستوب التوصية حتى داخل المدى: 4597 وخلفه درجة
check("داخل المدى → الوقف درجة خلف ستوب التوصية",
      {p.sl for p in _in}, {4596.0})

# (ب) السعر فات المدى — الوقف ستوب التوصية بالضبط
reset(4603.3)                      # ask 4603.5 فوق 4602
alerts.clear()
B.handle_kings_message(SYMBOL, LATE_SIG, "late:passed")
pump()
_late = bot_positions(B.MAGIC_KINGS)
check("فات المدى → يفتح ولا يرفض", len(_late), 1)
check("والوقف درجة خلف ستوب التوصية", {p.sl for p in _late}, {4596.0})
check("والهدف هدف التوصية الأول", sorted({p.tp for p in _late}), [4607.0])
check("والرسالة تذكر أنه فات المدى",
      any("فات المدى" in a for a in alerts), True)
print(f"     الدخول {_late[0].price_open} | الوقف {_late[0].sl} "
      f"(مسافة {round(_late[0].price_open - _late[0].sl, 2)}$)")

# الإدارة لا تعيده إلى $6 في الدورات التالية
for _ in range(6):
    pump()
check("ولا تعيده الإدارة إلى $6",
      {p.sl for p in bot_positions(B.MAGIC_KINGS)}, {4596.0})

# وعند الهدف الأول ينتقل الوقف للدخول كالمعتاد
broker.move(4607.0)
broker.sweep()
pump()
check("وعند الهدف الأول تخرج الصفقة", len(bot_positions(B.MAGIC_KINGS)), 0)

# (ج) ستوب توصية بعيد جداً يُرفض ونعود لحساب البوت
FAR_SL = """XAUUSD BUY NOW 4601-4602
Sl 4560

Tp 4607
Tp 4612
Tp open"""
reset(4603.3)
B.handle_kings_message(SYMBOL, FAR_SL, "late:farsl")
pump()
check("ستوب توصية أبعد من $15 → نعود إلى $6",
      {round(p.price_open - p.sl, 2) for p in bot_positions(B.MAGIC_KINGS)},
      {6.0})
print("     KINGS: صفقة واحدة 0.07 · ستوب التوصية وخلفه درجة · "
      "الخروج كله عند الهدف الأول")

print("\n" + "═" * 60)
print("  [١٨] شبكة الأمان: أرقام لم تصل → هدف احتياطي $5")
print("═" * 60)
# حالة حقيقية: القناة قالت "ناخد بيع" فدخل البوت بوقف $6 بلا هدف،
# ثم لم ترسل الأرقام. الصفقة كانت تبقى بلا مخرج.
reset(4450.9)
alerts.clear()
B.handle_kings_message(SYMBOL, "ناخد بيع", "net:1")
pump()
_n = bot_positions(B.MAGIC_KINGS)
_nentry = _n[0].price_open
check("دخل بصفقة واحدة 0.07", (len(_n), _n[0].volume), (1, 0.07))
check("بوقف $6 فوق الدخول", round(_n[0].sl - _nentry, 2), 6.0)
check("وبلا هدف في البداية", _n[0].tp, 0.0)

for _ in range(4):
    pump()
check("ولا يضع هدفاً قبل انتهاء المهلة",
      bot_positions(B.MAGIC_KINGS)[0].tp, 0.0)

# نُقدّم الساعة: مرّت المهلة ولم تصل الأرقام
for _t, _info in B._open_trades.items():
    if _info.get("channel") == "kings":
        _info["created_at"] = time.time() - B.CHANNEL_TARGETLESS_GRACE_SECONDS - 1
pump()
_after_net = bot_positions(B.MAGIC_KINGS)[0]
check("بعد المهلة يوضع هدف $5",
      round(_nentry - _after_net.tp, 2), 5.0)
check("والوقف كما هو $6", round(_after_net.sl - _nentry, 2), 6.0)
check("ووصل تنبيه بالهدف الاحتياطي",
      any("هدف احتياطي" in a for a in alerts), True)
print(f"     الدخول {_nentry} | الوقف {_after_net.sl} | "
      f"الهدف الاحتياطي {_after_net.tp}")

# وإن وصلت الأرقام بعدها حلّت محله أهداف التوصية
B.handle_kings_message(SYMBOL, """XAUUSD SELL NOW 4451
Sl 4456
Tp 4446
Tp 4441
Tp open""", "net:2")
pump()
_bound = bot_positions(B.MAGIC_KINGS)[0]
check("وصلت الأرقام → الهدف هدف التوصية", _bound.tp, 4446.0)
check("والوقف درجة خلف ستوب التوصية", _bound.sl, 4457.0)

print(f"\n{'─' * 60}\nنجح: {ok} | فشل: {fails}\n")
sys.exit(1 if fails else 0)
