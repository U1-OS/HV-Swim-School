/* Public controller. No trackers, background geolocation or embedded social feeds. */
(() => {
  'use strict';
  const root = document.documentElement;
  root.classList.add('js');
  const q = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const errorMessage = (detail, status) => Array.isArray(detail)
    ? 'Please check the information entered and try again.'
    : typeof detail === 'string' ? detail : `We could not complete that request (${status}). Please try again.`;
  async function requestJSON(url, options = {}, timeout = 8000) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (options.signal?.aborted) abort();
    else options.signal?.addEventListener('abort', abort, {once:true});
    const timer = setTimeout(abort, timeout);
    try {
      const response = await fetch(url, {...options, signal:controller.signal});
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(errorMessage(payload?.detail, response.status));
      if (payload === null) throw new Error('The service returned an unreadable response. Please try again.');
      return payload;
    } finally { clearTimeout(timer); options.signal?.removeEventListener('abort', abort); }
  }
  const pending = new Map();
  function fetchJSON(url, options = {}, timeout = 8000) {
    if ((options.method || 'GET').toUpperCase() !== 'GET' || options.signal) return requestJSON(url, options, timeout);
    if (!pending.has(url)) pending.set(url, requestJSON(url, options, timeout).finally(() => setTimeout(() => pending.delete(url), 1000)));
    return pending.get(url);
  }
  function formatClassTime(value) {
    const match = /^(\d{1,2}):(\d{2})$/.exec(String(value || ''));
    if (!match || +match[1] > 23 || +match[2] > 59) return String(value || '');
    return `${+match[1] % 12 || 12}:${match[2]} ${+match[1] >= 12 ? 'pm' : 'am'}`;
  }
  function formatDateTime(value) {
    const date = new Date(value);
    return !value || Number.isNaN(+date) ? 'Update time unavailable' : new Intl.DateTimeFormat('en-AU', {day:'numeric',month:'short',hour:'numeric',minute:'2-digit',timeZone:'Australia/Melbourne'}).format(date);
  }
  window.HVSwim = {fetchJSON, formatClassTime, formatDateTime, errorMessage};

  const menu = q('.nav-links');
  const toggle = q('.menu-toggle');
  const narrow = matchMedia('(max-width:860px)');
  function setMenu(open, focus = false) {
    menu?.classList.toggle('open', open && narrow.matches);
    toggle?.setAttribute('aria-expanded', String(open && narrow.matches));
    if (toggle) toggle.textContent = open && narrow.matches ? 'Close' : 'Menu';
    if (focus) toggle?.focus();
  }
  toggle?.addEventListener('click', () => setMenu(toggle.getAttribute('aria-expanded') !== 'true'));
  menu?.addEventListener('click', event => { if (event.target.closest('a')) setMenu(false); });
  document.addEventListener('keydown', event => { if(event.key === 'Escape' && toggle?.getAttribute('aria-expanded') === 'true') setMenu(false,true); });
  narrow.addEventListener('change', () => setMenu(false));

  const reduced = matchMedia('(prefers-reduced-motion:reduce)');
  let motionChoice = null;
  try { motionChoice = localStorage.getItem('hv-swim-motion'); } catch (_) {}
  function updateMotion() {
    const off = reduced.matches || motionChoice === 'off';
    root.dataset.motion = off ? 'off' : 'on';
    root.dataset.pageHidden = String(document.hidden);
    document.querySelectorAll('[data-motion-toggle]').forEach(button => {
      button.textContent = reduced.matches ? 'Reduced motion enabled' : off ? 'Resume motion' : 'Pause motion';
      button.setAttribute('aria-pressed',String(off));
      button.disabled = reduced.matches;
    });
  }
  document.querySelectorAll('[data-motion-toggle]').forEach(button => button.addEventListener('click', () => {
    motionChoice = root.dataset.motion === 'off' ? 'on' : 'off';
    try { localStorage.setItem('hv-swim-motion',motionChoice); } catch (_) {}
    updateMotion();
  }));
  reduced.addEventListener('change',updateMotion);
  document.addEventListener('visibilitychange',updateMotion);
  updateMotion();
  q('[data-clear-preferences]')?.addEventListener('click', () => {
    let cleared = true;
    try { ['hv-swim-motion','hv-swim-v4-weather-cache','hv-swim-last-device-alert','hv-swim-shopify-cart-v1'].forEach(key => localStorage.removeItem(key)); sessionStorage.removeItem('hv-swim-enquiry-preferences-v1'); } catch (_) { cleared = false; }
    motionChoice = null; updateMotion();
    const status = q('[data-preferences-status]');
    if(status) status.textContent = cleared ? 'Saved website preferences cleared. Account and offline files are unchanged.' : 'Some storage is blocked by your browser. Use browser site-data settings to clear it.';
  });
  document.querySelectorAll('[data-year]').forEach(node => { node.textContent = new Date().getFullYear(); });

  if (['127.0.0.1','localhost','[::1]'].includes(location.hostname)) {
    const notice = q('[data-preview-notice]');
    if(notice) notice.hidden = false;
  }
  async function hydrateSettings() {
    try {
      const payload = await fetchJSON('/api/public/site-settings');
      const preview = payload.mode === 'preview';
      root.dataset.siteMode = preview ? 'preview' : 'production';
      const notice = q('[data-preview-notice]');
      if (notice) notice.hidden = !preview;
      const settings = payload.settings || {};
      document.querySelectorAll('[data-site-field]').forEach(node => {
        const value = settings[node.dataset.siteField];
        if (typeof value === 'string' && value.trim()) node.textContent = value;
      });
      const announcement = q('.site-announcement');
      if (announcement && settings.announcement_enabled && settings.announcement_text) {
        q('[data-announcement-copy]').textContent = settings.announcement_text;
        announcement.hidden = false;
      }
    } catch (_) { /* Keep factual static copy. Unverified features stay hidden. */ }
  }
  hydrateSettings();

  let alertTimer;
  async function hydrateAlerts() {
    clearTimeout(alertTimer);
    if (document.hidden) return;
    const mount = q('.public-alerts');
    if (!mount) return;
    try {
      const payload = await fetchJSON('/api/public/alerts', {cache:'no-store'});
      const alerts = Array.isArray(payload.alerts) ? payload.alerts : [];
      mount.innerHTML = alerts.slice(0,8).map(alert => `<div class="container public-alert"><strong>${esc(alert.title)}</strong><p>${esc(alert.message)}</p><small>${esc(alert.location_name || "All locations")} · ${esc(formatDateTime(alert.published_at))}</small></div>`).join('');
      mount.hidden = alerts.length === 0;
    } catch (_) { mount.hidden = true; mount.replaceChildren(); }
    alertTimer = setTimeout(hydrateAlerts,60000);
  }
  document.addEventListener('visibilitychange',hydrateAlerts);
  hydrateAlerts();

  const finite = value => value !== null && value !== '' && value !== undefined && Number.isFinite(Number(value));
  const fresh = (value, maxAge) => {const stamp = Date.parse(value); const age = Date.now() - stamp; return Number.isFinite(stamp) && age >= -60000 && age < maxAge;};
  const weatherLabel = code => ({0:'Clear',1:'Mostly clear',2:'Partly cloudy',3:'Overcast',45:'Foggy',48:'Foggy',51:'Light drizzle',53:'Drizzle',55:'Heavy drizzle',61:'Light rain',63:'Rain',65:'Heavy rain',80:'Rain showers',81:'Rain showers',82:'Heavy showers',95:'Thunderstorm'})[code] || 'Local conditions';
  function text(selector, value) { document.querySelectorAll(selector).forEach(node => { node.textContent = value; }); }
  let conditionsTimer;
  let conditionsLoading = false;
  async function hydrateConditions() {
    clearTimeout(conditionsTimer);
    if(document.hidden || conditionsLoading) return;
    if (!q('[data-weather-value]') && !q('[data-pool-value]') && !q('[data-venue-status]')) return;
    conditionsLoading = true;
    const [weather, venues] = await Promise.allSettled([fetchJSON('/api/public/weather'),fetchJSON('/api/public/locations')]);
    if (weather.status === 'fulfilled') {
      const data = weather.value;
      const current = data.current || {};
      const valid = !data.stale && fresh(data.observed_at, 2*60*60*1000) && finite(current.temperature_2m);
      text('[data-weather-value]',valid ? `${Number(current.temperature_2m).toFixed(1)}°C` : 'Update needed');
      text('[data-weather-note]',valid ? `${weatherLabel(current.weather_code)} · ${data.cached ? 'Cached update' : 'Updated'} ${formatDateTime(data.observed_at)}. Air temperature.` : 'A current weather update is unavailable. Check conditions before travelling.');
    } else { text('[data-weather-value]','Unavailable'); text('[data-weather-note]','Weather is temporarily unavailable. Pool details are shown separately.'); }
    if (venues.status === 'fulfilled') {
      const locations = venues.value.locations || [];
      locations.forEach(venue => {
        if (!['wood-street','bendigo-east'].includes(venue.slug)) return;
        text(`[data-venue-status="${venue.slug}"]`,venue.public_status || 'Please confirm with the team');
        const reading = venue.latest_reading;
        const valid = reading && !venue.reading_stale && finite(reading.temperature) && fresh(reading.created_at,24*60*60*1000);
        text(`[data-pool-value="${venue.slug}"]`,valid ? `${Number(reading.temperature).toFixed(1)}°C` : 'Awaiting a reading');
        text(`[data-pool-note="${venue.slug}"]`,valid ? `Water temperature · staff reading ${formatDateTime(reading.created_at)}.` : 'No current staff water-temperature reading has been published.');
      });
    } else { text('[data-venue-status]','Contact us for current status');text('[data-pool-value]','Unavailable');text('[data-pool-note]','Pool updates are temporarily unavailable. Please contact the team.'); }
    conditionsLoading = false;
    if(!document.hidden) conditionsTimer = setTimeout(hydrateConditions,60000);
  }
  hydrateConditions();
  document.addEventListener('visibilitychange', hydrateConditions);

  // Only public static assets are precached; account APIs remain network-only in the worker.
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
    window.addEventListener('load',() => {navigator.serviceWorker.register('service-worker.js').catch(() => {});});
  }
})();
