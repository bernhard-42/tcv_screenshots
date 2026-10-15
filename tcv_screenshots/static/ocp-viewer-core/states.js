/**
 * Tree visibility state across a re-`show()`.
 *
 * When a model is shown again, the user's visibility choices should survive
 * for the objects that are still there. Without this, every `show()` resets the
 * tree.
 *
 * The two halves are pure and take no viewer: what the new model contains, and
 * which of the old choices are worth re-applying. Only the orchestrator at the
 * bottom touches a viewer.
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
 * The visibility state of every leaf in a tessellated model, keyed by id.
 *
 * A node with `parts` is a group and carries no state of its own; a node
 * without is a leaf. The key is the node's `id`, which is the leading-slash
 * path - the same form `viewer.treeview.getStates()` returns, which is what
 * makes the two comparable. The renderer assumes those two addressings agree
 * (`node.id === parent.id + "/" + node.name`) and validates it nowhere, so a
 * mismatch here shows up as states that silently fail to restore.
 */
export function collectStates(shapes) {
  const states = {};
  function walk(node) {
    if (node == null) {
      return;
    }
    if (node.parts != null) {
      for (const part of node.parts) {
        walk(part);
      }
    } else {
      states[node.id] = node.state;
    }
  }
  walk(shapes);
  return states;
}

/**
 * Which of the previous states should be re-applied to the new model.
 *
 * A key qualifies when it still exists in the new model and its state actually
 * differs, so an unchanged tree produces an empty result and no repaint. The
 * state is the `[faces, edges]` pair, compared element by element - the arrays
 * are distinct objects on both sides, so identity would say "different" every
 * time and restore the entire tree on every show.
 */
export function statesToRestore(oldStates, newStates) {
  const restore = {};
  if (oldStates == null || newStates == null) {
    return restore;
  }
  for (const key of Object.keys(oldStates)) {
    const before = oldStates[key];
    const after = newStates[key];
    if (after == null || before == null) {
      continue;
    }
    if (before[0] !== after[0] || before[1] !== after[1]) {
      restore[key] = before;
    }
  }
  return restore;
}

/**
 * Read the states a viewer currently holds, safely on a viewer that has not
 * rendered yet.
 *
 * Note that `getStates()` hands back the tree's own live arrays rather than
 * copies, so the result must be treated as a snapshot to read and never
 * mutated - the next render would be writing through it.
 */
export function currentStates(viewer) {
  if (viewer == null || viewer.treeview == null) {
    return {};
  }
  return viewer.treeview.getStates();
}

/**
 * Apply tree state after a model has been rendered.
 *
 * Explicit states win: a caller who passed `states=` is describing what they
 * want to see, and it outranks what the user last clicked. Otherwise the prior
 * choices are restored for whatever survived into the new model.
 *
 * Either way it is one batched `setStates`. A per-key `setState` loop is a
 * repaint per key, and on a large model - turning every edge off, say - that is
 * the whole scene re-rendered once per object, which freezes the host.
 */
export function restoreStates(viewer, shapes, oldStates, explicitStates) {
  if (explicitStates != null) {
    viewer.setStates(explicitStates);
    return explicitStates;
  }
  const restore = statesToRestore(oldStates, collectStates(shapes));
  if (Object.keys(restore).length > 0) {
    viewer.setStates(restore);
  }
  return restore;
}
