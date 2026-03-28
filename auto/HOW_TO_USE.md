# Auto Logo Stamper - Documentation

## Overview

This project provides **two ways** to stamp the Ohara logo onto product photos:

| Mode | Interface | Best for |
|------|-----------|----------|
| **Web App** (`app.py`) | Browser UI at `localhost:7860` | Interactive use, review & adjust |
| **CLI Batch** (`auto_stamp.py`) | Command line | Bulk processing, no UI needed |

Both share the same AI algorithm: detect the subject with rembg, find the best background region on a 7x7 grid, and pick white or black logo based on local brightness.

---

## Folder Structure

```
auto/
+-- app.py               <- Flask web server (serves UI + AI API)
+-- index.html           <- Frontend (stamper UI with AI integration)
+-- auto_stamp.py        <- CLI batch processor (standalone)
+-- requirements.txt     <- Python dependencies
+-- Dockerfile           <- Docker image definition
+-- docker-compose.yml   <- One-command Docker launch
+-- .dockerignore        <- Files excluded from Docker image
+-- HOW_TO_USE.md        <- This file
+-- images/
|   +-- ohara-white.png  <- White logo (for dark backgrounds)
|   +-- ohara-black.png  <- Black logo (for light backgrounds)
+-- input/               <- CLI mode: put photos here
+-- output/              <- CLI mode: results appear here
```

---

## Quick Start -- Web App (Docker)

### Prerequisites
- **Docker Desktop** installed (https://www.docker.com/products/docker-desktop)

### Run

```bash
docker compose up --build
```

Open **http://localhost:7860** in your browser.

### Run without Docker

```bash
py -m pip install -r requirements.txt
py app.py
```

Open **http://localhost:7860**.

---

## Quick Start -- CLI Batch Mode

### Setup (one time)

```bash
cd path/to/auto
py -m pip install -r requirements.txt
```

### Usage

1. Put product photos in `input/` (JPG, PNG, WebP, BMP, TIFF)
2. Run: `py auto_stamp.py`
3. Pick up results from `output/` (named `originalname_stamped.jpg`)

---

## Architecture

```
+---------------------------------------------------+
|                   Browser                         |
|                                                   |
|  index.html                                       |
|  +--------------+  +---------+  +----------+      |
|  | Setup Screen |->| Editor  |->|   Done   |      |
|  | (upload +    |  | (canvas |  | (download|      |
|  |  AI toggle)  |  |  + drag)|  |  results)|      |
|  +--------------+  +----+----+  +----------+      |
|                         |                         |
|           POST /api/find-position                 |
|                         |                         |
+-------------------------+-------------------------+
                          |
+-------------------------+-------------------------+
|                    Flask (app.py)                  |
|                         |                         |
|  GET /         -> index.html                      |
|  GET /images/* -> logo files                      |
|  POST /api/find-position                          |
|       |                                           |
|       +-- rembg (U2-Net) -> background mask       |
|       +-- 7x7 grid scoring -> best position       |
|       +-- footprint sampling -> logo color        |
|       +-- returns {x, y, use_white}               |
|                                                   |
+---------------------------------------------------+
```

---

## Web App -- User Flow

### Setup Screen

1. Upload one or more product images (drag & drop or file picker)
2. Choose logos -- both default logos (Ohara Black + Ohara White) are pre-selected; optionally upload custom logos
3. Adjust default logo size (5-80%, default 24%) and opacity (10-100%, default 100%)
4. **AI toggle** (checkbox, checked by default): enables automatic logo placement
5. Click **BAT DAU ->** to start

### AI Mode (toggle ON)

When the user clicks start, the app processes all images automatically:

```
For each image (no user interaction required):
  1. Display image on canvas
  2. Show loading overlay (AI dang phan tich anh...)
  3. POST image to /api/find-position
  4. Receive {x, y, use_white}
  5. Place logo at (x, y), auto-select white or black logo
  6. Render to JPEG blob, save result
  7. Advance to next image

After last image:
  Show review modal:
    "Xuat anh ngay"    -> go to download screen
    "Xem lai tu dau"   -> switch to manual mode, review from image 1
```

### Manual Mode (toggle OFF)

```
For each image:
  1. Display image with logo at top-center
  2. User drags logo to desired position
  3. User can: switch logo, resize, adjust opacity
  4. "Luu & Tiep"  -> save + next image
  5. "Bo qua"      -> skip (no save) + next image
  6. "Quay lai"    -> go back (restores saved edit state)

After last image:
  Show download screen
```

### Done Screen

- Download individual images (click each link)
- **Tai tat ca anh** -- downloads all images with `stamped_` prefix

---

## API Reference

### POST /api/find-position

Finds the optimal logo position for a given image.

**Request** (`multipart/form-data`):

| Field      | Type   | Description                                    |
|------------|--------|------------------------------------------------|
| `image`      | File   | The product image to analyze                   |
| `size_pct`   | string | Logo size as % of image width (5-80, default 24)|

**Response** (`application/json`):

```json
{
  "x": 0.5123,
  "y": 0.1456,
  "use_white": true
}
```

| Field       | Type    | Description                                    |
|-------------|---------|------------------------------------------------|
| `x`           | float   | Normalized X (0-1), center of logo position    |
| `y`           | float   | Normalized Y (0-1), center of logo position    |
| `use_white`   | boolean | true = use white logo (background is dark)     |

**Error response** (400 or 500):
```json
{ "error": "error message" }
```

### GET /

Serves `index.html` (the stamper UI).

### GET /images/<filename>

Serves logo files from the `images/` directory.

---

## AI Placement Algorithm (detailed)

The same algorithm is used by both `app.py` and `auto_stamp.py`.

### Step 1: Subject Detection

The **rembg** library (U2-Net neural network) generates a foreground mask:
- White = subject (bouquet/flowers)
- Black = background

The mask is **inverted** so white = background (areas where the logo CAN go).

### Step 2: Grid Analysis

The image is divided into a **7x7 grid** (49 regions):

```
+----+----+----+----+----+----+----+
| 0,0| 0,1| 0,2| 0,3| 0,4| 0,5| 0,6|
+----+----+----+----+----+----+----+
| 1,0| 1,1| 1,2| 1,3| 1,4| 1,5| 1,6|
+----+----+----+----+----+----+----+
| 2,0| 2,1| 2,2| 2,3| 2,4| 2,5| 2,6|
+----+----+----+----+----+----+----+
| 3,0| 3,1| 3,2| 3,3| 3,4| 3,5| 3,6|
+----+----+----+----+----+----+----+
| 4,0| 4,1| 4,2| 4,3| 4,4| 4,5| 4,6|
+----+----+----+----+----+----+----+
| 5,0| 5,1| 5,2| 5,3| 5,4| 5,5| 5,6|
+----+----+----+----+----+----+----+
| 6,0| 6,1| 6,2| 6,3| 6,4| 6,5| 6,6|
+----+----+----+----+----+----+----+
```

For each region, the algorithm calculates:
- **bg_ratio**: Percentage of background pixels (if < 60% -> skip, too much bouquet)
- **brightness**: Average brightness of background pixels (0=black, 255=white)
- **brightness_std**: Standard deviation of brightness (uniformity measure)

### Step 3: Scoring

Each valid region (bg_ratio >= 60%) gets a **weighted score**:

| Factor | Weight | What it measures |
|--------|--------|------------------|
| **bg_score** | 3.0 | More background = less bouquet overlap |
| **uniformity_score** | 2.5 | Consistent brightness = cleaner logo area |
| **top_score** | 2.5 | Prefers top of image (logo convention) |
| **center_x_score** | 2.0 | Prefers horizontally centered placement |
| **contrast_score** | 1.0 | Very dark or very light = better with logo |
| **edge_y_score** | 0.5 | Prefers vertical edges over dead center |

**Formulas:**
- `bg_score` = bg_ratio (0-1)
- `uniformity_score` = max(0, 1 - brightness_std / 80)
- `top_score` = 1 - (cy / image_height)
- `center_x_score` = 1 - |cx / image_width - 0.5| * 2
- `contrast_score` = |brightness - 128| / 128
- `edge_y_score` = |cy / image_height - 0.5| * 2

The region with the **highest total score** wins.

**Fallback**: If no region has >= 60% background, the logo is placed at top-center (50%, 10%).

### Step 4: Position Clamping

The logo center is clamped so the full logo stays within the image, with 3% edge padding:
- Accounts for logo width (`size_pct` % of image width)
- Maintains aspect ratio from the original logo file

### Step 5: Logo Color Selection

Instead of using the grid cell's average brightness, the algorithm samples the **actual pixels under the logo footprint**:

1. Calculate the exact pixel rectangle where the logo will be placed
2. Extract the grayscale values of that area
3. Compute the mean brightness
4. **Mean < 128** (dark background) -> use **white logo**
5. **Mean >= 128** (light background) -> use **black logo**

This gives more accurate color selection than the grid cell average, since the logo may span multiple cells.

### Step 6: Compositing (CLI mode only)

`auto_stamp.py` composites the logo onto the original image:
- Logo is resized to `LOGO_SIZE_PCT`% of image width (maintaining aspect ratio)
- Opacity is applied to the alpha channel (default 90%)
- Result is saved as JPEG at 95% quality

In web app mode, compositing happens in the browser via Canvas API at original image resolution.

---

## Configuration

### Web App (app.py)

| Setting | Value | Description |
|---------|-------|-------------|
| `EDGE_PADDING_PCT` | 3 | Min distance from edges (%) |
| `GRID_COLS` | 7 | Grid columns for scoring |
| `GRID_ROWS` | 7 | Grid rows for scoring |
| `MAX_CONTENT_LENGTH` | 50 MB | Max upload size |
| Port | 7860 | Server port |

Logo size and opacity are controlled by the user via the UI sliders.

### CLI (auto_stamp.py)

| Setting | Default | Description |
|---------|---------|-------------|
| `LOGO_SIZE_PCT` | 24 | Logo width as % of image width |
| `LOGO_OPACITY` | 0.9 | Logo transparency (1.0 = fully opaque) |
| `EDGE_PADDING_PCT` | 3 | Min distance from edges (%) |
| `GRID_COLS` | 7 | Grid columns for scoring |
| `GRID_ROWS` | 7 | Grid rows for scoring |
| `JPEG_QUALITY` | 95 | Output JPEG quality (1-100) |

---

## Frontend Details (index.html)

### Screens

| Screen | ID | Description |
|--------|----|-------------|
| Setup | `#setup-screen` | Upload images, select logos, set options, AI toggle |
| Editor | `#editor-screen` | Canvas with draggable logo, live controls |
| Done | `#done-screen` | Download results |
| AI Modal | `#ai-review-modal` | Post-AI review prompt (export or review) |

### Key JavaScript State

| Variable | Type | Purpose |
|----------|------|---------|
| `imageFiles` | Array | Uploaded product image files |
| `logoImages` | Array | All active logo Image objects (default + custom) |
| `activeLogoIndex` | number | Currently selected logo index |
| `currentIndex` | number | Current image index being edited |
| `results` | Array | Saved results [{name, blob}] |
| `logoX`, `logoY` | number | Logo center position (normalized 0-1) |
| `logoSizePct` | number | Logo size as % of canvas width |
| `logoOpacity` | number | Logo opacity (0.1-1.0) |
| `imageEditState` | Object | Per-image saved edit state for back/review |
| `useAI` | boolean | Whether AI auto-placement is active |
| `aiAutoAdvancing` | boolean | True while AI is chaining through images |
| `viewScale` | number | Current pinch-zoom scale |

### Key Functions

| Function | Description |
|----------|-------------|
| `loadImage(index)` | Loads image, checks for saved state -> AI -> manual fallback |
| `autoPlace(index)` | Sends image to API, places logo, auto-saves, auto-advances |
| `autoSelectLogo(useWhite)` | Picks white or black logo based on API response |
| `renderToCanvas()` | Renders canvas at original resolution -> JPEG blob |
| `setPos(pos)` | Sets logo to preset position (tl, tc, tr, ml, mc, mr, bl, bc, br) |
| `drawLogo()` | Updates logo handle position and opacity on canvas |
| `saveEditState(i)` | Saves current edit state for image i |
| `restoreEditState(i)` | Restores saved edit state for image i |
| `showAIReviewModal()` | Shows the post-AI review/export modal |
| `showDone()` | Transitions to download screen with all results |
| `syncSliders(source)` | Syncs sidebar and mobile control sliders |

### Logo Positions (setPos)

| Code | Position |
|------|----------|
| `tl` | Top-left |
| `tc` | Top-center (default for manual mode) |
| `tr` | Top-right |
| `ml` | Middle-left |
| `mc` | Middle-center |
| `mr` | Middle-right |
| `bl` | Bottom-left |
| `bc` | Bottom-center |
| `br` | Bottom-right |

All positions use 2% padding from edges.

---

## Docker

### Files

- **Dockerfile**: Python 3.11-slim, installs system deps (libgl1, libglib2.0-0), copies app.py + index.html + images/
- **docker-compose.yml**: Single `stamper` service, port 7860
- **.dockerignore**: Excludes input/, output/, auto_stamp.py, backups, scripts

### Build & Run

```bash
docker compose up --build          # first time / after changes
docker compose up                  # subsequent runs
docker compose down                # stop
```

### First Run

The first API call triggers the U2-Net model download (~170MB). This is cached inside the container. Subsequent calls are fast (5-15s per image depending on size and CPU).

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Pillow | >= 10.0 | Image processing (resize, composite, format conversion) |
| rembg[cpu] | >= 2.0 | AI background removal (U2-Net model, CPU inference) |
| numpy | latest | Array operations for mask/brightness analysis |
| flask | >= 3.0 | Web server (serves UI + API) |
| onnxruntime | (via rembg) | Neural network runtime for CPU |

---

## Troubleshooting

### "No onnxruntime backend found"
```
py -m pip install "rembg[cpu]"
```

### First run is slow
The U2-Net model (~170MB) downloads on first use. After that it's cached.

### Logo is in the wrong spot
The AI isn't perfect for every photo. Use the web app in manual mode (uncheck AI toggle) to drag the logo where you want it. Or try adjusting `GRID_COLS`/`GRID_ROWS` to 8 for finer placement.

### Want to use different logos
Replace `images/ohara-white.png` and `images/ohara-black.png` with your own logos. Keep transparent backgrounds (PNG with alpha). The web app also lets users upload custom logos at runtime.

### SSL/proxy errors during model download
If you're behind a corporate proxy, set `HTTPS_PROXY` environment variable or pre-download the model manually.
