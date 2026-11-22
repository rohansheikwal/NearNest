/* =============================================
   Neighborly — Main JavaScript
   ============================================= */

document.addEventListener('DOMContentLoaded', function() {

  // --- Password visibility toggle ---
  const eyeIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M2.06 12.35a1 1 0 0 1 0-.7C3.85 7.72 7.62 5 12 5s8.15 2.72 9.94 6.65a1 1 0 0 1 0 .7C20.15 16.28 16.38 19 12 19s-8.15-2.72-9.94-6.65Z"/><circle cx="12" cy="12" r="3"/></svg>';
  const eyeOffIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m3 3 18 18"/><path d="M10.58 10.58a2 2 0 0 0 2.83 2.83"/><path d="M9.88 5.09A10.94 10.94 0 0 1 12 5c4.38 0 8.15 2.72 9.94 6.65a1 1 0 0 1 0 .7 11.03 11.03 0 0 1-3.02 3.78"/><path d="M6.61 6.61a11.04 11.04 0 0 0-4.55 5.04 1 1 0 0 0 0 .7A10.98 10.98 0 0 0 12 19c1.61 0 3.13-.35 4.5-.98"/></svg>';
  document.querySelectorAll('input[type="password"]').forEach(input => {
    const wrapper = document.createElement('div');
    wrapper.className = 'password-field';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'password-toggle';
    toggle.setAttribute('aria-label', 'Show password');
    toggle.innerHTML = eyeIcon;
    toggle.addEventListener('click', () => {
      const isVisible = input.type === 'text';
      input.type = isVisible ? 'password' : 'text';
      toggle.setAttribute('aria-label', isVisible ? 'Show password' : 'Hide password');
      toggle.innerHTML = isVisible ? eyeIcon : eyeOffIcon;
    });
    wrapper.appendChild(toggle);
  });

  // --- CSRF Token helper ---
  function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
           document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1] || '';
  }

  // --- Per-Tab Portal Management ---
  const activePortal = (function() {
    try {
      const bodyPortal = document.body?.dataset?.portal;
      const urlParams = new URLSearchParams(window.location.search);
      const urlPortal = urlParams.get('portal');
      const isProviderPath = window.location.pathname.startsWith('/services/provider/') ||
                             window.location.pathname.startsWith('/admin/');
      const isCustomerPath = window.location.pathname.startsWith('/accounts/dashboard/') ||
                             window.location.pathname.startsWith('/bookings/');

      let portal = urlPortal || (isProviderPath ? 'provider' : (isCustomerPath ? 'customer' : bodyPortal));
      if (portal) {
        sessionStorage.setItem('nearnest_portal', portal);
      } else {
        portal = sessionStorage.getItem('nearnest_portal') || 'customer';
      }
      return portal;
    } catch (e) {
      return 'customer';
    }
  })();

  // Synchronize internal links and forms with active tab's portal
  if (activePortal === 'provider') {
    document.querySelectorAll('a[href]').forEach(link => {
      const href = link.getAttribute('href');
      if (href && !href.startsWith('#') && !href.startsWith('javascript:') && !href.startsWith('mailto:')) {
        try {
          const url = new URL(href, window.location.origin);
          if (url.origin === window.location.origin && !url.searchParams.has('portal') &&
              !url.pathname.startsWith('/accounts/logout/')) {
            url.searchParams.set('portal', 'provider');
            link.setAttribute('href', url.pathname + url.search + url.hash);
          }
        } catch (err) {}
      }
    });

    document.querySelectorAll('form').forEach(form => {
      if (!form.querySelector('input[name="portal"]')) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'portal';
        input.value = 'provider';
        form.appendChild(input);
      }
    });
  }

  // --- Alert auto-dismiss ---
  const alerts = document.querySelectorAll('.auto-dismiss');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 4500);
  });

  // --- Save Service Toggle ---
  document.querySelectorAll('.save-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      const serviceId = this.dataset.serviceId;
      const url = `/bookings/saved/toggle/${serviceId}/`;

      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
          'X-NearNest-Portal': activePortal,
        }
      })
      .then(res => res.json())
      .then(data => {
        if (data.saved) {
          this.classList.add('saved');
          this.title = 'Remove from saved';
          this.querySelector('svg')?.setAttribute('fill', 'currentColor');
        } else {
          this.classList.remove('saved');
          this.title = 'Save service';
          this.querySelector('svg')?.setAttribute('fill', 'none');
        }
        showToast(data.message);
      })
      .catch(() => {
        // If not logged in, redirect
        window.location.href = '/accounts/login/?next=' + window.location.pathname;
      });
    });
  });

  // --- Save Service Detail Button (on service_detail page) ---
  const saveDetailBtn = document.getElementById('save-detail-btn');
  if (saveDetailBtn) {
    saveDetailBtn.addEventListener('click', function(e) {
      e.preventDefault();
      const serviceId = this.dataset.serviceId;
      const url = `/bookings/saved/toggle/${serviceId}/`;

      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
          'X-NearNest-Portal': activePortal,
        }
      })
      .then(res => res.json())
      .then(data => {
        const textSpan = this.querySelector('.save-btn-text');
        const svg = this.querySelector('svg');
        if (data.saved) {
          this.classList.remove('btn-outline-primary');
          this.classList.add('btn-secondary');
          if (textSpan) textSpan.textContent = 'Saved';
          if (svg) {
            svg.setAttribute('fill', 'currentColor');
            svg.setAttribute('stroke-width', '2');
          }
        } else {
          this.classList.remove('btn-secondary');
          this.classList.add('btn-outline-primary');
          if (textSpan) textSpan.textContent = 'Save Service';
          if (svg) {
            svg.setAttribute('fill', 'none');
            svg.setAttribute('stroke-width', '2.5');
          }
        }
        showToast(data.message);
      })
      .catch(() => {
        window.location.href = '/accounts/login/?next=' + encodeURIComponent(window.location.pathname);
      });
    });
  }

  // --- Toast notifications ---
  function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `neighborly-toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('visible'), 50);
    setTimeout(() => {
      toast.classList.remove('visible');
      setTimeout(() => toast.remove(), 400);
    }, 3000);
  }
  window.showToast = showToast;

  // --- FAQ Accordion ---
  document.querySelectorAll('.faq-question').forEach(btn => {
    btn.addEventListener('click', function() {
      const answer = this.nextElementSibling;
      const isOpen = answer.style.display === 'block';
      // Close all
      document.querySelectorAll('.faq-answer').forEach(a => a.style.display = 'none');
      document.querySelectorAll('.faq-toggle-icon').forEach(i => i.style.transform = 'rotate(0deg)');
      if (!isOpen) {
        answer.style.display = 'block';
        const icon = this.querySelector('.faq-toggle-icon');
        if (icon) icon.style.transform = 'rotate(180deg)';
      }
    });
  });

  // --- Interactive star rating ---
  const ratingInputs = document.querySelectorAll('.rating-radio');
  ratingInputs.forEach(input => {
    input.addEventListener('change', function() {
      const val = parseInt(this.value);
      document.querySelectorAll('.rating-star-label').forEach((label, idx) => {
        const labelVal = parseInt(label.dataset.value);
        label.style.color = labelVal <= val ? 'var(--color-accent)' : 'var(--color-border)';
      });
    });
  });

  // --- Service image preview ---
  const imageInput = document.getElementById('id_image');
  const imagePreview = document.getElementById('image-preview');
  if (imageInput && imagePreview) {
    imageInput.addEventListener('change', function() {
      const file = this.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = e => {
          imagePreview.src = e.target.result;
          imagePreview.style.display = 'block';
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // --- Request status colour ---
  document.querySelectorAll('[data-status]').forEach(el => {
    const s = el.dataset.status;
    const cls = {
      pending: 'badge-warning',
      accepted: 'badge-info',
      rejected: 'badge-danger',
      inprogress: 'badge-primary',
      completed: 'badge-success',
      cancelled: 'badge-secondary',
    }[s];
    if (cls) el.classList.add(cls);
  });

  // --- Smooth scrolling for anchor links ---
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', function(e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // --- Filter form: auto-submit on select change ---
  document.querySelectorAll('.auto-submit').forEach(el => {
    el.addEventListener('change', function() {
      this.closest('form')?.submit();
    });
  });

  // --- Service card image fallback ---
  document.querySelectorAll('img[data-fallback]').forEach(img => {
    img.addEventListener('error', function() {
      this.src = this.dataset.fallback;
      this.onerror = null;
    });
  });

});

/* Toast CSS (inline for simplicity) */
(function injectToastStyles() {
  const style = document.createElement('style');
  style.textContent = `
    .neighborly-toast {
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: #234C3A;
      color: #fff;
      padding: 0.85rem 1.25rem;
      border-radius: 10px;
      font-size: 0.9rem;
      font-family: 'Manrope', sans-serif;
      font-weight: 500;
      z-index: 9999;
      box-shadow: 0 8px 24px rgba(0,0,0,0.18);
      opacity: 0;
      transform: translateY(10px);
      transition: opacity 0.3s ease, transform 0.3s ease;
      max-width: 300px;
    }
    .neighborly-toast.visible { opacity: 1; transform: translateY(0); }
    .neighborly-toast.toast-error { background: #DC2626; }
    .neighborly-toast.toast-info { background: #2563EB; }
  `;
  document.head.appendChild(style);
})();
