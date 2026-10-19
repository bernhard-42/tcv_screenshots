"""screenshot, the defaults functions and failure reporting (no browser)."""

import subprocess
import sys

import pytest
from build123d import Box, Pos

from tcv_screenshots import (
    get_defaults,
    get_failed_models,
    get_saved_models,
    get_screenshots,
    reset_defaults,
    save_model,
    screenshot,
    set_defaults,
)


def single_message():
    models = get_screenshots()
    assert len(models) == 1
    return models[0]


def test_screenshot_returns_the_core_data_message():
    screenshot(Box(1, 2, 3), name="box", cad_width=500, height=375, render_joints=True)
    name, message = single_message()
    assert name == "box"
    assert message["type"] == "data"
    config = message["config"]
    assert config["cadWidth"] == 500
    assert config["height"] == 375
    # show keywords arrive under the renderer's names
    assert config["renderJoints"] is True


def test_screenshot_defaults():
    screenshot(Box(1, 2, 3), name="box")
    _, message = single_message()
    config = message["config"]
    assert config["cadWidth"] == 1200
    assert config["height"] == 800
    assert config["glass"] is True
    assert config["tools"] is False
    assert config["edgeColor"] == "#707070"
    # every screenshot is its own model: the camera must not be kept
    assert config["resetCamera"] == "reset"


def test_colors_reach_the_parts():
    screenshot(Box(1, 1, 1), Pos(3, 0, 0) * Box(1, 1, 1), name="pair", colors=["red", "blue"])
    _, message = single_message()
    parts = message["data"]["shapes"]["parts"]
    assert [part["color"] for part in parts] == ["#ff0000", "#0000ff"]


def test_a_successful_screenshot_prints_nothing(capsys):
    # no tessellation progress characters ("+", "c") in the screenshot log
    screenshot(Box(1, 2, 3), name="box")
    single_message()
    assert capsys.readouterr().out == ""


def test_window_keywords_are_refused_but_the_model_is_saved(capsys):
    screenshot(Box(1, 2, 3), name="box", port=3939)
    name, _ = single_message()
    assert name == "box"
    captured = capsys.readouterr()
    assert "'port' is not something this viewer can be told" in captured.out + captured.err


def test_a_failing_screenshot_is_printed_recorded_and_does_not_raise(capsys):
    screenshot(Box(1, 2, 3), name="bad", cadWidth=500)  # a 0.3.0 config key
    screenshot(Box(1, 2, 3), name="good")

    assert [name for name, _ in get_screenshots()] == ["good"]
    failed = get_failed_models()
    assert [name for name, _ in failed] == ["bad"]
    assert get_failed_models() == []  # reading clears the list

    out = capsys.readouterr().out
    assert out.count("FAILURE bad: TypeError") == 1
    # the traceback starts at the line that called screenshot
    assert __file__ in out
    assert "cadWidth=500" in out



def test_the_deprecated_names_still_work_and_warn():
    with pytest.warns(FutureWarning, match=r"save_model\(\) is deprecated, use screenshot\(\)") as record:
        save_model(Box(1, 2, 3), name="old", cad_width=500, height=375)
    # the warning points at the caller, not at tcv_screenshots
    assert record[0].filename == __file__
    with pytest.warns(FutureWarning, match=r"get_saved_models\(\) is deprecated, use get_screenshots\(\)"):
        models = get_saved_models()
    assert [name for name, _ in models] == ["old"]
    assert models[0][1]["config"]["cadWidth"] == 500


def test_a_failing_deprecated_save_model_shows_the_callers_line(capsys):
    with pytest.warns(FutureWarning):
        save_model(Box(1, 2, 3), name="bad_old", cadWidth=500)
    assert [name for name, _ in get_failed_models()] == ["bad_old"]
    out = capsys.readouterr().out
    assert out.count("FAILURE bad_old: TypeError") == 1
    assert __file__ in out
    assert "cadWidth=500" in out


def test_the_deprecation_warning_is_shown_for_examples(write_example, tmp_path):
    # examples run as imported modules, where Python hides DeprecationWarning
    # by default; a fresh process has the default warning filters
    path = write_example(
        "old_names",
        "from build123d import Box\n"
        "from tcv_screenshots import save_model, get_saved_models\n\n"
        "def main():\n"
        "    save_model(Box(1, 1, 1), name='old', cad_width=500, height=375)\n"
        "    return get_saved_models()\n",
    )
    code = f"from tcv_screenshots import collect_models; print(collect_models({str(path)!r}).models[0][0])"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path, timeout=300, check=False
    )
    assert result.returncode == 0
    assert result.stdout.strip().endswith("old")
    assert "FutureWarning: save_model() is deprecated, use screenshot()" in result.stderr
    assert "FutureWarning: get_saved_models() is deprecated, use get_screenshots()" in result.stderr
    assert str(path) in result.stderr

def test_screenshot_without_a_name_raises():
    with pytest.raises(ValueError):
        screenshot(Box(1, 2, 3), name="")


def test_set_defaults_applies_until_reset():
    set_defaults(cad_width=640)
    assert get_defaults()["cad_width"] == 640

    screenshot(Box(1, 2, 3), name="from_defaults")
    screenshot(Box(1, 2, 3), name="keyword_wins", cad_width=320)
    widths = {name: message["config"]["cadWidth"] for name, message in get_screenshots()}
    assert widths == {"from_defaults": 640, "keyword_wins": 320}

    reset_defaults()
    screenshot(Box(1, 2, 3), name="after_reset")
    _, message = single_message()
    assert message["config"]["cadWidth"] == 1200
