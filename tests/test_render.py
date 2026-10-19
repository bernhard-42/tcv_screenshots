"""Rendering in headless Chromium.

Run with the GPU by default, `pytest --no-gpu` renders with SwiftShader (CI).
Images are compared with each other within one run, never with stored files:
GPU and SwiftShader, and different machines, differ slightly in anti-aliasing.
"""

import asyncio
import base64
import copy

import pytest
from build123d import Box, Cylinder, fillet
from conftest import REPO_EXAMPLES
from playwright.async_api import async_playwright
from pngtools import max_difference

from tcv_screenshots import collect_models, get_screenshots, render_models, screenshot
from tcv_screenshots.render import png_size, serve_viewer, start_viewer

pytestmark = pytest.mark.browser


def message_of(*cad_objs, **kwargs):
    screenshot(*cad_objs, name="tmp", **kwargs)
    [(_, message)] = get_screenshots()
    return message


def drilled_box():
    box = fillet(Box(10, 10, 10).edges(), 1)
    return box - Cylinder(2, 10)


def test_the_repo_examples_render_at_their_requested_size(tmp_path, gpu):
    models = collect_models(REPO_EXAMPLES).models
    assert len(models) == 8
    result = render_models(models, tmp_path, gpu=gpu)
    assert result.failed == []
    assert sorted(p.name for p in result.written) == sorted(f"{name}.png" for name, _ in models)
    for name, message in models:
        expected = (message["config"]["cadWidth"], message["config"]["height"])
        assert png_size((tmp_path / f"{name}.png").read_bytes()) == expected, name


def test_no_setting_carries_over_to_the_next_screenshot(tmp_path, gpu):
    box = message_of(drilled_box(), cad_width=500, height=375)
    stateful = message_of(
        drilled_box(),
        cad_width=500,
        height=375,
        transparent=True,
        axes=True,
        tab="clip",
        clip_slider_2=0,
        zoom=2.5,
        reset_camera="top",
    )
    alone = render_models([("box", box)], tmp_path / "alone", gpu=gpu)
    after = render_models([("stateful", stateful), ("box", box)], tmp_path / "after", gpu=gpu)
    assert alone.failed == [] and after.failed == []
    assert (tmp_path / "alone" / "box.png").read_bytes() == (tmp_path / "after" / "box.png").read_bytes()


async def two_captures(message, gpu):
    with serve_viewer([("model", message)]) as server:
        async with async_playwright() as p:
            # whichever browser a run would use: the test is about the page
            _name, browser, page = await start_viewer(
                p, f"{server.base_url}/viewer.html", True, False, gpu
            )
            try:
                await page.evaluate("(url) => window.loadModel(url)", "/models/0")
                first = await page.evaluate("(n) => window.getImage(n)", "first")
                second = await page.evaluate("(n) => window.getImage(n)", "second")
            finally:
                await browser.close()
    return [base64.b64decode(d.split(",", 1)[1]) for d in (first, second)]


def test_studio_mode_is_captured_settled_and_at_the_requested_size(gpu):
    # Studio renders supersampled and its first frame lacks SMAA anti-aliasing:
    # the first image must already be the settled, downscaled one
    message = message_of(drilled_box(), cad_width=500, height=375, tab="studio")
    first, second = asyncio.run(two_captures(message, gpu))
    assert png_size(first) == (500, 375)
    assert max_difference(first, second) <= 2


def test_a_failure_in_the_browser_is_followed_by_a_restart(tmp_path, gpu, capsys):
    good = message_of(drilled_box(), cad_width=500, height=375)
    broken = copy.deepcopy(good)
    broken["data"]["instances"][0]["vertices"] = "not a buffer"  # fails in the page
    result = render_models([("broken", broken), ("after", good)], tmp_path, gpu=gpu)
    assert result.failed == ["broken"]
    assert [p.name for p in result.written] == ["after.png"]
    out = capsys.readouterr().out
    assert "FAILURE broken" in out
    assert "Restarting browser after failure" in out


def test_swiftshader_renders_without_a_gpu(tmp_path, capsys):
    message = message_of(drilled_box(), cad_width=500, height=375)
    result = render_models([("software", message)], tmp_path, gpu=False)
    assert result.failed == []
    assert png_size((tmp_path / "software.png").read_bytes()) == (500, 375)
    # SwiftShader is chosen, not fallen back to: no GPU report, no warning
    assert "GPU" not in capsys.readouterr().out


def test_playwrights_chromium_can_be_chosen_explicitly(tmp_path, gpu, capsys):
    message = message_of(drilled_box(), cad_width=500, height=375)
    result = render_models([("explicit", message)], tmp_path, gpu=gpu, browser="chromium")
    assert result.failed == []
    assert "Browser: chromium " in capsys.readouterr().out


def test_without_a_choice_a_run_names_the_browser_it_found(tmp_path, gpu, capsys):
    message = message_of(drilled_box(), cad_width=500, height=375)
    result = render_models([("auto", message)], tmp_path, gpu=gpu)
    assert result.failed == []
    browser_line = [line for line in capsys.readouterr().out.splitlines() if line.startswith("Browser: ")]
    assert len(browser_line) == 1
    assert browser_line[0].split()[1] in ("chrome", "msedge", "chromium")


def test_check_names_the_browser_a_run_uses(capsys):
    from tcv_screenshots.render import check_browsers

    assert check_browsers() is True
    out = capsys.readouterr().out
    assert "A run uses: " in out
