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
A_DEAL, A_SLTP, A_PENDING, A_REMOVE = 1, 2, 5, 6


class Broker:
    def __init__(self, price=4010.0, spread=0.20):
        self.bid = price
        self.spread = spread
        self.positions = {}
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
        return ()

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
B._vip_state.update({"max_loss": 150.0, "halted": False,
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
check("والبوت موقوف", B._vip_state["halted"], True)

# بعد التوقف لا يفتح مهما وصل
say("بيع", key="after-halt")
check("«بيع» بعد التوقف لا تفتح", len(pos()), 0)
say("شراء الان", key="after-halt2")
check("ولا «شراء»", len(pos()), 0)

# الخسارة العائمة تُحسب، لا الرصيد وحده
B._vip_state.update({"halted": False, "start_equity": 1050.0,
                     "day": B.vip_today()})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=1050.0, equity=880.0)      # الرصيد سليم والعائم خاسر
check("العائم وحده يكفي للإيقاف", B.vip_loss_guard(SYM), True)

# الحد صفر = معطّل
B._vip_state.update({"halted": False, "max_loss": 0.0})
check("الحد صفر يعطّل الحارس", B.vip_loss_guard(SYM), False)
B._vip_state.update({"max_loss": 150.0, "halted": False})


print("\n[١٤] الحدّ يومي — يصفّر مع كل يوم جديد")
reset(4010.0)
# يوم الأمس انتهى على خسارة $200 — أكثر من الحد
B._vip_state.update({"max_loss": 150.0, "halted": False,
                     "start_equity": 1050.0, "day": "2020-01-01"})
mt5.account_info = lambda: types.SimpleNamespace(
    login=1550318365, trade_mode=mt5.ACCOUNT_TRADE_MODE_REAL,
    trade_allowed=True,
    margin_mode=mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING,
    balance=850.0, equity=850.0)
check("خسارة الأمس لا توقف اليوم", B.vip_loss_guard(SYM), False)
check("واليوم صار اليوم الحالي", B._vip_state["day"], B.vip_today())
check("والأساس صار حقوق اليوم", B._vip_state["start_equity"], 850.0)

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
check("والبوت موقوف", B._vip_state["halted"], True)
B._vip_state.update({"halted": False, "day": B.vip_today()})

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

print(f"\n{'─' * 58}\nنجح: {ok} | فشل: {bad}\n")
sys.exit(1 if bad else 0)
