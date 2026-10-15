#!/usr/bin/env python3
"""
Headless CAD model renderer.

1. Runs all examples in examples/ folder (each must have a main() returning
   get_saved_models())
2. Renders all saved models to PNG screenshots

Cross-platform: Linux (Intel/ARM), Windows (Intel), macOS (Intel/ARM).
"""

import asyncio
import base64
import contextlib
import importlib.resources
import importlib.util
import json
import struct
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from textwrap import indent

from ocp_viewer_core.codec import default as json_default
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from tcv_screenshots.host import (
    clear_saved_models,
    get_failed_models,
    get_saved_models,
)

# Seconds to wait for the viewer to deliver an image of a loaded model
IMAGE_TIMEOUT = 30.0


def get_package_dir() -> Path:
    """Directory of the installed package (viewer.html, static/)."""
    return Path(str(importlib.resources.files("tcv_screenshots")))


# Content types of the files the page loads. The JavaScript is ES modules,
# which a browser only executes when served with a JavaScript content type.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def resolve_viewer_file(url_path: str) -> Path | None:
    """
    Map a request path to viewer.html or a file below static/.

    Returns:
        The file, or None if the path does not name one of them
    """
    package_dir = get_package_dir()
    if url_path == "/viewer.html":
        return package_dir / "viewer.html"
    if not url_path.startswith("/static/"):
        return None

    static_dir = (package_dir / "static").resolve()
    candidate = (package_dir / url_path.removeprefix("/")).resolve()
    # No way out of static/, e.g. by "/static/../render.py"
    if not candidate.is_relative_to(static_dir) or not candidate.is_file():
        return None
    return candidate


class ViewerRequestHandler(BaseHTTPRequestHandler):
    """Serve the viewer page, its static files and the models (/models/<index>)."""

    def do_GET(self):
        if self.path.startswith("/models/"):
            index = self.path.removeprefix("/models/")
            if not index.isdigit() or int(index) >= len(self.server.models):
                self.send_error(404)
                return
            _name, message = self.server.models[int(index)]
            body = json.dumps(message, default=json_default).encode("utf-8")
            content_type = "application/json"
        else:
            file = resolve_viewer_file(self.path)
            if file is None or file.suffix not in CONTENT_TYPES:
                self.send_error(404)
                return
            body = file.read_bytes()
            content_type = CONTENT_TYPES[file.suffix]

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
    The page's ES modules need HTTP anyway, they do not load from file://.
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


def png_size(image_bytes: bytes) -> tuple[int, int]:
    """Width and height of a PNG, read from its IHDR chunk."""
    width, height = struct.unpack(">II", image_bytes[16:24])
    return width, height


def format_traceback(trace: traceback.TracebackException, example_path: Path) -> str:
    """
    Traceback of an error in an example, starting at the example's own code.

    The frames above it belong to the runner (this module, importlib) and
    would only bury the relevant part. A traceback without any frame of the
    example, e.g. of a SyntaxError, keeps none of them: the error message
    itself names file and line then.
    """
    frames = list(trace.stack)
    first = len(frames)
    for i, frame in enumerate(frames):
        if frame.filename == str(example_path):
            first = i
            break
    trace.stack = traceback.StackSummary.from_list(frames[first:])
    return indent("".join(trace.format()).rstrip("\n"), "    ")


def report_failure(
    name: str, trace: traceback.TracebackException, example_path: Path
) -> None:
    """Print a FAILURE line with the error, followed by its traceback."""
    summary = list(trace.format_exception_only())[-1].strip()
    print(f"FAILURE {name}: {summary}")
    print(format_traceback(trace, example_path))


def import_example(example_path: Path):
    """Import an example file as a module, running its top level code."""
    spec = importlib.util.spec_from_file_location(example_path.stem, example_path)
    module = importlib.util.module_from_spec(spec)

    # Add example's directory to path for relative imports
    sys.path.insert(0, str(example_path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def process_examples(
    examples: Path | list[Path], models_dir: Path = None
) -> tuple[list[tuple[str, dict]], int]:
    """
    Run examples and collect their saved models.

    Each example's main() must return get_saved_models(), i.e. a list of
    (name, message) tuples created by save_model().

    Errors are handled per model where possible: a failing save_model() call
    fails only its own model, and the models an example saved before raising
    an error are still returned.

    Args:
        examples: Directory containing Python example files, or list of file paths
        models_dir: If provided, save JSON files here (debug mode)

    Returns:
        List of (name, message) tuples, message being ocp-viewer-core's data
        message, and the number of failures
    """

    # Determine example files
    if isinstance(examples, list):
        example_files = examples
    else:
        # Find all Python files in directory (excluding __init__.py, __pycache__)
        example_files = sorted(
            f for f in examples.glob("*.py") if not f.name.startswith("_")
        )

    if len(example_files) == 0:
        print("No example files found")
        return [], 0

    print(f"Found {len(example_files)} example(s) to process")

    # Ensure models directory exists if saving
    if models_dir is not None:
        models_dir.mkdir(parents=True, exist_ok=True)

    processed_models = []
    fail_count = 0

    for example_path in example_files:
        model_name = example_path.stem

        # Skip files that don't import tcv_screenshots
        content = example_path.read_text(encoding="utf-8")
        if "from tcv_screenshots import" not in content and "import tcv_screenshots" not in content:
            print(f"SKIP {model_name}: no tcv_screenshots import")
            continue

        # Clear models a previous example saved but never returned
        clear_saved_models()

        error = None
        try:
            module = import_example(example_path)

            # Check for main() function
            if not hasattr(module, "main"):
                print(f"SKIP {model_name}: no main() function, skipping")
                continue

            # Call main() to get saved models
            result = module.main()
        except Exception as e:
            error = e
            # The models saved before the error are still rendered
            result = get_saved_models()

        # save_model() records its errors instead of raising them, so the
        # example went on after them
        for output_name, trace in get_failed_models():
            report_failure(output_name, trace, example_path)
            fail_count += 1

        if error is not None:
            trace = traceback.TracebackException.from_exception(error)
            report_failure(model_name, trace, example_path)
            fail_count += 1

        # Expect list from get_saved_models(): [(name, message), ...]
        if not isinstance(result, list):
            print(
                f"FAILURE {model_name}: main() must return get_saved_models(), "
                f"got {type(result).__name__}"
            )
            fail_count += 1
            continue

        models_to_process = []
        for item in result:
            if (
                isinstance(item, tuple)
                and len(item) == 2
                and isinstance(item[0], str)
                and isinstance(item[1], dict)
            ):
                models_to_process.append(item)
            else:
                print(
                    f"FAILURE {model_name}: invalid item in get_saved_models(): "
                    f"{item!r:.80}"
                )
                fail_count += 1

        if len(models_to_process) == 0:
            if error is None:
                print(f"SKIP {model_name}: no models to process")
            continue

        for output_name, message in models_to_process:
            # Save to file if debug mode
            if models_dir is not None:
                output_path = models_dir / f"{output_name}.json"
                try:
                    output_path.write_text(
                        json.dumps(message, default=json_default), encoding="utf-8"
                    )
                except Exception as e:
                    trace = traceback.TracebackException.from_exception(e)
                    report_failure(output_name, trace, example_path)
                    fail_count += 1
                    continue
                print(f"OK {output_name}.json")

            processed_models.append((output_name, message))

    return processed_models, fail_count


def describe_render_error(error: Exception, debug: bool) -> str:
    """
    Message of an error while rendering a model.

    When the browser dies, Playwright appends the browser's whole log to the
    message, and JavaScript errors bring their stack. Unless debug is set,
    keep only the first line.
    """
    message = str(error).strip()
    if debug or not isinstance(error, PlaywrightError):
        return message

    lines = message.splitlines()
    if len(lines) <= 1:
        return message
    return f"{lines[0]} [{len(lines) - 1} more lines with --debug]"


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

    # Load viewer and wait for its module script to have run
    try:
        await page.goto(viewer_url)
        await page.wait_for_function("window.viewerLoaded === true", timeout=10000)
    except Exception:
        await browser.close()
        raise

    return browser, page


async def capture_image(page, model_name: str) -> bytes:
    """
    Capture the loaded model as PNG.

    The viewer answers with no image until it is ready to render, so ask again
    until it delivers one or IMAGE_TIMEOUT has passed.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + IMAGE_TIMEOUT
    while True:
        data_url = await page.evaluate("(name) => window.getImage(name)", model_name)
        if isinstance(data_url, str) and data_url != "":
            return base64.b64decode(data_url.split(",", 1)[1])
        if loop.time() > deadline:
            raise RuntimeError(f"no image after {IMAGE_TIMEOUT:.0f}s")
        await asyncio.sleep(0.25)


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
        models: List of (name, message) tuples from process_examples
        screenshots_dir: Directory for output PNG files
        headless: Run browser in headless mode
        pause: Pause before each screenshot for debugging
        debug: Show browser console debug/info/warning messages

    Returns:
        Number of failures (0 = all succeeded)
    """

    if len(models) == 0:
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
                print(
                    "Error: Viewer failed to initialize: "
                    f"{describe_render_error(e, debug)}"
                )
                return len(models)

            restart = False

            # Process each model
            for index, (model_name, message) in enumerate(models):
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
                        print(
                            "Error: Viewer failed to restart: "
                            f"{describe_render_error(e, debug)}"
                        )
                        fail_count += len(models) - index
                        break
                    restart = False
                elif index > 0:
                    # A fresh page per screenshot: the viewer keeps its state
                    # across models (clipping, transparency, tab, camera), so
                    # without this a screenshot would depend on the ones before
                    try:
                        await page.reload()
                        await page.wait_for_function(
                            "window.viewerLoaded === true", timeout=10000
                        )
                    except Exception as e:
                        print(
                            f"FAILURE {model_name}: reloading viewer: "
                            f"{describe_render_error(e, debug)}"
                        )
                        fail_count += 1
                        restart = True
                        continue

                try:
                    config = message["config"]
                    width = config["cadWidth"]
                    height = config["height"]
                    await page.set_viewport_size({"width": width, "height": height})

                    # The page fetches the model from the local server
                    await page.evaluate(
                        "(url) => window.loadModel(url)", f"/models/{index}"
                    )

                    # Give time for rendering to complete
                    await asyncio.sleep(0.5)

                    # Wait for user input if pause mode
                    if pause:
                        input(f"  {model_name}: Press Enter to take screenshot...")
                        # Print camera state after user interaction
                        camera_state = await page.evaluate("() => window.getCamera()")
                        print(f"  'position': {camera_state['position']},")
                        print(f"  'quaternion': {camera_state['quaternion']},")
                        print(f"  'target': {camera_state['target']},")
                        print(f"  'zoom': {camera_state['zoom']},")

                    image_bytes = await capture_image(page, model_name)

                    actual = png_size(image_bytes)
                    if actual != (width, height):
                        raise RuntimeError(
                            f"image is {actual[0]}x{actual[1]}, expected {width}x{height}"
                        )

                    output_path.write_bytes(image_bytes)

                    print(f"OK {model_name}.png")
                    success_count += 1

                except Exception as e:
                    print(f"FAILURE {model_name}: {describe_render_error(e, debug)}")
                    if debug:
                        print(indent(traceback.format_exc().rstrip("\n"), "    "))
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
    """
    Main entry point.

    Exits with status 1 if any example or model failed, in processing or in
    rendering, so that a CI job fails.
    """
    # Process examples (optionally save JSON in debug mode)
    print("=== Processing examples ===\n")
    models, process_fail_count = process_examples(examples, debug_models_dir)

    render_fail_count = 0
    if len(models) == 0:
        print("No models to render")
    else:
        # Render models to screenshots
        print("\n=== Rendering models to screenshots ===")
        render_fail_count = asyncio.run(
            render_models_to_screenshots(
                models,
                screenshots_dir,
                headless=headless,
                pause=pause,
                debug=debug_models_dir is not None,
            )
        )

    if process_fail_count > 0:
        print(f"\n{process_fail_count} failure(s) while processing examples")
    if process_fail_count > 0 or render_fail_count > 0:
        sys.exit(1)
