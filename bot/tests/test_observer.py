"""
اختبارات مراقب السوق.

الغرض المعلَن: جعل نوعَي الخطأ اللذين سمّاهما المدرّب **مرئيَّين ومعدودَين**.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.observer import DayObservation, contradiction_note, observe

T0 = datetime(2026, 8, 27, 9, 0)


def mk(*rows) -> Series:
    return Series(
        "M5",
        [Candle(T0 + timedelta(minutes=5 * i), o, h, l, c) for i, (o, h, l, c) in enumerate(rows)],
    )


BULLISH = (
    (100, 102,  98, 101),
    (101, 112, 100, 111),
    (110, 110,  95,  97),
    (106, 118, 106, 117),
    (117, 122, 112, 121),
    (120, 120, 105, 107),
    (110, 128, 110, 127),
    (127, 135, 120, 134),
    (130, 130, 124, 126),
)


class TestObserve(unittest.TestCase):
    def test_records_trend_and_swings(self):
        o = observe(mk(*BULLISH), "H1")
        self.assertEqual(o.trend, "bullish")
        self.assertGreaterEqual(len(o.of("swing")), 4)

    def test_short_series_is_empty(self):
        o = observe(mk((100, 101, 99, 100), (100, 101, 99, 100)), "H1")
        self.assertEqual(o.events, [])

    def test_events_are_sorted_by_index(self):
        o = observe(mk(*BULLISH), "H1")
        self.assertEqual([e.index for e in o.events], sorted(e.index for e in o.events))

    def test_counts_summarise_each_kind(self):
        c = observe(mk(*BULLISH), "H1").counts()
        self.assertIn("swing", c)
        self.assertTrue(all(v > 0 for v in c.values()))

    def test_records_fvgs(self):
        o = observe(mk(*BULLISH), "H1")
        self.assertTrue(o.of("fvg"))

    def test_notable_candle_flagged(self):
        rows = tuple((100, 101, 99, 100) for _ in range(8)) + ((100, 130, 95, 128),)
        o = observe(mk(*rows), "H1", notable_range_multiple=2.0)
        self.assertTrue(o.of("notable_candle"))

    def test_flat_series_has_no_notable_candle(self):
        rows = tuple((100, 101, 99, 100) for _ in range(9))
        self.assertEqual(observe(mk(*rows), "H1").of("notable_candle"), [])


class TestUnactivatedPatternsAreRecorded(unittest.TestCase):
    """
    ⭐ ردّ اعتراض المدرّب: النموذج الذي تكوّن ولم يُفعَّل **يبقى مسجَّلًا**،
    فلا يختفي الرفض.
    """

    def test_forming_pattern_still_appears(self):
        rows = (
            (105, 107, 104, 106),
            (106, 107, 100, 102),      # قاع 100
            (102, 108, 101, 107),
            (107, 110, 106, 109),      # قمة 110
            (109, 109, 103, 104),
            (104, 106, 101, 105),      # قاع 101 — دبل بتم
            (105, 108, 104, 107),
            (107, 109, 106, 108),      # لا كسر لخط العنق
            (108, 109, 106, 107),
        )
        o = observe(mk(*rows), "M5", pattern_tolerance=2)
        pats = o.of("pattern")
        self.assertTrue(pats)
        self.assertTrue(any("لم يُفعَّل" in p.label for p in pats))

    def test_pattern_event_carries_neckline_and_extreme(self):
        rows = (
            (105, 107, 104, 106), (106, 107, 100, 102), (102, 108, 101, 107),
            (107, 110, 106, 109), (109, 109, 103, 104), (104, 106, 101, 105),
            (105, 108, 104, 107), (107, 109, 106, 108), (108, 109, 106, 107),
        )
        p = observe(mk(*rows), "M5", pattern_tolerance=2).of("pattern")[0]
        self.assertIn("خط العنق", p.detail)
        self.assertIn("الطرف", p.detail)


class TestNearMiss(unittest.TestCase):
    """⭐ «الشكل صح والحساب غلط» — يُرصد بدل أن يختفي."""

    ROWS = (
        (105, 107, 104, 106),
        (106, 107, 100, 102),      # 1 — قاع 100
        (102, 108, 101, 107),
        (107, 110, 106, 109),      # 3 — قمة 110
        (109, 109, 105, 106),
        (106, 106, 103, 105),      # 5 — قاع 103 · الفارق عن 100 = 3
        (105, 108, 104, 107),
        (107, 109, 106, 108),
        (108, 109, 106, 107),
    )

    def test_near_miss_detected_outside_tolerance(self):
        o = observe(mk(*self.ROWS), "M5", pattern_tolerance=1.5, near_miss_factor=3.0)
        self.assertTrue(o.near_misses)
        nm = o.near_misses[0]
        self.assertAlmostEqual(nm.actual, 3.0)
        self.assertAlmostEqual(nm.margin, 1.5)

    def test_inside_tolerance_is_not_a_near_miss(self):
        """ما قُبل ليس رفضًا بفارق ضئيل."""
        o = observe(mk(*self.ROWS), "M5", pattern_tolerance=5.0, near_miss_factor=2.0)
        self.assertEqual(o.near_misses, [])

    def test_far_miss_is_not_flagged(self):
        o = observe(mk(*self.ROWS), "M5", pattern_tolerance=0.2, near_miss_factor=1.5)
        self.assertEqual(o.near_misses, [])

    def test_render_explains_the_margin(self):
        o = observe(mk(*self.ROWS), "M5", pattern_tolerance=1.5, near_miss_factor=3.0)
        text = o.near_misses[0].render()
        self.assertIn("السماحية", text)
        self.assertIn("بفارق", text)
        self.assertIn("العين قد تراه", text)

    def test_invalid_factor_rejected(self):
        with self.assertRaises(ValueError):
            observe(mk(*self.ROWS), "M5", near_miss_factor=0.5)


class TestContradictionNote(unittest.TestCase):
    def test_none_when_nothing_unexplained(self):
        o = DayObservation(timeframe="H1")
        self.assertIsNone(contradiction_note(o, []))

    def test_note_counts_near_misses(self):
        o = observe(mk(*TestNearMiss.ROWS), "M5", pattern_tolerance=1.5, near_miss_factor=3.0)
        note = contradiction_note(o, ["تحت بوابة الـ50%"])
        self.assertIsNotNone(note)
        self.assertIn("رفضًا بفارق ضئيل", note)
        self.assertIn("المعايرة ضيقة", note)

    def test_note_mentions_rejection_reasons(self):
        o = observe(mk(*TestNearMiss.ROWS), "M5", pattern_tolerance=1.5, near_miss_factor=3.0)
        note = contradiction_note(o, ["كسر بزخم", "كسر بزخم"])
        self.assertIn("كسر بزخم", note)


class TestRender(unittest.TestCase):
    def test_render_has_trend_and_counts(self):
        out = observe(mk(*BULLISH), "H1").render()
        self.assertIn("مراقب H1", out)
        self.assertIn("الاتجاه: bullish", out)

    def test_render_lists_near_misses(self):
        o = observe(mk(*TestNearMiss.ROWS), "M5", pattern_tolerance=1.5, near_miss_factor=3.0)
        self.assertIn("رُفض بفارق ضئيل", o.render())

    def test_observer_never_decides(self):
        """المراقب يصف ولا يقرّر — لا يحمل دخولًا ولا وقفًا."""
        o = observe(mk(*BULLISH), "H1")
        self.assertFalse(hasattr(o, "entry"))
        self.assertFalse(hasattr(o, "stop"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
