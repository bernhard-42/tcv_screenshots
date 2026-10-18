"""The command line: options and exit codes (no browser: these runs render nothing)."""

import subprocess
import sys


def run_cli(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "tcv_screenshots", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=300,
        check=False,  # the tests assert the exit code themselves
    )


def test_help_lists_the_options(tmp_path):
    result = run_cli("--help", cwd=tmp_path)
    assert result.returncode == 0
    for option in ("--file", "--directory", "--output-folder", "--no-gpu", "--pause", "--debug"):
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
