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
      temperature: 31.8,
      status: 'open',
      statusText: 'Lessons running',
      verified: false,
      staff: 'Sample only',
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
  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.add('visible'); observer.unobserve(entry.target); }
  }), { threshold:0, rootMargin:'0px 0px -8% 0px' }) : null;
  document.querySelectorAll('.reveal').forEach(el => observer ? observer.observe(el) : el.classList.add('visible'));

  // Pool conditions shared by public, customer, staff, admin and app views.
  function conditionView(condition) {
    const updatedTime = new Date(condition.updatedAt || '').getTime();
    const isStale = condition.verified && (!Number.isFinite(updatedTime) || Date.now() - updatedTime > DAY);
    const temp = condition.temperature == null ? '—' : `${Number(condition.temperature).toFixed(1)}°C`;
    const tempLabel = condition.verified ? (isStale ? 'Reading over 24h old' : 'Staff verified') : 'Demo sample';
    const updated = condition.updatedAt ? `${formatDateTime(condition.updatedAt)} · ${condition.staff}` : 'Staff update required before treating as live';
    const statusText = isStale && condition.status === 'open' ? `Check required · ${condition.statusText}` : condition.statusText;
    const statusClass = isStale && condition.status === 'open' ? 'changed' : (condition.verified ? condition.status : 'demo');
    return { temp, tempLabel, updated, statusText, statusClass, isStale };
  }
  function renderConditions() {
    document.querySelectorAll('[data-location]').forEach(card => {
      const condition = conditions[card.dataset.location];
      if (!condition) return;
      const view = conditionView(condition);
      card.querySelectorAll('[data-temp]').forEach(el => el.textContent = view.temp);
      card.querySelectorAll('[data-temp-label]').forEach(el => el.textContent = view.tempLabel);
      card.querySelectorAll('[data-updated]').forEach(el => el.textContent = view.updated);
      card.querySelectorAll('[data-verified-by]').forEach(el => el.textContent = condition.verified ? `Verified by ${condition.staff}` : 'Demo sample only');
      card.querySelectorAll('[data-status]').forEach(el => {
        el.textContent = condition.verified ? view.statusText : `Demo · ${condition.statusText.toLowerCase()}`;
        el.classList.remove('open','closed','changed','demo');
        el.classList.add(view.statusClass);
      });
    });
    const wood = conditionView(conditions['wood-street']);
    document.querySelectorAll('[data-home-temp]').forEach(el => el.textContent = wood.temp);
    document.querySelectorAll('[data-home-updated]').forEach(el => el.textContent = wood.tempLabel);
    document.querySelectorAll('[data-home-status]').forEach(el => {
      el.textContent = conditions['wood-street'].verified ? wood.statusText : 'Awaiting check';
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
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) {
    navigator.serviceWorker.register('service-worker.js').catch(() => {});
  }

  // Preview-centre shortcuts provide the supplied test-account guidance.
  document.querySelectorAll('[data-demo-action]').forEach(button => button.addEventListener('click', () => showToast(button.dataset.demoAction || 'This action is available in the live connected build.')));
})();
