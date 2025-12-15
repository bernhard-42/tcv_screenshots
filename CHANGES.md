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
