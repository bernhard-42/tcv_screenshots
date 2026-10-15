"""
tcv_screenshots as a host of ocp-viewer-core.

The show pipeline - tessellation, materials, colors, every keyword of `show` -
is ocp-viewer-core's `Viewer`. This module supplies what a host supplies: the
transport (`ScreenshotComms`) and the defaults of a screenshot. A "sent" model
is not sent anywhere, it is collected and rendered later by `render.py`.
"""

from typing import Any

from ocp_viewer_core.comms import Comms, Session
from ocp_viewer_core.config import Camera, Collapse, Config
from ocp_viewer_core.show import Viewer

# Defaults of a screenshot, in the keyword names of `show`.
# They are the host's workspace config: every key here can be overridden
# per call by the same keyword of `save_model`.
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

    def send_backend(self, data: Any, timeit: bool = False) -> None:
        # `show` hands every model to the measurement backend; a screenshot
        # has none
        return None


viewer = Viewer[dict](Config(Session(ScreenshotComms()), EXCLUDE_KEYS))

# Model collector, filled by save_model
_saved_models: list[tuple[str, dict]] = []


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
    """
    if not isinstance(name, str) or name == "":
        raise ValueError("save_model needs a non-empty name")

    # No tessellation progress characters in the screenshot log. "" and not
    # None: show() drops None keywords and then falls back to its default
    kwargs.setdefault("progress", "")

    message = viewer.show(*cad_objs, **kwargs)
    if message is None:
        raise ValueError(f"save_model('{name}'): nothing to render")

    _saved_models.append((name, message))


def get_saved_models() -> list[tuple[str, dict]]:
    """
    Get all saved models and clear the collector.

    Returns:
        List of (name, message) tuples, message being the core's data message
    """
    models = _saved_models.copy()
    _saved_models.clear()
    return models


def clear_saved_models() -> None:
    """Clear the saved models collector."""
    _saved_models.clear()
