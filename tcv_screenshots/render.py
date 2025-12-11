#!/usr/bin/env python3
"""
Headless CAD model renderer.

1. Runs all examples in examples/ folder (each must have a main() returning model or (model, config))
2. Exports them to JSON in models/
3. Renders all models to PNG screenshots

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


def export_examples_to_json(examples_dir: Path, models_dir: Path) -> list[Path]:
    """
    Run all examples and export CAD objects to JSON files.

    Each example's main() should return either:
    - model: CAD object to render (uses all defaults)
    - (model, config): CAD object + dict of config overrides

    Returns:
        List of generated JSON file paths
    """
    # Import ocp_tessellate once (heavy import)
    from ocp_tessellate.convert import export_three_cad_viewer_js

    # Find all Python files in examples (excluding __init__.py, __pycache__)
    example_files = sorted(
        f for f in examples_dir.glob("*.py")
        if not f.name.startswith("_")
    )

    if not example_files:
        print(f"No example files found in {examples_dir}")
        return []

    print(f"Found {len(example_files)} example(s) to export")

    # Ensure models directory exists
    models_dir.mkdir(parents=True, exist_ok=True)

    generated_files = []

    for example_path in example_files:
        model_name = example_path.stem
        output_path = models_dir / f"{model_name}.json"

        try:
            # Dynamically import the example module
            spec = importlib.util.spec_from_file_location(model_name, example_path)
            module = importlib.util.module_from_spec(spec)

            # Add examples dir to path for relative imports within examples
            sys.path.insert(0, str(examples_dir))
            try:
                spec.loader.exec_module(module)
            finally:
                sys.path.pop(0)

            # Check for main() function
            if not hasattr(module, "main"):
                print(f"SKIP {model_name}: no main() function, skipping")
                continue

            # Call main() to get the CAD object and config
            result = module.main()

            # Handle both (model, config) tuple and single model return
            if isinstance(result, tuple) and len(result) == 2:
                cad_object, example_config = result
            else:
                cad_object = result
                example_config = {}

            if cad_object is None:
                print(f"SKIP {model_name}: main() returned None, skipping")
                continue

            # Merge defaults with example overrides
            config = {**DEFAULT_CONFIG, **(example_config or {})}

            # Export model to JSON string
            model_json = export_three_cad_viewer_js(None, cad_object)
            model_data = json.loads(model_json)

            # Create combined JSON with model and config
            combined_data = {
                "model": model_data,
                "config": config
            }

            output_path.write_text(json.dumps(combined_data), encoding="utf-8")

            print(f"OK {model_name}.json")
            generated_files.append(output_path)

        except Exception as e:
            print(f"FAILURE {model_name}: {e}")

    return generated_files


async def render_models_to_screenshots(
    models_dir: Path,
    screenshots_dir: Path,
    headless: bool = True,
    pause: bool = False
) -> int:
    """
    Render all JSON model files to PNG screenshots.

    Args:
        models_dir: Directory containing JSON model files
        screenshots_dir: Directory for output PNG files
        headless: Run browser in headless mode
        pause: Pause before each screenshot for debugging

    Returns:
        Number of failures (0 = all succeeded)
    """
    from playwright.async_api import async_playwright

    # Find all JSON files
    json_files = sorted(models_dir.glob("*.json"))

    if not json_files:
        print(f"No JSON files found in {models_dir}")
        return 0

    print(f"\nRendering {len(json_files)} model(s) to screenshots")

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
        page.on("console", lambda msg: print(f"[{msg.type}] {msg.text}"))
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
        for model_path in json_files:
            model_name = model_path.stem
            output_path = screenshots_dir / f"{model_name}.png"

            try:
                # Load JSON data (contains {model, config})
                json_data = json.loads(model_path.read_text(encoding="utf-8"))

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
                    print(f"  position: {camera_state['position']}")
                    print(f"  quaternion: {camera_state['quaternion']}")
                    print(f"  target: {camera_state['target']}")
                    print(f"  zoom: {camera_state['zoom']}")

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
    examples_dir: Path,
    models_dir: Path,
    screenshots_dir: Path,
    headless: bool = True,
    pause: bool = False,
    skip_export: bool = False,
    skip_render: bool = False,
):
    """Main entry point."""
    # Phase 1: Export examples to JSON
    if not skip_export:
        print("=== Exporting examples to JSON ===\n")
        export_examples_to_json(examples_dir, models_dir)

    # Phase 2: Render models to screenshots
    if not skip_render:
        print("\n=== Rendering models to screenshots ===")
        fail_count = asyncio.run(render_models_to_screenshots(
            models_dir,
            screenshots_dir,
            headless=headless,
            pause=pause
        ))
        if fail_count > 0:
            sys.exit(1)
