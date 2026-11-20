/**
 * A host's viewer settings, as the config an open viewer applies.
 *
 * A host's settings dialog - VS Code's, build123d Studio's - stores the viewer
 * settings under their Python names, and Python translates them when a model is
 * shown. A setting changed while a viewer is open has to reach that viewer from
 * the host: once a model is shown, the viewer's reported state wins over the
 * stored settings (`combined_config`), so without this the change would wait
 * for the viewer to be reopened. The translation is Python's, as data generated
 * into `keys.js`.
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

import { LIVE_SETTINGS, RENDERER_NAMES, VALUE_NAMES } from "./keys.js";

/**
 * Translate settings under their Python names into a config for `applyConfig`.
 *
 * Only the settings an open viewer reports and can apply (`LIVE_SETTINGS`): the
 * old value of any other setting does not win at the next show, so it needs no
 * push, and some must not be applied now - `reset_camera` would move the camera.
 *
 * @param settings  {python_name: value}, the settings that changed
 * @returns `{config, skipped}` - `config` under the renderer's names and values,
 *          `skipped` the names left to the next show and values that name nothing
 */
export function settingsToConfig(settings) {
  const config = {};
  const skipped = [];
  for (const [key, value] of Object.entries(settings)) {
    if (!LIVE_SETTINGS.includes(key)) {
      skipped.push(key);
      continue;
    }
    const values = VALUE_NAMES[key];
    if (values === undefined) {
      config[RENDERER_NAMES[key]] = value;
    } else if (Object.hasOwn(values, value)) {
      config[RENDERER_NAMES[key]] = values[value];
    } else {
      skipped.push(key);
    }
  }
  return { config, skipped };
}
