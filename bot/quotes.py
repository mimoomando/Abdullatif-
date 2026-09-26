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

    @classmethod
    def load(cls, folder: str = "knowledge/source") -> "Corpus":
        words: List[str] = []
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                path = os.path.join(folder, name)
                if os.path.isfile(path) and name.endswith((".md", ".txt")):
                    with open(path, encoding="utf-8") as fh:
                        words += tokens(fh.read())
        index: Dict[str, List[int]] = collections.defaultdict(list)
        for i, w in enumerate(words):
            index[w].append(i)
        return cls(words, index, " " + " ".join(words) + " ")

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
    print(render(check()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
