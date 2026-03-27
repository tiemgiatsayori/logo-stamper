# Auto Logo Stamper - Documentation

## What it does

This script automatically stamps the Ohara logo onto flower product photos.
For each image it:

1. **Detects the flower bouquet** using AI (U2-Net model) so the logo never covers the flowers
2. **Analyzes the background brightness** to pick the right logo color (white logo for dark backgrounds, dark logo for light backgrounds)
3. **Finds the best spot** in the background to place the logo with maximum contrast
4. **Composites the logo** at the correct size and opacity, then saves the result

---

## Setup (one-time)

### Step 1: Install Python

- Download Python from https://www.python.org/downloads/
- During installation, **check the box "Add Python to PATH"** (very important!)
- After installation, close and reopen your terminal

Verify it works:
```
py --version
```
You should see something like `Python 3.14.x`.

### Step 2: Install dependencies

Open a terminal in the `logo-stamper` folder and run:
```
py -m pip install Pillow "rembg[cpu]"
```

This installs:
- **Pillow** - image processing library (resize, composite, save)
- **rembg** - AI background removal (uses U2-Net model to detect the flower bouquet)
- **onnxruntime** - runs the AI model on your CPU

The first time you run the script, it will download the U2-Net model (~170MB). This only happens once — after that it's cached on your computer.

---

## How to use

### Step 1: Put photos in the input folder

Copy your flower product photos into:
```
logo-stamper/auto/input/
```

Supported formats: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff`

### Step 2: Run the script

Open a terminal in the `logo-stamper/auto` folder and run:
```
cd auto
py auto_stamp.py
```

You'll see progress like:
```
Loading logos...
Found 5 image(s) to process

[1/5] bouquet_01.jpg
  Detecting subject...
  Finding best logo placement...
  Used white logo at (150, 890)
  Saved -> output/bouquet_01_stamped.jpg

[2/5] bouquet_02.jpg
  ...

Done! 5/5 images processed.
Results in: C:\...\logo-stamper\output
```

### Step 3: Get your results

Pick up the stamped images from:
```
logo-stamper/auto/output/
```

Each file is named `{original_name}_stamped.jpg`.

---

## Folder structure

```
logo-stamper/
├── images/
│   ├── ohara-black.png    <-- dark logo (used on light backgrounds)
│   └── ohara-white.png    <-- white logo (used on dark backgrounds)
├── auto/                  <-- auto stamper lives here
│   ├── auto_stamp.py      <-- the script
│   ├── input/             <-- PUT YOUR PHOTOS HERE
│   ├── output/            <-- RESULTS APPEAR HERE
│   └── HOW_TO_USE.md      <-- this file
└── index.html             <-- manual web tool (separate)
```

---

## How the AI logic works (detailed)

### Step 1: Subject detection (bouquet masking)

```
Original photo  -->  rembg (U2-Net AI)  -->  Background mask
```

The script sends the image to the `rembg` library which uses a pre-trained neural network (U2-Net) to detect the main subject (the flower bouquet). It returns a **mask** — a black and white image where:
- **White = bouquet** (foreground)
- **Black = background**

We **invert** this mask so white = background (areas where we CAN place the logo).

### Step 2: Grid analysis

The image is divided into a **5x5 grid** (25 regions):

```
┌────┬────┬────┬────┬────┐
│ 0,0│ 0,1│ 0,2│ 0,3│ 0,4│
├────┼────┼────┼────┼────┤
│ 1,0│ 1,1│ 1,2│ 1,3│ 1,4│
├────┼────┼────┼────┼────┤
│ 2,0│ 2,1│ 2,2│ 2,3│ 2,4│
├────┼────┼────┼────┼────┤
│ 3,0│ 3,1│ 3,2│ 3,3│ 3,4│
├────┼────┼────┼────┼────┤
│ 4,0│ 4,1│ 4,2│ 4,3│ 4,4│
└────┴────┴────┴────┴────┘
```

For each region, the script calculates:
- **bg_ratio**: What percentage of this region is background (not bouquet)?
  - If less than 60% background → **skip** (too much bouquet here)
- **brightness**: Average brightness of the background pixels (0=black, 255=white)

### Step 3: Scoring — pick the best region

Each valid region gets a **score** based on 4 factors:

| Factor | Weight | Why |
|---|---|---|
| **bg_ratio** (more background = better) | 3.0x | Don't overlap the bouquet |
| **edge_score** (closer to edges/corners) | 2.0x | Logos look better at edges, not floating in the middle |
| **bottom_score** (prefer bottom half) | 1.0x | Convention: logos usually go near the bottom |
| **contrast_score** (very dark or very light) | 1.0x | Extreme brightness = better contrast with logo |

The region with the **highest total score** wins.

### Step 4: Logo color selection

Based on the winning region's average brightness:
- **Brightness < 128** (dark area) → use **white logo** (`ohara-white.png`)
- **Brightness >= 128** (light area) → use **dark logo** (`ohara-black.png`)

This ensures maximum contrast — the logo is always visible.

### Step 5: Logo sizing and placement

- Logo width = **18% of image width** (configurable)
- Logo height = calculated to maintain aspect ratio
- Position = center of the winning grid region
- Clamped to stay at least **3% padding** from image edges
- Opacity = **90%** (slightly transparent for a subtle look)

### Step 6: Compositing and export

- The logo is placed on a transparent overlay
- Opacity is applied to the logo's alpha channel
- The overlay is composited onto the original image
- Saved as **JPEG at 95% quality**

---

## Configuration

You can adjust these values at the top of `auto_stamp.py`:

| Setting | Default | Description |
|---|---|---|
| `LOGO_SIZE_PCT` | `18` | Logo width as percentage of image width. Increase for bigger logo, decrease for smaller. |
| `LOGO_OPACITY` | `0.9` | Logo transparency. 1.0 = fully opaque, 0.5 = half transparent. |
| `EDGE_PADDING_PCT` | `3` | Minimum distance from image edges as percentage. Prevents logo from touching the border. |
| `GRID_COLS` | `5` | Number of grid columns for analysis. More = finer placement but slower. |
| `GRID_ROWS` | `5` | Number of grid rows for analysis. |
| `JPEG_QUALITY` | `95` | Output JPEG quality (1-100). 95 is high quality with reasonable file size. |

### Example: make logo smaller and more transparent
```python
LOGO_SIZE_PCT = 12
LOGO_OPACITY = 0.7
```

### Example: finer placement grid
```python
GRID_COLS = 8
GRID_ROWS = 8
```

---

## Troubleshooting

### "No onnxruntime backend found"
```
py -m pip install "rembg[cpu]"
```

### "No images found in input/"
Make sure your photos are directly inside the `input/` folder (not in a subfolder) and are one of the supported formats.

### First run is slow
The first run downloads the U2-Net AI model (~170MB). After that it's cached and subsequent runs are much faster. Each image takes roughly 5-15 seconds depending on size and your CPU.

### Logo is in the wrong spot
The algorithm isn't perfect for every photo. For tricky images, use the manual tool (`index.html`) instead. You can also try adjusting `GRID_COLS`/`GRID_ROWS` to `8` for finer placement.

### Want to use different logos
Replace `images/ohara-white.png` and `images/ohara-black.png` with your own logos. Keep the filenames the same, and make sure they have transparent backgrounds (PNG with alpha).
