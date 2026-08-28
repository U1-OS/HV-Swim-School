import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, resolve, posix } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const output = resolve(root, 'www');
const suppliedUrl = (process.env.HV_MOBILE_APP_URL || '').trim().replace(/\/$/, '');

if (!/^https:\/\//.test(suppliedUrl) && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(suppliedUrl)) {
  console.error('Set HV_MOBILE_APP_URL to the HTTPS production app origin. Localhost is accepted only for simulator testing.');
  process.exit(1);
}

await rm(output, { recursive: true, force: true });
await mkdir(resolve(output, 'assets'), { recursive: true });

// The shell becomes the bundle's index.html.
const shell = (await readFile(resolve(root, 'mobile-shell.html'), 'utf8'))
  .replaceAll('__HV_MOBILE_APP_URL__', suppliedUrl);
await writeFile(resolve(output, 'index.html'), shell, 'utf8');

const PAGES = ['mobile-shell.html', 'offline.html'];
// offline.html points at app.html, which is right on the web but not part of this
// bundle — inside the packaged app the shell is the entry point. Rewrite it on the way in
// so the offline screen's button does not lead nowhere.
for (const file of PAGES.slice(1)) {
  const page = (await readFile(resolve(root, file), 'utf8')).replaceAll('href="app.html"', 'href="./"');
  await writeFile(resolve(output, file), page, 'utf8');
}

// Work out what the bundle actually needs rather than keeping a hand-written list.
// That list had already drifted: offline.html's stylesheet was missing, so the offline
// screen inside the app rendered unstyled, and two icons added later were never copied.
const needed = new Set();
for (const page of PAGES) {
  const html = page === 'mobile-shell.html' ? shell : await readFile(resolve(root, page), 'utf8');
  for (const match of html.matchAll(/(?:href|src)="([^"#?:]+)/g)) {
    const target = match[1].replace(/^\.\//, '');
    if (!target || /^(https?:|data:|mailto:|tel:)/.test(target)) continue;
    needed.add(target.split('?')[0]);
  }
}

// Icons come from the manifest, so adding one there is enough to ship it.
const manifest = JSON.parse(await readFile(resolve(root, 'manifest.webmanifest'), 'utf8'));
for (const icon of manifest.icons || []) needed.add(icon.src.replace(/^\.\//, ''));

// Inside the packaged app the shell is the entry point; app.html is not part of the bundle.
manifest.start_url = './';
manifest.scope = './';
await writeFile(resolve(output, 'manifest.webmanifest'), JSON.stringify(manifest, null, 2) + '\n', 'utf8');
needed.delete('manifest.webmanifest');
for (const page of PAGES) needed.delete(page);
needed.delete('app.html');

const copied = [];
const skipped = [];
for (const file of [...needed].sort()) {
  const source = resolve(root, file);
  if (!existsSync(source)) { skipped.push(file); continue; }
  await mkdir(dirname(resolve(output, file)), { recursive: true });
  await cp(source, resolve(output, file));
  copied.push(file);
}

if (skipped.length) {
  console.error(`Referenced but missing from the repo: ${skipped.join(', ')}`);
  process.exit(1);
}

console.log(`Mobile web shell built for ${suppliedUrl}`);
console.log(`Copied ${copied.length} files: ${copied.join(', ')}`);
