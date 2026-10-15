v0.4.0

**API Changes (breaking)**

- `save_model(*cad_objs, name, **kwargs)` takes the same objects and keywords as `show` of OCP CAD Viewer, instead of `save_model(model, name, config)` with a config dict of renderer names ([#2](https://github.com/bernhard-42/tcv_screenshots/issues/2)). Migration: `save_model(box, "box", {"cadWidth": 500, "height": 375})` becomes `save_model(box, name="box", cad_width=500, height=375)`; config keys become `show` keywords (`clipSlider0` → `clip_slider_0`, `blackEdges` → `black_edges`, ...)
- `render_edges=False` becomes `modes=[Render.FACES]`, `render_faces=False` becomes `modes=[Render.EDGES]`
- All keywords of `show` work, among them `colors`, `alphas` ([#1](https://github.com/bernhard-42/tcv_screenshots/issues/1)), `materials`, `render_joints`, `render_mates` and the `studio_*` options
- Objects with a `material` attribute, e.g. from bd_materials, are rendered with it, also in studio mode (`tab="studio"`) ([#7](https://github.com/bernhard-42/tcv_screenshots/issues/7))
- The option enums of `show` (`Camera`, `Collapse`, `Render`, `UiTab`, `Studio*`, `AnalysisTool`) can be imported from `tcv_screenshots`
- `get_saved_models()` returns `(name, message)` tuples, message being the data message of ocp-viewer-core

**Rendering**

- tcv_screenshots is a host of [ocp-viewer-core](https://github.com/bernhard-42/ocp-viewer-core) (Python 1.1.2, JavaScript 1.1.0) and uses three-cad-viewer 5.1.3 (was 3.6.3). It depends on `ocp-viewer-core>=1.1.2,<1.2.0` instead of `ocp_tessellate`
- Repeated parts of a model are sent once and placed by reference: the 100-screw assembly of #5 is 0.67 MB instead of 174 MB
- Every screenshot starts from a fresh viewer page, so settings such as clipping, transparency or the camera of one screenshot no longer carry over to the next
- Studio mode renders supersampled; its image is scaled down to the requested size
- The size of every image is checked against `cad_width` x `height`
- Model data is served to the viewer by a local HTTP server on `127.0.0.1` instead of being passed through Playwright's `page.evaluate`. Large models (e.g. a ~170 MB assembly) no longer crash the browser ([#5](https://github.com/bernhard-42/tcv_screenshots/issues/5))
- After a failed model the browser is restarted, so one crash no longer fails all remaining models

**Errors**

- A failing example prints its full traceback, starting at the example's own code ([#6](https://github.com/bernhard-42/tcv_screenshots/issues/6))
- Any failure while processing examples (error at import, error in `main()`, `main()` not returning a list, invalid items) makes the CLI exit with status 1. Before, only rendering failures did, so a CI job stayed green when every example was broken
- Errors are handled per model: an error in `save_model` fails only that model and the example goes on, and the models an example saved before an error are still rendered
- When rendering fails in the browser, only the first line of Playwright's message is printed (it can carry the browser's whole log or a JavaScript stack); `--debug` prints all of it plus the Python traceback

**Examples**

- `box_cyl_colors.py` saves `box_cyl_colors.png`; it overwrote `faces_only.png` of `box.py` before

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
