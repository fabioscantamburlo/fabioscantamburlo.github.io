from PIL import Image, ImageDraw

IMG_PATH = "docs/imgs/image.png"
PREVIEW_PATH = "docs/imgs/badges_preview.png"
OUTPUT_DIR = "docs/imgs"

# Tweak these to align the grid lines
V_OFFSET = -8   # shift vertical lines left (negative = left)
H_OFFSET = -6  # shift horizontal line up (negative = up)

img = Image.open(IMG_PATH)
w, h = img.size
print(f"Image size: {w}x{h}")

# Preview with grid lines
preview = img.copy().resize((512, int(512 * h / w)))
ph, pw = preview.size[1], preview.size[0]
draw = ImageDraw.Draw(preview)

for i in range(1, 4):
    x = i * pw // 4 + V_OFFSET
    draw.line([(x, 0), (x, ph)], fill="red", width=2)
draw.line([(0, ph // 2 + H_OFFSET), (pw, ph // 2 + H_OFFSET)], fill="red", width=2)
preview.save(PREVIEW_PATH)
print(f"Preview saved: {PREVIEW_PATH}")

# Uncomment to actually split the badges once grid is aligned:
scale_x = w / 512
scale_y = h / int(512 * h / w)
v_real = int(V_OFFSET * scale_x)
h_real = int(H_OFFSET * scale_y)
col_w = w // 4
row_h = h // 2
for r in range(2):
    for c in range(4):
        n = r * 4 + c + 1
        x0 = c * col_w + (v_real if c > 0 else 0)
        y0 = r * row_h + (h_real if r > 0 else 0)
        x1 = (c + 1) * col_w + v_real
        y1 = (r + 1) * row_h + h_real
        badge = img.crop((x0, y0, x1, y1))
        badge.save(f"{OUTPUT_DIR}/badge_{n}.png")
        print(f"Saved badge_{n}.png")
