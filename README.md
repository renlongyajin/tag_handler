# e621 Tagger · Tag Calibration Toolkit

[中文说明 / Chinese README](README_ZH.md)

## Overview
This project extends the original e621 tagger with a PyQt5 desktop application for reviewing, translating, calibrating, and locking illustration tags in batches. It also includes helper scripts for data processing and model training.

## Features
- 🏷️ **Tag Management** – Dual-column English/Chinese view with add/delete/edit, undo/redo, and batch replacement.
- 🌐 **Translation Pipeline** – Prioritises Google Translate; falls back to LibreTranslate, Argos Translate, or a local dictionary with caching.
- 📷 **Image Viewer** – Auto-fit preview, mouse-wheel zoom, double-click reset, and quick navigation via arrow keys.
- 📋 **Copy & Paste** – Copy current tags to clipboard, paste into any file, and auto-translate missing language fields.
- 🔒 **Completion Lock** – Toggle between “🔓 Mark as Complete” and “🔒 Unmark”; once locked, editing is disabled while viewing/copying remains available.
- 🧹 **Batch Utilities** – Bulk delete ignores locked files and summarises results (success/skip/failure).
- 💾 **Safe Saves** – Automatic `.bak` backup before saving; “Restore Initial” reverts to the state when the file was loaded.
- ⚙️ **Configurable Suffix** – Default tag suffix `.final.txt`, adjustable via toolbar.

## Directory Layout
```
├─tag_viewer.py          # Application entry point
├─tagger/
│  ├─app.py              # QApplication bootstrap
│  ├─main_window.py      # Main UI and workflow logic
│  ├─widgets.py          # Custom widgets (tag rows, image viewer)
│  ├─translation.py      # Translation pipeline and cache
│  ├─commands.py         # QUndoCommand implementations
│  ├─fileops.py          # File discovery, IO, and locking
│  ├─config.py           # Global constants
│  ├─utils.py            # Utility helpers
│  └─dto.py              # Data objects
├─docs/                  # Requirements and progress logs
├─data/poren/            # Sample images and tag files
├─train/                 # Training scripts and data prep
├─requirements.txt       # Base dependencies (install PyQt5 separately)
└─Other helper scripts (webui.py, gpt_merge_tags_batch.py, etc.)
```

## Setup
1. Install Python 3.9 or later.
2. (Optional) create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   source venv/bin/activate   # macOS / Linux
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install PyQt5 requests
   # Optional offline translation
   pip install argostranslate
   ```
4. A local dictionary (`data/local_dictionary.json`) is generated on first launch; extend it as needed.

## How to Run
```bash
python tag_viewer.py
```
On launch:
1. Select the folder containing images and tag files (default `data/poren`).
2. The left panel shows English/Chinese tags; the right panel previews the image.
3. Key actions:
   - **Add Tag** – Accepts Chinese or English input, auto-filling the other language.
   - **Retranslate** – Refresh all tag translations.
   - **Restore Initial** – Revert to the load-time state and clear undo history.
   - **Copy / Paste** – Reuse tags across files with automatic translation.
   - **🔓/🔒 Toggle** – Locks/unlocks the file; locked files permit viewing and copying only.
4. Shortcuts: `Ctrl+S` save, `Ctrl+Z / Ctrl+Shift+Z` undo/redo, arrow keys switch files, mouse wheel zooms, double-click resets zoom.

## Advanced Notes
- Lock state is indicated through button text and status bar icons (🔓/🔒).
- Translation results are cached to avoid repeated API calls.
- Batch deletion automatically skips locked files and reports statistics.
- Default naming assumes `xxx.png` pairs with `xxx.final.txt`; adjust via “Set Suffix”.
- Extend translation sources in `translation.py`; customise tag row styling in `widgets.py`.

## Developer Tips
- Undo logic relies on `QUndoStack` and commands defined in `tagger/commands.py`.
- Lock status persists via `.lock` files; remove them manually to force unlock.
- Update `docs/当前开发进度.md` (progress log) after implementing new features.
- Respect the licensing terms of the upstream project when redistributing.

## License & Credits
This project inherits the original e621 tagger licence. Ensure compliance with the upstream licence when publishing forks or derivatives.

---

For issues or feature requests, use `docs/需求整理.md` or your issue tracker of choice. The Chinese README lives in [`README.md`](README.md).
