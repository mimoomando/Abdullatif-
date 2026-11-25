"""فحص مرآة الحساب — بصفقاتٍ حقيقية من الحساب المراقَب:

    python3 test_mirror.py

الأرقام هنا منقولةٌ من سجلّ الحساب كما ظهر يومي 24 و25 نوفمبر، لا
مخترعة. ولا شيء هنا يلمس حساباً: الوسيط وهمي يعيش في الذاكرة.
"""
import os
import sys
import tempfile
import types


TYPE_BUY, TYPE_SELL = 0, 1


class Broker:
    """وسيطٌ وهمي: صفقاتٌ في الذاكرة وسعرٌ نحرّكه بأيدينا."""

    def __init__(self, price=3620.0, spread=0.20):
        self.bid = price
        self.spread = spread
        self.positions = {}
        self.deals = {}
        self.next_ticket = 70000
        self.bars = []        # شموع الدقيقة: (open, high, low, close)
        self.sent = []

    @property
    def ask(self):
        return round(self.bid + self.spread, 2)

    def move(self, price):
        self.bid = round(price, 2)

    def tick(self, symbol=None, **k):
        return types.SimpleNamespace(bid=self.bid, ask=self.ask,
                                     last=self.bid, time=0)

    def positions_get(self, **k):
        return tuple(self.positions.values())

    def open(self, symbol, buy, lot, price, sl=0.0, tp=0.0, when=1000.0):
        self.next_ticket += 1
        one = types.SimpleNamespace(
            ticket=self.next_ticket, identifier=self.next_ticket,
            symbol=symbol, volume=lot,
            type=TYPE_BUY if buy else TYPE_SELL,
            price_open=price, sl=sl, tp=tp, magic=0, comment="",
            profit=0.0, time=when)
        self.positions[one.ticket] = one
        return one.ticket

    def shut(self, ticket, price, when=1100.0):
        one = self.positions.pop(ticket)
        buy = one.type == TYPE_BUY
        money = round(((price - one.price_open) if buy
                       else (one.price_open - price)) * one.volume * 100, 2)
        self.deals[ticket] = (types.SimpleNamespace(
            entry=1, price=price, profit=money, swap=0.0,
            commission=0.0, time=when),)
        return money

    def history_deals_get(self, position=None, **k):
        return self.deals.get(position, ())

    def copy_rates_from_pos(self, symbol, frame, start, count):
        return self.bars[-count:] if self.bars else None

    def account_info(self):
        return types.SimpleNamespace(
            login=1550318365, server="JustMarkets-Live", balance=1000.0,
            equity=1000.0, margin=0.0, margin_free=1000.0,
            margin_level=0.0, trade_mode=0)

    def order_send(self, request):
        self.sent.append(request)
        return types.SimpleNamespace(retcode=10009, order=1, deal=1,
                                     price=0.0, comment="")


broker = Broker()
fake = types.ModuleType("MetaTrader5")
fake.TIMEFRAME_M1, fake.TIMEFRAME_M5 = 1, 5
fake.POSITION_TYPE_BUY, fake.POSITION_TYPE_SELL = TYPE_BUY, TYPE_SELL
fake.symbol_info_tick = broker.tick
fake.positions_get = broker.positions_get
fake.history_deals_get = broker.history_deals_get
fake.copy_rates_from_pos = broker.copy_rates_from_pos
fake.account_info = broker.account_info
fake.order_send = broker.order_send
fake.initialize = lambda *a, **k: True
fake.shutdown = lambda *a, **k: None
fake.last_error = lambda: (-1, "fake")
sys.modules["MetaTrader5"] = fake
sys.modules["requests"] = types.SimpleNamespace(
    post=lambda *a, **k: types.SimpleNamespace(status_code=200))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(tempfile.mkdtemp())
import mirror as M  # noqa: E402

SYM = "XAUUSD.m"
ok = bad = 0


def check(name, got, want):
    global ok, bad
    if got == want:
        ok += 1
        print(f"  ✅ {name}  ({got})")
    else:
        bad += 1
        print(f"  ❌ {name}\n       المتوقع {want}\n       الناتج  {got}")


def reset(price=3620.0):
    broker.positions.clear()
    broker.deals.clear()
    broker.sent.clear()
    broker.bars = []
    broker.move(price)
    M._rows.clear()
    M._baskets.clear()
    M._after.clear()
    M._tail.clear()
    M._sent.clear()
    M._acct.update({"at": 0.0, "balance": None, "told": 0.0})


def bar(o, h, l, c):
    broker.bars.append({"open": o, "high": h, "low": l, "close": c})


print("═" * 58)
print("  مرآة الحساب — تقرأ ولا تلمس")
print("═" * 58)

print("\n[١] الحارس: أمرُ التنفيذ مرفوضٌ أصلاً")
# مرآةٌ تستطيع التنفيذ ليست مرآة. والحارس في مكانٍ واحد: الدالّة
# نفسها — فلا يبلغ الوسيطَ أمرٌ مهما تغيّرت الشيفرة بعد اليوم.
reset()
M.refuse_orders()
_out = fake.order_send({"action": 1, "symbol": SYM, "volume": 0.05})
check("★ رُفض الأمر", _out.retcode, -1)
check("★ ولم يصل الوسيطَ شيء", broker.sent, [])
check("وسبب الرفض مكتوب", _out.comment, "mirror-only")

print("\n[٢] سلّة 24/11 الساعة 11:21 — ستُّ صفقات تُغلق معاً")
# منقولةٌ حرفياً من سجلّ الحساب: ستُّ بيعاتٍ بـ 0.02 دخلت عند
# 3616.95–3617.04 وأُغلقت كلها عند 3616.18 في الثانية نفسها.
reset(3617.00)
_entries = [3616.98, 3617.04, 3616.99, 3616.95, 3616.97, 3616.98]
_tickets = [broker.open(SYM, False, 0.02, p, sl=0.0, tp=3610.0,
                        when=1000.0 + i * 0.3)
            for i, p in enumerate(_entries)]
M.scan()
check("★ سُجّلت ستُّ صفقات", len(M._rows), 6)
check("★ وكلها سلّةٌ واحدة",
      len({r["basket"] for r in M._rows.values()}), 1)
check("بيعاً", all(not r["buy"] for r in M._rows.values()), True)
check("وهدفُه محفوظ",
      {r["tp"] for r in M._rows.values()}, {3610.0})

# ★ السعر ينزل معه ثم يُغلق قبل هدفه
for _p in (3616.40, 3616.18):
    broker.move(_p)
    M.scan()
_row = M._rows[_tickets[0]]
check("★ ولم يبلغ هدفه", _row["hit_tp"], "")
check("وأقصى ربحٍ مرّ به", _row["best"], 0.60)

# ★ شمعةُ الدقيقة تنقلب ضده (صاعدة في بيع) ثم يُغلق. وآخرُ ما
# يُقرأ من الشموع هي الجارية، والتي قبلها هي آخرُ مكتملة — فهذه
# الأخيرة هي الحَكَم.
bar(3617.0, 3617.2, 3616.1, 3616.2)   # هابطة — معه
bar(3616.2, 3616.6, 3616.1, 3616.5)   # صاعدة — ضده (آخرُ مكتملة)
bar(3616.5, 3616.6, 3616.1, 3616.2)   # الجارية
for _t in _tickets:
    broker.shut(_t, 3616.18, when=1100.0)
M.scan()
check("★ أُغلقت السلّة كلها", len(M._rows), 0)
_say = M._sent[-1]
check("★ وصل تقريرٌ واحد لا ستّة",
      sum("سلّة أُغلقت" in m for m in M._sent), 1)
check("فيه عدد الصفقات", "<b>6</b> صفقة" in _say, True)
check("★ وأنه أغلقها بيده قبل الهدف",
      "أغلقها بيده قبل الهدف" in _say, True)
check("★ وكم بقي على هدفه", "بقي عليه 6.18 درجة" in _say, True)
check("★ وفيه قراءةُ الشموع", "لماذا أغلقها" in _say, True)
check("★ وأن شمعة الدقيقة انقلبت ضده",
      "شمعة الدقيقة انقلبت ضده" in _say, True)

print("\n[٣] ما بعد الإغلاق — أترك ربحاً أم أنقذه خروجه؟")
# ★ السعر يستمرّ في اتجاهه بعد خروجه: خرج مبكراً
_watch = M._after[-1]
check("فُتحت عينٌ على ما بعدها", bool(_watch), True)
check("وسعرُ خروجه محفوظ", _watch["shut_price"], 3616.18)
for _p in (3614.0, 3611.5, 3609.8):
    broker.move(_p)
    M.scan()
check("★ تتبّع ما استمرّ", M._after[-1]["best"], 6.18)
check("★ وبلغ هدفه المتروك", bool(M._after[-1]["tp_hit"]), True)
_watch["at"] -= M.WINDOW_MIN * 60 + 1
M.scan()
_say = M._sent[-1]
check("★ وصل حكمُ ما بعد الإغلاق",
      "ما بعد الإغلاق" in _say, True)
check("★ والحكم: خرج مبكراً", "خرج مبكراً" in _say, True)
check("وكم ترك", "6.18 درجة" in _say, True)
check("وأن هدفه بلغه السوق", "بلغه السوق" in _say, True)

print("\n[٤] وخروجٌ أنقذه: السعر ينعكس بعده")
reset(3620.00)
_t = broker.open(SYM, True, 0.04, 3620.00, sl=3610.0, tp=3640.0,
                 when=2000.0)
M.scan()
broker.move(3621.50)
M.scan()
bar(3620.0, 3621.6, 3619.9, 3621.4)
bar(3621.4, 3621.6, 3620.9, 3621.0)
broker.shut(_t, 3621.50, when=2100.0)
M.scan()
check("أُغلقت", len(M._rows), 0)
for _p in (3618.0, 3614.0, 3611.0):
    broker.move(_p)
    M.scan()
M._after[-1]["at"] -= M.WINDOW_MIN * 60 + 1
M.scan()
_say = M._sent[-1]
check("★ الحكم: خروجه أنقذه", "خروجه أنقذه" in _say, True)
check("★ وكم كان سيخسر", "لو بقي لعكس عليه" in _say, True)
check("ولم يبلغ هدفه المتروك", "لم يبلغه بعد" in _say, True)

print("\n[٥] بلوغُ الهدف وضربُ الوقف يُقرآن على وجههما")
reset(3600.00)
_t = broker.open(SYM, False, 0.02, 3600.00, sl=3610.0, tp=3590.0,
                 when=3000.0)
M.scan()
broker.move(3589.80)
M.scan()
check("★ سُجّل بلوغُ الهدف", bool(M._rows[_t]["hit_tp"]), True)
broker.shut(_t, 3590.00, when=3100.0)
M.scan()
check("★ وسببُ الخروج: بلغت هدفها",
      "بلغت هدفها" in M._sent[-1], True)

reset(3600.00)
_t = broker.open(SYM, True, 0.02, 3600.00, sl=3595.0, tp=3620.0,
                 when=4000.0)
M.scan()
broker.move(3594.80)
M.scan()
check("★ سُجّل بلوغُ الوقف", bool(M._rows[_t]["hit_sl"]), True)
broker.shut(_t, 3595.00, when=4100.0)
M.scan()
check("★ وسببُ الخروج: ضُرب وقفها",
      "ضُرب وقفها" in M._sent[-1], True)

print("\n[٦] نقلُ الوقف أو الهدف بعد الفتح يُسجَّل بوقته")
reset(3600.00)
_t = broker.open(SYM, False, 0.02, 3600.00, sl=3612.0, tp=3590.0,
                 when=5000.0)
M.scan()
broker.positions[_t].sl = 3600.0
M.scan()
check("★ سُجّل النقل", len(M._rows[_t]["moves"]), 1)
check("من 3612 إلى 3600",
      (M._rows[_t]["moves"][0]["was_sl"], M._rows[_t]["moves"][0]["sl"]),
      (3612.0, 3600.0))
broker.shut(_t, 3600.0, when=5100.0)
M.scan()
check("★ والتقرير يذكره", "نقل وقفه أو هدفه" in M._sent[-1], True)

print("\n[٧] الشراء والبيع يُقاسان بالجهة الصحيحة")
# الشراء يُغلق على العرض والبيع على الطلب — وبه يُقاس بلوغُ الرقم
# كما يقيسه الوسيط لا كما نحبّ
reset(3600.00)
broker.spread = 0.40
_t = broker.open(SYM, False, 0.02, 3600.00, sl=0.0, tp=3598.00,
                 when=6000.0)
M.scan()
broker.move(3597.80)          # الطلب 3598.20 — لم يبلغ الهدف بعد
M.scan()
check("★ بيعٌ: العرض وحده لا يكفي", M._rows[_t]["hit_tp"], "")
broker.move(3597.55)          # الطلب 3597.95 — بلغه
M.scan()
check("★ بلغه عند الطلب", bool(M._rows[_t]["hit_tp"]), True)
broker.spread = 0.20

print("\n[٨] مراقبةُ الحساب: ضغطٌ يُنبَّه عنه")
reset(3600.00)
M._acct["balance"] = 1000.0
broker.open(SYM, False, 0.40, 3600.00, when=7000.0)
broker.account_info = lambda: types.SimpleNamespace(
    login=1550318365, server="JustMarkets-Live", balance=1000.0,
    equity=900.0, margin=300.0, margin_free=600.0, margin_level=250.0,
    trade_mode=0)
fake.account_info = broker.account_info
M._acct["at"] = 0.0
M.scan()
check("★ نبّه على الضغط",
      any("تحت ضغط" in m for m in M._sent), True)
check("وفيه العويم", any("-100.00$" in m for m in M._sent), True)
check("وفيه مستوى الهامش",
      any("250%" in m for m in M._sent), True)

print("\n[٩] لحظةُ الدخول تُقرأ كما تُقرأ لحظةُ الخروج")
# صاحب الحساب أراد أن يعرف لماذا يدخل: أبعد شمعةٍ بعينها؟ أعند
# قمّة المدى؟ أعلى رقمٍ مستدير؟ فتُلتقط الوقائعُ عند الفتح.
reset(3600.00)
for _o, _h, _l, _c in (
        (3594, 3595, 3593, 3594.5), (3594.5, 3596, 3594, 3595.8),
        (3595.8, 3597, 3595, 3596.9), (3596.9, 3598, 3596, 3597.8),
        (3597.8, 3600.2, 3597.7, 3600.0),  # جسمٌ كامل — آخرُ مكتملة
        (3600.0, 3600.2, 3599.8, 3599.9)):  # الجارية
    bar(_o, _h, _l, _c)
broker.open(SYM, False, 0.02, 3600.00, tp=3594.0, when=8000.0)
M.scan()
_in = list(M._baskets.values())[-1]["entry"]
check("★ قُرئت لحظة الدخول", bool(_in), True)
check("★ وأن شمعته صاعدة وهو يبيع — عكسها", _in["m1_with"], False)
check("★ وشكلُها", _in["m1_shape"], "جسمٌ كامل")
check("★ وخمسُ شموعٍ صاعدةٍ متتالية", _in["m1_run"], 5)
check("★ ودخل عند قمّة المدى", _in["place"] >= 90, True)
check("★ وعلى رقمٍ مستدير", _in["on_round"], True)
check("وبُعده عنه", _in["to_round"], 0.0)

print("\n[١٠] تقرير الأسبوع: نمطٌ يُعرض، وقلّةٌ لا يُبنى عليها")
# ★ سلّةٌ واحدة لا تصنع استراتيجية — والتقرير يقولها
import json as _json
_day = M.store_file("baskets-2026-11-25.jsonl")
with open(_day, "w", encoding="utf-8") as _fh:
    for _i in range(3):
        _fh.write(_json.dumps({
            "at": "2026-11-25 10:00:00", "why": ["خرج عند قمّة الحركة"],
            "entry": {"mine": "down", "m1_with": False, "m1_shape": "دوجي",
                      "m1_run": 3, "place": 88, "on_round": True,
                      "to_round": 0.1, "hour": 10}}, ensure_ascii=False)
                  + "\n")
_text = M.report_text()
check("★ يحذّر من قلّة العدد", "أقلُّ من خمس سلال" in _text, True)
check("ويعرض الأرقام مع ذلك", "بيع: 3 من 3" in _text, True)

# ★ أما ثمانٍ متشابهة فنمطٌ يُسمّى
with open(_day, "a", encoding="utf-8") as _fh:
    for _i in range(5):
        _fh.write(_json.dumps({
            "at": "2026-11-25 11:00:00",
            "why": ["شمعة الدقيقة انقلبت ضده"],
            "entry": {"mine": "down", "m1_with": False, "m1_shape": "دوجي",
                      "m1_run": 4, "place": 92, "on_round": True,
                      "to_round": 0.2, "hour": 11}}, ensure_ascii=False)
                  + "\n")
_text = M.report_text()
check("★ لم يعد يحذّر", "أقلُّ من خمس سلال" in _text, False)
check("★ ويقول إنه يدخل عكس الشمعة",
      "يدخل عكس الشمعة" in _text, True)
check("★ وإنه يدخل عند القمم", "يدخل عند القمم" in _text, True)
check("★ وعلى الأرقام المستديرة",
      "يدخل على الأرقام المستديرة" in _text, True)
check("★ وأكثرُ دخولاته بعد دوجي",
      "أكثرُ دخولاته بعد «دوجي»" in _text, True)
check("ومتوسط الشموع المتتالية", "3.6</b> شمعة" in _text, True)
check("★ وما يسبق خروجه",
      "شمعة الدقيقة انقلبت ضده: 5 من 8" in _text, True)

# ★ وخليطٌ بلا نمط لا يُسمّى نمطاً
with open(_day, "w", encoding="utf-8") as _fh:
    for _i in range(8):
        _fh.write(_json.dumps({
            "at": "2026-11-25 12:00:00", "why": [],
            "entry": {"mine": "up" if _i % 2 else "down",
                      "m1_with": bool(_i % 2), "m1_shape": "شمعةٌ عادية",
                      "m1_run": _i, "place": 10 + _i * 10,
                      "on_round": bool(_i % 2), "to_round": 0.4,
                      "hour": 9 + _i}}, ensure_ascii=False) + "\n")
_text = M.report_text()
check("★ خليطٌ لا يُسمّى نمطاً",
      any(w in _text for w in ("يدخل عكس الشمعة", "يدخل عند القمم",
                               "يدخل على الأرقام المستديرة")), False)
check("لكنّ الأرقام تُعرض", "موضع دخوله" in _text, True)

print("\n[١١] لا أمرَ واحد خرج في كل ما سبق")
check("★ الوسيط لم يستقبل شيئاً", broker.sent, [])

print(f"\n{'─' * 58}\nنجح: {ok} | فشل: {bad}\n")
sys.exit(1 if bad else 0)
