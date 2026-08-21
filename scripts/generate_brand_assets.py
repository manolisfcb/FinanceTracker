"""Generate TrueNorth's raster browser and social assets from its vector mark."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "src" / "static" / "images"
PAPER = "#f7f6f3"
INK = "#1c1b18"
MAPLE = "#b3372b"
MUTED = "#6f6b60"
BORDER = "#e7e4dc"

# The same 24-unit maple leaf used in brand-mark.svg.
LEAF = [
    (12, 2), (13.8, 5.4), (16.4, 4.2), (15.8, 7.2), (19, 6.8),
    (17.6, 9.4), (21, 11), (18, 12.8), (19.6, 15.6), (16.2, 15),
    (16.6, 18.4), (13.6, 16.6), (12, 22), (10.4, 17.6), (7.4, 19.4),
    (7.8, 16), (4.4, 16.6), (6, 13.8), (3, 12), (6.4, 10.4),
    (5, 7.8), (8.2, 8.2), (7.6, 5.2), (10.2, 6.4),
]


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def draw_leaf(draw: ImageDraw.ImageDraw, box, fill: str) -> None:
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    points = [
        (left + (x - 2) / 20 * width, top + (y - 2) / 20 * height)
        for x, y in LEAF
    ]
    draw.polygon(points, fill=fill)


def app_icon(size: int, *, maskable: bool = False, rounded: bool = False) -> Image.Image:
    scale = 4
    canvas_size = size * scale
    image = Image.new("RGB", (canvas_size, canvas_size), MAPLE)
    draw = ImageDraw.Draw(image)
    if rounded:
        image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (0, 0, canvas_size - 1, canvas_size - 1),
            round(canvas_size * 0.22),
            fill=MAPLE,
        )
    padding = canvas_size * (0.27 if maskable else 0.22)
    draw_leaf(draw, (padding, padding, canvas_size - padding, canvas_size - padding), PAPER)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def social_card() -> Image.Image:
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(image)

    # Quiet editorial grid and a restrained maple accent.
    draw.rectangle((0, 0, 16, height), fill=MAPLE)
    draw.line((80, 78, 1120, 78), fill=BORDER, width=2)
    draw.line((80, 552, 1120, 552), fill=BORDER, width=2)

    draw.rounded_rectangle((80, 120, 260, 300), radius=40, fill=MAPLE)
    draw_leaf(draw, (122, 162, 218, 258), PAPER)

    serif = "/System/Library/Fonts/NewYork.ttf"
    sans = "/System/Library/Fonts/SFNS.ttf"
    if not Path(serif).exists():
        serif = "/System/Library/Fonts/Supplemental/Georgia.ttf"
    if not Path(sans).exists():
        sans = "/System/Library/Fonts/Supplemental/Arial.ttf"

    draw.text((304, 126), "TrueNorth", font=font(serif, 82), fill=INK)
    draw.text((308, 224), "ANALYTICS", font=font(sans, 22), fill=MAPLE, spacing=8)
    draw.text(
        (80, 356),
        "Tu portafolio canadiense,\ncon el análisis que le falta.",
        font=font(serif, 49),
        fill=INK,
        spacing=8,
    )

    chip_font = font(sans, 19)
    chips = ((760, "RRSP · TFSA · FHSA"), (964, "TSX · NYSE · NASDAQ"))
    for left, label in chips:
        text_box = draw.textbbox((0, 0), label, font=chip_font)
        chip_width = text_box[2] - text_box[0] + 34
        draw.rounded_rectangle((left, 504, left + chip_width, 542), radius=19, outline=BORDER, width=2)
        draw.text((left + 17, 513), label, font=chip_font, fill=MUTED)

    return image


def main() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    app_icon(16, rounded=True).save(IMAGES / "favicon-16.png", optimize=True)
    app_icon(32, rounded=True).save(IMAGES / "favicon-32.png", optimize=True)
    app_icon(180).save(IMAGES / "apple-touch-icon.png", optimize=True)
    app_icon(150).save(IMAGES / "mstile-150.png", optimize=True)
    app_icon(192).save(IMAGES / "icon-192.png", optimize=True)
    app_icon(512).save(IMAGES / "icon-512.png", optimize=True)
    app_icon(512, maskable=True).save(IMAGES / "icon-512-maskable.png", optimize=True)
    app_icon(64, rounded=True).save(
        IMAGES / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )
    social_card().save(IMAGES / "og-image.png", optimize=True)


if __name__ == "__main__":
    main()
