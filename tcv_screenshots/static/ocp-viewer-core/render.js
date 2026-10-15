/**
 * Drawing a model, and deciding where the camera ends up.
 *
 * This is the part that was hard to get right, and it is the part every client
 * has to agree on: what `reset_camera` means, and above all what *keeping* the
 * camera means when the model underneath it has changed. ocp_vscode worked this
 * out over a long time; cad-viewer-widget has its own version; build123d Studio
 * has none at all, which is why a second `show()` there throws the view away.
 * One answer, so a script that looks right in one viewer looks right in all of
 * them.
 *
 * The three modes, since the names understate the difference:
 *
 *   keep    the camera direction survives, the distance is recomputed from the
 *           new bounding box, and the zoom is corrected by how much that
 *           distance moved. Not "leave the camera alone" - a model ten times
 *           larger, left alone, is off screen.
 *   center  the direction survives and the target moves to the new centre.
 *   reset   and the preset views: the stored state is discarded.
 *
 * Nothing here touches the DOM, a transport or a host. The two things only a
 * host knows - the size of the surface it draws on, and how to send a status
 * message - arrive as callbacks.
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

import { VIEWS } from "./apply.js";
import { buildRenderOptions, buildViewerOptions, preset } from "./options.js";

// The carry-over pairs: the option name the renderer takes, and the name the
// same value comes back under in a notification. Sliders and normals are
// deliberately absent - three-cad-viewer decides for itself whether to keep or
// reset those, from whether the bounding box changed, and an explicit value
// from the caller already arrives through buildViewerOptions.
const CARRY_OVER = [
    ["clipIntersection", "clip_intersection"],
    ["clipPlaneHelpers", "clip_planes"],
    ["clipObjectColors", "clip_object_colors"],
    ["zebraCount", "zebra_count"],
    ["zebraOpacity", "zebra_opacity"],
    ["zebraDirection", "zebra_direction"],
    ["zebraColorScheme", "zebra_color_scheme"],
    ["zebraMappingMode", "zebra_mapping_mode"]
];

function length(v) {
    return Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
}

function normalize(v) {
    const n = length(v);
    return [v[0] / n, v[1] / n, v[2] / n];
}

/** The centre and the radius of a model's bounding box. */
function boundingSphere(bb) {
    const center = [
        (bb.xmax + bb.xmin) / 2,
        (bb.ymax + bb.ymin) / 2,
        (bb.zmax + bb.zmin) / 2
    ];
    const radius = Math.max(
        Math.sqrt(
            Math.pow(bb.xmax - bb.xmin, 2) +
                Math.pow(bb.ymax - bb.ymin, 2) +
                Math.pow(bb.zmax - bb.zmin, 2)
        ),
        length(center)
    );
    return { center, radius };
}

/**
 * Create the renderer for one viewer.
 *
 * State is held here rather than by the host because it is this policy's:
 * the camera distance of the previous render, which the zoom correction needs,
 * and the previous bounding radius.
 *
 * @param viewer      a three-cad-viewer instance
 * @param status      the picture `createNotifier` keeps. Read for the stored
 *                    camera and the carried-over settings, and written with
 *                    what the renderer settled on - a render is a change the
 *                    viewer does not notify about
 * @param overrides   optional {render, viewer, theme} - only what this host
 *                    genuinely differs on. The defaults themselves come from
 *                    the core, so a host that overrides nothing behaves like
 *                    every other one
 * @param resize      () => void, called when the config carries a tree width.
 *                    Only the host can resolve the other two dimensions
 * @param sendStatus  (snapshot) => void, the host's status message
 * @param debug       optional (label, value) => void
 */
export function createRenderer({ viewer, status, overrides, resize, sendStatus, debug }) {
    const hostOverrides = overrides || {};
    let cameraDistance = null;
    let lastRadius = null;

    function log(label, value) {
        if (debug) {
            debug(label, value);
        }
    }

    function render(meshData, config) {
        const shapes = meshData.shapes || meshData;
        const renderOptions = buildRenderOptions(config, hostOverrides.render);
        const viewerOptions = buildViewerOptions(config, hostOverrides.viewer);

        if (!config.theme) {
            config.theme = hostOverrides.theme;
        }

        const resetCamera = preset(config, "resetCamera", "keep");
        log("renderOptions", renderOptions);
        log("viewerOptions", viewerOptions);
        log("resetCamera", resetCamera);

        const { center, radius } = boundingSphere(shapes["bb"]);
        lastRadius = radius;

        // "keep" and "center" are the two modes that carry the previous camera
        // over; a preset view and "reset" start from the config alone.
        const useStoredState = resetCamera === "keep" || resetCamera === "center";
        const newZoom = config.zoom !== undefined;

        if (!useStoredState) {
            viewerOptions.zoom = config.zoom !== undefined ? config.zoom : 1.0;
            if (config.position !== undefined) {
                viewerOptions.position = config.position;
            }
            if (config.quaternion !== undefined) {
                viewerOptions.quaternion = config.quaternion;
            }
            if (config.target !== undefined) {
                viewerOptions.target = config.target;
            }
            cameraDistance = null;
        } else {
            if (config.position) {
                viewerOptions.position = config.position;
            } else if (status.position) {
                let p = [0, 0, 0];
                if (resetCamera === "keep") {
                    // The direction from target to camera is what survives. The
                    // distance is taken from the new model's radius, so the
                    // model stays the same size on screen however much it grew.
                    const distance = 2.5 * radius;
                    for (let i = 0; i < 3; i++) {
                        p[i] = status.position[i] - status.target[i];
                    }
                    p = normalize(p);
                    for (let i = 0; i < 3; i++) {
                        p[i] = p[i] * distance + status.target[i];
                    }
                } else {
                    // center: same direction, aimed at the new centre.
                    for (let i = 0; i < 3; i++) {
                        p[i] = status.position[i] - status.target[i] + center[i];
                    }
                    status.target = center;
                }
                viewerOptions.position = p;
            }
            status.position = viewerOptions.position;

            if (config.quaternion) {
                viewerOptions.quaternion = config.quaternion;
            } else if (status.quaternion) {
                viewerOptions.quaternion = status.quaternion;
            }
            status.quaternion = viewerOptions.quaternion;

            if (config.target) {
                viewerOptions.target = config.target;
            } else if (status.target) {
                viewerOptions.target = status.target;
            }
            status.target = viewerOptions.target;

            if (config.zoom) {
                viewerOptions.zoom = config.zoom;
            } else if (status.zoom) {
                viewerOptions.zoom = status.zoom;
            }
            status.zoom = viewerOptions.zoom;
        }

        log("position", status.position);
        log("quaternion", status.quaternion);
        log("target", status.target);
        log("zoom", status.zoom);

        for (const [optionKey, statusKey] of CARRY_OVER) {
            viewerOptions[optionKey] =
                config[optionKey] !== undefined ? config[optionKey] : status[statusKey];
        }

        if (config.tab) {
            // Through render rather than a setActiveTab afterwards, so the
            // scene is built in the target tab instead of being painted in CAD
            // mode first and switched.
            viewerOptions.tab = config.tab;
        }

        // The envelope when it is the instanced format, the tree otherwise.
        //
        // A host that received base64 hands over `{instances, shapes}` and the
        // renderer decodes and resolves it itself. A host that decoded its own
        // buffers - build123d Studio reads raw arrays off a binary frame and
        // builds typed-array views onto it with no copy - cannot go that way:
        // `decodeBuffer` base64-decodes unconditionally. It resolves the refs
        // itself, with the renderer's own `resolveInstances`, and hands over a
        // plain tree.
        //
        // Passing the envelope regardless is what broke that host: with no
        // `instances` beside them, the shapes went in as an object with no
        // `parts`, and the walk died on `id.replaceAll` of undefined - after
        // clear() had already taken the previous model off the screen.
        const instanced = Array.isArray(meshData.instances);
        viewer.render(instanced ? meshData : shapes, renderOptions, viewerOptions);

        if (config.treeWidth && resize) {
            resize();
        }

        if (!newZoom && resetCamera === "keep" && cameraDistance != null) {
            // The camera moved to suit the new model's size, so the zoom is
            // corrected by the same ratio - without this, "keep" keeps the
            // number and loses the framing.
            viewer.setCameraZoom(
                ((status.zoom == null ? 1.0 : status.zoom) *
                    viewer.camera.camera_distance) /
                    cameraDistance
            );
        }

        if (VIEWS.includes(resetCamera)) {
            viewer.setView(resetCamera);
        }

        // Read back what the renderer settled on. A render is a change it does
        // not notify about, so without this the next "keep" carries over the
        // camera from two models ago.
        status.position = viewer.getCameraPosition();
        status.quaternion = viewer.getCameraQuaternion();
        status.target = viewer.controls.getTarget().toArray();
        status.zoom = viewer.getCameraZoom();
        cameraDistance = viewer.camera.camera_distance;

        status.clip_planes = viewer.getClipPlaneHelpers();
        status.clip_object_colors = viewer.getObjectColorCaps();
        status.clip_intersection = viewer.getClipIntersection();
        status.zebra_count = viewer.getZebraCount();
        status.zebra_opacity = viewer.getZebraOpacity();
        status.zebra_direction = viewer.getZebraDirection();
        status.zebra_color_scheme = viewer.getZebraColorScheme();
        status.zebra_mapping_mode = viewer.getZebraMappingMode();

        if (sendStatus) {
            sendStatus({ ...status });
        }

        if (config.explode) {
            viewer.setExplode(true);
        }

        // Applied here rather than through the option path, the same way explode
        // is: it is a tool activation, not an option the renderer holds.
        if (["distance", "properties", "select"].includes(config.analysisTool)) {
            viewer.display.setTool(config.analysisTool, true);
        }

        return viewerOptions;
    }

    return {
        render,
        /** The previous model's bounding radius, for a host that wants it. */
        get lastRadius() {
            return lastRadius;
        }
    };
}
