"""
اختبارات أنواع الفراغ الجديدة — BPR والفراغ المنعكس — والدخول من
منتصف الأوردر بلوك الكبير. كلها من البثّ ٣ (2026-09-12).
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.fvg import (
    BPR,
    FVG,
    Inversion,
    find_bprs,
    find_fvgs,
    find_inversions,
)

T0 = datetime(2026, 9, 14, 9, 0)


def mk(*rows, tf="M15"):
    return Series(tf, [
        Candle(T0 + timedelta(minutes=15 * i), o, h, l, c)
        for i, (o, h, l, c) in enumerate(rows)
    ])


def gap(index, direction, top, bottom):
    return FVG(index, T0 + timedelta(minutes=15 * index), direction, top, bottom)


# ═══════════════════════ الفراغ المنعكس ═══════════════════════


class TestInversionConditions(unittest.TestCase):
    """
    ⭐ «ما بتعامل مع الفير فالو السلبية في حال السوق عندي صاعد.
    ممكن تكون **نقطة ارتكاز** عندي **إذا طلع أغلق فوق وعاد الاختبار**»
    """

    def test_a_gap_with_the_structure_is_never_a_candidate(self):
        """الموافق يُتداول كما هو ولا يحتاج انقلابًا."""
        s = mk(*[(100, 101, 99, 100)] * 5)
        self.assertEqual(find_inversions(s, [gap(0, "bullish", 105, 100)],
                                         "bullish"), [])

    def test_a_close_beyond_it_alone_is_not_enough(self):
        """⚠️ شرطان: إغلاقٌ خلفه **وإعادة اختبار**."""
        s = mk((100, 101, 99, 100),
               (100, 112, 100, 111))        # أغلق فوق 105 ولم يعد
        inv = find_inversions(s, [gap(0, "bearish", 105, 100)], "bullish")
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0].closed_beyond_at, 1)
        self.assertFalse(inv[0].confirmed)

    def test_close_then_retest_confirms_it(self):
        s = mk((100, 101, 99, 100),
               (100, 112, 100, 111),        # 1 — إغلاق فوق 105
               (111, 112, 103, 104))        # 2 — عاد فلامس 100–105
        inv = find_inversions(s, [gap(0, "bearish", 105, 100)], "bullish")
        self.assertTrue(inv[0].confirmed)
        self.assertEqual(inv[0].retested_at, 2)

    def test_a_close_inside_it_is_mitigation_not_a_breach(self):
        """«إغلاقٌ في منتصفه مخالطةٌ لا اختراق»."""
        s = mk((100, 101, 99, 100),
               (100, 104, 100, 103))        # أغلق **داخل** 100–105
        self.assertEqual(find_inversions(s, [gap(0, "bearish", 105, 100)],
                                         "bullish"), [])

    def test_the_new_direction_is_the_structures(self):
        s = mk((100, 101, 99, 100), (100, 112, 100, 111),
               (111, 112, 103, 104))
        inv = find_inversions(s, [gap(0, "bearish", 105, 100)], "bullish")
        self.assertEqual(inv[0].direction, "bullish")
        self.assertNotEqual(inv[0].direction, inv[0].source.direction)

    def test_the_bearish_mirror(self):
        s = mk((100, 101, 99, 100),
               (100, 100, 88, 89),          # أغلق تحت 95
               (89, 97, 89, 96))            # عاد فلامس 95–100
        inv = find_inversions(s, [gap(0, "bullish", 100, 95)], "bearish")
        self.assertTrue(inv[0].confirmed)
        self.assertEqual(inv[0].direction, "bearish")

    def test_an_undefined_structure_yields_nothing(self):
        """لا انقلاب بلا اتجاهٍ يُنقلب إليه."""
        s = mk(*[(100, 101, 99, 100)] * 3)
        self.assertEqual(find_inversions(s, [gap(0, "bearish", 105, 100)],
                                         "undefined"), [])

    def test_geometry_comes_from_the_source_gap(self):
        inv = Inversion(gap(0, "bearish", 105, 100), "bullish", 1, 2)
        self.assertEqual((inv.bottom, inv.top, inv.midpoint), (100, 105, 102.5))
        self.assertTrue(inv.contains(100) and inv.contains(105))

    def test_the_render_says_whether_it_is_confirmed(self):
        pending = Inversion(gap(0, "bearish", 105, 100), "bullish", 1)
        done = Inversion(gap(0, "bearish", 105, 100), "bullish", 1, 2)
        self.assertIn("بانتظار", pending.render())
        self.assertIn("مؤكَّدة", done.render())


class TestInversionIsNotAnEntryByItself(unittest.TestCase):
    """
    ⛔ الشرط الثالث — «مع **تأكيد من الفريم المرتبط**» — ليس من شأن
    هذه البدائيّة. فلا تدّعي `confirmed` أنه استُوفي.
    """

    def test_the_docstring_names_the_missing_condition(self):
        self.assertIn("الفريم المرتبط", Inversion.__doc__)

    def test_the_module_does_not_decide_entries(self):
        import bot.primitives.fvg as m
        with open(m.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("order_send", "def entry(", "def enter("):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, src)


# ═══════════════════════ BPR ═══════════════════════


class TestBPR(unittest.TestCase):
    """
    ⭐ «نقطة دخوله اللي هي **البي بي آر مع الفير فالو جاب السلبية**…
    **ستوبي هيدا القمّة عليها بقليل**»
    """

    def test_two_opposite_overlapping_gaps_make_one(self):
        a = gap(2, "bullish", 110, 100)
        b = gap(5, "bearish", 108, 102)
        got = find_bprs([a, b])
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0].bottom, got[0].top), (102, 108))

    def test_the_zone_is_the_overlap_not_the_union(self):
        got = find_bprs([gap(2, "bullish", 110, 100), gap(5, "bearish", 120, 105)])
        self.assertEqual((got[0].bottom, got[0].top), (105, 110))

    def test_same_direction_gaps_are_not_a_bpr(self):
        self.assertEqual(find_bprs([gap(2, "bullish", 110, 100),
                                    gap(5, "bullish", 108, 102)]), [])

    def test_opposite_but_apart_is_not_a_bpr(self):
        """⚠️ التراكب شرطٌ لا التجاور."""
        self.assertEqual(find_bprs([gap(2, "bullish", 110, 100),
                                    gap(5, "bearish", 90, 80)]), [])

    def test_touching_edges_are_not_an_overlap(self):
        """حدٌّ يلمس حدًّا تراكبه صفر — و`min_overlap=0` ترفضه."""
        self.assertEqual(find_bprs([gap(2, "bullish", 110, 100),
                                    gap(5, "bearish", 100, 90)]), [])

    def test_a_minimum_overlap_can_be_required(self):
        gaps = [gap(2, "bullish", 110, 100), gap(5, "bearish", 103, 90)]
        self.assertEqual(len(find_bprs(gaps, min_overlap=1.0)), 1)
        self.assertEqual(find_bprs(gaps, min_overlap=5.0), [])

    def test_each_gap_is_paired_at_most_once(self):
        """فلا تولّد سلسلةٌ طويلة تراكباتٍ وهميّة."""
        gaps = [gap(1, "bullish", 110, 100), gap(2, "bearish", 108, 102),
                gap(3, "bearish", 109, 101)]
        got = find_bprs(gaps)
        self.assertEqual(len(got), 1)

    def test_the_direction_comes_from_the_later_gap(self):
        """🔶 مشتقٌّ من مثالٍ واحد: تداول بيعًا مع الفراغ السلبيّ الأحدث."""
        got = find_bprs([gap(2, "bullish", 110, 100), gap(5, "bearish", 108, 102)])
        self.assertEqual(got[0].direction, "bearish")
        got = find_bprs([gap(2, "bearish", 110, 100), gap(5, "bullish", 108, 102)])
        self.assertEqual(got[0].direction, "bullish")

    def test_the_param_records_that_this_rests_on_one_example(self):
        from bot import params as P
        self.assertEqual(P.BPR_DIRECTION_FROM.value, "latest_gap")
        self.assertEqual(P.BPR_DIRECTION_FROM.origin, "DERIVED")
        self.assertIn("مثالٌ واحد", P.BPR_DIRECTION_FROM.note)

    def test_the_stop_sits_beyond_the_far_edge(self):
        """«ستوبي هيدا القمّة عليها بقليل»."""
        sell = BPR(gap(2, "bullish", 110, 100), gap(5, "bearish", 108, 102), 108, 102)
        self.assertAlmostEqual(sell.stop_for(2.0), 110.0)
        buy = BPR(gap(2, "bearish", 110, 100), gap(5, "bullish", 108, 102), 108, 102)
        self.assertAlmostEqual(buy.stop_for(2.0), 100.0)

    def test_a_negative_buffer_is_refused(self):
        p = find_bprs([gap(2, "bullish", 110, 100), gap(5, "bearish", 108, 102)])[0]
        with self.assertRaises(ValueError):
            p.stop_for(-1.0)

    def test_index_is_when_the_overlap_completed(self):
        p = find_bprs([gap(2, "bullish", 110, 100), gap(5, "bearish", 108, 102)])[0]
        self.assertEqual(p.index, 5)

    def test_midpoint_and_size(self):
        p = find_bprs([gap(2, "bullish", 110, 100), gap(5, "bearish", 108, 102)])[0]
        self.assertEqual((p.size, p.midpoint), (6, 105))

    def test_the_render_carries_the_numbers(self):
        p = find_bprs([gap(2, "bullish", 110, 100), gap(5, "bearish", 108, 102)])[0]
        self.assertIn("BPR", p.render())
        self.assertIn("102", p.render())

    def test_no_gaps_is_no_bprs(self):
        self.assertEqual(find_bprs([]), [])

    def test_the_bpr_outranks_the_gap_it_sits_inside(self):
        """
        ⚠️ السلسلة تأخذ `zones[-1]`، والـBPR يحمل فهرس فراغه الأحدث
        فيتساويان. فالأسبقيّة **صريحة** لا رهينةَ ترتيب الإدخال:
        الأضيق يتقدّم، وهو ما عيّنه هو منطقةَ دخول.
        """
        from bot.primitives.liquidity_map import internal_from
        a, b = gap(2, "bullish", 110, 100), gap(5, "bearish", 108, 102)
        p = find_bprs([a, b])[0]
        zones = internal_from([a, b], (), [p])
        self.assertEqual(zones[-1].kind, "bpr")

    def test_the_order_of_arguments_does_not_decide_precedence(self):
        """العطب الذي كان: ترجيحٌ يتغيّر بأي تعديلٍ لاحق بلا أن يشكو اختبار."""
        from bot.primitives.liquidity_map import internal_from
        a, b = gap(2, "bullish", 110, 100), gap(5, "bearish", 108, 102)
        p = find_bprs([a, b])[0]
        self.assertEqual(internal_from([a, b], (), [p])[-1].kind,
                         internal_from([b, a], (), [p])[-1].kind)

    def test_it_works_on_gaps_found_from_a_real_series(self):
        """⚠️ لا يُختبَر على فراغاتٍ مصنوعة وحدها."""
        s = mk((10, 100, 9, 99), (99, 130, 98, 128), (128, 140, 105, 138),
               (138, 140, 137, 139), (139, 139, 100, 101), (101, 103, 90, 92))
        found = find_fvgs(s)
        self.assertTrue(found)
        for p in find_bprs(found):
            self.assertGreater(p.size, 0)
            self.assertNotEqual(p.first.direction, p.second.direction)


# ═══════════════════════ منتصف الأوردر بلوك الكبير ═══════════════════════


class TestLargeBlockMidpointEntry(unittest.TestCase):
    """
    ⭐ «لمّا بكون **بهالشكل الكبير** بحدّد منطقة المنتصف لنتعامل مع
    منطقة المنتصف فيها» — والعتبة **بلا رقم**.
    """

    def _ob(self, direction="bullish", top=110.0, bottom=100.0):
        from bot.primitives.liquidity import Sweep
        from bot.primitives.swings import Swing
        low = direction == "bullish"
        s = Swing(0, T0, 99.0, "low" if low else "high")
        from bot.primitives.order_block import OrderBlock
        return OrderBlock(
            index=2, time=T0, direction=direction, top=top, bottom=bottom,
            sweep=Sweep(swept_swing=s, penetration_index=1, reclaim_index=2,
                        time=T0, side="sell_side" if low else "buy_side",
                        level=99.0, extreme=98.0),
            break_index=3, governing_level=115.0,
            fvg=gap(2, direction, top, bottom), is_rejection_block=False,
        )

    def test_without_a_threshold_the_near_edge_stands(self):
        """None ⇒ غير مطبَّق — وهو الافتراضيّ."""
        self.assertEqual(self._ob().entry_for(), 110.0)
        self.assertEqual(self._ob().entry_for(None), 110.0)

    def test_a_block_larger_than_the_threshold_enters_at_its_midpoint(self):
        self.assertEqual(self._ob().entry_for(5.0), 105.0)

    def test_a_block_at_the_threshold_is_not_large(self):
        """الحدّ نفسه ليس تجاوزًا له."""
        self.assertEqual(self._ob().entry_for(10.0), 110.0)

    def test_the_bearish_near_edge_is_the_bottom(self):
        b = self._ob("bearish")
        self.assertEqual(b.near_edge, 100.0)
        self.assertEqual(b.entry_for(5.0), 105.0)

    def test_the_midpoint_halves_the_risk(self):
        """
        ⭐ السبب: الوقف يبقى خلف الطرف البعيد، فالدخول من المنتصف
        ينصّف المخاطرة — وهو معنى «التدرّج بالفريمات لتصغير الوقف».
        """
        o = self._ob()
        stop = o.stop_for(0.0)
        self.assertAlmostEqual(abs(o.entry_for(None) - stop), 10.0)
        self.assertAlmostEqual(abs(o.entry_for(5.0) - stop), 5.0)

    def test_the_threshold_is_undefined_in_params(self):
        """⛔ «كبير» بلا رقم ⇒ لا يُخترع له واحد."""
        from bot import params as P
        self.assertIsNone(P.OB_LARGE_THRESHOLD.value)
        self.assertEqual(P.OB_LARGE_THRESHOLD.origin, "UNDEFINED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
