(() => {
  'use strict';

  const DAY = 24 * 60 * 60 * 1000;
  const days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const classTime = window.HVSwim?.formatClassTime || (value => String(value || ''));
  const request = window.HVSwim?.fetchJSON || (async (url, options = {}, timeout = 8000) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, {...options, signal:controller.signal});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Request unavailable');
      return payload;
    } finally { clearTimeout(timer); }
  });
  let classRequest;
  const getClasses = () => (classRequest ||= request('/api/classes', {headers:{Accept:'application/json'}}));

  async function applySiteSettings() {
    if (!document.querySelector('[data-site-field], #site-announcement')) return;
    try {
      const {settings = {}} = await request('/api/public/site-settings', {headers:{Accept:'application/json'}});
      document.querySelectorAll('[data-site-field]').forEach(element => {
        const value = settings[element.dataset.siteField];
        if (value) element.textContent = value;
      });
      const announcement = document.getElementById('site-announcement');
      if (announcement && settings.announcement_enabled) {
        document.getElementById('site-announcement-text').textContent = settings.announcement_text;
        document.getElementById('site-enrolment-status').textContent = ({open:'Enrolments open',limited:'Limited places',waitlist:'Waitlist only'})[settings.enrolment_status] || 'Enrolment update';
        announcement.hidden = false;
      }
    } catch (_) {}
  }
  applySiteSettings();

  const availability = document.getElementById('public-availability');
  if (availability) {
    availability.setAttribute('aria-busy', 'true');
    getClasses().then(payload => {
      const open = (payload.classes || []).filter(item => Number(item.available) > 0).slice(0, 6);
      availability.innerHTML = open.map((item, index) => {
        const time = classTime(item.start_time);
        const query = new URLSearchParams({program:item.title,class:`${days[item.weekday]} ${time} at ${item.location_name}`});
        return `<article class="availability-card reveal visible" style="--reveal-delay:${Math.min(index * 60, 240)}ms"><span class="class-day">${esc(days[item.weekday])} · ${esc(time)}</span><h3>${esc(item.title)}</h3><p>${esc(item.level)} · ${esc(item.duration_minutes)} minutes<br>${esc(item.location_name)}</p><div class="availability-card-foot"><div><strong>${item.available} ${item.available === 1 ? 'place' : 'places'} showing</strong><span>${new Intl.NumberFormat('en-AU',{style:'currency',currency:'AUD'}).format(Number(item.price || 0))} per lesson · confirmed before enrolment</span></div><a class="text-link" href="enquire.html?${query}">Enquire</a></div></article>`;
      }).join('') || '<div class="empty-state"><strong>No classes are showing places right now.</strong><p>Places can reopen as families change days. Send an enquiry and the team will check the current timetable for you.</p><a class="btn btn-blue btn-small" href="enquire.html">Join the list <span aria-hidden="true">&rarr;</span></a></div>';
      document.getElementById('availability-source').textContent = 'Current published places are shown here. Lessons are $22.50 each, charged by the term and due on enrolment; HV Swim confirms class fit before the place is finalised.';
    }).catch(() => {
      availability.innerHTML = '<div class="empty-state"><strong>Class times are not loading right now.</strong><p>This is a temporary connection problem, not a sign that classes are full. Tell us what you need and the team will check what is open.</p><a class="btn btn-blue btn-small" href="enquire.html">Find a lesson <span aria-hidden="true">&rarr;</span></a></div>';
      const badge = document.getElementById('availability-connection');
      if (badge) { badge.textContent = 'Timetable unavailable'; badge.classList.remove('open'); badge.classList.add('changed'); }
      const note = document.getElementById('availability-connection-note');
      if (note) note.textContent = 'Please use the lesson finder or call the team for current options.';
    }).finally(() => availability.setAttribute('aria-busy', 'false'));
  }

  const todayGrid = document.getElementById('today-grid');
  if (!todayGrid) return;

  const weatherLabel = code => ({0:'Clear',1:'Mostly clear',2:'Partly cloudy',3:'Overcast',45:'Foggy',48:'Foggy',51:'Light drizzle',53:'Drizzle',55:'Heavy drizzle',61:'Light rain',63:'Rain',65:'Heavy rain',71:'Light snow',80:'Rain showers',81:'Rain showers',82:'Heavy showers',95:'Thunderstorm'})[Number(code)] || 'Local conditions';
  const dateTime = value => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Update time unavailable' : new Intl.DateTimeFormat('en-AU',{day:'numeric',month:'short',hour:'numeric',minute:'2-digit',timeZone:'Australia/Melbourne'}).format(date);
  };
  const currentMelbourneTime = () => {
    const now = new Date();
    const weekday = new Intl.DateTimeFormat('en-AU',{weekday:'long',timeZone:'Australia/Melbourne'}).format(now);
    const parts = Object.fromEntries(new Intl.DateTimeFormat('en-AU',{hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:'Australia/Melbourne'}).formatToParts(now).filter(part => part.type !== 'literal').map(part => [part.type, part.value]));
    return {day:days.indexOf(weekday), minutes:Number(parts.hour) * 60 + Number(parts.minute)};
  };

  todayGrid.setAttribute('aria-busy', 'true');
  Promise.allSettled([
    request('/api/public/weather', {headers:{Accept:'application/json'}}),
    request('/api/public/locations', {headers:{Accept:'application/json'}}),
    getClasses()
  ]).then(([weatherResult, locationResult, classResult]) => {
    if (weatherResult.status === 'fulfilled') {
      const current = weatherResult.value.current || {};
      const temperature = current.temperature_2m == null ? NaN : Number(current.temperature_2m);
      const apparent = current.apparent_temperature == null ? NaN : Number(current.apparent_temperature);
      const wind = current.wind_speed_10m == null ? NaN : Number(current.wind_speed_10m);
      document.getElementById('today-weather-temp').textContent = Number.isFinite(temperature) ? `${temperature.toFixed(1)}°C` : 'Unavailable';
      document.getElementById('today-weather-detail').textContent = `${weatherLabel(current.weather_code)}${Number.isFinite(apparent) ? ` · feels like ${apparent.toFixed(1)}°C` : ''}${Number.isFinite(wind) ? ` · wind ${wind.toFixed(0)} km/h` : ''}`;
    } else {
      document.getElementById('today-weather-temp').textContent = 'Unavailable';
      document.getElementById('today-weather-detail').textContent = 'Live weather is temporarily unavailable.';
    }

    if (locationResult.status === 'fulfilled') {
      const locations = locationResult.value.locations || [];
      const wood = locations.find(item => item.slug === 'wood-street');
      const reading = wood?.latest_reading;
      const readingDate = new Date(reading?.created_at || '');
      const stale = !reading || Number.isNaN(readingDate.getTime()) || Date.now() - readingDate.getTime() > DAY;
      const currentReading = Boolean(reading && !stale && reading.temperature != null);
      document.getElementById('today-pool-temp').textContent = currentReading ? `${Number(reading.temperature).toFixed(1)}°C` : 'Check conditions';
      document.getElementById('today-pool-detail').textContent = currentReading ? `Staff verified · ${dateTime(reading.created_at)} · ${reading.first_name || 'HV Swim team'}` : 'No verified water reading has been published in the last 24 hours.';
      const seasonal = locations.find(item => item.slug === 'bendigo-east');
      document.getElementById('today-seasonal-copy').textContent = seasonal?.public_status || 'Status unavailable';
      const isClosed = seasonal?.public_status?.toLowerCase().includes('closed');
      const seasonalStatus = document.getElementById('today-seasonal-status');
      seasonalStatus.textContent = isClosed ? 'Closed' : 'Venue update';
      seasonalStatus.className = `status ${isClosed ? 'closed' : 'changed'}`;
    } else {
      document.getElementById('today-pool-temp').textContent = 'Unavailable';
      document.getElementById('today-pool-detail').textContent = 'Open Locations for the latest published condition.';
      document.getElementById('today-seasonal-copy').textContent = 'Venue status is temporarily unavailable.';
    }

    if (classResult.status === 'fulfilled') {
      const now = currentMelbourneTime();
      const open = (classResult.value.classes || []).filter(item => Number(item.available) > 0).map(item => {
        const [hour, minute] = String(item.start_time).split(':').map(Number);
        let dayDelta = (Number(item.weekday) - now.day + 7) % 7;
        if (dayDelta === 0 && hour * 60 + minute <= now.minutes) dayDelta = 7;
        return {...item, sort:dayDelta * 1440 + hour * 60 + minute};
      }).sort((a,b) => a.sort - b.sort);
      const next = open[0];
      if (next) {
        const time = classTime(next.start_time);
        document.getElementById('today-class-title').textContent = next.title;
        document.getElementById('today-class-detail').textContent = `${days[next.weekday]} ${time} · ${next.location_name} · ${next.available} ${next.available === 1 ? 'place' : 'places'} showing`;
        document.getElementById('today-class-link').href = `enquire.html?${new URLSearchParams({program:next.title,class:`${days[next.weekday]} ${time} at ${next.location_name}`})}`;
      } else {
        document.getElementById('today-class-title').textContent = 'Ask the team';
        document.getElementById('today-class-detail').textContent = 'No open class is currently showing online.';
      }
    } else {
      document.getElementById('today-class-title').textContent = 'Ask the team';
      document.getElementById('today-class-detail').textContent = 'The team can confirm current lesson options.';
    }

    const failures = [weatherResult, locationResult, classResult].filter(result => result.status === 'rejected').length;
    document.getElementById('today-updated').textContent = failures === 3 ? 'Live details unavailable' : `${failures ? 'Partly updated' : 'Updated'} ${new Intl.DateTimeFormat('en-AU',{hour:'numeric',minute:'2-digit',timeZone:'Australia/Melbourne'}).format(new Date())}`;
  }).finally(() => todayGrid.setAttribute('aria-busy', 'false'));
})();
