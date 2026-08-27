(() => {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const money = value => new Intl.NumberFormat('en-AU', {style:'currency', currency:'AUD', maximumFractionDigits:2}).format(Number(value || 0));
  const days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const groupFor = title => {
    const value = String(title || '').toLowerCase();
    if (value.includes('infant')) return 'infant';
    if (value.includes('private')) return 'private';
    if (value.includes('stroke')) return 'stroke';
    return 'learn';
  };

  let classes = [];
  let activeFilter = 'all';

  const updateProgramSummaries = () => {
    ['infant','learn','stroke','private'].forEach(group => {
      const matching = classes.filter(item => groupFor(item.title) === group);
      const prices = matching.map(item => Number(item.price)).filter(Number.isFinite);
      const open = matching.reduce((sum, item) => sum + Number(item.available || 0), 0);
      const price = document.querySelector(`[data-price="${group}"]`);
      const place = document.querySelector(`[data-place="${group}"]`);
      if (price) price.textContent = prices.length ? `From ${money(Math.min(...prices))} / lesson` : 'Ask the team';
      if (place) place.textContent = matching.length ? `${open} ${open === 1 ? 'place' : 'places'} showing across ${matching.length} ${matching.length === 1 ? 'class' : 'classes'}` : 'Tailored availability by enquiry';
    });
  };

  const renderAvailability = () => {
    const grid = document.getElementById('program-availability');
    if (!grid) return;
    const visible = classes.filter(item => activeFilter === 'all' || groupFor(item.title) === activeFilter);
    grid.innerHTML = visible.map((item, index) => {
      const available = Number(item.available || 0);
      const query = new URLSearchParams({program:item.title, class:`${days[item.weekday]} ${item.start_time} at ${item.location_name}`});
      return `<article class="availability-card reveal visible" style="--reveal-delay:${Math.min(index * 45, 225)}ms"><div class="class-card-top"><span class="class-day">${esc(days[item.weekday])} · ${esc(item.start_time)}</span><span class="status ${available ? 'open' : 'closed'}">${available ? `${available} ${available === 1 ? 'place' : 'places'}` : 'Waitlist'}</span></div><h3>${esc(item.title)}</h3><p>${esc(item.level)} · ${esc(item.duration_minutes)} minutes<br>${esc(item.location_name)}</p><div class="availability-card-foot"><div><strong>${money(item.price)} per lesson</strong><span>Connected preview price</span></div><a class="text-link" href="enquire.html?${query}">${available ? 'Enquire' : 'Join waitlist'}</a></div></article>`;
    }).join('') || '<div class="empty-state">No classes match this filter. The team can still discuss tailored availability.</div>';
  };

  fetch('/api/classes', {headers:{Accept:'application/json'}}).then(async response => {
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Availability unavailable');
    classes = payload.classes || [];
    updateProgramSummaries();
    renderAvailability();
    document.getElementById('program-availability-source').textContent = 'Connected to the local HV Swim class database. Prices, places and timetable entries remain preview data until management imports and approves the production timetable.';
  }).catch(() => {
    document.querySelectorAll('[data-price]').forEach(element => element.textContent = 'Ask the team');
    document.querySelectorAll('[data-place]').forEach(element => element.textContent = 'Availability confirmed personally');
    const grid = document.getElementById('program-availability');
    if (grid) grid.innerHTML = '<div class="empty-state">The timetable is temporarily unavailable. Enquire and the team will confirm the best current option.</div>';
    document.getElementById('program-availability-source').textContent = 'Live class data needs the connected HV Swim server. No availability has been invented.';
  });

  document.getElementById('program-filters')?.addEventListener('click', event => {
    const button = event.target.closest('[data-filter]');
    if (!button) return;
    activeFilter = button.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(item => item.classList.toggle('active', item === button));
    renderAvailability();
  });

  document.getElementById('program-matcher')?.addEventListener('submit', event => {
    event.preventDefault();
    const age = document.getElementById('matcher-age').value;
    const confidence = document.getElementById('matcher-confidence').value;
    const goal = document.getElementById('matcher-goal').value;
    let title = 'Learn to Swim';
    let anchor = 'learn';
    let explanation = 'A small-group learn-to-swim pathway can build confidence and core skills, with the exact level confirmed personally.';
    if (age === 'under2') { title = 'Infant Aquatics'; anchor = 'infant'; explanation = 'A carer-supported infant program creates positive early water experiences and safe foundations.'; }
    else if (goal === 'personal') { title = 'Private 1:1 Lesson'; anchor = 'private'; explanation = 'One-to-one coaching can match the swimmer’s pace, confidence, communication style and individual goals.'; }
    else if (confidence === 'independent' || goal === 'technique') { title = 'Stroke Development'; anchor = 'stroke'; explanation = 'A technique-focused pathway can strengthen movement patterns, breathing and endurance for an independent swimmer.'; }
    else if (age === 'teenadult' && (confidence === 'new' || goal === 'confidence')) { title = 'Adult / Teen Private Assessment'; anchor = 'private'; explanation = 'A calm private assessment gives a teen or adult a personal, no-pressure starting point.'; }
    const query = new URLSearchParams({program:title});
    const result = document.getElementById('matcher-result');
    result.innerHTML = `<span class="matcher-result-label">Suggested starting point</span><strong>${esc(title)}</strong><p>${esc(explanation)}</p><div class="matcher-result-actions"><a class="btn btn-blue btn-small" href="enquire.html?${query}">Continue to enquiry</a><a class="text-link" href="#${anchor}">Review this program</a></div>`;
    result.classList.add('has-result');
  });
})();
