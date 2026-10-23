// Runs after `vite build`: renders the production dependency licenses into
// dist/THIRD-PARTY-NOTICES.txt. The bundle inlines this code and the minifier
// strips license comments, so this file is what carries the notices the MIT
// and BSD-3-Clause licenses require in "all copies or substantial portions"
// of the software. The API serves it at /THIRD-PARTY-NOTICES.txt.

import { execFileSync } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = fileURLToPath(import.meta.url);
const WEB = dirname(dirname(SCRIPT));
const DIST = resolve(WEB, "dist");

// The full license text for every SPDX id the output may list. An unknown id
// fails the build instead of shipping a notice without its terms: a new
// license in the runtime closure must be added here deliberately.
const LICENSE_TEXTS = {
  MIT: `Copyright (c) the respective package authors listed above.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`,

  "BSD-3-Clause": `Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.`,

  Unlicense: `This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org>`,
};

function packageLine(entry) {
  const versions = (entry.versions ?? []).join(", ");
  let line = [entry.name, versions].filter(Boolean).join(" ");
  if (typeof entry.author === "string" && entry.author.length > 0) {
    line += ` — ${entry.author}`;
  }
  if (typeof entry.homepage === "string" && entry.homepage.length > 0) {
    line += ` (${entry.homepage})`;
  }
  return line;
}

/** Renders pnpm's `licenses list --prod --json` output as the notices file. */
export function formatNotices(licenses) {
  if (typeof licenses !== "object" || licenses === null || Array.isArray(licenses)) {
    throw new Error("expected pnpm's licenses JSON: an object keyed by license id");
  }
  for (const [id, packages] of Object.entries(licenses)) {
    if (!Array.isArray(packages)) {
      throw new Error(`expected the packages of "${id}" to be an array`);
    }
  }
  const ids = Object.keys(licenses).sort();
  const missing = ids.filter((id) => !LICENSE_TEXTS[id]);
  if (missing.length > 0) {
    throw new Error(
      `no embedded license text for ${missing.join(", ")}: add it to LICENSE_TEXTS in web/scripts/generate-notices.mjs`,
    );
  }

  const lines = [
    "Third-party notices for the Narrare web application",
    "===================================================",
    "",
    "Narrare's own code is MIT-licensed; see the LICENSE file of this",
    "distribution. The packages below form the production dependency closure",
    "of the web application and are bundled into its JavaScript assets, where",
    "the minifier removes their license comments. Their licenses require",
    "these notices to accompany every copy. Attribution comes from the",
    "packages' published metadata; the copyright holders are the authors",
    "named below.",
    "",
    "Packages",
    "--------",
    "",
  ];
  for (const id of ids) {
    lines.push(id);
    const packages = [...licenses[id]].sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    for (const entry of packages) {
      lines.push(`  ${packageLine(entry)}`);
    }
    lines.push("");
  }
  lines.push("License texts", "------------", "");
  for (const id of ids) {
    lines.push(id, "", LICENSE_TEXTS[id], "");
  }
  return `${lines.join("\n").trimEnd()}\n`;
}

function main() {
  if (!existsSync(resolve(DIST, "index.html"))) {
    throw new Error(`no build in ${DIST}: run vite build before generating the notices`);
  }
  const raw = execFileSync("pnpm", ["licenses", "list", "--prod", "--json"], {
    cwd: WEB,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });
  const licenses = JSON.parse(raw);
  const packages = Object.values(licenses).reduce((total, group) => total + group.length, 0);
  if (packages === 0) {
    throw new Error("pnpm reported no production packages; refusing to write an empty notice");
  }
  writeFileSync(resolve(DIST, "THIRD-PARTY-NOTICES.txt"), formatNotices(licenses), "utf8");
  console.log(`THIRD-PARTY-NOTICES.txt: ${packages} packages, ${Object.keys(licenses).length} licenses`);
}

if (resolve(process.argv[1] ?? "") === SCRIPT) {
  main();
}
