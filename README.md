# tcv-screenshots

Headless screenshot generator for three-cad-viewer. Render 3D CAD models to PNG screenshots.

## Supported Platforms

- Linux (Intel, ARM)
- Windows (Intel)
- macOS (Intel, Apple Silicon)

## Installation

```bash
pip install tcv-screenshots
playwright install chromium
```

If you use build123d for creating 3D objects, `build123d` neeeds to be installed, similar for CadQuery.

## Usage

```bash
python -m tcv_screenshots examples/ screenshots/ [options]
```

**Arguments:**

- `examples/` - Directory containing Python example files
- `screenshots/` - Directory for output PNG screenshots

**Options:**

- `--no-headless` - Show browser window (for debugging)
- `--pause` - Pause before each screenshot (for debugging)
- `--debug MODELS_DIR` - Save JSON model files to directory (for debugging)

## Writing Examples

Create a Python file with a `main()` function that returns a CAD model:

```python
from build123d import *

def main():
    return Box(10, 20, 30)
```

### Custom Config (Optional)

To override defaults, return `(model, config)`:

```python
def main():
    model = Box(10, 20, 30)
    config = {
        "cadWidth": 800,
        "height": 600,
        "metalness": 0.8,
        "tab": "clip",
    }
    return model, config
```

### Multiple Models per Example

For incremental examples that need screenshots at different stages, use `save_model`:

```python
from build123d import *
from tcv_screenshots import save_model, get_saved_models

config = {"cadWidth": 500, "height": 375}

# Step 1: Create base box
box = Box(10, 10, 10)
save_model(box, "step1_box", config)

# Step 2: Add fillet
filleted = fillet(box.edges(), 1)
save_model(filleted, "step2_fillet", config)

# Step 3: Add hole
final = filleted - Cylinder(2, 10)
save_model(final, "step3_hole", {**config, "render_edges": False})

def main():
    return get_saved_models()
```

This generates `step1_box.png`, `step2_fillet.png`, and `step3_hole.png`.

### Available Config Options

See [VS Code CAD Viewer's show command](https://github.com/bernhard-42/vscode-ocp-cad-viewer/blob/main/docs/show.md)

#### Examples

**Display options:**

- `cadWidth` - Viewport width (default: 1200)
- `height` - Viewport height (default: 800)
- `treeWidth` - Tree panel width (default: 0)
- `theme` - 'light' or 'dark' (default: 'light')
- `glass` - Glass mode (default: True)
- `tools` - Show tools (default: False)

**Render options:**

- `ambientIntensity` - Ambient light intensity (default: 1.0)
- `directIntensity` - Direct light intensity (default: 1.1)
- `metalness` - Material metalness (default: 0.3)
- `roughness` - Material roughness (default: 0.65)
- `edgeColor` - Edge color as hex int (default: 0x707070)
- `render_edges` - Show edges (default: True)
- `render_faces` - Show faces (default: True)

**Viewer options:**

- `ortho` - Orthographic projection (default: True)
- `control` - Control type (default: 'trackball')
- `up` - Up axis: 'Z' or 'Y' (default: 'Z')
- `tab` - Active tab: 'tree', 'clip', 'material'
- `reset_camera` - Camera view: 'iso', 'front', 'rear', 'left', 'right', 'top', 'bottom'

## CI/CD

`tcv_screenshots` can be used in CI/CD workflows, an example can seen in [.github/workflows/screenshots.yml](.github/workflows/screenshots.yml)

## Development

Build the wheel:

```bash
pip install build
python -m build
```
