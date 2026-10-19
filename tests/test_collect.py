"""collect_models: running example files, the example contract, errors (no browser)."""

from build123d import Box

from tcv_screenshots import collect_models, get_saved_models, save_model

OK_EXAMPLE = """
from build123d import Box
from tcv_screenshots import save_model, get_saved_models

def main():
    save_model(Box(1, 1, 1), name="{name}", cad_width=500, height=375)
    return get_saved_models()
"""


def names(models):
    return [name for name, _ in models]


def test_an_example_returns_its_models(write_example):
    path = write_example("ok", OK_EXAMPLE.format(name="model_a"))
    result = collect_models(path)
    assert names(result.models) == ["model_a"]
    assert result.failed == []


def test_files_without_tcv_screenshots_import_are_skipped(write_example, capsys):
    path = write_example("plain", "x = 1\n")
    result = collect_models(path)
    assert result.models == [] and result.failed == []
    assert "SKIP plain: no tcv_screenshots import" in capsys.readouterr().out


def test_examples_without_main_are_skipped(write_example, capsys):
    path = write_example("no_main", "import tcv_screenshots\n")
    result = collect_models(path)
    assert result.models == [] and result.failed == []
    assert "SKIP no_main: no main() function" in capsys.readouterr().out


def test_an_error_at_import_fails_with_a_traceback_from_the_example(write_example, capsys):
    path = write_example("import_error", "import tcv_screenshots\n\nraise RuntimeError('broken at import')\n")
    result = collect_models(path)
    assert result.failed == ["import_error"]
    out = capsys.readouterr().out
    assert "FAILURE import_error: RuntimeError: broken at import" in out
    assert f'File "{path}", line 3' in out
    # the runner's own frames are left out
    assert "importlib" not in out


def test_models_saved_before_an_error_in_main_are_kept(write_example):
    path = write_example(
        "main_error",
        "from build123d import Box\n"
        "from tcv_screenshots import save_model, get_saved_models\n"
        "def main():\n"
        "    save_model(Box(1, 1, 1), name='saved_first')\n"
        "    raise ValueError('later')\n",
    )
    result = collect_models(path)
    assert names(result.models) == ["saved_first"]
    assert result.failed == ["main_error"]


def test_main_must_return_a_list(write_example, capsys):
    path = write_example("returns_none", "import tcv_screenshots\ndef main():\n    return None\n")
    result = collect_models(path)
    assert result.failed == ["returns_none"]
    assert "main() must return get_saved_models()" in capsys.readouterr().out


def test_invalid_items_fail_and_valid_ones_are_kept(write_example):
    path = write_example(
        "bad_items",
        "from build123d import Box\n"
        "from tcv_screenshots import save_model, get_saved_models\n"
        "def main():\n"
        "    save_model(Box(1, 1, 1), name='valid')\n"
        "    return get_saved_models() + [('no_message',), 42]\n",
    )
    result = collect_models(path)
    assert names(result.models) == ["valid"]
    assert result.failed == ["bad_items", "bad_items"]


def test_a_failing_save_model_fails_only_its_model_and_is_printed_once(write_example, capsys):
    path = write_example(
        "save_error",
        "from build123d import Box\n"
        "from tcv_screenshots import save_model, get_saved_models\n"
        "def main():\n"
        "    save_model(Box(1, 1, 1), name='bad_one', cadWidth=500)\n"
        "    save_model(Box(1, 1, 1), name='good_one')\n"
        "    return get_saved_models()\n",
    )
    result = collect_models(path)
    assert names(result.models) == ["good_one"]
    assert result.failed == ["bad_one"]
    out = capsys.readouterr().out
    assert out.count("FAILURE bad_one") == 1
    # starts at the example's line, not in the runner
    assert f'File "{path}", line 4, in main' in out
    assert "collect_models" not in out


def test_models_saved_before_collect_models_are_kept(write_example):
    save_model(Box(1, 1, 1), name="mine")
    path = write_example("ok", OK_EXAMPLE.format(name="from_example"))
    result = collect_models(path)
    assert names(result.models) == ["from_example"]
    assert names(get_saved_models()) == ["mine"]


def test_a_file_named_twice_runs_once(write_example):
    path = write_example("ok", OK_EXAMPLE.format(name="once"))
    result = collect_models(path, path.parent)
    assert names(result.models) == ["once"]



def test_hidden_files_in_a_directory_are_not_run(write_example):
    # e.g. the ._*.py metadata files macOS adds to archives and network drives
    path = write_example("ok", OK_EXAMPLE.format(name="visible"))
    (path.parent / "._ok.py").write_bytes(b"\x00\x05\x16\x07\x00\x02\x00\x00\xa3")
    result = collect_models(path.parent)
    assert names(result.models) == ["visible"]
    assert result.failed == []


def test_a_file_that_is_not_utf8_fails_alone(write_example, capsys):
    path = write_example("ok", OK_EXAMPLE.format(name="kept"))
    # a Latin-1 pound sign in code: Python's import raises a SyntaxError
    (path.parent / "latin.py").write_bytes(b"import tcv_screenshots\n\nprice = '\xa3 5'\n")
    result = collect_models(path.parent)
    assert names(result.models) == ["kept"]
    assert result.failed == ["latin"]
    assert "FAILURE latin" in capsys.readouterr().out

def test_set_defaults_inside_an_example_does_not_leak(write_example):
    first = write_example(
        "a_sets_defaults",
        "from build123d import Box\n"
        "from tcv_screenshots import save_model, get_saved_models, set_defaults\n"
        "def main():\n"
        "    set_defaults(cad_width=777)\n"
        "    save_model(Box(1, 1, 1), name='first')\n"
        "    return get_saved_models()\n",
    )
    write_example("b_plain", OK_EXAMPLE.format(name="second").replace(", cad_width=500, height=375", ""))
    result = collect_models(first.parent)
    widths = {name: message["config"]["cadWidth"] for name, message in result.models}
    assert widths == {"first": 777, "second": 1200}
