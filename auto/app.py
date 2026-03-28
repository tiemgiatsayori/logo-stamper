"""
Ohara Flower — Logo Stamper (Flask Web App)
Serves the manual stamper UI with AI-powered auto-placement.
"""

import os
import numpy as np
from PIL import Image
from rembg import remove
from flask import Flask, request, jsonify, send_from_directory

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_WHITE_PATH = os.path.join(SCRIPT_DIR, "images", "ohara-white.png")
LOGO_BLACK_PATH = os.path.join(SCRIPT_DIR, "images", "ohara-black.png")

EDGE_PADDING_PCT = 3
GRID_COLS = 7
GRID_ROWS = 7

# Pre-load logos (for aspect ratio reference)
logo_white = Image.open(LOGO_WHITE_PATH).convert("RGBA")
logo_black = Image.open(LOGO_BLACK_PATH).convert("RGBA")

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB max upload


def get_background_mask(img):
    """Use rembg to detect the subject, return background mask."""
    result = remove(img, only_mask=True)
    mask = np.array(result)
    return 255 - mask


def analyze_region(img_gray, bg_mask, x1, y1, x2, y2):
    """Analyze a grid region. Returns (avg_brightness, bg_ratio, brightness_std)."""
    region_gray = img_gray[y1:y2, x1:x2]
    region_mask = bg_mask[y1:y2, x1:x2]
    total_pixels = region_mask.size
    if total_pixels == 0:
        return None, 0.0, 0.0
    bg_pixels = np.sum(region_mask > 128)
    bg_ratio = bg_pixels / total_pixels
    if bg_pixels < 10:
        return None, bg_ratio, 0.0
    bg_values = region_gray[region_mask > 128]
    return float(np.mean(bg_values)), float(bg_ratio), float(np.std(bg_values))


def find_best_position(img, size_pct=24):
    """Find best logo position. Returns (x, y, use_white) where x,y are 0-1 normalized."""
    w, h = img.size

    bg_mask = get_background_mask(img)
    img_gray = np.array(img.convert("L"))
    gh, gw = img_gray.shape

    cell_w = gw // GRID_COLS
    cell_h = gh // GRID_ROWS
    candidates = []

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            x1, y1 = col * cell_w, row * cell_h
            x2, y2 = min(x1 + cell_w, gw), min(y1 + cell_h, gh)
            brightness, bg_ratio, brightness_std = analyze_region(
                img_gray, bg_mask, x1, y1, x2, y2
            )
            if brightness is None or bg_ratio < 0.6:
                continue
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            candidates.append({
                "cx": cx, "cy": cy,
                "brightness": brightness, "bg_ratio": bg_ratio,
                "brightness_std": brightness_std,
            })

    if not candidates:
        cx, cy = w * 0.50, h * 0.10
    else:
        best_score, best = -1, None
        for c in candidates:
            bg_score = c["bg_ratio"]
            top_score = 1.0 - (c["cy"] / h)
            center_x_score = 1.0 - abs(c["cx"] / w - 0.5) * 2
            dy = abs(c["cy"] / h - 0.5) * 2
            uniformity_score = max(0.0, 1.0 - c["brightness_std"] / 80.0)
            contrast_score = abs(c["brightness"] - 128) / 128

            score = (bg_score * 3.0 +
                     uniformity_score * 2.5 +
                     top_score * 2.5 +
                     center_x_score * 2.0 +
                     contrast_score * 1.0 +
                     dy * 0.5)

            if score > best_score:
                best_score, best = score, c

        cx, cy = best["cx"], best["cy"]

    # Clamp position considering logo size
    logo_w = int(w * size_pct / 100)
    logo_h = int(logo_w * logo_white.height / logo_white.width)
    padding = int(w * EDGE_PADDING_PCT / 100)
    half_w, half_h = logo_w / 2, logo_h / 2
    cx = max(padding + half_w, min(w - padding - half_w, cx))
    cy = max(padding + half_h, min(h - padding - half_h, cy))

    # Determine logo color by sampling brightness under logo footprint
    paste_x = int(cx - logo_w // 2)
    paste_y = int(cy - logo_h // 2)
    logo_area = img_gray[paste_y:paste_y + logo_h, paste_x:paste_x + logo_w]
    use_white = bool(float(np.mean(logo_area)) < 128)

    # Normalize to 0-1
    norm_x = cx / w
    norm_y = cy / h

    return norm_x, norm_y, use_white


# --- Routes ---

@app.route("/")
def index():
    return send_from_directory(SCRIPT_DIR, "index.html")


@app.route("/images/<path:filename>")
def serve_images(filename):
    return send_from_directory(os.path.join(SCRIPT_DIR, "images"), filename)


@app.route("/api/find-position", methods=["POST"])
def api_find_position():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    file = request.files["image"]
    size_pct = request.form.get("size_pct", "24")
    try:
        size_pct = max(5, min(80, int(size_pct)))
    except (ValueError, TypeError):
        size_pct = 24

    try:
        img = Image.open(file.stream).convert("RGB")
        x, y, use_white = find_best_position(img, size_pct)
        return jsonify({
            "x": round(x, 4),
            "y": round(y, 4),
            "use_white": use_white,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)
