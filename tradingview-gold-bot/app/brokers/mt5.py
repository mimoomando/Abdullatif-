"""
وسيط ميتاتريدر ٥ — هنا تُفتح الصفقة فعلاً على حساب جست ماركتس.

الحزمة ``MetaTrader5`` تعمل على ويندوز وحده وتكلّم نافذة الميتاتريدر
المفتوحة على الجهاز نفسه. فتُستورد عند الاتصال لا عند تحميل الملف،
ليبقى باقي البريدج قابلاً للتشغيل والاختبار على أي نظام.
"""

from app.brokers.base import Broker, BrokerError, Position, SymbolInfo

# رموز الأمر كما تعرّفها الحزمة. تُملأ عند الاتصال.
_mt5 = None


def _load():
    global _mt5
    if _mt5 is None:
        try:
            import MetaTrader5  # noqa: N813
        except ImportError as exc:
            raise BrokerError(
                "حزمة MetaTrader5 غير موجودة. تعمل على ويندوز وحده، "
                "وتُثبَّت بـ pip install MetaTrader5."
            ) from exc
        _mt5 = MetaTrader5
    return _mt5


class MT5Broker(Broker):
    name = "mt5"

    def __init__(self, login=0, password="", server="", path="",
                 slippage_points=30, magic=0):
        self.login = int(login or 0)
        self.password = password
        self.server = server
        self.path = path
        self.slippage_points = int(slippage_points)
        self.magic = int(magic)
        self._connected = False

    # ── الاتصال ──

    def connect(self):
        mt5 = _load()
        kwargs = {}
        if self.path:
            kwargs["path"] = self.path
        if self.login:
            kwargs.update(login=self.login, password=self.password, server=self.server)

        if not mt5.initialize(**kwargs):
            raise BrokerError(f"تعذّر الاتصال بالميتاتريدر: {mt5.last_error()}")

        account = mt5.account_info()
        if account is None:
            mt5.shutdown()
            raise BrokerError(f"تعذّرت قراءة الحساب: {mt5.last_error()}")
        if not account.trade_allowed:
            mt5.shutdown()
            raise BrokerError(
                "التداول ممنوع على هذا الحساب أو في هذه النافذة. "
                "فعّل AutoTrading في الميتاتريدر."
            )
        self._connected = True
        return account

    def shutdown(self):
        if self._connected and _mt5 is not None:
            _mt5.shutdown()
            self._connected = False

    def _mt(self):
        if not self._connected:
            raise BrokerError("لا اتصال بالميتاتريدر.")
        return _load()

    # ── القراءة ──

    def balance(self):
        mt5 = self._mt()
        account = mt5.account_info()
        if account is None:
            raise BrokerError(f"تعذّرت قراءة الرصيد: {mt5.last_error()}")
        return float(account.balance)

    def symbol_info(self, symbol):
        mt5 = self._mt()
        raw = mt5.symbol_info(symbol)
        if raw is None:
            raise BrokerError(
                f"الرمز {symbol} غير موجود عند الوسيط. "
                "راجع اسمه في نافذة Market Watch وصحّح SYMBOL."
            )
        if not raw.visible and not mt5.symbol_select(symbol, True):
            raise BrokerError(f"تعذّر إظهار الرمز {symbol} في Market Watch.")
        raw = mt5.symbol_info(symbol)

        tick_size = float(raw.trade_tick_size or raw.point or 0.0)
        tick_value = float(raw.trade_tick_value or 0.0)
        if tick_size <= 0 or tick_value <= 0:
            raise BrokerError(
                f"بيانات الرمز {symbol} ناقصة: قيمة الدرجة غير معروفة."
            )

        point = float(raw.point or 0.0)
        return SymbolInfo(
            name=raw.name,
            digits=int(raw.digits),
            point=point,
            volume_min=float(raw.volume_min),
            volume_step=float(raw.volume_step),
            volume_max=float(raw.volume_max),
            value_per_price_unit=tick_value / tick_size,
            stops_distance=float(raw.trade_stops_level or 0) * point,
            bid=float(raw.bid),
            ask=float(raw.ask),
        )

    def positions(self, symbol=None, magic=None):
        mt5 = self._mt()
        raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if raw is None:
            return []
        found = []
        for item in raw:
            if magic is not None and int(item.magic) != int(magic):
                continue
            found.append(Position(
                ticket=int(item.ticket),
                symbol=item.symbol,
                side="buy" if item.type == mt5.POSITION_TYPE_BUY else "sell",
                volume=float(item.volume),
                price_open=float(item.price_open),
                sl=float(item.sl),
                tp=float(item.tp),
                profit=float(item.profit),
                magic=int(item.magic),
                comment=item.comment,
            ))
        return found

    def position_by_ticket(self, ticket):
        for position in self.positions():
            if position.ticket == int(ticket):
                return position
        return None

    # ── التنفيذ ──

    def market_order(self, symbol, side, lot, sl=None, tp=None, comment="", magic=0):
        mt5 = self._mt()
        info = self.symbol_info(symbol)
        price = info.entry_price(side)
        if not price:
            raise BrokerError(f"لا سعر حيّ للرمز {symbol}.")

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": self.slippage_points,
            "magic": int(magic or self.magic),
            "comment": comment[:31],   # الميتاتريدر يقطع ما زاد
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(symbol),
        }
        if sl:
            request["sl"] = round(float(sl), info.digits)
        if tp:
            request["tp"] = round(float(tp), info.digits)

        result = self._send(request, "فتح صفقة")
        ticket = int(getattr(result, "order", 0) or 0)
        position = self.position_by_ticket(ticket) if ticket else None
        if position:
            return position

        # الصفقة نُفّذت ولم تُقرأ بعد: نعيد ما تعرفه نتيجة الأمر
        return Position(
            ticket=ticket,
            symbol=symbol,
            side=side,
            volume=float(getattr(result, "volume", lot) or lot),
            price_open=float(getattr(result, "price", price) or price),
            sl=float(request.get("sl", 0.0)),
            tp=float(request.get("tp", 0.0)),
            magic=int(request["magic"]),
            comment=comment,
        )

    def modify(self, position, sl=None, tp=None):
        mt5 = self._mt()
        info = self.symbol_info(position.symbol)
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": int(position.ticket),
            "sl": round(float(sl), info.digits) if sl else float(position.sl or 0.0),
            "tp": round(float(tp), info.digits) if tp else float(position.tp or 0.0),
        }
        self._send(request, "تعديل الوقف والهدف")
        return self.position_by_ticket(position.ticket) or position

    def close(self, position, volume=None):
        mt5 = self._mt()
        info = self.symbol_info(position.symbol)
        closing = "sell" if position.is_buy else "buy"
        price = info.entry_price(closing)
        amount = float(volume or position.volume)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": amount,
            "type": mt5.ORDER_TYPE_SELL if position.is_buy else mt5.ORDER_TYPE_BUY,
            "position": int(position.ticket),
            "price": price,
            "deviation": self.slippage_points,
            "magic": int(position.magic or self.magic),
            "comment": "إغلاق"[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(position.symbol),
        }
        self._send(request, "إغلاق صفقة")
        return position

    # ── تفاصيل الوسيط ──

    def _filling_mode(self, symbol):
        """
        نمط التعبئة الذي يقبله هذا الرمز عند هذا الوسيط.

        اختيار نمط لا يدعمه الرمز يُرجع الخطأ 10030، وهو أشهر سبب
        لرفض أمر سليم في كل شيء آخر.
        """
        mt5 = self._mt()
        raw = mt5.symbol_info(symbol)
        modes = int(getattr(raw, "filling_mode", 0) or 0)
        if modes & 1:                     # SYMBOL_FILLING_FOK
            return mt5.ORDER_FILLING_FOK
        if modes & 2:                     # SYMBOL_FILLING_IOC
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def _send(self, request, what):
        mt5 = self._mt()
        result = mt5.order_send(request)
        if result is None:
            raise BrokerError(f"{what}: لا ردّ من الميتاتريدر {mt5.last_error()}")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise BrokerError(
                f"{what}: رفضه الوسيط برمز {result.retcode} — {result.comment}"
            )
        return result
