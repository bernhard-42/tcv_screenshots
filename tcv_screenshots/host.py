"""
tcv_screenshots as a host of ocp-viewer-core.

The show pipeline - tessellation, materials, colors, every keyword of `show` -
is ocp-viewer-core's `Viewer`. This module supplies what a host supplies: the
transport (`ScreenshotComms`) and the defaults of a screenshot. A "sent" model
is not sent anywhere, it is collected and rendered later by `render.py`.
"""

import contextlib
import traceback
from pathlib import Path
from textwrap import indent
from typing import Any

from ocp_viewer_core.comms import Comms, Session
from ocp_viewer_core.config import Camera, Collapse, Config
from ocp_viewer_core.show import Viewer

# Defaults of a screenshot, in the keyword names of `show`.
# They are the host's workspace config: every key here can be overridden by
# `set_defaults` and per call by the same keyword of `save_model`.
DEFAULT_CONFIG = {
    # Display options
    "cad_width": 1200,
    "height": 800,
    "tree_width": 0,
    "theme": "light",
    "glass": True,
    "tools": False,
    # Render options
    "ambient_intensity": 1.0,
    "direct_intensity": 1.1,
    "metalness": 0.3,
    "roughness": 0.65,
    "default_edgecolor": "#707070",
    # Viewer options
    "ortho": True,
    "orbit_control": False,
    "up": "Z",
    "collapse": Collapse.ROOT,
    # Every screenshot is its own model: the page reuses one viewer, and
    # keeping the camera of the previous screenshot would frame the wrong object
    "reset_camera": Camera.RESET,
    # A screenshot has no splash to replace
    "_splash": False,
}

# Keywords of `show` that address a viewer process or window, which a
# screenshot does not have
EXCLUDE_KEYS = ("port", "viewer", "anchor", "pinning")


class ScreenshotComms(Comms[dict]):
    """
    The transport of a screenshot run: there is no viewer to talk to.

    `send_data` hands the finished data message back as the handle of `show`,
    so `save_model` receives exactly what another host would put on the wire.
    """

    def status(self) -> dict:
        # No running viewer, so nothing was changed in one
        return {}

    def workspace_config(self) -> dict:
        return dict(DEFAULT_CONFIG)

    def send_data(self, data: Any, timeit: bool = False) -> dict:
        return data

    def send_config(self, config: Any, timeit: bool = False) -> None:
        # `set_defaults` also pushes the settings to a running viewer; a
        # screenshot has none, the defaults apply from the next save_model on
        return None

    def send_backend(self, data: Any, timeit: bool = False) -> None:
        # `show` hands every model to the measurement backend; a screenshot
        # has none
        return None


viewer = Viewer[dict](Config(Session(ScreenshotComms()), EXCLUDE_KEYS))

# The defaults functions of ocp_vscode, from the same core: `set_defaults`
# takes the keywords of `show` and applies them to every following save_model,
# over DEFAULT_CONFIG and under the keywords of a single save_model call
set_defaults = viewer.config.set_defaults
get_defaults = viewer.config.get_defaults


def reset_defaults() -> None:
    """Forget everything `set_defaults` was told, back to DEFAULT_CONFIG."""
    # apply=False: there is no running viewer to send the reset to
    viewer.config.reset_defaults(apply=False)


@contextlib.contextmanager
def isolated_defaults():
    """
    Restore the defaults of `set_defaults` at the end of the block.

    Runs an example with the defaults its caller set, without letting a
    `set_defaults` call inside the example leak into the next one.
    """
    saved = dict(viewer.config.defaults)
    try:
        yield
    finally:
        viewer.config.defaults = saved

# Model collector, filled by save_model
_saved_models: list[tuple[str, dict]] = []

# Models save_model could not create, with the traceback of the error
_failed_models: list[tuple[str, traceback.TracebackException]] = []


@contextlib.contextmanager
def isolated_collector():
    """
    Run examples without touching what the caller has saved so far.

    Each example starts with an empty collector, so the models and failures a
    script recorded with save_model before running examples are set aside and
    put back at the end of the block. What examples left behind is dropped:
    their models were handed over or reported already.
    """
    saved = _saved_models.copy()
    failed = _failed_models.copy()
    _saved_models.clear()
    _failed_models.clear()
    try:
        yield
    finally:
        _saved_models[:] = saved
        _failed_models[:] = failed


def save_model(*cad_objs, name: str, **kwargs) -> None:
    """
    Save CAD objects as one screenshot.

    Call this at different points in your example code to capture
    incremental states. Then have main() return get_saved_models().

    Args:
        cad_objs: CAD objects to render, like the positional arguments of `show`
        name: Unique name for this screenshot (used as filename)
        kwargs: Any keyword of ocp_vscode's `show`, e.g. `colors`, `alphas`,
            `render_joints`, `reset_camera`, `cad_width`, `height`

    An error while creating the model does not raise: it is printed with its
    traceback and recorded (see get_failed_models), so the example goes on and
    its other models are still rendered. Only a missing name raises, as there
    is nothing to record.
    """
    if not isinstance(name, str) or name == "":
        raise ValueError("save_model needs a non-empty name")

    # No tessellation progress characters in the screenshot log. "" and not
    # None: show() drops None keywords and then falls back to its default
    kwargs.setdefault("progress", "")

    try:
        message = viewer.show(*cad_objs, **kwargs)
        if message is None:
            raise ValueError(f"save_model('{name}'): nothing to render")
    except Exception as error:
        trace = _traceback_with_caller(error)
        # Printed here and not by whoever collects the models: a script that
        # calls save_model directly would otherwise never hear of the error
        _print_failure(name, trace)
        _failed_models.append((name, trace))
        return

    _saved_models.append((name, message))


# Files of this package; their frames in front of the caller's code are the
# runner's (command line, collect_models), not the user's
_PACKAGE_DIR = Path(__file__).resolve().parent


def _is_runner_frame(filename: str) -> bool:
    """Whether a frame belongs to this package or to Python's import machinery."""
    if filename.startswith("<frozen "):
        return True
    return Path(filename).resolve().parent == _PACKAGE_DIR


def _print_failure(name: str, trace: traceback.TracebackException) -> None:
    """
    Print a FAILURE line with the error, followed by its traceback.

    The traceback starts at the code that called save_model: walking back from
    save_model's own frame, it stops at the first frame of the runner (command
    line, collect_models, the import machinery). The frames in front of it,
    including a script that called collect_models, would only bury the
    relevant part.
    """
    frames = list(trace.stack)
    this_file = Path(__file__).resolve()
    end = len(frames) - 1
    for i, frame in enumerate(frames):
        if frame.name == "save_model" and Path(frame.filename).resolve() == this_file:
            end = i
    first = end
    while first > 0 and not _is_runner_frame(frames[first - 1].filename):
        first -= 1
    trace.stack = traceback.StackSummary.from_list(frames[first:])

    summary = list(trace.format_exception_only())[-1].strip()
    print(f"FAILURE {name}: {summary}")
    print(indent("".join(trace.format()).rstrip("\n"), "    "))


def _traceback_with_caller(error: Exception) -> traceback.TracebackException:
    """
    Traceback of an error caught in save_model, including its callers.

    A caught exception's traceback starts at the frame that caught it, so it
    would not show the line of the example that called save_model. Prepend
    the frames above save_model (the last one of extract_stack is save_model
    itself, which the traceback already starts with).
    """
    callers = traceback.extract_stack()[:-2]
    trace = traceback.TracebackException.from_exception(error)
    trace.stack = traceback.StackSummary.from_list(callers + list(trace.stack))
    return trace


def get_saved_models() -> list[tuple[str, dict]]:
    """
    Get all saved models and clear the collector.

    Returns:
        List of (name, message) tuples, message being the core's data message
    """
    models = _saved_models.copy()
    _saved_models.clear()
    return models


def get_failed_models() -> list[tuple[str, traceback.TracebackException]]:
    """
    Get all models save_model could not create, and clear that list.

    save_model has printed each of them already; a script uses this to decide
    its exit status.

    Returns:
        List of (name, traceback) tuples
    """
    failed = _failed_models.copy()
    _failed_models.clear()
    return failed


def clear_saved_models() -> None:
    """Clear the saved models collector and the list of failed models."""
    _saved_models.clear()
    _failed_models.clear()
