const header = document.querySelector('.site-header');
const menuToggle = document.querySelector('.menu-toggle');
const mobileMenu = document.querySelector('.mobile-menu');

function syncHeader() {
  header.classList.toggle('scrolled', window.scrollY > 30);
}

function closeMenu() {
  menuToggle.setAttribute('aria-expanded', 'false');
  menuToggle.setAttribute('aria-label', 'Abrir menu');
  mobileMenu.classList.remove('open');
  mobileMenu.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('menu-open');
}

menuToggle.addEventListener('click', () => {
  const willOpen = menuToggle.getAttribute('aria-expanded') !== 'true';
  menuToggle.setAttribute('aria-expanded', String(willOpen));
  menuToggle.setAttribute('aria-label', willOpen ? 'Fechar menu' : 'Abrir menu');
  mobileMenu.classList.toggle('open', willOpen);
  mobileMenu.setAttribute('aria-hidden', String(!willOpen));
  document.body.classList.toggle('menu-open', willOpen);
});

document.querySelectorAll('.mobile-menu a').forEach((link) => link.addEventListener('click', closeMenu));
window.addEventListener('scroll', syncHeader, { passive: true });
syncHeader();

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.12, rootMargin: '0px 0px -40px' });

document.querySelectorAll('.reveal').forEach((element) => observer.observe(element));
document.getElementById('year').textContent = new Date().getFullYear();
