"""
رسم الشارت — مخرَج للعين، لا مصدرًا للتحليل.

قرار المستخدم 2026-08-27: «لا يمكنك أن تجعل البوت يرسل صور الشارت أيضًا».

⚠️ **تمييز يجب ألا يضيع.** الصورة المرسومة هنا **مشتقّة من الأرقام نفسها**
التي حلّلها البوت. فهي:

  ✅ تكشف **أين رسم البوت مناطقه** — وهذا ما لا يظهر في جدول أرقام.
     إن وضع الأوردر بلوك في المكان الخطأ، تراه بعينك في ثانية.

  ✅ أداة دراسة: ترى ما رآه البوت كما رآه — وهو ما طلبته من البداية.

  ❌ **لا تضيف شيئًا لحكمي أنا على الشكل.** أنا أصلًا أقرأ الأرقام،
     والصورة المرسومة منها هي الأرقام ذاتها بلبوس آخر. لو حكمت عليها
     لحكمت على مخرَج البوت لا على السوق.

الصورة **المستقلة** الوحيدة هي لقطة من طرفية MT5 نفسها
(`ChartScreenShot()` من سكربت MQL5) — بكسل من عند الوسيط لا من عند البوت.
تلك تنتظر جسر MT5، وهي مسجَّلة في «ما لم يُبنَ بعد».

الصيغة SVG بمكتبة قياسية فقط: خطوط وأرقام ونصّ — لا تبعية على جهازك.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .data import Candle

# ─────────────────────────── الألوان ───────────────────────────

PALETTE: Dict[str, str] = {
    "bg": "#0e1117",
    "grid": "#1b2130",
    "axis": "#8b97a8",
    "text": "#c8d2e0",
    "bull": "#26a69a",
    "bear": "#ef5350",
    "fvg": "#3b82f6",
    "ob": "#f59e0b",
    "swing": "#94a3b8",
    "entry": "#e5e7eb",
    "stop": "#ef5350",
    "target": "#22c55e",
    "sweep": "#a855f7",
}


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ─────────────────────────── ما يُرسم فوق الشموع ───────────────────────────


@dataclass(frozen=True)
class Zone:
    """منطقة سعرية — فراغ سعري أو أوردر بلوك."""

    top: float
    bottom: float
    label: str = ""
    color: str = "fvg"
    start: Optional[int] = None      # None ⇒ من أول الشارت
    end: Optional[int] = None        # None ⇒ حتى آخره

    def __post_init__(self) -> None:
        if self.top < self.bottom:
            raise ValueError("أعلى المنطقة دون أدناها")


@dataclass(frozen=True)
class Level:
    """خط أفقي — دخول · وقف · هدف · خط عنق."""

    price: float
    label: str = ""
    color: str = "entry"
    dashed: bool = True


@dataclass(frozen=True)
class Marker:
    """علامة عند شمعة — قمة · قاع · كسح."""

    index: int
    price: float
    label: str = ""
    above: bool = True
    color: str = "swing"


@dataclass
class Scene:
    """كل ما سيُرسم. لا يقرّر شيئًا — يستقبل ما قرّره غيره."""

    candles: List[Candle]
    timeframe: str = ""
    symbol: str = ""
    title: str = ""
    zones: List[Zone] = field(default_factory=list)
    levels: List[Level] = field(default_factory=list)
    markers: List[Marker] = field(default_factory=list)

    def price_bounds(self) -> tuple:
        """المدى السعري شاملًا كل ما يُرسم — وإلا خرج الوقف خارج الصورة."""
        if not self.candles:
            raise ValueError("لا شموع للرسم")

        lo = min(c.low for c in self.candles)
        hi = max(c.high for c in self.candles)
        for z in self.zones:
            lo, hi = min(lo, z.bottom), max(hi, z.top)
        for lv in self.levels:
            lo, hi = min(lo, lv.price), max(hi, lv.price)
        for m in self.markers:
            lo, hi = min(lo, m.price), max(hi, m.price)

        if hi == lo:                      # سوق ساكن تمامًا
            hi, lo = hi + 1.0, lo - 1.0
        pad = (hi - lo) * 0.06
        return lo - pad, hi + pad


# ─────────────────────────── الرسم ───────────────────────────

_PAD = {"top": 46, "right": 78, "bottom": 34, "left": 14}


def render_svg(
    scene: Scene,
    width: int = 1000,
    height: int = 560,
    grid_lines: int = 6,
) -> str:
    """
    يبني SVG كاملًا مكتفيًا بنفسه.

    محور السعر يمينًا والزمن أسفل — كترتيب المنصّة الذي اعتاده المدرّب،
    كي تكون المقارنة بين الصورتين مباشرة بلا إعادة توجيه للعين.
    """
    if not scene.candles:
        raise ValueError("لا شموع للرسم")
    if width < 200 or height < 160:
        raise ValueError("المقاس أصغر من أن يُقرأ")

    n = len(scene.candles)
    lo, hi = scene.price_bounds()
    span = hi - lo

    left, right = _PAD["left"], width - _PAD["right"]
    top, bottom = _PAD["top"], height - _PAD["bottom"]
    plot_w, plot_h = right - left, bottom - top
    slot = plot_w / n
    body = max(1.0, slot * 0.62)

    def x(i: float) -> float:
        return left + (i + 0.5) * slot

    def y(p: float) -> float:
        return bottom - (p - lo) / span * plot_h

    P = PALETTE
    out: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="DejaVu Sans, Segoe UI, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="{P["bg"]}"/>',
    ]

    # ── العنوان ──
    head = scene.title or f"{scene.symbol} · {scene.timeframe}".strip(" ·")
    if head:
        out.append(
            f'<text x="{left}" y="26" fill="{P["text"]}" font-size="15" '
            f'font-weight="600">{_esc(head)}</text>'
        )

    # ── الشبكة ومحور السعر ──
    for k in range(grid_lines + 1):
        p = lo + span * k / grid_lines
        gy = y(p)
        out.append(
            f'<line x1="{left}" y1="{gy:.1f}" x2="{right}" y2="{gy:.1f}" '
            f'stroke="{P["grid"]}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{right + 7}" y="{gy + 4:.1f}" fill="{P["axis"]}" '
            f'font-size="11">{p:.2f}</text>'
        )

    # ── المناطق: تحت الشموع كي لا تحجبها ──
    for z in scene.zones:
        zx1 = x(z.start - 0.5) if z.start is not None else left
        zx2 = x(z.end + 0.5) if z.end is not None else right
        zx1, zx2 = max(left, zx1), min(right, zx2)
        zy, zh = y(z.top), max(1.0, y(z.bottom) - y(z.top))
        col = P.get(z.color, z.color)
        out.append(
            f'<rect x="{zx1:.1f}" y="{zy:.1f}" width="{max(1.0, zx2 - zx1):.1f}" '
            f'height="{zh:.1f}" fill="{col}" fill-opacity="0.16" '
            f'stroke="{col}" stroke-opacity="0.55" stroke-width="1"/>'
        )
        if z.label:
            out.append(
                f'<text x="{zx1 + 5:.1f}" y="{zy + 13:.1f}" fill="{col}" '
                f'font-size="11">{_esc(z.label)}</text>'
            )

    # ── الشموع ──
    for i, c in enumerate(scene.candles):
        cx = x(i)
        col = P["bull"] if c.close >= c.open else P["bear"]
        out.append(
            f'<line x1="{cx:.1f}" y1="{y(c.high):.1f}" x2="{cx:.1f}" '
            f'y2="{y(c.low):.1f}" stroke="{col}" stroke-width="1"/>'
        )
        by, bh = y(c.body_top), max(1.0, y(c.body_bottom) - y(c.body_top))
        out.append(
            f'<rect x="{cx - body / 2:.1f}" y="{by:.1f}" width="{body:.1f}" '
            f'height="{bh:.1f}" fill="{col}"/>'
        )

    # ── الخطوط الأفقية ──
    for lv in scene.levels:
        ly = y(lv.price)
        col = P.get(lv.color, lv.color)
        dash = ' stroke-dasharray="6 4"' if lv.dashed else ""
        out.append(
            f'<line x1="{left}" y1="{ly:.1f}" x2="{right}" y2="{ly:.1f}" '
            f'stroke="{col}" stroke-width="1.3"{dash}/>'
        )
        if lv.label:
            out.append(
                f'<text x="{left + 5}" y="{ly - 5:.1f}" fill="{col}" '
                f'font-size="11">{_esc(lv.label)}</text>'
            )

    # ── العلامات ──
    for m in scene.markers:
        if not 0 <= m.index < n:
            continue
        mx, my = x(m.index), y(m.price)
        col = P.get(m.color, m.color)
        dy = -7 if m.above else 7
        out.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="2.6" fill="{col}"/>')
        if m.label:
            anchor = "middle"
            ty = my + (dy - 4 if m.above else dy + 10)
            out.append(
                f'<text x="{mx:.1f}" y="{ty:.1f}" fill="{col}" font-size="10" '
                f'text-anchor="{anchor}">{_esc(m.label)}</text>'
            )

    # ── محور الزمن ──
    step = max(1, n // 8)
    for i in range(0, n, step):
        out.append(
            f'<text x="{x(i):.1f}" y="{bottom + 18:.1f}" fill="{P["axis"]}" '
            f'font-size="10" text-anchor="middle">'
            f'{scene.candles[i].time:%H:%M}</text>'
        )

    out.append("</svg>")
    return "\n".join(out)


def write_svg(scene: Scene, path: str, **kw) -> str:
    """يكتب الملف ويعيد مساره."""
    svg = render_svg(scene, **kw)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return path


def to_png(svg_path: str, png_path: str) -> str:
    """
    تحويل اختياري إلى PNG — لأن تيليجرام يعرض PNG داخل المحادثة
    ويرسل SVG كملف مرفق.

    يحتاج `cairosvg` (اختياري). ترك التحويل خارج النواة مقصود: النواة
    تبقى بمكتبة قياسية فقط، فلا يتعطّل التحليل إن غابت مكتبة رسم.
    """
    try:
        import cairosvg
    except ImportError as exc:
        raise RuntimeError(
            "تحويل PNG يحتاج cairosvg:  pip install cairosvg\n"
            "أو أرسل SVG كما هو — يفتح في المتصفح مباشرة."
        ) from exc

    cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=1400)
    return png_path


def legend() -> str:
    """
    مفتاح الشارت — يُرسَل نصًّا مع الصورة.

    التسميات على الشارت لاتينية قصيرة لأن محوّلات SVG→PNG لا تصل الحروف
    العربية ولا تعكس اتجاهها فتخرج مقلوبة. فالشرح هنا، في النصّ، حيث
    يُعرض العربي صحيحًا.
    """
    return (
        "🎨 مفتاح الشارت\n"
        "   🟦 FVG   = فراغ سعري\n"
        "   🟧 OB    = أوردر بلوك\n"
        "   ⬜ Entry = الدخول\n"
        "   🟥 SL    = الوقف\n"
        "   🟩 TP    = الهدف\n"
        "   ⚪ رمادي = قمة/قاع\n"
        "   🟪 بنفسجي = كسح سيولة"
    )
