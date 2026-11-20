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
 *
 * `selected` and `lastPick` are state since three-cad-viewer 5.2, kept so that
 * `status()` can tell what the user has selected and last picked. Nothing
 * re-applies them: no host acts on either (the clipboard runs on
 * `selectedText`), Python's `combined_config` takes only the keys of
 * `keys.CONFIG`, a new model reports the empty selection, and the page drops
 * `lastPick` itself on a new model.
 */
export const EVENT_KEYS = new Set([
  "selectedShapeIDs",
  "activeTool",
  "relative_time",
  // three-cad-viewer 5.1: the point Ctrl/Cmd-C copied, for hosts whose page
  // cannot reach the clipboard. A copy, not a property of the viewer.
  "copiedPoint",
  // The select tool's selection as clipboard text, made here from `selected`
  // (see `selectionText`). It belongs to that selection only.
  "selectedText",
]);

/**
 * The kinds whose indices a person pastes into `select_faces`, `select_edges`
 * and `select_vertices`; a whole solid has none.
 */
const INDEX_KINDS = new Set(["faces", "edges", "vertices"]);

let unusableSelectionWarned = false;

/**
 * The clipboard text for three-cad-viewer's `selected`, or null to copy nothing.
 *
 * `selected` is `{"<object path>/<kind>": [indices]}` since three-cad-viewer
 * 5.2.0, in the order of selection. The text is for a person, who pastes the
 * indices into `select_edges(obj, [...])` and its siblings, so it stays what the
 * clipboard held before 5.2.0 wherever that was right:
 *
 * - one key of faces, edges or vertices: the indices, comma-separated, e.g.
 *   `6,16,7,17`;
 * - several keys (several objects, or several kinds of one object): a comment
 *   line `# <object path> <kind>` before each key's indices, so the indices of
 *   two objects are never one list that selects the wrong shapes;
 * - a whole solid (`<solid path>/solids`): its comment line only, `# <path>
 *   solid`, since there are no indices to paste;
 * - the empty selection (`{}`, sent when the select tool goes off or on
 *   Escape): null, so the user's clipboard is not emptied.
 *
 * Anything else, e.g. the list of an older three-cad-viewer, is null with one
 * warning: the peer range excludes that format, and guessing at it would copy
 * text that selects the wrong shapes.
 *
 * The page hosts get the text as `selectedText` from the notifier below; a host
 * with its own notification handler (the widget) calls this directly.
 */
export function selectionText(selected) {
  const isPlainObject =
    selected !== null &&
    typeof selected === "object" &&
    Array.isArray(selected) === false;
  if (isPlainObject === false) {
    if (unusableSelectionWarned === false) {
      unusableSelectionWarned = true;
      console.warn(
        "ocp-viewer-core: `selected` is not grouped by object and kind; " +
          "three-cad-viewer 5.2.0 or later is required, nothing was copied"
      );
    }
    return null;
  }

  const entries = Object.entries(selected);
  if (entries.length === 0) {
    return null;
  }

  const split = (key) => {
    const slash = key.lastIndexOf("/");
    return [key.slice(0, slash), key.slice(slash + 1)];
  };

  if (entries.length === 1) {
    const [key, indices] = entries[0];
    const [, kind] = split(key);
    if (INDEX_KINDS.has(kind)) {
      return indices.join(",");
    }
  }

  const lines = [];
  for (const [key, indices] of entries) {
    const [object, kind] = split(key);
    if (kind === "solids") {
      lines.push(`# ${object} solid`);
    } else {
      lines.push(`# ${object} ${kind}`, indices.join(","));
    }
  }
  return lines.join("\n");
}

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

    // The clipboard text rides with the selection it was made from; for an
    // empty selection there is none, so a host copies nothing.
    if (message.selected !== undefined) {
      const text = selectionText(message.selected);
      if (text !== null) {
        message.selectedText = text;
      }
    }

    // One up for every selection and every pick, so a reader of the status
    // tells a new one from the same one read twice, also when the new one
    // equals the last.
    if (message.selected !== undefined) {
      status.selection_seq = (status.selection_seq ?? 0) + 1;
      message.selection_seq = status.selection_seq;
    }
    if (message.lastPick !== undefined) {
      status.pick_seq = (status.pick_seq ?? 0) + 1;
      message.pick_seq = status.pick_seq;
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
