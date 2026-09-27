"""
تدقيقُ الاقتباسات — أكلُّ ما نُسب إلى المدرّب موجودٌ في نصّه؟

╔══════════════════════════════════════════════════════════════════╗
║  ⛔ **لماذا وُجدت** — طلبَ المستخدم (2026-09-26):                  ║
║                                                                  ║
║      «أريد كلّ شيء دقيق ولا أريد أخطاء هذه المرّة»                ║
║                                                                  ║
║  والقاعدةُ ① تقول: كلُّ معاملٍ `SOURCE` **قاله المدرّب بنصّه،      ║
║  ومعه الاقتباس**. وهذا يجعل تلك الدعوى **قابلةً للفحص آليًّا**    ║
║  بدل أن تُصدَّق: كلُّ ما بين «…» في `params.py` يُبحث عنه في       ║
║  `knowledge/source/`.                                            ║
╚══════════════════════════════════════════════════════════════════╝

⚠️ **وما لا تفعله هذه الأداة — يُقال أوّلًا:**

  • **لا تفحص فهمي للنصّ.** تثبت أنّ العبارة قيلت، لا أنّ ما بنيتُه
    عليها صحيح. وأكثرُ أخطاء هذا المشروع كانت في **الكود والقياس**
    لا في الاقتباس — فهذه لا تمنع تلك.
  • **ولا تفحص القصير.** ثلاثُ كلماتٍ أو أربع لا تُميَّز من إعادة
    صياغة، فتُستثنى صراحةً بدل أن تُعدّ زورًا.
  • **ولا تفحص ما لم يصل نصُّه.** سبعةُ دروسٍ لا نملك تفريغَها،
    واقتباساتُها **غيرُ قابلةٍ للفحص** — لا مكذَّبة.

⭐ **والمطابقةُ بالكلمات لا بالحروف.** فاقتباساتي مهذَّبةٌ بالإعراب
والتفريغُ خامٌّ بلا إعراب، ومطابقةُ الحروف تردّ الصحيحَ مع الخطأ.
(وقد جرّبتُها أوّلًا فأعطت «92 غير موجود» — رقمٌ كاذبٌ كلُّه.)

⭐⭐ **وعُويرت على حالاتٍ معروفةِ الجواب** قبل أن تُصدَّق:

    ما أعرف أنّه في النصّ   ⇒  86% · 92% · 100%
    ما اخترعتُه للاختبار    ⇒  27% · 30%

⇒ فعتبةُ **55%** تفصل بينهما فصلًا نظيفًا. وهي معايرةٌ لا اختيار.

╔══════════════════════════════════════════════════════════════════╗
║  ⛔⛔ **وعطبان فيها صُحّحا 2026-09-27** — وكلاهما من الصنف          ║
║  المسجَّل في `CLAUDE.md`: «بندٌ معلَنٌ لا يعمل، **ويصمت عند**      ║
║  **تعطُّله**».                                                     ║
║                                                                  ║
║  ① **مجلّدٌ كاملٌ لم يُقرأ.** كانت تستعمل `os.listdir` مع          ║
║    `os.path.isfile`، فـ`knowledge/source/analyses/` — **وفيه**    ║
║    **تحاليلُ الذهب اليوميّة كلُّها** — كان يُهمَل صامتًا. فالأداةُ  ║
║    تقول «لم يُوجد» عن نصٍّ نملكه ولم تفتحه. ⇒ `os.walk`.          ║
║                                                                  ║
║  ② ⭐ **وكانت تصدّق نفسَها.** فترويسةُ كلّ ملفٍّ في `source/`       ║
║    **كتابتي أنا** وفيها اقتباساتٌ نقلتُها بيدي — فلو حرّفتُ        ║
║    اقتباسًا في `params.py` ونقلتُ التحريفَ نفسَه إلى الترويسة،     ║
║    لوجدته الأداةُ «✅ موجودًا في النصّ». **دائرةٌ مغلقة.** ⇒ لا    ║
║    يُقرأ إلّا **ما بين ``` ``` ``` **: التفريغُ الخامّ وحده.       ║
║                                                                  ║
║  ⭐ **وقِيس أثرُ ②، والدائرةُ كانت واقعةً لا محتملة:** من 64       ║
║  ناجحًا **لم يسقط ولا واحد**، لكنّ عبارةً واحدة (**«الهيكل غير**   ║
║  **محدَّد»** في `STRUCTURAL_SWING_LOOKBACK`) كانت تُطابَق          ║
║  **متّصلةً** — وموضعُها الوحيد في السجلّ كلِّه **سطرٌ من كتابتي**  ║
║  أنا (`lesson-33` س48، خارج السياج). ⇒ فصارت «أقصرَ من أن         ║
║  تُفحَص»، وهو **الصواب**: ثلاثُ كلماتٍ لا تُميَّز.                 ║
║                                                                  ║
║  ⚠️ وهي أصلًا **ليست كلامَ المدرّب** بل نصُّ سببِ رفضٍ من الكود —   ║
║  فالمستخرِجُ يأخذ كلَّ ما بين «…» ولا يفرّق. حدٌّ معلَنٌ لا عطب.    ║
╚══════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import collections
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

# دون هذا الطول لا يُحكم — إعادةُ الصياغة والاقتباسُ سواء
MIN_WORDS = 7
# فوق هذه العتبة يُعدّ الاقتباس حاضرًا (معايَرة — انظر الترويسة)
FOUND = 0.55
# كلمةٌ أشيعُ من هذا لا تصلح مرساةً
MAX_ANCHOR_FREQ = 3000
ANCHORS = 6

_DIAC = re.compile(r"[ً-ْٰـ]")
_KEEP = re.compile(r"[^ء-ي0-9]")
_QUOTE = re.compile(r"«([^»]{12,})»")
# التفريغُ الخامُّ وحده — وما خارجَ السياج ترويسةٌ كتبتُها أنا
_FENCED = re.compile(r"^```[^\n]*\n(.*?)\n```", re.S | re.M)


_BOX = re.compile(r"[║╔╗╚╝═╠╣╦╩╬│┌┐└┘─]")


def _undecorate(code: str) -> str:
    """
    يُسقط زخرفةَ الصناديق وعلاماتَ التعليق ووصلَ سلاسل بايثون.

    ⚠️ **ولولاه لتقطّع كلُّ اقتباسٍ يمتدّ سطرين داخل صندوق** — فأعطى
    خمسةَ أرقامٍ كاذبةٍ في أوّل تشغيل.
    """
    code = _BOX.sub(" ", code)
    code = re.sub(r"(?m)^\s*#", "", code)
    code = re.sub(r'"\s*\n\s*"', "", code)      # "…" \n "…" ⇒ سلسلة واحدة
    return re.sub(r"\s+", " ", code)


def raw_only(text: str) -> str:
    """
    ⛔ **يُسقط كلامي ويُبقي كلامَه.**

    فكلُّ ملفٍّ في `knowledge/source/` ترويسةٌ من كتابتي ثمّ التفريغُ
    الخامُّ بين ``` ``` ```. ولو بقيت الترويسةُ في السجلّ لصارت
    الأداةُ تصدّق نفسَها: اقتباسٌ محرَّفٌ في `params.py` نقلتُه
    محرَّفًا إلى الترويسة يُوجد «في النصّ».

    ⚠️ وملفٌّ بلا سياج (`.txt` الخامّ) يُقرأ كلُّه — فليس فيه كلامي.
    """
    blocks = _FENCED.findall(text)
    return "\n".join(blocks) if blocks else text


def normalise(word: str) -> str:
    """يُسقط الإعراب ويوحّد الألف والياء والتاء — فالتفريغُ لا يضبطها."""
    w = _DIAC.sub("", word)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"),
                 ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي")):
        w = w.replace(a, b)
    return _KEEP.sub("", w)


def tokens(text: str, least: int = 2) -> List[str]:
    return [w for w in (normalise(x) for x in re.split(r"\s+", text))
            if len(w) >= least]


@dataclass
class Corpus:
    """نصوصُ المدرّب الخام، مفهرسةً بالكلمة."""

    words: List[str]
    index: Dict[str, List[int]]
    joined: str = ""          # الكلماتُ مفصولةً بمسافة — للمتّصل
    files: Sequence[str] = ()  # ما قُرئ فعلًا — كي لا يُهمَل مجلّدٌ صامتًا

    @classmethod
    def load(cls, folder: str = "knowledge/source") -> "Corpus":
        """
        ⚠️ **بـ`os.walk` لا `os.listdir`.** فالنسخةُ الأولى كانت تهمل
        `analyses/` كلَّه — وفيه تحاليلُ الذهب اليوميّة، **وهي مصدرٌ
        مستقلٌّ كالدروس**. فكانت تقول «لم يُوجد» عن نصٍّ لم تفتحه.
        """
        words: List[str] = []
        read: List[str] = []
        for root, _dirs, names in os.walk(folder):
            for name in sorted(names):
                if not name.endswith((".md", ".txt")):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as fh:
                    words += tokens(raw_only(fh.read()))
                read.append(os.path.relpath(path, folder).replace("\\", "/"))
        index: Dict[str, List[int]] = collections.defaultdict(list)
        for i, w in enumerate(words):
            index[w].append(i)
        return cls(words, index, " " + " ".join(words) + " ", sorted(read))

    def contiguous(self, quote: str) -> bool:
        """
        أتظهر كلماتُ الاقتباس **متّصلةً بترتيبها** في النصّ؟

        ⭐ وهذا ما يُنقذ الاقتباسَ القصير: ثلاثُ كلماتٍ متّصلةٍ بعينها
        دليلٌ، بينما ثلاثُ كلماتٍ متفرّقةٍ في نافذةٍ ليست دليلًا.
        """
        want = tokens(quote, least=2)
        if len(want) < 2:
            return False
        return f" {' '.join(want)} " in self.joined

    def coverage(self, quote: str) -> float:
        """
        أكبرُ نسبةٍ من كلمات الاقتباس تجتمع في نافذةٍ واحدة من النصّ.

        ⚠️ **وتُجرَّب عدّةُ مراسٍ لا مرساةٌ واحدة.** فكلمةٌ واحدة قد
        يختلف رسمُها في التفريغ فيضيع الموضعُ كلُّه — وذلك بعينه ما
        أعطى «33%» لعبارةٍ تحقّقتُ بعيني أنّها في النصّ.
        """
        want = [w for w in tokens(quote, least=3)]
        if not want:
            return 0.0
        known = sorted((w for w in set(want)
                        if 0 < len(self.index.get(w, ())) <= MAX_ANCHOR_FREQ),
                       key=lambda w: len(self.index[w]))
        if not known:
            return 0.0
        span = max(15, 3 * len(want))
        need = collections.Counter(want)
        best = 0.0
        for anchor in known[:ANCHORS]:
            for pos in self.index[anchor]:
                lo, hi = max(0, pos - span), min(len(self.words), pos + span)
                have = collections.Counter(self.words[lo:hi])
                hit = sum(min(c, have[w]) for w, c in need.items())
                best = max(best, hit / len(want))
        return best


@dataclass(frozen=True)
class Checked:
    param: str
    origin: str
    lesson: str
    quote: str
    words: int
    coverage: float
    exact: bool = False        # ظهرت كلماتُه متّصلةً بترتيبها

    @property
    def testable(self) -> bool:
        """
        القصيرُ لا يُحكم عليه بالنافذة — **إلّا إن وُجد متّصلًا**.

        فثلاثُ كلماتٍ متّصلةٍ بعينها دليلٌ، وثلاثٌ متفرّقةٌ ليست.
        """
        return self.words >= MIN_WORDS or self.exact

    @property
    def found(self) -> bool:
        return self.exact or self.coverage >= FOUND


def check(corpus: Optional[Corpus] = None,
          params_module: str = "bot.params") -> List[Checked]:
    """
    يفحص كلّ ما بين «…» في `params.py`.

    ⛔ **ويُستثنى `USER`** — قراراتُ المستخدم ليست كلامَ المدرّب،
    فغيابُها من النصّ هو الصواب لا الخطأ.
    """
    import importlib

    corpus = corpus or Corpus.load()
    mod = importlib.import_module(params_module)
    out: List[Checked] = []
    for name in sorted(dir(mod)):
        value = getattr(mod, name)
        if type(value).__name__ != "Param" or value.origin == "USER":
            continue
        for quote in _QUOTE.findall(value.note or ""):
            out.append(Checked(
                param=name, origin=value.origin, lesson=value.lesson or "",
                quote=quote, words=len(tokens(quote, least=3)),
                coverage=corpus.coverage(quote),
                exact=corpus.contiguous(quote)))
    return out


def check_code(corpus: Optional[Corpus] = None,
               folder: str = "bot") -> List[Checked]:
    """
    ⭐⭐⭐ **ويفحص الكودَ أيضًا — أُضيف 2026-09-27.**

    ╔══════════════════════════════════════════════════════════════╗
    ║  ⛔ **وسببُ إضافته عطبٌ وقع بالفعل.** كان الحارسُ يقرأ         ║
    ║  `params.py` وحده، فصُحّحت ثلاثةُ اقتباساتٍ محرَّفةٍ في         ║
    ║  الدفتر يوم 26-09 **وبقيت محرَّفةً في**                       ║
    ║  **`primitives/continuation.py`** — وأحدُها في **رسالة خطأٍ**  ║
    ║  يطبعها البوت. فظنّ المشروعُ أنّ البابَ أُغلق وهو مفتوح.       ║
    ╚══════════════════════════════════════════════════════════════╝

    **والعرفُ الذي يجعل هذا ممكنًا:**

        «…»  ⇒  كلامُ المدرّب **بنصّه** — ويُفحَص آليًّا
        [ … ] ⇒  كلُّ ما عداه: قرارُ المستخدم · صياغتي · رقمٌ مقيس

    ⇒ فالمعقوفان **إقرارٌ صريح** بأنّ الكلام ليس كلامَه، لا تهرُّبٌ من
    الفحص. (وحُوِّل إليهما 16 موضعًا يومَ الإضافة.)

    ⚠️ **ويُنقّى النصُّ من زخرفة الصناديق قبل الاستخراج** — وإلّا
    تقطّع الاقتباسُ الممتدّ على سطرين بحرف `║` فأعطى رقمًا كاذبًا.
    """
    corpus = corpus or Corpus.load()
    out: List[Checked] = []
    for root, _dirs, names in os.walk(folder):
        if "tests" in root.split(os.sep):
            continue
        for name in sorted(names):
            if not name.endswith(".py") or name in ("params.py", "quotes.py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                text = _undecorate(fh.read())
            for quote in _QUOTE.findall(text):
                out.append(Checked(
                    param=path.replace("\\", "/"), origin="CODE", lesson="",
                    quote=quote, words=len(tokens(quote, least=3)),
                    coverage=corpus.coverage(quote),
                    exact=corpus.contiguous(quote)))
    return out


def suspect(results: Sequence[Checked]) -> List[Checked]:
    """الطويلُ الذي لم يُوجد — وهو وحده ما يستحقّ نظرًا."""
    return [c for c in results if c.testable and not c.found]


def render(results: Sequence[Checked]) -> str:
    ok = [c for c in results if c.testable and c.found]
    short = [c for c in results if not c.testable]
    bad = suspect(results)
    lines = [
        f"اقتباساتٌ منسوبةٌ للمدرّب: {len(results)}",
        f"  ✅ موجودٌ في النصّ      : {len(ok)}",
        f"  ◆ أقصرُ من أن يُفحَص   : {len(short)}  (دون {MIN_WORDS} كلمات)",
        f"  ⛔ طويلٌ ولم يُوجد     : {len(bad)}",
    ]
    if bad:
        lines.append("")
        lines.append("والأخيرُ يُفحص يدويًّا — وغيابُ نصّ الدرس أحدُ أسبابه:")
        for c in sorted(bad, key=lambda c: c.coverage):
            lines.append(f"  {c.coverage:3.0%} · {c.words:2d} كلمة · "
                         f"{c.param} [{c.lesson[:38]}]")
    lines.append("")
    lines.append("⚠️ يثبت أنّ العبارة قيلت — لا أنّ ما بُني عليها صحيح.")
    return "\n".join(lines)


def main(argv=None) -> int:
    from .replay import utf8_console
    utf8_console()
    corpus = Corpus.load()
    print("① الدفتر — `params.py`")
    print(render(check(corpus)))
    print()
    print("② الكود — كلُّ ما بين «» في `bot/` (وما بين [ ] مستثنًى بإقرار)")
    print(render(check_code(corpus)))
    print()
    print(f"وقُرئ من `knowledge/source/`: {len(corpus.files)} ملفًّا · "
          f"{len(corpus.words):,} كلمة")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
