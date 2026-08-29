"""
اختبارات جسر MT5.

مكتبة MetaTrader5 تعمل على ويندوز فقط، فالجسر يستقبل الطرفية حقنًا
وتُمرَّر هنا طرفية زائفة. وبهذا يُختبَر كل مسار المنطق بلا طرفية.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from bot.mt5_bridge import (
    FORBIDDEN_CALLS,
    BridgeConfig,
    BridgeError,
    DataGap,
    MT5Bridge,
    NotConnected,
    find_gaps,
)
from bot.data import Candle, Series
from bot import local_config

EPOCH = int(datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc).timestamp())


def row(offset_min, o, h, l, c, tick_volume=100, real_volume=0):
    """صفّ كما تعيده الطرفية — بالوصول بالاسم."""
    return {
        "time": EPOCH + offset_min * 60,
        "open": o, "high": h, "low": l, "close": c,
        "tick_volume": tick_volume,
        "real_volume": real_volume,
        "spread": 20,
    }


class Tick:
    def __init__(self, bid=4360.0, ask=4360.30, time=EPOCH):
        self.bid, self.ask, self.time = bid, ask, time


class Info:
    def __init__(self, digits=2):
        self.digits = digits


class Position:
    def __init__(self, ticket=1, type_=0, volume=0.01, price_open=4360.0,
                 sl=4358.0, tp=4366.0, time=EPOCH):
        self.ticket, self.type, self.volume = ticket, type_, volume
        self.price_open, self.sl, self.tp, self.time = price_open, sl, tp, time


class FakeTerminal:
    """طرفية زائفة — تحاكي ما نستعمله من واجهة MetaTrader5 فقط."""

    TIMEFRAME_M1 = 1
    TIMEFRAME_M3 = 3
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388
    TIMEFRAME_D1 = 16408
    TIMEFRAME_W1 = 32769

    def __init__(self, rows=None, symbol_known=True, init_ok=True,
                 tick=None, positions=()):
        self.rows = rows if rows is not None else [
            row(i * 15, 100 + i, 105 + i, 95 + i, 102 + i) for i in range(6)
        ]
        self.symbol_known = symbol_known
        self.init_ok = init_ok
        self._tick = tick if tick is not None else Tick()
        self._positions = list(positions)
        self.init_kwargs = None
        self.shutdown_calls = 0

    def initialize(self, **kw):
        self.init_kwargs = kw
        return self.init_ok

    def shutdown(self):
        self.shutdown_calls += 1

    def last_error(self):
        return (-1, "خطأ زائف")

    def symbol_info(self, symbol):
        return Info() if self.symbol_known else None

    def symbol_info_tick(self, symbol):
        return self._tick

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        return self.rows[-count:] if count else self.rows

    def positions_get(self, symbol=None):
        return self._positions


def bridge(**kw) -> MT5Bridge:
    t = FakeTerminal(**kw)
    b = MT5Bridge(t, BridgeConfig(symbol="XAUUSD.m"))
    b.connect()
    return b


# ─────────────────────────── حاجز التنفيذ ───────────────────────────


class TestReadOnly(unittest.TestCase):
    """⛔ الجسر يقرأ ولا يأمر — والمنع في الكود لا في التوثيق."""

    def test_bridge_exposes_no_execution_method(self):
        b = MT5Bridge(FakeTerminal())
        for name in FORBIDDEN_CALLS:
            with self.subTest(name=name):
                self.assertFalse(hasattr(b, name), name)

    def test_no_execution_word_in_the_module_source(self):
        """حارس ضد تسلّل دالة تنفيذ لاحقًا."""
        import bot.mt5_bridge as m
        with open(m.__file__, encoding="utf-8") as fh:
            src = fh.read()
        # الاسم مذكور في قائمة المنع وفي الاختبار فقط — لا كاستدعاء
        self.assertNotIn("order_send(", src)
        self.assertNotIn(".order_send", src)


# ─────────────────────────── الاتصال ───────────────────────────


class TestConnection(unittest.TestCase):
    def test_failed_initialize_raises(self):
        b = MT5Bridge(FakeTerminal(init_ok=False))
        with self.assertRaises(NotConnected):
            b.connect()

    def test_unknown_symbol_raises_and_closes_the_terminal(self):
        t = FakeTerminal(symbol_known=False)
        b = MT5Bridge(t, BridgeConfig(symbol="XAUUSD.wrong"))
        with self.assertRaises(BridgeError) as cm:
            b.connect()
        self.assertIn("Market Watch", str(cm.exception))
        self.assertEqual(t.shutdown_calls, 1)      # لا يُترك مفتوحًا

    def test_reading_before_connect_raises(self):
        b = MT5Bridge(FakeTerminal())
        with self.assertRaises(NotConnected):
            b.fetch("M15", 3)

    def test_credentials_are_passed_and_not_stored(self):
        """⚠️ كلمة السرّ لا تبقى على الكائن — تُسرَّب في السجل لو بقيت."""
        t = FakeTerminal()
        b = MT5Bridge(t)
        b.connect(path="C:/mt5.exe", login=123, password="s3cret")
        self.assertEqual(t.init_kwargs["password"], "s3cret")
        self.assertNotIn("s3cret", repr(vars(b)))

    def test_context_manager_shuts_down(self):
        t = FakeTerminal()
        b = MT5Bridge(t)
        b.connect()
        with b:
            pass
        self.assertEqual(t.shutdown_calls, 1)


# ─────────────────────────── الشموع ───────────────────────────


class TestFetch(unittest.TestCase):
    """⭐ الشمعة قيد التكوّن — أخطر مزلق في الجسر كله."""

    def test_forming_candle_is_dropped(self):
        b = bridge()
        s = b.fetch("M15", 3)
        self.assertEqual(len(s), 3)
        # الصفوف 0..5 · تُحذف الأخيرة ⇒ آخر شمعة هي صفّ 4
        self.assertAlmostEqual(s[-1].close, 106.0)

    def test_requesting_n_returns_n_closed_candles(self):
        """يُطلب n+1 ثم تُسقَط الأخيرة — فلا يعود العدد ناقصًا واحدًا."""
        for n in (1, 2, 5):
            with self.subTest(n=n):
                self.assertEqual(len(bridge().fetch("M15", n)), n)

    def test_keeping_the_forming_candle_is_opt_in(self):
        t = FakeTerminal()
        b = MT5Bridge(t, BridgeConfig(drop_forming_candle=False))
        b.connect()
        self.assertAlmostEqual(b.fetch("M15", 3)[-1].close, 107.0)

    def test_volume_comes_from_tick_volume(self):
        """الذهب بلا حجم حقيقي — real_volume صفر عند أغلب الوسطاء."""
        rows = [row(i * 15, 100, 105, 95, 102, tick_volume=77, real_volume=0)
                for i in range(4)]
        t = FakeTerminal(rows=rows)
        b = MT5Bridge(t)
        b.connect()
        self.assertAlmostEqual(b.fetch("M15", 2)[0].volume, 77.0)

    def test_candles_are_sorted_by_time(self):
        rows = [row(45, 100, 105, 95, 102), row(0, 90, 95, 85, 92),
                row(15, 95, 100, 90, 97), row(30, 97, 102, 92, 99)]
        t = FakeTerminal(rows=rows)
        b = MT5Bridge(t)
        b.connect()
        times = [c.time for c in b.fetch("M15", 3)]
        self.assertEqual(times, sorted(times))

    def test_unsupported_timeframe_rejected(self):
        with self.assertRaises(BridgeError):
            bridge().fetch("M7", 3)

    def test_zero_count_rejected(self):
        with self.assertRaises(BridgeError):
            bridge().fetch("M15", 0)

    def test_empty_response_raises_rather_than_returning_nothing(self):
        t = FakeTerminal(rows=[])
        b = MT5Bridge(t)
        b.connect()
        with self.assertRaises(BridgeError):
            b.fetch("M15", 3)

    def test_single_row_leaves_nothing_after_dropping(self):
        t = FakeTerminal(rows=[row(0, 100, 105, 95, 102)])
        b = MT5Bridge(t)
        b.connect()
        with self.assertRaises(BridgeError) as cm:
            b.fetch("M15", 1)
        self.assertIn("قيد التكوّن", str(cm.exception))

    def test_series_carries_symbol_and_timeframe(self):
        s = bridge().fetch("M15", 2)
        self.assertEqual(s.symbol, "XAUUSD.m")
        self.assertEqual(s.timeframe, "M15")


# ─────────────────────────── الوقت ───────────────────────────


class TestServerTime(unittest.TestCase):
    """⚠️ الإزاحة الخاطئة تزيح كل قاعدة زمنية ساعاتٍ كاملة."""

    def test_offset_is_applied_to_utc(self):
        b = MT5Bridge(FakeTerminal(), BridgeConfig(server_utc_offset_hours=3))
        server = datetime(2026, 8, 27, 21, 0)
        self.assertEqual(b.to_utc(server), datetime(2026, 8, 27, 18, 0))

    def test_measured_offset_rounds_to_half_hours(self):
        future = int((datetime.now(timezone.utc) + timedelta(hours=2, minutes=58)).timestamp())
        t = FakeTerminal(tick=Tick(time=future))
        b = MT5Bridge(t)
        b.connect()
        self.assertAlmostEqual(b.measure_server_offset(), 3.0)

    def test_zero_offset_is_measured_as_zero(self):
        now = int(datetime.now(timezone.utc).timestamp())
        t = FakeTerminal(tick=Tick(time=now))
        b = MT5Bridge(t)
        b.connect()
        self.assertAlmostEqual(b.measure_server_offset(), 0.0)


# ─────────────────────────── السبريد ───────────────────────────


class TestSpread(unittest.TestCase):
    def test_spread_is_ask_minus_bid_in_price_units(self):
        t = FakeTerminal(tick=Tick(bid=4360.0, ask=4360.35))
        b = MT5Bridge(t)
        b.connect()
        self.assertAlmostEqual(b.spread(), 0.35, places=6)

    def test_negative_spread_is_rejected_as_corrupt(self):
        t = FakeTerminal(tick=Tick(bid=4360.5, ask=4360.0))
        b = MT5Bridge(t)
        b.connect()
        with self.assertRaises(BridgeError):
            b.spread()

    def test_digits(self):
        self.assertEqual(bridge().symbol_digits(), 2)


# ─────────────────────────── الفجوات ───────────────────────────


class TestGaps(unittest.TestCase):
    """`detect_data_gaps` من متطلبات الصمود المسجَّلة."""

    def _series(self, minutes):
        base = datetime(2026, 8, 27, 9, 0)
        return Series("M15", [
            Candle(base + timedelta(minutes=m), 100, 101, 99, 100) for m in minutes
        ])

    def test_continuous_series_has_no_gaps(self):
        self.assertEqual(find_gaps(self._series([0, 15, 30, 45]), "M15"), [])

    def test_missing_bar_is_found(self):
        gaps = find_gaps(self._series([0, 15, 45]), "M15")
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].missing_bars, 1)

    def test_gap_size_is_counted(self):
        gaps = find_gaps(self._series([0, 15, 120]), "M15")
        self.assertEqual(gaps[0].missing_bars, 6)

    def test_tolerance_suppresses_small_gaps(self):
        self.assertEqual(find_gaps(self._series([0, 15, 45]), "M15", tolerance=2), [])

    def test_unknown_timeframe_rejected(self):
        with self.assertRaises(BridgeError):
            find_gaps(self._series([0, 15]), "M7")

    def test_invalid_tolerance_rejected(self):
        with self.assertRaises(BridgeError):
            find_gaps(self._series([0, 15]), "M15", tolerance=0)

    def test_render_is_readable(self):
        g = DataGap(datetime(2026, 8, 27, 9, 0), datetime(2026, 8, 27, 10, 0), 3)
        self.assertIn("3 شمعة", g.render())


# ─────────────────────────── المراكز ───────────────────────────


class TestPositions(unittest.TestCase):
    def test_no_positions(self):
        self.assertEqual(bridge().open_positions(), [])

    def test_position_is_mapped(self):
        t = FakeTerminal(positions=[Position(ticket=42, type_=1)])
        b = MT5Bridge(t)
        b.connect()
        p = b.open_positions()[0]
        self.assertEqual(p["ticket"], 42)
        self.assertEqual(p["type"], "sell")
        self.assertAlmostEqual(p["volume"], 0.01)


# ─────────────────────────── النبضة ───────────────────────────


class TestHealth(unittest.TestCase):
    def test_healthy_bridge(self):
        h = bridge().health("M15", count=4)
        self.assertTrue(h.healthy)
        self.assertEqual(h.bars, 4)
        self.assertIn("✅", h.render())

    def test_gaps_make_it_unhealthy(self):
        rows = [row(0, 100, 105, 95, 102), row(15, 101, 106, 96, 103),
                row(75, 102, 107, 97, 104), row(90, 103, 108, 98, 105)]
        t = FakeTerminal(rows=rows)
        b = MT5Bridge(t)
        b.connect()
        h = b.health("M15", count=3)
        self.assertFalse(h.healthy)
        self.assertIn("⚠️", h.render())

    def test_health_reads_data_not_just_connection_state(self):
        """طرفية «متصلة» ببيانات متوقّفة حالة واقعية — يكشفها آخر ختم."""
        h = bridge().health("M15", count=4)
        self.assertIsNotNone(h.last_bar_time)

    def test_health_includes_spread(self):
        self.assertAlmostEqual(bridge().health("M15", 4).spread, 0.30, places=6)


# ─────────────────────────── الإعدادات المحلية ───────────────────────────


class TestLocalConfig(unittest.TestCase):
    """⚠️ لا بيانات اعتماد في المستودع — ولا في رسائل الخطأ."""

    def _write(self, body):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "config.local.py")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
        return p

    def test_missing_file_explains_how_to_create_it(self):
        with self.assertRaises(local_config.ConfigMissing) as cm:
            local_config.load("/nonexistent/config.local.py")
        self.assertIn("config.local.example.py", str(cm.exception))

    def test_only_uppercase_names_are_read(self):
        p = self._write('MT5_PATH = "C:/x.exe"\nhelper = 1\n')
        s = local_config.load(p)
        self.assertIn("MT5_PATH", s)
        self.assertNotIn("helper", s)

    def test_path_alone_is_enough(self):
        creds = local_config.mt5_credentials({"MT5_PATH": "C:/x.exe"})
        self.assertEqual(creds, {"path": "C:/x.exe"})

    def test_login_is_coerced_to_int(self):
        creds = local_config.mt5_credentials(
            {"MT5_PATH": "C:/x.exe", "MT5_LOGIN": "12345", "MT5_PASSWORD": "p"}
        )
        self.assertEqual(creds["login"], 12345)

    def test_missing_path_is_named(self):
        with self.assertRaises(local_config.ConfigMissing) as cm:
            local_config.mt5_credentials({})
        self.assertIn("MT5_PATH", str(cm.exception))

    def test_describe_never_reveals_a_secret(self):
        s = {"MT5_PATH": "C:/x.exe", "MT5_PASSWORD": "s3cret", "MT5_LOGIN": "999"}
        out = local_config.describe(s).render()
        self.assertNotIn("s3cret", out)
        self.assertNotIn("999", out)
        self.assertIn("محجوبة", out)

    def test_describe_reports_readiness(self):
        self.assertTrue(local_config.describe({"MT5_PATH": "x"}).ready)
        self.assertFalse(local_config.describe({}).ready)

    def test_redact_hides_secrets_but_keeps_shape(self):
        r = local_config.redact({"MT5_PATH": "C:/x.exe", "MT5_PASSWORD": "s3cret"})
        self.assertEqual(r["MT5_PATH"], "C:/x.exe")
        self.assertEqual(r["MT5_PASSWORD"], "•••")

    def test_empty_secret_is_not_masked_into_looking_present(self):
        self.assertEqual(local_config.redact({"MT5_PASSWORD": ""})["MT5_PASSWORD"], "")


class TestExampleTemplateIsSafe(unittest.TestCase):
    """القالب مرفوع — فيجب أن يبقى فارغًا من كل قيمة."""

    def test_template_has_no_real_values(self):
        path = os.path.join(local_config.project_root(), "config.local.example.py")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        for key in ("MT5_LOGIN", "MT5_PASSWORD", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"):
            with self.subTest(key=key):
                self.assertIn(f'{key} = ""', src)

    def test_gitignore_blocks_the_real_file(self):
        path = os.path.join(local_config.project_root(), ".gitignore")
        with open(path, encoding="utf-8") as fh:
            self.assertIn("config.local.py", fh.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
