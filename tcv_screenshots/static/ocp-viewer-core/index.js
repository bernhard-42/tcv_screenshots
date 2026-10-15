/**
 * The shared viewer policy, as one entry point.
 *
 * Everything here is host-neutral. All of it but `page.js` takes a
 * three-cad-viewer instance and plain data and touches no DOM, no transport
 * and no host; `page.js` is the page, so it does. What stays with a host is
 * how it starts - where it loaded these modules from, where its settings come
 * from - and the sending half of its Comms.
 *
 * Names are camelCase and values are plain JSON, because that is what this side
 * of the wire speaks. Python converts once, at the boundary, on its way out.
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

export { applyConfig, currentValue, isApplicable, GEOMETRY_KEYS, VIEWS } from "./apply.js";

export {
  buildDisplayOptions,
  buildRenderOptions,
  buildViewerOptions,
  preset,
  DISPLAY_DEFAULTS,
  RENDER_DEFAULTS,
  RENDER_OPTION_KEYS,
  VIEWER_DEFAULTS,
  VIEWER_OPTION_KEYS,
} from "./options.js";

// Drawing a model and deciding where the camera ends up - the policy every
// client has to agree on, and the one that was hardest to get right.
export { createRenderer } from "./render.js";

// The page itself: the viewer, the message handling and the resizing. The one
// module here that touches the DOM, because it is the page.
export { createPage } from "./page.js";

export {
  collectStates,
  currentStates,
  restoreStates,
  statesToRestore,
} from "./states.js";

export { addAnimationTrack, animate, animationDuration } from "./animation.js";

export { createNotifier, EVENT_KEYS } from "./notify.js";

// The splash. Data rather than policy, and here for the same reason the policy
// is: every client shows it, and four of them had their own copy.
export { logo } from "./logo.js";

// The JavaScript half's version, for the major.minor handshake with Python.
export { VERSION } from "./version.js";
