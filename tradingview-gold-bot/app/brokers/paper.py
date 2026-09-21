"""
وسيط ورقي: ينفّذ كل شيء في الذاكرة ولا يمسّ مالاً.

به يُجرَّب الطريق كاملاً — من رسالة التنبيه إلى حساب الوقف والهدف
وإدارة الصفقة — قبل أن تُفتح صفقة واحدة بمال حقيقي.
"""

import itertools
import time

from app.brokers.base import Broker, BrokerError, Position, SymbolInfo


class PaperBroker(Broker):
    name = "paper"

    def __init__(self, balance=10000.0, spread=0.30, symbol_defaults=None):
        self._balance = balance
        self._spread = spread
        self._positions = {}
        self._prices = {}
        self._quote_times = {}
        self._tickets = itertools.count(1)
        self._defaults = symbol_defaults or {}

    # ── حالة السوق المحاكاة ──

    def set_price(self, symbol, price):
        """سعر يُحاكى عنده التنفيذ. يضعه البريدج من سعر التنبيه."""
        self._prices[symbol] = float(price)
        self._quote_times[symbol] = time.time()

    def quote_time(self, symbol):
        return self._quote_times.get(symbol)

    def last_price(self, symbol):
        price = self._prices.get(symbol)
        if not price:
            raise BrokerError(
                f"لا سعر محفوظاً للرمز {symbol}: ضع سعراً قبل التنفيذ الورقي."
            )
        return price

    # ── الواجهة ──

    def connect(self):
        return True

    def balance(self):
        return self._balance

    def symbol_info(self, symbol):
        info = SymbolInfo(name=symbol, **self._defaults.get(symbol, {}))
        price = self._prices.get(symbol, 0.0)
        if price:
            info.bid = round(price - self._spread / 2, info.digits)
            info.ask = round(price + self._spread / 2, info.digits)
        return info

    def positions(self, symbol=None, magic=None):
        found = list(self._positions.values())
        if symbol:
            found = [p for p in found if p.symbol == symbol]
        if magic is not None:
            found = [p for p in found if p.magic == magic]
        return found

    def market_order(self, symbol, side, lot, sl=None, tp=None, comment="", magic=0):
        info = self.symbol_info(symbol)
        fill = info.entry_price(side)
        if not fill:
            raise BrokerError(f"لا سعر للرمز {symbol}.")
        position = Position(
            ticket=next(self._tickets),
            symbol=symbol,
            side=side,
            volume=lot,
            price_open=fill,
            sl=round(sl, info.digits) if sl else 0.0,
            tp=round(tp, info.digits) if tp else 0.0,
            magic=magic,
            comment=comment,
        )
        self._positions[position.ticket] = position
        return position

    def modify(self, position, sl=None, tp=None):
        stored = self._positions.get(position.ticket)
        if not stored:
            raise BrokerError(f"لا صفقة بالرقم {position.ticket}.")
        info = self.symbol_info(stored.symbol)
        if sl is not None:
            stored.sl = round(sl, info.digits)
        if tp is not None:
            stored.tp = round(tp, info.digits)
        return stored

    def close(self, position, volume=None):
        stored = self._positions.get(position.ticket)
        if not stored:
            raise BrokerError(f"لا صفقة بالرقم {position.ticket}.")
        if volume is None or volume >= stored.volume:
            return self._positions.pop(position.ticket)
        stored.volume = round(stored.volume - volume, 8)
        closed = Position(
            ticket=stored.ticket,
            symbol=stored.symbol,
            side=stored.side,
            volume=volume,
            price_open=stored.price_open,
            sl=stored.sl,
            tp=stored.tp,
            magic=stored.magic,
            comment="إغلاق جزئي",
        )
        return closed
