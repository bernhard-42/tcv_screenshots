"""Headless screenshot generator for three-cad-viewer."""

__version__ = "0.1.0"

# Model collector for incremental examples
_saved_models = []


def save_model(model, name: str, config: dict = None):
    """
    Save a model for later export.

    Call this at different points in your example code to capture
    incremental states. Then have main() return get_saved_models().

    Args:
        model: CAD object to render
        name: Unique name for this snapshot (used in filename)
        config: Optional config overrides
    """
    _saved_models.append((model, name, config or {}))


def get_saved_models() -> list:
    """
    Get all saved models and clear the collector.

    Returns:
        List of (model, name, config) tuples
    """
    global _saved_models
    models = _saved_models.copy()
    _saved_models = []
    return models


def clear_saved_models():
    """Clear the saved models collector."""
    global _saved_models
    _saved_models = []
