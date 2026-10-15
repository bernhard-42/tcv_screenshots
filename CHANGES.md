v0.4.0

**API Changes**

- `colors` and `alphas` in the config of `save_model` set the colors and transparency of the objects

**Rendering**

- Model data is served to the viewer by a local HTTP server on `127.0.0.1` instead of being passed through Playwright's `page.evaluate`. Large models (e.g. a ~170 MB assembly) no longer crash the browser ([#5](https://github.com/bernhard-42/tcv_screenshots/issues/5))
- After a failed model the browser is restarted, so one crash no longer fails all remaining models
- The previous model is now really cleared before the next one is loaded (the old `window.viewer.clear()` call never ran). Rendering a small model after a large one went from minutes to below a second

v0.3.0

**CLI Changes**

- New syntax:

  ```bash
  usage: tcv_screenshots [-h] (-f FILE | -d DIRECTORY) [-o OUTPUT_FOLDER] [--no-headless] [--pause] [--debug MODELS_DIR]

  Generate screenshots from CAD examples using three-cad-viewer

  options:
    -h, --help            show this help message and exit
    -f FILE, --file FILE  Single Python example file to process
    -d DIRECTORY, --directory DIRECTORY
                          Directory containing Python example files (requires -o)
    -o OUTPUT_FOLDER, --output-folder OUTPUT_FOLDER
                          Output directory for PNG screenshots
    --no-headless         Run browser in visible mode (for debugging)
    --pause               Pause before each screenshot (for debugging)
    --debug MODELS_DIR    Save JSON model files to this directory (for debugging)
  ```

  - Removed positional arguments for examples/models/screenshots dirs
  - Models now rendered in memory; `--debug MODELS_DIR` saves JSON files for debugging
  - Removed `--skip-export` and `--skip-render` flags

**API Changes**

- `main()` must now return `get_saved_models()` (removed support for `return model` and `return (model, config)`)
- Files without `tcv_screenshots` import are now skipped (enable by the last change about retuns in main)
- Added `clear_saved_models()` to the rendering process to prevent model spillover between examples

**Output**

- Browser console debug/info/warning messages only shown with --debug
- Suppressed "Unknown option" warnings from viewer
