#!/usr/bin/env node
// Static consistency checks for the site. No build step, no dependencies:
//
//     node scripts/check-site.mjs
//
// Every check here exists because the matching fault was actually found in this repo:
// a precache list that had drifted, a stylesheet class that was never written, a script
// pointing at elements that no longer existed, and an asset version bumped in the pages
// but not in the service worker. Run it before you commit.

import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (file) => readFileSync(join(root, file), 'utf8');
const pages = readdirSync(root).filter((f) => f.endsWith('.html'));
const scripts = readdirSync(join(root, 'assets')).filter((f) => f.endsWith('.js'));
const styles = readdirSync(join(root, 'assets')).filter((f) => f.endsWith('.css'));

const problems = [];
const fail = (check, detail) => problems.push(`${check}: ${detail}`);
const allHtml = pages.map(read).join('\n');
const allCss = styles.map((f) => read(join('assets', f))).join('\n');

// 1. Every local href/src in every page resolves to a real file.
for (const page of pages) {
  for (const [, raw] of read(page).matchAll(/(?:href|src)="([^"]*)"/g)) {
    if (!raw || raw.startsWith('#')) continue;
    if (/^[a-z][a-z0-9+.-]*:/i.test(raw) || raw.startsWith('//')) continue;   // tel:, mailto:, https:, //cdn
    const clean = raw.replace(/^\.?\//, '').split(/[?#]/)[0];
    if (!clean) continue;
    if (!existsSync(join(root, clean))) fail('broken link', `${page} -> ${raw}`);
  }
}

// 2. Every service-worker precache entry exists, and its ?v= matches what the pages request.
const sw = read('service-worker.js');
const shell = [...(sw.match(/const SHELL\s*=\s*\[([\s\S]*?)\];/)?.[1] || '').matchAll(/'([^']+)'/g)].map((m) => m[1]);
if (!shell.length) fail('service worker', 'could not read the SHELL list');
for (const entry of shell) {
  const [path, query] = entry.replace(/^\.\//, '').split('?');
  if (path && path !== '/' && !existsSync(join(root, path))) {
    fail('precache', `${entry} does not exist — cache.addAll will reject and the PWA will never install`);
  }
  if (query) {
    const pageVersion = allHtml.match(new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\?(v=[\\d.]+)'))?.[1];
    if (pageVersion && pageVersion !== query) {
      fail('version drift', `${path} is ${query} in the service worker but ${pageVersion} in the pages`);
    }
  }
}

// 3. Every class used in markup or scripts has a rule somewhere.
const definedClasses = new Set([...allCss.matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]));
const behavioural = new Set(['location-admin-form']); // matched by JS, deliberately unstyled
for (const file of [...pages, ...scripts.map((f) => join('assets', f))]) {
  const source = read(file);
  for (const [, list] of source.matchAll(/class="([^"${}]+)"/g)) {
    for (const name of list.split(/\s+/)) {
      if (name && !definedClasses.has(name) && !behavioural.has(name)) {
        fail('unstyled class', `.${name} used in ${file} has no rule in any stylesheet`);
      }
    }
  }
}

// 4. No script reaches for an element id that exists on no page.
for (const file of scripts) {
  const source = read(join('assets', file));
  for (const [, id] of source.matchAll(/getElementById\(['"]([^'"]+)['"]\)/g)) {
    if (!allHtml.includes(`id="${id}"`) && !source.includes(`id="${id}"`)) {
      fail('dead reference', `assets/${file} looks for #${id}, which no page contains`);
    }
  }
}

// 5. Every manifest icon exists.
const manifest = JSON.parse(read('manifest.webmanifest'));
for (const icon of manifest.icons || []) {
  const src = icon.src.replace(/^\.?\//, '');
  if (!existsSync(join(root, src))) fail('manifest', `icon ${icon.src} is missing`);
}

if (problems.length) {
  console.error(`${problems.length} problem${problems.length === 1 ? '' : 's'} found:\n`);
  for (const problem of problems) console.error(`  ${problem}`);
  process.exit(1);
}
console.log(`All checks passed — ${pages.length} pages, ${shell.length} precached files, ${scripts.length} scripts.`);
