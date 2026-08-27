import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
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

const shell = (await readFile(resolve(root, 'mobile-shell.html'), 'utf8'))
  .replaceAll('__HV_MOBILE_APP_URL__', suppliedUrl);
await writeFile(resolve(output, 'index.html'), shell, 'utf8');

for (const file of ['offline.html', 'manifest.webmanifest']) {
  await cp(resolve(root, file), resolve(output, file));
}
for (const file of ['mobile-shell.css', 'mobile-shell.js', 'app-icon-192.png', 'app-icon-512.png', 'app-icon-1024.png', 'hv-swim-logo.png']) {
  await cp(resolve(root, 'assets', file), resolve(output, 'assets', file));
}

console.log(`Mobile web shell built for ${suppliedUrl}`);
