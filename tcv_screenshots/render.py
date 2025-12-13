#!/usr/bin/env python3
"""
Headless CAD model renderer.

1. Runs all examples in examples/ folder (each must have a main() returning model or (model, config))
2. Renders all models to PNG screenshots

Cross-platform: Linux (Intel/ARM), Windows (Intel), macOS (Intel/ARM).
"""

import asyncio
import base64
import importlib.resources
import importlib.util
import json
import sys
from pathlib import Path


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
    # Import ocp_tessellate once (heavy import)
    from ocp_tessellate.convert import export_three_cad_viewer_js

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

        # Clear any leftover saved models from previous example
        from tcv_screenshots import clear_saved_models
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

            # Call main() to get the CAD object(s) and config(s)
            result = module.main()

            # Normalize result to list of (model, name, config)
            models_to_process = []

            if isinstance(result, list):
                # List from get_saved_models(): [(model, name, config), ...]
                for item in result:
                    if isinstance(item, tuple) and len(item) == 3:
                        models_to_process.append(item)
                    else:
                        print(f"SKIP {model_name}: invalid list item format")
            elif isinstance(result, tuple) and len(result) == 2:
                # Old format: (model, config)
                models_to_process.append((result[0], model_name, result[1]))
            elif result is not None:
                # Single model, no config
                models_to_process.append((result, model_name, {}))
            else:
                print(f"SKIP {model_name}: main() returned None, skipping")
                continue

            if not models_to_process:
                print(f"SKIP {model_name}: no models to process")
                continue

            # Process each model
            for cad_object, output_name, example_config in models_to_process:
                # Merge defaults with example overrides
                config = {**DEFAULT_CONFIG, **(example_config or {})}

                # Export model to JSON string
                model_json = export_three_cad_viewer_js(None, cad_object)
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
    from playwright.async_api import async_playwright

    if not models:
        print("No models to render")
        return 0

    print(f"\nRendering {len(models)} model(s) to screenshots")

    # Ensure output directory exists
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Get viewer.html from package
    viewer_path = get_package_file("viewer.html")

    success_count = 0
    fail_count = 0

    async with async_playwright() as p:
        # Launch browser with WebGL support
        browser = await p.chromium.launch(
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

        # Load viewer
        await page.goto(f"file://{viewer_path}")

        # Wait for viewer to initialize
        try:
            await page.wait_for_function(
                "typeof window.loadModel === 'function'",
                timeout=10000,
            )
        except Exception as e:
            print(f"Error: Viewer failed to initialize: {e}")
            await browser.close()
            return 1

        # Process each model
        for model_name, json_data in models:
            output_path = screenshots_dir / f"{model_name}.png"

            try:
                # Set viewport to match config dimensions
                config = json_data.get("config", {})
                width = config.get("cadWidth", DEFAULT_CONFIG["cadWidth"])
                height = config.get("height", DEFAULT_CONFIG["height"])
                await page.set_viewport_size({"width": width, "height": height})

                # Clear previous model and load new one
                await page.evaluate(
                    """(data) => {
                        if (window.viewer && window.viewer.clear) {
                            window.viewer.clear();
                        }
                        window.loadModel(data);
                    }""",
                    json_data,
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
