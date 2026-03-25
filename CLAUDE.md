# Logo Stamper

Single-page web app (`index.html`) for batch-stamping logos onto product photos. No build system — pure HTML/CSS/JS.

## Architecture

- **One file**: Everything lives in `index.html` (styles, markup, script)
- **Three screens**: Setup → Editor → Done
- **Canvas-based**: Preview uses display-sized canvas; export renders at full resolution
- **Responsive**: Desktop uses sidebar, mobile uses collapsible bottom panel + action bar

## Key Constraints

- **iOS Safari canvas limit**: Max ~16MP. `renderToCanvas()` scales down large images to stay under this. Do not remove.
- **iOS download**: Uses `URL.createObjectURL` + blob approach (not `toDataURL`) because data URLs fail for large files on iOS Safari.
- **Download all**: Uses `onclick =` (not `addEventListener`) to avoid stacking duplicate handlers when `showDone()` is called.
- **Touch handling**: Logo drag + pinch-to-zoom + double-tap reset. Uses `{ passive: false }` where `preventDefault()` is needed.

## Multi-Logo Support

- Users can upload multiple logos at once
- Logo picker (thumbnail strip) appears in sidebar and mobile controls when >1 logo
- `logoImg` always points to the currently active logo from `logoImages[]`
- Failed logo loads are filtered out with `onerror` handler
- Object URLs are revoked on re-upload to prevent memory leaks

## Slider Sync

Three copies of size/opacity sliders (setup, sidebar, mobile) are kept in sync via `syncSliders(source)`. When adding new controls, remember to sync all three.
