"""
اختبارات القناة السعريّة.

⛔ **مبنيّةٌ غير موصولة** — وهو نفسُه يقول إنّها لا تُحترم دائمًا:
«مش شرط إنّه يحترمها السعر بشكل كثير كبير». فهي **قراءةٌ للموجة**
لا زنادُ دخول: «القنوات السعريّة بتعبّر عن **الموجة كاملة**».
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.channel import (
    MAX_CLONES,
    MIN_CORRECTION,
    anchor_ok,
    build,
    chain,
    corrected,
)
from bot.primitives.swings import Swing

T0 = datetime(2026, 9, 14, 0, 0)


def mk(*rows, tf="M15"):
    return Series(tf, [Candle(T0 + timedelta(minutes=15 * i), o, h, l, c)
                       for i, (o, h, l, c) in enumerate(rows)], symbol="XAUUSD")


def sw(i, price, kind):
    return Swing(i, T0 + timedelta(minutes=15 * i), price, kind)


class TestTheSpokenNumbers(unittest.TestCase):
    def test_the_correction_floor_is_the_spoken_half(self):
        """«بدها تكون قمّة منتهية ومصحَّحة — **مصحّحها أكثر من 50%**»."""
        self.assertEqual(MIN_CORRECTION, 0.50)

    def test_the_clone_cap_is_the_spoken_three(self):
        """«مرّتين أو ثلاث، مش أكثر… **كحدٍّ أقصى**»."""
        self.assertEqual(MAX_CLONES, 3)


class TestAnchorMustBeFinished(unittest.TestCase):
    """
    ⭐ «**ما بدها تكون قمّة عم تتشكّل هلّق** تحدّدها… لا، ما بتزبط»

    فقمّةٌ لا شمعةَ بعدها **لا تُقاس** — وذلك غير «صحّحت صفرًا».
    """

    def test_a_peak_with_nothing_after_it_is_not_judged(self):
        s = mk((10, 20, 9, 19), (19, 30, 18, 29))
        self.assertIsNone(corrected(s, sw(1, 30.0, "high")))

    def test_and_it_is_not_an_acceptable_anchor(self):
        s = mk((10, 20, 9, 19), (19, 30, 18, 29))
        self.assertFalse(anchor_ok(s, sw(1, 30.0, "high")))


class TestAnchorMustBeCorrected(unittest.TestCase):
    def test_a_deep_correction_qualifies(self):
        # الموجة 10→30 (مدى 20) ثم نزلت إلى 15 ⇒ صحّحت 15/20 = 75%
        s = mk((10, 12, 10, 11), (11, 30, 11, 29), (29, 29, 15, 16))
        self.assertAlmostEqual(corrected(s, sw(1, 30.0, "high")), 0.75)
        self.assertTrue(anchor_ok(s, sw(1, 30.0, "high")))

    def test_a_shallow_correction_does_not(self):
        # نزلت إلى 26 فقط ⇒ 4/20 = 20%
        s = mk((10, 12, 10, 11), (11, 30, 11, 29), (29, 29, 26, 27))
        self.assertAlmostEqual(corrected(s, sw(1, 30.0, "high")), 0.20)
        self.assertFalse(anchor_ok(s, sw(1, 30.0, "high")))

    def test_exactly_half_is_not_enough(self):
        """⚠️ و«**أكثر من** 50%» حرفيّة — فالخمسون بالضبط لا تكفي."""
        s = mk((10, 12, 10, 11), (11, 30, 11, 29), (29, 29, 20, 21))
        self.assertAlmostEqual(corrected(s, sw(1, 30.0, "high")), 0.50)
        self.assertFalse(anchor_ok(s, sw(1, 30.0, "high")))

    def test_lows_mirror(self):
        # الموجة 30→10 (مدى 20) ثم صعدت إلى 25 ⇒ صحّحت 15/20 = 75%
        s = mk((29, 30, 28, 29), (29, 29, 10, 11), (11, 25, 11, 24))
        self.assertAlmostEqual(corrected(s, sw(1, 10.0, "low")), 0.75)


class TestWhichAnchorsTheSideNeeds(unittest.TestCase):
    """«صاعد ⇒ **قاعان وقمّة** · هابط ⇒ **قمّتان وقاع**»."""

    def setUp(self):
        self.s = mk(*[(20, 40, 5, 25)] * 12)

    def test_bullish_rests_on_two_lows(self):
        swings = [sw(1, 10.0, "low"), sw(3, 30.0, "high"), sw(5, 14.0, "low")]
        ch = build(self.s, swings, "bullish")
        self.assertIsNotNone(ch)
        self.assertTrue(ch.first.is_low and ch.second.is_low)
        self.assertTrue(ch.opposite.is_high)

    def test_bearish_rests_on_two_highs(self):
        swings = [sw(1, 30.0, "high"), sw(3, 10.0, "low"), sw(5, 26.0, "high")]
        ch = build(self.s, swings, "bearish")
        self.assertIsNotNone(ch)
        self.assertTrue(ch.first.is_high and ch.second.is_high)
        self.assertTrue(ch.opposite.is_low)

    def test_one_low_is_not_a_channel(self):
        self.assertIsNone(build(self.s, [sw(1, 10.0, "low"),
                                         sw(3, 30.0, "high")], "bullish"))

    def test_no_opposite_anchor_is_not_a_channel(self):
        self.assertIsNone(build(self.s, [sw(1, 10.0, "low"),
                                         sw(5, 14.0, "low")], "bullish"))


class TestASubChannelIsNotRejected(unittest.TestCase):
    """
    ⭐ «أمّا إنّك تيجي تحطّها بهالشكل… **فهي مرفوضة، هي صارت فرعيّة**»

    فالمرتكزُ الناقص **لا يُسقط القناة** — يغيّر اسمَها. ولذلك
    `sub=True` ولا `None`.
    """

    def test_an_unfinished_anchor_makes_it_a_sub_channel(self):
        s = mk(*[(20, 40, 5, 25)] * 8)
        swings = [sw(1, 10.0, "low"), sw(3, 30.0, "high"), sw(7, 14.0, "low")]
        ch = build(s, swings, "bullish")
        self.assertIsNotNone(ch)
        self.assertTrue(ch.sub)
        self.assertEqual(ch.kind, "فرعيّة")


class TestCloning(unittest.TestCase):
    """«أعمل **كلون** وأحطّ **المقاومة عند مستوى الدعم**»."""

    def setUp(self):
        self.s = mk(*[(20, 40, 5, 25)] * 12)
        self.ch = build(self.s, [sw(1, 10.0, "low"), sw(3, 30.0, "high"),
                                 sw(5, 14.0, "low")], "bullish")

    def test_a_clone_advances_the_generation(self):
        self.assertEqual(self.ch.generation, 0)
        self.assertEqual(self.ch.cloned().generation, 1)

    def test_it_stops_at_the_spoken_cap(self):
        """⛔ «مرّة ثالثة رابعة خامسة؟ **لا** — مرّتين أو ثلاث كحدٍّ أقصى»."""
        made = chain(self.ch)
        self.assertEqual(len(made), MAX_CLONES + 1)     # الأصل وثلاثُ نسخ
        self.assertIsNone(made[-1].cloned())

    def test_the_clone_keeps_the_same_anchors(self):
        c = self.ch.cloned()
        self.assertEqual(c.first, self.ch.first)
        self.assertEqual(c.opposite, self.ch.opposite)


class TestGeometry(unittest.TestCase):
    def test_body_and_wick_give_different_lines(self):
        """«بنرسم على الذيول، ولكن **الأفضل على جسم الشمعة**»."""
        s = mk((20, 40, 5, 25), (20, 40, 5, 25), (20, 40, 5, 25),
               (20, 40, 5, 25), (20, 40, 5, 25), (20, 40, 5, 25))
        swings = [sw(1, 5.0, "low"), sw(2, 40.0, "high"), sw(3, 5.0, "low")]
        body = build(s, swings, "bullish", on_body=True)
        wick = build(s, swings, "bullish", on_body=False)
        self.assertNotEqual(body.base_at(s, 0), wick.base_at(s, 0))

    def test_a_flat_base_has_no_slope(self):
        s = mk(*[(20, 40, 5, 25)] * 8)
        ch = build(s, [sw(1, 10.0, "low"), sw(2, 30.0, "high"),
                       sw(5, 10.0, "low")], "bullish")
        self.assertAlmostEqual(ch.slope(s), 0.0)


class TestItIsNotWiredIntoAnyDecision(unittest.TestCase):
    """
    ⛔⛔ **وهو نفسُه يقول إنّها لا تُحترم دائمًا:**

        «**مش شرط إنّه يحترمها السعر** بشكل كثير كبير»

    فهي قراءةٌ للموجة لا زنادُ دخول. ولا تُوصَل بقرارٍ قبل قياس.
    """

    def test_no_decision_module_imports_it(self):
        import pathlib
        import re
        pattern = re.compile(r"^\s*from\s+\S*channel\s+import|^\s*import\s+\S*channel",
                             re.MULTILINE)
        for name in ("chain.py", "runner.py"):
            src = (pathlib.Path("bot") / name).read_text(encoding="utf-8")
            with self.subTest(module=name):
                self.assertIsNone(pattern.search(src),
                                  f"{name} صار يستورد قاعدةً لم تُقَس")


if __name__ == "__main__":
    unittest.main(verbosity=2)
