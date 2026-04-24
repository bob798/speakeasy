"""
生成 PWA 图标（V0.9.1）

产物（写入 frontend/public/）：
  - pwa-192x192.png
  - pwa-512x512.png
  - apple-touch-icon.png (180x180)
  - favicon.svg

设计：
  - 背景色：accent 绿 #3d6b4f
  - 主体：白色 "S" 字母，居中，占比约 55%
  - 圆角：maskable 需留 10% safe zone

运行：python scripts/gen_pwa_icons.py
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ACCENT = (61, 107, 79)         # #3d6b4f
ACCENT_DARK = (51, 94, 68)     # #335e44
WHITE = (255, 255, 255)


def _find_bold_font(size: int):
    """寻找系统可用的 bold 字体（macOS 优先）。"""
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/SFNSRounded.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def gen_icon(size: int, out_path: Path, maskable: bool = False):
    """生成单个正方形图标。maskable 图标留 10% safe zone。"""
    img = Image.new("RGB", (size, size), ACCENT)
    draw = ImageDraw.Draw(img)

    # 渐变感：上浅下深（simple overlay）
    for y in range(size):
        ratio = y / size
        r = int(ACCENT[0] * (1 - ratio * 0.15))
        g = int(ACCENT[1] * (1 - ratio * 0.15))
        b = int(ACCENT[2] * (1 - ratio * 0.15))
        draw.line([(0, y), (size, y)], fill=(r, g, b))

    # 字体大小：maskable 留 10% 内边距，普通留 5%
    pad_ratio = 0.20 if maskable else 0.10
    inner = size * (1 - pad_ratio * 2)
    font_size = int(inner * 0.75)
    font = _find_bold_font(font_size)

    text = "S"
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1]
    draw.text((x, y), text, fill=WHITE, font=font)

    img.save(out_path, "PNG", optimize=True)
    print(f"✓ {out_path.name} ({size}x{size})")


def gen_favicon_svg(out_path: Path):
    """简单 SVG favicon（可被浏览器 tab 缩放）。"""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3d6b4f"/>
      <stop offset="100%" stop-color="#335e44"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="14" fill="url(#g)"/>
  <text x="32" y="44" font-family="-apple-system, 'SF Pro', 'Helvetica Neue', sans-serif"
        font-weight="700" font-size="38" fill="#fff" text-anchor="middle">S</text>
</svg>"""
    out_path.write_text(svg, encoding="utf-8")
    print(f"✓ {out_path.name}")


if __name__ == "__main__":
    gen_icon(192, OUT_DIR / "pwa-192x192.png", maskable=False)
    gen_icon(512, OUT_DIR / "pwa-512x512.png", maskable=True)
    gen_icon(180, OUT_DIR / "apple-touch-icon.png", maskable=False)
    gen_favicon_svg(OUT_DIR / "favicon.svg")
    print(f"\nAll icons written to: {OUT_DIR}")
