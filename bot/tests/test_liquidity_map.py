"""اختبارات خريطة السيولة — كل اختبار يتحقق من قاعدة منصوص عليها."""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.fvg import FVG
from bot.primitives.liquidity_map import (
    External,
    Internal,
    classify_external,
    internal_from,
    mark_protected,
    mark_swept,
    read_cycle,
    targets_above,
    targets_below,
    tier_for,
    usable_internal,
)
from bot.primitives.order_block import OrderBlock
from bot.primitives.swings import Swing

T0 = datetime(2026, 8, 27, 12, 0)


def mk(*rows) -> Series:
    return Series(
        "M5",
        [Candle(T0 + timedelta(minutes=5 * i), o, h, l, c) for i, (o, h, l, c) in enumerate(rows)],
    )


def swing(i, price, kind):
    return Swing(i, T0 + timedelta(minutes=5 * i), price, kind)


class TestTiers(unittest.TestCase):
    """درس السيولة الضخمة: التصنيف بالإطار الزمني."""

    def test_tier_table(self):
        self.assertEqual(tier_for("D1"), "major")
        self.assertEqual(tier_for("W1"), "major")
        self.assertEqual(tier_for("H1"), "medium")
        self.assertEqual(tier_for("M15"), "light")
        self.assertEqual(tier_for("M5"), "negligible")
        self.assertEqual(tier_for("M1"), "negligible")

    def test_unknown_timeframe_rejected(self):
        with self.assertRaises(ValueError):
            tier_for("H3")


class TestStrength(unittest.TestCase):
    """«لما بتكون لحالها فهي سيولة قوية… قمة مقرّبة لها ⇒ مخففة»."""

    def test_lone_swing_is_strong(self):
        out = classify_external([swing(1, 100, "high"), swing(5, 130, "high")], "H1", proximity=5)
        self.assertTrue(all(e.strength == "strong" for e in out))

    def test_nearby_peer_makes_it_thinned(self):
        out = classify_external([swing(1, 100, "high"), swing(5, 102, "high")], "H1", proximity=5)
        self.assertTrue(all(e.strength == "thinned" for e in out))

    def test_proximity_threshold_matters(self):
        pair = [swing(1, 100, "high"), swing(5, 108, "high")]
        self.assertTrue(all(e.strength == "strong" for e in classify_external(pair, "H1", 5)))
        self.assertTrue(all(e.strength == "thinned" for e in classify_external(pair, "H1", 10)))

    def test_different_kinds_do_not_thin_each_other(self):
        out = classify_external([swing(1, 100, "high"), swing(5, 101, "low")], "H1", proximity=5)
        self.assertTrue(all(e.strength == "strong" for e in out))

    def test_negative_proximity_rejected(self):
        with self.assertRaises(ValueError):
            classify_external([], "H1", proximity=-1)


class TestProtected(unittest.TestCase):
    """«نظّف كل السيولة السابقة، ومرتد هو أصلًا من أوردر بلوك»."""

    def _ob(self, bottom, top, direction="bullish"):
        return OrderBlock(
            index=3, time=T0, direction=direction, top=top, bottom=bottom,
            sweep=None, break_index=5, governing_level=0, fvg=None, is_rejection_block=False,
        )

    def test_both_conditions_required(self):
        e = classify_external([swing(3, 50, "low")], "H1", proximity=1)
        both = mark_protected(e, [self._ob(48, 52)], swept_levels=[50])
        self.assertTrue(both[0].protected)
        self.assertFalse(both[0].is_target)

    def test_cleaned_but_no_order_block(self):
        e = classify_external([swing(3, 50, "low")], "H1", proximity=1)
        self.assertFalse(mark_protected(e, [], swept_levels=[50])[0].protected)

    def test_order_block_but_did_not_clean(self):
        e = classify_external([swing(3, 50, "low")], "H1", proximity=1)
        self.assertFalse(mark_protected(e, [self._ob(48, 52)], swept_levels=[])[0].protected)

    def test_opposite_direction_block_does_not_protect(self):
        e = classify_external([swing(3, 50, "low")], "H1", proximity=1)
        out = mark_protected(e, [self._ob(48, 52, "bearish")], swept_levels=[50])
        self.assertFalse(out[0].protected)


class TestTargets(unittest.TestCase):
    def test_swept_level_is_no_longer_a_target(self):
        s = mk((50, 55, 49, 54), (54, 62, 53, 61), (61, 70, 60, 69))
        e = classify_external([swing(0, 55, "high")], "H1", proximity=1)
        self.assertTrue(mark_swept(s, e)[0].swept)
        self.assertFalse(mark_swept(s, e)[0].is_target)

    def test_nearest_first(self):
        e = classify_external(
            [swing(1, 110, "high"), swing(2, 130, "high"), swing(3, 120, "high")], "H1", 1
        )
        self.assertEqual([x.price for x in targets_above(e, 100)], [110, 120, 130])

    def test_targets_below_for_sells(self):
        e = classify_external([swing(1, 90, "low"), swing(2, 70, "low")], "H1", 1)
        self.assertEqual([x.price for x in targets_below(e, 100)], [90, 70])

    def test_protected_excluded_from_targets(self):
        e = [External(swing(1, 90, "low"), "H1", "medium", "strong", protected=True)]
        self.assertEqual(targets_below(e, 100), [])


class TestInternal(unittest.TestCase):
    """«الأوردر بلوك هو نفسه سيولة داخلية»."""

    def test_combines_fvg_and_order_block(self):
        g = FVG(2, T0, "bullish", 105, 100)
        ob = OrderBlock(
            index=4, time=T0, direction="bullish", top=98, bottom=94,
            sweep=None, break_index=6, governing_level=0, fvg=None, is_rejection_block=False,
        )
        zones = internal_from([g], [ob])
        self.assertEqual([z.kind for z in zones], ["fvg", "order_block"])

    def test_midpoint_is_the_zone_average(self):
        """«ليه بنقول خط المنتصف؟ لأنه هو متوسط الفراغ»."""
        self.assertEqual(Internal("fvg", "bullish", 105, 100, 0).midpoint, 102.5)

    def test_structure_gate_filters_opposite_zones(self):
        zones = [
            Internal("fvg", "bullish", 105, 100, 1),
            Internal("fvg", "bearish", 95, 90, 2),
        ]
        self.assertEqual([z.direction for z in usable_internal(zones, "bullish")], ["bullish"])
        self.assertEqual([z.direction for z in usable_internal(zones, "bearish")], ["bearish"])

    def test_undefined_structure_yields_nothing(self):
        zones = [Internal("fvg", "bullish", 105, 100, 1)]
        self.assertEqual(usable_internal(zones, "undefined"), [])


class TestCycle(unittest.TestCase):
    """«أخذ انترنال، راح ضرب اكسترنال ⇒ مستمر · ولم يضرب ⇒ احتمال تغيّر»."""

    def setUp(self):
        self.zone = Internal("fvg", "bullish", 102, 100, 0)
        self.ext = classify_external([swing(0, 120, "high")], "H1", proximity=1)

    def test_continuation_when_external_reached(self):
        s = mk(
            (105, 106, 104, 105),
            (105, 106, 101, 103),      # لمس المنطقة 100–102
            (103, 112, 102, 111),
            (111, 121, 110, 120),      # بلغ 120
        )
        r = read_cycle(s, self.zone, self.ext, "bullish", max_bars_to_external=5, start=1)
        self.assertEqual(r.state, "continuation")
        self.assertIn("الاتجاه مستمر", r.detail)

    def test_structure_change_when_external_missed(self):
        s = mk(
            (105, 106, 104, 105),
            (105, 106, 101, 103),
            (103, 108, 102, 104),
            (104, 107, 100, 101),
            (101, 105, 98, 99),
            (99, 103, 95, 96),
            (96, 100, 92, 93),
        )
        r = read_cycle(s, self.zone, self.ext, "bullish", max_bars_to_external=3, start=1)
        self.assertEqual(r.state, "possible_structure_change")
        self.assertIn("احتمال تغيّر الهيكل", r.detail)

    def test_pending_when_zone_untouched(self):
        s = mk((130, 135, 128, 134), (134, 140, 133, 139))
        r = read_cycle(s, self.zone, self.ext, "bullish", max_bars_to_external=5, start=0)
        self.assertEqual(r.state, "pending")

    def test_pending_when_deadline_not_elapsed(self):
        s = mk((105, 106, 104, 105), (105, 106, 101, 103))
        r = read_cycle(s, self.zone, self.ext, "bullish", max_bars_to_external=10, start=1)
        self.assertEqual(r.state, "pending")
        self.assertIn("المهلة لم تنتهِ", r.detail)

    def test_no_valid_external_is_pending(self):
        s = mk((105, 106, 104, 105), (105, 106, 101, 103))
        protected = [External(swing(0, 120, "high"), "H1", "medium", "strong", protected=True)]
        r = read_cycle(s, self.zone, protected, "bullish", max_bars_to_external=5, start=1)
        self.assertEqual(r.state, "pending")
        self.assertIn("لا سيولة خارجية", r.detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
