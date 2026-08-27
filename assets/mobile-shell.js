(() => {
  'use strict';
  const configured = document.body.dataset.appUrl || '';
  const appUrl = configured.includes('__HV_') ? location.origin : configured.replace(/\/$/, '');
  const card = document.getElementById('connection-card');
  const title = document.getElementById('connection-title');
  const detail = document.getElementById('connection-detail');
  const open = document.getElementById('open-connected-app');

  async function checkConnection() {
    card.className = 'connection-card'; title.textContent = 'Checking connection…'; detail.textContent = appUrl; open.disabled = true;
    try {
      const response = await fetch(`${appUrl}/api/health`, { headers:{ Accept:'application/json' }, cache:'no-store', signal:AbortSignal.timeout?.(6000) });
      if (!response.ok) throw new Error('Unavailable');
      const health = await response.json();
      card.classList.add('online'); title.textContent = 'HV Swim is online'; detail.textContent = `${health.service} · secure connection ready`; open.disabled = false;
    } catch (_) {
      card.classList.add('offline'); title.textContent = navigator.onLine ? 'Platform unavailable' : 'You are offline'; detail.textContent = 'Reconnect, then check again. Saved app files remain on this device.';
    }
  }
  open.addEventListener('click', () => { location.href = `${appUrl}/app.html?native=1`; });
  document.getElementById('retry-connection').addEventListener('click', checkConnection);
  window.addEventListener('online', checkConnection); window.addEventListener('offline', checkConnection);
  checkConnection();
})();
