"""أنواع بيانات الشموع ومصادرها."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, List, Optional, Sequence


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_top(self) -> float:
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        return self.high - self.body_top

    @property
    def lower_wick(self) -> float:
        return self.body_bottom - self.low


class Series:
    """سلسلة شموع لإطار زمني واحد، مرتبة تصاعديًا بالزمن."""

    def __init__(self, timeframe: str, candles: Sequence[Candle], symbol: str = "XAUUSD.m"):
        self.timeframe = timeframe
        self.symbol = symbol
        self._candles: List[Candle] = list(candles)
        self._validate()

    def _validate(self) -> None:
        for i, c in enumerate(self._candles):
            if not (c.low <= c.open <= c.high and c.low <= c.close <= c.high):
                raise ValueError(f"شمعة غير صالحة عند {i} ({c.time}): OHLC غير متسق")
        times = [c.time for c in self._candles]
        if times != sorted(times):
            raise ValueError("الشموع غير مرتبة زمنيًا تصاعديًا")

    # ── وصول ──
    def __len__(self) -> int:
        return len(self._candles)

    def __getitem__(self, i):
        if isinstance(i, slice):
            return Series(self.timeframe, self._candles[i], self.symbol)
        return self._candles[i]

    def __iter__(self) -> Iterator[Candle]:
        return iter(self._candles)

    @property
    def candles(self) -> List[Candle]:
        return list(self._candles)

    def highs(self) -> List[float]:
        return [c.high for c in self._candles]

    def lows(self) -> List[float]:
        return [c.low for c in self._candles]

    def closes(self) -> List[float]:
        return [c.close for c in self._candles]

    def last_closed(self) -> Optional[Candle]:
        """آخر شمعة مغلقة. الانحياز اليومي لا يُقرأ إلا بعد الإغلاق (Lesson 14)."""
        return self._candles[-1] if self._candles else None

    # ── تحميل ──
    @classmethod
    def from_csv(cls, path: str, timeframe: str, symbol: str = "XAUUSD.m") -> "Series":
        """CSV بأعمدة: time,open,high,low,close[,volume] — الوقت ISO-8601."""
        out: List[Candle] = []
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                out.append(
                    Candle(
                        time=datetime.fromisoformat(row["time"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume") or 0.0),
                    )
                )
        return cls(timeframe, out, symbol)


class MT5Source:
    """
    واجهة مصدر MT5 الحي.

    غير مفعّلة في هذه البيئة (لينكس بلا طرفية MT5). مكتبة MetaTrader5
    الرسمية تعمل على ويندوز فقط، ولذلك تُترك الواجهة معرّفة والتنفيذ مؤجَّلًا
    حتى يُحدَّد مكان تشغيل الطرفية.

    ملاحظة تصميمية مهمة: البوت يقرأ الأرقام من فيد الوسيط الذي سينفّذ عليه،
    لا من شارت مزوّد آخر — وهذا ما يتفادى التعارض C4 (اختلاف الذيول بين المزوّدين).
    """

    def __init__(self, symbol: str = "XAUUSD.m"):
        self.symbol = symbol

    def fetch(self, timeframe: str, count: int) -> Series:
        raise NotImplementedError(
            "مصدر MT5 غير موصول بعد.\n"
            "يلزم: طرفية MT5 تعمل + حزمة MetaTrader5 (ويندوز)، "
            "أو جسر عبر Expert Advisor.\n"
            "للتطوير والاختبار استعمل Series.from_csv()."
        )
