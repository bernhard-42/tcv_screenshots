"""save_model, the defaults functions and failure reporting (no browser)."""

import pytest
from build123d import Box, Pos

from tcv_screenshots import (
    get_defaults,
    get_failed_models,
    get_saved_models,
    reset_defaults,
    save_model,
    set_defaults,
)


def single_message():
    models = get_saved_models()
    assert len(models) == 1
    return models[0]


def test_save_model_returns_the_core_data_message():
    save_model(Box(1, 2, 3), name="box", cad_width=500, height=375, render_joints=True)
    name, message = single_message()
    assert name == "box"
    assert message["type"] == "data"
    config = message["config"]
    assert config["cadWidth"] == 500
    assert config["height"] == 375
    # show keywords arrive under the renderer's names
    assert config["renderJoints"] is True


def test_screenshot_defaults():
    save_model(Box(1, 2, 3), name="box")
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
    save_model(Box(1, 1, 1), Pos(3, 0, 0) * Box(1, 1, 1), name="pair", colors=["red", "blue"])
    _, message = single_message()
    parts = message["data"]["shapes"]["parts"]
    assert [part["color"] for part in parts] == ["#ff0000", "#0000ff"]


def test_a_successful_save_model_prints_nothing(capsys):
    # no tessellation progress characters ("+", "c") in the screenshot log
    save_model(Box(1, 2, 3), name="box")
    single_message()
    assert capsys.readouterr().out == ""


def test_window_keywords_are_refused_but_the_model_is_saved(capsys):
    save_model(Box(1, 2, 3), name="box", port=3939)
    name, _ = single_message()
    assert name == "box"
    captured = capsys.readouterr()
    assert "'port' is not something this viewer can be told" in captured.out + captured.err


def test_a_failing_save_model_is_printed_recorded_and_does_not_raise(capsys):
    save_model(Box(1, 2, 3), name="bad", cadWidth=500)  # a 0.3.0 config key
    save_model(Box(1, 2, 3), name="good")

    assert [name for name, _ in get_saved_models()] == ["good"]
    failed = get_failed_models()
    assert [name for name, _ in failed] == ["bad"]
    assert get_failed_models() == []  # reading clears the list

    out = capsys.readouterr().out
    assert out.count("FAILURE bad: TypeError") == 1
    # the traceback starts at the line that called save_model
    assert __file__ in out
    assert "cadWidth=500" in out


def test_save_model_without_a_name_raises():
    with pytest.raises(ValueError):
        save_model(Box(1, 2, 3), name="")


def test_set_defaults_applies_until_reset():
    set_defaults(cad_width=640)
    assert get_defaults()["cad_width"] == 640

    save_model(Box(1, 2, 3), name="from_defaults")
    save_model(Box(1, 2, 3), name="keyword_wins", cad_width=320)
    widths = {name: message["config"]["cadWidth"] for name, message in get_saved_models()}
    assert widths == {"from_defaults": 640, "keyword_wins": 320}

    reset_defaults()
    save_model(Box(1, 2, 3), name="after_reset")
    _, message = single_message()
    assert message["config"]["cadWidth"] == 1200
