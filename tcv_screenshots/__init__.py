"""Headless screenshot generator for three-cad-viewer."""

# The option enums of `show`, the same ones ocp_vscode exports
from ocp_viewer_core.config import (
    AnalysisTool,
    Camera,
    Collapse,
    Render,
    StudioBackground,
    StudioEnvironment,
    StudioTextureMapping,
    StudioToneMapping,
    UiTab,
)

from tcv_screenshots.host import (
    clear_saved_models,
    get_defaults,
    get_failed_models,
    get_saved_models,
    reset_defaults,
    save_model,
    set_defaults,
)
from tcv_screenshots.render import (
    CollectResult,
    RenderResult,
    collect_models,
    render_models,
    render_models_async,
)

__version__ = "0.4.0"

__all__ = [
    "save_model",
    "get_saved_models",
    "get_failed_models",
    "clear_saved_models",
    "set_defaults",
    "reset_defaults",
    "get_defaults",
    "collect_models",
    "render_models",
    "render_models_async",
    "CollectResult",
    "RenderResult",
    "AnalysisTool",
    "Camera",
    "Collapse",
    "Render",
    "StudioBackground",
    "StudioEnvironment",
    "StudioTextureMapping",
    "StudioToneMapping",
    "UiTab",
]
