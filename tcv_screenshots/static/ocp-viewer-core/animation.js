/**
 * Animation tracks.
 *
 * A track is `[selector, action, times, values]`, and the action decides which
 * of the viewer's five track methods it becomes. `viewer.html` has this as a
 * switch in its message handler; cad-viewer-widget has the same mapping spread
 * across `addTrack`, `addTracks`, `animate` and `clearAnimation`.
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

/** The two-letter action codes, and the call each becomes. */
const TRACKS = {
  t: (v, sel, times, values) => v.addPositionTrack(sel, times, values),
  q: (v, sel, times, values) => v.addQuaternionTrack(sel, times, values),
  tx: (v, sel, times, values) => v.addTranslationTrack(sel, "x", times, values),
  ty: (v, sel, times, values) => v.addTranslationTrack(sel, "y", times, values),
  tz: (v, sel, times, values) => v.addTranslationTrack(sel, "z", times, values),
  rx: (v, sel, times, values) => v.addRotationTrack(sel, "x", times, values),
  ry: (v, sel, times, values) => v.addRotationTrack(sel, "y", times, values),
  rz: (v, sel, times, values) => v.addRotationTrack(sel, "z", times, values),
};

/**
 * Add one track. An unknown action is reported rather than ignored - it means a
 * producer and this table disagree, and silently dropping a track produces an
 * animation that is subtly wrong instead of one that fails.
 */
export function addAnimationTrack(viewer, track, onUnknown) {
  const [selector, action, times, values] = track;
  const add = TRACKS[action];
  if (add == null) {
    if (onUnknown) {
      onUnknown(action, track);
    }
    return false;
  }
  add(viewer, selector, times, values);
  return true;
}

/** The longest time in any track, which is how long the animation runs. */
export function animationDuration(tracks) {
  let duration = 0;
  for (const track of tracks) {
    for (const time of track[2]) {
      if (time > duration) {
        duration = time;
      }
    }
  }
  return duration;
}

/**
 * Load a set of tracks and start the animation.
 *
 * Explode is turned off first: both are transforms on the same objects, and
 * leaving explode on animates an already-displaced model. A speed of zero loads
 * the tracks without starting - that is how a caller scrubs by hand rather than
 * playing.
 */
export function animate(viewer, tracks, speed, onUnknown) {
  viewer.setExplode(false);
  for (const track of tracks) {
    addAnimationTrack(viewer, track, onUnknown);
  }
  const duration = animationDuration(tracks);
  if (speed > 0) {
    viewer.initAnimation(duration, speed);
  }
  return duration;
}
