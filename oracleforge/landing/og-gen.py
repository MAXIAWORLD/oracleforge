"""Generate /og.png for MAXIA Oracle landing (1200x630).
Dark background, teal accent, mono-heavy type — matches the landing.
Run: python og-gen.py -> og.png
"""
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG       = (10, 10, 11)         # #0a0a0b
BG_RAISE = (16, 16, 19)         # #101013
BORDER   = (31, 31, 36)         # #1f1f24
TEXT     = (236, 236, 241)      # #ececf1
DIM      = (138, 138, 147)      # #8a8a93
FAINT    = (86, 86, 95)         # #56565f
ACCENT   = (94, 234, 212)       # #5eead4
ACCENT_D = (45, 212, 191)       # #2dd4bf

from PIL import ImageFilter

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img, "RGBA")

# 1) Subtle top glow via single-pass blurred ellipse (proper radial)
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
gd.ellipse((W/2 - 420, -180, W/2 + 420, 140), fill=(94, 234, 212, 42))
glow = glow.filter(ImageFilter.GaussianBlur(radius=90))
img.paste(glow, (0, 0), glow)
d = ImageDraw.Draw(img, "RGBA")  # re-bind

# 2) Dotted grid overlay
for y in range(40, H, 32):
    for x in range(40, W, 32):
        d.point((x, y), fill=(255, 255, 255, 20))

# 3) Top brand bar
d.line([(64, 92), (104, 92)], fill=ACCENT, width=2)
FONT_BRAND = ImageFont.truetype("C:/Windows/Fonts/CascadiaCode.ttf", 22)
d.text((128, 78), "MAXIA · ORACLE",
       font=FONT_BRAND, fill=TEXT, spacing=8)

FONT_TAG = ImageFont.truetype("C:/Windows/Fonts/CascadiaCode.ttf", 16)
d.text((W - 220, 82), "v0.1.0 · apache-2.0",
       font=FONT_TAG, fill=FAINT)

# 4) Main title (two lines, tight typography)
FONT_H1  = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 82)
FONT_H1I = ImageFont.truetype("C:/Windows/Fonts/segoeuii.ttf", 82)  # italic if exists

d.text((64, 180), "Multi-source price feed", font=FONT_H1, fill=TEXT)
try:
    d.text((64, 274), "for AI agents.", font=FONT_H1I, fill=ACCENT_D)
except Exception:
    # fallback if italic font missing
    FONT_H1_FALLBACK = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 82)
    d.text((64, 274), "for AI agents.", font=FONT_H1_FALLBACK, fill=ACCENT_D)

# 5) Hairline separator
d.line([(64, 400), (W - 64, 400)], fill=BORDER, width=1)

# 6) Three sources row
FONT_BODY  = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 24)
FONT_LBL   = ImageFont.truetype("C:/Windows/Fonts/CascadiaCode.ttf", 14)
FONT_MONO  = ImageFont.truetype("C:/Windows/Fonts/CascadiaCode.ttf", 20)

sources = [
    ("PYTH HERMES", "decentralized publishers"),
    ("CHAINLINK",   "on-chain · Base mainnet"),
    ("SPOT VENUE",  "third reading · divergence check"),
]
col_x = [64, 448, 832]
row_y = 440
for i, (lbl, desc) in enumerate(sources):
    x = col_x[i]
    d.text((x, row_y),      lbl,  font=FONT_LBL,  fill=ACCENT_D)
    d.text((x, row_y + 28), desc, font=FONT_BODY, fill=DIM)

# 7) Bottom bar with URL + disclaimer
d.line([(64, H - 84), (W - 64, H - 84)], fill=BORDER, width=1)
FONT_FOOT = ImageFont.truetype("C:/Windows/Fonts/CascadiaCode.ttf", 18)
d.text((64, H - 62), "oracle.maxiaworld.app",
       font=FONT_FOOT, fill=TEXT)
d.text((W - 464, H - 62), "data feed only · no custody · no kyc",
       font=FONT_FOOT, fill=FAINT)

# Accent dot near brand
d.ellipse((W - 244, 88, W - 236, 96), fill=ACCENT)

out = "og.png"
img.save(out, "PNG", optimize=True)
print(f"wrote {out} ({W}x{H})")
