"""The command line: options and exit codes (no browser: these runs render nothing)."""

import os
import subprocess
import sys


def run_cli(*args, cwd, env=None):
    return subprocess.run(
        [sys.executable, "-m", "tcv_screenshots", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=300,
        check=False,  # the tests assert the exit code themselves
        env=env,
    )


def test_help_lists_the_options(tmp_path):
    result = run_cli("--help", cwd=tmp_path)
    assert result.returncode == 0
    for option in ("--file", "--directory", "--output-folder", "--no-gpu", "--browser", "--check", "--pause", "--debug"):
        assert option in result.stdout


def test_a_failing_example_exits_with_1(write_example, tmp_path):
    # 0.3.0 exited with 0 here, so a CI job stayed green with broken examples
    path = write_example("broken", "import tcv_screenshots\n\nraise RuntimeError('broken')\n")
    result = run_cli("-f", str(path), "-o", str(tmp_path / "out"), cwd=tmp_path)
    assert result.returncode == 1
    assert "FAILURE broken: RuntimeError: broken" in result.stdout


def test_skipped_files_alone_exit_with_0(write_example, tmp_path):
    path = write_example("plain", "x = 1\n")
    result = run_cli("-f", str(path), "-o", str(tmp_path / "out"), cwd=tmp_path)
    assert result.returncode == 0
    assert "SKIP plain" in result.stdout


def test_directory_requires_an_output_folder(tmp_path):
    result = run_cli("-d", str(tmp_path), cwd=tmp_path)
    assert result.returncode == 2
    assert "requires -o/--output-folder" in result.stderr


def test_only_the_supported_browsers_can_be_chosen(tmp_path):
    result = run_cli("--browser", "firefox", "--check", cwd=tmp_path)
    assert result.returncode == 2
    assert "invalid choice: 'firefox'" in result.stderr


def test_check_without_a_browser_tells_how_to_install_one(tmp_path):
    # An empty browser directory: Playwright's own Chromium cannot be found
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(tmp_path / "no-browsers")}
    result = run_cli("--check", "--browser", "chromium", cwd=tmp_path, env=env)
    assert result.returncode == 1
    assert "chromium  not usable" in result.stdout
    assert "Install Playwright's Chromium with: playwright install chromium" in result.stdout


def test_an_example_without_a_browser_fails_with_the_install_hint(write_example, tmp_path):
    path = write_example(
        "ok",
        "from build123d import Box\n"
        "from tcv_screenshots import save_model, get_saved_models\n"
        "def main():\n"
        "    save_model(Box(1, 1, 1), name='box', cad_width=500, height=375)\n"
        "    return get_saved_models()\n",
    )
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(tmp_path / "no-browsers")}
    result = run_cli("-f", str(path), "-o", str(tmp_path / "out"), "--browser", "chromium", cwd=tmp_path, env=env)
    assert result.returncode == 1
    assert "no usable browser" in result.stdout
    assert "playwright install chromium" in result.stdout
