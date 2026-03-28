"""
Ohara Flower — Logo Stamper (Gradio Web UI)
Runs locally via Docker. Upload photos, get stamped results.
"""

import io
import os
import zipfile
import tempfile
import numpy as np
from PIL import Image
from rembg import remove
import gradio as gr

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_WHITE_PATH = os.path.join(SCRIPT_DIR, "images", "ohara-white.png")
LOGO_BLACK_PATH = os.path.join(SCRIPT_DIR, "images", "ohara-black.png")

LOGO_SIZE_PCT = 24
LOGO_OPACITY = 0.9
EDGE_PADDING_PCT = 3
GRID_COLS = 7
GRID_ROWS = 7
JPEG_QUALITY = 95

# Pre-load logos
logo_white = Image.open(LOGO_WHITE_PATH).convert("RGBA")
logo_black = Image.open(LOGO_BLACK_PATH).convert("RGBA")


def get_background_mask(img):
    result = remove(img, only_mask=True)
    mask = np.array(result)
    return 255 - mask


def analyze_region(img_gray, bg_mask, x1, y1, x2, y2):
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


def find_best_region(img, bg_mask):
    img_gray = np.array(img.convert("L"))
    h, w = img_gray.shape
    cell_w = w // GRID_COLS
    cell_h = h // GRID_ROWS
    candidates = []

    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            x1, y1 = col * cell_w, row * cell_h
            x2, y2 = min(x1 + cell_w, w), min(y1 + cell_h, h)
            brightness, bg_ratio, brightness_std = analyze_region(img_gray, bg_mask, x1, y1, x2, y2)
            if brightness is None or bg_ratio < 0.6:
                continue
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            candidates.append({
                "cx": cx, "cy": cy,
                "brightness": brightness, "bg_ratio": bg_ratio,
                "brightness_std": brightness_std,
            })

    if not candidates:
        return w * 0.50, h * 0.10

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

    return best["cx"], best["cy"]


def clamp_logo_position(cx, cy, logo_w, logo_h, img_w, img_h, padding):
    half_w, half_h = logo_w / 2, logo_h / 2
    cx = max(padding + half_w, min(img_w - padding - half_w, cx))
    cy = max(padding + half_h, min(img_h - padding - half_h, cy))
    return int(cx), int(cy)


def stamp_single(img, size_pct, opacity):
    w, h = img.size
    bg_mask = get_background_mask(img)
    cx, cy = find_best_region(img, bg_mask)

    logo_w = int(w * size_pct / 100)
    logo_h = int(logo_w * logo_white.height / logo_white.width)
    padding = int(w * EDGE_PADDING_PCT / 100)
    cx, cy = clamp_logo_position(cx, cy, logo_w, logo_h, w, h, padding)

    paste_x, paste_y = cx - logo_w // 2, cy - logo_h // 2
    logo_area = np.array(img.convert("L"))[paste_y:paste_y + logo_h, paste_x:paste_x + logo_w]
    use_white = float(np.mean(logo_area)) < 128
    logo = logo_white if use_white else logo_black
    logo_resized = logo.resize((logo_w, logo_h), Image.LANCZOS)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay.paste(logo_resized, (paste_x, paste_y))

    if opacity < 1.0:
        r, g, b, a = overlay.split()
        a = a.point(lambda x: int(x * opacity))
        overlay = Image.merge("RGBA", (r, g, b, a))

    result = Image.new("RGBA", img.size)
    result.paste(img, (0, 0))
    result = Image.alpha_composite(result, overlay)
    return result.convert("RGB")


def process_images(files, size_pct, opacity):
    if not files:
        return [], None

    results = []
    for file_path in files:
        img = Image.open(file_path).convert("RGB")
        stamped = stamp_single(img, size_pct, opacity / 100.0)

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        stamped.save(tmp.name, "JPEG", quality=JPEG_QUALITY)
        results.append(tmp.name)

    # Create zip for batch download
    zip_path = os.path.join(tempfile.gettempdir(), "ohara_stamped.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, path in enumerate(results):
            basename = os.path.basename(files[i])
            name = os.path.splitext(basename)[0]
            zf.write(path, f"{name}_stamped.jpg")

    return results, zip_path


# --- Gradio UI ---
css = """
.gradio-container { max-width: 1100px !important; }
footer { display: none !important; }
"""

with gr.Blocks(
    title="Ohara Flower — Logo Stamper",
    theme=gr.themes.Soft(primary_hue="pink", neutral_hue="stone"),
    css=css,
) as app:
    gr.Markdown(
        "# 🌸 Ohara Flower — Logo Stamper\n"
        "Upload product photos → get them stamped with the Ohara logo automatically."
    )

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="Upload Photos",
                file_count="multiple",
                file_types=["image"],
                type="filepath",
            )
            with gr.Row():
                size_slider = gr.Slider(
                    minimum=5, maximum=80, value=24, step=1,
                    label="Logo Size (%)",
                )
                opacity_slider = gr.Slider(
                    minimum=10, maximum=100, value=90, step=5,
                    label="Logo Opacity (%)",
                )
            run_btn = gr.Button("✿ Stamp All Photos", variant="primary", size="lg")

        with gr.Column(scale=2):
            gallery = gr.Gallery(
                label="Stamped Results",
                columns=3,
                height="auto",
                object_fit="contain",
            )
            zip_output = gr.File(label="Download All (ZIP)")

    run_btn.click(
        fn=process_images,
        inputs=[file_input, size_slider, opacity_slider],
        outputs=[gallery, zip_output],
    )

app.launch(server_name="0.0.0.0", server_port=7860)
