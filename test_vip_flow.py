"""فحص تنفيذ أوامر القناة البشرية على وسيط وهمي:

    python3 test_vip_flow.py

تسلسل كامل كما ترسله قناة VIP AN — رسالةً رسالة — ويُتحقَّق بعد كل
واحدة من حالة الحساب: كم صفقة، وأين الوقف، وأين الهدف.

لا شيء هنا يلمس حساباً حقيقياً: الوسيط وهمي يعيش في الذاكرة.
"""
import os
import sys
import tempfile
import types


DONE, NO_CHANGES = 10009, 10025
TYPE_BUY, TYPE_SELL = 0, 1
A_DEAL, A_SLTP, A_PENDING, A_REMOVE, A_MODIFY = 1, 2, 5, 6, 7
m_BUY_LIMIT, m_SELL_LIMIT = 30, 31


class Broker:
    def __init__(self, price=4010.0, spread=0.20):
        self.bid = price
        self.spread = spread
        self.positions = {}
        self.orders = {}          # الأوامر المعلّقة
        self.next_ticket = 5000
        self.log = []

    @property
    def ask(self):
        return round(self.bid + self.spread, 2)

    def move(self, price):
        self.bid = round(price, 2)

    def tick(self, *a, **k):
        return types.SimpleNamespace(bid=self.bid, ask=self.ask,
                                     last=self.bid, time=0)

    def positions_get(self, symbol=None, **k):
        return tuple(self.positions.values())

    def orders_get(self, *a, **k):
        return tuple(self.orders.values())

    def fill(self, ticket):
        """تنفيذ أمر معلّق — كما لو بلغ السعرُ سعرَه."""
        order = self.orders.pop(ticket)
        self.next_ticket += 1
        pid = self.next_ticket
        is_buy = order.type == m_BUY_LIMIT
        self.positions[pid] = types.SimpleNamespace(
            ticket=pid, identifier=pid, symbol=order.symbol,
            volume=order.volume, type=TYPE_BUY if is_buy else TYPE_SELL,
            price_open=order.price_open, sl=order.sl, tp=order.tp,
            magic=order.magic, comment=order.comment, profit=0.0, time=0)
        self.log.append(("FILL", ticket, pid))
        return pid

    def history_deals_get(self, *a, **k):
        return ()

    def symbols_get(self, *a, **k):
        return ()

    def symbol_info(self, symbol):
        return types.SimpleNamespace(point=0.01, digits=2, trade_stops_level=0,
                                     volume_min=0.01, volume_step=0.01,
                                     visible=True, name=symbol)

    def symbol_select(self, *a, **k):
        return True

    def order_send(self, req):
        action = req.get("action")
        if action == A_DEAL and not req.get("position"):
            return self._open(req)
        if action == A_DEAL and req.get("position"):
            return self._close(req)
        if action == A_SLTP:
            return self._sltp(req)
        if action == A_PENDING:
            return self._pending(req)
        if action == A_REMOVE:
            self.orders.pop(req.get("order"), None)
            return types.SimpleNamespace(retcode=DONE, comment="removed")
        if action == A_MODIFY:
            o = self.orders.get(req.get("order"))
            if not o:
                return types.SimpleNamespace(retcode=10013, comment="none")
            o.sl = round(float(req.get("sl") or 0.0), 2)
            o.tp = round(float(req.get("tp") or 0.0), 2)
            self.log.append(("ORDER-SLTP", o.ticket, o.sl, o.tp))
            return types.SimpleNamespace(retcode=DONE, comment="done")
        return types.SimpleNamespace(retcode=DONE, order=0, deal=0,
                                     price=self.bid, comment="ok")

    def _open(self, req):
        self.next_ticket += 1
        ticket = self.next_ticket
        is_buy = req["type"] == TYPE_BUY
        price = self.ask if is_buy else self.bid
        self.positions[ticket] = types.SimpleNamespace(
            ticket=ticket, identifier=ticket, symbol=req["symbol"], volume=req["volume"],
            type=TYPE_BUY if is_buy else TYPE_SELL, price_open=price,
            sl=float(req.get("sl") or 0.0), tp=float(req.get("tp") or 0.0),
            magic=req.get("magic", 0), comment=req.get("comment", ""),
            profit=0.0, time=0)
        self.log.append(("OPEN", ticket, price, req.get("sl"), req.get("tp")))
        return types.SimpleNamespace(retcode=DONE, order=ticket, deal=ticket,
                                     price=price, volume=req["volume"],
                                     comment="done")

    def _pending(self, req):
        self.next_ticket += 1
        ticket = self.next_ticket
        self.orders[ticket] = types.SimpleNamespace(
            ticket=ticket, symbol=req["symbol"], volume=req["volume"],
            type=req["type"], price_open=round(float(req["price"]), 2),
            sl=round(float(req.get("sl") or 0.0), 2),
            tp=round(float(req.get("tp") or 0.0), 2),
            magic=req.get("magic", 0), comment=req.get("comment", ""),
            time_setup=0)
        self.log.append(("PENDING", ticket, req["price"],
                         req.get("sl"), req.get("tp")))
        return types.SimpleNamespace(retcode=DONE, order=ticket,
                                     price=req["price"], comment="done")

    def _close(self, req):
        ticket = req["position"]
        self.positions.pop(ticket, None)
        self.log.append(("CLOSE", ticket))
        return types.SimpleNamespace(retcode=DONE, order=ticket, deal=ticket,
                                     price=self.bid, comment="done")

    def _sltp(self, req):
        ticket = req["position"]
        p = self.positions.get(ticket)
        if not p:
            return types.SimpleNamespace(retcode=10013, comment="no position")
        new_sl = round(float(req.get("sl") or 0.0), 2)
        new_tp = round(float(req.get("tp") or 0.0), 2)
        if (new_sl, new_tp) == (round(p.sl, 2), round(p.tp, 2)):
            return types.SimpleNamespace(retcode=NO_CHANGES, comment="same")
        p.sl, p.tp = new_sl, new_tp
        self.log.append(("SLTP", ticket, new_sl, new_tp))
        return types.SimpleNamespace(retcode=DONE, comment="done")


def _install(sys_modules, broker):
    m = types.ModuleType("MetaTrader5")
    for i, n in enumerate([
        "TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15", "TIMEFRAME_M30",
        "TIMEFRAME_H1", "ORDER_TIME_GTC", "ORDER_TIME_SPECIFIED",
        "ORDER_FILLING_IOC", "ORDER_FILLING_FOK", "ORDER_FILLING_RETURN",
        "ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT",
        "ORDER_TYPE_BUY_STOP", "ORDER_TYPE_SELL_STOP",
        "ACCOUNT_TRADE_MODE_REAL", "ACCOUNT_TRADE_MODE_DEMO",
        "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", "DEAL_REASON_SL",
        "DEAL_REASON_TP",
    ]):
        setattr(m, n, i + 20)
    m.TRADE_ACTION_DEAL, m.TRADE_ACTION_SLTP = A_DEAL, A_SLTP
    m.TRADE_ACTION_PENDING, m.TRADE_ACTION_REMOVE = A_PENDING, A_REMOVE
    m.TRADE_ACTION_MODIFY = A_MODIFY
    m.ORDER_TYPE_BUY_LIMIT, m.ORDER_TYPE_SELL_LIMIT = m_BUY_LIMIT, m_SELL_LIMIT
    m.ORDER_TYPE_BUY, m.ORDER_TYPE_SELL = TYPE_BUY, TYPE_SELL
    m.POSITION_TYPE_BUY, m.POSITION_TYPE_SELL = TYPE_BUY, TYPE_SELL
    m.TRADE_RETCODE_DONE, m.TRADE_RETCODE_NO_CHANGES = DONE, NO_CHANGES
    m.last_error = lambda: (-1, "fake")
    m.copy_rates_from_pos = m.copy_rates_from = lambda *a, **k: None
    m.initialize = lambda *a, **k: True
    m.shutdown = lambda *a, **k: None
    m.account_info = lambda: types.SimpleNamespace(
        login=1550318365, trade_mode=m.ACCOUNT_TRADE_MODE_REAL,
        trade_allowed=True,
        margin_mode=m.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING, balance=1000.0)
    m.terminal_info = lambda: types.SimpleNamespace(connected=True,
                                                    trade_allowed=True)
    m.symbol_info_tick = broker.tick
    m.positions_get = broker.positions_get
    m.orders_get = broker.orders_get
    m.history_deals_get = broker.history_deals_get
    m.symbols_get = broker.symbols_get
    m.symbol_info = broker.symbol_info
    m.symbol_select = broker.symbol_select
    m.order_send = broker.order_send
    sys_modules["MetaTrader5"] = m
    rq = types.ModuleType("requests")
    rq.post = rq.get = lambda *a, **k: types.SimpleNamespace(
        status_code=200, text="", json=lambda: {})
    rq.exceptions = types.SimpleNamespace(RequestException=Exception)
    sys_modules["requests"] = rq
    return m


broker = Broker(price=4010.0)
mt5 = _install(sys.modules, broker)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(tempfile.mkdtemp())
import master_bot as B  # noqa: E402

SYM = "XAUUSD.m"
B._channel_runtime_mode.update({"enabled": True, "symbol": SYM,
                                "allow_demo": False,
                                "account_login": 1550318365})
alerts = []
B.notify_tg = lambda t: alerts.append(t)
B.send_tg = lambda t: alerts.append(t)

ok = bad = 0
def check(name, got, want):
    global ok, bad
    if got == want: ok += 1; print(f"  ✅ {name}  ({got})")
    else: bad += 1; print(f"  ❌ {name}\n       المتوقع {want}\n       الناتج  {got}")

def pos():
    return B.vip_positions(SYM)

def reset(price=4010.0):
    broker.positions.clear(); broker.log.clear(); broker.move(price)
    B._open_trades.clear(); B._pending_meta.clear(); B._group_results.clear()
    B._processed_signals.clear(); B._last_signal.clear()
    B._vip_state.update({"direction": None, "no_reopen": False,
                         "stop_was_hit": False})
    alerts.clear()

def say(text, key=None):
    B.handle_vip_message(SYM, text, key or f"k{len(broker.log)}:{text[:8]}")

print("═" * 58)
print("  تسلسل كامل من قناة VIP AN على وسيط وهمي")
print("═" * 58)

print("\n[١] «بيع» → ٤ صفقات بوقف مؤقت $5")
reset(4010.0)
say("اجهز");            check("«اجهز» لا تفتح", len(pos()), 0)
say("بيع")
rows = pos()
check("عدد الصفقات", len(rows), 4)
check("كلها بيع", all(p.type == mt5.POSITION_TYPE_SELL for p in rows), True)
check("اللوت 0.01", {p.volume for p in rows}, {0.01})
entry = rows[0].price_open
check("الوقف المؤقت $5 فوق الدخول",
      {round(p.sl - p.price_open, 2) for p in rows}, {5.0})
check("بلا هدف بعد", {p.tp for p in rows}, {0.0})

print("\n[٢] «ستوبك 4007» → على الأربع")
say("ستوبك على 4007")
check("الوقف 4007 على الكل", {p.sl for p in pos()}, {4007.0})

print("\n[٣] «هدفك 4000» → لصفقتين فقط")
say("هدفك 4000")
rows = pos()
check("صفقتان بهدف 4000", sum(1 for p in rows if p.tp == 4000.0), 2)
check("وصفقتان بلا هدف", sum(1 for p in rows if p.tp == 0.0), 2)

print("\n[٤] «هدف ثاني 3995» → للأُخريَين")
say("هدف ثاني 3995")
rows = pos()
check("صفقتان 4000", sum(1 for p in rows if p.tp == 4000.0), 2)
check("صفقتان 3995", sum(1 for p in rows if p.tp == 3995.0), 2)

print("\n[٥] «ستوبك دخولك» → وقف الكل إلى الدخول")
say("يلا ستوبك دخولك الان")
check("كل وقف عند دخوله",
      all(round(p.sl, 2) == round(p.price_open, 2) for p in pos()), True)

print("\n[٦] «احجز نص» → يغلق ٢ ووقف الباقي للدخول")
say("الاول تم احجز نص من ربحك")
rows = pos()
check("بقيت صفقتان", len(rows), 2)
check("وقفهما عند الدخول",
      all(round(p.sl, 2) == round(p.price_open, 2) for p in rows), True)

print("\n[٧] «خروووججج» → يغلق الكل")
say("خرووووججججج، شلال زيرو انعكاس")
check("لا صفقات", len(pos()), 0)

print("\n[٨] «بيع» وهناك صفقة مفتوحة → لا يفتح ثانية")
reset(4010.0); say("بيع"); first = len(pos())
say("شراء الان", key="dup1"); say("بيع", key="dup2")
check("بقي العدد كما هو", len(pos()), first)

print("\n[٩] تأمين تلقائي عند +$5 بلا رسالة")
reset(4010.0); say("بيع")
before = {p.ticket: p.sl for p in pos()}
broker.move(4004.0)          # البيع رابح $6
B.vip_auto_breakeven(SYM)
rows = pos()
check("الوقف انتقل للدخول",
      all(round(p.sl, 2) == round(p.price_open, 2) for p in rows), True)
check("ولم يكن كذلك قبلها",
      any(round(before[p.ticket], 2) != round(p.price_open, 2) for p in rows),
      True)

print("\n[١٠] «شراء بلوت بسيط» → صفقتان")
reset(4010.0); say("شراء بلوت بسيط")
check("صفقتان", len(pos()), 2)
check("كلها شراء", all(p.type == mt5.POSITION_TYPE_BUY for p in pos()), True)

print("\n[١١] «انتهت لا تفعل» → يغلق ولا يفتح")
reset(4010.0); say("بيع")
say("انتهت لا تفعل")
check("أُغلق الكل", len(pos()), 0)
# «لا تفعل» تمنع التجديد وإعادة الدخول المشروط وحدهما. أما توصية
# جديدة مستقلة بعد ساعات فتعمل — ولو منعت كل فتح لاحق لتعطّل
# البوت إلى الأبد حتى يُعاد تشغيله. (أقرّه صاحب الحساب.)
say("جدد", key="renew-after-noreopen")
check("«جدد» لا تعمل بعدها", len(pos()), 0)
say("بيع", key="after-noreopen")
check("توصية جديدة مستقلة تعمل", len(pos()), 4)

print("\n[١٢] كلام القناة لا يحرّك شيئاً")
reset(4010.0); say("بيع"); n = len(pos())
for noise in ["مبروكك حبايبي", "افتتاح مبارك", "طمنوني حبايي",
              "نموذج ابتلاعي قوي بمنطقتنا", "خرجتو من البيع على ربح؟",
              "رح نبيع من 4009-4008", "مناطق الشراء 24-25-26 كلها ضمن النطاق",
              "اغلق 3 استمر بدخول 5 بتقدر الان"]:
    say(noise, key="n" + noise[:6])
check("الصفقات كما هي", len(pos()), n)
check("ولا تعديل", all(p.sl == pos()[0].sl for p in pos()), True)

print("\n[١٣] حدّ الخسارة — يغلق كل شيء ويتوقف")
reset(4010.0)
B._guard_state.update({"max_loss": 150.0, "halted": False,
                       "start_equity": 1050.0, "day": B.vip_today()})
_equity = {"value": 1050.0}
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1050.0, equity=_equity["value"])

say("بيع")
check("فُتحت ٤ صفقات", len(pos()), 4)

# خسارة دون الحد: لا يتدخل
_equity["value"] = 1050.0 - 149.0
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1050.0, equity=_equity["value"])
check("خسارة $149 لا توقف", B.vip_loss_guard(SYM), False)
check("والصفقات باقية", len(pos()), 4)

# بلوغ الحد: يغلق ويتوقف
_equity["value"] = 1050.0 - 150.0
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1050.0, equity=_equity["value"])
check("خسارة $150 توقف", B.vip_loss_guard(SYM), True)
check("وأُغلقت كل الصفقات", len(pos()), 0)
check("والبوت موقوف", B._guard_state["halted"], True)

# بعد التوقف لا يفتح مهما وصل
say("بيع", key="after-halt")
check("«بيع» بعد التوقف لا تفتح", len(pos()), 0)
say("شراء الان", key="after-halt2")
check("ولا «شراء»", len(pos()), 0)

# الخسارة العائمة تُحسب، لا الرصيد وحده
B._guard_state.update({"halted": False, "start_equity": 1050.0,
                       "day": B.vip_today()})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1050.0, equity=880.0)      # الرصيد سليم والعائم خاسر
check("العائم وحده يكفي للإيقاف", B.vip_loss_guard(SYM), True)

# الحد صفر = معطّل
B._guard_state.update({"halted": False, "max_loss": 0.0})
check("الحد صفر يعطّل الحارس", B.vip_loss_guard(SYM), False)
B._guard_state.update({"max_loss": 150.0, "halted": False})


print("\n[١٤] الحدّ يومي — يصفّر مع كل يوم جديد")
reset(4010.0)
# يوم الأمس انتهى على خسارة $200 — أكثر من الحد
B._guard_state.update({"max_loss": 150.0, "halted": False,
                       "start_equity": 1050.0, "day": "2020-01-01"})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=850.0, equity=850.0)
check("خسارة الأمس لا توقف اليوم", B.vip_loss_guard(SYM), False)
check("واليوم صار اليوم الحالي", B._guard_state["day"], B.vip_today())
check("والأساس صار حقوق اليوم", B._guard_state["start_equity"], 850.0)

# ومن هذا الأساس الجديد يُقاس: $149 تحت الحد
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=850.0, equity=701.0)
check("خسارة $149 من الأساس الجديد لا توقف",
      B.vip_loss_guard(SYM), False)

# و$150 منه توقف — لا جمع مع خسارة الأمس
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=850.0, equity=700.0)
check("و$150 منه توقف", B.vip_loss_guard(SYM), True)
check("والبوت موقوف", B._guard_state["halted"], True)
B._guard_state.update({"halted": False, "day": B.vip_today()})

print("\n[١٥] حارس اللوت — وسيط آخر قد يرفض 0.01")
reset(4010.0)
_limits = {"min": 0.01, "step": 0.01, "max": 100.0}
mt5.symbol_info = lambda sym: types.SimpleNamespace(
    point=0.01, digits=2, trade_stops_level=0, visible=True, name=sym,
    volume_min=_limits["min"], volume_step=_limits["step"],
    volume_max=_limits["max"])

B._vip_state["lot"] = 0.01
check("0.01 مقبول عند وسيط حدّه 0.01", B.vip_lot_ok(SYM)[0], True)

B._vip_state["lot"] = 0.0
check("صفر مرفوض", B.vip_lot_ok(SYM)[0], False)

B._vip_state["lot"] = -0.1
check("سالب مرفوض", B.vip_lot_ok(SYM)[0], False)

# وسيط حدّه الأدنى 0.1 — الحالة التي يحمي منها الحارس فعلاً
_limits.update({"min": 0.1, "step": 0.1})
B._vip_state["lot"] = 0.01
rejected, why = B.vip_lot_ok(SYM)
check("0.01 مرفوض عند وسيط حدّه 0.1", rejected, False)
check("والسبب يذكر الحدّ الأدنى", "0.1" in why, True)
B._vip_state["lot"] = 0.1
check("و0.1 مقبول عنده", B.vip_lot_ok(SYM)[0], True)

# الخطوة: 0.15 ليست من مضاعفات 0.1
B._vip_state["lot"] = 0.15
check("0.15 مرفوض لأن الخطوة 0.1", B.vip_lot_ok(SYM)[0], False)

# والعشرية لا تخدع الفحص: 0.3 = ثلاث خطوات من 0.1
B._vip_state["lot"] = 0.3
check("0.3 مقبول رغم خدعة العشرية", B.vip_lot_ok(SYM)[0], True)

# السقف
B._vip_state["lot"] = 200.0
check("فوق السقف مرفوض", B.vip_lot_ok(SYM)[0], False)

# اللوت المضبوط هو الذي يُفتح به — لا الثابت
_limits.update({"min": 0.01, "step": 0.01})
B._vip_state.update({"lot": 0.05, "halted": False, "no_reopen": False,
                     "day": B.vip_today(), "start_equity": None})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1050.0, equity=1050.0)
say("بيع", key="lot-05")
check("فُتحت ٤ صفقات", len(pos()), 4)
check("كل واحدة بـ0.05 لا 0.01",
      sorted({round(p.volume, 4) for p in pos()}), [0.05])
B._vip_state["lot"] = 0.01

print("\n[١٦] وضع الهدف الواحد — كل الصفقات تُغلق عند الهدف الأول")
reset(4010.0)
B._vip_state.update({"lot": 0.20, "one_target": True, "halted": False,
                     "no_reopen": False, "day": B.vip_today(),
                     "start_equity": None, "max_loss": 150.0})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=5000.0, equity=5000.0)

say("شراء")
check("فُتحت ٤ صفقات", len(pos()), 4)
check("كل واحدة بـ0.20", sorted({round(p.volume, 4) for p in pos()}), [0.2])

say("هدف اول 4030")
check("الهدف على ٤ صفقات لا ٢", sum(1 for p in pos() if p.tp == 4030.0), 4)

say("الهدف الثاني 4060")
check("الهدف الثاني لا يغيّر شيئاً",
      sum(1 for p in pos() if p.tp == 4030.0), 4)
check("ولا صفقة واحدة أخذت 4060",
      sum(1 for p in pos() if p.tp == 4060.0), 0)

# التأمين كما هو
say("تامين")
check("التأمين ينقل وقف ٤ صفقات",
      sum(1 for p in pos() if p.sl == p.price_open), 4)

# «خروج» تغلق كل شيء
say("خروووج حبايبي")
check("«خروج» تغلق الكل", len(pos()), 0)

# الوضع الافتراضي لم يتغيّر: الهدف الأول للنصف
reset(4010.0)
B._vip_state.update({"lot": 0.01, "one_target": False, "halted": False,
                     "no_reopen": False, "day": B.vip_today()})
say("شراء", key="two-target")
say("هدف اول 4030", key="two-target-tp1")
check("بلا الوضع: الهدف الأول على ٢ فقط",
      sum(1 for p in pos() if p.tp == 4030.0), 2)
say("الهدف الثاني 4060", key="two-target-tp2")
check("والثاني على الـ٢ الباقية",
      sum(1 for p in pos() if p.tp == 4060.0), 2)

print("\n[١٧] المخاطرة بالدولار — «5 نقاط» ليست «$5» عند كل لوت")
reset(4010.0)
# وسيط يعطي بيانات التك: الذهب 1 لوت = 100 أونصة
mt5.symbol_info = lambda sym: types.SimpleNamespace(
    point=0.01, digits=2, trade_stops_level=0, visible=True, name=sym,
    volume_min=0.01, volume_step=0.01, volume_max=100.0,
    trade_tick_size=0.01, trade_tick_value=1.0)

B._vip_state["lot"] = 0.01
check("5 نقاط بلوت 0.01 = $5",
      round(B.vip_points_to_money(SYM, 5.0), 2), 5.0)
B._vip_state["lot"] = 0.10
check("ونفسها بلوت 0.10 = $50",
      round(B.vip_points_to_money(SYM, 5.0), 2), 50.0)
B._vip_state["lot"] = 0.20
check("وبلوت 0.20 = $100",
      round(B.vip_points_to_money(SYM, 5.0), 2), 100.0)

B._vip_state["lot"] = 0.10
text = B.vip_risk_text(SYM, 5.0, group=True)
check("النص يذكر مبلغ الصفقة", "$50" in text, True)
check("ومبلغ الأربع", "$200" in text, True)

# وسيط لا يعطي بيانات التك: المسافة وحدها، بلا رقم مخترع
mt5.symbol_info = lambda sym: types.SimpleNamespace(
    point=0.01, digits=2, trade_stops_level=0, visible=True, name=sym,
    volume_min=0.01, volume_step=0.01, volume_max=100.0)
check("بلا بيانات تك لا يُخترع مبلغ",
      B.vip_points_to_money(SYM, 5.0), None)
check("والنص يذكر المسافة وحدها",
      B.vip_risk_text(SYM, 5.0), "5 نقاط")
B._vip_state["lot"] = 0.01

print("\n[١٨] جلسة 30/10 كاملةً — كما وصلت من القناة")
reset(3965.0)
B._vip_state.update({"lot": 0.01, "one_target": False, "halted": False,
                     "no_reopen": False, "day": B.vip_today(),
                     "direction": None, "stop_was_hit": False,
                     "start_equity": None, "max_loss": 150.0})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1050.0, equity=1050.0)

say("شراء الان", key="s1")
check("12:47 «شراء الان» تفتح ٤", len(pos()), 4)

say("من 65", key="s2")
check("12:47 «من 65» لا تفتح شيئاً", len(pos()), 4)

say("طيران مين فعل معي ؟", key="s3")
check("12:48 السؤال لا يغلق", len(pos()), 4)

say("حط ستوبك دخولك ولو ضربك بتفعل من 64-65", key="s4")
check("12:54 التأمين ينقل ٤ أوقاف",
      sum(1 for p in pos() if p.sl == p.price_open), 4)

# القاعدة الجديدة: أمرٌ بسعرٍ صريح يضيف ولو بقيت صفقات.
# «حط ستوبك دخولك ولو ضربك بتفعل من 64-65» أضافت أربعاً قبلها.
check("12:54 الشرطية أضافت أربعاً", len(pos()), 8)
say("يلا خذ من 64", key="s5")
check("12:55 «خذ من 64» تضيف أربعاً أخرى", len(pos()), 12)

say("ستوبك 60", key="s6")
check("12:56 الستوب 3960 على الاثنتي عشرة",
      sum(1 for p in pos() if p.sl == 3960.0), 12)

say("هدف اول 70\nهدف ثاني 75", key="s7")
check("12:57 الهدف الأول 3970 على النصف",
      sum(1 for p in pos() if p.tp == 3970.0), 6)
check("والهدف الثاني 3975 على النصف الآخر",
      sum(1 for p in pos() if p.tp == 3975.0), 6)

say("الان قادمة حركة زمنية ستوبك ثابت", key="s8")
check("12:59 «ستوبك ثابت» بلا رقم لا تغيّر",
      sum(1 for p in pos() if p.sl == 3960.0), 12)

say("اغلاق دخول", key="s9")
check("13:03 «اغلاق دخول» تغلق الكل", len(pos()), 0)

# توصية جديدة: فتحٌ وستوبٌ في رسالة واحدة
say("شراء من 62 ستوبك 60", key="s10")
check("13:13 «شراء من 62 ستوبك 60» تفتح ٤", len(pos()), 4)
check("وكلها شراء",
      all(p.type == mt5.POSITION_TYPE_BUY for p in pos()), True)
check("وبالستوب 3960 من الرسالة نفسها",
      sum(1 for p in pos() if p.sl == 3960.0), 4)

say("يعني ستوبك pip 20 فقط انتبه", key="s11")
check("13:14 شرح النقاط لا يحرّك الوقف",
      sum(1 for p in pos() if p.sl == 3960.0), 4)

say("انتهت حبايي", key="s12")
check("13:15 «انتهت» تغلق ما بقي", len(pos()), 0)

for quiet in ("المنطقة اصبحت مستهلكة", "بأذن الله ننتظر دخول نظيف",
              "وندخل سوا", "شوف تلاعب يوم الجمعة يلمسه ويطير"):
    say(quiet, key=f"q{quiet[:6]}")
check("13:15-13:17 الكلام الأخير لا يفتح شيئاً", len(pos()), 0)

print("\n[١٩] صفقة واحدة × 0.10 بهدف واحد — الحساب الصغير")
reset(3965.0)
B._vip_state.update({"lot": 0.10, "positions": 1, "one_target": True,
                     "halted": False, "no_reopen": False,
                     "day": B.vip_today(), "direction": None,
                     "stop_was_hit": False, "start_equity": None,
                     "max_loss": 50.0})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=100.0, equity=100.0)

say("شراء الان", key="one1")
check("تُفتح صفقة واحدة لا أربع", len(pos()), 1)
check("بلوت 0.10", {round(p.volume, 4) for p in pos()}, {0.1})

say("هدف اول 70\nهدف ثاني 75", key="one2")
check("الهدف الأول على الصفقة", sum(1 for p in pos() if p.tp == 3970.0), 1)
check("ولا هدف ثانٍ", sum(1 for p in pos() if p.tp == 3975.0), 0)

# «احجز نص» لا تُنهي التوصية: صفقة واحدة لا تُنصَّف
say("احجز نص", key="one3")
check("«احجز نص» لا تغلق الصفقة الوحيدة", len(pos()), 1)
check("لكنها تنقل الوقف للدخول",
      sum(1 for p in pos() if p.sl == p.price_open), 1)

# «خفف لوتك» لا تغلق آخر صفقة أيضاً
say("خفف لوتك", key="one4")
check("«خفف لوتك» لا تغلق الوحيدة", len(pos()), 1)

say("اخرج", key="one5")
check("«اخرج» تغلقها", len(pos()), 0)

# «شراء بلوت بسيط» مع صفقة واحدة: تبقى واحدة لا صفراً
say("شراء بلوت بسيط", key="one6")
check("«لوت بسيط» تفتح واحدة لا صفراً", len(pos()), 1)
say("انتهت", key="one7")

B._vip_state.update({"lot": 0.01, "positions": 4, "one_target": False})

print("\n[٢٠] بلا وقف مؤقت — الوقف من المدرّب وحده")
reset(3965.0)
B._vip_state.update({"lot": 0.10, "positions": 1, "one_target": True,
                     "temp_sl": 0.0, "halted": False, "no_reopen": False,
                     "day": B.vip_today(), "direction": None,
                     "stop_was_hit": False, "start_equity": None,
                     "max_loss": 0.0})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=100.0, equity=100.0)

say("شراء الان", key="nosl1")
check("فُتحت الصفقة", len(pos()), 1)
check("بلا وقف", [p.sl for p in pos()], [0.0])

# وقف المدرّب يُوضع حين يصل
say("ستوبك 60", key="nosl2")
check("وقف المدرّب يُوضع", [p.sl for p in pos()], [3960.0])

say("اخرج", key="nosl3")

# والوقف المؤقت يعمل كما كان حين يُطلب
B._vip_state.update({"temp_sl": 5.0, "no_reopen": False})
say("شراء الان", key="withsl")
check("وبوقف مؤقت 5 حين يُضبط",
      [round(p.price_open - p.sl, 2) for p in pos()], [5.0])
say("اخرج", key="withsl2")
B._vip_state.update({"lot": 0.01, "positions": 4, "one_target": False,
                     "temp_sl": 5.0})

print("\n[٢١] رسالة البدء تُبنى في كل الأوضاع")
# انكسرت مرّةً فتعطّل التشغيل كلّه ولم يكشفها فحص: تُبنى هنا بكل
# تركيبة، فأيّ كسرٍ فيها يظهر قبل أن يصل إلى حساب حقيقي.
combos = 0
for one_target in (True, False):
    for positions in (1, 4):
        for temp_sl in (0.0, 5.0):
            for max_loss in (0.0, 60.0):
                for is_real in (True, False):
                    B._vip_state.update({
                        "one_target": one_target, "positions": positions,
                        "temp_sl": temp_sl, "lot": 0.10})
                    B._guard_state["max_loss"] = max_loss
                    text = B.startup_message(
                        SYM, 250950427, 100.0, is_real,
                        "حقيقي" if is_real else "تجريبي", "VIP AN")
                    assert isinstance(text, str) and len(text) > 200, text
                    assert "VIP AN" in text
                    combos += 1
check("كل التركيبات تُبنى", combos, 32)

B._vip_state.update({"temp_sl": 0.0, "positions": 1,
                     "one_target": True, "lot": 0.10})
B._guard_state["max_loss"] = 0.0
text = B.startup_message(SYM, 250950427, 100.0, True, "حقيقي", "VIP AN")
check("تقول «بلا وقف مؤقت» صراحةً", "بلا وقف مؤقت" in text, True)
check("وتقول إن الحدّ اليومي معطّل", "معطّل" in text, True)
check("وصفقة واحدة لا تُنصَّف", "لا تُنصَّف" in text, True)
check("ولا تَعِد بهدف ثانٍ", "ولا هدف ثانٍ" in text, True)

B._vip_state.update({"temp_sl": 5.0, "positions": 4,
                     "one_target": False, "lot": 0.01})
B._guard_state["max_loss"] = 150.0
text = B.startup_message(SYM, 1550318365, 1050.0, True, "حقيقي", "VIP AN")
check("وبالوضع الافتراضي تذكر الوقف المؤقت", "وقف مؤقت" in text, True)
check("والحدّ اليومي برقمه", "$150" in text, True)

print("\n[٢٢] لا يخلط الحسابين — أمرٌ واحد لا يمرّ إلى حساب آخر")
# بوتان يعملان معاً بلوتين مختلفين. الخوف أن يذهب أمر الواحد إلى
# حساب الآخر، فتُفتح 0.10 على حساب 0.01. الفحص هنا يثبت أن كل أمر
# — فتحاً وتعديلاً وإغلاقاً — يتحقق من رقم الحساب لحظة إرساله، لا
# عند الإقلاع وحده: منصّةٌ بدّلت الحساب بعد ساعة لا تمرّ.
reset(3965.0)
B._vip_state.update({"lot": 0.10, "positions": 1, "one_target": True,
                     "temp_sl": 0.0, "halted": False, "no_reopen": False,
                     "day": B.vip_today(), "direction": None,
                     "stop_was_hit": False, "start_equity": None,
                     "max_loss": 0.0})

def _account(login):
    return lambda: types.SimpleNamespace(
        login=login, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
        trade_allowed=True,
        margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
        balance=100.0, equity=100.0)

# الحساب الصحيح: يفتح
mt5.account_info = _account(250950427)
B._channel_runtime_mode["account_login"] = 250950427
say("شراء الان", key="mix1")
check("على حسابه يفتح", len(pos()), 1)

# المنصّة بدّلت إلى الحساب الآخر — حساب البوت الأول
mt5.account_info = _account(1550318365)
say("اخرج", key="mix2")
check("ولا يغلق على حساب آخر", len(pos()), 1)
say("ستوبك 60", key="mix3")
check("ولا يعدّل وقفاً على حساب آخر", [p.sl for p in pos()], [0.0])

B._vip_state["no_reopen"] = False
say("بيع الان", key="mix4")
check("ولا يفتح على حساب آخر", len(pos()), 1)

# عادت المنصّة إلى حسابه: يعمل من جديد
mt5.account_info = _account(250950427)
say("اخرج", key="mix5")
check("وبعودة حسابه يغلق", len(pos()), 0)

B._channel_runtime_mode["account_login"] = 1550318365
B._vip_state.update({"lot": 0.01, "positions": 4, "one_target": False,
                     "temp_sl": 5.0, "no_reopen": False})

print("\n[٢٣] هدف ثابت +5 نقاط — وأهداف القناة تُتجاهل")
reset(3897.0)
B._vip_state.update({"lot": 0.05, "positions": 1, "one_target": True,
                     "temp_sl": 0.0, "fixed_tp": 5.0, "halted": False,
                     "no_reopen": False, "day": B.vip_today(),
                     "direction": None, "stop_was_hit": False,
                     "start_equity": None, "max_loss": 0.0})
B._channel_runtime_mode["account_login"] = 250950427
mt5.account_info = lambda: types.SimpleNamespace(
    login=250950427, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=100.0, equity=100.0)

say("شراء من 94", key="ft1")
check("فُتحت الصفقة", len(pos()), 1)
check("والهدف +5 من دخولها",
      [round(p.tp - p.price_open, 2) for p in pos()], [5.0])
check("وبلا وقف", [p.sl for p in pos()], [0.0])

# وقف القناة يُوضع ولا يمسّ الهدف
say("ستوبك 90", key="ft2")
check("وقف القناة يُوضع", [p.sl for p in pos()], [3890.0])
check("والهدف الثابت باقٍ",
      [round(p.tp - p.price_open, 2) for p in pos()], [5.0])

# هدف القناة يُتجاهل
say("هدف اول 4903\nهدف ثاني 4907", key="ft3")
check("هدف القناة لا يغيّر شيئاً",
      [round(p.tp - p.price_open, 2) for p in pos()], [5.0])
say("هدفك 3906", key="ft4")
check("ولا هدفها الآخر",
      [round(p.tp - p.price_open, 2) for p in pos()], [5.0])

# البيع: الهدف تحت الدخول
say("اخرج", key="ft5")
B._vip_state["no_reopen"] = False
say("بيع الان", key="ft6")
check("وفي البيع الهدف تحت الدخول",
      [round(p.price_open - p.tp, 2) for p in pos()], [5.0])
say("اخرج", key="ft7")

# وبصفر يعود إلى هدف القناة
B._vip_state.update({"fixed_tp": 0.0, "no_reopen": False,
                     "one_target": True})
say("شراء الان", key="ft8")
check("بصفر لا هدف عند الفتح", [p.tp for p in pos()], [0.0])
say("هدفك 3906", key="ft9")
check("وهدف القناة يُوضع", [p.tp for p in pos()], [3906.0])
say("اخرج", key="ft10")

B._channel_runtime_mode["account_login"] = 1550318365
B._vip_state.update({"lot": 0.01, "positions": 4, "one_target": False,
                     "temp_sl": 5.0, "fixed_tp": 0.0, "no_reopen": False})

print("\n[٢٤] قناتان منفصلتان — أمرُ إحداهما لا يمسّ الأخرى")
reset(3900.0)
A, Bch = B.set_channels([
    B.parse_channel_spec("VIP AN|lot=0.05|pos=1|sl=5|tp=5|one", 0, {}),
    B.parse_channel_spec("القناة الثانية|lot=0.02|pos=2|sl=8", 1, {}),
])
B._guard_state.update({"max_loss": 0.0, "halted": False,
                       "day": B.vip_today(), "start_equity": None})
mt5.account_info = lambda: types.SimpleNamespace(
    login=250950427, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=100.0, equity=100.0)
B._channel_runtime_mode["account_login"] = 250950427

def mine(ch):
    return B.vip_positions(SYM, ch)

check("لكلٍّ رقم سحرٍ مختلف", A["magic"] != Bch["magic"], True)

# A تفتح
B.handle_vip_message(SYM, "شراء الان", "a1", A)
check("A فتحت صفقة واحدة", len(mine(A)), 1)
check("بلوت 0.05", [round(p.volume, 4) for p in mine(A)], [0.05])
check("B لم تفتح شيئاً", len(mine(Bch)), 0)

# B تفتح بلوتها وعددها
B.handle_vip_message(SYM, "بيع الان", "b1", Bch)
check("B فتحت صفقتين", len(mine(Bch)), 2)
check("بلوت 0.02", sorted({round(p.volume, 4) for p in mine(Bch)}), [0.02])
check("وA ما زالت واحدة", len(mine(A)), 1)
check("والمجموع ثلاث", len(pos()) if False else
      len(mine(A)) + len(mine(Bch)), 3)

# وقف كل قناة من رسالتها هي
check("وقف A المؤقت 5", [round(p.price_open - p.sl, 2) for p in mine(A)], [5.0])
check("ووقف B المؤقت 8",
      sorted({round(p.sl - p.price_open, 2) for p in mine(Bch)}), [8.0])

# هدف A ثابت، وهدف القناة يُتجاهل؛ وB تتبع قناتها
check("هدف A ثابت +5",
      [round(p.tp - p.price_open, 2) for p in mine(A)], [5.0])
B.handle_vip_message(SYM, "هدفك 3950", "a2", A)
check("وهدف قناة A يُتجاهل",
      [round(p.tp - p.price_open, 2) for p in mine(A)], [5.0])
B.handle_vip_message(SYM, "هدفك 3890", "b2", Bch)
# B على الوضع الافتراضي (هدفان)، فالهدف الأول لنصف مجموعتها
check("وهدف قناة B يُوضع على نصف صفقاتها",
      sum(1 for p in mine(Bch) if p.tp == 3890.0), 1)
check("ولم يمسّ صفقة A",
      [round(p.tp - p.price_open, 2) for p in mine(A)], [5.0])

# ★ الجوهر: «خروج» من A لا تغلق صفقات B
B.handle_vip_message(SYM, "اخرج", "a3", A)
check("«خروج» من A تغلق صفقتها", len(mine(A)), 0)
check("وصفقتا B باقيتان", len(mine(Bch)), 2)

# و«انتهت لا تفعل» في A لا تمنع B من الفتح
B.handle_vip_message(SYM, "انتهت لا تفعل شيء", "a4", A)
check("A ممنوعة من الفتح", A["no_reopen"], True)
check("وB غير ممنوعة", Bch["no_reopen"], False)
B.handle_vip_message(SYM, "اخرج", "b3", Bch)
check("و«خروج» من B تغلق صفقتيها", len(mine(Bch)), 0)
B.handle_vip_message(SYM, "شراء الان", "b4", Bch)
check("وB تفتح رغم منع A", len(mine(Bch)), 2)
check("وA ما زالت مغلقة", len(mine(A)), 0)

# حارس الخسارة على الحساب: يغلق القناتين معاً
B._guard_state.update({"max_loss": 20.0, "halted": False,
                       "day": B.vip_today(), "start_equity": 100.0})
A["no_reopen"] = False
B.handle_vip_message(SYM, "شراء الان", "a5", A)
check("A فتحت من جديد", len(mine(A)), 1)
mt5.account_info = lambda: types.SimpleNamespace(
    login=250950427, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=100.0, equity=79.0)
check("الحدّ يُبلَغ", B.vip_loss_guard(SYM), True)
check("ويغلق صفقات A", len(mine(A)), 0)
check("وصفقات B معاً", len(mine(Bch)), 0)
check("ويوقف الحساب كله", B._guard_state["halted"], True)

# العودة إلى قناة واحدة لبقية الفحوصات
B.set_channels([B.new_channel("", B.MAGIC_GOLDBOT)])
B._guard_state.update({"max_loss": 150.0, "halted": False,
                       "day": B.vip_today(), "start_equity": None})
B._channel_runtime_mode["account_login"] = 1550318365

print("\n[٢٥] وصف القناة في سطر الأوامر")
_d = {"lot": 0.01, "positions": 4, "temp_sl": 5.0, "fixed_tp": 0.0,
      "one_target": False}
_c = B.parse_channel_spec("VIP AN|lot=0.05|pos=1|sl=5|tp=5|one", 0, _d)
check("الوصف الكامل يُفهم",
      (_c["name"], _c["lot"], _c["positions"], _c["temp_sl"],
       _c["fixed_tp"], _c["one_target"]),
      ("VIP AN", 0.05, 1, 5.0, 5.0, True))
_c2 = B.parse_channel_spec("القناة الثانية", 1, _d)
check("وما لم يُذكر يأخذ الإعداد العام",
      (_c2["lot"], _c2["positions"], _c2["one_target"]), (0.01, 4, False))
check("والسحر من الترتيب", _c2["magic"] - _c["magic"], 1)
_c3 = B.parse_channel_spec("  X | lot = 0.2 | TP=3 ", 2, _d)
check("المسافات وحالة الأحرف لا تضرّ",
      (_c3["name"], _c3["lot"], _c3["fixed_tp"]), ("X", 0.2, 3.0))
_c4 = B.parse_channel_spec("Y|lot=سبعة|zzz=1", 3, _d)
check("القيمة الفاسدة تُتجاهل ويبقى العام", _c4["lot"], 0.01)
_chs = B.build_channels(["A|lot=0.05", "B|lot=0.02"], _d)
check("قناتان بسحرين", [c["name"] for c in _chs], ["A", "B"])
B.set_channels(_chs)
check("وسحرهما في حُرّاس الصفقات",
      {c["magic"] for c in _chs} <= B.ACTIVE_CHANNEL_MAGICS, True)
check("والأولى هي _vip_state", B._vip_state is _chs[0], True)

# رسالة البدء تصف القناتين لا واحدة
_txt = B.startup_message(SYM, 250950427, 100.0, True, "حقيقي", "A، B")
check("رسالة البدء تذكر الأولى", "A" in _txt, True)
check("وتذكر الثانية", "B" in _txt, True)
check("وتقول إنهما منفصلتان", "منفصلتان" in _txt, True)

B.set_channels([B.new_channel("", B.MAGIC_GOLDBOT)])
B._channel_runtime_mode["account_login"] = 1550318365

print("\n[٢٦] VEY GOLD VIP — صفقة عند كل رقم")
reset(4010.0)
broker.orders.clear()
V = B.set_channels([B.parse_channel_spec(
    "VEY GOLD VIP|lot=0.02|parser=en", 0, {})])[0]
B._guard_state.update({"max_loss": 0.0, "halted": False,
                       "day": B.vip_today(), "start_equity": None})
mt5.account_info = lambda: types.SimpleNamespace(
    login=250950427, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=100.0, equity=100.0)
B._channel_runtime_mode["account_login"] = 250950427

check("اللهجة إنجليزية", V["parser"], "en")
check("وتُبقي أوامرها المعلّقة", V["keep_pending"], True)
check("ووقفها الافتراضي 10 درجات", V["default_sl"], 10.0)
check("وهدفها 10 درجات", V["fixed_tp"], 10.0)
# صفقة عند كل رقم، والقناة ترسل رقمين: لولا ضبطه لقال العرضُ
# وحسابُ المخاطرة أربعاً وهي اثنتان
check("وعددها صفقتان لا أربع", B.vip_full(V), 2)

def mine():
    return B.vip_positions(SYM, V)

def waiting():
    return B.vey_pending(SYM, V)

# ★ السعر 4010 — عند الرقم الأعلى: سوقاً، والأدنى معلّق
B.route_message(SYM, "»» BUY NOW ««", "v1", V)
check("الاتجاه حُفظ وتُنتظر الأرقام", V["pending_direction"], "BUY")
B.route_message(SYM, "4005-4010", "v2", V)
check("صفقة واحدة سوقاً", len(mine()), 1)
check("وأمر واحد معلّق", len(waiting()), 1)
check("المعلّق عند 4005", [o.price_open for o in waiting()], [4005.0])
check("وبلوت 0.02",
      [round(p.volume, 4) for p in mine()] +
      [round(o.volume, 4) for o in waiting()], [0.02, 0.02])
check("والوقف 3995 للاثنين",
      sorted({p.sl for p in mine()} | {o.sl for o in waiting()}), [3995.0])
check("وهدف السوقية +10 من دخولها",
      [round(p.tp - p.price_open, 2) for p in mine()], [10.0])
check("وهدف المعلّقة 4015", [o.tp for o in waiting()], [4015.0])
check("والاتجاه استُهلك", V["pending_direction"], None)

# المعلّق يُنفَّذ حين يبلغه السعر
_t = waiting()[0].ticket
broker.fill(_t)
check("المعلّق صار صفقة", len(mine()), 2)
check("ولم يبقَ معلّق", len(waiting()), 0)

# وقف المدرّب يحلّ محل الافتراضي
B.route_message(SYM, "SL 3998", "v3", V)
check("وقف المدرّب على الصفقتين",
      sorted({p.sl for p in mine()}), [3998.0])

# التأمين
B.route_message(SYM, "+70 PIPS B/E ✅", "v4", V)
check("التأمين ينقل الوقف للدخول",
      sum(1 for p in mine() if p.sl == p.price_open), 2)

# الإغلاق
B.route_message(SYM, "TP 1 HIT 🎯 100PIPS\nWE CLOSE 60-70% OF THE DEALS",
                "v5", V)
check("الإغلاق يغلق الصفقتين", len(mine()), 0)

print("\n[٢٧] VEY — البيع، والسعر لم يبلغ، والمعلّقات تبقى")
reset(4015.0)
broker.orders.clear()
V["pending_direction"] = None

# ★ السعر 4030 والبيع 4021-4026: الاثنان تحته، فأمران معلّقان
B.route_message(SYM, "»» SELL NOW ««", "w1", V)
B.route_message(SYM, "4021-4026", "w2", V)
check("لا صفقة سوقية", len(mine()), 0)
check("وأمران معلّقان", len(waiting()), 2)
check("عند 4021 و4026",
      sorted(o.price_open for o in waiting()), [4021.0, 4026.0])
check("والوقف 4036 = الأعلى + 10",
      sorted({o.sl for o in waiting()}), [4036.0])
check("وهدفاهما تحت دخولهما بـ10",
      sorted(round(o.price_open - o.tp, 2) for o in waiting()), [10.0, 10.0])

# ★ توصية جديدة لا تلغي المعلّق القديم — مناطق سيولة
B.route_message(SYM, "BUY LIMIT 4000-3995", "w3", V)
check("المعلّقات صارت أربعة", len(waiting()), 4)

# ★ والإغلاق لا يلغيها أيضاً
B.route_message(SYM, "TP1 HIT", "w4", V)
check("والإغلاق يُبقيها", len(waiting()), 4)

# ★ وقف المدرّب يصل إلى المعلّقات أيضاً
B.route_message(SYM, "sl 4040", "w5", V)
check("وقف المدرّب على كل المعلّقات",
      sorted({o.sl for o in waiting()}), [4040.0])

print("\n[٢٨] VEY — السعر تجاوز الوقف: لا يفتح شيئاً")
reset(3990.0)
broker.orders.clear()
V["pending_direction"] = None
B.route_message(SYM, "»» BUY NOW ««", "x1", V)
B.route_message(SYM, "4005-4010", "x2", V)
check("لا صفقة", len(mine()), 0)
check("ولا أمر معلّق", len(waiting()), 0)

# وبيعٌ فوق وقفه كذلك
reset(4040.0)
V["pending_direction"] = None
B.route_message(SYM, "»» SELL NOW ««", "x3", V)
B.route_message(SYM, "4021-4026", "x4", V)
check("والبيع فوق وقفه لا يفتح", len(mine()) + len(waiting()), 0)

B.set_channels([B.new_channel("", B.MAGIC_GOLDBOT)])
B._guard_state.update({"max_loss": 150.0, "halted": False})
B._channel_runtime_mode["account_login"] = 1550318365
broker.orders.clear()

print("\n[٢٩] ثلاث قنوات معاً — كلٌّ بسحرها")
reset(4010.0)
broker.orders.clear()
_three = B.set_channels([
    B.parse_channel_spec("VIP AN|lot=0.05|pos=1|sl=5|tp=5|one", 0, {}),
    B.parse_channel_spec("AN Damages|lot=0.05|pos=1|sl=5|tp=5|one", 1, {}),
    B.parse_channel_spec("VEY GOLD VIP|lot=0.02|parser=en", 2, {}),
])
_an, _dam, _vey = _three
check("ثلاثة أرقام سحرٍ مختلفة",
      len({c["magic"] for c in _three}), 3)
check("والأوليان متطابقتان في الإعداد",
      (_an["lot"], _an["positions"], _an["temp_sl"], _an["fixed_tp"],
       _an["one_target"], _an["parser"]) ==
      (_dam["lot"], _dam["positions"], _dam["temp_sl"], _dam["fixed_tp"],
       _dam["one_target"], _dam["parser"]), True)
check("والثالثة إنجليزية", _vey["parser"], "en")

B._guard_state.update({"max_loss": 0.0, "halted": False,
                       "day": B.vip_today(), "start_equity": None})
mt5.account_info = lambda: types.SimpleNamespace(
    login=250950427, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=138.0, equity=138.0)
B._channel_runtime_mode["account_login"] = 250950427

# نفس الرسالة من القناتين: صفقتان منفصلتان — هذا ما اختاره صاحب
# الحساب وهو يعلم أنه يضاعف المخاطرة
B.route_message(SYM, "شراء الان", "t1", _an)
B.route_message(SYM, "شراء الان", "t2", _dam)
check("VIP AN فتحت واحدة", len(B.vip_positions(SYM, _an)), 1)
check("و AN Damages واحدة أخرى", len(B.vip_positions(SYM, _dam)), 1)
# pos() يقرأ القناة الافتراضية وحدها، والمجموع يُجمع من القنوات
check("والمجموع صفقتان",
      sum(len(B.vip_positions(SYM, c)) for c in _three), 2)

# «خروج» من إحداهما لا تمسّ الأخرى
B.route_message(SYM, "اخرج", "t3", _an)
check("«خروج» من VIP AN تغلق صفقتها", len(B.vip_positions(SYM, _an)), 0)
check("وصفقة AN Damages باقية", len(B.vip_positions(SYM, _dam)), 1)

# والإنجليزية لا تتأثر بشيء منهما
B.route_message(SYM, "»» BUY NOW ««", "t4", _vey)
B.route_message(SYM, "4005-4010", "t5", _vey)
check("VEY فتحت واحدة وعلّقت واحدة",
      (len(B.vip_positions(SYM, _vey)), len(B.vey_pending(SYM, _vey))),
      (1, 1))
check("و AN Damages ما زالت واحدة", len(B.vip_positions(SYM, _dam)), 1)
B.route_message(SYM, "اخرج", "t6", _dam)
check("وإغلاقها لا يمسّ VEY", len(B.vip_positions(SYM, _vey)), 1)

B.set_channels([B.new_channel("", B.MAGIC_GOLDBOT)])
B._guard_state.update({"max_loss": 150.0, "halted": False})
B._channel_runtime_mode["account_login"] = 1550318365
broker.orders.clear()

print("\n[٣٠] جلسة AN Damages — الوقف إلى دخول المدرّب")
# المدرّب يبيع من 3947، والبوت يتأخر لحظة فيبيع من 3946. فإذا قال
# «ستوبك دخولك» نُقل الوقف إلى 3946: أضيق بدرجة من وقف المدرّب،
# فيُضرب وحده ثم تمضي الصفقة إلى هدفه.
reset(3946.0)
D = B.set_channels([B.parse_channel_spec(
    "AN Damages|lot=0.01|pos=4|sl=5|one", 0, {})])[0]
B._guard_state.update({"max_loss": 0.0, "halted": False,
                       "day": B.vip_today(), "start_equity": None})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1000.0, equity=1000.0)
B._channel_runtime_mode["account_login"] = 1550318365

say("بيع الان", key="d1")
check("فُتحت ٤ صفقات بيع", len(pos()), 4)
_entry = pos()[0].price_open
check("ودخول البوت 3946", round(_entry, 2), 3946.0)

# أرقام المدرّب تصل بعدها
say("46", key="d2")
say("3946", key="d3")
say("3947", key="d4")
check("حُفظت أسعار المدرّب", sorted(D["quoted"]), [3946.0, 3947.0])

say("هدفك 3940", key="d5")
check("الهدف لا يُحسب سعر دخول", sorted(D["quoted"]), [3946.0, 3947.0])

say("ستوبك دخولك الان", key="d6")
check("الوقف إلى 3947 لا 3946",
      sorted({p.sl for p in pos()}), [3947.0])

# ★ ودرجةٌ واحدة هي الفرق: لو كان الوقف 3946 لضُرب هنا
check("ولو كان عند دخول البوت لكان 3946",
      round(_entry, 2) != 3947.0, True)

# توصية جديدة تصفّر الأسعار القديمة
say("خروووججج", key="d7")
say("بيع الان", key="d8")
check("التوصية الجديدة تصفّر أسعار القديمة", D["quoted"], [])
say("ستوبك دخولك", key="d9")
check("وبلا أسعار يعود إلى دخول البوت",
      sorted({round(p.sl, 2) for p in pos()}),
      sorted({round(p.price_open, 2) for p in pos()}))

# وفي الشراء يُؤخذ الأدنى — الأوسع مدى
say("خروووججج", key="d10")
reset(3918.0)
say("شراء الان", key="d11")
say("4917-4918", key="d12")   # غلطة خانة الألوف: 3917 و3918
check("حُفظ الرقمان", sorted(D["quoted"]), [3917.0, 3918.0])
say("ستوبك دخولك", key="d13")
check("وفي الشراء الأدنى 3917",
      sorted({p.sl for p in pos()}), [3917.0])
say("خروووججج", key="d14")

B.set_channels([B.new_channel("", B.MAGIC_GOLDBOT)])
B._guard_state.update({"max_loss": 150.0, "halted": False})

print("\n[٣٢] «انت تأمين لا تجدد» — خبرُ نهاية لا أمرُ وقف")
reset(3957.0)
E = B.set_channels([B.parse_channel_spec(
    "AN Damages|lot=0.01|pos=4|sl=5|one", 0, {})])[0]
B._guard_state.update({"max_loss": 0.0, "halted": False,
                       "day": B.vip_today(), "start_equity": None})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1000.0, equity=1000.0)
B._channel_runtime_mode["account_login"] = 1550318365

# جلسة 18:35 كما وقعت
say("اجهز", key="e0")
say("شراء من 57", key="e1")
check("فُتحت ٤ صفقات", len(pos()), 4)
say("3957", key="e2")
say("هدفك 3965", key="e3")
check("الهدف 3965", sorted({p.tp for p in pos()}), [3965.0])

# ★ الرقم الصريح في رسالة التأمين
say("ستوبك دخولك على 57", key="e4")
check("الوقف إلى 3957 من الرسالة نفسها",
      sorted({p.sl for p in pos()}), [3957.0])

# ★ «انت تأمين لا تجدد»: إغلاقٌ ومنعُ فتح، لا نقلُ وقف
say("انت تأمين لا تجدد", key="e5")
check("أُغلقت كل الصفقات", len(pos()), 0)
check("ومُنع الفتح مجدداً", E["no_reopen"], True)
# «جدد» ممنوعة — وهي المقصودة بـ«لا تجدد»
say("جدد", key="e6")
check("«جدد» ممنوعة", len(pos()), 0)
check("والمنع ما زال قائماً", E["no_reopen"], True)

# وتوصيةٌ جديدة صريحة ترفعه، كما اتفقنا: «توصية جديدة تعمل»
say("شراء الان", key="e7")
check("والتوصية الجديدة تفتح", len(pos()), 4)
check("وترفع المنع", E["no_reopen"], False)
say("انتهى التامين", key="e8")
check("و«انتهى التامين» تغلق", len(pos()), 0)
check("لكن بلا منع — لم يقل لا تجدد", E["no_reopen"], False)

B.set_channels([B.new_channel("", B.MAGIC_GOLDBOT)])
B._guard_state.update({"max_loss": 150.0, "halted": False})

print("\n[٣٣] abdool الجديد — وقف أبعد بدرجة وهدف مؤقت")
reset(3957.0)
A2 = B.set_channels([B.parse_channel_spec(
    "VIP AN|lot=0.01|pos=4|sl=10|ttp=10|pad=1|one", 0, {})])[0]
B._guard_state.update({"max_loss": 0.0, "halted": False,
                       "day": B.vip_today(), "start_equity": None})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1063.0, equity=1063.0)
B._channel_runtime_mode["account_login"] = 1550318365
check("الإعداد مقروء",
      (A2["temp_sl"], A2["temp_tp"], A2["sl_pad"]), (10.0, 10.0, 1.0))

say("شراء الان", key="a1")
check("فُتحت ٤", len(pos()), 4)
check("وقف مؤقت 10 درجات",
      sorted({round(p.price_open - p.sl, 2) for p in pos()}), [10.0])
check("وهدف مؤقت 10 درجات",
      sorted({round(p.tp - p.price_open, 2) for p in pos()}), [10.0])

# ★ وقف المدرّب يُزاح درجةً أبعد
say("ستوبك 50", key="a2")
check("وقف المدرّب 3950 يصير 3949",
      sorted({p.sl for p in pos()}), [3949.0])

# وهدف المدرّب يحلّ محل المؤقت فوراً
say("هدفك 3965", key="a3")
check("هدف المدرّب يحلّ محل المؤقت",
      sorted({p.tp for p in pos()}), [3965.0])

# وفي البيع الإزاحة إلى الأعلى
say("خروووججج", key="a4")
reset(3957.0)
say("بيع الان", key="a5")
check("البيع: وقف مؤقت 10 فوق الدخول",
      sorted({round(p.sl - p.price_open, 2) for p in pos()}), [10.0])
say("ستوبك 65", key="a6")
check("وقف المدرّب 3965 يصير 3966",
      sorted({p.sl for p in pos()}), [3966.0])

# ★ «خذ من 50» تضيف أربعاً
say("يلا خذ من 50", key="a7")
check("أُضيفت أربع", len(pos()), 8)
check("وكلها بيع",
      all(p.type == mt5.POSITION_TYPE_SELL for p in pos()), True)
say("خروووججج", key="a8")

B.set_channels([B.new_channel("", B.MAGIC_GOLDBOT)])
B._guard_state.update({"max_loss": 150.0, "halted": False})

print("\n[٣٤] لا تأمين تلقائي — الوقف لا يتحرك إلا بأمر المدرّب")
# «اذا امن وحده بعد خمس درجات وبعدها نزل السعر عند الدخول تغلق
# الصفقة والمدرب يربح» — فأُطفئ في abdool.
reset(3950.0)
Z = B.set_channels([B.parse_channel_spec(
    "VIP AN|lot=0.01|pos=4|sl=10|ttp=10|pad=1|abe=0|one", 0, {})])[0]
B._guard_state.update({"max_loss": 0.0, "halted": False,
                       "day": B.vip_today(), "start_equity": None})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1061.0, equity=1061.0)
B._channel_runtime_mode["account_login"] = 1550318365
check("التأمين التلقائي مُطفأ", Z["auto_be"], 0.0)

say("شراء الان", key="z1")
_sl0 = sorted({p.sl for p in pos()})
check("فُتحت ٤ بوقف مؤقت", len(pos()), 4)

# السعر يرتفع عشر درجات — ضِعفُ العتبة القديمة
broker.move(3960.0)
B.vip_auto_breakeven(SYM)
check("الوقف لم يتحرك رغم +10 درجات",
      sorted({p.sl for p in pos()}), _sl0)

# وأمر المدرّب وحده يحرّكه
say("ستوبك دخولك", key="z2")
check("وأمر المدرّب يحرّكه",
      sorted({round(p.sl, 2) for p in pos()}),
      sorted({round(p.price_open, 2) for p in pos()}))
say("خروووججج", key="z3")

# وقناةٌ أبقته تعمل كما كانت
reset(3950.0)
Y = B.set_channels([B.parse_channel_spec(
    "VIP AN|lot=0.01|pos=4|sl=10|abe=5|one", 0, {})])[0]
say("شراء الان", key="y1")
broker.move(3960.0)
B.vip_auto_breakeven(SYM)
check("وبإبقائه يتحرك عند +5",
      sorted({round(p.sl, 2) for p in pos()}),
      sorted({round(p.price_open, 2) for p in pos()}))
say("خروووججج", key="y2")

B.set_channels([B.new_channel("", B.MAGIC_GOLDBOT)])
B._guard_state.update({"max_loss": 150.0, "halted": False})

print("\n[٣١] السجلّ اليومي — يكتب ولا يعطّل")
import glob
import io as _io
_j = B.JOURNAL_DIR
B.journal("رسالة", "قناة", "نصٌّ للفحص", "سبب")
_files = glob.glob(os.path.join(_j, "*.txt"))
check("أنشأ ملف اليوم", len(_files) >= 1, True)
_text = _io.open(_files[0], encoding="utf-8").read()
check("وكتب النص", "نصٌّ للفحص" in _text, True)
check("والسبب", "سبب" in _text, True)

# نصٌّ طويل يُقصّ فلا ينتفخ الملف برسالةٍ واحدة
B.journal("رسالة", "قناة", "ط" * 900)
_text = _io.open(_files[0], encoding="utf-8").read()
check("والطويل يُقصّ", max(len(l) for l in _text.splitlines()) < 400, True)

# ★ السجلّ أداة تشخيص لا جزءٌ من التنفيذ: عطبُه لا يوقف البوت
_orig = B.JOURNAL_DIR
B.JOURNAL_DIR = "\x00مسار/غير/صالح"
B.journal("رسالة", "قناة", "لا يجب أن يرفع استثناءً")
B.journal_account(SYM, "ولا هذه")
check("ومسارٌ فاسد لا يرفع استثناءً", True, True)
B.JOURNAL_DIR = _orig

print(f"\n{'─' * 58}\nنجح: {ok} | فشل: {bad}\n")
sys.exit(1 if bad else 0)
