"""Shared fixtures for the tcv_screenshots tests."""

from pathlib import Path

import pytest

from tcv_screenshots import clear_saved_models, get_failed_models, reset_defaults

REPO_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def pytest_addoption(parser):
    parser.addoption(
        "--no-gpu",
        action="store_true",
        help="render the browser tests with SwiftShader instead of the GPU",
    )


@pytest.fixture
def gpu(request) -> bool:
    """Whether browser tests render with the GPU (default) or SwiftShader."""
    return not request.config.getoption("--no-gpu")


@pytest.fixture(autouse=True)
def clean_host():
    """Every test starts and ends with an empty collector and no set_defaults."""
    clear_saved_models()
    reset_defaults()
    yield
    clear_saved_models()
    get_failed_models()
    reset_defaults()


@pytest.fixture
def write_example(tmp_path):
    """Write an example file into a fresh directory and return its path."""

    def write(name: str, code: str) -> Path:
        path = tmp_path / f"{name}.py"
        path.write_text(code, encoding="utf-8")
        return path

    return write
