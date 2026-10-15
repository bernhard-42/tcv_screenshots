/**
 * Reporting viewer changes back to Python.
 *
 * three-cad-viewer calls a notification callback with `{key: {old, new}}` for
 * whatever changed. This turns that into the message a host sends, and keeps a
 * running picture of the viewer's state so a host can answer `status()` out of
 * memory instead of asking the browser.
 *
 * The names here are the renderer's own notification names, which are
 * snake_case - `clip_intersection`, `zebra_count`, `relative_time`. So nothing
 * is translated on the way back: the renderer already emits what Python
 * speaks, and the camelCase conversion is one-directional by the renderer's own
 * choice rather than by ours.
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

/**
 * Keys that report that something happened, as opposed to what something is.
 *
 * These must never be accumulated into a status snapshot. An accumulated
 * `selectedShapeIDs` replays a selection the user made minutes ago into the
 * next measurement, against a model that may not even contain those ids.
 *
 * The distinction is not "does it change often". It is whether re-applying the
 * last value to a different model still means anything.
 */
export const EVENT_KEYS = new Set([
  "selectedShapeIDs",
  "selected",
  "lastPick",
  "activeTool",
  "relative_time",
  // three-cad-viewer 5.1: the point Ctrl/Cmd-C copied, for hosts whose page
  // cannot reach the clipboard. A copy, not a property of the viewer.
  "copiedPoint",
]);

/**
 * Create the notification callback.
 *
 * The message sent is the *delta* - only what this change carried - rather than
 * a snapshot accumulated across every change so far. `viewer.html` accumulates
 * into one long-lived object, which is what lets a stale event key ride along
 * with an unrelated update. The accumulated picture still exists here, as
 * `status`, but it holds state keys only and is never what goes on the wire.
 *
 * @param viewer  the viewer, read for tree states
 * @param send    (message) => void, the host's transport
 * @param debug   optional (label, value) => void
 * @returns `{ notify, status }` - `notify` is the callback to hand the viewer,
 *          `status` is the live picture to answer a status request from
 */
export function createNotifier({ viewer, send, debug }) {
  const status = {};
  let lastStatesJson = null;

  function notify(change) {
    if (debug) {
      debug("notify", change);
    }

    const message = {};
    let changed = false;

    for (const key of Object.keys(change)) {
      const value = change[key] == null ? undefined : change[key].new;
      if (value === undefined) {
        continue;
      }
      message[key] = value;
      changed = true;
      if (!EVENT_KEYS.has(key)) {
        status[key] = value;
      }
    }

    // Tree state is not part of the change set - the viewer reports it
    // separately - so it is read and compared. Serialising is also how it gets
    // cloned: `getStates()` hands back the tree's own live arrays, so keeping
    // the reference would compare an object against itself and never report a
    // change.
    if (viewer != null && viewer.treeview != null) {
      const json = JSON.stringify(viewer.treeview.getStates());
      if (lastStatesJson == null || lastStatesJson !== json) {
        const states = JSON.parse(json);
        message.states = states;
        status.states = states;
        lastStatesJson = json;
        changed = true;
      }
    }

    if (changed) {
      send(message);
    }
    return changed ? message : null;
  }

  return { notify, status };
}
