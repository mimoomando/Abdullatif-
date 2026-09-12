"""
اختبارات مراحل الأوردر بلوك — البثّ ٣.

⛔ الشرط الحاكم (§7): هذه المراحل **ليست أنماط شموع مستقلّة** —
«valid only in that history». فكلُّ اختبار هنا يبني أمًّا أوّلًا.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.fvg import FVG
from bot.primitives.liquidity import Sweep
from bot.primitives.ob_lifecycle import (
    DerivedBlock,
    Lifecycle,
    trace,
    trace_all,
    usable,
)
from bot.primitives.order_block import OrderBlock
from bot.primitives.swings import Swing, find_swings

T0 = datetime(2026, 9, 14, 9, 0)


def mk(*rows, tf="M15"):
    return Series(tf, [
        Candle(T0 + timedelta(minutes=15 * i), o, h, l, c)
        for i, (o, h, l, c) in enumerate(rows)
    ])


def sw(index, price, kind):
    return Swing(index, T0 + timedelta(minutes=15 * index), price, kind)


def ob(index=2, direction="bullish", top=102.0, bottom=98.0,
       break_index=3, state="fresh"):
    """أمٌّ اصطناعيّة — الثلاثية مضمونة ببناء الكائن."""
    low_side = direction == "bullish"
    swept = sw(0, 97.0, "low" if low_side else "high")
    return OrderBlock(
        index=index, time=T0 + timedelta(minutes=15 * index),
        direction=direction, top=top, bottom=bottom,
        sweep=Sweep(swept_swing=swept, penetration_index=1, reclaim_index=2,
                    time=swept.time,
                    side="sell_side" if low_side else "buy_side",
                    level=97.0, extreme=96.0 if low_side else 98.0),
        break_index=break_index, governing_level=105.0,
        fvg=FVG(index, T0, direction, top, bottom),
        is_rejection_block=False, state=state,
    )


# ── السلسلة القياسيّة ───────────────────────────────────────────────
#
# الأمّ 98–102 صاعدة (break_index=3)، ثم:
#   4  تخفيف   — لامست المنطقة (أدنى 101)
#   6  قمة 106
#   7  الشمعة المعرِّفة للبروبلشن ⇒ 97–105
#   8  إغلاق 119 فوق 106 بالجسم  ⇒ **BMS**
#
FULL = ((100, 101, 99, 100), (100, 101, 99, 100), (101, 102, 98, 99),
        (99, 112, 99, 111), (111, 111, 101, 102), (102, 103, 95, 96),
        (96, 106, 96, 105), (105, 105, 97, 98), (98, 120, 98, 119),
        (119, 120, 116, 117))

# المرآة الهابطة — الأمّ 98–102 هابطة، وBMS هبوطًا عند 8
FULL_BEAR = ((100, 101, 99, 100), (100, 101, 99, 100), (99, 102, 98, 101),
             (101, 101, 88, 89), (89, 99, 89, 98), (98, 105, 97, 104),
             (104, 104, 94, 95), (95, 103, 95, 102), (102, 102, 80, 81),
             (81, 84, 80, 83))

TOUCH_ONLY = FULL[:6]          # تخفيف بلا BMS
AWAY = tuple([(120, 121, 119, 120)] * 8)     # لم يعد إلى المنطقة قطّ


def cycle(rows=FULL, **kw):
    s = mk(*rows)
    return trace(s, ob(**kw), find_swings(s)), s


class TestNoStandaloneDetection(unittest.TestCase):
    """
    ⛔ لا دالّة تمسح السلسلة بحثًا عن «بروبلشن» — هذا هو القيد نفسه.
    """

    def test_the_module_exposes_no_standalone_finder(self):
        import bot.primitives.ob_lifecycle as m
        for bad in ("find_propulsion", "find_mitigation", "find_blocks"):
            with self.subTest(bad=bad):
                self.assertFalse(hasattr(m, bad))

    def test_every_derived_block_names_its_parent(self):
        cyc, _ = cycle()
        for b in (cyc.mitigation, cyc.propulsion):
            self.assertIsNotNone(b)
            self.assertEqual(b.parent_index, cyc.parent.index)


class TestStageSequence(unittest.TestCase):
    """
    ⭐ «أول لمس اللي هو هيدا **الميتيجيشن**، وطلع **عمل بي إم إس**،
    وهون هيدا **البروبلشن بلوك** — **آخر مرحلة**»
    """

    def test_untouched_stays_fresh(self):
        cyc, _ = cycle(AWAY)
        self.assertEqual(cyc.stage, "طازجة")
        self.assertIsNone(cyc.mitigation)

    def test_the_first_touch_is_the_mitigation_block(self):
        cyc, _ = cycle(TOUCH_ONLY)
        self.assertIsNotNone(cyc.mitigation)
        self.assertEqual(cyc.mitigation.stage, "mitigation")
        self.assertEqual(cyc.mitigation.index, 4)

    def test_mitigation_without_a_bms_stops_there(self):
        cyc, _ = cycle(TOUCH_ONLY)
        self.assertEqual(cyc.stage, "مخفَّفة")
        self.assertIsNone(cyc.propulsion)

    def test_the_full_sequence_reaches_propulsion(self):
        cyc, _ = cycle()
        self.assertIsNotNone(cyc.propulsion)
        self.assertEqual(cyc.propulsion.stage, "propulsion")
        self.assertIn("آخر مرحلة", cyc.stage)
        self.assertEqual(cyc.bms_index, 8)

    def test_the_propulsion_sits_between_the_touch_and_the_bms(self):
        cyc, _ = cycle()
        self.assertGreaterEqual(cyc.propulsion.index, cyc.mitigation.index)
        self.assertLessEqual(cyc.propulsion.index, cyc.bms_index)

    def test_the_bms_must_go_with_the_blocks_direction(self):
        """كسرٌ هابطٌ ليس BMS لمنطقةٍ صاعدة — ولو كسر هيكلًا."""
        cyc, _ = cycle(FULL_BEAR)                # كسورها هبوطًا
        self.assertIsNone(cyc.propulsion)


class TestPermanentDeath(unittest.TestCase):
    """
    ⭐⭐ «بعد هلّا ها المنطقة **إذا في حال انضربت راح تروح نهائي**»
    """

    def _dead(self):
        # البروبلشن 97–105؛ والشمعة 9 تُغلق بجسمها تحت 97
        return cycle(FULL[:9] + ((119, 120, 80, 82),))

    def test_breaking_the_propulsion_kills_it(self):
        cyc, _ = self._dead()
        self.assertTrue(cyc.dead)
        self.assertEqual(cyc.dead_at, 9)
        self.assertEqual(cyc.stage, "ميّتة")

    def test_a_dead_cycle_offers_nothing_active(self):
        """ولو عاد السعر إليها ألف مرّة."""
        cyc, _ = self._dead()
        self.assertIsNone(cyc.active)

    def test_usable_filters_the_dead(self):
        cyc, _ = self._dead()
        self.assertEqual(usable([cyc]), [])

    def test_a_wick_through_the_propulsion_does_not_kill_it(self):
        """الضرب إغلاقٌ بالجسم — كما في `failed`، ولا قاعدةً ثانية."""
        cyc, _ = cycle(FULL[:9] + ((119, 120, 80, 119),))
        self.assertFalse(cyc.dead)
        self.assertIsNotNone(cyc.active)

    def test_the_render_says_why_it_died(self):
        cyc, _ = self._dead()
        self.assertIn("نهائيًّا", cyc.render())


class TestActiveZone(unittest.TestCase):
    def test_the_propulsion_supersedes_the_parent(self):
        """«آخر مرحلة» — وهي الأقرب إلى السعر، ومنها الدفع."""
        cyc, _ = cycle()
        self.assertIs(cyc.active, cyc.propulsion)

    def test_without_a_propulsion_the_parent_stands(self):
        cyc, _ = cycle(AWAY)
        self.assertIs(cyc.active, cyc.parent)


class TestFailedIsADifferentRoad(unittest.TestCase):
    """
    ⚠️ البريكر منطقةٌ **فشلت** فانقلب دورها؛ وهذه مراحلُ منطقةٍ
    **نجحت**. فالمساران متنافيان ولا يُخترع تسلسلٌ لمنطقةٍ فاشلة.
    """

    def test_a_failed_block_gets_no_stages(self):
        cyc, _ = cycle(state="failed")
        self.assertIsNone(cyc.mitigation)
        self.assertIsNone(cyc.propulsion)
        self.assertEqual(cyc.stage, "طازجة")     # لا مراحل أصلًا

    def test_a_breaker_gets_no_stages_either(self):
        cyc, _ = cycle(state="breaker")
        self.assertIsNone(cyc.mitigation)


class TestBearishMirror(unittest.TestCase):
    def test_the_sequence_mirrors_for_a_bearish_block(self):
        cyc, _ = cycle(FULL_BEAR, direction="bearish")
        self.assertIsNotNone(cyc.mitigation)
        self.assertIsNotNone(cyc.propulsion)
        self.assertEqual(cyc.propulsion.direction, "bearish")
        self.assertEqual(cyc.bms_index, 8)
        # الوقف فوق الطرف الأعلى في البيع
        self.assertGreater(cyc.propulsion.stop_for(2.0), cyc.propulsion.top)

    def test_a_bearish_cycle_dies_on_a_close_above_its_propulsion(self):
        cyc, _ = cycle(FULL_BEAR[:9] + ((81, 130, 80, 128),),
                       direction="bearish")
        self.assertTrue(cyc.dead)


class TestDerivedBlockGeometry(unittest.TestCase):
    def _b(self, direction="bullish"):
        return DerivedBlock(2, "propulsion", 5, T0, direction, 110.0, 100.0)

    def test_midpoint_and_size(self):
        b = self._b()
        self.assertEqual((b.size, b.midpoint), (10.0, 105.0))

    def test_stop_sits_beyond_the_far_edge(self):
        self.assertEqual(self._b().stop_for(2.0), 98.0)
        self.assertEqual(self._b("bearish").stop_for(2.0), 112.0)

    def test_a_negative_buffer_is_refused(self):
        with self.assertRaises(ValueError):
            self._b().stop_for(-1.0)

    def test_contains_is_inclusive(self):
        b = self._b()
        self.assertTrue(b.contains(100.0) and b.contains(110.0))
        self.assertFalse(b.contains(99.9))


class TestTraceAll(unittest.TestCase):
    def test_one_cycle_per_block(self):
        s = mk(*AWAY)
        blocks = [ob(index=2), ob(index=3, top=103.0, bottom=99.0)]
        self.assertEqual(len(trace_all(s, blocks, find_swings(s))), 2)

    def test_an_empty_list_is_fine(self):
        self.assertEqual(trace_all(mk((1, 2, 0, 1)), [], []), [])


class TestParamsMatch(unittest.TestCase):
    def test_the_stage_names_match_the_lesson(self):
        from bot import params as P
        self.assertEqual(P.OB_STAGES.value, ["mitigation", "bms", "propulsion"])
        self.assertEqual(P.OB_STAGES.origin, "SOURCE")

    def test_the_kill_rule_is_on(self):
        from bot import params as P
        self.assertTrue(P.PROPULSION_BREAK_KILLS_OB.value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
