(() => {
  'use strict';

  const ENDPOINT = '/api/public/support-tickets';
  const FOCUSABLE = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled]):not([type="hidden"])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  function initialiseSupportWidget() {
    if (document.querySelector('[data-hv-support-widget]')) return;

    const widget = document.createElement('div');
    widget.className = 'hv-support-widget';
    widget.dataset.hvSupportWidget = '';
    widget.innerHTML = `
      <button class="hv-support-launcher" type="button" data-support-open aria-label="Message HV Swim" aria-haspopup="dialog" aria-controls="hv-support-dialog" aria-expanded="false">
        <span class="hv-support-launcher-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" focusable="false"><path d="M4.5 6.75h15v10.5h-15z"></path><path d="m5.25 7.5 6.75 5 6.75-5"></path></svg>
        </span>
        <span class="hv-support-launcher-copy"><strong>Message HV Swim</strong><small>We’ll get back to you</small></span>
      </button>

      <dialog class="hv-support-dialog" id="hv-support-dialog" aria-labelledby="hv-support-title" aria-describedby="hv-support-description">
        <div class="hv-support-shell">
          <header class="hv-support-header">
            <button class="hv-support-close" type="button" data-hv-support-close aria-label="Close message form">
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m6.5 6.5 11 11M17.5 6.5l-11 11"></path></svg>
            </button>
            <div class="hv-support-eyebrow">Help &amp; support</div>
            <h2 id="hv-support-title">Message HV Swim</h2>
            <p id="hv-support-description">Send the team a clear message and keep the reference we return.</p>
            <div class="hv-support-not-live">
              <span aria-hidden="true"></span>
              <div><strong>This is not live chat.</strong><small>Messages are reviewed by the HV Swim team. For an emergency, call 000.</small></div>
            </div>
          </header>

          <div class="hv-support-account">
            <div>
              <strong>Already have a family account?</strong>
              <span>Open secure account messages to see your ticket history and replies.</span>
            </div>
            <a href="platform.html#messages">Open account messages <span aria-hidden="true">→</span></a>
          </div>

          <div class="hv-support-body">
            <form class="hv-support-form" id="hv-support-form" autocomplete="on">
              <div class="hv-support-grid">
                <div class="hv-support-field hv-support-field-wide">
                  <label for="hv-support-category">What can we help with? <span aria-hidden="true">*</span></label>
                  <select id="hv-support-category" name="category" required>
                    <option value="">Choose a topic</option>
                    <option value="lessons">Lessons and programs</option>
                    <option value="bookings">Bookings and availability</option>
                    <option value="billing">Billing and payments</option>
                    <option value="merchandise">Merchandise and uniforms</option>
                    <option value="pool_conditions">Pool conditions or closures</option>
                    <option value="accessibility_support">Accessibility or learning support</option>
                    <option value="app_help">Website or app help</option>
                    <option value="other">Something else</option>
                  </select>
                </div>

                <div class="hv-support-field">
                  <label for="hv-support-name">Your name <span aria-hidden="true">*</span></label>
                  <input id="hv-support-name" name="name" type="text" minlength="2" maxlength="100" autocomplete="name" required>
                </div>

                <div class="hv-support-field">
                  <label for="hv-support-email">Email address <span aria-hidden="true">*</span></label>
                  <input id="hv-support-email" name="email" type="email" maxlength="254" inputmode="email" autocomplete="email" required>
                </div>

                <div class="hv-support-field">
                  <label for="hv-support-phone">Phone <span>Optional</span></label>
                  <input id="hv-support-phone" name="phone" type="tel" maxlength="40" inputmode="tel" autocomplete="tel">
                </div>

                <div class="hv-support-field">
                  <label for="hv-support-subject">Subject <span aria-hidden="true">*</span></label>
                  <input id="hv-support-subject" name="subject" type="text" minlength="3" maxlength="120" required>
                </div>

                <div class="hv-support-field hv-support-field-wide">
                  <label for="hv-support-message">Message <span aria-hidden="true">*</span></label>
                  <textarea id="hv-support-message" name="message" rows="5" minlength="10" maxlength="2000" aria-describedby="hv-support-message-help" required></textarea>
                  <small id="hv-support-message-help">Please don’t include passwords or payment card details.</small>
                </div>

                <div class="hv-support-honeypot" aria-hidden="true">
                  <label for="hv-support-website">Website — leave this blank</label>
                  <input id="hv-support-website" name="website" type="text" tabindex="-1" autocomplete="off">
                </div>

                <label class="hv-support-consent hv-support-field-wide" for="hv-support-consent">
                  <input id="hv-support-consent" name="consent_acknowledged" type="checkbox" required>
                  <span>I understand this is not live chat and agree that HV Swim may use these details to respond. <a href="privacy.html" target="_blank" rel="noopener">Read the privacy notice</a>.</span>
                </label>
              </div>

              <p class="hv-support-error" id="hv-support-error" role="alert" tabindex="-1" hidden></p>

              <div class="hv-support-actions">
                <button class="hv-support-submit" type="submit" data-hv-support-submit>
                  <span data-hv-support-submit-label>Send message</span>
                  <span class="hv-support-spinner" aria-hidden="true"></span>
                </button>
                <button class="hv-support-secondary" type="button" data-hv-support-close>Cancel</button>
              </div>
            </form>

            <section class="hv-support-success" id="hv-support-success" aria-labelledby="hv-support-success-title" hidden>
              <span class="hv-support-success-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false"><path d="m5.5 12.5 4 4 9-9"></path></svg>
              </span>
              <div class="hv-support-success-kicker">Message received</div>
              <h3 id="hv-support-success-title" tabindex="-1">Thank you — it’s with the team.</h3>
              <p id="hv-support-success-message">HV Swim will review your message and respond using the details you supplied.</p>
              <div class="hv-support-reference">
                <span>Your reference</span>
                <strong id="hv-support-reference">—</strong>
              </div>
              <p class="hv-support-success-note">Keep this reference if you need to follow up. It is not saved on this device by the website.</p>
              <button class="hv-support-submit" type="button" data-hv-support-close>Done</button>
            </section>

            <p class="hv-support-live-region" id="hv-support-live-region" role="status" aria-live="polite"></p>
          </div>
        </div>
      </dialog>`;

    document.body.append(widget);
    if (document.querySelector('.mobile-book-bar, .shop-mobile-bar')) {
      document.body.classList.add('hv-support-has-mobile-bar');
    }

    const launcher = widget.querySelector('.hv-support-launcher');
    const dialog = widget.querySelector('.hv-support-dialog');
    const form = widget.querySelector('.hv-support-form');
    const submit = widget.querySelector('[data-hv-support-submit]');
    const submitLabel = widget.querySelector('[data-hv-support-submit-label]');
    const error = widget.querySelector('.hv-support-error');
    const success = widget.querySelector('.hv-support-success');
    const successTitle = widget.querySelector('#hv-support-success-title');
    const successMessage = widget.querySelector('#hv-support-success-message');
    const reference = widget.querySelector('#hv-support-reference');
    const liveRegion = widget.querySelector('#hv-support-live-region');
    const supportsNativeDialog = typeof dialog.showModal === 'function';

    let submitting = false;
    let successActive = false;
    let returnFocus = null;

    function visibleFocusables() {
      return [...dialog.querySelectorAll(FOCUSABLE)].filter(element => {
        return !element.hidden && element.tabIndex >= 0 && element.getClientRects().length > 0 && !element.closest('[aria-hidden="true"]');
      });
    }

    function setError(message = '') {
      error.textContent = message;
      error.hidden = !message;
      if (message) requestAnimationFrame(() => error.focus({ preventScroll:true }));
    }

    function setSubmitting(active) {
      submitting = active;
      submit.disabled = active;
      form.setAttribute('aria-busy', String(active));
      submit.classList.toggle('is-loading', active);
      submitLabel.textContent = active ? 'Sending…' : 'Send message';
      if (active) liveRegion.textContent = 'Sending your message.';
      else if (!successActive) liveRegion.textContent = '';
    }

    function resetView() {
      successActive = false;
      form.hidden = false;
      success.hidden = true;
      reference.textContent = '—';
      successMessage.textContent = 'HV Swim will review your message and respond using the details you supplied.';
      liveRegion.textContent = '';
      setError('');
      setSubmitting(false);
    }

    function finaliseClose() {
      document.body.classList.remove('hv-support-lock');
      launcher.setAttribute('aria-expanded', 'false');
      const target = returnFocus?.isConnected ? returnFocus : launcher;
      returnFocus = null;
      requestAnimationFrame(() => target.focus({ preventScroll:true }));
    }

    function closeDialog() {
      if (!dialog.open) return;
      if (supportsNativeDialog) dialog.close();
      else {
        dialog.removeAttribute('open');
        dialog.classList.remove('hv-support-dialog-fallback');
        finaliseClose();
      }
    }

    function openDialog(trigger = document.activeElement) {
      if (dialog.open) return;
      if (successActive) {
        form.reset();
        resetView();
      }
      setError('');
      returnFocus = trigger instanceof HTMLElement ? trigger : launcher;
      document.body.classList.add('hv-support-lock');
      launcher.setAttribute('aria-expanded', 'true');
      try {
        if (supportsNativeDialog) dialog.showModal();
        else {
          dialog.setAttribute('open', '');
          dialog.classList.add('hv-support-dialog-fallback');
        }
      } catch (_) {
        document.body.classList.remove('hv-support-lock');
        launcher.setAttribute('aria-expanded', 'false');
        return;
      }
      requestAnimationFrame(() => {
        const firstField = form.querySelector('select:not([disabled]), input:not([disabled])');
        (firstField || dialog.querySelector('[data-hv-support-close]'))?.focus({ preventScroll:true });
      });
    }

    function apiMessage(payload, status) {
      if (status === 429) return 'Too many messages have been sent from this connection. Please wait and try again.';
      if (Array.isArray(payload?.detail)) {
        return payload.detail.map(item => item?.msg).filter(Boolean).join(' ') || 'Please check the form and try again.';
      }
      if (typeof payload?.detail === 'string') return payload.detail;
      if (typeof payload?.message === 'string' && status >= 400) return payload.message;
      return 'We couldn’t send your message right now. Please try again, or use the phone or email details in the website footer.';
    }

    async function sendMessage(event) {
      event.preventDefault();
      if (submitting) return;
      setError('');

      if (!form.checkValidity()) {
        form.reportValidity();
        form.querySelector(':invalid')?.focus({ preventScroll:true });
        return;
      }

      const fields = form.elements;
      const payload = {
        category: fields.category.value,
        name: fields.name.value.trim(),
        email: fields.email.value.trim(),
        phone: fields.phone.value.trim(),
        subject: fields.subject.value.trim(),
        message: fields.message.value.trim(),
        consent_acknowledged: fields.consent_acknowledged.checked,
        website: fields.website.value.trim()
      };
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 15000);
      setSubmitting(true);

      try {
        const response = await fetch(ENDPOINT, {
          method:'POST',
          credentials:'same-origin',
          headers:{ 'Accept':'application/json', 'Content-Type':'application/json' },
          body:JSON.stringify(payload),
          signal:controller.signal
        });
        let result = null;
        try { result = await response.json(); } catch (_) {}
        if (!response.ok) throw Object.assign(new Error('Support request failed'), { payload:result, status:response.status });
        if (!result?.reference && result?.id == null) throw new Error('The server did not return a message reference.');

        form.reset();
        form.hidden = true;
        success.hidden = false;
        successActive = true;
        reference.textContent = String(result.reference || `HV-${result.id}`);
        if (typeof result.message === 'string' && result.message.trim()) successMessage.textContent = result.message.trim();
        liveRegion.textContent = `Message received. Your reference is ${reference.textContent}.`;
        requestAnimationFrame(() => successTitle.focus({ preventScroll:true }));
      } catch (requestError) {
        const message = requestError?.name === 'AbortError'
          ? 'The request took too long. Please check your connection and try again.'
          : apiMessage(requestError?.payload, requestError?.status || 0);
        setError(message);
      } finally {
        window.clearTimeout(timeout);
        setSubmitting(false);
      }
    }

    document.addEventListener('click', event => {
      const openTrigger = event.target.closest('[data-support-open], a[href="#support"]');
      if (openTrigger) {
        event.preventDefault();
        openDialog(openTrigger);
        return;
      }
      if (event.target.closest('[data-hv-support-close]')) closeDialog();
    });

    form.addEventListener('submit', sendMessage);
    dialog.addEventListener('cancel', event => {
      event.preventDefault();
      closeDialog();
    });
    dialog.addEventListener('close', finaliseClose);
    dialog.addEventListener('click', event => {
      if (event.target === dialog) closeDialog();
    });
    dialog.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !supportsNativeDialog) {
        event.preventDefault();
        closeDialog();
        return;
      }
      if (event.key !== 'Tab') return;
      const stops = visibleFocusables();
      if (!stops.length) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = stops[0];
      const last = stops[stops.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    window.HVSwimSupport = Object.freeze({ open:openDialog, close:closeDialog });
    if (location.hash === '#support') openDialog(launcher);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialiseSupportWidget, { once:true });
  else initialiseSupportWidget();
})();
