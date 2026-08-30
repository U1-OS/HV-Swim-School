(() => {
  'use strict';

  const WEATHER_KEY = 'hv-swim-v4-weather-cache';
  const DAY = 24 * 60 * 60 * 1000;
  const iconNames = {'♡':'heart','≈':'waves','✓':'check','↗':'arrow-up-right','→':'arrow-right','◇':'settings','°C':'thermometer','☀':'sun','⌂':'home','◎':'status','⌕':'search'};
  const iconSvg = name => `<svg class="ui-icon" aria-hidden="true"><use href="assets/icons.svg#${name}"></use></svg>`;
  const upgradeLegacyIcons = (root=document) => {
    const candidates=[];
    if(root instanceof Element)candidates.push(root);
    candidates.push(...root.querySelectorAll('[aria-hidden="true"],.icon-box,.integration-logo,.approach-card-top>span'));
    candidates.forEach(element=>{
      if(element.querySelector?.('svg'))return;
      const value=element.textContent.trim();
      const name=value==='◇'&&element.closest('[data-cart-open]')?'bag':iconNames[value];
      if(name)element.innerHTML=iconSvg(name);
    });
  };
  const conditions = {
    'wood-street': {
      temperature: null,
      status: 'changed',
      statusText: 'Staff check required',
      verified: false,
      staff: 'Awaiting staff update',
      updatedAt: null
    },
    'bendigo-east': {
      temperature: null,
      status: 'closed',
      statusText: 'Closed for winter',
      verified: true,
      staff: 'City of Greater Bendigo notice',
      updatedAt: '2026-05-10T17:00:00+10:00'
    }
  };

  function formatTime(date) { return new Intl.DateTimeFormat('en-AU', { hour:'numeric', minute:'2-digit', timeZone:'Australia/Melbourne' }).format(date); }
  function formatClassTime(value) {
    const match = String(value || '').match(/^(\d{1,2}):(\d{2})/);
    if (!match) return String(value || '');
    const hour = Number(match[1]);
    const minute = Number(match[2]);
    if (!Number.isInteger(hour) || hour > 23 || !Number.isInteger(minute) || minute > 59) return String(value || '');
    return `${hour % 12 || 12}:${match[2]} ${hour >= 12 ? 'pm' : 'am'}`;
  }
  function formatDateTime(value) {
    if (!value) return 'Staff update required';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Update time unavailable';
    return new Intl.DateTimeFormat('en-AU', { day:'numeric', month:'short', hour:'numeric', minute:'2-digit', timeZone:'Australia/Melbourne' }).format(date);
  }
  const requestCache = new Map();
  async function requestJSON(url, options = {}, timeout = 8000) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { ...options, signal:controller.signal });
      let payload = null;
      try { payload = await response.json(); } catch (_) {}
      if (!response.ok) throw new Error(payload?.detail || `Request failed (${response.status})`);
      return payload;
    } finally {
      window.clearTimeout(timer);
    }
  }
  function fetchJSON(url, options = {}, timeout = 8000) {
    const cacheable = String(options.method || 'GET').toUpperCase() === 'GET' && !options.signal;
    if (!cacheable) return requestJSON(url, options, timeout);
    if (requestCache.has(url)) return requestCache.get(url);
    const pending = requestJSON(url, options, timeout).finally(() => window.setTimeout(() => requestCache.delete(url), 1000));
    requestCache.set(url, pending);
    return pending;
  }
  window.HVSwim = Object.assign(window.HVSwim || {}, { fetchJSON, formatClassTime, formatDateTime });

  const escapePublic = value => String(value ?? '').replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));
  async function hydrateAssociationBadges() {
    const featureNodes=[...document.querySelectorAll('[data-public-feature="association_badges"]')];
    featureNodes.forEach(node=>{node.hidden=true;});
    try {
      const payload=await fetchJSON('/api/public/association-badges',{headers:{Accept:'application/json'}});
      if(!payload.published||!Array.isArray(payload.badges)||payload.badges.length!==3)return;
      const cards=payload.badges.map(badge=>`<a class="credential-card" href="${escapePublic(badge.directory_url)}" target="_blank" rel="noopener"><span class="directory-card-mark issued" aria-hidden="true"><img src="${escapePublic(badge.artwork_url)}" alt=""></span><span><strong>${escapePublic(badge.display_name)}</strong><small>View the current public organisation record</small><em class="credential-state listed">Verified through ${escapePublic(new Intl.DateTimeFormat('en-AU',{day:'numeric',month:'short',year:'numeric'}).format(new Date(`${badge.valid_until}T00:00:00`)))}</em></span></a>`).join('');
      const publicGrid=document.getElementById('association-badge-list');
      if(publicGrid)publicGrid.innerHTML=cards;
      const footerLinks=document.querySelector('.footer-association-links');
      if(footerLinks)footerLinks.innerHTML=payload.badges.map(badge=>`<a href="${escapePublic(badge.directory_url)}" target="_blank" rel="noopener"><img src="${escapePublic(badge.artwork_url)}" alt="${escapePublic(badge.display_name)}"><span>View current record</span><em>Verified to ${escapePublic(badge.valid_until)}</em></a>`).join('');
      featureNodes.forEach(node=>{node.hidden=false;});
    } catch (_) {
      featureNodes.forEach(node=>{node.hidden=true;});
    }
  }

  // Public modules fail closed. Preview-only and not-yet-approved brand/commerce
  // sections remain absent if the server cannot confirm the current environment.
  async function hydratePublicMode() {
    if (!/^https?:$/.test(location.protocol)) return;
    try {
      const payload = await fetchJSON('/api/public/site-settings', { headers:{ Accept:'application/json' } });
      const mode = payload.mode === 'preview' ? 'preview' : 'production';
      document.documentElement.dataset.siteMode = mode;
      document.querySelectorAll('[data-preview-only]').forEach(element => { element.hidden = mode !== 'preview'; });
      document.querySelectorAll('[data-public-feature]').forEach(element => {
        element.hidden = element.dataset.publicFeature === 'association_badges' || payload.features?.[element.dataset.publicFeature] !== true;
      });
      if(payload.features?.association_badges===true)await hydrateAssociationBadges();
      const primaryLabel = String(payload.settings?.primary_cta || 'Find the right lesson').trim();
      document.querySelectorAll('[data-primary-cta-label]').forEach(element => { element.textContent = primaryLabel; });
    } catch (_) {
      document.documentElement.dataset.siteMode = 'production';
    }
  }
  hydratePublicMode();
  function showToast(message) {
    const toast = document.querySelector('.toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => toast.classList.remove('show'), 4200);
  }

  // Shared navigation and presentation behaviour.
  const menuToggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.nav-links');
  const mobileNav = window.matchMedia('(max-width: 980px)');
  const syncBodyLock = () => {
    const overlayOpen = Boolean(nav?.classList.contains('open') || document.querySelector('.cart-drawer.open'));
    document.body.classList.toggle('no-scroll', overlayOpen);
  };
  const setMenu = open => {
    const shouldOpen = Boolean(open && mobileNav.matches);
    nav?.classList.toggle('open', shouldOpen);
    menuToggle?.setAttribute('aria-expanded', String(shouldOpen));
    menuToggle?.setAttribute('aria-label', shouldOpen ? 'Close menu' : 'Open menu');
    if (nav) {
      nav.inert = mobileNav.matches && !shouldOpen;
      if (mobileNav.matches && !shouldOpen) nav.setAttribute('aria-hidden', 'true');
      else nav.removeAttribute('aria-hidden');
    }
    syncBodyLock();
  };
  const closeMenu = ({ refocus = false } = {}) => {
    const wasOpen = Boolean(nav?.classList.contains('open'));
    setMenu(false);
    // Send focus back to the control that opened it, or it lands at the top of the page.
    if (wasOpen && refocus) menuToggle?.focus();
  };
  menuToggle?.addEventListener('click', () => {
    const open = !nav?.classList.contains('open');
    setMenu(open);
    if (open) nav?.querySelector('a')?.focus();
  });
  nav?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => closeMenu()));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeMenu({ refocus: true });
    if (event.key !== 'Tab' || !nav?.classList.contains('open')) return;
    // While the overlay menu covers the page, keep Tab inside it.
    // Document order matters: the toggle sits after the links in the markup, so building
    // the list any other way leaves a gap where Tab escapes the overlay.
    const stops = [...document.querySelectorAll('.nav-links a, .menu-toggle')]
      .filter(el => el.offsetParent !== null);
    if (!stops.length) return;
    const first = stops[0];
    const last = stops[stops.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  const handleNavBreakpoint = () => closeMenu();
  if (mobileNav.addEventListener) mobileNav.addEventListener('change', handleNavBreakpoint);
  else mobileNav.addListener(handleNavBreakpoint);
  setMenu(false);
  document.querySelectorAll('[data-year]').forEach(el => el.textContent = String(new Date().getFullYear()));
  document.querySelectorAll('.grid-2,.grid-3,.grid-4,.journey-grid,.availability-grid').forEach(grid => {
    [...grid.children].forEach((item,index) => item.style.setProperty('--reveal-delay',`${Math.min(index * 70, 280)}ms`));
  });
  const header = document.querySelector('.site-header');
  const updateHeader = () => header?.classList.toggle('scrolled', window.scrollY > 24);
  updateHeader(); window.addEventListener('scroll', updateHeader, { passive:true });

  // Verified association artwork is shown consistently at the bottom of public pages.
  // The strip begins empty and stays hidden unless the server returns all three current,
  // integrity-checked records through the explicit publication gate.
  const footer = document.querySelector('.site-footer');
  if (footer && !footer.querySelector('.footer-business-identity')) {
    const identity = document.createElement('p');
    identity.className = 'container footer-business-identity';
    identity.textContent = 'HVS BENDIGO PTY LTD · ABN 46 687 937 962 · 76 Wood Street, California Gully VIC 3556';
    const bottom = footer.querySelector('.footer-bottom');
    if (bottom) footer.insertBefore(identity, bottom); else footer.append(identity);
  }
  if (footer && !footer.querySelector('.footer-association-strip')) {
    const strip = document.createElement('div');
    strip.className = 'container footer-association-strip';
    strip.dataset.publicFeature = 'association_badges';
    strip.hidden = true;
    strip.setAttribute('aria-label', 'HV Swim aquatic industry directory links');
    strip.innerHTML = `<div class="footer-association-intro"><span>Current credentials</span><strong>Check HV Swim at the source.</strong><small>Organisation-issued marks with management-verified evidence and expiry dates.</small></div><div class="footer-association-links"></div>`;
    const footerBottom = footer.querySelector('.footer-bottom');
    if (footerBottom) footer.insertBefore(strip, footerBottom);
    else footer.append(strip);
  }

  // Urgent website/app alerts. Open pages receive a new closure or changed-condition
  // notice within the server-provided refresh window. Native/web push while the app is
  // closed remains a separate production provider boundary.
  const ALERT_STORAGE_KEY = 'hv-swim-last-device-alert';
  const escapeAlert = value => String(value ?? '').replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));
  const severityLabels = { closure:'Pool closure', change:'Changed conditions', reopening:'Reopened', information:'Important update' };
  const publicAlertRoot = document.createElement('aside');
  publicAlertRoot.className = 'public-alert-stack';
  publicAlertRoot.setAttribute('aria-label', 'Important HV Swim updates');
  publicAlertRoot.setAttribute('aria-live', 'assertive');
  publicAlertRoot.hidden = true;
  const alertAnchor = document.querySelector('.shop-launch-bar') || header;
  if (alertAnchor) alertAnchor.insertAdjacentElement('afterend', publicAlertRoot);
  else document.body.prepend(publicAlertRoot);

  const deviceAlertAvailable = () => 'Notification' in window && window.isSecureContext && 'serviceWorker' in navigator;
  async function showDeviceAlert(alert) {
    if (!deviceAlertAvailable() || Notification.permission !== 'granted') return;
    let lastShown = '';
    try { lastShown = localStorage.getItem(ALERT_STORAGE_KEY) || ''; } catch (_) {}
    if (lastShown === String(alert.id)) return;
    try {
      const registration = await navigator.serviceWorker.ready;
      await registration.showNotification(alert.title, {
        body:alert.message,
        tag:`hv-swim-alert-${alert.id}`,
        renotify:true,
        icon:'assets/app-icon-v3-192.png',
        badge:'assets/app-icon-v3-64.png',
        data:{ url:'locations.html' }
      });
      try { localStorage.setItem(ALERT_STORAGE_KEY, String(alert.id)); } catch (_) {}
    } catch (_) {}
  }

  function renderPublicAlerts(alerts) {
    const active = Array.isArray(alerts) ? alerts.slice(0, 3) : [];
    publicAlertRoot.hidden = !active.length;
    publicAlertRoot.innerHTML = active.map((alert,index) => {
      const severity = Object.hasOwn(severityLabels, alert.severity) ? alert.severity : 'information';
      const locationName = alert.location_name || 'All HV Swim locations';
      const published = alert.published_at ? formatDateTime(alert.published_at) : 'Published now';
      const deviceButton = index === 0 && deviceAlertAvailable() && Notification.permission !== 'denied'
        ? `<button type="button" data-enable-device-alerts>${Notification.permission === 'granted' ? 'Device alerts enabled' : 'Enable device alerts'}</button>` : '';
      return `<article class="public-alert ${severity}" data-alert-id="${escapeAlert(alert.id)}"><div class="public-alert-icon" aria-hidden="true">${severity === 'closure' ? '!' : severity === 'reopening' ? '✓' : 'i'}</div><div class="public-alert-copy"><span>${escapeAlert(severityLabels[severity])} · ${escapeAlert(locationName)}</span><strong>${escapeAlert(alert.title)}</strong><p>${escapeAlert(alert.message)}</p><small>${escapeAlert(published)} · live website and connected-app notice</small></div><div class="public-alert-actions"><a href="locations.html">View conditions</a>${deviceButton}</div></article>`;
    }).join('');
    if (active[0]) showDeviceAlert(active[0]);
  }

  async function hydratePublicAlerts() {
    if (!/^https?:$/.test(location.protocol)) return;
    try {
      const payload = await requestJSON('/api/public/alerts', { headers:{ Accept:'application/json' }, cache:'no-store' }, 5000);
      renderPublicAlerts(payload.alerts);
    } catch (_) {
      // A missing connection must never leave an old closure looking current.
      publicAlertRoot.hidden = true;
      publicAlertRoot.replaceChildren();
    }
  }
  publicAlertRoot.addEventListener('click', async event => {
    const button = event.target.closest('[data-enable-device-alerts]');
    if (!button || !deviceAlertAvailable()) return;
    if (Notification.permission === 'default') await Notification.requestPermission();
    button.textContent = Notification.permission === 'granted' ? 'Device alerts enabled' : 'Alerts blocked in browser';
    if (Notification.permission === 'granted') hydratePublicAlerts();
  });
  if (/^https?:$/.test(location.protocol)) {
    hydratePublicAlerts();
    window.setInterval(() => { if (!document.hidden) hydratePublicAlerts(); }, 15000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) hydratePublicAlerts(); });
  }
  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.add('visible'); observer.unobserve(entry.target); }
  }), { threshold:0, rootMargin:'0px 0px -8% 0px' }) : null;
  document.querySelectorAll('.reveal').forEach(el => observer ? observer.observe(el) : el.classList.add('visible'));

  // Keep the mobile quick action out of the opening hero, then reveal it when it is useful.
  // The shop owns its saved-items bar separately, so it is intentionally excluded here.
  const mobileBookBar = document.querySelector('.mobile-book-bar:not(.shop-mobile-bar)');
  const openingHero = document.querySelector('.hero,.programs-hero,.enrolment-hero,.about-hero,.app-hero');
  if (mobileBookBar) {
    mobileBookBar.classList.add('is-managed');
    if (openingHero && 'IntersectionObserver' in window) {
      const quickActionObserver = new IntersectionObserver(([entry]) => {
        mobileBookBar.classList.toggle('is-visible', !entry.isIntersecting);
      }, { threshold:.08 });
      quickActionObserver.observe(openingHero);
    } else {
      mobileBookBar.classList.add('is-visible');
    }
  }

  // Pool conditions shared by public, customer, staff, admin and app views.
  function conditionView(condition) {
    const updatedTime = new Date(condition.updatedAt || '').getTime();
    const isStale = condition.verified && (!Number.isFinite(updatedTime) || Date.now() - updatedTime > DAY);
    const hasCurrentReading = Boolean(condition.verified && !isStale && condition.temperature != null);
    const temp = hasCurrentReading ? `${Number(condition.temperature).toFixed(1)}°C` : '—';
    const tempLabel = hasCurrentReading ? 'Staff verified today' : 'No verified reading today';
    const updated = condition.updatedAt ? `${formatDateTime(condition.updatedAt)} · ${condition.staff}` : 'No current staff reading published';
    const statusText = isStale && condition.status === 'open' ? `Check required · ${condition.statusText}` : condition.statusText;
    const statusClass = isStale && condition.status === 'open' ? 'changed' : (condition.verified ? condition.status : 'changed');
    return { temp, tempLabel, updated, statusText, statusClass, isStale, hasCurrentReading };
  }
  function renderConditions() {
    document.querySelectorAll('[data-location]').forEach(card => {
      const condition = conditions[card.dataset.location];
      if (!condition) return;
      const view = conditionView(condition);
      card.querySelectorAll('[data-reading]').forEach(el => { el.hidden = !view.hasCurrentReading; });
      card.querySelectorAll('[data-reading-fallback]').forEach(el => { el.hidden = view.hasCurrentReading; });
      card.querySelectorAll('[data-temp]').forEach(el => el.textContent = view.temp);
      card.querySelectorAll('[data-temp-label]').forEach(el => el.textContent = view.tempLabel);
      card.querySelectorAll('[data-updated]').forEach(el => el.textContent = view.updated);
      card.querySelectorAll('[data-verified-by]').forEach(el => el.textContent = view.hasCurrentReading ? `Verified by ${condition.staff}` : 'No current verified reading');
      card.querySelectorAll('[data-status]').forEach(el => {
        el.textContent = condition.verified ? view.statusText : view.statusText;
        el.classList.remove('open','closed','changed','demo');
        el.classList.add(view.statusClass);
      });
    });
    const wood = conditionView(conditions['wood-street']);
    document.querySelectorAll('[data-current-reading-only]').forEach(el => { el.hidden = !wood.hasCurrentReading; });
    document.querySelectorAll('[data-home-temp]').forEach(el => el.textContent = wood.temp);
    document.querySelectorAll('[data-home-updated]').forEach(el => el.textContent = wood.tempLabel);
    document.querySelectorAll('[data-home-status]').forEach(el => {
      el.textContent = wood.hasCurrentReading ? wood.statusText : 'Check conditions';
      el.className = `status ${wood.statusClass}`;
    });
  }
  renderConditions();

  async function hydrateServerConditions() {
    if (!/^https?:$/.test(location.protocol)) return;
    try {
      const payload = await fetchJSON('/api/public/locations', { headers:{ Accept:'application/json' } });
      payload.locations.forEach(locationItem => {
        const reading = locationItem.latest_reading;
        if (!conditions[locationItem.slug]) return;
        if (!reading) {
          conditions[locationItem.slug].statusText = locationItem.public_status || conditions[locationItem.slug].statusText;
          return;
        }
        conditions[locationItem.slug] = {
          temperature: reading.temperature,
          status: reading.status,
          statusText: locationItem.public_status,
          verified: true,
          staff: `${reading.first_name || 'HV Swim'} ${reading.last_name || 'team'}`.trim(),
          updatedAt: reading.created_at
        };
      });
      renderConditions();
    } catch (_) {}
  }
  if (document.querySelector('[data-location], [data-home-temp]')) hydrateServerConditions();

  // Live Bendigo weather. Pool temperature remains a separate staff-verified measurement.
  const weatherCodes = {
    0:['Clear','sun'], 1:['Mostly clear','cloud-sun'], 2:['Partly cloudy','cloud-sun'], 3:['Overcast','cloud'],
    45:['Fog','fog'], 48:['Fog','fog'], 51:['Light drizzle','cloud-rain'], 53:['Drizzle','cloud-rain'], 55:['Heavy drizzle','cloud-rain'],
    61:['Light rain','cloud-rain'], 63:['Rain','cloud-rain'], 65:['Heavy rain','cloud-rain'], 80:['Rain showers','cloud-rain'], 81:['Rain showers','cloud-rain'],
    82:['Heavy showers','cloud-rain'], 95:['Thunderstorm','cloud-lightning'], 96:['Thunderstorm','cloud-lightning'], 99:['Thunderstorm','cloud-lightning']
  };
  function renderWeather(data, cached=false) {
    const current = data.current || data;
    const [summary, icon] = weatherCodes[current.weather_code] || ['Current conditions','status'];
    const temperature = current.temperature_2m == null ? NaN : Number(current.temperature_2m);
    const apparent = current.apparent_temperature == null ? NaN : Number(current.apparent_temperature);
    const wind = current.wind_speed_10m == null ? NaN : Number(current.wind_speed_10m);
    document.querySelectorAll('[data-weather-temp]').forEach(el => el.textContent = Number.isFinite(temperature) ? `${Math.round(temperature)}°C` : '—');
    document.querySelectorAll('[data-weather-summary]').forEach(el => el.textContent = `${summary}${Number.isFinite(apparent) ? ` · feels ${Math.round(apparent)}°C` : ''}`);
    document.querySelectorAll('[data-weather-icon]').forEach(el => el.innerHTML = iconSvg(icon));
    document.querySelectorAll('[data-weather-wind]').forEach(el => el.textContent = Number.isFinite(wind) ? `${Math.round(wind)} km/h` : 'Unavailable');
    document.querySelectorAll('[data-weather-updated]').forEach(el => el.textContent = `${cached ? 'Cached' : 'Live'} · ${formatTime(new Date())}`);
  }
  async function fetchWeather(force=false) {
    let cached;
    try { cached = JSON.parse(localStorage.getItem(WEATHER_KEY)); } catch (_) {}
    if (!force && cached && Date.now() - cached.savedAt < 15 * 60 * 1000) { renderWeather(cached.data, true); return; }
    try {
      const payload = await fetchJSON('/api/public/weather', { headers:{ Accept:'application/json' } });
      const data = { current:payload.current };
      // Caching is a convenience. If storage is unavailable the fetch still succeeded,
      // so the reading must still be shown rather than falling through to the error path.
      try { localStorage.setItem(WEATHER_KEY, JSON.stringify({ savedAt:Date.now(), data })); } catch (_) {}
      renderWeather(data, false);
    } catch (_) {
      if (cached?.data) { renderWeather(cached.data, true); }
      else {
        document.querySelectorAll('[data-weather-temp]').forEach(el => el.textContent = '—');
        document.querySelectorAll('[data-weather-summary]').forEach(el => el.textContent = 'Weather feed unavailable');
        document.querySelectorAll('[data-weather-updated]').forEach(el => el.textContent = 'Try refresh when online');
      }
    }
  }
  upgradeLegacyIcons();
  if (document.querySelector('[data-weather-card]')) fetchWeather();
  document.querySelectorAll('[data-refresh-weather]').forEach(btn => btn.addEventListener('click', () => { fetchWeather(true); showToast('Refreshing live Bendigo weather…'); }));

  // App installation and offline shell.
  let deferredInstallPrompt = null;
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault(); deferredInstallPrompt = event;
    document.querySelectorAll('[data-install-app]').forEach(button => button.hidden = false);
  });
  document.querySelectorAll('[data-install-app]').forEach(button => button.addEventListener('click', async () => {
    if (!deferredInstallPrompt) { showToast('On iPhone/iPad, use Share → Add to Home Screen. On Mac, use the browser install option.'); return; }
    deferredInstallPrompt.prompt(); await deferredInstallPrompt.userChoice; deferredInstallPrompt = null; button.hidden = true;
  }));
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost','127.0.0.1'].includes(location.hostname))) {
    navigator.serviceWorker.register('service-worker.js').catch(() => {});
  }

  // Installed/native launches prioritise secure account access over website-install marketing.
  if (document.body.dataset.page === 'app') {
    const params = new URLSearchParams(location.search);
    const installedLaunch = params.get('native') === '1' || window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
    if (installedLaunch) {
      document.body.classList.add('app-launch-mode');
      const intro = document.querySelector('[data-app-launch-copy]');
      if (intro) intro.textContent = 'Choose your secure workspace below. If you are already signed in, we will take you straight to your HV Swim account.';
      const status = document.querySelector('[data-app-launch-status]');
      if (status) status.hidden = false;
      if (/^https?:$/.test(location.protocol)) {
        fetchJSON('/api/auth/me', { headers:{ Accept:'application/json' } }, 4500)
          .then(payload => { if (payload?.user) location.replace('platform.html'); })
          .catch(() => { if (status) status.textContent = 'Choose a secure workspace to sign in'; });
      }
    }
  }

  // The Facebook timeline is opt-in so Meta receives no browser request until a visitor chooses to load it.
  document.querySelectorAll('[data-facebook-feed]').forEach(feed => {
    const button = feed.querySelector('[data-load-facebook]');
    if (!button) return;
    button.addEventListener('click', () => {
      if (feed.querySelector('iframe')) return;
      if (['localhost','127.0.0.1'].includes(location.hostname)) {
        const preview = document.createElement('div');
        preview.className = 'facebook-consent facebook-local-preview';
        preview.innerHTML = `<div class="facebook-consent-mark" aria-hidden="true">f</div><span class="status changed">Meta embed configured</span><h3>Local preview keeps Meta disconnected.</h3><p>This local-only mode does not load the Meta iframe. Test the optional timeline on the approved production domain before launch, or use the direct link to see every current post.</p><a class="btn btn-blue" href="https://www.facebook.com/hvswimschoolbendigo" target="_blank" rel="noopener">View all Facebook posts <span aria-hidden="true">↗</span></a>`;
        feed.classList.add('is-preview');
        feed.replaceChildren(preview);
        return;
      }
      const frame = document.createElement('iframe');
      frame.className = 'facebook-iframe';
      frame.title = 'Latest posts from HV Swim School Bendigo on Facebook';
      frame.src = feed.dataset.src;
      frame.width = '500';
      frame.height = '680';
      frame.loading = 'lazy';
      frame.allow = 'autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share';
      frame.setAttribute('allowfullscreen', 'true');
      frame.setAttribute('scrolling', 'yes');
      feed.classList.add('is-loaded');
      feed.replaceChildren(frame);
    });
  });

  // Preview-centre shortcuts provide the supplied test-account guidance.
  document.querySelectorAll('[data-demo-action]').forEach(button => button.addEventListener('click', () => showToast(button.dataset.demoAction || 'This action is available in the live connected build.')));
})();
