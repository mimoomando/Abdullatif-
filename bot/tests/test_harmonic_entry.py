"""
اختبارات وصل الهارمونيك بالسلسلة.

⭐ **وموضعُه منصوص:** «عندك نقطة اهتمام من ربع ساعة، فأنا على الدقيقة
أو ثلاث دقائق باخذ موجة، **نقطة انعكاس على الهارمونيك، منها بأكّد**».

فهو تأكيدٌ على الإطار المقابل — لا يولّد نقطة اهتمام ولا يغيّر هدفًا.
"""

import unittest
from datetime import datetime, timedelta

from bot.data import Candle, Series
from bot.primitives.harmonic_entry import best, candidates
from bot.primitives.swings import Swing

T0 = datetime(2026, 9, 14, 10, 0)


def mk(n: int, tf="M3") -> Series:
    """
    سلسلةٌ هادئة بطول `n` — **لا تكسر C ولا تبلغ D**.

    ⚠️ والشموع عند 78 لا عند 90: شمعةٌ قمّتُها 90.1 **تكسر C=90**،
    فتُبطل كلّ نموذج. وقعتُ فيها أوّلَ مرّة.
    """
    return Series(tf, [Candle(T0 + timedelta(minutes=3 * i), 78, 78.1, 77.9, 78)
                       for i in range(n)], symbol="XAUUSD")


def sw(i, price, kind):
    return Swing(i, T0 + timedelta(minutes=3 * i), price, kind)


# A=100 قمّة · B=80 قاع · C=90 قمّة ⇒ تصحيح 0.50 ⇒ امتداد 2.000
#   ضلع B→C = 10 · D = 90 − 20 = 70.00
#   وقف الإغلاق 2.240 ⇒ 67.60 · الوقف الصلب 2.618 ⇒ 63.82
BULL = [sw(0, 100.0, "high"), sw(2, 80.0, "low"), sw(4, 90.0, "high")]
D, HARD = 70.0, 63.82


class TestCandidates(unittest.TestCase):
    def setUp(self):
        self.s = mk(12)

    def test_it_finds_the_pattern_when_D_falls_in_the_zone(self):
        got = candidates(self.s, BULL, "bullish", 69.0, 71.0)
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0].entry, D, places=2)
        self.assertAlmostEqual(got[0].stop, HARD, places=2)

    def test_D_outside_the_zone_is_not_a_confirmation(self):
        """
        ⚠️ نموذجٌ طرفُه بعيدٌ عن المنطقة **إعدادٌ آخر** في مكانٍ آخر من
        الشارت — لا تأكيدٌ لهذه النقطة. وهو الشرط نفسه الذي تفرضه
        `refine.candidates` على النماذج الكلاسيكيّة.
        """
        self.assertEqual(candidates(self.s, BULL, "bullish", 75.0, 80.0), [])
        self.assertEqual(candidates(self.s, BULL, "bullish", 60.0, 65.0), [])

    def test_tolerance_widens_the_zone(self):
        self.assertEqual(candidates(self.s, BULL, "bullish", 71.0, 75.0), [])
        got = candidates(self.s, BULL, "bullish", 71.0, 75.0, tolerance=1.5)
        self.assertEqual(len(got), 1)

    def test_the_wrong_direction_is_dropped(self):
        """«إذا انت فايت **عكس الترند** رح يضربك»."""
        self.assertEqual(candidates(self.s, BULL, "bearish", 69.0, 71.0), [])

    def test_an_unprotected_pattern_is_refused(self):
        """
        ⛔⛔ الدخول من **2.240** وقفُ إغلاقه 2.618 — وهو طرفُ السلّم،
        فلا درجةَ بعده ولا وقفَ صلبًا.

        وقرارُ المستخدم (2026-09-05) أنّ الوقف الصلب شرطُ الدخول. فصفقةٌ
        لا تُحمى لا تُؤخذ — ولو كانت D في قلب المنطقة.

        وتصحيحُ 0.40 يقع في الصفّ الأوّل (0.382–0.48 ⇒ 2.240).
        """
        # A=100 · B=80 · C=88 ⇒ تصحيح 0.40 ⇒ امتداد 2.240 · D = 88 − 17.92
        unprotected = [sw(0, 100.0, "high"), sw(2, 80.0, "low"),
                       sw(4, 88.0, "high")]
        entry = 88.0 - 8.0 * 2.240
        self.assertEqual(
            candidates(self.s, unprotected, "bullish", entry - 1, entry + 1), [])

    def test_a_retrace_below_the_floor_builds_nothing(self):
        """«أقل نسبة مسموح يصحح فيها هي 0.382 — اذا نزل تحت ما في نموذج»."""
        shallow = [sw(0, 100.0, "high"), sw(2, 80.0, "low"), sw(4, 86.0, "high")]
        self.assertEqual(candidates(self.s, shallow, "bullish", 0.0, 1e9), [])

    def test_a_broken_C_invalidates_it(self):
        """«اذا قبل ما يوصل لمنطقة الارتداد **طلع كسر الـC** — نموذج يُلغى»."""
        bars = [Candle(T0 + timedelta(minutes=3 * i), 78, 78.1, 77.9, 78)
                for i in range(12)]
        bars[6] = Candle(bars[6].time, 78, 95.0, 77.9, 94.0)   # فوق C=90
        broken = Series("M3", bars, symbol="XAUUSD")
        self.assertEqual(candidates(broken, BULL, "bullish", 69.0, 71.0), [])


class TestBest(unittest.TestCase):
    def test_it_returns_none_when_nothing_qualifies(self):
        self.assertIsNone(best(mk(12), BULL, "bullish", 10.0, 20.0))

    def test_it_picks_the_tightest_stop(self):
        """
        ⭐ **والأضيقُ هو المختار** — الغرض المنصوص من التدرّج في الأطر
        هو تصغير الوقف: «بلا ترابط 110 نقطة · على الساعة 590 ·
        بترابط الفريمات **10 نقاط**».
        """
        s = mk(30)
        # ثلاثيّةٌ ثانية: C=90 · قاع 75 · قمّة 84 ⇒ تصحيح 0.60 ⇒ 1.618
        #   D = 84 − 9×1.618 = 69.44 · الوقف الصلب 2.240 ⇒ 63.84
        #   فمخاطرتُها 5.60$ دون 6.18$ للأولى
        swings = BULL + [sw(6, 75.0, "low"), sw(8, 84.0, "high")]
        found = candidates(s, swings, "bullish", 0.0, 1e9)
        self.assertGreater(len(found), 1, "لم تُبنَ ثلاثيّةٌ ثانية")
        chosen = best(s, swings, "bullish", 0.0, 1e9)
        self.assertEqual(chosen.risk, min(f.risk for f in found))


class TestItIsWiredButOff(unittest.TestCase):
    """
    ⛔⛔ **مبنيٌّ، مختبَر، مطفأ — قِيس فخسر.**

    على 09-14…15 من شموع المنصّة:

        بلا هارمونيك   5 إعدادات   **+3.94$**
        مع الهارمونيك  4 إعدادات  **−17.36$**   ⇒ **−21.30$**

    وأهمّ من الحصيلة ما كشفه **العدد**: 5 ⇐ 4. فقد قلتُ حين بنيتُه
    إنّ أثرَه «مُضافٌ لا مُزيح» — وقاعدةٌ مُضافة لا تُنقص إعدادًا
    أبدًا. وهو في مسار اللمس المباشر **يستبدل** الدخول والوقف،
    ووقفُه الصلب درجتان خلف D فيتجاوز سقف الـ20$ أحيانًا فيسقط
    الإعداد. **فأزاح رابحًا.**

    انظر `knowledge/analyses/2026-09-20-harmonic-wired.md`.
    """

    def test_the_chain_imports_it(self):
        import pathlib
        src = pathlib.Path("bot/chain.py").read_text(encoding="utf-8")
        self.assertIn("harmonic_entry", src)
        self.assertIn("harmonic_enabled", src)

    def test_it_is_off_by_default(self):
        """⛔ ولا يُعاد تشغيلُه قبل إصلاح الاستبدال وقياسٍ جديد."""
        from bot.chain import ChainConfig
        cfg = ChainConfig(poi_timeframe="M15", confirm_timeframe="M3",
                          spread=0.3)
        self.assertFalse(cfg.harmonic_enabled,
                         "أُعيد تشغيلُ قاعدةٍ لم يسندها القياس")

    def test_it_can_be_switched_on_in_one_line(self):
        """والقياسُ القادم يحتاج تشغيلَه بسطر — فلا يُحذف الكود."""
        from bot.chain import ChainConfig
        cfg = ChainConfig(poi_timeframe="M15", confirm_timeframe="M3",
                          spread=0.3, harmonic_enabled=True)
        self.assertTrue(cfg.harmonic_enabled)


if __name__ == "__main__":
    unittest.main(verbosity=2)
