/**
 * Applying a configuration to a running three-cad-viewer instance.
 *
 * One dispatch for every host: a set of changed keys in, a call on the viewer
 * for each. A host asked to apply a configuration - from Python, or from a
 * widget's own change observer - routes it through here.
 *
 * The keys are camelCase and the values are plain JSON, because that is what
 * this side of the wire speaks. Python owns snake_case and the enums, and
 * converts once, at the boundary, in `Config.to_javascript`. Nothing here
 * translates a name or unwraps an enum: a key that arrives in snake_case is a
 * host that has not converted, and it should surface as an unknown key rather
 * than be quietly accepted in both spellings.
 *
 * A host whose wire format shares one name across both halves - an ipywidgets
 * traitlet, say - converts before calling in. The rule is the same; only the
 * place it is applied differs.
 *
 * The method is not derivable from the name: `grid` is `setGrids`, `glass` is
 * `glassMode`, `tools` is `showTools`, `collapse` is `collapseNodes`. Deriving a
 * mechanism from a name is how the option path silently lost keys, so the table
 * is written out.
 *
 * Nothing here touches the DOM, a transport, or a host, so it can be tested
 * headless against a stub viewer.
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

// Keys whose value is a viewport dimension. Only the host knows the other two,
// so applying one means asking the host to resize rather than calling the
// viewer directly. Both hosts end in `resizeCadView`, reading the other
// dimensions from their own state.
export const GEOMETRY_KEYS = ["cadWidth", "treeWidth", "height"];

// The camera views `resetCamera` accepts beyond "reset", which is "iso" plus a
// resize. Anything else - including "keep" - deliberately does nothing, because
// `setView` on an unknown name leaves the camera where it was with no error.
export const VIEWS = ["iso", "left", "right", "top", "bottom", "rear", "front"];

const TOOLS = ["distance", "properties", "select"];

/**
 * Call a viewer setter, appending the notify flag only when the host asked for
 * one. cad-viewer-widget passes `true` to keep its traitlets in step;
 * ocp_vscode omits it and takes the setter's own default. Passing `undefined`
 * is not the same as not passing it, so the argument list is built rather than
 * padded.
 */
function call(viewer, method, args, notify) {
  if (notify === undefined) {
    viewer[method](...args);
  } else {
    viewer[method](...args, notify);
  }
}

const SETTERS = {
  axes: (v, value, ctx) => call(v, "setAxes", [value], ctx.notify),
  axes0: (v, value, ctx) => call(v, "setAxes0", [value], ctx.notify),
  grid: (v, value, ctx) => call(v, "setGrids", [value], ctx.notify),
  centerGrid: (v, value, ctx) => call(v, "setGridCenter", [value], ctx.notify),
  ortho: (v, value, ctx) => call(v, "setOrtho", [value], ctx.notify),
  transparent: (v, value, ctx) => call(v, "setTransparent", [value], ctx.notify),
  blackEdges: (v, value, ctx) => call(v, "setBlackEdges", [value], ctx.notify),

  zoom: (v, value, ctx) => call(v, "setCameraZoom", [value], ctx.notify),
  // `setCameraPosition(position, relative, notify)` takes a flag between the
  // value and the notify flag that the other three camera setters do not, so
  // `relative` is passed explicitly. Without it a host that asks for
  // notification lands `true` in that slot and the camera moves *by* the
  // vector instead of *to* it.
  position: (v, value, ctx) => call(v, "setCameraPosition", [value, false], ctx.notify),
  quaternion: (v, value, ctx) => call(v, "setCameraQuaternion", [value], ctx.notify),
  target: (v, value, ctx) => call(v, "setCameraTarget", [value], ctx.notify),

  // No `up` here, and it is not an omission. It cannot be applied to a live
  // viewer: `Camera` reads `cameraUp[this.up]` once, in its constructor, so
  // assigning `camera.up` afterwards changes nothing about the cameras - it only
  // corrupts the lookup `presetCamera` makes, and the next click on ISO or TOP
  // dies on `defaultDirections[undefined]`. Worse, the value written was the
  // config's "Z", where that lookup is keyed by "z_up".
  //
  // `up` is a render option instead, and `Viewer.render` honours it: it builds a
  // new `Camera` with `viewerOptions.up` every time. So `set_defaults(up=...)`
  // takes effect on the next show, which is the only moment it can.

  edgeColor: (v, value, ctx) => call(v, "setEdgeColor", [value], ctx.notify),
  defaultOpacity: (v, value, ctx) => call(v, "setOpacity", [value], ctx.notify),
  ambientIntensity: (v, value, ctx) => call(v, "setAmbientLight", [value], ctx.notify),
  directIntensity: (v, value, ctx) => call(v, "setDirectLight", [value], ctx.notify),
  metalness: (v, value, ctx) => call(v, "setMetalness", [value], ctx.notify),
  roughness: (v, value, ctx) => call(v, "setRoughness", [value], ctx.notify),

  // three-cad-viewer has had `setKeyMap(config)` all along (`viewer.ts:4538`)
  // and nothing called it: the keymap reached only `new Display(...)`, which
  // runs once per page, so the modifier keys a user configured applied in
  // whichever host happened to pass them at splash and nowhere else, and could
  // never be changed on a live viewer.
  keymap: (v, value) => v.setKeyMap(value),

  zoomSpeed: (v, value, ctx) => call(v, "setZoomSpeed", [value], ctx.notify),
  panSpeed: (v, value, ctx) => call(v, "setPanSpeed", [value], ctx.notify),
  rotateSpeed: (v, value, ctx) => call(v, "setRotateSpeed", [value], ctx.notify),

  // "light", "dark", or "browser" to follow the surface. Applied on a live
  // viewer as well as at construction, which is what lets a host whose theme
  // changes under it - a VS Code colour theme - say so without rebuilding.
  theme: (v, value) => v.setTheme(value),

  glass: (v, value, ctx) => call(v, "glassMode", [value], ctx.notify),
  tools: (v, value, ctx) => call(v, "showTools", [value], ctx.notify),
  tab: (v, value, ctx) => call(v, "setActiveTab", [value], ctx.notify),
  explode: (v, value, ctx) => call(v, "setExplode", [value], ctx.notify),

  // The value is the CollapseState the renderer uses. Python's Collapse enum
  // carries those same numbers, so unwrapping the enum is the whole of the
  // translation and nothing is mapped here.
  collapse: (v, value, ctx) => call(v, "collapseNodes", [value], ctx.notify),

  clipIntersection: (v, value, ctx) => call(v, "setClipIntersection", [value], ctx.notify),
  clipPlaneHelpers: (v, value, ctx) => call(v, "setClipPlaneHelpers", [value], ctx.notify),
  clipObjectColors: (v, value, ctx) => call(v, "setClipObjectColorCaps", [value], ctx.notify),

  zebraCount: (v, value, ctx) => call(v, "setZebraCount", [value], ctx.notify),
  zebraOpacity: (v, value, ctx) => call(v, "setZebraOpacity", [value], ctx.notify),
  zebraDirection: (v, value, ctx) => call(v, "setZebraDirection", [value], ctx.notify),
  zebraColorScheme: (v, value, ctx) => call(v, "setZebraColorScheme", [value], ctx.notify),
  zebraMappingMode: (v, value, ctx) => call(v, "setZebraMappingMode", [value], ctx.notify),

  // The studio family. cad-viewer-widget has had these as a setter table;
  // ocp_vscode accepts all eleven through set_viewer_config and has no branch
  // for any of them, so sending one posts a message the viewer drops without a
  // word. Unifying the dispatch closes that by construction, and it is a gain in
  // capability for ocp_vscode rather than a like-for-like move.
  studioEnvironment: (v, value, ctx) => call(v, "setStudioEnvironment", [value], ctx.notify),
  studioEnvIntensity: (v, value, ctx) => call(v, "setStudioEnvIntensity", [value], ctx.notify),
  studioEnvRotation: (v, value, ctx) => call(v, "setStudioEnvRotation", [value], ctx.notify),
  studioBackground: (v, value, ctx) => call(v, "setStudioBackground", [value], ctx.notify),
  studioToneMapping: (v, value, ctx) => call(v, "setStudioToneMapping", [value], ctx.notify),
  studioExposure: (v, value, ctx) => call(v, "setStudioExposure", [value], ctx.notify),
  studioShadowIntensity: (v, value, ctx) =>
    call(v, "setStudioShadowIntensity", [value], ctx.notify),
  studioShadowSoftness: (v, value, ctx) => call(v, "setStudioShadowSoftness", [value], ctx.notify),
  studioAOIntensity: (v, value, ctx) => call(v, "setStudioAOIntensity", [value], ctx.notify),
  studioTextureMapping: (v, value, ctx) => call(v, "setStudioTextureMapping", [value], ctx.notify),
  studio4kEnvMaps: (v, value, ctx) => call(v, "setStudio4kEnvMaps", [value], ctx.notify),

  // "reset" means iso plus a resize; the other view names pass through.
  resetCamera: (v, value) => {
    if (value === "reset") {
      v.setView("iso");
      v.resize();
    } else if (VIEWS.includes(value)) {
      v.setView(value);
    }
  },

  // Deactivate whatever measurement tool is on before activating the new one.
  // `setTool(name, false)` is a no-op when that tool was not on, so this is safe
  // to run unconditionally. "off" leaves everything off.
  analysisTool: (v, value) => {
    const active = v.state.get("activeTool");
    if (typeof active === "string" && TOOLS.includes(active)) {
      v.display.setTool(active, false);
    }
    if (TOOLS.includes(value)) {
      v.display.setTool(value, true);
    }
  },

  // Batched on purpose: a per-key `setState` loop over a large model is one
  // repaint per key and freezes the host. Paths absent from the current model
  // are dropped - a state map outlives the model it was taken from.
  states: (v, value, ctx) => {
    const valid = Object.keys(v.treeview.getStates());
    const next = {};
    for (const path of Object.keys(value)) {
      if (valid.includes(path)) {
        next[path] = value[path];
      }
    }
    if (Object.keys(next).length > 0) {
      call(v, "setStates", [next], ctx.notify);
    }
  },
};

/** Clip sliders and normals are indexed by the digit their key ends with. */
function clipSetter(key) {
  if (key.startsWith("clipSlider")) {
    return (v, value, ctx) => call(v, "setClipSlider", [Number(key.slice(-1)), value], ctx.notify);
  }
  if (key.startsWith("clipNormal")) {
    // The slider has to be handed back in, or setting a normal moves the plane.
    return (v, value, ctx) => {
      const index = Number(key.slice(-1));
      call(v, "setClipNormal", [index, value, v.getClipSlider(index)], ctx.notify);
    };
  }
  return null;
}

/**
 * What the viewer currently holds for a key, or `undefined` if it cannot be
 * read back.
 *
 * The other half of `SETTERS`, and here for the same reason: which getter
 * answers for which option is three-cad-viewer's fact, not a host's, and a
 * wrong pairing is silent. It exists for `applyConfig`'s `accept` hook - a host
 * driven by change notifications needs to know whether a value is already in
 * place, or it re-applies what the viewer just told it.
 *
 * `undefined` means "no way to ask", not "unset", and a caller should read that
 * as "apply it". Several settings are genuinely write-only from here - explode
 * and the tab are actions rather than state, and the studio family has no
 * getters at all.
 */
export function currentValue(viewer, key) {
  const getter = GETTERS[key];
  return getter === undefined ? undefined : getter(viewer);
}

const GETTERS = {
  axes: (v) => v.getAxes(),
  axes0: (v) => v.getAxes0(),
  grid: (v) => v.getGrids(),
  ortho: (v) => v.getOrtho(),
  transparent: (v) => v.getTransparent(),
  blackEdges: (v) => v.getBlackEdges(),
  tools: (v) => v.getTools(),

  zoom: (v) => v.getCameraZoom(),
  position: (v) => v.getCameraPosition(),
  quaternion: (v) => v.getCameraQuaternion(),
  target: (v) => v.getCameraTarget(),

  edgeColor: (v) => v.getEdgeColor(),
  defaultOpacity: (v) => v.getOpacity(),
  ambientIntensity: (v) => v.getAmbientLight(),
  directIntensity: (v) => v.getDirectLight(),
  metalness: (v) => v.getMetalness(),
  roughness: (v) => v.getRoughness(),

  zoomSpeed: (v) => v.getZoomSpeed(),
  panSpeed: (v) => v.getPanSpeed(),
  rotateSpeed: (v) => v.getRotateSpeed(),

  clipIntersection: (v) => v.getClipIntersection(),
  clipPlaneHelpers: (v) => v.getClipPlaneHelpers(),
  clipObjectColors: (v) => v.getObjectColorCaps(),

  clipSlider0: (v) => v.getClipSlider(0),
  clipSlider1: (v) => v.getClipSlider(1),
  clipSlider2: (v) => v.getClipSlider(2),
  clipNormal0: (v) => v.getClipNormal(0),
  clipNormal1: (v) => v.getClipNormal(1),
  clipNormal2: (v) => v.getClipNormal(2),
};

/** Whether this key is one `applyConfig` knows how to apply. */
export function isApplicable(key) {
  return Boolean(SETTERS[key]) || Boolean(clipSetter(key)) || GEOMETRY_KEYS.includes(key);
}

/**
 * Apply a configuration to a live viewer.
 *
 * @param viewer   a three-cad-viewer instance
 * @param config   {key: value}, camelCase keys and plain JSON values
 * @param ctx      optional hooks:
 *                   notify    - passed as the trailing flag to every setter
 *                               that takes one; omitted entirely when undefined
 *                   resize    - (key, value) => void, for a viewport dimension,
 *                               which only the host can resolve
 *                   accept    - (key, value) => boolean, a chance to skip a key
 *                               whose value the viewer already holds. The widget
 *                               needs it: driven by traitlet changes, it would
 *                               otherwise re-apply what it just reported
 *                   onUnknown - (key, value) => void, for a key nothing here
 *                               handles. Left unset the key is dropped, which is
 *                               the default, but silently
 * @returns the keys that were applied
 */
export function applyConfig(viewer, config, ctx = {}) {
  if (viewer == null || config == null) {
    return [];
  }
  const applied = [];
  for (const key of Object.keys(config)) {
    const value = config[key];

    if (ctx.accept && !ctx.accept(key, value)) {
      continue;
    }

    if (GEOMETRY_KEYS.includes(key)) {
      if (ctx.resize) {
        ctx.resize(key, value);
        applied.push(key);
      }
      continue;
    }

    const setter = SETTERS[key] || clipSetter(key);
    if (setter) {
      setter(viewer, value, ctx);
      applied.push(key);
    } else if (ctx.onUnknown) {
      ctx.onUnknown(key, value);
    }
  }
  return applied;
}
