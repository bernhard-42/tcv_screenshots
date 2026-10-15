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

from tcv_screenshots.host import clear_saved_models, get_saved_models, save_model

__version__ = "0.4.0"

__all__ = [
    "save_model",
    "get_saved_models",
    "clear_saved_models",
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
