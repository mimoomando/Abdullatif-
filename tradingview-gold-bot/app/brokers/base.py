"""
الواجهة التي يكلّم بها البريدج أي وسيط.

فوقها اثنان: وسيط ورقي يحاكي التنفيذ دون مال، وميتاتريدر يفتح
الصفقة فعلاً. ومن ورائهما لا يعرف باقي البريدج أيّهما يعمل، فيُجرَّب
كل شيء على الورقي ثم يُنقل إلى الحقيقي بتبديل سطر واحد.
"""

from dataclasses import dataclass


class BrokerError(RuntimeError):
    """الوسيط رفض الأمر أو تعذّر الوصول إليه."""


@dataclass
class SymbolInfo:
    name: str
    digits: int = 2
    point: float = 0.01
    volume_min: float = 0.01
    volume_step: float = 0.01
    volume_max: float = 100.0
    # قيمة تحرّك السعر درجة واحدة للوت الواحد بالدولار
    value_per_price_unit: float = 100.0
    # أقل بُعد يقبله الوسيط بين السعر والوقف، بسعر الأداة
    stops_distance: float = 0.0
    bid: float = 0.0
    ask: float = 0.0

    def entry_price(self, side):
        """السعر الذي يُنفَّذ عنده الدخول: الطلب شراءً والعرض بيعاً."""
        return self.ask if side == "buy" else self.bid


@dataclass
class Position:
    ticket: int
    symbol: str
    side: str
    volume: float
    price_open: float
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0
    magic: int = 0
    comment: str = ""

    @property
    def is_buy(self):
        return self.side == "buy"


class Broker:
    """ما يجب أن يقدر عليه كل وسيط."""

    name = "broker"

    def connect(self):
        raise NotImplementedError

    def shutdown(self):
        pass

    def balance(self):
        raise NotImplementedError

    def symbol_info(self, symbol):
        raise NotImplementedError

    def positions(self, symbol=None, magic=None):
        raise NotImplementedError

    def quote_time(self, symbol):
        """
        زمن آخر سعر وصل من الوسيط لهذا الرمز، أو لا شيء إن لم يُعرف.

        به يفرّق حارس الصمت بين سوق مقفل — فالأسعار متجمدة — وبين
        تنبيهات انقطعت والسوق يتحرك. ومن لا يعرفه يعيد لا شيء،
        فيُحمل الأمر على أن السوق مفتوح ويُنبَّه.
        """
        return None

    def market_order(self, symbol, side, lot, sl=None, tp=None, comment="", magic=0):
        """يفتح صفقة سوقية ويعيدها بسعر تنفيذها الفعلي."""
        raise NotImplementedError

    def modify(self, position, sl=None, tp=None):
        raise NotImplementedError

    def close(self, position, volume=None):
        """يغلق الصفقة كلها، أو جزءاً منها إن مُرّر حجم."""
        raise NotImplementedError


def opposite(side):
    return "sell" if side == "buy" else "buy"
