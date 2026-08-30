"""
اختبارات المناطق المفتاحية — البثّ المباشر ٢.

⭐ هذه الوحدة تجسّد حلّ التعارض C1: المنطقة تُبنى من **إغلاقات الأجسام**
لأن «السيولة الحقيقية تكمن عند إغلاق جسم الشمعة»، بينما الذيل «سيولة
مرتكزة لسحب الستوبات».
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.key_zones import (
    KeyZone,
    between_zones,
    find_key_zones,
    opposite_zone,
    zone_at,
)

T0 = datetime(2026, 8, 30, 9, 0)


def mk(*rows) -> Series:
    return Series(
        "M15",
        [Candle(T0 + timedelta(minutes=15 * i), o, h, l, c)
         for i, (o, h, l, c) in enumerate(rows)],
    )


class TestFind(unittest.TestCase):
    def test_clustered_closes_form_a_zone(self):
        s = mk(
            (100, 106, 99, 100.0),
            (100, 107, 98, 100.4),
            (100, 108, 97, 100.2),
            (100, 131, 96, 130.0),
        )
        zones = find_key_zones(s, tolerance=1.0)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].touches, 3)

    def test_wicks_are_ignored_entirely(self):
        """
        ⭐ جوهر C1: الذيل سيولة ستوبات لا منطقة.

        الذيول هنا متطابقة عند 80 والإغلاقات متباعدة — فلا منطقة.
        """
        s = mk(
            (100, 101, 80, 100.0),
            (110, 111, 80, 110.0),
            (120, 121, 80, 120.0),
        )
        self.assertEqual(find_key_zones(s, tolerance=1.0), [])

    def test_single_close_is_a_point_not_a_zone(self):
        s = mk((100, 101, 99, 100.0), (140, 141, 139, 140.0))
        self.assertEqual(find_key_zones(s, tolerance=0.5), [])

    def test_min_touches_filters(self):
        s = mk(
            (100, 101, 99, 100.0), (100, 101, 99, 100.2),
            (140, 141, 139, 140.0), (140, 141, 139, 140.1),
            (140, 141, 139, 140.2),
        )
        self.assertEqual(len(find_key_zones(s, 1.0, min_touches=2)), 2)
        self.assertEqual(len(find_key_zones(s, 1.0, min_touches=3)), 1)

    def test_zones_are_returned_low_to_high(self):
        s = mk(
            (140, 141, 139, 140.0), (140, 141, 139, 140.1),
            (100, 101, 99, 100.0), (100, 101, 99, 100.1),
        )
        zones = find_key_zones(s, 1.0)
        self.assertLess(zones[0].bottom, zones[1].bottom)

    def test_max_zones_keeps_the_most_touched(self):
        s = mk(
            (100, 101, 99, 100.0), (100, 101, 99, 100.1),
            (140, 141, 139, 140.0), (140, 141, 139, 140.1), (140, 141, 139, 140.2),
        )
        zones = find_key_zones(s, 1.0, max_zones=1)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].touches, 3)

    def test_invalid_tolerance_rejected(self):
        with self.assertRaises(ValueError):
            find_key_zones(mk((100, 101, 99, 100)), tolerance=0)

    def test_min_touches_below_two_rejected(self):
        with self.assertRaises(ValueError):
            find_key_zones(mk((100, 101, 99, 100)), 1.0, min_touches=1)

    def test_empty_series(self):
        self.assertEqual(find_key_zones(Series("M15", []), 1.0), [])


class TestRole(unittest.TestCase):
    """«طالما السعر تحت منها هي مقاومة، بس يصير فوق منها بصير دعم»."""

    Z = KeyZone(bottom=100.0, top=102.0, touches=3, first_index=0, last_index=5)

    def test_price_below_makes_it_resistance(self):
        self.assertEqual(self.Z.role_for(95.0), "resistance")

    def test_price_above_makes_it_support(self):
        self.assertEqual(self.Z.role_for(110.0), "support")

    def test_role_flips_at_the_midpoint(self):
        self.assertEqual(self.Z.role_for(100.5), "resistance")
        self.assertEqual(self.Z.role_for(101.5), "support")

    def test_contains_and_distance(self):
        self.assertTrue(self.Z.contains(101.0))
        self.assertEqual(self.Z.distance_from(101.0), 0.0)
        self.assertAlmostEqual(self.Z.distance_from(105.0), 3.0)
        self.assertAlmostEqual(self.Z.distance_from(95.0), 5.0)

    def test_render_states_the_role(self):
        self.assertIn("مقاومة", self.Z.render(price=95.0))
        self.assertIn("دعم", self.Z.render(price=110.0))


class TestZoneAt(unittest.TestCase):
    """⭐ هذه بوابة قراءة الفوليوم — «بغير المنطقة المفتاحية ما تشوفه»."""

    ZONES = [
        KeyZone(100.0, 102.0, 3, 0, 5),
        KeyZone(130.0, 131.0, 2, 6, 9),
    ]

    def test_inside_a_zone(self):
        self.assertIsNotNone(zone_at(self.ZONES, 101.0))

    def test_outside_every_zone_is_none(self):
        self.assertIsNone(zone_at(self.ZONES, 120.0))

    def test_proximity_widens_the_reach(self):
        self.assertIsNone(zone_at(self.ZONES, 104.0))
        self.assertIsNotNone(zone_at(self.ZONES, 104.0, proximity=2.5))

    def test_nearest_zone_wins(self):
        z = zone_at(self.ZONES, 120.0, proximity=50.0)
        self.assertEqual(z.bottom, 130.0)      # 130 أقرب إلى 120 من 102

    def test_negative_proximity_rejected(self):
        with self.assertRaises(ValueError):
            zone_at(self.ZONES, 101.0, proximity=-1)


class TestOppositeZone(unittest.TestCase):
    """«مجرد الخروج من المنطقة… بستهدف المنطقة المقابلة فورًا»."""

    ZONES = [
        KeyZone(90.0, 91.0, 2, 0, 3),
        KeyZone(100.0, 102.0, 3, 4, 8),
        KeyZone(130.0, 131.0, 2, 9, 12),
    ]

    def test_target_above(self):
        z = opposite_zone(self.ZONES, 105.0, "up")
        self.assertEqual(z.bottom, 130.0)

    def test_target_below(self):
        z = opposite_zone(self.ZONES, 95.0, "down")
        self.assertEqual(z.top, 91.0)

    def test_nearest_not_farthest(self):
        """الهدف أقرب منطقة — لا مستوى بعيد مختار بنسبة عائد."""
        z = opposite_zone(self.ZONES, 92.0, "up")
        self.assertEqual(z.bottom, 100.0)

    def test_none_when_nothing_lies_ahead(self):
        self.assertIsNone(opposite_zone(self.ZONES, 200.0, "up"))


class TestBetweenZones(unittest.TestCase):
    """«الأكيوميوليشن بدها تصير بين منطقتين مفتاحيتين»."""

    ZONES = [KeyZone(90.0, 91.0, 2, 0, 3), KeyZone(130.0, 131.0, 2, 9, 12)]

    def test_range_between_two_zones(self):
        self.assertTrue(between_zones(self.ZONES, 100.0, 120.0))

    def test_range_with_nothing_above(self):
        self.assertFalse(between_zones(self.ZONES, 100.0, 200.0))

    def test_range_with_nothing_below(self):
        self.assertFalse(between_zones(self.ZONES, 50.0, 120.0))

    def test_inverted_range_rejected(self):
        with self.assertRaises(ValueError):
            between_zones(self.ZONES, 120.0, 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
