(() => {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const money = value => new Intl.NumberFormat('en-AU', {style:'currency', currency:'AUD', maximumFractionDigits:2}).format(Number(value || 0));
  const days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const classTime = window.HVSwim?.formatClassTime || (value => String(value || ''));
  const request = window.HVSwim?.fetchJSON || (async url => {
    const response = await fetch(url, {headers:{Accept:'application/json'}});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Request unavailable');
    return payload;
  });
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
      const time = classTime(item.start_time);
      const query = new URLSearchParams({program:item.title, class:`${days[item.weekday]} ${time} at ${item.location_name}`});
      return `<article class="availability-card reveal visible" style="--reveal-delay:${Math.min(index * 45, 225)}ms"><div class="class-card-top"><span class="class-day">${esc(days[item.weekday])} · ${esc(time)}</span><span class="status ${available ? 'open' : 'closed'}">${available ? `${available} ${available === 1 ? 'place' : 'places'}` : 'Waitlist'}</span></div><h3>${esc(item.title)}</h3><p>${esc(item.level)} · ${esc(item.duration_minutes)} minutes<br>${esc(item.location_name)}</p><div class="availability-card-foot"><div><strong>${groupFor(item.title)==='private'?'Contact us for pricing':`${money(item.price)} per lesson`}</strong><span>Fee confirmed before enrolment</span></div><a class="text-link" href="enquire.html?${query}">${available ? 'Enquire' : 'Ask about waitlist'}</a></div></article>`;
    }).join('') || '<div class="empty-state"><strong>No classes match those filters.</strong><p>That does not mean there is nothing suitable — times shift each term and private options are available. Tell us what you need and we will look.</p><a class="btn btn-blue btn-small" href="enquire.html">Find a lesson <span aria-hidden="true">&rarr;</span></a></div>';
  };

  const availabilityGrid = document.getElementById('program-availability');
  availabilityGrid?.setAttribute('aria-busy', 'true');
  request('/api/classes', {headers:{Accept:'application/json'}}).then(payload => {
    classes = payload.classes || [];
    updateProgramSummaries();
    renderAvailability();
    document.getElementById('program-availability-source').textContent = 'Current published places are shown here. Standard lessons are $22.50 each, charged by the term and due on enrolment. Ask us about private pricing; HV Swim confirms class fit before the place is finalised.';
  }).catch(() => {
    document.querySelectorAll('[data-price]').forEach(element => element.textContent = 'Ask the team');
    document.querySelectorAll('[data-place]').forEach(element => element.textContent = 'Availability confirmed personally');
    const grid = document.getElementById('program-availability');
    if (grid) grid.innerHTML = '<div class="empty-state"><strong>The timetable is not loading right now.</strong><p>This is a temporary problem on our side, not a sign that classes are full. Send an enquiry and the team will confirm what is open.</p><a class="btn btn-blue btn-small" href="enquire.html">Find a lesson <span aria-hidden="true">&rarr;</span></a></div>';
    document.getElementById('program-availability-source').textContent = 'The live timetable is temporarily unavailable. The HV Swim team can confirm current options personally.';
  }).finally(() => availabilityGrid?.setAttribute('aria-busy', 'false'));

  document.getElementById('program-filters')?.addEventListener('click', event => {
    const button = event.target.closest('[data-filter]');
    if (!button) return;
    activeFilter = button.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(item => {
      const selected = item === button;
      item.classList.toggle('active', selected);
      item.setAttribute('aria-pressed', String(selected));
    });
    renderAvailability();
  });

  document.getElementById('program-matcher')?.addEventListener('submit', event => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    const age = document.getElementById('matcher-age').value;
    const confidence = document.getElementById('matcher-confidence').value;
    const goal = document.getElementById('matcher-goal').value;
    const {title, anchor, explanation} = window.HVLessonPathway({age, confidence, goal});
    const query = new URLSearchParams({program:title, matcher_age:age, matcher_confidence:confidence, matcher_goal:goal});
    const result = document.getElementById('matcher-result');
    const answers = ['matcher-age','matcher-confidence','matcher-goal'].map(id => document.getElementById(id).selectedOptions[0].textContent);
    result.innerHTML = `<div class="matcher-answer-summary">${answers.map(answer => `<span>${esc(answer)}</span>`).join('')}</div><span class="matcher-result-label">Suggested starting point</span><strong>${esc(title)}</strong><p>${esc(explanation)}</p><div class="matcher-result-actions"><a class="btn btn-blue btn-small" href="enquire.html?${query}">Continue to enquiry</a><a class="text-link" href="#${anchor}">Review this program</a></div>`;
    result.classList.add('has-result');
    result.focus({preventScroll:true});
  });


  const matcher = document.getElementById('program-matcher');
  const matcherResult = document.getElementById('matcher-result');
  const initialResult = matcherResult?.innerHTML;
  matcher?.addEventListener('change', () => {
    matcherResult.innerHTML = initialResult;
    matcherResult.classList.remove('has-result');
  });
  document.getElementById('lesson-checklist')?.addEventListener('change', event => {
    const list = event.currentTarget;
    const count = list.querySelectorAll('input:checked').length;
    document.getElementById('lesson-checklist-count').textContent = `${count} of 4 ready${count === 4 ? ' · You’re prepared. See you poolside!' : ''}`;
  });

})();
