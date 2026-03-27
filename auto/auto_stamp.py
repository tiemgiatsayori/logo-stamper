"""
Auto Logo Stamper for Ohara Flower
Automatically stamps the correct logo on product photos.
- Detects the flower bouquet (subject) and avoids it
- Analyzes background brightness to pick white or dark logo
- Places logo in the best background region with good contrast

Usage:
    1. Put product photos in the input/ folder
    2. Run: python auto_stamp.py
    3. Pick up results from output/ folder

Requirements:
    pip install Pillow rembg
"""

import os
import sys
import numpy as np
from PIL import Image
from rembg import remove

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(SCRIPT_DIR, "input")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
LOGO_WHITE = os.path.join(SCRIPT_DIR, "images", "ohara-white.png")
LOGO_BLACK = os.path.join(SCRIPT_DIR, "images", "ohara-black.png")

LOGO_SIZE_PCT = 18          # logo width as % of image width
LOGO_OPACITY = 0.9          # 0.0 - 1.0
EDGE_PADDING_PCT = 3        # padding from image edges as %
GRID_COLS = 5               # grid divisions for region scoring
GRID_ROWS = 5
JPEG_QUALITY = 95
SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def get_background_mask(img):
    """Use rembg to detect the subject, return background mask as numpy array."""
    # rembg returns image with alpha channel where foreground is opaque
    result = remove(img, only_mask=True)
    mask = np.array(result)
    # mask: 255 = foreground (bouquet), 0 = background
    # invert: we want background = 255
    bg_mask = 255 - mask
    return bg_mask


def analyze_region(img_gray, bg_mask, x1, y1, x2, y2):
    """Analyze a grid region. Returns (avg_brightness, bg_ratio)."""
    region_gray = img_gray[y1:y2, x1:x2]
    region_mask = bg_mask[y1:y2, x1:x2]

    # What fraction of this region is background?
    total_pixels = region_mask.size
    if total_pixels == 0:
        return None, 0.0

    bg_pixels = np.sum(region_mask > 128)
    bg_ratio = bg_pixels / total_pixels

    if bg_pixels < 10:
        return None, bg_ratio

    # Average brightness of background pixels only
    bg_brightness = np.mean(region_gray[region_mask > 128])
    return float(bg_brightness), float(bg_ratio)


def find_best_region(img, bg_mask):
    """
    Divide image into grid, score each region, return best placement.
    Returns: (center_x, center_y, use_white_logo)
    """
    img_gray = np.array(img.convert("L"))
    h, w = img_gray.shape

    cell_w = w // GRID_COLS
    cell_h = h // GRID_ROWS

    candidates = []

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            x1 = col * cell_w
            y1 = row * cell_h
            x2 = min(x1 + cell_w, w)
            y2 = min(y1 + cell_h, h)

            brightness, bg_ratio = analyze_region(img_gray, bg_mask, x1, y1, x2, y2)

            if brightness is None or bg_ratio < 0.6:
                # Skip regions that are mostly bouquet
                continue

            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            candidates.append({
                "col": col, "row": row,
                "cx": cx, "cy": cy,
                "brightness": brightness,
                "bg_ratio": bg_ratio,
            })

    if not candidates:
        # Fallback: bottom-right corner
        return w * 0.85, h * 0.90, True

    # Score candidates
    # Prefer: high bg_ratio, edges/corners, good contrast potential
    best_score = -1
    best = None

    for c in candidates:
        # Prefer regions with more background
        bg_score = c["bg_ratio"]

        # Prefer edges and corners (further from center)
        dx = abs(c["cx"] / w - 0.5) * 2  # 0 at center, 1 at edge
        dy = abs(c["cy"] / h - 0.5) * 2
        edge_score = (dx + dy) / 2

        # Prefer bottom half slightly (conventional logo placement)
        bottom_score = c["cy"] / h

        # Contrast score: very dark or very light regions are good
        # (more room for contrast with either logo)
        contrast_score = abs(c["brightness"] - 128) / 128

        score = (bg_score * 3.0 +
                 edge_score * 2.0 +
                 bottom_score * 1.0 +
                 contrast_score * 1.0)

        if score > best_score:
            best_score = score
            best = c

    # Decide logo color based on region brightness
    use_white = best["brightness"] < 128

    return best["cx"], best["cy"], use_white


def clamp_logo_position(cx, cy, logo_w, logo_h, img_w, img_h, padding):
    """Ensure logo stays within image bounds with padding."""
    half_w = logo_w / 2
    half_h = logo_h / 2
    cx = max(padding + half_w, min(img_w - padding - half_w, cx))
    cy = max(padding + half_h, min(img_h - padding - half_h, cy))
    return int(cx), int(cy)


def stamp_image(img_path, logo_white, logo_black):
    """Process a single image. Returns the stamped PIL Image."""
    img = Image.open(img_path).convert("RGB")
    w, h = img.size

    print(f"  Detecting subject...")
    bg_mask = get_background_mask(img)

    print(f"  Finding best logo placement...")
    cx, cy, use_white = find_best_region(img, bg_mask)

    # Pick logo
    logo = logo_white if use_white else logo_black
    logo_label = "white" if use_white else "black"

    # Resize logo
    logo_w = int(w * LOGO_SIZE_PCT / 100)
    logo_h = int(logo_w * logo.height / logo.width)
    logo_resized = logo.resize((logo_w, logo_h), Image.LANCZOS)

    # Clamp position
    padding = int(w * EDGE_PADDING_PCT / 100)
    cx, cy = clamp_logo_position(cx, cy, logo_w, logo_h, w, h, padding)

    # Composite with opacity
    # Create an overlay with the logo at the right position
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    paste_x = cx - logo_w // 2
    paste_y = cy - logo_h // 2
    overlay.paste(logo_resized, (paste_x, paste_y))

    # Apply opacity
    if LOGO_OPACITY < 1.0:
        r, g, b, a = overlay.split()
        a = a.point(lambda x: int(x * LOGO_OPACITY))
        overlay = Image.merge("RGBA", (r, g, b, a))

    # Composite onto original
    result = Image.new("RGBA", img.size)
    result.paste(img, (0, 0))
    result = Image.alpha_composite(result, overlay)
    result = result.convert("RGB")

    print(f"  Used {logo_label} logo at ({cx}, {cy})")
    return result


def main():
    # Check directories
    if not os.path.isdir(INPUT_DIR):
        print(f"Error: input/ folder not found at {INPUT_DIR}")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load logos
    print("Loading logos...")
    logo_white = Image.open(LOGO_WHITE).convert("RGBA")
    logo_black = Image.open(LOGO_BLACK).convert("RGBA")

    # Find images
    files = sorted([
        f for f in os.listdir(INPUT_DIR)
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXT
    ])

    if not files:
        print(f"No images found in {INPUT_DIR}")
        print(f"Supported formats: {', '.join(SUPPORTED_EXT)}")
        sys.exit(1)

    print(f"Found {len(files)} image(s) to process\n")

    success = 0
    for i, filename in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {filename}")
        try:
            img_path = os.path.join(INPUT_DIR, filename)
            result = stamp_image(img_path, logo_white, logo_black)

            # Save as JPEG
            name_without_ext = os.path.splitext(filename)[0]
            out_path = os.path.join(OUTPUT_DIR, f"{name_without_ext}_stamped.jpg")
            result.save(out_path, "JPEG", quality=JPEG_QUALITY)
            print(f"  Saved → {out_path}\n")
            success += 1
        except Exception as e:
            print(f"  Error: {e}\n")

    print(f"Done! {success}/{len(files)} images processed.")
    print(f"Results in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
