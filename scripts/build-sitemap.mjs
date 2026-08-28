#!/usr/bin/env node
// Generates sitemap.xml and adds the Sitemap line to robots.txt.
// Usage: node scripts/build-sitemap.mjs https://your-domain.com.au
// The production domain is a business decision, so nothing is guessed here.

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

// Public pages only. Portals and shells are excluded and stay disallowed in robots.txt.
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

const today = new Date().toISOString().slice(0, 10);
const urls = PAGES.map(([page, priority, freq]) => {
  const loc = page === 'index.html' ? `${base}/` : `${base}/${page}`;
  return `  <url>\n    <loc>${loc}</loc>\n    <lastmod>${today}</lastmod>\n    <changefreq>${freq}</changefreq>\n    <priority>${priority}</priority>\n  </url>`;
}).join('\n');

writeFileSync(join(root, 'sitemap.xml'),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`);

const robotsPath = join(root, 'robots.txt');
const robots = readFileSync(robotsPath, 'utf8')
  .replace(/# Sitemap: the production domain[\s\S]*$/m, `Sitemap: ${base}/sitemap.xml\n`)
  .replace(/^Sitemap: .*$/m, `Sitemap: ${base}/sitemap.xml`);
writeFileSync(robotsPath, robots);

console.log(`sitemap.xml written with ${PAGES.length} pages, robots.txt updated for ${base}`);
