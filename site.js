(function () {
  var header = document.querySelector('.site-header');
  var toggle = document.querySelector('.menu-toggle');
  var menu = document.querySelector('.mobile-menu');

  function syncHeader() {
    if (header) header.classList.toggle('scrolled', window.scrollY > 30);
  }

  function closeMenu() {
    if (!toggle || !menu) return;
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Abrir menu');
    menu.classList.remove('open');
    menu.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('menu-open');
  }

  if (toggle && menu) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
      menu.classList.toggle('open', open);
      menu.setAttribute('aria-hidden', String(!open));
      document.body.classList.toggle('menu-open', open);
    });
    menu.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', closeMenu); });
  }
  window.addEventListener('scroll', syncHeader, { passive: true });
  syncHeader();

  // Animações de entrada
  var items = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('is-visible'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px' });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add('is-visible'); });
  }

  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  // Formulário de contato: monta a mensagem e abre o WhatsApp da iSnap Labs
  var form = document.getElementById('contact-form');
  if (form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var f = form.elements;
      var ok = true;
      ['nome', 'email', 'mensagem'].forEach(function (n) {
        var bad = !f[n].value.trim() || (n === 'email' && !/^\S+@\S+\.\S+$/.test(f[n].value));
        f[n].classList.toggle('invalid', bad);
        if (bad) ok = false;
      });
      if (!ok) return;
      var txt = 'Olá, venho do site da iSnap Labs.\n\nNome: ' + f.nome.value.trim() +
        '\nE-mail: ' + f.email.value.trim() +
        (f.telefone.value.trim() ? '\nTelefone: ' + f.telefone.value.trim() : '') +
        '\n\n' + f.mensagem.value.trim();
      window.open('https://api.whatsapp.com/send?phone=' + form.dataset.wa + '&text=' + encodeURIComponent(txt), '_blank', 'noopener');
      if (window.gtag) gtag('event', 'generate_lead', { method: 'contact_form' });
      if (window.fbq) fbq('track', 'Lead');
    });
  }

  // Conversões: clique em botões/links do WhatsApp
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href*="api.whatsapp.com"]');
    if (!a) return;
    if (window.gtag) gtag('event', 'click_whatsapp', { link_url: a.href });
    if (window.fbq) fbq('track', 'Contact');
  });

  // Botão flutuante do WhatsApp: abre o pop-up de captação em vez de ir direto
  var waFloat = document.querySelector('.wa-float');
  var waModal = document.getElementById('wa-modal');
  var waForm = document.getElementById('wa-popup-form');
  if (waFloat && waModal && waForm) {
    var waLastFocus = null;

    function openWaModal() {
      waLastFocus = document.activeElement;
      waModal.classList.add('is-open');
      waModal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('wa-modal-open');
      var first = waForm.querySelector('input');
      if (first) first.focus();
    }
    function closeWaModal() {
      waModal.classList.remove('is-open');
      waModal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('wa-modal-open');
      if (waLastFocus) waLastFocus.focus();
    }

    waFloat.addEventListener('click', function (e) {
      e.preventDefault();
      openWaModal();
    });
    waModal.querySelectorAll('[data-wa-close]').forEach(function (el) {
      el.addEventListener('click', closeWaModal);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && waModal.classList.contains('is-open')) closeWaModal();
    });

    waForm.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var f = waForm.elements;
      var ok = true;
      ['nome', 'email', 'telefone'].forEach(function (n) {
        var bad = !f[n].value.trim() || (n === 'email' && !/^\S+@\S+\.\S+$/.test(f[n].value));
        f[n].classList.toggle('invalid', bad);
        if (bad) ok = false;
      });
      if (!f.robo.checked) ok = false;
      if (!ok) return;
      window.open(waFloat.getAttribute('href'), '_blank', 'noopener');
      if (window.gtag) {
        gtag('event', 'generate_lead', { method: 'whatsapp_popup', lead_name: f.nome.value.trim(), lead_email: f.email.value.trim() });
      }
      if (window.fbq) fbq('track', 'Lead');
      waForm.reset();
      closeWaModal();
    });
  }
})();
