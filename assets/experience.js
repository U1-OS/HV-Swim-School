(() => {
  'use strict';
  const root = document.documentElement;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
  const key = 'hv-swim-motion';
  let paused = false;
  try { paused = localStorage.getItem(key) === 'off'; } catch (_) { /* Private browsing still works. */ }
  const motionOff = () => paused || reduced.matches;

  const footer = document.querySelector('.site-footer');
  if (footer) {
    const row = document.createElement('div');
    row.className = 'container footer-motion';
    const text = document.createElement('span');
    text.textContent = 'A little confidence goes a long way.';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'motion-preference';
    button.dataset.motionToggle = '';
    row.append(text, button);
    footer.append(row);
  }
  if (document.body) {
    const dock = document.createElement('button');
    dock.type = 'button';
    dock.className = 'motion-preference motion-dock';
    dock.dataset.motionToggle = '';
    document.body.append(dock);
  }
  function syncMotion() {
    root.dataset.motion = motionOff() ? 'off' : 'on';
    document.querySelectorAll('[data-motion-toggle]').forEach(button => {
      button.textContent = reduced.matches ? 'Reduced motion' : paused ? 'Enable motion' : 'Pause motion';
      button.setAttribute('aria-pressed', String(motionOff()));
      button.setAttribute('aria-label', button.textContent);
      button.disabled = reduced.matches;
      button.title = reduced.matches ? 'Following your device’s reduced-motion setting.' : 'Control decorative movement across the website.';
    });
    document.querySelectorAll('[data-depth-active]').forEach(element => element.removeAttribute('data-depth-active'));
  }
  document.addEventListener('click', event => {
    if (!event.target.closest('[data-motion-toggle]') || reduced.matches) return;
    paused = !paused;
    try { localStorage.setItem(key, paused ? 'off' : 'on'); } catch (_) {}
    syncMotion();
  });
  reduced.addEventListener('change', syncMotion);
  syncMotion();
  const syncVisibility = () => { root.dataset.pageVisible = String(!document.hidden); };
  document.addEventListener('visibilitychange', syncVisibility);
  syncVisibility();

  // A frame is requested only after input; there is no continuously running render loop.
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  document.querySelectorAll('[data-scene]').forEach(scene => {
    const viewport = scene.querySelector('.scene-viewport');
    const object = scene.querySelector('[data-scene-object]');
    if (!viewport || !object) return;
    const pool = scene.dataset.scene === 'pool';
    const initial = pool ? [57, -28] : [-12, -28];
    let x = initial[0], y = initial[1], drag = null, frame = 0;
    const paint = () => {
      frame = 0;
      object.style.setProperty('--scene-x', `${x}deg`);
      object.style.setProperty('--scene-y', `${y}deg`);
    };
    const render = () => { if (!frame) frame = requestAnimationFrame(paint); };
    function turn(deltaX, deltaY) {
      x = clamp(x + deltaX, pool ? 35 : -30, pool ? 72 : 25);
      y = pool ? clamp(y + deltaY, -70, 25) : ((y + deltaY + 540) % 360) - 180;
      render();
    }
    viewport.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      drag = {id:event.pointerId, x:event.clientX, y:event.clientY};
      viewport.setPointerCapture(event.pointerId);
    });
    viewport.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      // Keep vertical page scrolling native on touchscreens.
      turn(event.pointerType === 'mouse' ? -dy * .16 : 0, dx * (pool ? .2 : .65));
      drag.x = event.clientX; drag.y = event.clientY;
    });
    const endDrag = () => { drag = null; };
    viewport.addEventListener('pointerup', endDrag);
    viewport.addEventListener('pointercancel', endDrag);
    viewport.addEventListener('lostpointercapture', endDrag);
    viewport.addEventListener('keydown', event => {
      const steps = {ArrowLeft:[0,-8], ArrowRight:[0,8], ArrowUp:[-4,0], ArrowDown:[4,0]};
      if (steps[event.key]) { event.preventDefault(); turn(...steps[event.key]); }
      if (event.key === 'Home') { event.preventDefault(); x = initial[0]; y = initial[1]; render(); }
    });
    scene.querySelectorAll('[data-scene-turn]').forEach(button => button.addEventListener('click', () => turn(0, Number(button.dataset.sceneTurn) * 15)));
    scene.querySelector('[data-scene-reset]')?.addEventListener('click', () => { [x,y] = initial; render(); });
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => {
        scene.dataset.sceneVisible = String(entries[0].isIntersecting);
      }, {rootMargin:'80px'});
      observer.observe(scene);
    }
  });

  const stages = {
    infant:['Small splashes. A big beginning.', 'Infant aquatics from four months, with a parent or carer.', 'Explore infant aquatics'],
    learn:['Their next little leap.', 'Build breathing, floating and swimming skills in small groups.', 'Explore learn to swim'],
    stroke:['More skill. More possibility.', 'Develop technique and endurance with patient, personal coaching.', 'Explore stroke development']
  };
  document.querySelectorAll('[data-swim-stage]').forEach(button => button.addEventListener('click', () => {
    const id = button.dataset.swimStage;
    if (!stages[id]) return;
    const scene = button.closest('[data-scene]');
    scene.dataset.stage = id;
    scene.querySelectorAll('[data-swim-stage]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    scene.querySelector('.scene-caption h2').textContent = stages[id][0];
    scene.querySelector('[data-stage-description]').textContent = stages[id][1];
    const link = scene.querySelector('[data-stage-link]');
    link.href = `programs.html#${id}`;
    link.setAttribute('aria-label', stages[id][2]);
  }));

  document.querySelectorAll('[data-bottle-faces]').forEach(body => {
    const faces = document.createDocumentFragment();
    for (let index = 0; index < 20; index++) {
      const face = document.createElement('span');
      face.className = 'bottle-face';
      face.style.setProperty('--face-angle', `${index * 18}deg`);
      face.style.setProperty('--face-light', String(.77 + .3 * Math.cos((index * 18 - 35) * Math.PI / 180)));
      faces.append(face);
    }
    body.append(faces);
  });
  const colours = {navy:['#123b55','Midnight navy'],aqua:['#008ccb','Ocean blue'],sand:['#b49b66','Warm sand']};
  document.querySelectorAll('[data-bottle-colour]').forEach(button => button.addEventListener('click', () => {
    const selected = colours[button.dataset.bottleColour];
    if (!selected) return;
    const scene = button.closest('[data-scene]');
    scene.style.setProperty('--bottle-colour', selected[0]);
    scene.querySelector('[data-bottle-colour-name]').textContent = selected[1];
    scene.querySelectorAll('[data-bottle-colour]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  }));

  // Event delegation also covers cards loaded by the existing catalogue API.
  let depthTarget = null, depthFrame = 0, point = null;
  function clearDepth() {
    depthTarget?.removeAttribute('data-depth-active');
    depthTarget = null;
  }
  document.addEventListener('pointermove', event => {
    if (!finePointer.matches || motionOff()) return;
    const card = event.target.closest('.program-card,.collection-nav-card,.shop-card:not(.loading-card)');
    if (card !== depthTarget) { clearDepth(); depthTarget = card; }
    if (!card) return;
    point = [event.clientX, event.clientY];
    if (depthFrame) return;
    depthFrame = requestAnimationFrame(() => {
      depthFrame = 0;
      if (!depthTarget || motionOff()) return;
      const rect = depthTarget.getBoundingClientRect();
      depthTarget.style.setProperty('--depth-x', `${clamp((.5-(point[1]-rect.top)/rect.height)*5,-3,3)}deg`);
      depthTarget.style.setProperty('--depth-y', `${clamp(((point[0]-rect.left)/rect.width-.5)*5,-3,3)}deg`);
      depthTarget.dataset.depthActive = '';
    });
  }, {passive:true});
  document.documentElement.addEventListener('pointerleave', clearDepth);
  window.addEventListener('blur', clearDepth);
  if (document.querySelector('.site-header')) {
    const progress = document.createElement('div');
    progress.className = 'reading-progress';
    progress.setAttribute('aria-hidden','true');
    document.body.append(progress);
    let frame = 0;
    const update = () => {
      frame = 0;
      const distance = root.scrollHeight - innerHeight;
      progress.style.setProperty('--read-progress', String(distance > 0 ? clamp(scrollY / distance,0,1) : 0));
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    window.addEventListener('scroll', schedule, {passive:true});
    window.addEventListener('resize', schedule, {passive:true});
    update();
  }
})();
