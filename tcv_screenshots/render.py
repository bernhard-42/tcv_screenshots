#!/usr/bin/env python3
"""
Headless CAD model renderer.

1. collect_models: runs example files (each must have a main() returning
   get_saved_models()) and collects their models
2. render_models: renders models to PNG screenshots

`run` combines both for the command line.

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
from dataclasses import dataclass, field
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
    isolated_collector,
    isolated_defaults,
)

# Upper bound in seconds for capturing one image, so that a hung browser cannot
# block the run forever. Not a wait: a capture returns as soon as it is done.
# Generous, as SwiftShader needed up to 75 s for one large model.
IMAGE_TIMEOUT = 600.0


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


@dataclass
class CollectResult:
    """The models collected from example files, and what failed on the way."""

    # (name, message) tuples, message being ocp-viewer-core's data message
    models: list[tuple[str, dict]] = field(default_factory=list)
    # Names of the examples and models that failed
    failed: list[str] = field(default_factory=list)


@dataclass
class RenderResult:
    """The screenshots written, and the names of the models that failed."""

    written: list[Path] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def find_example_files(paths) -> list[Path]:
    """
    Expand files and directories to the example files to run.

    A directory stands for its Python files, sorted by name, without the ones
    starting with "_" (__init__.py, private helpers) or "." (hidden files such
    as macOS's ._*.py metadata). A file named twice, e.g. by itself and via its
    directory, runs once.
    """
    example_files = []
    for path in paths:
        path = Path(path).resolve()
        if path.is_dir():
            candidates = sorted(
                f for f in path.glob("*.py") if not f.name.startswith(("_", "."))
            )
        else:
            candidates = [path]
        for candidate in candidates:
            if candidate not in example_files:
                example_files.append(candidate)
    return example_files


def run_example(example_path: Path, models_dir: Path | None = None) -> CollectResult:
    """
    Run one example file and collect the models it saved.

    The example's main() must return get_saved_models(), i.e. a list of
    (name, message) tuples created by save_model().

    Errors are handled per model where possible: a failing save_model() call
    fails only its own model, and the models the example saved before raising
    an error are still returned.

    Args:
        example_path: The Python file to run
        models_dir: If provided, save each model's JSON here (debug mode)
    """
    result = CollectResult()
    model_name = example_path.stem

    if not example_path.is_file():
        print(f"FAILURE {model_name}: no such file {example_path}")
        result.failed.append(model_name)
        return result

    # Skip files that don't import tcv_screenshots. Only looked at here: a file
    # that is not valid UTF-8 fails when imported, as Python reads it
    content = example_path.read_text(encoding="utf-8", errors="replace")
    if "from tcv_screenshots import" not in content and "import tcv_screenshots" not in content:
        print(f"SKIP {model_name}: no tcv_screenshots import")
        return result

    # Clear models a previous example saved but never returned
    clear_saved_models()

    error = None
    try:
        module = import_example(example_path)

        # Check for main() function
        if not hasattr(module, "main"):
            print(f"SKIP {model_name}: no main() function, skipping")
            return result

        # Call main() to get saved models
        returned = module.main()
    except Exception as e:
        error = e
        # The models saved before the error are still rendered
        returned = get_saved_models()

    # save_model() prints and records its errors instead of raising them, so
    # the example went on after them; count them here
    for output_name, _trace in get_failed_models():
        result.failed.append(output_name)

    if error is not None:
        trace = traceback.TracebackException.from_exception(error)
        report_failure(model_name, trace, example_path)
        result.failed.append(model_name)

    # Expect list from get_saved_models(): [(name, message), ...]
    if not isinstance(returned, list):
        print(
            f"FAILURE {model_name}: main() must return get_saved_models(), "
            f"got {type(returned).__name__}"
        )
        result.failed.append(model_name)
        return result

    models_to_process = []
    for item in returned:
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
            result.failed.append(model_name)

    if len(models_to_process) == 0:
        # No SKIP after a failure: the example did not run as written
        if len(result.failed) == 0:
            print(f"SKIP {model_name}: no models to process")
        return result

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
                result.failed.append(output_name)
                continue
            print(f"OK {output_name}.json")

        result.models.append((output_name, message))

    return result


def collect_models(*paths: str | Path, models_dir: str | Path | None = None) -> CollectResult:
    """
    Run example files and collect the models they saved.

    Every example runs with the defaults given to `set_defaults` before this
    call; a `set_defaults` inside one example does not reach the next.

    Args:
        paths: Example files and directories of example files
        models_dir: If provided, save each model's JSON here (debug mode)

    Returns:
        The collected models, ready for render_models, and the names of the
        examples and models that failed
    """
    result = CollectResult()

    example_files = find_example_files(paths)
    if len(example_files) == 0:
        print("No example files found")
        return result

    print(f"Found {len(example_files)} example(s) to process")

    # Ensure models directory exists if saving
    if models_dir is not None:
        models_dir = Path(models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)

    # Models the caller saved before this call stay theirs
    with isolated_collector():
        for example_path in example_files:
            with isolated_defaults():
                example_result = run_example(example_path, models_dir)
            result.models.extend(example_result.models)
            result.failed.extend(example_result.failed)

    return result


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


# Software rendering (SwiftShader): works on a machine without a GPU such as a
# CI runner (gpu=False, --no-gpu), but is much slower for large models.
SWIFTSHADER_ARGS = [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--enable-unsafe-swiftshader",
]

# Chromium flags for the GPU per platform; the headless shell renders with
# SwiftShader without them. Measured on an Apple M1 Max and on a Ryzen 9 7900
# with integrated AMD graphics plus an NVIDIA RTX 5060 (Linux and Windows 11):
# - macOS: Metal reaches the GPU
# - Windows: d3d11 alone picks the integrated GPU; --force_high_performance_gpu
#   makes it the RTX (vulkan reaches it too, but d3d11 exists on every Windows)
# - Linux: vulkan reaches the RTX; "gl" fell back to SwiftShader and "gl-egl"
#   picked the integrated GPU
GPU_ARGS = {
    "darwin": ["--use-angle=metal"],
    "win32": ["--use-angle=d3d11", "--force_high_performance_gpu"],
    "linux": ["--use-angle=vulkan"],
}


def gpu_args(platform: str = sys.platform) -> list[str]:
    """
    Chromium flags for hardware rendering on a platform (the default).

    --enable-unsafe-swiftshader keeps WebGL working on a machine without a
    usable GPU: Chromium then falls back to SwiftShader instead of having no
    WebGL at all. With a GPU it does not change the choice (measured on macOS).
    """
    platform_args = GPU_ARGS.get(platform, GPU_ARGS["linux"])
    return [*platform_args, "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]


async def webgl_renderer(page) -> str:
    """The renderer WebGL reports in the page, e.g. a GPU or SwiftShader."""
    return await page.evaluate(
        """() => {
            const gl = document.createElement("canvas").getContext("webgl2");
            if (gl === null) {
                return "no WebGL 2";
            }
            const info = gl.getExtension("WEBGL_debug_renderer_info");
            return info === null
                ? gl.getParameter(gl.RENDERER)
                : gl.getParameter(info.UNMASKED_RENDERER_WEBGL);
        }"""
    )


# The browsers tcv_screenshots drives through Playwright: an installed Google
# Chrome or Microsoft Edge, or Playwright's own Chromium (`playwright install
# chromium`). All are Chromium, so the GPU flags above apply to each. Firefox and
# WebKit are left out: Playwright needs its own builds of them and cannot drive
# an installed Firefox or Safari.
BROWSERS = ("chrome", "msedge", "chromium")

INSTALL_HINT = "playwright install chromium"


def browser_order(platform: str = sys.platform) -> tuple[str, ...]:
    """
    The browsers tried, in this order, when none is given.

    An installed browser saves the download of Playwright's own Chromium
    (several hundred MB). Windows always has Edge; on macOS and Linux Chrome is
    the more likely one. Playwright's Chromium comes last; CI pins it with
    --browser chromium, as its version does not change with updates of the
    machine.
    """
    if platform == "win32":
        return ("msedge", "chrome", "chromium")
    return ("chrome", "msedge", "chromium")


async def launch_browser(playwright, name: str, headless: bool, gpu: bool):
    """Launch one of BROWSERS, with the GPU flags or SwiftShader."""
    if name not in BROWSERS:
        raise ValueError(f"unknown browser {name!r}, use one of: {', '.join(BROWSERS)}")
    args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        *(gpu_args() if gpu else SWIFTSHADER_ARGS),
    ]
    if name == "chromium":
        return await playwright.chromium.launch(headless=headless, args=args)
    return await playwright.chromium.launch(channel=name, headless=headless, args=args)


async def launch_viewer(
    playwright,
    viewer_url: str,
    headless: bool,
    debug: bool,
    gpu: bool = True,
    browser: str = "chromium",
):
    """
    Launch a browser and open the viewer page in it.

    Args:
        playwright: The running Playwright instance
        viewer_url: URL of viewer.html
        headless: Run browser in headless mode
        debug: Show browser console debug/info/warning messages
        gpu: Render with the GPU; False renders with SwiftShader
        browser: One of BROWSERS

    Returns:
        (browser, page) with the viewer initialized
    """
    instance = await launch_browser(playwright, browser, headless, gpu)

    # Create page (viewport will be set per-model based on config)
    page = await instance.new_page()

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
        await instance.close()
        raise

    return instance, page


def first_line(error: Exception) -> str:
    """The first line of an error message; Playwright appends long logs."""
    lines = str(error).strip().splitlines()
    return lines[0] if len(lines) > 0 else type(error).__name__


async def start_viewer(
    playwright,
    viewer_url: str,
    headless: bool,
    debug: bool,
    gpu: bool = True,
    browser: str | None = None,
):
    """
    Open the viewer in the given browser, or in the first of browser_order()
    that works. A browser that is not installed fails within milliseconds, so
    trying them in turn on every run costs nothing measurable.

    Returns:
        (name, browser, page)

    Raises:
        RuntimeError: No browser worked; names each one's error and how to
            install Playwright's Chromium
    """
    names = browser_order() if browser is None else (browser,)
    errors = []
    for name in names:
        try:
            instance, page = await launch_viewer(
                playwright, viewer_url, headless, debug, gpu, name
            )
            return name, instance, page
        except Exception as e:
            errors.append(f"{name}: {first_line(e)}")
    raise RuntimeError(
        f"no usable browser ({'; '.join(errors)}). "
        f"Install Playwright's Chromium with: {INSTALL_HINT}"
    )


async def check_browsers_async(gpu: bool = True, browser: str | None = None) -> bool:
    """
    Print which browsers can be launched, with version and renderer, and which
    one a run would use. Writes nothing.

    Returns:
        Whether a run would find a browser
    """
    names = browser_order() if browser is None else (browser,)
    mode = "GPU" if gpu else "SwiftShader (--no-gpu)"
    if browser is None:
        print(f"Browsers in the order a run tries them, rendering with {mode}:")
    else:
        print(f"Browser given with --browser, rendering with {mode}:")
    chosen = None
    async with async_playwright() as p:
        for name in names:
            try:
                instance = await launch_browser(p, name, True, gpu)
            except Exception as e:
                print(f"  {name:9s} not usable: {first_line(e)}")
                continue
            try:
                page = await instance.new_page()
                await page.goto("about:blank")
                renderer = await webgl_renderer(page)
                version = instance.version
            finally:
                await instance.close()
            print(f"  {name:9s} {version}, {renderer}")
            if chosen is None:
                chosen = name
    if chosen is None:
        print(f"No usable browser. Install Playwright's Chromium with: {INSTALL_HINT}")
        return False
    print(f"A run uses: {chosen}")
    return True


def check_browsers(gpu: bool = True, browser: str | None = None) -> bool:
    """The synchronous form of check_browsers_async."""
    return asyncio.run(check_browsers_async(gpu, browser))


async def capture_image(page, model_name: str) -> bytes:
    """
    Capture the loaded model as PNG.

    The model is drawn synchronously by loadModel, so the viewer is ready right
    after it; the page only needs extra frames for studio mode (see getImage
    in viewer.html). No image means the viewer was not ready, which is an error.
    """
    try:
        data_url = await asyncio.wait_for(
            page.evaluate("(name) => window.getImage(name)", model_name),
            timeout=IMAGE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(f"no image after {IMAGE_TIMEOUT:.0f}s") from None
    if not isinstance(data_url, str) or data_url == "":
        raise RuntimeError("the viewer was not ready to render the model")
    return base64.b64decode(data_url.split(",", 1)[1])


async def render_models_async(
    models: list[tuple[str, dict]],
    output_dir: str | Path,
    *,
    headless: bool = True,
    pause: bool = False,
    debug: bool = False,
    gpu: bool = True,
    browser: str | None = None,
) -> RenderResult:
    """
    Render models to PNG screenshots, `<output_dir>/<name>.png`.

    The awaitable form of render_models, for callers that already run an
    event loop (e.g. Jupyter).

    Args:
        models: (name, message) tuples, from collect_models(...).models or
            get_saved_models()
        output_dir: Directory for the PNG files, created if missing
        headless: Run browser in headless mode
        pause: Pause before each screenshot for debugging
        debug: Show browser console messages and full error messages
        gpu: Render with the GPU (default). False renders with the software
            renderer SwiftShader: works without a GPU (CI), but much slower
            for large models
        browser: "chrome", "msedge" or "chromium" (Playwright's own); None
            tries them in the order of browser_order()

    Returns:
        The PNG files written and the names of the models that failed
    """
    result = RenderResult()

    if len(models) == 0:
        print("No models to render")
        return result

    print(f"\nRendering {len(models)} model(s) to screenshots")

    # Ensure output directory exists
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with serve_viewer(models) as server:
        viewer_url = f"{server.base_url}/viewer.html"

        async with async_playwright() as p:
            try:
                browser, instance, page = await start_viewer(
                    p, viewer_url, headless, debug, gpu, browser
                )
            except Exception as e:
                print(
                    "Error: Viewer failed to initialize: "
                    f"{describe_render_error(e, debug)}"
                )
                result.failed.extend(name for name, _message in models)
                return result

            print(f"Browser: {browser} {instance.version}")

            if gpu:
                # Chromium falls back to software rendering when it cannot use
                # the GPU; say so instead of silently being slow
                renderer = await webgl_renderer(page)
                if "SwiftShader" in renderer:
                    print(
                        f"Warning: no usable GPU, the browser renders with {renderer}. "
                        "Use --no-gpu (gpu=False) to choose SwiftShader explicitly"
                    )
                else:
                    print(f"GPU rendering: {renderer}")

            restart = False

            # Process each model
            for index, (model_name, message) in enumerate(models):
                output_path = output_dir / f"{model_name}.png"

                # After a failure the page or browser may be dead (crash) or the
                # viewer in a broken state: continue with a fresh browser, otherwise
                # every remaining model fails as well
                if restart:
                    print("Restarting browser after failure")
                    with contextlib.suppress(Exception):
                        await instance.close()
                    try:
                        instance, page = await launch_viewer(
                            p, viewer_url, headless, debug, gpu, browser
                        )
                    except Exception as e:
                        print(
                            "Error: Viewer failed to restart: "
                            f"{describe_render_error(e, debug)}"
                        )
                        result.failed.extend(name for name, _message in models[index:])
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
                        result.failed.append(model_name)
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
                    result.written.append(output_path)

                except Exception as e:
                    print(f"FAILURE {model_name}: {describe_render_error(e, debug)}")
                    if debug:
                        print(indent(traceback.format_exc().rstrip("\n"), "    "))
                    result.failed.append(model_name)
                    restart = True

            # The browser may already be dead after a failure of the last model
            with contextlib.suppress(Exception):
                await instance.close()

    print(f"\nDone: {len(result.written)} succeeded, {len(result.failed)} failed")
    return result


def render_models(
    models: list[tuple[str, dict]],
    output_dir: str | Path,
    *,
    headless: bool = True,
    pause: bool = False,
    debug: bool = False,
    gpu: bool = True,
    browser: str | None = None,
) -> RenderResult:
    """
    Render models to PNG screenshots, `<output_dir>/<name>.png`.

    Args:
        models: (name, message) tuples, from collect_models(...).models or
            get_saved_models()
        output_dir: Directory for the PNG files, created if missing
        headless: Run browser in headless mode
        pause: Pause before each screenshot for debugging
        debug: Show browser console messages and full error messages
        gpu: Render with the GPU (default). False renders with the software
            renderer SwiftShader: works without a GPU (CI), but much slower
            for large models
        browser: "chrome", "msedge" or "chromium" (Playwright's own); None
            tries them in the order of browser_order()

    Returns:
        The PNG files written and the names of the models that failed
    """
    return asyncio.run(
        render_models_async(
            models,
            output_dir,
            headless=headless,
            pause=pause,
            debug=debug,
            gpu=gpu,
            browser=browser,
        )
    )


def run(
    examples: str | Path | list[str | Path],
    screenshots_dir: str | Path,
    headless: bool = True,
    pause: bool = False,
    debug_models_dir: str | Path | None = None,
    gpu: bool = True,
    browser: str | None = None,
):
    """
    Command line entry point: collect_models, then render_models.

    Exits with status 1 if any example or model failed, in processing or in
    rendering, so that a CI job fails.
    """
    if not isinstance(examples, list):
        examples = [examples]

    # Process examples (optionally save JSON in debug mode)
    print("=== Processing examples ===\n")
    collected = collect_models(*examples, models_dir=debug_models_dir)

    rendered = RenderResult()
    if len(collected.models) == 0:
        print("No models to render")
    else:
        # Render models to screenshots
        print("\n=== Rendering models to screenshots ===")
        rendered = render_models(
            collected.models,
            screenshots_dir,
            headless=headless,
            pause=pause,
            debug=debug_models_dir is not None,
            gpu=gpu,
            browser=browser,
        )

    if len(collected.failed) > 0:
        print(f"\n{len(collected.failed)} failure(s) while processing examples")
    if len(collected.failed) > 0 or len(rendered.failed) > 0:
        sys.exit(1)
