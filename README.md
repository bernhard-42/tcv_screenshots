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

## Usage

```bash
python -m tcv_screenshots examples/ models/ screenshots/ [options]
```

**Arguments:**

- `examples/` - Directory containing Python example files
- `models/` - Directory for JSON model files
- `screenshots/` - Directory for output PNG screenshots

**Options:**

- `--skip-export` - Skip JSON export, only render existing models
- `--skip-render` - Skip rendering, only export JSON models
- `--no-headless` - Show browser window (for debugging)
- `--pause` - Pause before each screenshot (for debugging)

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

**Viewer options:**

- `ortho` - Orthographic projection (default: True)
- `control` - Control type (default: 'trackball')
- `up` - Up axis: 'Z' or 'Y' (default: 'Z')
- `tab` - Active tab: 'tree', 'clip', 'material'

## Development

Build the wheel:

```bash
pip install build
python -m build
```
