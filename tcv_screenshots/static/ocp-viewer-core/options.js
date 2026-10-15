/**
 * Assembling the three option objects `Viewer.render` and `new Display` take.
 *
 * Which option belongs to which object is three-cad-viewer's fact rather than
 * Python's, so the lists live here in renderer names. The config arrives in
 * those names, Python having converted once at the boundary; no name is
 * translated here. A key still in snake_case is a host that has not converted,
 * and it will miss its entry and fall back to a default rather than be renamed
 * into something plausible.
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

// The defaults themselves, not only the key lists. They describe
// three-cad-viewer, so every client should start from the same numbers and
// override only what is genuinely its own - a viewer whose ambient light or
// whose metalness differs from another's for no stated reason is a difference
// nobody chose.

/** Defaults for `Viewer.render`'s second argument. */
export const RENDER_DEFAULTS = {
  ambientIntensity: 1.0,
  directIntensity: 1.1,
  metalness: 0.3,
  roughness: 0.65,
  // A CSS colour rather than 0x707070. The renderer takes either, but Python
  // always sends this form - `Color(...).web_color` - and a host that mirrors
  // what the renderer reports back into a string-typed setting cannot take the
  // number. One representation across the ecosystem, and it is this one.
  edgeColor: "#707070",
  defaultOpacity: 0.5,
  normalLen: 0,
  angularTolerance: 0.2,
  deviation: 0.1,
  defaultColor: "#e8b024",
};

/** Defaults for `Viewer.render`'s third argument. */
export const VIEWER_DEFAULTS = {
  timeit: false,
  zoom: 1.0,
  position: null,
  quaternion: null,
  target: null,
  centerGrid: false,
  gridFontSize: 12,
  newTreeBehavior: true,
  studioEnvironment: "studio",
  studioEnvIntensity: 1.0,
  studioEnvRotation: 0,
  studioBackground: "environment",
  studioToneMapping: "neutral",
  studioExposure: 1.0,
  studioShadowIntensity: 0.5,
  studioShadowSoftness: 0.2,
  studioAOIntensity: 0.5,
  studioTextureMapping: "parametric",
  studio4kEnvMaps: false,
};

/**
 * Defaults for `new Display(container, options)`.
 *
 * `cadWidth`, `height` and `treeWidth` are here for completeness and are always
 * replaced by the geometry the host measures. The tool flags say which tools
 * exist in this surface at all, which is a host's decision - these are the
 * common answer, not the only one.
 */
export const DISPLAY_DEFAULTS = {
  cadWidth: 730,
  height: 525,
  treeWidth: 240,
  glass: false,
  tools: true,
  theme: "browser",
  pinning: false,
  newTreeBehavior: true,
  keymap: {
    shift: "shiftKey",
    ctrl: "ctrlKey",
    meta: "metaKey",
    alt: "altKey",
  },
  measureTools: true,
  selectTool: true,
  explodeTool: true,
  // Stated here rather than left to the renderer's own default, which is
  // `true`: a host passing `studioTool: false` to hide the Studio tab was
  // silently keeping it, because `display.ts` tests `=== false` and the key
  // never arrived to be tested.
  studioTool: true,
  zebraTool: true,
  zscaleTool: false,
  externalMeasurementBackend: true,
};

/** Options `Viewer.render` takes as its second argument. */
export const RENDER_OPTION_KEYS = [
  "ambientIntensity",
  "directIntensity",
  "metalness",
  "roughness",
  "edgeColor",
  "defaultOpacity",
  "normalLen",
];

/** Options `Viewer.render` takes as its third argument. */
export const VIEWER_OPTION_KEYS = [
  "axes",
  "axes0",
  // A state key `ViewerState._update` accepts and the tree builder reads on
  // every render (`viewer.ts:1343`, `:3446`). Without it here the setting had
  // no route at all in the two page hosts: it is not in either one's splash
  // config, so the Display and Viewer were built with the logo config's
  // `true`, later shows computed it and `page.js` dropped it because the
  // Display already existed, and `apply.js` has no setter for it. Jupyter
  // CadQuery is the contrast that proves it - there `viewer_args` carries it
  // and it works.
  "newTreeBehavior",
  "blackEdges",
  "grid",
  "collapse",
  "ortho",
  "ticks",
  "centerGrid",
  "gridFontSize",
  "timeit",
  "tools",
  "glass",
  "up",
  "transparent",
  "control",
  "panSpeed",
  "zoomSpeed",
  "rotateSpeed",
  "clipSlider0",
  "clipSlider1",
  "clipSlider2",
  "clipNormal0",
  "clipNormal1",
  "clipNormal2",
  "clipIntersection",
  "clipPlaneHelpers",
  "clipObjectColors",
  "zebraCount",
  "zebraOpacity",
  "zebraDirection",
  "zebraColorScheme",
  "zebraMappingMode",
  "studioEnvironment",
  "studioEnvIntensity",
  "studioEnvRotation",
  "studioBackground",
  "studioToneMapping",
  "studioExposure",
  "studioShadowIntensity",
  "studioShadowSoftness",
  "studioAOIntensity",
  "studioTextureMapping",
  "studio4kEnvMaps",
];

/**
 * The config's value for a key, or the fallback.
 *
 * `null` and `undefined` both mean "not given": a host that sends an explicit
 * null is asking for the default, not for null. Every other falsy value -
 * `false`, `0`, `""` - is a value the caller meant, so the test is against null
 * rather than truthiness. Getting that wrong turns `axes: false` into `axes:
 * true` wherever the default is on.
 */
export function preset(config, key, fallback) {
  return config == null || config[key] == null ? fallback : config[key];
}

/** Pick a list of keys out of the config, defaulting each. */
function pick(keys, config, defaults) {
  const options = {};
  for (const key of keys) {
    const value = preset(config, key, defaults == null ? undefined : defaults[key]);
    // A key nobody has a value for is left out rather than passed as
    // undefined. The two are not the same to the renderer: an option that is
    // present is applied, and applying undefined resets whatever it names -
    // which for a camera key means the viewer reports null back, and a host
    // whose settings are typed refuses it.
    //
    // It matters most for a host whose config comes from what a user has set
    // rather than from a stored workspace, where most keys are legitimately
    // absent.
    if (value !== undefined) {
      options[key] = value;
    }
  }
  return options;
}

// Each builder starts from the core's defaults and lets a host override the
// ones that are genuinely its own. A host that passes nothing gets the shared
// answer, which is the point: the numbers describe three-cad-viewer, so a
// client differing from another for no stated reason is a difference nobody
// chose.

export function buildRenderOptions(config, overrides) {
  return pick(RENDER_OPTION_KEYS, config, { ...RENDER_DEFAULTS, ...overrides });
}

export function buildViewerOptions(config, overrides) {
  return pick(VIEWER_OPTION_KEYS, config, { ...VIEWER_DEFAULTS, ...overrides });
}

/**
 * The display options, which are what `new Display(container, options)` reads
 * and what seeds the viewer's state.
 *
 * `geometry` is the host's: only it knows the size of the surface it is drawing
 * on and what to subtract for its own chrome. It supplies `cadWidth`, `height`
 * and `treeWidth` already normalised.
 *
 * `theme` arrives as "light", "dark" or "browser" and is passed through: it is
 * one word in every language here, and the renderer resolves "browser" itself.
 * The boolean `dark` it replaced is gone from the vocabulary - it had not been
 * on the wire since 2025, because each host converted it to `theme` before
 * answering a config request.
 */
export function buildDisplayOptions(config, overrides, geometry) {
  const defaults = { ...DISPLAY_DEFAULTS, ...overrides };
  const fromConfig = pick(["glass", "tools", "keymap", "newTreeBehavior"], config, defaults);

  const theme = preset(config, "theme", defaults.theme);

  return {
    ...fromConfig,
    theme,
    cadWidth: geometry.cadWidth,
    height: geometry.height,
    treeWidth: geometry.treeWidth,

    // Capability flags the host owns: whether a tool exists in this surface at
    // all is not something a document can ask for.
    //
    // `pinning` and `studioTool` were merged into `defaults` above and then
    // left out of this hand-written list, so they never reached the renderer.
    // `display.ts` reads `options.pinning` in its constructor, which is why
    // cad-viewer-widget's pin-as-PNG button could not appear in any cell
    // viewer, `pinning=True` asked for or defaulted. Nothing was said: an
    // option the renderer does not receive is indistinguishable from one it
    // was never given.
    pinning: defaults.pinning,
    studioTool: defaults.studioTool,
    measureTools: defaults.measureTools,
    selectTool: defaults.selectTool,
    explodeTool: defaults.explodeTool,
    zscaleTool: defaults.zscaleTool,
    zebraTool: defaults.zebraTool,
    externalMeasurementBackend: defaults.externalMeasurementBackend,
  };
}
