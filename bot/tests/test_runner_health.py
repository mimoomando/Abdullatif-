"""
حارسا الصحّة — وكلاهما بُني بعد عطبٍ وقع لا احتياطًا.

⛔ في أسبوع 09-14 سقطت منصّة MT5 ليلة الثلاثاء. فـ:
   · صمتت الحلقة ثلاثة أيّام، والنافذة بقيت حيّةَ المظهر
   · وانتفخ errors.jsonl إلى 13.3 ميغابايت من نسخٍ متطابقة
     مقابل 0.3 ميغابايت من القرارات
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from bot.runner import (Heartbeat, OffsetProbe, Recorder, RunConfig,
                        alarm_passes, evidence)


class TestAStaleTickIsNotATimezone(unittest.TestCase):
    """
    ⛔⛔⛔ **العطبُ الأخطر من ليلة 09-21 — وقد مرّ صامتًا.**

    الإزاحةُ تُقاس `tick.time − now`. فتكّةٌ عمرُها ساعة تعطي **+2
    مكان +3** — رقمٌ مشروعٌ فيُقبَل. وقد وقع حرفيًّا: قِيس +3 والسوقُ
    حيّ، ثمّ +2 بعد إعادةِ تشغيلٍ والتغذيةُ واقفة.

    ⚠️ **والإزاحة تُقاس مرّةً وتبقى** — فساعةُ غلطٍ تُختم على كلّ
    قرارٍ في الأسبوع، وتبدو الأوقاتُ سليمةً وهي مزاحة.
    """

    class Feed:
        """جسرٌ تُملي عليه: أتتقدّم التكّةُ أم تقف؟"""

        def __init__(self, moving: bool, offset: float = 3.0):
            self.moving = moving
            self.offset = offset
            self.t = datetime(2026, 9, 21, 22, 0)
            self.measured = 0

        def last_tick_time(self):
            if self.moving:
                self.t += timedelta(seconds=30)
            return self.t

        def measure_server_offset(self):
            self.measured += 1
            return self.offset

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rec = Recorder(RunConfig(out_dir=self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_frozen_feed_yields_no_offset_at_all(self):
        feed, probe = self.Feed(moving=False), OffsetProbe(min_gap=0)
        for _ in range(40):
            probe.read(feed, self.rec)
        self.assertIsNone(probe.value, "قُبلت إزاحةٌ من تغذيةٍ واقفة")
        self.assertEqual(feed.measured, 0, "قِيست أصلًا — وما كان يجوز")

    def test_a_moving_feed_is_measured_normally(self):
        feed, probe = self.Feed(moving=True), OffsetProbe(min_gap=0)
        probe.read(feed, self.rec)                  # العيّنة الأولى
        probe.read(feed, self.rec)                  # تقدّمت ⇒ تُقاس
        self.assertEqual(probe.value, 3.0)

    def test_one_sample_is_never_enough(self):
        """⭐ عيّنةٌ واحدة لا تفرّق بين حيٍّ وواقف — فلا تُقبل."""
        feed, probe = self.Feed(moving=True), OffsetProbe(min_gap=0)
        self.assertIsNone(probe.read(feed, self.rec))
        self.assertEqual(feed.measured, 0)

    def test_the_wait_between_samples_is_respected(self):
        feed, probe = self.Feed(moving=True), OffsetProbe(min_gap=120)
        t = datetime(2026, 9, 21, 23, 0)
        probe.read(feed, self.rec, now=t)
        probe.read(feed, self.rec, now=t + timedelta(seconds=60))
        self.assertIsNone(probe.value, "قِيس قبل انقضاء المهلة")
        probe.read(feed, self.rec, now=t + timedelta(seconds=130))
        self.assertEqual(probe.value, 3.0)

    def test_a_frozen_feed_is_logged_once_it_backs_off(self):
        feed, probe = self.Feed(moving=False), OffsetProbe(min_gap=0)
        for _ in range(40):
            probe.read(feed, self.rec)
        path = os.path.join(self.tmp.name, "errors.jsonl")
        with open(path, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        self.assertTrue(rows, "سكت تمامًا عن تغذيةٍ واقفة")
        self.assertLess(len(rows), 12, "أغرق السجلّ بالنسخ")


class TestTheAlarmShowsEvidenceNotAdvice(unittest.TestCase):
    """
    ⛔⛔ **ليلة 09-21 — الرسالةُ وصفت دواءً واحدًا لحالتين.**

    قالت «أعد تشغيل البوت»، فأُعيد مرّتين، والعطبُ لم يكن فيه:
    التغذيةُ توقّفت عند 21:45. ⇒ فلا تُقترح أدوية — تُعرض الحقيقةُ
    التي تفصل الحالتين: **هل تقدّم ختمُ التكّة؟**
    """

    NOW = datetime(2026, 9, 21, 23, 35)

    def test_a_stopped_feed_is_named_so_the_user_does_not_restart(self):
        line = evidence(tick=self.NOW - timedelta(minutes=97), now=self.NOW)
        self.assertIn("FEED STOPPED", line)
        self.assertIn("97 min ago", line)

    def test_a_live_feed_points_at_the_bridge_instead(self):
        line = evidence(tick=self.NOW - timedelta(minutes=1), now=self.NOW)
        self.assertIn("feed alive", line)
        self.assertNotIn("FEED STOPPED", line)

    def test_a_silent_bridge_is_not_dressed_up_as_a_closed_market(self):
        self.assertIn("UNKNOWN", evidence(tick=None, now=self.NOW))

    def test_it_prints_the_last_candle_to_compare_with_the_chart(self):
        line = evidence(bars={"M15": datetime(2026, 9, 21, 21, 45)},
                        tick=self.NOW, now=self.NOW)
        self.assertIn("M15 21:45", line)

    def test_the_alarm_carries_the_evidence(self):
        h = Heartbeat(alarm_after=1, every_seconds=60)
        msg = h.beat(0, bars={"M15": datetime(2026, 9, 21, 21, 45)},
                     tick=self.NOW - timedelta(minutes=97), now=self.NOW)
        self.assertIn("FEED STOPPED", msg)
        self.assertIn("M15 21:45", msg)
        self.assertTrue(msg.splitlines()[0].isascii())


class TestTheAlarmMatchesTheDataRhythm(unittest.TestCase):
    """
    ⛔⛔ **ليلة 09-21 — الحارسُ صرخ اثنتي عشرةَ مرّةً كلَّ ربع ساعة.**

    والبوتُ سليم: لا يُكتب قرارٌ إلّا عند إغلاق شمعةٍ جديدة، وأسرعُ
    إطارٍ ربعُ ساعة، والتمريرةُ دقيقة. فسقفُ «ثلاثِ تمريرات» كان
    **أقصرَ من إيقاع البيانات نفسِه** — إنذارٌ كاذبٌ بالبناء.
    """

    def test_a_quarter_hour_frame_is_allowed_to_be_quiet(self):
        after = alarm_passes({"M15": "M3"}, every_seconds=60)
        self.assertGreater(after, 15, "ربعُ ساعةٍ من الصمت ليس عطبًا")
        self.assertEqual(after, 31)                  # شمعتان + واحدة

    def test_the_fastest_frame_sets_the_ceiling_not_the_slowest(self):
        """⭐ H4 يصمت أربعَ ساعاتٍ وهو سليم — فلا يُقاس به شيء."""
        fast = alarm_passes({"M15": "M3"}, 60)
        both = alarm_passes({"H4": "M30", "H1": "M5", "M15": "M3"}, 60)
        self.assertEqual(both, fast)

    def test_a_slower_pass_needs_fewer_passes(self):
        self.assertEqual(alarm_passes({"M15": "M3"}, 300), 7)   # 5د ⇒ 3/شمعة

    def test_it_never_drops_below_the_floor(self):
        self.assertGreaterEqual(alarm_passes({"M15": "M3"}, 3600),
                                Heartbeat.ALARM_AFTER)

    def test_nonsense_input_falls_back_instead_of_crashing(self):
        self.assertEqual(alarm_passes({}, 60), Heartbeat.ALARM_AFTER)
        self.assertEqual(alarm_passes({"M15": "M3"}, 0), Heartbeat.ALARM_AFTER)
        self.assertEqual(alarm_passes({"???": "M3"}, 60), Heartbeat.ALARM_AFTER)

    def test_the_real_silence_still_reaches_the_alarm(self):
        """والسقفُ ارتفع — ولم يُلغَ. فانقطاعٌ حقيقيّ يُكشف بعده."""
        h = Heartbeat(alarm_after=alarm_passes({"M15": "M3"}, 60))
        for _ in range(30):
            self.assertIsNone(h.beat(0))
        self.assertIsNotNone(h.beat(0))

    def test_the_alarm_says_minutes_because_passes_mean_nothing(self):
        h = Heartbeat(alarm_after=2, every_seconds=60)
        h.beat(0)
        msg = h.beat(0)
        self.assertIn("2 MIN", msg)
        self.assertTrue(msg.splitlines()[0].isascii())


class TestHeartbeatSpeaksWhenSilent(unittest.TestCase):
    """الصمتُ نفسه يُطبع — وسطرٌ يتغيّر هو وحده ما يثبت الحياة."""

    def test_a_working_pass_says_nothing(self):
        h = Heartbeat()
        self.assertIsNone(h.beat(3))
        self.assertIsNone(h.beat(1))

    def test_it_stays_quiet_below_the_threshold(self):
        h = Heartbeat(alarm_after=3)
        self.assertIsNone(h.beat(0))
        self.assertIsNone(h.beat(0))

    def test_it_alarms_on_the_threshold_pass(self):
        h = Heartbeat(alarm_after=3)
        h.beat(0); h.beat(0)
        msg = h.beat(0)
        self.assertIsNotNone(msg)
        self.assertIn("NO NEW DATA", msg)

    def test_it_keeps_alarming_every_pass_not_once(self):
        """
        ⭐ جوهرُ الإصلاح: إنذارٌ **يتكرّر**.

        فإنذارٌ مرّةً واحدة يصعد في الشاشة ويختفي، وتعود النافذة
        ساكنةً — وهي الحالة نفسها التي كلّفتنا ثلاثة أيّام.
        """
        h = Heartbeat(alarm_after=2)
        h.beat(0)
        msgs = [h.beat(0) for _ in range(5)]
        self.assertTrue(all(m for m in msgs), "الإنذار سكت قبل أن يعود التسجيل")
        self.assertIn("6 تمريرة", msgs[-1])       # والعدّاد يتزايد

    def test_recovery_is_announced_once_then_silence_returns(self):
        h = Heartbeat(alarm_after=2)
        h.beat(0); h.beat(0)
        back = h.beat(2)
        self.assertIn("عاد التسجيل", back)
        self.assertIsNone(h.beat(2))

    def test_a_single_good_pass_resets_the_counter(self):
        h = Heartbeat(alarm_after=3)
        h.beat(0); h.beat(0); h.beat(1)
        self.assertIsNone(h.beat(0))
        self.assertIsNone(h.beat(0))

    def test_every_alarm_opens_with_a_pure_ascii_line(self):
        """
        ⛔⛔ **وحارسٌ لا يُقرأ ليس حارسًا.**

        نافذة `cmd` القديمة تعرض العربيّة **مقلوبة** — رآها المستخدم
        كذلك أوّلَ تشغيلٍ بعد التحديث («ارّارق 0 لجَـسّ» مكان «سُجّل 0
        قرارًا»). فلو صرخ الحارسُ بالعربيّة وحدها لَمرّ الإنذارُ أمام
        عينه **غيرَ مقروء** — وهو العطب نفسه الذي بُني الحارسُ له.

        ⇒ فأوّلُ سطرٍ من كلّ رسالةٍ **لاتينيٌّ خالص**، لا يعتمد على
        محرفٍ قد لا يُرسم ولا على اتّجاهٍ قد يُقلب.
        """
        h = Heartbeat(alarm_after=2)
        h.beat(0)
        messages = [h.beat(0), h.beat(0), h.beat(5)]   # إنذار · إنذار · تعافٍ
        for msg in messages:
            with self.subTest(msg=msg):
                self.assertIsNotNone(msg)
                first = msg.splitlines()[0]
                self.assertTrue(first.isascii(),
                                f"أوّلُ سطرٍ ليس لاتينيًّا خالصًا: {first!r}")
                self.assertTrue(first.strip(), "أوّلُ سطرٍ فارغ")


class TestErrorLogFoldsRepeats(unittest.TestCase):
    """المتطابق المتتالي يُكتب مرّةً، ثم يُعَدّ."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.rec = Recorder(RunConfig(out_dir=self.dir, save_charts=False,
                                      save_dossiers=False))

    def _rows(self):
        p = self.rec.cfg.errors_path
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_the_first_one_carries_its_trace(self):
        self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertIn("trace", rows[0])

    def test_identical_repeats_are_muted(self):
        for _ in range(50):
            self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        self.assertEqual(len(self._rows()), 1, "المكرَّر كُتب مرّةً بعد أخرى")

    def test_one_counting_line_lands_every_hundred(self):
        for _ in range(201):
            self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        rows = self._rows()
        self.assertEqual([r.get("repeats") for r in rows], [None, 100, 200])
        self.assertNotIn("trace", rows[1])        # سطرُ عدٍّ لا تتبُّع

    def test_a_different_error_is_never_folded_behind_an_old_one(self):
        """⛔ ولا يُطوى عطبٌ جديد خلف قديم — وإلّا لأخفى الحارسُ ما جاء له."""
        for _ in range(50):
            self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        self.rec.write_error("pair:H1", ValueError("رمزٌ غير معروف"))
        rows = self._rows()
        self.assertEqual(len(rows), 2)
        self.assertIn("trace", rows[-1])

    def test_rotating_pairs_are_each_folded_on_their_own(self):
        """
        ⭐⭐ **الحالة التي أسقطت أوّل صياغةٍ لهذا الإصلاح.**

        الأزواج تتناوب، فمقارنةُ الخطأ بسابقه وحده لا تطوي شيئًا.
        والعدّ يجب أن يكون **لكل بصمةٍ على حدة**.
        """
        for i in range(300):
            self.rec.write_error(f"pair:{['H4', 'H1', 'M15'][i % 3]}",
                                 RuntimeError("IPC send failed"))
        rows = self._rows()
        self.assertEqual(sum(1 for r in rows if "trace" in r), 3)
        self.assertEqual(len(rows), 3, "التناوبُ أفلت من الطيّ")

    def test_the_same_text_from_a_different_place_is_not_folded(self):
        for _ in range(20):
            self.rec.write_error("pair:H1", RuntimeError("IPC send failed"))
        self.rec.write_error("pair:M15", RuntimeError("IPC send failed"))
        self.assertEqual(len(self._rows()), 2)

    def test_the_week_that_caused_this_would_have_stayed_small(self):
        """
        ⭐ القياس: 13.3 ميغابايت صارت كم؟

        ثلاثة أزواج × تمريرةٍ كل دقيقة × ثلاثة أيّام ≈ 12,960 خطأ.
        """
        for i in range(12960):
            self.rec.write_error(f"pair:{['H4','H1','M15'][i % 3]}",
                                 RuntimeError("IPC send failed"))
        size = os.path.getsize(self.rec.cfg.errors_path)
        self.assertLess(size, 200_000, f"الملفّ ما زال ضخمًا: {size} بايت")


if __name__ == "__main__":
    unittest.main(verbosity=2)
