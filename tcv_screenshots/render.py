#!/usr/bin/env python3
"""
Headless CAD model renderer.

1. Runs all examples in examples/ folder (each must have a main() returning model or (model, config))
2. Renders all models to PNG screenshots

Cross-platform: Linux (Intel/ARM), Windows (Intel), macOS (Intel/ARM).
"""

import asyncio
import base64
import contextlib
import importlib.resources
import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ocp_tessellate.convert import export_three_cad_viewer_js
from tcv_screenshots import clear_saved_models
from playwright.async_api import async_playwright

# Default configuration for viewer
DEFAULT_CONFIG = {
    # Display options
    "cadWidth": 1200,
    "height": 800,
    "treeWidth": 0,
    "theme": "light",
    "glass": True,
    "tools": False,
    # Render options
    "ambientIntensity": 1.0,
    "directIntensity": 1.1,
    "metalness": 0.3,
    "roughness": 0.65,
    "edgeColor": 0x707070,
    # Viewer options
    "ortho": True,
    "control": "trackball",
    "up": "Z",
}


def get_package_file(filename: str) -> Path:
    """Get path to a file bundled with the package."""
    return importlib.resources.files("tcv_screenshots").joinpath(filename)


# Viewer files served to the browser, with their content types
VIEWER_FILES = {
    "/viewer.html": "text/html; charset=utf-8",
    "/three-cad-viewer.js": "text/javascript; charset=utf-8",
    "/three-cad-viewer.css": "text/css; charset=utf-8",
}


class ViewerRequestHandler(BaseHTTPRequestHandler):
    """Serve the viewer files and the model data (/models/<index>)."""

    def do_GET(self):
        if self.path in VIEWER_FILES:
            body = get_package_file(self.path[1:]).read_bytes()
            content_type = VIEWER_FILES[self.path]
        elif self.path.startswith("/models/"):
            index = self.path.removeprefix("/models/")
            if not index.isdigit() or int(index) >= len(self.server.models):
                self.send_error(404)
                return
            _name, json_data = self.server.models[int(index)]
            body = json.dumps(json_data).encode("utf-8")
            content_type = "application/json"
        else:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Keep the console free of one line per request
        pass


class ViewerServer(ThreadingHTTPServer):
    """
    HTTP server on localhost that hands viewer and models to the browser.

    Model data goes to the page via fetch() instead of page.evaluate():
    Playwright's connection cannot carry large payloads (the browser dies
    on a ~170 MB model), while the page reads them over HTTP without problems.
    """

    daemon_threads = True

    def __init__(self, models: list[tuple[str, dict]]):
        # Port 0: let the OS pick a free port
        super().__init__(("127.0.0.1", 0), ViewerRequestHandler)
        self.models = models

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


@contextlib.contextmanager
def serve_viewer(models: list[tuple[str, dict]]):
    """Run a ViewerServer in a background thread for the duration of the block."""
    server = ViewerServer(models)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


async def launch_viewer(playwright, viewer_url: str, headless: bool, debug: bool):
    """
    Launch a browser and open the viewer page in it.

    Args:
        playwright: The running Playwright instance
        viewer_url: URL of viewer.html
        headless: Run browser in headless mode
        debug: Show browser console debug/info/warning messages

    Returns:
        (browser, page) with the viewer initialized
    """
    # Launch browser with WebGL support
    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--enable-webgl",
            "--ignore-gpu-blocklist",
            "--enable-unsafe-swiftshader",
        ],
    )

    # Create page (viewport will be set per-model based on config)
    page = await browser.new_page()

    # Log page console output
    def log_console(msg):
        if msg.type == "warning" and msg.text.startswith("Unknown option"):
            return
        if msg.type in ("debug", "info", "warning", "log") and not debug:
            return
        print(f"[{msg.type}] {msg.text}")

    page.on("console", log_console)
    page.on("pageerror", lambda err: print(f"PAGE EXCEPTION: {err}"))

    # Load viewer and wait for it to initialize
    try:
        await page.goto(viewer_url)
        await page.wait_for_function(
            "typeof window.loadModel === 'function'",
            timeout=10000,
        )
    except Exception:
        await browser.close()
        raise

    return browser, page


def process_examples(
    examples: Path | list[Path], models_dir: Path = None
) -> list[tuple[str, dict]]:
    """
    Run examples and convert CAD objects to viewer data.

    Each example's main() should return either:
    - model: CAD object to render (uses all defaults)
    - (model, config): CAD object + dict of config overrides
    - list of (model, name, config) tuples from get_saved_models()

    Args:
        examples: Directory containing Python example files, or list of file paths
        models_dir: If provided, save JSON files here (debug mode)

    Returns:
        List of (name, data) tuples where data is {model, config}
    """

    # Determine example files
    if isinstance(examples, list):
        example_files = examples
    else:
        # Find all Python files in directory (excluding __init__.py, __pycache__)
        example_files = sorted(
            f for f in examples.glob("*.py") if not f.name.startswith("_")
        )

    if not example_files:
        print("No example files found")
        return []

    print(f"Found {len(example_files)} example(s) to process")

    # Ensure models directory exists if saving
    if models_dir:
        models_dir.mkdir(parents=True, exist_ok=True)

    processed_models = []

    for example_path in example_files:
        model_name = example_path.stem

        # Skip files that don't import tcv_screenshots
        content = example_path.read_text(encoding="utf-8")
        if "from tcv_screenshots import" not in content and "import tcv_screenshots" not in content:
            print(f"SKIP {model_name}: no tcv_screenshots import")
            continue

        # Clear any leftover saved models from previous example
        clear_saved_models()

        try:
            # Dynamically import the example module
            spec = importlib.util.spec_from_file_location(model_name, example_path)
            module = importlib.util.module_from_spec(spec)

            # Add example's directory to path for relative imports
            sys.path.insert(0, str(example_path.parent))
            try:
                spec.loader.exec_module(module)
            finally:
                sys.path.pop(0)

            # Check for main() function
            if not hasattr(module, "main"):
                print(f"SKIP {model_name}: no main() function, skipping")
                continue

            # Call main() to get saved models
            result = module.main()

            # Expect list from get_saved_models(): [(model, name, config), ...]
            if not isinstance(result, list):
                print(f"SKIP {model_name}: main() must return get_saved_models()")
                continue

            models_to_process = []
            for item in result:
                if isinstance(item, tuple) and len(item) == 3:
                    models_to_process.append(item)
                else:
                    print(f"SKIP {model_name}: invalid item format in get_saved_models()")

            if not models_to_process:
                print(f"SKIP {model_name}: no models to process")
                continue

            # Process each model
            for cad_object, output_name, example_config in models_to_process:
                # Merge defaults with example overrides
                config = {**DEFAULT_CONFIG, **(example_config or {})}

                # Export model to JSON string
                if isinstance(cad_object, tuple|list):
                    cad_objects = cad_object
                else:
                    cad_objects = [cad_object]
                model_json = export_three_cad_viewer_js(
                    None, 
                    *cad_objects, 
                    colors=config.get("colors"), 
                    alphas=config.get("alphas")
                )
                model_data = json.loads(model_json)

                # Create combined data with model and config
                combined_data = {"model": model_data, "config": config}

                # Save to file if debug mode
                if models_dir:
                    output_path = models_dir / f"{output_name}.json"
                    output_path.write_text(json.dumps(combined_data), encoding="utf-8")
                    print(f"OK {output_name}.json")

                processed_models.append((output_name, combined_data))

        except Exception as e:
            print(f"FAILURE {model_name}: {e}")

    return processed_models


async def render_models_to_screenshots(
    models: list[tuple[str, dict]],
    screenshots_dir: Path,
    headless: bool = True,
    pause: bool = False,
    debug: bool = False,
) -> int:
    """
    Render models to PNG screenshots.

    Args:
        models: List of (name, data) tuples where data is {model, config}
        screenshots_dir: Directory for output PNG files
        headless: Run browser in headless mode
        pause: Pause before each screenshot for debugging
        debug: Show browser console debug/info/warning messages

    Returns:
        Number of failures (0 = all succeeded)
    """

    if not models:
        print("No models to render")
        return 0

    print(f"\nRendering {len(models)} model(s) to screenshots")

    # Ensure output directory exists
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    fail_count = 0

    with serve_viewer(models) as server:
        viewer_url = f"{server.base_url}/viewer.html"

        async with async_playwright() as p:
            try:
                browser, page = await launch_viewer(p, viewer_url, headless, debug)
            except Exception as e:
                print(f"Error: Viewer failed to initialize: {e}")
                return 1

            restart = False

            # Process each model
            for index, (model_name, json_data) in enumerate(models):
                output_path = screenshots_dir / f"{model_name}.png"

                # After a failure the page or browser may be dead (crash) or the
                # viewer in a broken state: continue with a fresh browser, otherwise
                # every remaining model fails as well
                if restart:
                    print("Restarting browser after failure")
                    with contextlib.suppress(Exception):
                        await browser.close()
                    try:
                        browser, page = await launch_viewer(
                            p, viewer_url, headless, debug
                        )
                    except Exception as e:
                        print(f"Error: Viewer failed to restart: {e}")
                        fail_count += len(models) - index
                        break
                    restart = False

                try:
                    # Set viewport to match config dimensions
                    config = json_data.get("config", {})
                    width = config.get("cadWidth", DEFAULT_CONFIG["cadWidth"])
                    height = config.get("height", DEFAULT_CONFIG["height"])
                    await page.set_viewport_size({"width": width, "height": height})

                    # Fetch model from the local server, clear previous model and
                    # load the new one
                    await page.evaluate(
                        """async (url) => {
                            const response = await fetch(url);
                            if (!response.ok) {
                                throw new Error(`fetching ${url}: HTTP ${response.status}`);
                            }
                            const data = await response.json();
                            window.clearModel();
                            window.loadModel(data);
                        }""",
                        f"/models/{index}",
                    )

                    # Wait for viewer to be ready
                    await page.wait_for_function("window.isReady()", timeout=30000)

                    # Give extra time for rendering to complete
                    await asyncio.sleep(0.5)

                    # Wait for user input if pause mode
                    if pause:
                        input(f"  {model_name}: Press Enter to take screenshot...")
                        # Print camera state after user interaction
                        camera_state = await page.evaluate("""() => ({
                            position: viewer.getCameraPosition(),
                            quaternion: viewer.getCameraQuaternion(),
                            target: viewer.getCameraTarget(),
                            zoom: viewer.getCameraZoom()
                        })""")
                        print(f"  'position': {camera_state['position']},")
                        print(f"  'quaternion': {camera_state['quaternion']},")
                        print(f"  'target': {camera_state['target']},")
                        print(f"  'zoom': {camera_state['zoom']},")

                    # Get image using viewer's getImage method
                    data_url = await page.evaluate(
                        """async () => {
                            const result = await window.getImage('screenshot');
                            return result.dataUrl;
                        }"""
                    )

                    if not data_url:
                        raise RuntimeError("Failed to capture image")

                    # Convert data URL to bytes and save
                    base64_data = data_url.split(",", 1)[1]
                    image_bytes = base64.b64decode(base64_data)
                    output_path.write_bytes(image_bytes)

                    print(f"OK {model_name}.png")
                    success_count += 1

                except Exception as e:
                    print(f"FAILURE {model_name}: {e}")
                    fail_count += 1
                    restart = True

            # The browser may already be dead after a failure of the last model
            with contextlib.suppress(Exception):
                await browser.close()

    print(f"\nDone: {success_count} succeeded, {fail_count} failed")
    return fail_count


def run(
    examples: Path | list[Path],
    screenshots_dir: Path,
    headless: bool = True,
    pause: bool = False,
    debug_models_dir: Path = None,
):
    """Main entry point."""
    # Process examples (optionally save JSON in debug mode)
    print("=== Processing examples ===\n")
    models = process_examples(examples, debug_models_dir)

    if not models:
        print("No models to render")
        return

    # Render models to screenshots
    print("\n=== Rendering models to screenshots ===")
    fail_count = asyncio.run(
        render_models_to_screenshots(
            models,
            screenshots_dir,
            headless=headless,
            pause=pause,
            debug=debug_models_dir is not None,
        )
    )
    if fail_count > 0:
        sys.exit(1)
