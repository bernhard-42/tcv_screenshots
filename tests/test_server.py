"""The local HTTP server that hands viewer files and models to the page (no browser)."""

import http.client
import json

from pngtools import decode, encode

from tcv_screenshots.render import (
    BROWSERS,
    SWIFTSHADER_ARGS,
    browser_order,
    gpu_args,
    png_size,
    resolve_viewer_file,
    serve_viewer,
)


def test_viewer_files_resolve():
    assert resolve_viewer_file("/viewer.html").is_file()
    assert resolve_viewer_file("/static/three-cad-viewer.esm.js").is_file()
    assert resolve_viewer_file("/static/ocp-viewer-core/index.js").is_file()


def test_nothing_outside_static_is_served():
    assert resolve_viewer_file("/render.py") is None
    assert resolve_viewer_file("/static/../render.py") is None
    assert resolve_viewer_file("/static/ocp-viewer-core/../../host.py") is None
    assert resolve_viewer_file("/static/missing.js") is None


def get(server, path):
    host, port = server.server_address
    connection = http.client.HTTPConnection(host, port, timeout=10)
    # http.client sends the path as given, without normalizing "..", so the
    # server's own check is what is tested
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, response.getheader("Content-Type"), body


def test_the_server_serves_page_modules_and_models():
    message = {"type": "data", "config": {"cadWidth": 500}, "data": {"shapes": {}}}
    with serve_viewer([("model", message)]) as server:
        status, content_type, _ = get(server, "/viewer.html")
        assert (status, content_type) == (200, "text/html; charset=utf-8")

        # ES modules only run when served with a JavaScript content type
        status, content_type, _ = get(server, "/static/ocp-viewer-core/index.js")
        assert (status, content_type) == (200, "text/javascript; charset=utf-8")

        status, content_type, body = get(server, "/models/0")
        assert (status, content_type) == (200, "application/json")
        assert json.loads(body) == message

        assert get(server, "/models/1")[0] == 404
        assert get(server, "/models/x")[0] == 404
        assert get(server, "/static/../render.py")[0] == 404
        assert get(server, "/render.py")[0] == 404


def test_png_size_and_the_test_decoder():
    rgba = bytes([255, 0, 0, 255] * 3 + [0, 0, 255, 128] * 3)
    data = encode(3, 2, rgba)
    assert png_size(data) == (3, 2)
    assert decode(data) == (3, 2, 4, rgba)


def test_gpu_flags_per_platform():
    assert gpu_args("darwin")[0] == "--use-angle=metal"
    assert gpu_args("win32")[:2] == ["--use-angle=d3d11", "--force_high_performance_gpu"]
    assert gpu_args("linux")[0] == "--use-angle=vulkan"
    # any other platform gets the Linux flags
    assert gpu_args("freebsd") == gpu_args("linux")
    # without a usable GPU, WebGL must fall back to SwiftShader instead of failing
    for platform in ("darwin", "win32", "linux"):
        assert "--enable-unsafe-swiftshader" in gpu_args(platform)
    assert "--use-angle=swiftshader" in SWIFTSHADER_ARGS


def test_browser_order_per_platform():
    # Windows always has Edge; elsewhere Chrome is the more likely installed one;
    # Playwright's own Chromium is the last resort everywhere
    assert browser_order("win32") == ("msedge", "chrome", "chromium")
    assert browser_order("darwin") == ("chrome", "msedge", "chromium")
    assert browser_order("linux") == ("chrome", "msedge", "chromium")
    for platform in ("win32", "darwin", "linux"):
        assert sorted(browser_order(platform)) == sorted(BROWSERS)
