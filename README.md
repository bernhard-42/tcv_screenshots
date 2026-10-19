# tcv-screenshots

Headless screenshot generator for three-cad-viewer. Render 3D CAD models to PNG screenshots.

## Supported Platforms

- Linux (Intel, ARM)
- Windows (Intel)
- macOS (Intel, Apple Silicon)

## Installation

```bash
pip install tcv-screenshots
playwright install chromium   # only needed without an installed Chrome or Edge
```

tcv_screenshots uses an installed Google Chrome or Microsoft Edge when there is one, see [Browser](#browser); `tcv_screenshots --check` shows which one. If you use build123d for creating 3D objects, `build123d` neeeds to be installed, similar for CadQuery.

## Usage

```bash
# Single file (output to current directory)
tcv_screenshots -f example.py

# Single file with output folder
tcv_screenshots -f example.py -o screenshots

# Directory of examples (requires -o)
tcv_screenshots -d examples -o screenshots
```

Installing the package puts the `tcv_screenshots` command into the environment's `bin` folder (macOS, Linux) or `Scripts` folder (Windows, `tcv_screenshots.exe`). `python -m tcv_screenshots` does the same, e.g. when that folder is not on the `PATH`.

**Options:**

- `-f, --file FILE` - Single Python example file to process
- `-d, --directory DIR` - Directory containing Python example files (requires -o)
- `-o, --output-folder DIR` - Output directory for PNG screenshots
- `--no-headless` - Show browser window (for debugging)
- `--pause` - Pause before each screenshot (for debugging)
- `--no-gpu` - Render with the software renderer SwiftShader instead of the GPU, e.g. on CI runners, see [GPU Rendering](#gpu-rendering)
- `--browser {chrome,msedge,chromium}` - Use this browser only, see [Browser](#browser)
- `--check` - Show which browsers work, with version and renderer, and which one a run would use; renders nothing
- `--debug MODELS_DIR` - Save JSON model files to directory, show browser console messages and full rendering errors (for debugging)

## Writing Examples

Create a Python file with a `main()` function that uses `screenshot` and returns `get_screenshots()`:

```python
from build123d import *

model = Box(10, 20, 30)

def main():
    from tcv_screenshots import screenshot, get_screenshots

    screenshot(model, name="box", cad_width=800, height=600)
    return get_screenshots()
```

`screenshot(*cad_objs, name, **kwargs)` takes the CAD objects like `show` of [OCP CAD Viewer](https://github.com/bernhard-42/vscode-ocp-cad-viewer), a `name` for the PNG file, and any keyword of `show`, e.g. `colors`, `alphas`, `modes`, `materials`, `render_joints`, `reset_camera` or the `studio_*` options. Both use the same pipeline ([ocp-viewer-core](https://github.com/bernhard-42/ocp-viewer-core)), so the same call gives the same result as in the viewer. Objects with a `material` (e.g. from bd_materials) are rendered with it.

### Multiple Models per Example

For incremental examples that need screenshots at different stages:

```python
from build123d import *

# Step 1: Create base box
box = Box(10, 10, 10)

# Step 2: Add fillet
filleted = fillet(box.edges(), 1)

# Step 3: Add hole
final = filleted - Cylinder(2, 10)

def main():
    from tcv_screenshots import Render, screenshot, get_screenshots

    size = {"cad_width": 500, "height": 375}

    screenshot(box, name="step1_box", **size)
    screenshot(filleted, name="step2_fillet", **size)
    screenshot(final, name="step3_hole", modes=[Render.FACES], **size)

    return get_screenshots()
```

This generates `step1_box.png`, `step2_fillet.png`, and `step3_hole.png`.

### Complex Example

```python
from build123d import *

def create_hexapod():
    ...

hexapod = create_hexapod()

def main():
    from tcv_screenshots import screenshot, get_screenshots

    screenshot(
        hexapod,
        name="hexapod",
        cad_width=800,
        height=600,
        axes=True,
        transparent=True,
        clip_intersection=True,
        clip_slider_0=0,
        clip_slider_1=0,
        clip_slider_2=20,
        tab="clip",
        position=[465.1, 475.9, 463.2],
        quaternion=[0.18, 0.46, 0.80, 0.35],
        target=[-100, -93.4, -9.0],
        zoom=1.2,
    )

    return get_screenshots()
```

![hexapod](screenshots/hexapod.png)

### Available Options

Every keyword of `show`, see [OCP CAD Viewer's show command](https://github.com/bernhard-42/vscode-ocp-cad-viewer/blob/main/docs/show.md). The enums used there (`Camera`, `Collapse`, `Render`, `UiTab`, `Studio*`, ...) can be imported from `tcv_screenshots`. `port`, `viewer`, `anchor` and `pinning` address a viewer window and are ignored with a warning.

**Defaults of a screenshot** (override them for all following screenshots with `set_defaults(**kwargs)`, or for one screenshot with the keyword of the same name; `reset_defaults()` goes back to these):

- `cad_width` - Image width (default: 1200, minimum 450)
- `height` - Image height (default: 800)
- `theme` - 'light' or 'dark' (default: 'light')
- `glass` - Glass mode (default: True)
- `tools` - Show tools (default: False)
- `ambient_intensity` - Ambient light intensity (default: 1.0)
- `direct_intensity` - Direct light intensity (default: 1.1)
- `metalness` - Material metalness (default: 0.3)
- `roughness` - Material roughness (default: 0.65)
- `default_edgecolor` - Edge color (default: '#707070')
- `ortho` - Orthographic projection (default: True)
- `up` - Up axis: 'Z' or 'Y' (default: 'Z')
- `reset_camera` - Camera view (default: `Camera.RESET`); also 'iso', 'front', 'rear', 'left', 'right', 'top', 'bottom'

Every screenshot starts with a fresh viewer, so no setting carries over from one screenshot to the next.

Use `--no-headless --pause` to adjust the view by hand; the camera values (`position`, `quaternion`, `target`, `zoom`) are printed before each screenshot and can be passed to `screenshot`.

## Scripted Use

The two steps of the command line are functions, for build scripts that need more control:

```python
from build123d import Box
from tcv_screenshots import (
    collect_models,
    get_failed_models,
    get_screenshots,
    render_models,
    screenshot,
    set_defaults,
)

# Defaults for every following screenshot call, the keywords of `show`
set_defaults(cad_width=1000, height=1000)

# Run example files and directories of examples (each with a main() as above)
collected = collect_models("examples", "more/extra_example.py")

# Or save models directly, without example files
screenshot(Box(1, 2, 3), name="box")
failed_saves = [name for name, _traceback in get_failed_models()]

rendered = render_models(collected.models + get_screenshots(), "screenshots")
print(rendered.written)                                    # the PNG files
print(collected.failed + failed_saves + rendered.failed)  # names of what failed
```

- `collect_models(*paths, models_dir=None)` returns a `CollectResult` with `models` and `failed`. Each example runs with the defaults set before the call; a `set_defaults` inside one example does not reach the next. Screenshots a script requested with `screenshot` before the call stay in the collector for `get_screenshots()`. With `models_dir`, every model's JSON is saved there.
- `render_models(models, output_dir, *, headless=True, pause=False, debug=False, gpu=True, browser=None)` writes `<output_dir>/<name>.png` and returns a `RenderResult` with `written` and `failed`. In an environment that already runs an event loop (e.g. Jupyter), use `await render_models_async(...)` with the same arguments.
- Neither function exits: failures are printed, with tracebacks, and returned.
- `screenshot` does not raise either: a model it cannot create is printed as `FAILURE` with its traceback, and `get_failed_models()` returns the `(name, traceback)` pairs since the last call. `collect_models` counts these in its `failed`; a script that calls `screenshot` itself reads them with `get_failed_models()`.

## GPU Rendering

By default the browser renders with the GPU. `--no-gpu` (or `render_models(..., gpu=False)`) renders with SwiftShader, a software renderer, instead: it needs no GPU, e.g. on CI runners, but large models are much slower. Use it in CI, as in [.github/workflows/screenshots.yml](.github/workflows/screenshots.yml).

| Machine | 8 examples of this repo, whole run | heat exchanger (149 filleted tubes, 33 MB of mesh) and an assembly of 100 screws |
| --- | --- | --- |
| Apple M1 Max, macOS: SwiftShader | 20.2 s | 112.8 s |
| Apple M1 Max, macOS: GPU (Metal) | 11.0 s | 2.5 s |
| Ryzen 9 7900 + RTX 5060, Linux: SwiftShader | 11.9 s | 73.6 s |
| Ryzen 9 7900 + RTX 5060, Linux: GPU (Vulkan) | 9.9 s | 2.5 s |
| Ryzen 9 7900 + RTX 5060, Windows 11: SwiftShader | 12.1 s | 65.9 s |
| Ryzen 9 7900 + RTX 5060, Windows 11: GPU (Direct3D 11) | 8.3 s | 2.4 s |

GPU and SwiftShader images differ in anti-aliasing only (at most 0.6% of the pixels by more than 32/255 in these examples); SwiftShader images of different machines and Chromium versions differ much less, but are not byte-identical either. A comparison against stored reference images should therefore use one renderer consistently. The renderer is printed (`GPU rendering: ...`). Without a usable GPU, Chromium falls back to SwiftShader and a warning says so; `--no-gpu` makes that choice explicit and silent. Verified on macOS (Metal), Linux (Vulkan) and Windows 11 (Direct3D 11 with `--force_high_performance_gpu`, which picks the discrete GPU over the integrated one).

## Browser

tcv_screenshots drives a Chromium-based browser through Playwright. On every run it uses the first that works of:

| Platform      | Order                                                    |
| ------------- | -------------------------------------------------------- |
| Windows       | Microsoft Edge (always installed), Google Chrome, Playwright's Chromium |
| macOS, Linux  | Google Chrome, Microsoft Edge, Playwright's Chromium     |

An installed Chrome or Edge saves the download of Playwright's own Chromium (`playwright install chromium`, several hundred MB). A browser that is not installed is skipped within milliseconds, so nothing is stored between runs. The browser in use is printed (`Browser: chrome 155.0...`).

- `--check` lists every candidate with its version and WebGL renderer and names the one a run would use. If none works, it says to run `playwright install chromium` and exits with status 1.
- `--browser chrome|msedge|chromium` (`render_models(..., browser="chromium")`) uses exactly that browser, without falling back.

An installed Chrome or Edge updates itself, so screenshots can change slightly between its versions. For reproducible screenshots, e.g. in CI, pin Playwright's Chromium, whose version only changes with the Playwright version: `--browser chromium`. Firefox and WebKit are not supported: Playwright needs its own builds of them and cannot drive an installed Firefox or Safari.

## Migration from 0.3.0

0.4.0 renders through [ocp-viewer-core](https://github.com/bernhard-42/ocp-viewer-core), the pipeline of OCP CAD Viewer, with three-cad-viewer 5.1.3 instead of 3.6.3. `save_model` is now `screenshot`, and it takes the arguments of `show` instead of a config dict; `get_saved_models` is now `get_screenshots`. The old names still work with the new arguments, but are deprecated and print a `FutureWarning`. Example files and the command line keep working once their `save_model` calls are converted. Code that used internals of `tcv_screenshots.render` has to move to the functions of [Scripted Use](#scripted-use).

### `save_model` calls become `screenshot` calls

| 0.3.0                                                      | 0.4.0                                                    |
| ---------------------------------------------------------- | -------------------------------------------------------- |
| `save_model(box, "box", {"cadWidth": 500, "height": 375})` | `screenshot(box, name="box", cad_width=500, height=375)` |
| `save_model([box, cyl], "pair", config)`                   | `screenshot(box, cyl, name="pair", ...)`                 |
| `{"colors": ["red", "blue"], "alphas": [0.5, 1.0]}`        | `colors=["red", "blue"], alphas=[0.5, 1.0]`              |
| `{"render_edges": False}`                                  | `modes=[Render.FACES]`                                   |
| `{"render_faces": False}`                                  | `modes=[Render.EDGES]`                                   |

- `name` is a keyword argument now.
- Pass several objects as separate positional arguments. 0.3.0 split a list into its objects; 0.4.0 shows a list as one object, so `colors` and `alphas` apply to it as a whole.
- `modes` takes a list with one value per object, and `Render` (like the other option enums) is imported from `tcv_screenshots`.

### Config keys become `show` keywords

The keys of the config dict were three-cad-viewer's camelCase names; the keywords are those of `show` in snake_case. Most keys convert mechanically (`clipSlider0` → `clip_slider_0`, `blackEdges` → `black_edges`, `clipIntersection` → `clip_intersection`, `clipObjectColors` → `clip_object_colors`, `ambientIntensity` → `ambient_intensity`). These do not:

| 0.3.0 config key                   | 0.4.0 keyword                  |
| ---------------------------------- | ------------------------------ |
| `cadWidth`                         | `cad_width` (minimum 450)      |
| `treeWidth`                        | `tree_width`                   |
| `edgeColor: 0x707070`              | `default_edgecolor="#707070"`  |
| `control: "trackball"` / `"orbit"` | `orbit_control=False` / `True` |
| `clipPlaneHelpers`                 | `clip_planes`                  |

Unchanged: `height`, `theme`, `glass`, `tools`, `ortho`, `up`, `axes`, `transparent`, `tab`, `zoom`, `position`, `quaternion`, `target`, `reset_camera`.

### Removed internals

| 0.3.0                                                                                                    | 0.4.0                                                                                                                    |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `get_saved_models()` returns `(model, name, config)` tuples                                              | `get_screenshots()` returns `(name, message)` tuples, `message` being ocp-viewer-core's data message; pass them to `render_models` unchanged |
| `tcv_screenshots.render.process_examples(examples)`                                                      | `collect_models(*paths)`, returns a `CollectResult`                                                                      |
| `await tcv_screenshots.render.render_models_to_screenshots(models, dir)`, returns the number of failures | `render_models(models, dir)` or `await render_models_async(models, dir)`, returns a `RenderResult`                       |
| `tcv_screenshots.render.DEFAULT_CONFIG`, merged into each config                                         | `set_defaults(...)` with `show` keywords, before the `screenshot` calls                                                  |
| model data built with ocp_tessellate's `export_three_cad_viewer_js` as `{"model": ..., "config": ...}`   | not understood by the new viewer page; create every model with `screenshot`                                              |

A build script that imported its model modules and rendered their saved models looked like this in 0.3.0:

```python
from tcv_screenshots import get_saved_models
from tcv_screenshots.render import DEFAULT_CONFIG, render_models_to_screenshots

# ... import the modules that call save_model ...

models = []
for obj, name, config in get_saved_models():
    model = json.loads(export_three_cad_viewer_js(None, obj))
    models.append((name, {"model": model, "config": {**DEFAULT_CONFIG, "cadWidth": 1000, **config}}))
if asyncio.run(render_models_to_screenshots(models, destination)) > 0:
    sys.exit(1)
```

In 0.4.0:

```python
from tcv_screenshots import get_failed_models, get_screenshots, render_models, set_defaults

# Defaults apply when screenshot is called, so set them first
set_defaults(cad_width=1000, height=1000)

# ... import the modules that call screenshot ...

# screenshot has printed its errors; collect them for the exit status
failed = [name for name, _traceback in get_failed_models()]
result = render_models(get_screenshots(), destination)
if len(failed) > 0 or len(result.failed) > 0:
    sys.exit(1)
```

A camera computed by the script goes to `screenshot` as keywords: `position=`, `quaternion=`, `target=`, `zoom=`.

### Behaviour changes

- Every screenshot starts with a fresh viewer: settings of one screenshot (clipping, transparency, camera, tab) no longer carry over to the next.
- Rendering uses the GPU by default; 0.3.0 always used the software renderer SwiftShader. In CI without a GPU, add `--no-gpu` (images then match what 0.4.0 renders with SwiftShader elsewhere).
- The command line exits with status 1 when an example fails to load or run, not only when rendering fails.
- An error in `screenshot` (formerly `save_model`) no longer raises: it is printed with its traceback, the screenshot is recorded as failed (`get_failed_models()`), and the code calling `screenshot` goes on. A leftover 0.3.0 key such as `cadWidth=500` shows up this way, as `TypeError: ... unexpected keyword argument 'cadWidth'`.

## CI/CD

`tcv_screenshots` can be used in CI/CD workflows, an example can seen in [.github/workflows/screenshots.yml](.github/workflows/screenshots.yml). The command line exits with status 1 if any example or model fails.

## Development

Install with the development tools and run the tests:

```bash
pip install -e ".[dev]"
playwright install chromium
python -m pytest
```

- `python -m pytest -m "not browser"` runs only the fast tests, without a browser (seconds).
- `python -m pytest --no-gpu` renders the browser tests with SwiftShader, as CI does on runners without a GPU.
- Browser tests compare images within one run, not with stored reference images: GPU and SwiftShader, and different machines, differ slightly in anti-aliasing.

Build the wheel:

```bash
python -m build
```
