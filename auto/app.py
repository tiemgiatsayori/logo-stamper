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
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Space+Mono:wght@400;700&display=swap');

:root {
    --bg:       #100b0d;
    --surface:  #1c1215;
    --surface2: #261a1e;
    --border:   #3a2530;
    --accent:   #f0adc3;
    --accent2:  #d97b8a;
    --text:     #fdf0f4;
    --muted:    #7a5a65;
}

body, .gradio-container { background: var(--bg) !important; color: var(--text) !important; }
.gradio-container { max-width: 1100px !important; margin: 0 auto !important; font-family: 'Space Mono', monospace !important; }
footer { display: none !important; }

/* Title area */
.ohara-title {
    text-align: center;
    padding: 32px 0 8px 0;
}
.ohara-title .petal {
    font-size: 1.6rem;
    letter-spacing: 8px;
    opacity: 0.6;
    margin-bottom: 6px;
}
.ohara-title h1 {
    font-family: 'Cormorant Garamond', serif !important;
    font-size: 3.2rem;
    font-weight: 600;
    letter-spacing: 4px;
    line-height: 1;
    color: var(--text);
}
.ohara-title h1 em {
    color: var(--accent);
    font-style: italic;
}
.ohara-divider {
    display: flex;
    align-items: center;
    gap: 12px;
    justify-content: center;
    margin-top: 12px;
}
.ohara-divider::before,
.ohara-divider::after {
    content: '';
    height: 1px;
    width: 60px;
    background: var(--border);
}
.ohara-divider span {
    color: var(--muted);
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* Panels - only style actual content cards, not every block */
.gr-panel, .gr-box, .gr-form, .gr-input, .gr-padded {
    background: transparent !important;
}
.block.gr-file, .block.gr-gallery, .block.gr-slider, .block.gr-button {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
}
.gr-group { background: transparent !important; border: none !important; }

/* File upload */
.upload-button { background: var(--surface2) !important; border: 1px dashed var(--border) !important; color: var(--muted) !important; }
.upload-button:hover { border-color: var(--accent) !important; color: var(--accent) !important; }
.file-preview { background: var(--surface) !important; border-color: var(--border) !important; }

/* Sliders */
input[type="range"] { accent-color: var(--accent) !important; }
.range-slider input { accent-color: var(--accent) !important; }

/* Labels */
label, .label-wrap span, span.text-gray-500, .gr-input-label {
    color: var(--muted) !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
}

/* Primary button */
.primary {
    background: var(--accent) !important;
    color: #1a0a10 !important;
    border: none !important;
    border-radius: 14px !important;
    font-weight: 800 !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.95rem !important;
    padding: 16px !important;
    transition: all 0.2s ease !important;
}
.primary:hover {
    background: #fde6ee !important;
    transform: translateY(-2px);
    box-shadow: 0 10px 40px rgba(240,173,195,0.25) !important;
}

/* Gallery */
.gallery-item { border-radius: 12px !important; overflow: hidden; border: 1px solid var(--border) !important; }
.gallery-item:hover { border-color: var(--accent) !important; }
.gallery-item img { border-radius: 0 !important; }

/* Download link */
a { color: var(--accent) !important; }
a:hover { color: #fde6ee !important; }

/* Misc text */
.gr-text-input, textarea, input[type="text"], input[type="number"] {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 10px !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent2); }

/* Number display for sliders */
.rangeSlider, .range-slider span, input[type="number"] {
    color: var(--accent) !important;
    font-family: 'Space Mono', monospace !important;
}

/* Status badge style for file count */
.file-count {
    display: inline-block;
    padding: 3px 12px;
    background: var(--accent);
    color: #1a0a10;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 700;
    font-family: 'Space Mono', monospace;
}

/* Settings panel styling */
.settings-section h4 {
    font-size: 0.65rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 14px;
    font-family: 'Space Mono', monospace;
}
"""

ohara_theme = gr.themes.Base(
    primary_hue=gr.themes.Color(
        c50="#fdf0f4", c100="#fde6ee", c200="#f8c8d8",
        c300="#f0adc3", c400="#e8919e", c500="#d97b8a",
        c600="#c4687a", c700="#a3505f", c800="#7a3a47",
        c900="#52252f", c950="#1a0a10",
    ),
    neutral_hue=gr.themes.Color(
        c50="#fdf0f4", c100="#e8d5dc", c200="#bfa0ab",
        c300="#7a5a65", c400="#5a3f4a", c500="#3a2530",
        c600="#261a1e", c700="#1c1215", c800="#100b0d",
        c900="#0a0608", c950="#050304",
    ),
).set(
    body_background_fill="#100b0d",
    body_text_color="#fdf0f4",
    block_background_fill="#1c1215",
    block_border_color="#3a2530",
    block_title_text_color="#7a5a65",
    block_label_text_color="#7a5a65",
    input_background_fill="#261a1e",
    input_border_color="#3a2530",
    button_primary_background_fill="#f0adc3",
    button_primary_text_color="#1a0a10",
    button_primary_background_fill_hover="#fde6ee",
    border_color_primary="#3a2530",
)

with gr.Blocks(
    title="Ohara Flower — Logo Stamper",
    theme=ohara_theme,
    css=css,
) as app:
    gr.HTML("""
        <div class="ohara-title">
            <div class="petal">✿ ✾ ✿</div>
            <h1>OHARA <em>Flower</em></h1>
            <div class="ohara-divider"><span>auto logo stamper</span></div>
        </div>
    """)

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="Ảnh sản phẩm",
                file_count="multiple",
                file_types=["image"],
                type="filepath",
            )
            with gr.Row():
                size_slider = gr.Slider(
                    minimum=5, maximum=80, value=24, step=1,
                    label="Kích thước logo (%)",
                )
                opacity_slider = gr.Slider(
                    minimum=10, maximum=100, value=90, step=5,
                    label="Độ trong suốt (%)",
                )
            run_btn = gr.Button("✿  BẮT ĐẦU  ✿", variant="primary", size="lg")

        with gr.Column(scale=2):
            gallery = gr.Gallery(
                label="Kết quả",
                columns=3,
                height="auto",
                object_fit="contain",
            )
            zip_output = gr.File(label="Tải tất cả (ZIP)")

    run_btn.click(
        fn=process_images,
        inputs=[file_input, size_slider, opacity_slider],
        outputs=[gallery, zip_output],
    )

app.launch(server_name="0.0.0.0", server_port=7860)
