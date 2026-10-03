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
    ⭐ «**ما بدها تكون قمّة عم تتشكّل هلّا** تحدّدها… لا، ما بتزبط»

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


class TestTwoThingsFoundOn0930(unittest.TestCase):
    """
    ⚠️ **والوحدةُ غيرُ موصولة** — فلا قرارَ يتغيّر بما هنا.

    **CH1** وصفٌ لا مطالبة (المقامُ `UNDEFINED` بنصّه) — ولم يُغيَّر.
    ✅ **وCH2 أُغلق 2026-10-03**: وصل سندُه (درس 22 عند 4:06) فبُني،
    **وهو أوّلُ تغييرِ سلوكٍ في هذه الوحدة** — ولأنّها غيرُ موصولة
    فلا رقمٌ منشورٌ يتحرّك به.
    """

    T = datetime(2026, 9, 1)

    def _mk(self, rows):
        return Series("M15", [
            Candle(self.T + timedelta(minutes=15 * i), o, h, l, c)
            for i, (o, h, l, c) in enumerate(rows)])

    def _sw(self, i, kind, price):
        return Swing(index=i, kind=kind, price=price,
                     time=self.T + timedelta(minutes=15 * i))

    # ── CH1: المقامُ التاريخُ كلُّه لا الموجة ──
    WAVE = [(100, 101, 99.5, 100.5), (101, 104, 100.5, 103), (103, 110, 102.5, 109)]
    BACK = [(109, 109.5, 104.0, 104.5)]

    def _with_history(self, bars: int):
        older = [(160 - k * 3, 160 - k * 3 + 0.5, 157 - k * 3, 157 - k * 3)
                 for k in range(bars)]
        series = self._mk(older + self.WAVE + self.BACK)
        return series, self._sw(bars + 2, "high", 110.0)

    def test_the_same_correction_reads_differently_by_how_far_back_you_fetched(self):
        """
        ⛔ الموجةُ 99.5 ⇒ 110 والتصحيحُ إلى 104 — أي **57%**.
        والسوقُ واحد، والذي تغيّر **كم شمعةً جُلبت**.
        """
        s0, sw0 = self._with_history(0)
        s1, sw1 = self._with_history(30)

        self.assertAlmostEqual(corrected(s0, sw0), 0.571, places=3)
        self.assertAlmostEqual(corrected(s1, sw1), 0.150, places=3)

        self.assertTrue(anchor_ok(s0, sw0))
        self.assertFalse(anchor_ok(s1, sw1),
                         "⇒ الحكمُ يقرّره --poi-bars لا السعر")

    def test_the_denominator_is_declared_where_it_lives(self):
        self.assertIn("CH1", corrected.__doc__)
        self.assertIn("رقمٌ يقلبه اختيارُك", corrected.__doc__)

    # ── CH2: والنسخةُ تُزيح — أُغلق 2026-10-03 ──
    def _channel(self):
        from bot.primitives.channel import Channel
        return Channel("bullish",
                       self._sw(0, "low", 90.0), self._sw(10, "low", 95.0),
                       self._sw(5, "high", 105.0), on_body=False)

    def _bearish(self):
        """قناةٌ هابطة: **قمّتان وقاع** — والقاعدةُ هي خطُّ المقاومة."""
        from bot.primitives.channel import Channel
        return Channel("bearish",
                       self._sw(0, "high", 110.0), self._sw(10, "high", 105.0),
                       self._sw(5, "low", 97.5), on_body=False)

    def test_each_clone_steps_one_width_across_the_base(self):
        """
        ✅ «بعمل كلون **هي نفسها بسحبها**» — والمقابلُ على قاعدة الأصل.

        ⇒ فالخطّان ينزاحان **عرضًا واحدًا لكلّ جيل**، والميلُ واحد.
        """
        series = self._mk([(100, 101, 99, 100)] * 20)
        copies = chain(self._channel())
        self.assertEqual(len(copies), MAX_CLONES + 1)

        lines = [(round(c.base_at(series, 15), 6),
                  round(c.top_at(series, 15), 6)) for c in copies]
        self.assertEqual(lines, [(97.5, 110.0), (85.0, 97.5),
                                 (72.5, 85.0), (60.0, 72.5)])

        # ⭐ وخطُّ كلّ نسخةٍ المقابلُ **هو** قاعدةُ سابقتها
        for older, newer in zip(copies, copies[1:]):
            self.assertAlmostEqual(newer.top_at(series, 15),
                                   older.base_at(series, 15))
            self.assertAlmostEqual(newer.slope(series), older.slope(series),
                                   msg="الميلُ تغيّر — والنسخةُ «هي نفسها»")

    def test_the_two_spoken_cases_come_out_of_one_formula(self):
        """
        ⭐⭐⭐ واللفظان ليسا متناقضين — **هما الجهتان**:

        4:06 «بحط هيدا اللي تحت اللي كان دعم من تحت على خط المقاومه»
             ⇒ قناةٌ **هابطة** كُسرت صاعدةً ⇒ النسخةُ **أعلى**
        6:43 «واحط مستوى المقاومه عند مستوى الدعم»
             ⇒ قناةٌ **صاعدة** كُسرت هابطةً ⇒ النسخةُ **أسفل**
        """
        series = self._mk([(100, 101, 99, 100)] * 20)

        up = self._bearish()
        up_clone = up.cloned()
        # قاعدةُ الهابطة هي خطُّ المقاومة، ومقابلُها الدعم
        self.assertGreater(up.base_at(series, 15), up.top_at(series, 15))
        # ⇒ ودعمُ النسخة يصير على مقاومة الأصل ⇒ النسخةُ أعلى
        self.assertAlmostEqual(up_clone.top_at(series, 15),
                               up.base_at(series, 15))
        self.assertGreater(up_clone.base_at(series, 15),
                           up.base_at(series, 15))

        down = self._channel()
        down_clone = down.cloned()
        # ⇒ ومقاومةُ النسخة تصير على دعم الأصل ⇒ النسخةُ أسفل
        self.assertAlmostEqual(down_clone.top_at(series, 15),
                               down.base_at(series, 15))
        self.assertLess(down_clone.base_at(series, 15),
                        down.base_at(series, 15))

    def test_the_original_is_not_shifted(self):
        """⛔ والجيلُ صفرٌ لا يُزاح — وإلّا انتقل الأصلُ نفسُه."""
        series = self._mk([(100, 101, 99, 100)] * 20)
        self.assertEqual(self._channel().shift(series), 0.0)
        self.assertEqual(self._bearish().shift(series), 0.0)

    def test_only_the_label_changes(self):
        self.assertEqual([c.kind for c in chain(self._channel())],
                         ["أساسيّة", "نسخة 1", "نسخة 2", "نسخة 3"])

    def test_the_clone_limit_still_matches_the_text(self):
        """✅ «مرّتين أو ثلاث — مش أكثر»: ثلاثُ نسخٍ وأصلُها."""
        self.assertEqual(MAX_CLONES, 3)
        self.assertIsNone(chain(self._channel())[-1].cloned())

    def test_the_closed_gap_keeps_its_record_where_whoever_wires_it_reads(self):
        """
        ⚠️ وCH2 أُغلق — **ولا يُحذَف سجلُّه**: فيه خطئي (قرأتُ جوارَ
        السطر لا المقطعَ) وفيه الاقتباسُ الذي حسمه.
        """
        from bot.primitives.channel import Channel
        doc = Channel.cloned.__doc__
        self.assertIn("CH2", doc)
        self.assertIn("4:06", doc)
        self.assertIn("هي نفسها بسحبها", doc)


class TestCH3TheAttributionItself(unittest.TestCase):
    """
    ⛔⛔ **CH3 — [أفي الملفّ الذي نسبتُها إليه؟]** · 2026-10-03.

    ترويسةُ `channel.py` كانت تنسب ستّةَ اقتباساتٍ إلى [درس القنوات
    السعريّة] وحدَه، **وثلاثةٌ منها في درس 32**.

    ⭐⭐ **وهذا الفحصُ أصرمُ من `bot.quotes`**: ذاك يسأل [أقيلت
    العبارة؟] فيطابق على **السجلّ كلِّه**، وهذا يسأل [**أفي الملفّ
    الذي سمّيتُه**؟]. **ومقيسٌ**: كشف «هلّق» وصوابُها «هلّا» —
    وتحريفُ كلمةٍ واحدةٍ يمرّ على التغطية الواسعة (QT4).

    ⚠️ **وحدُّه يُقال**: `channel.py` هي **الوحدةُ الوحيدةُ** التي
    تسمّي ملفَّ مصدرٍ صريحًا. والبواقي تنسب بالنصّ ([الدرس 10] ·
    [درس السيولة]) — **أسماءُ توثيقٍ لا معرّفات**، وهو حدُّ PR1
    بعينه. ⇒ **فـCH3 غيرُ مقيسٍ في غيرها، لا معدومٌ فيها.**
    """

    NAMED = ("lesson-22-price-channels.md", "lesson-32-order-block-03.md")

    def test_every_quote_sits_in_a_file_the_header_names(self):
        import pathlib
        import re

        from bot import quotes as Q

        hay = []
        for name in self.NAMED:
            path = pathlib.Path("knowledge/source") / name
            raw = Q.raw_only(path.read_text(encoding="utf-8"))
            hay.append(" ".join(Q.normalise(w)
                                for w in Q.tokens(raw, least=1)))

        src = pathlib.Path("bot/primitives/channel.py")
        bare = Q._undecorate(src.read_text(encoding="utf-8"))
        checked = 0
        for quote in re.findall(r"«([^»]+)»", bare):
            quote = " ".join(quote.split())
            toks = Q.tokens(quote)
            if len(toks) < Q.MIN_WORDS:
                continue           # ◆ أقصرُ من أن يُفحَص — شأنُ الأداة
            checked += 1
            missing = [[t for t in toks if t not in h] for h in hay]
            with self.subTest(quote=quote[:48]):
                self.assertTrue(any(not m for m in missing),
                                "اقتباسٌ ليس في أيٍّ من الملفّين "
                                f"المسمَّيين — الناقص: {missing[0][:4]}")
        self.assertGreaterEqual(checked, 15, "تقلّص المفحوصُ — راجِع CH3")
