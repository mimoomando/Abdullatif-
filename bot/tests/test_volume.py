"""
اختبارات قراءة الفوليوم — وايكوف/د4.

كل اختبار يتحقق من جملة منصوصة.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.key_zones import KeyZone
from bot.primitives.volume import (
    find_weakness,
    has_volume,
    opposing_volume,
    read_break,
)

T0 = datetime(2026, 8, 27, 9, 0)


def mk(*rows) -> Series:
    """(open, high, low, close, volume)"""
    return Series(
        "M15",
        [
            Candle(T0 + timedelta(minutes=15 * i), o, h, l, c, v)
            for i, (o, h, l, c, v) in enumerate(rows)
        ],
    )


class TestHasVolume(unittest.TestCase):
    def test_feed_without_volume_is_detected(self):
        self.assertFalse(has_volume(mk((100, 101, 99, 100, 0))))

    def test_feed_with_volume(self):
        self.assertTrue(has_volume(mk((100, 101, 99, 100, 50))))


class TestOpposingVolume(unittest.TestCase):
    def test_picks_the_largest_opposing_candle(self):
        s = mk(
            (100, 101, 96, 97, 40),      # هابطة
            (97, 99, 96, 98, 90),        # صاعدة — ليست مقابلة لكسر صاعد
            (98, 101, 95, 96, 70),       # هابطة — الأكبر
            (96, 105, 95, 104, 30),      # 3 — شمعة الكسر
        )
        self.assertEqual(opposing_volume(s, 3, "up"), 70)

    def test_no_opposing_candle_returns_zero(self):
        s = mk((96, 99, 95, 98, 40), (98, 105, 97, 104, 30))
        self.assertEqual(opposing_volume(s, 1, "up"), 0.0)

    def test_lookback_limits_the_search(self):
        s = mk(
            (100, 101, 96, 97, 99),      # هابطة كبيرة — خارج النظر
            (97, 99, 96, 98, 10),
            (98, 99, 96, 97, 20),        # هابطة صغيرة
            (97, 105, 96, 104, 30),
        )
        self.assertEqual(opposing_volume(s, 3, "up", lookback=2), 20)

    def test_invalid_lookback_rejected(self):
        with self.assertRaises(ValueError):
            opposing_volume(mk((100, 101, 99, 100, 5)), 0, "up", lookback=0)


class TestReadBreak(unittest.TestCase):
    """
    ⭐ «الشمعة اللي طلعت أعلى من مستوى البائعين… بالفوليوم كانت هي أقل
    ⇒ هذا كسر وهمي».
    """

    def _series(self, break_volume):
        return mk(
            (100, 101, 96, 97, 80),      # هابطة قوية — الطرف المقابل
            (97, 99, 96, 98, 20),
            (98, 106, 97, 105, break_volume),
        )

    def test_weak_break_volume_means_fake(self):
        r = read_break(self._series(30), 2, "up")
        self.assertEqual(r.verdict, "fake")
        self.assertAlmostEqual(r.ratio, 30 / 80)
        self.assertIn("كسر وهمي", r.detail)

    def test_strong_break_volume_means_real(self):
        r = read_break(self._series(120), 2, "up")
        self.assertEqual(r.verdict, "real")
        self.assertGreater(r.ratio, 1)

    def test_real_break_warns_that_continuation_pattern_is_missing(self):
        """⛔ «فيك تكمل معه إذا أعطاك نموذج استمراري» — ولم يُدرَّس بعد."""
        r = read_break(self._series(120), 2, "up")
        self.assertIn("نموذج استمراري", r.detail)

    def test_missing_volume_is_unknown_not_a_guess(self):
        """غياب البيانات ليس دليلًا على شيء."""
        r = read_break(mk((100, 101, 96, 97, 0), (97, 106, 96, 105, 0)), 1, "up")
        self.assertEqual(r.verdict, "unknown")
        self.assertIsNone(r.ratio)
        self.assertFalse(r.usable)

    def test_no_opposing_candle_is_unknown(self):
        s = mk((96, 99, 95, 98, 40), (98, 106, 97, 105, 30))
        self.assertEqual(read_break(s, 1, "up").verdict, "unknown")

    def test_weak_ratio_tightens_the_test(self):
        """🔴 V1 — «أدنى بكثير» بلا نسبة: المقبض مكشوف."""
        s = self._series(75)
        self.assertEqual(read_break(s, 2, "up", weak_ratio=1.0).verdict, "fake")
        self.assertEqual(read_break(s, 2, "up", weak_ratio=0.5).verdict, "real")

    def test_downward_break_compares_against_up_candles(self):
        s = mk(
            (96, 104, 95, 103, 90),      # صاعدة قوية
            (103, 104, 100, 101, 20),
            (101, 102, 94, 95, 30),      # كسر هبوطًا بحجم أضعف
        )
        self.assertEqual(read_break(s, 2, "down").verdict, "fake")

    def test_out_of_range_index_rejected(self):
        with self.assertRaises(ValueError):
            read_break(mk((100, 101, 99, 100, 5)), 9, "up")

    def test_invalid_ratio_rejected(self):
        with self.assertRaises(ValueError):
            read_break(mk((100, 101, 99, 100, 5)), 0, "up", weak_ratio=0)

    def test_render_is_readable(self):
        self.assertIn("الفوليوم", read_break(self._series(30), 2, "up").render())


class TestWeakness(unittest.TestCase):
    """
    ⭐ «المشتريين أدنى من البائعين، ولكن شموع الخضر أعلى
    ⇒ هذا الصعود وهم».
    """

    def test_higher_high_on_weaker_volume_is_flagged(self):
        s = mk(
            (100, 102, 99, 101, 30),
            (101, 103, 100, 102, 25),
            (102, 103, 99, 100, 90),     # هابطة بحجم كبير
            (100, 102, 99, 101, 20),
            (101, 103, 100, 102, 15),
            (102, 106, 101, 105, 18),    # قمة أعلى بحجم أضعف
        )
        w = find_weakness(s, "up")
        self.assertTrue(w)
        self.assertEqual(w[-1].index, 5)
        self.assertLess(w[-1].with_volume, w[-1].against_volume)

    def test_strong_advance_is_not_weakness(self):
        s = mk(
            (100, 102, 99, 101, 80),
            (101, 103, 100, 102, 85),
            (102, 103, 99, 100, 20),
            (100, 102, 99, 101, 90),
            (101, 103, 100, 102, 95),
            (102, 106, 101, 105, 99),
        )
        self.assertEqual(find_weakness(s, "up"), [])

    def test_no_new_high_is_not_weakness(self):
        s = mk(
            (100, 108, 99, 101, 20),
            (101, 103, 100, 102, 15),
            (102, 103, 99, 100, 90),
            (100, 102, 99, 101, 10),
            (101, 102, 100, 101, 12),
            (101, 102, 100, 101, 11),    # لا قمة أعلى
        )
        self.assertEqual(find_weakness(s, "up"), [])

    def test_downward_weakness(self):
        s = mk(
            (105, 106, 103, 104, 30),
            (104, 105, 102, 103, 25),
            (103, 107, 102, 106, 90),    # صاعدة بحجم كبير
            (106, 107, 103, 104, 20),
            (104, 105, 102, 103, 15),
            (103, 104, 98, 99, 18),      # قاع أدنى بحجم أضعف
        )
        w = find_weakness(s, "down")
        self.assertTrue(w)
        self.assertIn("البائعين", w[-1].render())

    def test_render_names_who_is_weak(self):
        s = mk(
            (100, 102, 99, 101, 30), (101, 103, 100, 102, 25),
            (102, 103, 99, 100, 90), (100, 102, 99, 101, 20),
            (101, 103, 100, 102, 15), (102, 106, 101, 105, 18),
        )
        self.assertIn("ضعف المشتريين", find_weakness(s, "up")[-1].render())

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            find_weakness(mk((100, 101, 99, 100, 5)), "up", window=1)

    def test_feed_without_volume_yields_nothing(self):
        s = mk(*[(100, 101 + i, 99, 100, 0) for i in range(8)])
        self.assertEqual(find_weakness(s, "up"), [])


class TestVolumeOnlyAtKeyZones(unittest.TestCase):
    """
    ⭐⭐ تصحيح منصوص — البثّ المباشر ٢:

        «ما تيجي بكرة تقول لي الشمعة الحمراء بيّنت كثير بدي أبيع.
         **هذا الحكي مرفوض**»
        «بنقرا الفوليوم **عند المناطق المفتاحية فقط**»
        «بغير المنطقة المفتاحية — **ما تشوفه**»

    كانت `find_weakness` تمسح السلسلة كلها، أي تُنتج بالضبط الحكم
    الذي سمّاه مرفوضًا.
    """

    ROWS = (
        (100, 102, 99, 101, 30),
        (101, 103, 100, 102, 25),
        (102, 103, 99, 100, 90),
        (100, 102, 99, 101, 20),
        (101, 103, 100, 102, 15),
        (102, 106, 101, 105, 18),      # التباعد هنا — عند 105
    )

    def test_without_zones_it_scans_everything(self):
        """السلوك القديم يبقى متاحًا للاستكشاف التاريخي وحده."""
        self.assertTrue(find_weakness(mk(*self.ROWS), "up"))

    def test_a_zone_far_from_price_suppresses_the_reading(self):
        """⭐ لا منطقة ⇒ لا حكم. هذا هو التصحيح."""
        far = [KeyZone(bottom=50.0, top=51.0, touches=3, first_index=0, last_index=1)]
        self.assertEqual(find_weakness(mk(*self.ROWS), "up", zones=far), [])

    def test_a_zone_at_the_move_allows_the_reading(self):
        near = [KeyZone(bottom=104.0, top=106.0, touches=3, first_index=0, last_index=1)]
        found = find_weakness(mk(*self.ROWS), "up", zones=near)
        self.assertTrue(found)
        self.assertEqual(found[-1].index, 5)

    def test_empty_zone_list_suppresses_everything(self):
        """قائمة فارغة ليست «بلا قيد» — هي «لا منطقة مفتاحية».""" 
        self.assertEqual(find_weakness(mk(*self.ROWS), "up", zones=[]), [])

    def test_proximity_widens_the_gate(self):
        near = [KeyZone(bottom=108.0, top=109.0, touches=3, first_index=0, last_index=1)]
        self.assertEqual(find_weakness(mk(*self.ROWS), "up", zones=near), [])
        self.assertTrue(
            find_weakness(mk(*self.ROWS), "up", zones=near, proximity=3.0)
        )

    def test_the_candle_range_opens_the_gate_not_just_the_close(self):
        """الشمعة التي اخترقت المنطقة ثم أغلقت خارجها هي المقصودة بالقراءة."""
        pierce = [KeyZone(bottom=103.0, top=104.0, touches=3, first_index=0, last_index=1)]
        self.assertTrue(find_weakness(mk(*self.ROWS), "up", zones=pierce))

    def test_negative_proximity_rejected(self):
        with self.assertRaises(ValueError):
            find_weakness(mk(*self.ROWS), "up", zones=[], proximity=-1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
