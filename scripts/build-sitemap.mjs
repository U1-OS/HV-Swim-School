#!/usr/bin/env node
// Applies the production domain across the site: writes sitemap.xml, fills in the
// Sitemap line in robots.txt, and makes each public page's canonical URL and social
// share image absolute. Facebook and other scrapers will not resolve a relative
// og:image, so this step is required before links share properly.
//
// Usage: node scripts/build-sitemap.mjs https://your-domain.com.au
//
// The production domain is a business decision, so nothing here is guessed. Run it
// again any time the domain changes; it is safe to run repeatedly.

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

// Public pages only. Portals and shells stay out of the sitemap and disallowed in robots.txt.
const PAGES = [
  ['index.html', '1.0', 'weekly'],
  ['programs.html', '0.9', 'weekly'],
  ['enquire.html', '0.9', 'monthly'],
  ['locations.html', '0.8', 'weekly'],
  ['about.html', '0.7', 'monthly'],
  ['shop.html', '0.7', 'weekly'],
  ['app.html', '0.5', 'monthly'],
  ['privacy.html', '0.3', 'yearly'],
  ['terms.html', '0.3', 'yearly'],
  ['photo-consent.html', '0.3', 'yearly'],
];

const base = (process.argv[2] || '').replace(/\/+$/, '');
if (!/^https?:\/\/.+/.test(base)) {
  console.error('Usage: node scripts/build-sitemap.mjs https://your-domain.com.au');
  process.exit(1);
}

const urlFor = (page) => (page === 'index.html' ? `${base}/` : `${base}/${page}`);
const today = new Date().toISOString().slice(0, 10);

// 1. sitemap.xml
const urls = PAGES.map(([page, priority, freq]) =>
  `  <url>\n    <loc>${urlFor(page)}</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>${freq}</changefreq>\n    <priority>${priority}</priority>\n  </url>`
).join('\n');
writeFileSync(join(root, 'sitemap.xml'),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`);

// 2. robots.txt
const robotsPath = join(root, 'robots.txt');
writeFileSync(robotsPath, readFileSync(robotsPath, 'utf8')
  .replace(/# Sitemap: the production domain[\s\S]*$/m, `Sitemap: ${base}/sitemap.xml\n`)
  .replace(/^Sitemap: .*$/m, `Sitemap: ${base}/sitemap.xml`));

// 3. Absolute canonical, og:url and share image on every public page.
let touched = 0;
for (const [page] of PAGES) {
  const path = join(root, page);
  let html = readFileSync(path, 'utf8');
  const absoluteImage = `${base}/assets/og-share.jpg`;

  html = html
    .replace(/(<meta property="og:image" content=")[^"]*(">)/, `$1${absoluteImage}$2`)
    .replace(/(<meta name="twitter:image" content=")[^"]*(">)/, `$1${absoluteImage}$2`);

  if (/<meta property="og:url"/.test(html)) {
    html = html.replace(/(<meta property="og:url" content=")[^"]*(">)/, `$1${urlFor(page)}$2`);
  } else {
    html = html.replace(/(<meta property="og:type"[^>]*>)/, `$1\n  <meta property="og:url" content="${urlFor(page)}">`);
  }

  if (/<link rel="canonical"/.test(html)) {
    html = html.replace(/(<link rel="canonical" href=")[^"]*(">)/, `$1${urlFor(page)}$2`);
  } else {
    html = html.replace(/(<title>)/, `<link rel="canonical" href="${urlFor(page)}">\n  $1`);
  }

  writeFileSync(path, html);
  touched += 1;
}

console.log(`sitemap.xml written with ${PAGES.length} pages`);
console.log(`robots.txt updated for ${base}`);
console.log(`canonical, og:url and absolute share image set on ${touched} pages`);
