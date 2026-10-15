/**
 * The viewer page, held once for every host that shows one.
 *
 * A host's HTML supplies only what is genuinely its own: where it loaded these
 * modules from, where its settings come from, and how to send a message. Even
 * measuring the surface is here - a host that owns a whole browsing context
 * gets the window measured for it, and one that shows the viewer in a pane
 * passes its own container and its own size.
 *
 * This is the one module in the package that touches the DOM, and it does so
 * because it *is* the page. Everything else here takes a viewer and plain data
 * and could run headless; that distinction is worth keeping, so new DOM work
 * belongs in this file or in a host, not spread through the others.
 */

/*
   Copyright 2026 Bernhard Walter

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/

import { animate } from "./animation.js";
import { applyConfig } from "./apply.js";
import { logo } from "./logo.js";
import { createNotifier } from "./notify.js";
import { buildDisplayOptions, preset } from "./options.js";
import { createRenderer } from "./render.js";
import { currentStates, restoreStates } from "./states.js";
import { VERSION } from "./version.js";

const MIN_WIDTH = 450;

// The version handshake: the Python half sends `_core_version` in every
// model's config, and major.minor is the contract - the patch level is each
// half's own. Warned once per page, loudly, because a contract mismatch shows
// up as the vaguest of symptoms otherwise: an option that does nothing, a key
// nobody answers.
let versionWarned = false;

function consumeCoreVersion(config, send) {
    if (config == null || config._core_version === undefined) {
        return;
    }
    const python = String(config._core_version);
    delete config._core_version;
    if (versionWarned) {
        return;
    }
    const [pyMajor, pyMinor] = python.split(".");
    const [jsMajor, jsMinor] = VERSION.split(".");
    if (pyMajor !== jsMajor || pyMinor !== jsMinor) {
        versionWarned = true;
        const msg =
            `ocp-viewer-core version mismatch: Python ${python}, JavaScript ${VERSION} - ` +
            "major.minor must match; update the older side";
        console.error(msg);
        if (send != null) {
            send("log", msg);
        }
    }
}

/**
 * Build the page.
 *
 * @param Viewer, Display, Timer  three-cad-viewer's three, passed in because
 *                                only the host knows where it loaded them from
 * @param send        (command, message) => void - the host's channel to Python
 * @param overrides   {display, viewer} - the settings this host differs on
 * @param theme       the host's resolved theme, for the observer below
 * @param container   the element to draw into, or its id. Default "cad_viewer"
 * @param getSize     () => {width, height} of the surface. Default the window
 * @param listen      attach the window's `message` and `resize` listeners.
 *                    Default true; a host that has neither passes false and
 *                    drives `handleMessage` and `resize` itself
 * @returns `{ showSplash, setTheme, handleMessage, resize }` - the two page
 *          hosts deliver messages as a `message` event, the extension posting
 *          into the webview and the standalone's socket shim posting what came
 *          off the wire, and both let this file listen for them. A host whose
 *          models arrive some other way calls `handleMessage` with the same
 *          objects, so every host runs the one dispatch and no host can end up
 *          with a message branch, and so a feature, that another lacks.
 */
export function createPage({
    Viewer,
    Display,
    Timer,
    send,
    overrides,
    theme,
    container,
    getSize,
    listen
}) {
    var viewer = null;
    var display = null;
    var _shapes = null;
    var _meshData = null;
    var _config = null;
    var _camera_distance = null;
    var viewerOptions = {};
    var last_bb_radius = null;

    // The viewer's own state, as the renderer reports it: one object the
    // notifier keeps, under the names the renderer notifies with - camelCase
    // for the camera, which is sent straight to checkChanges, and snake_case
    // for everything that goes through its notification map. render() writes
    // into it too, after
    // reading the camera back off the viewer.
    //
    // It is also what goes on the wire. The extension answers a status
    // request with the last message the webview sent, replacing rather
    // than merging, so a delta would lose every earlier value - and
    // combined_config merges the viewer's state into the next show. The
    // notifier's delta plus this snapshot is what preserves both.
    var notifier = null;
    var renderer = null;
    var status = {};

    function debugLog(tag, obj) {
        console.log(tag, obj);
        var msg = tag + (obj ? " " + JSON.stringify(obj) : "");
        send("log", msg);
    }

    function nc(change) {
        return notifier == null ? null : notifier.notify(change);
    }

    function makeRenderer() {
        renderer = createRenderer({
            viewer: viewer,
            status: status,
            overrides: { viewer: overrides.viewer, theme: overrides.display.theme },
            // A tree width is a resize, and only this host knows the
            // other two dimensions.
            resize: () => {
                const displayOptions = getDisplayOptions(_config.theme);
                viewer.resizeCadView(
                    displayOptions.cadWidth,
                    displayOptions.treeWidth,
                    displayOptions.height,
                    displayOptions.glass
                );
            },
            sendStatus: (snapshot) => send("status", snapshot),
            debug: _config != null && _config.debug ? debugLog : null
        });
    }

    function makeNotifier() {
        notifier = createNotifier({
            viewer: viewer,
            // The delta is what changed; the snapshot is what the
            // extension will answer the next status request with.
            // Event keys - a selection, a pick, the active tool - ride
            // on the delta only, so a selection made minutes ago is not
            // replayed into an unrelated update.
            send: (delta) => send("status", { ...status, ...delta }),
            debug: _config != null && _config.debug ? debugLog : null
        });
        status = notifier.status;
    }

    function normalizeWidth(width, glass, tools) {
        const treeWidth =
            glass || !tools
                ? 0
                : preset(_config, "treeWidth", overrides.display.treeWidth);
        return Math.max(MIN_WIDTH - treeWidth, width - treeWidth - 20);
    }

    /**
     * The chrome above the canvas, measured rather than assumed.
     *
     * This was the constant 65, which is an approximation of the canvas's own
     * top offset and wrong in both directions: it over-reserves in a pane,
     * showing as a bottom margin visibly larger than the left and top ones,
     * and measuring the toolbar alone instead under-reserves - the toolbar's
     * offset and the gap below it are part of the same distance, and without
     * them the canvas overflows and clips the status line, which is pinned to
     * `bottom: 4px` inside it.
     *
     * Taken from the container so that it means the same thing to a host that
     * owns the window and to one that draws into a pane.
     */
    const ASSUMED_CHROME = 65;

    function getContainer() {
        if (container == null) {
            return document.getElementById("cad_viewer");
        }
        return typeof container === "string"
            ? document.getElementById(container)
            : container;
    }

    function reservedHeight() {
        const element = getContainer();
        if (element == null) {
            return ASSUMED_CHROME;
        }
        const canvas = element.querySelector(
            ".tcv_cad_view_glass, .tcv_cad_view"
        );
        if (canvas != null) {
            const offset =
                canvas.getBoundingClientRect().top -
                element.getBoundingClientRect().top;
            if (offset > 0) {
                return Math.round(offset);
            }
        }
        // Before the canvas exists, approximate from the toolbar if it is there.
        const toolbar = element.querySelector(".tcv_cad_toolbar");
        if (toolbar != null && toolbar.offsetHeight > 0) {
            return toolbar.offsetHeight + 10;
        }
        return ASSUMED_CHROME;
    }

    function normalizeHeight(height) {
        return height - reservedHeight();
    }

    function measureSize() {
        if (getSize != null) {
            return getSize();
        }
        // The window, less the container's own offset in it - a page's body
        // margin - above it and, for the same margin, below it. The chrome is
        // measured from the container's top, so an offset of the container
        // itself was counted nowhere: the standalone page keeps the browser's
        // 8px body margin, and its canvas ended 8px under the window edge,
        // cutting the status line pinned to `bottom: 4px` inside it. A VS Code
        // webview's body has no margin, so its offset is 0.
        const element = getContainer();
        const top =
            element == null
                ? 0
                : Math.max(0, Math.round(element.getBoundingClientRect().top));
        return {
            width: window.innerWidth,
            height: window.innerHeight - 2 * top
        };
    }

    function getGeometry() {
        const size = measureSize();
        const glass = preset(_config, "glass", overrides.display.glass);
        const tools = preset(_config, "tools", overrides.display.tools);
        return {
            cadWidth: normalizeWidth(size.width, glass, tools),
            height: normalizeHeight(size.height),
            treeWidth: preset(
                _config,
                "treeWidth",
                overrides.display.treeWidth
            )
        };
    }

    function getDisplayOptions(theme) {
        const options = buildDisplayOptions(
            _config,
            overrides.display,
            getGeometry()
        );
        // An explicit theme argument still wins: showViewer is called
        // with config.theme, and the observer below with the host's.
        if (theme) {
            options.theme = theme;
        }
        return options;
    }

    function showViewer(meshData, config) {
        debugLog("showViewer called");
        _meshData = meshData;
        _shapes = meshData.shapes || meshData;
        _config = config;
        const displayOptions = getDisplayOptions(config.theme);
        if (display == null) {
            const element = getContainer();
            element.innerHTML = "";
            display = new Display(element, displayOptions);
        }
        if (_config == null) {
            debugLog("OCP CAD Viewer: config is null");
            _config = {};
        }
        if (_config.debug) {
            debugLog("_config", _config);
            debugLog("displayOptions", displayOptions);
        }
        // Reuse the viewer across shows: clear() tears down the scene and
        // resets activeTab to "tree" (which triggers leaveStudioMode if the
        // previous show was in Studio mode), but keeps the WebGL context,
        // ViewerState (preferences), and StudioManager (incl. PMREM env
        // cache) alive — saving a context teardown and HDR re-fetch per show.
        if (viewer != null) {
            viewer.clear();
        } else {
            viewer = new Viewer(display, displayOptions, nc, null);
            // After the viewer, because both read it. `nc` is the
            // trampoline that bridges the notifier to the constructor.
            makeNotifier();
            makeRenderer();
        }

        if (_shapes) renderer.render(_meshData, _config);

        // Three display options are re-applied on every show, for one reason:
        // the Display is built once, so everything it was constructed with is
        // dropped by every show after the first. The theme is the one that was
        // missing - `show(theme=...)` and a changed workspace setting both
        // computed it into displayOptions and then threw it away, because by
        // then `display` was no longer null.
        viewer.setTheme(displayOptions.theme);
        viewer.glassMode(displayOptions.glass);
        viewer.showTools(displayOptions.tools);

        debugLog("showViewer finished");

        return viewer;

        // viewer.trimUI(["axes", "axes0", "grid", "ortho", "more", "help"])
    }

    /**
     * The surface changed size.
     *
     * A window resize for the two page hosts, and a splitter drag for a host
     * that draws into a pane - the same work either way, which is why it is a
     * function rather than a listener body.
     */
    function resize() {
        // `ready` and not only null: clear() returns the viewer to its
        // never-rendered state, where resizeCadView throws - a splitter drag
        // over an emptied pane must not be an error. The next show measures
        // the surface for itself, so a skipped resize here loses nothing.
        if (viewer != null && viewer.ready === true) {
            const displayOptions = getDisplayOptions(_config.theme);
            viewer.resizeCadView(
                displayOptions.cadWidth,
                displayOptions.treeWidth,
                displayOptions.height,
                displayOptions.glass
            );
            viewer.gridHelper.clearCache();
            viewer.gridHelper.update(viewer.getCameraZoom(), true);
            viewer.update(true, true);
        }
    }

    function handleMessage(message) {
        var data = message;

        // Before anything reads the config: take the Python half's version
        // out of it and check the contract, so `_core_version` never reaches
        // applyConfig as an unknown key.
        consumeCoreVersion(data?.config, send);

        if (data.type === "logo") {
            // The splash lives in the core, so a host asks for it by name and
            // sends only what it alone knows: its theme, its tree width and
            // its modifier keys.
            const splash = logo();
            data = {
                ...splash,
                config: { ...splash.config, ...(data.config || {}) }
            };
        }

        if (data.type === "data" && data?.data?.shapes?.parts?.length > 0) {
            const timer = new Timer("webView", data.config.timeit);

            const oldStates = currentStates(viewer);

            let meshData = data.data;
            let config = data.config;

            if (config._splash) {
                const displayOptions = getDisplayOptions(config.theme);
                config.zoom = Math.min(
                    1.0,
                    displayOptions.cadWidth / displayOptions.height
                );
                // debugLog("logo zoom =", config.zoom);
            }

            showViewer(meshData, config);

            // Explicit states win, otherwise the user's prior visibility
            // choices are restored for whatever survived into the new
            // model - in one batched setStates either way, because a
            // per-key loop is a repaint per key and freezes the host.
            restoreStates(viewer, meshData.shapes, oldStates, config.states);
            timer.split("states updated");

            timer.stop();
        } else if (data.type === "screenshot") {
            var promise = viewer.getImage(data.filename);
            promise.then((result) => {
                send("screenshot", {
                    filename: result.task,
                    data: result.dataUrl
                });
            });
        } else if (data.type === "set_relative_time") {
            if (viewer) {
                viewer.setRelativeTime(data.value);
            }
        } else if (data.type === "backend_response") {
            viewer.handleBackendResponse(data);
        } else if (data.type === "clear") {
            // Python's `show_clear()`, and `show_all()` when it finds nothing
            // drawable. clear() is a no-op on a viewer that shows nothing, and
            // the stored model goes with the scene - a cleared model must not
            // be resurrectable by anything that re-renders `_meshData`.
            if (viewer != null) {
                viewer.clear();
                _meshData = null;
                _shapes = null;
            }
        // No `init` branch, which was one of two of the same kind and the
        // worse: it called `init(data.paths, data.settings)`, a name this
        // module never defines. Only the extension sends an `init` message,
        // and `viewer.html`'s own listener answers it - by *calling*
        // `createPage`, so this listener does not exist yet when the first one
        // arrives. A second one would have reached here and thrown a
        // ReferenceError. Deleting it also removes the one branch that could
        // not work from a host driving `handleMessage` directly.
        //
        // No `show` branch: nothing in any host sends it, and it was a
        // landmine rather than merely dead - `showViewer()` with
        // no arguments evaluates `getDisplayOptions(config.theme)` against an
        // undefined config and throws before reaching its own null guard, and
        // it assigns `_meshData = undefined` on the way, destroying the stored
        // model so that even a corrected call could not re-show. If a host
        // ever needs to re-render what it already has, that is `showViewer(
        // _meshData, _config)` guarded on `_meshData` being present.
        } else if (data.type === "ui") {
            // Nothing on screen is a normal state now that show_clear exists,
            // and most setters read the rendered scene and throw without one.
            // Said rather than silent: in this ecosystem a dropped config is
            // the hardest thing to debug.
            if (viewer == null || viewer.ready !== true) {
                debugLog("ui: no model on screen, config not applied");
                return;
            }
            if (_config["_splash"]) {
                return;
            }
            if (data.config.debug) {
                debugLog("data.config", data.config);
            }
            // One dispatch for every key, shared with every other host, so
            // that a setter cannot exist in one client and not another.
            const applied = applyConfig(viewer, data.config, {
                // Only the host knows the other two dimensions, so a
                // viewport key is a resize rather than a setter.
                resize: (key, value) => {
                    const displayOptions = getDisplayOptions(data.config.theme);
                    const glass =
                        data.config.glass !== undefined
                            ? data.config.glass
                            : displayOptions.glass;
                    viewer.resizeCadView(
                        key === "cadWidth" ? value : displayOptions.cadWidth,
                        key === "treeWidth" ? value : displayOptions.treeWidth,
                        key === "height" ? value : displayOptions.height,
                        glass
                    );
                },
                onUnknown: (key) => {
                    debugLog(`ui: no setter for '${key}'`);
                }
            });
            // The viewer changed; _config follows, for exactly the applied
            // keys. Without this the two disagree, and resize() - a window
            // resize, a splitter drag, Studio's pane observer on every Run -
            // re-derives geometry from the value the ui call just replaced:
            // set_viewer_config(glass=False) held until the next resize
            // snapped glass back on. Same family: tools, treeWidth, theme.
            for (const key of applied) {
                _config[key] = data.config[key];
            }
            // Glass and tools decide whether the tree sits over the canvas or
            // beside it, and three-cad-viewer re-lays out with the `cadWidth`
            // it was given: leaving glass mode grows the viewer by `treeWidth`
            // where the canvas should have shrunk by it, so it overflows the
            // pane until something else happens to resize it. The host owns
            // the other two dimensions, so it re-derives all three here, the
            // way a window resize does - `_config` carries the new value by
            // now, which is what `normalizeWidth` reads.
            if (applied.includes("glass") || applied.includes("tools")) {
                resize();
            }
        } else if (data.type === "animation") {
            // Explode goes off first: both transform the same objects,
            // and animating an already-displaced model is wrong.
            animate(viewer, data.data, data.config.speed, (action) => {
                console.error(`Unknown animation action: ${action}`);
            });
        }
    }

    // The window is where two of the three hosts' messages and resizes arrive,
    // and it is not where the third's do: a pane host has no window message of
    // its own and resizes when a splitter moves, so it passes `listen: false`
    // and calls `handleMessage` and `resize` itself. The dispatch above is the
    // same one either way, which is the point - a message branch is a feature,
    // and a host that wrote its own dispatch would have its own feature set.
    if (listen !== false) {
        window.addEventListener("resize", () => resize(), true);
        window.addEventListener("message", (event) => {
            handleMessage(
                typeof event.data === "string" || event.data instanceof String
                    ? JSON.parse(event.data)
                    : event.data
            );
        });
    }

    return {
        /** Draw the splash, with whatever the host knows that the core cannot. */
        showSplash(config) {
            const splash = logo();
            showViewer(splash.data, { ...splash.config, ...config });
        },

        /** The host's theme changed under it - a VS Code colour theme, say. */
        setTheme(next) {
            if (viewer != null) {
                viewer.setTheme(next);
            }
        },

        /** One message, already parsed. What the window listener above calls. */
        handleMessage,

        /** The surface changed size. What the resize listener above calls. */
        resize
    };
}
