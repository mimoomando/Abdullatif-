"""
اختبارات رسم الشارت.

⚠️ الرسم **مخرَج** لا مصدر. هذه الاختبارات تتحقق من أن الصورة تمثّل
الأرقام بأمانة — لا من أن الأرقام صحيحة، فذلك شأن البدائيات.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle
from bot.render import Level, Marker, Scene, Zone, legend, render_svg, write_svg

T0 = datetime(2026, 8, 27, 9, 0)


def candles(*rows):
    return [
        Candle(T0 + timedelta(minutes=5 * i), o, h, l, c)
        for i, (o, h, l, c) in enumerate(rows)
    ]


ROWS = (
    (100, 104,  98, 103),
    (103, 108, 102, 107),
    (107, 107,  99, 100),
    (100, 106,  99, 105),
    (105, 112, 104, 111),
)


def scene(**kw) -> Scene:
    base = dict(candles=candles(*ROWS), timeframe="M5", symbol="XAUUSD.m")
    base.update(kw)
    return Scene(**base)


class TestScene(unittest.TestCase):
    def test_bounds_cover_the_candles(self):
        lo, hi = scene().price_bounds()
        self.assertLess(lo, 98)
        self.assertGreater(hi, 112)

    def test_bounds_stretch_to_include_a_stop_outside_the_candles(self):
        """⭐ وقف خارج المدى يجب أن يظهر — وإلا رُسمت صورة كاذبة."""
        lo, _ = scene(levels=[Level(80.0, "وقف", "stop")]).price_bounds()
        self.assertLess(lo, 80.0)

    def test_bounds_include_zones_and_markers(self):
        _, hi = scene(zones=[Zone(140.0, 138.0)]).price_bounds()
        self.assertGreater(hi, 140.0)
        lo, _ = scene(markers=[Marker(0, 50.0)]).price_bounds()
        self.assertLess(lo, 50.0)

    def test_flat_market_does_not_collapse_the_scale(self):
        s = Scene(candles=candles((100, 100, 100, 100), (100, 100, 100, 100)))
        lo, hi = s.price_bounds()
        self.assertGreater(hi - lo, 0)

    def test_no_candles_is_an_error(self):
        with self.assertRaises(ValueError):
            Scene(candles=[]).price_bounds()

    def test_inverted_zone_is_rejected(self):
        with self.assertRaises(ValueError):
            Zone(top=100.0, bottom=110.0)


class TestSvg(unittest.TestCase):
    def test_it_is_a_wellformed_svg(self):
        out = render_svg(scene())
        self.assertTrue(out.startswith("<svg"))
        self.assertTrue(out.rstrip().endswith("</svg>"))
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', out)

    def test_one_body_rect_per_candle(self):
        out = render_svg(scene())
        bodies = out.count('<rect x=')
        self.assertEqual(bodies, len(ROWS))

    def test_bullish_and_bearish_use_different_colours(self):
        out = render_svg(scene())
        self.assertIn("#26a69a", out)      # صاعدة
        self.assertIn("#ef5350", out)      # هابطة — الشمعة الثالثة

    def test_levels_are_drawn_and_labelled(self):
        out = render_svg(scene(levels=[Level(105.0, "دخول 105", "entry")]))
        self.assertIn("دخول 105", out)
        self.assertIn("stroke-dasharray", out)

    def test_zone_is_drawn_under_the_candles(self):
        """المنطقة قبل الشموع في الترتيب — وإلا حجبتها."""
        out = render_svg(scene(zones=[Zone(106.0, 102.0, "أوردر بلوك", "ob")]))
        self.assertIn("أوردر بلوك", out)
        self.assertLess(out.index("fill-opacity"), out.index("#26a69a"))

    def test_marker_label_appears(self):
        out = render_svg(scene(markers=[Marker(1, 108.0, "قمة")]))
        self.assertIn("قمة", out)

    def test_marker_outside_the_window_is_skipped(self):
        out = render_svg(scene(markers=[Marker(99, 108.0, "خارج")]))
        self.assertNotIn("خارج", out)

    def test_price_axis_is_labelled(self):
        self.assertIn("112", render_svg(scene(), grid_lines=4))

    def test_title_falls_back_to_symbol_and_timeframe(self):
        self.assertIn("XAUUSD.m · M5", render_svg(scene()))

    def test_explicit_title_wins(self):
        self.assertIn("#1 — إعداد", render_svg(scene(title="#1 — إعداد")))

    def test_text_is_escaped(self):
        """نصّ غير مهرَّب يكسر الملف — والصورة المكسورة أسوأ من لا صورة."""
        out = render_svg(scene(title='<script>&"'))
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_empty_scene_is_rejected(self):
        with self.assertRaises(ValueError):
            render_svg(Scene(candles=[]))

    def test_unreadable_size_is_rejected(self):
        with self.assertRaises(ValueError):
            render_svg(scene(), width=100, height=100)

    def test_single_candle_renders(self):
        self.assertIn("<svg", render_svg(Scene(candles=candles((100, 104, 98, 103)))))


class TestGeometry(unittest.TestCase):
    """السعر الأعلى يجب أن يرتفع في الصورة — محور y مقلوب في SVG."""

    def _rect_y(self, svg, colour):
        for line in svg.splitlines():
            if line.startswith("<rect x=") and colour in line:
                return float(line.split('y="')[1].split('"')[0])
        raise AssertionError("لم يُعثر على الشمعة")

    def test_higher_price_is_higher_on_screen(self):
        low_then_high = candles((100, 101, 99, 100), (100, 130, 99, 129))
        svg = render_svg(Scene(candles=low_then_high))
        ys = [
            float(l.split('y="')[1].split('"')[0])
            for l in svg.splitlines() if l.startswith("<rect x=")
        ]
        self.assertLess(ys[1], ys[0])      # الأعلى سعرًا أصغر y


class TestFile(unittest.TestCase):
    def test_write_svg_creates_a_readable_file(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            p = write_svg(scene(), os.path.join(d, "c.svg"))
            with open(p, encoding="utf-8") as fh:
                self.assertIn("<svg", fh.read())


class TestLegend(unittest.TestCase):
    def test_legend_names_every_overlay_colour(self):
        out = legend()
        for token in ("فراغ سعري", "أوردر بلوك", "الدخول", "الوقف", "الهدف"):
            self.assertIn(token, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
