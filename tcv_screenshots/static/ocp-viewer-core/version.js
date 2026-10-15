/**
 * The JavaScript half's own version.
 *
 * The Python half sends its version with every model, and page.js compares
 * the two here: major.minor is the contract and must match, the patch level
 * is each half's own. Kept in step with js/package.json by `make bump-js` -
 * a source constant because the packages ship as plain modules, so there is
 * no build step that could inject it.
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

export const VERSION = "1.1.0";
