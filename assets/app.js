(() => {
  'use strict';

  const STORAGE_KEY = 'hv-swim-v4-demo-state';
  const WEATHER_KEY = 'hv-swim-v4-weather-cache';
  const DAY = 24 * 60 * 60 * 1000;
  const defaults = {
    version: 4,
    conditions: {
      'wood-street': {
        temperature: 31.8,
        status: 'open',
        statusText: 'Lessons running',
        verified: false,
        staff: 'Demo sample',
        updatedAt: null,
        note: 'Sample reading — staff update required before treating as live'
      },
      'bendigo-east': {
        temperature: null,
        status: 'closed',
        statusText: 'Closed for winter',
        verified: true,
        staff: 'City of Greater Bendigo notice',
        updatedAt: '2026-05-10T17:00:00+10:00',
        note: '2026/27 reopening arrangements are still to be confirmed'
      }
    },
    conditionHistory: [],
    clock: { active: false, start: null, location: 'wood-street', geo: null },
    timeEntries: [],
    timesheetStatus: 'draft',
    approvals: [],
    checklist: [false, false, false, false]
  };

  function cloneDefaults() { return JSON.parse(JSON.stringify(defaults)); }
  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (!saved || saved.version !== 4) return cloneDefaults();
      return {
        ...cloneDefaults(), ...saved,
        conditions: { ...cloneDefaults().conditions, ...(saved.conditions || {}) }
      };
    } catch (_) { return cloneDefaults(); }
  }
  let state = loadState();
  function saveState() { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (_) {} }
  function escapeHTML(value) {
    return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
  }
  function formatTime(date) { return new Intl.DateTimeFormat('en-AU', { hour:'numeric', minute:'2-digit', timeZone:'Australia/Melbourne' }).format(date); }
  function formatDateTime(value) {
    if (!value) return 'Staff update required';
    const date = new Date(value);
    return new Intl.DateTimeFormat('en-AU', { day:'numeric', month:'short', hour:'numeric', minute:'2-digit', timeZone:'Australia/Melbourne' }).format(date);
  }
  function locationName(key) {
    return ({ 'wood-street':'Wood Street Indoor Pool', 'bendigo-east':'Bendigo East Swimming Pool', office:'Administration / off pool' })[key] || key;
  }
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
  const setMenu = open => {
    nav?.classList.toggle('open', open);
    menuToggle?.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('no-scroll', open);
  };
  const closeMenu = ({ refocus = false } = {}) => {
    if (!nav?.classList.contains('open')) return;
    setMenu(false);
    // Send focus back to the control that opened it, or it lands at the top of the page.
    if (refocus) menuToggle?.focus();
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
  // A menu left open across a resize to desktop would keep the page scroll-locked.
  window.addEventListener('resize', () => { if (window.innerWidth > 980) closeMenu(); }, { passive: true });
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
    const isStale = condition.verified && condition.updatedAt && (Date.now() - new Date(condition.updatedAt).getTime() > DAY);
    const temp = condition.temperature == null ? '—' : `${Number(condition.temperature).toFixed(1)}°C`;
    const tempLabel = condition.verified ? (isStale ? 'Reading over 24h old' : 'Staff verified') : 'Demo sample';
    const updated = condition.updatedAt ? `${formatDateTime(condition.updatedAt)} · ${condition.staff}` : 'Staff update required before treating as live';
    const statusText = isStale && condition.status === 'open' ? `Check required · ${condition.statusText}` : condition.statusText;
    const statusClass = isStale && condition.status === 'open' ? 'changed' : (condition.verified ? condition.status : 'demo');
    return { temp, tempLabel, updated, statusText, statusClass, isStale };
  }
  function renderConditions() {
    document.querySelectorAll('[data-location]').forEach(card => {
      const condition = state.conditions[card.dataset.location];
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
    const wood = conditionView(state.conditions['wood-street']);
    document.querySelectorAll('[data-home-temp]').forEach(el => el.textContent = wood.temp);
    document.querySelectorAll('[data-home-updated]').forEach(el => el.textContent = wood.tempLabel);
    document.querySelectorAll('[data-home-status]').forEach(el => {
      el.textContent = state.conditions['wood-street'].verified ? wood.statusText : 'Demo';
      el.className = `status ${wood.statusClass}`;
    });
  }
  renderConditions();

  async function hydrateServerConditions() {
    if (!/^https?:$/.test(location.protocol)) return;
    try {
      const response = await fetch('/api/public/locations', { headers:{ Accept:'application/json' } });
      if (!response.ok) return;
      const payload = await response.json();
      payload.locations.forEach(locationItem => {
        const reading = locationItem.latest_reading;
        if (!reading || !state.conditions[locationItem.slug]) return;
        state.conditions[locationItem.slug] = {
          temperature: reading.temperature,
          status: reading.status,
          statusText: locationItem.public_status,
          verified: true,
          staff: `${reading.first_name || 'HV Swim'} ${reading.last_name || 'staff'}`.trim(),
          updatedAt: reading.created_at,
          note: reading.note || ''
        };
      });
      renderConditions();
    } catch (_) {}
  }
  hydrateServerConditions();

  const conditionForm = document.querySelector('[data-condition-form]');
  conditionForm?.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(conditionForm);
    const key = String(data.get('location'));
    const temperature = Number(data.get('temperature'));
    const status = String(data.get('status'));
    const statusText = ({ open:'Lessons running', changed:'Changed conditions', closed:'Closed / lessons cancelled' })[status];
    if (!Number.isFinite(temperature) || temperature < 15 || temperature > 40) {
      showToast('Enter a water temperature between 15°C and 40°C.'); return;
    }
    const record = {
      temperature, status, statusText, verified:true,
      staff:String(data.get('staff') || 'Staff member').trim(),
      updatedAt:new Date().toISOString(),
      note:String(data.get('note') || '').trim()
    };
    state.conditions[key] = record;
    state.conditionHistory.unshift({ location:key, ...record });
    state.conditionHistory = state.conditionHistory.slice(0, 30);
    state.checklist[1] = true;
    saveState(); renderConditions(); renderConditionHistory(); renderChecklist();
    conditionForm.querySelector('[name="temperature"]').value = '';
    conditionForm.querySelector('[name="note"]').value = '';
    showToast(`${locationName(key)} updated: ${temperature.toFixed(1)}°C · ${statusText}.`);
  });
  function renderConditionHistory() {
    const wrap = document.querySelector('[data-condition-history]');
    if (!wrap) return;
    if (!state.conditionHistory.length) {
      wrap.innerHTML = '<div class="lesson-row"><time>Demo</time><span>Wood Street · 31.8°C</span><strong>Sample</strong></div>';
      return;
    }
    wrap.innerHTML = state.conditionHistory.slice(0, 6).map(item => `<div class="lesson-row"><time>${escapeHTML(formatDateTime(item.updatedAt))}</time><span>${escapeHTML(locationName(item.location))} · ${Number(item.temperature).toFixed(1)}°C</span><strong>${escapeHTML(item.staff)}</strong></div>`).join('');
  }
  renderConditionHistory();
  document.querySelector('[data-clear-condition-history]')?.addEventListener('click', () => {
    state.conditionHistory = []; saveState(); renderConditionHistory(); showToast('Demo temperature history cleared.');
  });

  // Live Bendigo weather. Pool temperature remains a separate staff-verified measurement.
  const weatherCodes = {
    0:['Clear','☀'], 1:['Mostly clear','🌤'], 2:['Partly cloudy','⛅'], 3:['Overcast','☁'],
    45:['Fog','≋'], 48:['Fog','≋'], 51:['Light drizzle','🌦'], 53:['Drizzle','🌦'], 55:['Heavy drizzle','🌧'],
    61:['Light rain','🌦'], 63:['Rain','🌧'], 65:['Heavy rain','🌧'], 80:['Rain showers','🌦'], 81:['Rain showers','🌧'],
    82:['Heavy showers','🌧'], 95:['Thunderstorm','⛈'], 96:['Thunderstorm','⛈'], 99:['Thunderstorm','⛈']
  };
  function renderWeather(data, cached=false) {
    const current = data.current || data;
    const [summary, icon] = weatherCodes[current.weather_code] || ['Current conditions','◌'];
    document.querySelectorAll('[data-weather-temp]').forEach(el => el.textContent = `${Math.round(current.temperature_2m)}°C`);
    document.querySelectorAll('[data-weather-summary]').forEach(el => el.textContent = `${summary} · feels ${Math.round(current.apparent_temperature)}°C`);
    document.querySelectorAll('[data-weather-icon]').forEach(el => el.textContent = icon);
    document.querySelectorAll('[data-weather-wind]').forEach(el => el.textContent = `${Math.round(current.wind_speed_10m)} km/h`);
    document.querySelectorAll('[data-weather-updated]').forEach(el => el.textContent = `${cached ? 'Cached' : 'Live'} · ${formatTime(new Date())}`);
  }
  async function fetchWeather(force=false) {
    let cached;
    try { cached = JSON.parse(localStorage.getItem(WEATHER_KEY)); } catch (_) {}
    if (!force && cached && Date.now() - cached.savedAt < 15 * 60 * 1000) { renderWeather(cached.data, true); return; }
    try {
      let data;
      const internal = await fetch('/api/public/weather', { headers:{ Accept:'application/json' } });
      if (internal.ok) {
        const payload = await internal.json(); data = { current:payload.current };
      } else {
        const endpoint = 'https://api.open-meteo.com/v1/forecast?latitude=-36.757&longitude=144.279&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m&timezone=Australia%2FMelbourne';
        const response = await fetch(endpoint, { signal: AbortSignal.timeout ? AbortSignal.timeout(8000) : undefined });
        if (!response.ok) throw new Error('Weather unavailable'); data = await response.json();
      }
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
  if (document.querySelector('[data-weather-card]')) fetchWeather();
  document.querySelectorAll('[data-refresh-weather]').forEach(btn => btn.addEventListener('click', () => { fetchWeather(true); showToast('Refreshing live Bendigo weather…'); }));

  // Staff shift clock and optional browser geolocation.
  function renderClock() {
    const timeEl = document.querySelector('[data-clock-time]');
    const stateEl = document.querySelector('[data-clock-state]');
    const button = document.querySelector('[data-clock-toggle]');
    const select = document.querySelector('[data-clock-location]');
    if (!timeEl || !stateEl || !button || !select) return;
    timeEl.textContent = formatTime(new Date());
    select.value = state.clock.location || 'wood-street';
    select.disabled = state.clock.active;
    button.textContent = state.clock.active ? 'Clock out' : 'Clock in';
    if (state.clock.active && state.clock.start) {
      const elapsed = Math.max(0, Date.now() - new Date(state.clock.start).getTime());
      const hours = Math.floor(elapsed / 3600000); const mins = Math.floor((elapsed % 3600000) / 60000);
      stateEl.textContent = `Clocked in at ${locationName(state.clock.location)} · ${hours}h ${mins}m`;
    } else stateEl.textContent = 'Not clocked in · Select a venue to begin';
  }
  renderClock(); setInterval(renderClock, 30000);
  document.querySelector('[data-clock-location]')?.addEventListener('change', event => { state.clock.location = event.target.value; saveState(); });
  document.querySelector('[data-clock-toggle]')?.addEventListener('click', () => {
    const select = document.querySelector('[data-clock-location]');
    if (!state.clock.active) {
      state.clock = { ...state.clock, active:true, start:new Date().toISOString(), location:select.value };
      showToast(`Clocked in at ${locationName(select.value)}.`);
    } else {
      const finish = new Date(); const start = new Date(state.clock.start);
      const hours = Math.max(.1, (finish - start) / 3600000);
      state.timeEntries.unshift({ date:finish.toISOString(), location:state.clock.location, start:start.toISOString(), finish:finish.toISOString(), hours });
      state.clock = { ...state.clock, active:false, start:null };
      showToast(`Clocked out. Demo shift recorded as ${hours.toFixed(2)} hours.`);
    }
    saveState(); renderClock(); renderTimeEntries();
  });
  document.querySelector('[data-use-location]')?.addEventListener('click', () => {
    const status = document.querySelector('[data-geo-status]');
    if (!navigator.geolocation) { if (status) status.textContent = 'Location is not available on this device'; return; }
    if (status) status.textContent = 'Requesting device permission…';
    navigator.geolocation.getCurrentPosition(position => {
      state.clock.geo = { latitude:+position.coords.latitude.toFixed(5), longitude:+position.coords.longitude.toFixed(5), accuracy:Math.round(position.coords.accuracy), capturedAt:new Date().toISOString() };
      saveState();
      if (status) status.textContent = `Captured on device · accuracy ±${state.clock.geo.accuracy} m`;
      showToast('Work location captured in this browser demo.');
    }, () => { if (status) status.textContent = 'Permission not granted · manual venue selection remains available'; });
  });
  function renderTimeEntries() {
    const body = document.querySelector('[data-timesheet-body]');
    if (!body) return;
    const base = '<tr><td>Monday</td><td>Wood Street</td><td>8:45 am</td><td>5:45 pm</td><td>30 min</td><td>8.5</td><td><span class="status demo">Draft</span></td></tr><tr><td>Tuesday</td><td>Wood Street</td><td>2:45 pm</td><td>6:15 pm</td><td>—</td><td>3.5</td><td><span class="status demo">Draft</span></td></tr>';
    const extra = state.timeEntries.map(entry => `<tr><td>${escapeHTML(new Intl.DateTimeFormat('en-AU',{weekday:'long',timeZone:'Australia/Melbourne'}).format(new Date(entry.date)))}</td><td>${escapeHTML(locationName(entry.location))}</td><td>${escapeHTML(formatTime(new Date(entry.start)))}</td><td>${escapeHTML(formatTime(new Date(entry.finish)))}</td><td>—</td><td>${Number(entry.hours).toFixed(2)}</td><td><span class="status demo">Draft</span></td></tr>`).join('');
    body.innerHTML = base + extra;
    const total = 12 + state.timeEntries.reduce((sum,item) => sum + Number(item.hours || 0), 0);
    document.querySelectorAll('[data-total-hours]').forEach(el => el.textContent = `${total.toFixed(2)} hours`);
  }
  renderTimeEntries();
  document.querySelector('[data-submit-timesheet]')?.addEventListener('click', event => {
    state.timesheetStatus = 'submitted'; saveState();
    const status = document.querySelector('[data-timesheet-status]');
    if (status) { status.textContent = 'Submitted'; status.className = 'status open'; }
    event.currentTarget.disabled = true; event.currentTarget.textContent = 'Submitted';
    showToast('Timesheet submitted to the demo approval queue.');
  });
  if (state.timesheetStatus === 'submitted') {
    const status = document.querySelector('[data-timesheet-status]');
    if (status) { status.textContent = 'Submitted'; status.className = 'status open'; }
    const submit = document.querySelector('[data-submit-timesheet]'); if (submit) { submit.disabled = true; submit.textContent = 'Submitted'; }
  }

  // Staff checklist.
  function renderChecklist() {
    const checks = [...document.querySelectorAll('[data-checklist]')];
    checks.forEach((box,index) => box.checked = Boolean(state.checklist[index]));
    const remaining = state.checklist.filter(value => !value).length;
    const status = document.querySelector('[data-checklist-status]');
    if (status) { status.textContent = remaining ? `${remaining} remaining` : 'Complete'; status.className = `status ${remaining ? 'changed' : 'open'}`; }
  }
  document.querySelectorAll('[data-checklist]').forEach((box,index) => box.addEventListener('change', () => { state.checklist[index] = box.checked; saveState(); renderChecklist(); }));
  renderChecklist();

  // Admin approval interactions.
  function renderApprovals() {
    let pendingHours = 0; let pendingCount = 0;
    document.querySelectorAll('[data-approval-row]').forEach((row,index) => {
      const approved = state.approvals.includes(index);
      const action = row.querySelector('[data-approve]');
      if (approved && action) { action.textContent = 'Approved'; action.disabled = true; action.className = 'btn btn-soft btn-small'; }
      if (!approved) { pendingHours += Number(row.dataset.hours || 0); pendingCount += 1; }
    });
    document.querySelectorAll('[data-pending-hours]').forEach(el => el.textContent = pendingHours.toFixed(1));
    document.querySelectorAll('[data-approval-foot]').forEach(el => el.textContent = `${pendingCount} staff timesheet${pendingCount === 1 ? '' : 's'}`);
  }
  document.querySelectorAll('[data-approve]').forEach((button,index) => button.addEventListener('click', () => {
    if (!state.approvals.includes(index)) state.approvals.push(index);
    saveState(); renderApprovals(); showToast('Timesheet approved and marked ready for the Xero workflow.');
  }));
  document.querySelector('[data-approve-all]')?.addEventListener('click', () => {
    document.querySelectorAll('[data-approve]').forEach((_,index) => { if (!state.approvals.includes(index)) state.approvals.push(index); });
    saveState(); renderApprovals(); showToast('All clean demo timesheets approved.');
  });
  renderApprovals();

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

  // Explicitly labelled demo actions.
  document.querySelectorAll('[data-demo-action]').forEach(button => button.addEventListener('click', () => showToast(button.dataset.demoAction || 'This action is available in the live connected build.')));
  document.querySelectorAll('[data-demo-shop]').forEach(button => button.addEventListener('click', () => showToast('Demo product only — Shopify catalogue and checkout are not connected yet.')));
  document.querySelectorAll('[data-reset-demo]').forEach(button => button.addEventListener('click', () => {
    if (!window.confirm('Reset the HV Swim V4 browser demo data on this device?')) return;
    // Storage can throw outright where site data is blocked; the reset must still run.
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
    state = cloneDefaults(); saveState(); location.reload();
  }));
})();
