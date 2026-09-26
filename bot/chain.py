"""
سلسلة القرار — تجمّع البدائيات في التسلسل الذي وصفه درس ترابط الفريمات.

╔══════════════════════════════════════════════════════════════════╗
║  ١. الهيكل على إطار نقطة الاهتمام                                 ║
║  ٢. نقطة اهتمام **مع اتجاه الهيكل** (فراغ أو أوردر بلوك)          ║
║  ٣. وصول السعر إليها                                             ║
║  ٤. الموقع مقبول من بوابة الـ50%                                  ║
║  ٥. النزول إلى **الإطار المقابل** من جدول الأزواج                  ║
║  ٦. إمّا دخول من اللمس (بشرط التسلسل) أو نموذج انعكاسي مفعَّل      ║
║  ٧. هدف صالح على السيولة الخارجية                                ║
║  ٨. بوابة المخاطرة — حد المراكز                                   ║
╚══════════════════════════════════════════════════════════════════╝

    «ما فيك تيجي من اليومي فورًا تفوت خمس دقائق… في ترابط.
     إذا ما أعطاني من الساعة **ما بفوت**»

كل خطوة تُسجَّل كفحص بدليله ومصدره — فالنتيجة `TradeRationale` جاهزة
للعرض في تيليجرام وللسجل اليومي.

**السلسلة تتوقف عند أول فشل** وتسجّله: معرفة أول مانع أنفع من قائمة
فحوص لا معنى لها بعد سقوط ما قبلها.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional, Sequence

from .data import Series
from .primitives.fibonacci import Impulse, measure
from .primitives.fvg import FVG, find_bprs, find_fvgs, find_inversions
from .primitives.liquidity import find_sweeps
from .primitives.liquidity_map import (
    External,
    Internal,
    classify_external,
    internal_from,
    mark_swept,
    targets_above,
    targets_below,
    usable_internal,
)
from .primitives.harmonic_entry import HarmonicEntry, best as best_harmonic
from .primitives.higher_poi import (
    required_for as higher_poi_needed,
    support as higher_support,
)
from .primitives.order_block import (
    OrderBlock,
    find_order_blocks,
    qualifies_for_direct_touch,
    stop_buffer,
    update_states,
)
from .primitives.line_chart import rejected as line_rejected, survivors
from .primitives.patterns import activate, entry_plan, find_all
from .primitives.refine import refine
from .primitives.ob_lifecycle import trace_all
from .primitives.structure import classify_trend, describe_trend
from .primitives.swings import Swing, find_swings
from .reporting import TradeRationale
from .trail import ladder as trail_ladder

Disposition = Literal["taken", "blocked", "rejected"]

MAX_TARGET_RR = 3.0   # «واحد على ثلاثة يكون ماكسيموم» — ترابط الفريمات

# ⭐ عددُ الأهداف المعلَنة — **منطوقٌ بالعدّ** (الأوردر بلوك ج2 ≈19:25):
#
#     «الأهداف تبعت الأوردر بلوك هي القيعان السابقة — واحد، اثنين،
#      ثلاثة، **أربعة**. يعني أربع أهداف. بدك الخامس؟ **لا، ما بيمشي
#      الحال**»
#
# ⛔ وكان هنا `3` عاريًا بلا مصدر. فالأربعة **تصحيحُ رقمٍ مخترَع**، لا
#    توسيعُ سقف.
MAX_TARGETS = 4


@dataclass
class ChainConfig:
    poi_timeframe: str
    confirm_timeframe: str
    spread: float
    swing_lookback: int = 1
    thinning_proximity: float = 2.0
    pattern_tolerance: float = 1.5
    require_containment: bool = False      # D1 — غير محسوم
    # ⭐ **رُفع حدّ المراكز** (المستخدم 2026-09-20): «لا أريد حدًّا».
    #    `None` = بلا سقف. وما يحكم الآن هو الدولار لا العدد — انظر
    #    `daily_loss_limit` أدناه.
    open_positions: int = 0
    max_open_positions: Optional[int] = None

    # ⛔ **سقفُ خسارة اليوم — 100$** (المستخدم 2026-09-20). وبلغَه ⇒ لا
    #    إعداد جديد يُعلَن بقيّته. و`daily_loss` حصيلةُ اليوم بالدولار،
    #    يمرّرها المشغّل من قرارات اليوم نفسِها مصحَّحةً بـ`replay`.
    #    ⚠️ وهي **موجبةٌ ربحًا وسالبةٌ خسارة** — فالبلوغ عند ‎−100.
    daily_loss: float = 0.0
    daily_loss_limit: Optional[float] = 100.0

    # T2 — «درجتان» و«الدولار كاملًا» (المستخدم 2026-08-27) ⇒ هامش 2.00
    stop_degrees: Optional[float] = 2.0
    degree_value: Optional[float] = 1.00

    # البثّ المباشر: بوابة الـ50% تُقاس بالإغلاق لا باللمس
    gate_by_close: bool = True

    # ⭐⭐ اختبار الخطّ — «هيدا مش دبل بتم» (البثّ ٣ ≈20:05).
    # النموذج الذي تصنعه الذيول وحدها يُردّ. اعتراضٌ لا استبدال.
    line_chart_veto: bool = True

    # ⭐⭐ تنقيح الدخول داخل المنطقة — أعلى بندٍ قِسنا كلفته بالدولار.
    # «بدون تأكيد ما بنصح» (البثّ ٣ ≈1:10:26). ويُعطَّل بسطر.
    refine_entry: bool = True
    # سماحية احتواء طرف النموذج في المنطقة. صفرٌ = داخلها تمامًا.
    #
    # ⛔ **قِيست بالإعداد الحيّ (2026-09-20، بالبوّابتين) ولم تُغيَّر:**
    #
    #     0$ · 1$ · 2$   ⇒  6 إعدادات · 2 هدف · 4 وقف   −2.32$
    #     3$             ⇒  6 إعدادات · 2 هدف · 4 وقف   +0.16$
    #
    # فالعددُ واحدٌ في الأربعة، والفارقُ 2.48$ على ستّ صفقات. وتفصيلُ
    # المسارات عند 3$ يقلبها: «منقَّح» ثلاثةُ قراراتٍ بـ‎−6.29$، و«من
    # حدّ المنطقة» سبعةَ عشرَ بـ‎+6.45$ — فالمنقَّحُ هو الخاسر. ولا
    # هضبةَ ولا قمّةٌ قرب 5.56$، فالرقم مصادفة.
    refine_tolerance: float = 0.0
    # ⭐ يبتلع اختبارُ الاحتواء **وقفَ المنطقة** لا قاعَها وحده.
    #
    # ⛔ **مطفأٌ حتّى يُقاس** — ولا يُشغَّل بالظنّ. وهو ليس سماحيّةً
    # تُختار بل **حدُّ المخاطرة القائم**: البوت يخاطر إلى `zone_stop`
    # على كلّ حال، فنموذجٌ قاعُه فوقه ليس «في مكانٍ آخر من الشارت».
    # وأثرُه إمّا وقفٌ أضيق وإمّا لا شيء — انظر `refine.py`.
    #
    # 🔶 والقياسُ يحتاج MT5 على جهاز المستخدم:
    #   python -m bot.backtest --rule refine-floor --from ... --detail
    refine_floor_to_stop: bool = False
    # عتبة «الأوردر بلوك الكبير» ⇒ الدخول من منتصفه. None = غير مطبَّقة
    # (البثّ ٣ ≈14:41 — «كبير» بلا رقم).
    ob_large_threshold: Optional[float] = None

    # ⭐⭐ الهارمونيك — **تأكيدٌ على الإطار المقابل، لا استراتيجيّة موازية**:
    #
    #     «عندك نقطة اهتمام من ربع ساعة، فأنا على الدقيقة أو ثلاث
    #      دقائق باخذ موجة، **نقطة انعكاس على الهارمونيك، منها بأكّد**»
    #
    # فلا يولّد نقطةَ اهتمام ولا يغيّر هدفًا — يعطي الدخول ووقفَه حين
    # يقع D داخل المنطقة. انظر `harmonic_entry.py`.
    #
    # ⛔⛔ **وهو مُطفَأ — قِيس فخسر** (09-14…15 على شموع المنصّة):
    #
    #     بلا هارمونيك   5 إعدادات · 2 هدف · 2 وقف · 1 ملتبس   **+3.94$**
    #     مع الهارمونيك  4 إعدادات · 1 هدف · 2 وقف · 1 ملتبس  **−17.36$**
    #     ────────────────────────────────────────────────────────────
    #     الفرق                                        **−21.30$** · وإعدادٌ أقلّ
    #
    # ⚠️ **وقلتُ إنّ أثرَه «مُضافٌ لا مُزيح» — وكان ذلك خطأً**، كشفه
    # العدد: 5 ⇐ 4. فهو في مسار اللمس المباشر **يستبدل** الدخول والوقف
    # حين يعجز التنقيح الكلاسيكيّ، ووقفُه الصلب درجتان خلف D فيتّسع —
    # فيتجاوز سقفَ الـ20$ أحيانًا، فيسقط الإعدادُ كلُّه. أزاح رابحًا.
    #
    # ⇒ فيبقى مبنيًّا مختبَرًا **مطفأً**، كـ`structural.py`، حتى يُصلَح
    # الاستبدالُ ويُقاس من جديد. انظر
    # `knowledge/analyses/2026-09-20-harmonic-wired.md`.
    harmonic_enabled: bool = False
    # سماحية وقوع D داخل المنطقة. صفرٌ = داخلها تمامًا.
    harmonic_tolerance: float = 0.0

    # ⭐ نوعا نقاط الاهتمام من البثّ ٣ — ويُعطَّل أيٌّ منهما بسطر.
    # ولماذا مفتوحان؟ لأن نصّه فيهما صريح، وكلاهما يلزمه **تأكيد من
    # الإطار المقابل** فلا يدخل من مجرّد اللمس.
    bpr_enabled: bool = True
    inversion_enabled: bool = True

    # ⭐⭐ سندُ الإطار الأكبر — **الأوردر بلوك الصغير لا يقوم وحده**:
    #
    #     «الأوردر بلوك اللي بيكون على **أربع ساعات** — هيدا **ما
    #      بحاجة**… أما اللي بيكون على **الربع ساعة** — **بحاجة لنقاط
    #      اهتمام من إطار أكبر**»
    #     «إذا بدّك تاخذ أوردر بلوك على فريم الدقيقة… **بدّه يكون عندك
    #      نقطة اهتمام من نطاق أعلى**»
    #
    # ✅ **وقِيس على أسبوع 09-14…18 من شموع المنصّة، فلم يكلّف شيئًا:**
    #
    #     بلا سند   7 إعدادات · 2 هدف · 3 وقف · 2 ملتبس   −17.49$
    #     مع السند  7 إعدادات · 2 هدف · 3 وقف · 2 ملتبس   −17.49$
    #     ────────────────────────────────────────────────────────
    #     الفرق                                    **+0.00$** · وإعدادٌ صفر
    #
    # ⛔ **وصفرٌ في الحصيلة لا يعني قاعدةً خاملة** — فحصتُ ذلك ولم
    #    أفترضه: الشرطُ **يردّ 54% من المناطق** (55 من 102). فكلُّ ما
    #    كان سيردّه كانت بوّابةٌ لاحقة تردّه أصلًا في هذا الأسبوع.
    #
    # ⇒ **مرشِّحٌ منصوصٌ لا يكلّف شيئًا** — وهو الميزان نفسُه الذي
    #   أُبقي به `max_stop = 20$`: «يترك الأسبوع كما هو تمامًا ويقصّ
    #   الذيل». فيُشغَّل.
    #
    # 🔶 **ولم يُثبت نفعًا، إنّما نفى ضررًا.** وثلاثةُ تفاصيلَ فيه
    #    تأويلٌ منّي (أيُّ إطارٍ أعلى · معنى «مرتكز» · حالُ H1)، فيبقى
    #    أوّلَ ما يُطفأ إن ساء أسبوع. انظر `higher_poi.py`.
    higher_poi_required: bool = True
    # سماحيةُ التداخل بين المنطقتين. صفرٌ = تداخلٌ فعليّ.
    higher_poi_tolerance: float = 0.0

    # ⭐⭐⭐ **موافقةُ الإطار الأعلى في الاتّجاه** — لا في المكان.
    #
    #     «لو علّمتك الماركت ستركتشر شيفت، ولو علّمتك كلّ الأنماط
    #      الانعكاسيّة — **إذا انت فايت عكس الترند رح يضربك**»
    #
    # 🔴 **وأسبوع 09-14 يقول هذا بالأرقام**: قورن اتّجاهُ كلّ صفقةٍ
    #    بحكم المدرّب المسجَّل لذلك اليوم، فكان:
    #
    #      09-14  قال هابط · اشترى البوت ×2   **−25.82$**
    #      09-15  قال صاعد · اشترى البوت ×3   **+29.76$**
    #      09-16  قال صاعد · باع البوت   ×2   **−21.43$**
    #
    #    ⇒ وافقه فربح · خالفه مرّتين فخسر **−47.25$**.
    #
    # ⚠️ **والبوت لا يقرأ فيديوهاته.** فالمبنيُّ هنا ليس «وافِق
    #    المدرّب» بل «**وافِق قراءتك أنت للإطار الأعلى**» — وهي فرضيّةٌ
    #    أخرى: أنّ قراءة الكود لـH1 تشبه حكمَه. **تُقاس ولا تُفترَض.**
    #
    # ✅ **وقِيس على مدَيَين مستقلّين، فكسب في كليهما:**
    #
    #     09-14…18  (5 أيّام · 7 إعدادات)    −17.49$ ⇒ **+1.89$**   (+19.38)
    #     08-26…09-18 (3.5 أسابيع · 18)      −75.01$ ⇒ **−42.01$**  (+33.00)
    #
    # ⇒ **اتّساقُ الإشارة على مدًى أطولَ ثلاثَ مرّات** هو ما شغّله —
    #   لا الرقمُ الأكبر. وهو **مرشِّحٌ خالص**: أسقط إعدادين ولم يزد
    #   واحدًا.
    #
    # ⛔⛔ **والفرضيّة التي بُني عليها سقطت، ويُذكر ذلك:** توقّعتُ أن
    #    يمنع صفقات 09-14 و09-16 — اليومين اللذين خالف فيهما البوت حكمَ
    #    المدرّب وخسر. **فلم يمنع واحدةً منها.** ⇒ قراءةُ الكود لـH1
    #    **لا تشبه حكمَ المدرّب**. فهو ينفع لسببٍ آخر لا أعرفه بعد.
    #
    # 🔶 ونفعٌ بلا تفسيرٍ يبقى مراقَبًا — ويُطفأ بسطر.
    require_higher_trend: bool = True

    # ⭐⭐⭐ **إغلاقُ مسار النموذج الانعكاسيّ** — وهو مصدرُ النزيف.
    #
    # 🔴 قِيس على 08-26…09-18 بتفصيل المسارات (`--why`):
    #
    #     اللمس المباشر (منقَّح + من حدّه)   **+2.69$**
    #     النموذج الانعكاسيّ                **−65.36$**
    #
    # ⇒ فطريقةُ المدرّب الأساسيّة — الدخول من أوردر بلوك عند لمسه —
    #   متعادلةٌ بل موجبة. والخسارةُ كلُّها في الفرع الذي يدخل من
    #   **نموذجٍ انعكاسيّ بلا أوردر بلوك**.
    #
    # ✅ **وقِيس وحده على 08-26…09-18، فكان أكبرَ أثرٍ ظهر:**
    #
    #     كلا المسارين       18 إعدادًا · 3 هدف · 12 وقف   −75.01$
    #     اللمس المباشر وحده  9 إعدادات · 3 هدف ·  6 وقف    −6.08$
    #     ──────────────────────────────────────────────────────
    #     الفرق                                        **+68.93$**
    #
    # ⭐ وانظر عمود الأهداف: **ثلاثةٌ في الحالتين**. فالفرعُ الانعكاسيّ
    #   أعطى **تسعةَ إعدادات · صفرَ رابحٍ · ‎−68.93$**.
    #
    # ⛔ **وإغلاقُه يردّ نصًّا** — «أنا منها بفوت شراء **مع تأكيد من
    #    الفريم المرتبط**». ويُردّ لأنّ **صفرًا من تسعة** أقوى من نصٍّ
    #    عامّ، لا لأنّ الرقم أكبر.
    #
    # ✅ **وجرى التشغيل المؤكِّد ببوّابتَي H1 عاملتين:**
    #
    #     كلا المسارين       16 إعدادًا · 4 هدف · 10 وقف · 1 ملتبس  −42.01$
    #     اللمس المباشر وحده  6 إعدادات · 2 هدف ·  4 وقف · 0 ملتبس   −2.32$
    #     ──────────────────────────────────────────────────────────
    #     الفرق                                            **+39.69$**
    #
    # ⇒ **والأثران يتداخلان فعلًا**: 68.93$ بلا البوّابتين، و**39.69$**
    #   معهما. فنصفُ الفائدة كانتا تحصّلانها أصلًا، والرقمُ الصحيح هو
    #   الثاني.
    #
    # ⚠️ **وثمنُه يُذكر معه:** 16 إعدادًا ⇐ **6** في ثلاثة أسابيع ونصف
    #    — أي إعدادان في الأسبوع. فالبوت يصمت أيّامًا، وحكمُ أسبوعٍ
    #    واحد عليه لا يكفي.
    #
    # ⚠️ ونقصت **رابحتان** أيضًا (4 ⇐ 2) — فالفرعُ ليس خاليًا من الربح
    #    كما بدا في القياس الأوّل. والحصيلةُ أفضل لأنّه أسقط ستّ
    #    خاسراتٍ وملتبسةً مقابلهما.
    #
    # 🔶 ويُعاد فتحُه بسطرٍ إن قال أسبوعٌ آخر غير ذلك.
    direct_touch_only: bool = True

    # ⭐ سقفُ الأهداف — «واحد، اثنين، ثلاثة، **أربعة**… بدك الخامس؟
    #    **لا، ما بيمشي الحال**» (الأوردر بلوك ج2 ≈19:25). وكان `3`
    #    عاريًا هنا، فهذا تصحيحُ رقمٍ مخترَع لا توسيعُ سقف.
    max_targets: int = MAX_TARGETS

    # ⭐ سقف مسافة الوقف — **مستخرَج من أسبوع الملاحظة**، لا مخترَع.
    # انظر `max_stop` أدناه. ويُعطَّل بوضع None.
    max_stop: Optional[float] = 20.0
    # سبريد شاذّ يوقف التداول. لم يقع هذا الأسبوع (أعلى سبريد عند
    # إعداد مقبول 0.68$) — فهو تأمينٌ بلا كلفة مقاسة.
    max_spread: Optional[float] = 2.0

    @property
    def stop_buffer(self) -> float:
        """
        هامش الوقف الفعلي — 2 درجة × 1.00 = **2.00 دولار** افتراضًا.

        بسبريد ذهب نموذجي (0.20–0.40) تحكم الدرجتان دائمًا، والسبريد
        أرضية لا تُبلَغ إلا في اتساع شاذّ — وحينها يتّسع الوقف معه.
        """
        return stop_buffer(self.spread, self.stop_degrees, self.degree_value)


@dataclass
class ChainResult:
    rationale: TradeRationale
    disposition: Disposition
    note: str = ""
    poi: Optional[Internal] = None
    order_block: Optional[OrderBlock] = None
    targets: Sequence[External] = ()


# ─────────────────────────── أدوات ───────────────────────────


@dataclass(frozen=True)
class FrameView:
    """ما تراه السلسلة على إطارٍ واحد — وتحتاجه كلَّه لا بعضَه."""

    gaps: List[FVG]
    blocks: List[OrderBlock]
    dead: int                 # كم منطقةً أُسقطت لأنّ بروبلشنها ضُرب
    zones: List[Internal]


def read_frame(series: Series, swings: Sequence[Swing], structure: str,
               cfg: "ChainConfig") -> FrameView:
    """
    نقاطُ الاهتمام على إطارٍ ما — **بالمنطق نفسِه** أينما استُعمل.

    ⭐ واستُخرجت لتُستعمل **مرّتين**: على إطار القرار، وعلى الإطار
    الأكبر الذي يسنده (`higher_poi.py`). ونسخةٌ ثانيةٌ من المنطق كانت
    ستتباعد عن الأولى بصمت.

    ⚠️ و`swings` تُمرَّر ولا تُحسب هنا: إطارُ القرار حسبها في الخطوة
    الأولى، وإعادةُ حسابها تفتح بابَ اختلافٍ صامتٍ بين حسابين.
    """
    gaps = find_fvgs(series)
    sweeps = find_sweeps(series, swings)
    blocks = update_states(series, find_order_blocks(series, swings, sweeps, gaps))

    # ⭐ البثّ ٣ — «إذا في حال انضربت راح تروح نهائي»
    #
    # البروبلشن آخر مرحلة، وضربُها يقتل الأمّ. فالمنطقة الميّتة تُسقط
    # **قبل** أي فحصٍ آخر: تقييدٌ خالص، لا يزيد إعدادًا بل يمنع
    # إعدادًا على منطقةٍ استُنفدت.
    cycles = trace_all(series, blocks, swings)
    dead = {c.parent.index for c in cycles if c.dead}
    if dead:
        blocks = [b for b in blocks if b.index not in dead]

    # ⭐⭐ ونوعان جديدان من نقاط الاهتمام — البثّ ٣.
    #
    # ⚠️ **ولا يدخل أيٌّ منهما من مجرّد اللمس.** فحصُ اللمس المباشر
    # يشترط أوردر بلوك، فيسقط هذان إلى مسار «نموذج انعكاسي مفعَّل»
    # على الإطار المقابل — وهو ما نصّ عليه للمنعكسة حرفيًّا:
    # «أنا منها بفوت شراء **مع تأكيد من الفريم المرتبط**».
    bprs = find_bprs(gaps) if cfg.bpr_enabled else []
    inversions = (find_inversions(series, gaps, structure)
                  if cfg.inversion_enabled else [])

    return FrameView(
        gaps=gaps,
        blocks=blocks,
        dead=len(dead),
        zones=usable_internal(
            internal_from(gaps, blocks, bprs, inversions), structure),
    )


def _buffer_why(cfg: "ChainConfig") -> str:
    """يشرح في السجل من أين جاء الهامش — رقم بلا مصدر لا يُراجَع."""
    if cfg.stop_degrees is None or cfg.degree_value is None:
        return f"السبريد الحي {cfg.spread:g} — قيمة الدرجة معلّقة"
    span = cfg.stop_degrees * cfg.degree_value
    if span >= cfg.spread:
        return f"{cfg.stop_degrees:g} درجة × {cfg.degree_value:g}"
    return f"السبريد {cfg.spread:g} فاق {cfg.stop_degrees:g} درجة — الأرضية تحكم"


def _patterns_on_line(series: Series, swings: Sequence[Swing],
                      cfg: "ChainConfig") -> List:
    """
    نماذج الإطار المقابل بعد عرضها على **خطّ الإغلاقات**.

    ⭐ «هيدا مش دبل بتم — شوفوا ع الشموع، **هيدا قاع واحد**». فالنموذج
    يُكتشَف بالذيول (والمناطق تُرسم بها، وذلك مقيسٌ من شاشته)، ثم
    يُعرَض على الخطّ: ما لم يبقَ نموذجًا عليه رُدَّ.
    """
    found = find_all(swings, cfg.pattern_tolerance)
    if not cfg.line_chart_veto:
        return found
    return survivors(series, found, cfg.pattern_tolerance, cfg.swing_lookback)


def active_impulse(swings: Sequence[Swing], direction: str) -> Optional[Impulse]:
    """
    الموجة الفعّالة التي تُقاس عليها بوابة الـ50%.

    الدرس 6: تُقاس **الموجة كاملة** من القاع الحاكم إلى القمة — لا تذبذبًا داخليًا.
    """
    lows = [s for s in swings if s.is_low]
    highs = [s for s in swings if s.is_high]
    if not lows or not highs:
        return None
    lo, hi = lows[-1].price, highs[-1].price
    if hi <= lo:
        return None
    return measure(lo, hi, "bullish" if direction == "bullish" else "bearish")


def _price_reached(series: Series, zone: Internal, since: int) -> Optional[int]:
    for i in range(max(since, 0), len(series)):
        c = series[i]
        if c.low <= zone.top and c.high >= zone.bottom:
            return i
    return None


def _capped(entry: float, stop: float, targets: Sequence[External], direction: str) -> List[External]:
    """يستبعد الأهداف التي تتجاوز 1:3 — «واحد على ثلاثة يكون ماكسيموم»."""
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    return [t for t in targets if abs(t.price - entry) / risk <= MAX_TARGET_RR + 1e-6]


# ─────────────────────────── السلسلة ───────────────────────────


def evaluate(
    poi_series: Series,
    confirm_series: Series,
    cfg: ChainConfig,
    now: Optional[datetime] = None,
    higher_series: Optional[Series] = None,
) -> ChainResult:
    """
    يشغّل السلسلة كاملة ويرجع النتيجة بأسبابها.

    `poi_series`     : شموع إطار نقطة الاهتمام (H4 · H1 · M15)
    `confirm_series` : شموع الإطار المقابل    (M30 · M5 · M3)
    `higher_series`  : شموع **إطارٍ أعلى** يسند نقطة الاهتمام —
                       اختياريّ، ولا يُفحص إلّا مع `higher_poi_required`.
    """
    stamp = now or (poi_series.last_closed().time if len(poi_series) else datetime.now())
    r = TradeRationale(
        symbol=poi_series.symbol,
        direction="buy",
        poi_timeframe=cfg.poi_timeframe,
        confirm_timeframe=cfg.confirm_timeframe,
        detected_at=stamp,
    )

    def reject(note: str = "") -> ChainResult:
        return ChainResult(r, "rejected", note)

    # ── ٠. سبريد شاذّ ──
    #
    # لم يقع هذا الأسبوع: أعلى سبريد عند إعدادٍ **مقبول** كان 0.68$،
    # وبلغ 6.87$ في ثلاثة قرارات — كلها عند تدوير اليوم ومرفوضة
    # لأسباب أخرى. فالحارس تأمينٌ لم تُقَس كلفته، لكنّ ضرره مقيس:
    # `stop_buffer = max(2.00, spread)` ⇒ سبريد 6.87 يفتح وقفًا بـ6.87$.
    if cfg.max_spread is not None and cfg.spread > cfg.max_spread:
        r.add(
            "السبريد طبيعي",
            False,
            f"{cfg.spread:.2f}$ > {cfg.max_spread:g}$ — اتساع شاذّ يوسّع الوقف معه",
            "أسبوع 09-07…11",
        )
        return reject("سبريد شاذّ")

    # ── ١. الهيكل ──
    swings = find_swings(poi_series, cfg.swing_lookback)
    structure, why = describe_trend(swings)
    if structure == "undefined":
        r.add("الهيكل محدد", False, why, "الدرس 9")
        return reject("الهيكل غير محدد")

    r.direction = "buy" if structure == "bullish" else "sell"
    r.add(
        "الهيكل محدد",
        True,
        f"{structure} — آخر قمة {[s.price for s in swings if s.is_high][-1]} · "
        f"آخر قاع {[s.price for s in swings if s.is_low][-1]}",
        "الدرس 9",
    )

    # ── ١½. الإطار الأعلى لا يخالف ──
    #
    #     «إذا انت فايت **عكس الترند** رح يضربك»
    #
    # ⭐ **وأرخصُ بوّابةٍ في السلسلة**: سوينجاتٌ وحكمُ اتّجاه، بلا فراغات
    #    ولا أوردر بلوك. فتُوضع أوّلًا، فيسقط المخالفُ قبل أيّ حساب.
    #
    # ⚠️ و«غيرُ محدَّد» على الإطار الأعلى **ليس مخالفةً**: من لا ترند
    #    له لا يُذهب عكسَه. فيمرّ، ويُسمّى في السجلّ.
    # ⛔⛔⛔ **وغيابُ الإطار يُكتب — وكان يمرّ بلا أثر.**
    #
    # هنا خفي عطبُ H1 ثلاثةَ أسابيع. فبوّابةُ السند المجاورة (سطر 544)
    # تسجّل «⚠️ لم يُفحَص» حين لا يصلها الإطارُ الأعلى، **وهذه كانت
    # تُتخطّى بلا سطرٍ واحد**. فصفقتا H1 خرجتا من السجلّ وليس فيهما
    # ذكرٌ للاتّجاه أصلًا — لا نجاحًا ولا فشلًا ولا «لم يُفحَص».
    #
    # ⇒ وبوّابةٌ تصمت عند تعطُّلها **لا يُكتشف تعطُّلها**. فتُسوَّى
    #   بجارتها: تُسجَّل ناجحةً مع تصريحٍ أنّها لم تُجرَ.
    if cfg.require_higher_trend and (higher_series is None
                                     or len(higher_series) < 3):
        r.add("الإطار الأعلى لا يخالف", True,
              "⚠️ لم يُفحَص — لم يُعطَ الإطار الأعلى",
              "الأوردر بلوك ج3 · ترابط الفريمات")

    if cfg.require_higher_trend and higher_series is not None \
            and len(higher_series) >= 3:
        h_trend, h_why = describe_trend(
            find_swings(higher_series, cfg.swing_lookback))
        disagrees = h_trend != "undefined" and h_trend != structure
        r.add(
            "الإطار الأعلى لا يخالف",
            not disagrees,
            (f"{higher_series.timeframe} {h_trend} و{cfg.poi_timeframe} "
             f"{structure} — «إذا انت فايت عكس الترند رح يضربك»"
             if disagrees else
             f"{higher_series.timeframe} {h_trend}"
             + (f" ({h_why})" if h_trend == "undefined" else "")),
            "الأوردر بلوك ج3 · ترابط الفريمات",
        )
        if disagrees:
            return reject("الإطار الأعلى يخالف")

    # ── ٢. نقطة اهتمام مع الاتجاه ──
    view = read_frame(poi_series, swings, structure, cfg)
    gaps, blocks, dead, zones = view.gaps, view.blocks, view.dead, view.zones

    if not zones:
        r.add(
            "نقطة اهتمام مع الاتجاه",
            False,
            f"لا فراغ ولا أوردر بلوك باتجاه {structure} — «ما بيتخيّط»"
            + (f" · وأُسقطت {dead} منطقة ميّتة" if dead else ""),
            "ترابط الفريمات",
        )
        return reject("لا نقطة اهتمام")

    poi = zones[-1]
    r.add(
        "نقطة اهتمام مع الاتجاه",
        True,
        f"{poi.kind} {poi.bottom}–{poi.top} · المنتصف {poi.midpoint}",
        "السيولة الداخلية · ترابط الفريمات",
    )

    # ── ٢½. سندُ الإطار الأكبر ──
    #
    #     «الأوردر بلوك اللي بيكون على **أربع ساعات** — هيدا **ما
    #      بحاجة** لأني أعمل له نقاط اهتمام. أما اللي بيكون على **الربع
    #      ساعة** — **بحاجة لنقاط اهتمام من إطار أكبر** ليكون ناجحًا»
    #
    # ⭐ **مرشِّحٌ لا مولِّد**: لا يخترع إعدادًا، يردّ إعدادًا لا سندَ له.
    if cfg.higher_poi_required and higher_poi_needed(cfg.poi_timeframe):
        if higher_series is None or len(higher_series) < 3:
            # ⛔ **ولا يُعَدّ الغيابُ نجاحًا.** فحصٌ لم يُجرَ ليس فحصًا
            #    نجح، والسجلّ يقول ذلك بلفظه كي لا يُقرأ خطأً لاحقًا.
            r.add("سند من إطار أكبر", True,
                  "⚠️ لم يُفحَص — لم يُعطَ الإطار الأكبر",
                  "الأوردر بلوك ج1 · ج3")
        else:
            hview = read_frame(
                higher_series,
                find_swings(higher_series, cfg.swing_lookback),
                structure, cfg)
            sup = higher_support(poi, hview.zones, cfg.higher_poi_tolerance)
            r.add(
                "سند من إطار أكبر",
                sup is not None,
                (f"{sup.kind} {sup.bottom}–{sup.top} على {higher_series.timeframe}"
                 if sup is not None else
                 f"لا نقطة اهتمام على {higher_series.timeframe} تسند "
                 f"{poi.bottom}–{poi.top} — «بحاجة لنقاط اهتمام من إطار أكبر»"),
                "الأوردر بلوك ج1 · ج3",
            )
            if sup is None:
                return reject("لا سند من إطار أكبر")

    # ── ٣. وصول السعر ──
    reached = _price_reached(poi_series, poi, poi.index + 1)
    if reached is None:
        r.add("السعر وصل إليها", False, "لم يصل بعد", "م2/د3")
        return reject("لم يصل السعر لنقطة الاهتمام")
    r.add("السعر وصل إليها", True, f"عند الشمعة {reached}", "م2/د3")

    # ── ٤. بوابة الـ50% ──
    impulse = active_impulse(swings, structure)
    entry_ref = poi.top if structure == "bullish" else poi.bottom
    if impulse is not None:
        # البثّ المباشر: «بس **ما يغلق** — هي مش غالق فوق الـ50%»
        # ⇒ الحكم على **إغلاق** آخر شمعة، لا على مستوى مجرَّد.
        # الذيل فوق المنتصف مقبول — كقاعدته العامة: الذيل يستكشف
        # والإغلاق يقرّر.
        last = poi_series.last_closed()
        if cfg.gate_by_close and last is not None:
            expensive = impulse.closed_beyond_midpoint(last, impulse.direction)
            how = f"إغلاق {last.close:.2f}"
        else:
            expensive = impulse.is_expensive(entry_ref, impulse.direction)
            how = f"الدخول المرجعي {entry_ref:.2f}"
        r.add(
            "الموقع تحت بوابة الـ50%",
            not expensive,
            f"المنتصف {impulse.midpoint:.2f} و{how}",
            "الدرس 14 · C3 · البثّ المباشر",
        )
        if expensive:
            return reject("الدخول غالٍ")
    else:
        r.add("الموقع تحت بوابة الـ50%", True, "لا موجة مقاسة — البوابة غير مطبَّقة", "الدرس 14")

    # ── ٥/٦. التأكيد: لمس مباشر أو نموذج مفعَّل ──
    nested = [g for g in gaps if g.direction == structure]
    direct: Optional[OrderBlock] = None

    for ob in blocks:
        # أول لمسة لا غير — «اللمسة الثانية أو الثالثة ما بنتعامل معها»
        if ob.direction != structure or ob.state in ("failed", "mitigated"):
            continue
        chk = qualifies_for_direct_touch(
            ob, nested,
            impulse_midpoint=impulse.midpoint if impulse else None,
            require_containment=cfg.require_containment,
        )
        if chk.eligible:
            direct, direct_reasons = ob, chk.reasons
            break

    if direct is not None:
        r.add("دخول من مجرد اللمس", True, " · ".join(direct_reasons[:2]), "م2/د3")
        buf = cfg.stop_buffer
        entry = direct.entry_for(cfg.ob_large_threshold)
        stop = direct.stop_for(buf)
        stop_why = f"أدنى الأوردر بلوك {direct.bottom} − هامش {buf:g} ({_buffer_why(cfg)})"

        # ── ٦½. تنقيح الدخول **داخل** المنطقة ──
        #
        # ⭐⭐⭐ البثّ ٣ (≈1:10:26) — نصٌّ فاصل:
        #
        #     «هي الارتداد من الأوردر بلوك العالم بتفوت، في أغلبيتها
        #      بتفوت من الأوردر بلوك بيكون **الستوب تبعها قاع الأوردر
        #      بلوك**، **ولكن أنا بدون تأكيد ما بنصح**»
        #
        # فالدخول من حدّ المنطقة بوقفٍ عند قاعها كاملًا هو ما يفعله
        # «العالم» — وهو ما لا ينصح به بلا تأكيد. وطريقتُه: نموذجٌ
        # انعكاسيّ **داخل** المنطقة على الإطار المقابل، والوقف من
        # **قاع النموذج** لا من قاع المنطقة (ترابط الفريمات §3/§8).
        #
        # 🔴 وكلفة غيابه مقيسة: وسيط وقف البوت في أسبوع 09-07…11 كان
        # **10.91$** وأقصاه **74.77$**، وأرقامه هو **1–3.5$**.
        if cfg.refine_entry:
            c_swings_r = find_swings(confirm_series, cfg.swing_lookback)
            c_gaps_r = find_fvgs(confirm_series)
            ref = refine(
                zone_entry=entry, zone_stop=stop, direction=structure,
                confirm_series=confirm_series,
                patterns=activate(
                    confirm_series,
                    _patterns_on_line(confirm_series, c_swings_r, cfg),
                    c_gaps_r,
                ),
                buffer=buf,
                zone_bottom=direct.bottom, zone_top=direct.top,
                tolerance=cfg.refine_tolerance,
                extend_to_stop=cfg.refine_floor_to_stop,
            )
            # ⚠️ الرقمان معًا — المسلوك والمتروك. فسجلٌّ بلا المتروك
            # لا يقيس ما وفّره التنقيح، وذلك هو الغرض من بنائه.
            r.add(
                "تنقيح الدخول داخل المنطقة",
                ref.refined,
                ref.render(),
                "البثّ ٣ ≈1:10:26 · ترابط الفريمات §3 و§9",
            )
            if ref.refined:
                entry, stop = ref.entry, ref.stop
                stop_why = (
                    f"قاع النموذج {ref.pattern.extreme} − هامش {buf:g} "
                    f"({_buffer_why(cfg)}) · بدل قاع الأوردر بلوك "
                    f"{direct.bottom} — «بدون تأكيد ما بنصح»"
                )
            elif cfg.harmonic_enabled:
                # ⭐ والهارمونيك **بعد** الكلاسيكيّ لا قبله: فحين ينقّح
                # النموذجُ الانعكاسيّ لا حاجة لثانٍ، وحين لا ينقّح يبقى
                # الدخول من حدّ المنطقة — «بدون تأكيد ما بنصح». فهنا
                # موضعُه: يملأ فراغًا، ولا يزيح شيئًا قائمًا.
                harm = best_harmonic(
                    confirm_series, c_swings_r, structure,
                    direct.bottom, direct.top, cfg.harmonic_tolerance,
                )
                if harm is not None and harm.risk < ref.zone_risk:
                    r.add("تأكيد هارمونيّ داخل المنطقة", True,
                          f"{harm.render()} — بدل {ref.zone_risk:.2f}$ من حدّ المنطقة",
                          "البرق السريع §9 — «منها بأكّد»")
                    entry, stop = harm.entry, harm.stop
                    stop_why = (
                        f"وقف البرق السريع الصلب {harm.stop:.2f} "
                        f"(امتداد {harm.pattern.extension:g}) · "
                        f"بدل قاع الأوردر بلوك {direct.bottom}"
                    )
    elif cfg.direct_touch_only:
        # ⛔ لا أوردر بلوك يُلمَس ⇒ لا دخول. انظر `direct_touch_only`.
        r.add("دخول من مجرد اللمس", False,
              "لا أوردر بلوك مؤهَّل — ومسارُ النموذج الانعكاسيّ مغلق",
              "قياس 08-26…09-18 · المسارات")
        return reject("لا لمس مباشر")

    else:
        c_swings = find_swings(confirm_series, cfg.swing_lookback)
        c_gaps = find_fvgs(confirm_series)
        on_line = _patterns_on_line(confirm_series, c_swings, cfg)
        patterns = [
            p
            for p in activate(confirm_series, on_line, c_gaps)
            if p.activated and p.direction == structure
        ]
        harm: Optional[HarmonicEntry] = None
        if not patterns and cfg.harmonic_enabled:
            # ⭐ ولا نموذجَ كلاسيكيًّا — فهل عند الهارمونيك تأكيد؟
            #
            #     «نقطة انعكاس على الهارمونيك، **منها بأكّد**»
            #
            # وشرطُ الاحتواء هو نفسُه: D داخل نقطة الاهتمام، وإلّا فهو
            # إعدادٌ آخر في مكانٍ آخر من الشارت لا تأكيدٌ لهذه.
            harm = best_harmonic(
                confirm_series, c_swings, structure,
                poi.bottom, poi.top, cfg.harmonic_tolerance,
            )

        if harm is not None:
            r.add("نموذج انعكاسي مفعَّل", True,
                  f"لا نموذج كلاسيكيّ — والتأكيد هارمونيّ: {harm.render()}",
                  "البرق السريع §9 — «منها بأكّد»")
            entry, stop = harm.entry, harm.stop
            stop_why = (
                f"وقف البرق السريع الصلب {harm.stop:.2f} "
                f"(امتداد {harm.pattern.extension:g}) — الدرجة بعد وقف الإغلاق"
            )
        else:
            if not patterns:
                # ⭐ ويُسمّى عددُ ما ردّه الخطّ — فرفضٌ سببه «نموذجٌ من
                # ذيول» غيرُ رفضٍ سببه «لا نموذج أصلًا»، والفرق يضبط
                # السماحية.
                vetoed = (
                    len(line_rejected(confirm_series,
                                      find_all(c_swings, cfg.pattern_tolerance),
                                      cfg.pattern_tolerance, cfg.swing_lookback))
                    if cfg.line_chart_veto else 0
                )
                r.add(
                    "نموذج انعكاسي مفعَّل",
                    False,
                    f"لا نموذج مفعَّل على {cfg.confirm_timeframe} — «إذا ما أعطاني ما بفوت»"
                    + (f" · وردَّ الخطُّ {vetoed} نموذجًا من ذيول" if vetoed else "")
                    + (" · ولا برقًا سريعًا داخل المنطقة"
                       if cfg.harmonic_enabled else ""),
                    "ترابط الفريمات",
                )
                return reject("لا تأكيد على الإطار المقابل")

            pat = patterns[-1]
            plan = entry_plan(pat, cfg.stop_buffer)
            if plan is None:
                r.add("خطة دخول من الريتست", False,
                      "النموذج مفعَّل بلا فراغ كسر", "§10")
                return reject("لا فراغ عند الكسر")

            r.add(
                "نموذج انعكاسي مفعَّل",
                True,
                f"{pat.kind} · كسر خط العنق {pat.neckline} بالجسم "
                f"· فراغ {pat.fvg.bottom}–{pat.fvg.top}",
                "الدرس 7 · ترابط الفريمات",
            )
            entry, stop = plan.entry, plan.stop
            stop_why = (
                f"طرف النموذج {pat.extreme} − هامش {cfg.stop_buffer:g} "
                f"({_buffer_why(cfg)})"
            )

    # ── ٦½. سقف مسافة الوقف ──
    #
    # ⭐ **الرقم مقيس لا مقدَّر.** في أسبوع الملاحظة (2026-09-07…11)
    # أُعيد بناء مسار M15 من السجل نفسه واختُبرت الإعدادات العشرون
    # عليه، فتبيّن:
    #
    #   • أقصى ارتدادٍ معاكس احتاجه **رابح** قبل هدفه: **13.30$**
    #     (ووسيط ما احتاجه الرابحون 8.71$)
    #   • سقفٌ عند 20$ يترك الأسبوع **كما هو تمامًا** (−10.21$)
    #   • وتشديدٌ إلى 12$ يقلبه إلى **−109.85$** — يقتل الرابحين
    #
    # ⇒ فالعشرون دولارًا هو السقف **الذي لا يكلّف شيئًا** ويقصّ
    # الذيل: أسوأ إعداد في الأسبوع كان وقفه **74.77$** لصفقةٍ واحدة.
    #
    # ويوافق حدَّ المدرّب المنطوق في درس الخفاش: دخول 4416 بوقف 4440
    # — «24$ — **كارثي** بالنسبة لمتداول على الذهب».
    if cfg.max_stop is not None and abs(entry - stop) > cfg.max_stop:
        r.entry, r.stop, r.stop_reason = entry, stop, stop_why
        r.add(
            "مسافة الوقف ضمن السقف",
            False,
            f"{abs(entry - stop):.2f}$ > {cfg.max_stop:g}$ — «خلّي ستوبك معقول»",
            "أسبوع 09-07…11 · درس الخفاش",
        )
        return reject("الوقف أبعد من السقف")
    if cfg.max_stop is not None:
        r.add(
            "مسافة الوقف ضمن السقف",
            True,
            f"{abs(entry - stop):.2f}$ ≤ {cfg.max_stop:g}$",
            "أسبوع 09-07…11 · درس الخفاش",
        )

    # ── ٧. الأهداف ──
    ext = mark_swept(poi_series, classify_external(swings, cfg.poi_timeframe, cfg.thinning_proximity))
    pool = targets_above(ext, entry) if structure == "bullish" else targets_below(ext, entry)
    pool = _capped(entry, stop, pool, structure)

    if not pool:
        r.add(
            "هدف على السيولة الخارجية",
            False,
            "لا قمة/قاع صالح ضمن حد 1:3 — والداخلية ليست هدفًا",
            "السيولة الخارجية",
        )
        return reject("لا هدف صالح")

    r.add(
        "هدف على السيولة الخارجية",
        True,
        " · ".join(f"{t.price:.2f} ({t.strength})" for t in pool[:cfg.max_targets]),
        "السيولة الخارجية · «أول قمة آمن»",
    )

    r.entry, r.stop = entry, stop
    r.stop_reason = stop_why
    r.targets = [t.price for t in pool[:cfg.max_targets]]
    r.target_reason = "قمم/قيعان سابقة — سيولة خارجية · الأقرب أولًا"

    # ── ٧½. سلّمُ نقل الوقف ──
    #
    # ⭐ «بس ضرب الهدف الأوّل، **بدك تأمّن**… بترفع الستوب لوز لفوق
    #    دخولك **بدولار**» (الأوردر بلوك ج3) — ثم سلّمُ المستخدم بعدها.
    #
    # ⚠️ **ويُعرَض ولا يُنفَّذ**: البوت لا يلمس مركزًا. لكنّ عرضَه قبل
    #    الدخول يجعل الخطّة مقروءةً وقتَ القرار، لا بعده.
    r.trail_plan = [
        s.render() for s in trail_ladder(
            entry, stop, r.targets,
            "buy" if structure == "bullish" else "sell")
    ]

    # ── ٨. بوابة المخاطرة ──
    #
    # ⛔ **حدُّ الخسارة اليوميّ أوّلًا** — فهو الحدّ العامل بعد رفع حدّ
    # المراكز (المستخدم 2026-09-20). ويُقاس بالدولار لا بالعدّ، لأنّ
    # مركزين وقفُهما 3$ ليسا كمركزٍ وقفُه 20$.
    if (cfg.daily_loss_limit is not None
            and cfg.daily_loss <= -abs(cfg.daily_loss_limit)):
        r.blocked_reason = (
            f"بلغ اليومُ حدَّ خسارته ({cfg.daily_loss:+.2f}$ ≤ "
            f"−{abs(cfg.daily_loss_limit):g}$) — لا إعداد جديد اليوم"
        )
        return ChainResult(r, "blocked", r.blocked_reason, poi, direct, pool)

    if (cfg.max_open_positions is not None
            and cfg.open_positions >= cfg.max_open_positions):
        r.blocked_reason = (
            f"مركز مفتوح ({cfg.open_positions}/{cfg.max_open_positions}) — تنبيه لا أمر"
        )
        return ChainResult(r, "blocked", r.blocked_reason, poi, direct, pool)

    return ChainResult(r, "taken", "", poi, direct, pool)
