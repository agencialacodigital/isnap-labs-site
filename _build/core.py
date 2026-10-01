"""Núcleo do gerador: leitura do conteúdo WordPress, parser do Elementor, SEO e layout."""
import html
import json
import os
import re
import time
from html.parser import HTMLParser

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(os.path.dirname(__file__), 'source')
ORIGIN = 'https://isnap.com.br'

WHATSAPP = '554499922804'
WA_TEXT = 'Olá, venho do site da iSnap Labs e quero agendar uma consultoria estratégica.'
WA_URL = 'https://api.whatsapp.com/send?phone=%s&text=%s' % (WHATSAPP, WA_TEXT.replace(' ', '%20'))
EMAIL = 'voe@isnap.com.br'
CLIENT_AREA_URL = 'https://app.isnap.com.br/'
ADDRESS = 'Av. Advogado Horácio Raccanello Filho, 5570 – Zona 07, Maringá / PR – CEP 87020-035'
PHONES = [('(44) 99992-2804', '+5544999922804')]
DISCLAIMER = ('A iSnap Labs é uma empresa privada de consultoria educacional. Não é instituição de ensino superior '
              'e não concede autorização, credenciamento ou reconhecimento do MEC. A oferta e a certificação de cursos '
              'são de responsabilidade das instituições de ensino e dos órgãos competentes.')

MESES = ['jan.', 'fev.', 'mar.', 'abr.', 'mai.', 'jun.', 'jul.', 'ago.', 'set.', 'out.', 'nov.', 'dez.']


def load(name):
    with open(os.path.join(SRC, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def esc(s):
    return html.escape(s or '', quote=True)


def fmt_date(iso):
    y, m, d = iso[:10].split('-')
    return '%d %s %s' % (int(d), MESES[int(m) - 1], y)


# ---------------------------------------------------------------- URLs / imagens
UPLOADS_RE = re.compile(r'https?://(?:www\.)?isnap\.com\.br/wp-content/uploads/[^\s"\'<>()]+')
IMAGES = set()


def localize(text):
    """Reescreve URLs internas para caminhos relativos à raiz e registra as imagens a baixar."""
    if not text:
        return text
    for m in UPLOADS_RE.findall(text):
        IMAGES.add(m.split(' ')[0])
    text = re.sub(r'https?://(?:www\.)?isnap\.com\.br/', '/', text)
    text = text.replace('href="/offer-details/"', 'href="/consultoria-mentoria/"')
    return text


def fix_href(href):
    if not href:
        return href
    if href.startswith('#elementor-action'):
        return WA_URL
    href = re.sub(r'^https?://(?:www\.)?isnap\.com\.br', '', href) or '/'
    href = href.rstrip('/') + '/' if href.startswith('/') and '.' not in href.split('/')[-1] and '?' not in href else href
    if href in ('/offer-details/',):
        href = '/consultoria-mentoria/'
    if href == '/blog':
        href = '/blog/'
    return href


def upload_path(url):
    """https://isnap.com.br/wp-content/uploads/x.jpg -> /wp-content/uploads/x.jpg"""
    return re.sub(r'^https?://(?:www\.)?isnap\.com\.br', '', url)


# ---------------------------------------------------------------- parser Elementor
INLINE_OK = {'strong', 'b', 'em', 'i', 'br', 'a', 'u'}


class Blocks(HTMLParser):
    """Converte HTML do Elementor em uma lista plana de blocos: h, p, img, btn, q, a."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.cur = None       # bloco em captura
        self.skip = 0
        self.div_stack = []   # True quando o div é elementor-tab-content
        self.in_tab = 0
        self.btn_href = None
        self.in_btn_text = False
        self.btn_text = ''
        self.in_btn = False

    # -- helpers
    def _start(self, kind, **kw):
        self._flush()
        self.cur = dict(kind=kind, html='', **kw)

    def _flush(self):
        if self.cur:
            txt = re.sub(r'[ \t\r\f\v]+', ' ', self.cur['html'])
            txt = re.sub(r'\s*<br\s*/?>\s*', '<br>', txt).strip()
            plain = re.sub(r'<[^>]+>', '', txt).strip()
            if plain:
                self.cur['html'] = txt
                self.blocks.append(self.cur)
            self.cur = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class') or ''
        if tag in ('style', 'script'):
            self.skip += 1
            return
        if tag == 'div':
            is_tab = 'elementor-tab-content' in cls
            self.div_stack.append(is_tab)
            if is_tab:
                self.in_tab += 1
            return
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self._start('h', level=int(tag[1]))
        elif tag == 'p' or tag == 'li':
            self._start('a' if self.in_tab else 'p')
        elif tag == 'img':
            src = a.get('src') or a.get('data-src') or ''
            if src:
                self._flush()
                self.blocks.append(dict(kind='img', src=src, alt=a.get('alt') or '',
                                        width=int(a.get('width') or 0), height=int(a.get('height') or 0), html=''))
        elif tag == 'a' and ('elementor-accordion-title' in cls or 'elementor-toggle-title' in cls):
            self._start('q')
        elif tag == 'a' and 'elementor-button' in cls:
            self._flush()
            self.in_btn = True
            self.btn_href = a.get('href')
            self.btn_text = ''
        elif tag == 'span' and self.in_btn and 'elementor-button-text' in cls:
            self.in_btn_text = True
        elif self.cur and tag in INLINE_OK:
            if tag == 'a':
                href = fix_href(a.get('href') or '')
                ext = ' target="_blank" rel="noopener"' if href.startswith('http') else ''
                self.cur['html'] += '<a href="%s"%s>' % (esc(href), ext)
            elif tag == 'br':
                self.cur['html'] += '<br>'
            else:
                self.cur['html'] += '<%s>' % tag

    def handle_endtag(self, tag):
        if tag in ('style', 'script'):
            self.skip -= 1
            return
        if tag == 'div':
            if self.div_stack and self.div_stack.pop():
                self.in_tab -= 1
                self._flush()
            return
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li'):
            self._flush()
        elif tag == 'a' and self.cur and self.cur['kind'] == 'q':
            self._flush()
        elif tag == 'a' and self.in_btn:
            self.in_btn = False
            self.in_btn_text = False
            text = re.sub(r'\s+', ' ', self.btn_text).strip()
            if text:
                self.blocks.append(dict(kind='btn', html=text, href=fix_href(self.btn_href or ''), ))
        elif tag == 'span' and self.in_btn_text:
            self.in_btn_text = False
        elif self.cur and tag in INLINE_OK and tag != 'br':
            self.cur['html'] += '</%s>' % tag

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_btn_text:
            self.btn_text += data
        elif self.cur:
            self.cur['html'] += esc(data)

    def close(self):
        super().close()
        self._flush()


def parse_blocks(content_html):
    p = Blocks()
    p.feed(content_html)
    p.close()
    return p.blocks


def plain(h):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', h or '')).strip()


# ---------------------------------------------------------------- SEO / layout
def head_seo(y, path, fallback_title, fallback_desc=''):
    """Monta as tags <title>/<meta>/JSON-LD a partir dos metadados do Yoast."""
    y = y or {}
    def clean(t):
        return html.unescape(t or '').replace('(44) 3037-6030 ', '').replace('(44) 3037-6030', '')
    y = dict(y, **{k: clean(y[k]) for k in ('title', 'description', 'og_title', 'og_description') if y.get(k)})
    title = y.get('title') or fallback_title
    desc = y.get('description') or y.get('og_description') or fallback_desc
    canonical = ORIGIN + path
    robots = y.get('robots') or {}
    robots_txt = 'index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1'
    if robots.get('index') == 'noindex':
        robots_txt = 'noindex, follow'
    out = ['<title>%s</title>' % esc(title)]
    if desc:
        out.append('<meta name="description" content="%s">' % esc(desc))
    out.append('<meta name="robots" content="%s">' % robots_txt)
    out.append('<link rel="canonical" href="%s">' % esc(canonical))
    og_img = (y.get('og_image') or [{}])[0].get('url', '')
    og = [('og:locale', 'pt_BR'), ('og:type', y.get('og_type') or 'website'),
          ('og:title', y.get('og_title') or title), ('og:description', y.get('og_description') or desc),
          ('og:url', canonical), ('og:site_name', 'iSnap Labs')]
    if og_img:
        og.append(('og:image', og_img))
        IMAGES.add(og_img)
    if y.get('article_published_time'):
        og.append(('article:published_time', y['article_published_time']))
    if y.get('article_modified_time'):
        og.append(('article:modified_time', y['article_modified_time']))
    for k, v in og:
        out.append('<meta property="%s" content="%s">' % (k, esc(v)))
    out.append('<meta name="twitter:card" content="%s">' % esc(y.get('twitter_card') or 'summary_large_image'))
    if y.get('schema'):
        ld = json.dumps(y['schema'], ensure_ascii=False).replace('(44) 3037-6030 ', '').replace('(44) 3037-6030', '')
        out.append('<script type="application/ld+json">%s</script>' % ld)
    return '\n  '.join(out)


TRACKING = """<script async src="https://www.googletagmanager.com/gtag/js?id=G-L40Y7CEJPK"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-L40Y7CEJPK');
    gtag('config', 'AW-16453136249');
  </script>
  <script>
    !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
    fbq('init', '4701343299976079');
    fbq('track', 'PageView');
  </script>"""

NAV = [('/', 'Início'), ('/sobre-nos/', 'Sobre nós'), ('/solucoes/', 'Soluções'), ('/blog/', 'Blog'), ('/contato/', 'Contato')]
SERVICES = [('/pos-graduacao-ou-mba/', 'Pós-Graduação ou MBA'), ('/extensao-universitaria/', 'Extensão Universitária'),
            ('/consultoria-metep/', 'Consultoria METEP'), ('/consultoria-mentoria/', 'Consultoria Educacional')]


def nav_links(current, mobile=False):
    out = []
    for href, label in NAV:
        cur = ' aria-current="page"' if current == href else ''
        if href == '/solucoes/' and not mobile:
            sub = ''.join('<a href="%s">%s</a>' % (h, esc(l)) for h, l in SERVICES)
            out.append('<div class="nav-item has-sub"><a href="%s"%s>%s <small>▾</small></a>'
                       '<div class="nav-sub">%s</div></div>' % (href, cur, label, sub))
        else:
            out.append('<a href="%s"%s>%s</a>' % (href, cur, label))
    return ''.join(out)


def header_html(current, home=False):
    cls = 'site-header'
    return """<a class="skip-link" href="#conteudo">Ir para o conteúdo</a>
  <header class="%s" id="topo">
    <div class="nav-shell">
      <a class="brand" href="/" aria-label="iSnap Labs, início"><img class="brand-logo" src="/assets/isnap-logo.png" alt="iSnap Labs" width="165" height="40" /></a>
      <nav class="desktop-nav" aria-label="Navegação principal">%s</nav>
      <a class="nav-cta" href="%s" target="_blank" rel="noopener">Área do cliente <span>↗</span></a>
      <a class="header-button" href="%s" target="_blank" rel="noopener">Falar com especialista</a>
      <button class="menu-toggle" aria-label="Abrir menu" aria-expanded="false" aria-controls="mobile-menu"><span></span><span></span></button>
    </div>
    <div class="mobile-menu" id="mobile-menu" aria-hidden="true">
      <nav aria-label="Navegação móvel">%s%s<a href="%s" target="_blank" rel="noopener">Área do cliente</a><a href="%s" target="_blank" rel="noopener">Falar com especialista</a></nav>
    </div>
  </header>""" % (cls, nav_links(current), esc(CLIENT_AREA_URL), esc(WA_URL), nav_links(current, True),
                  ''.join('<a class="sub" href="%s">%s</a>' % (h, esc(l)) for h, l in SERVICES), esc(CLIENT_AREA_URL), esc(WA_URL))


def footer_html():
    phones = ' · '.join('<a href="tel:%s">%s</a>' % (t, l) for l, t in PHONES)
    return """<section class="legal-note">
      <div class="container">
        <span>Transparência iSnap</span>
        <p>%s</p>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <div class="container footer-top">
      <div>
        <a class="brand footer-brand" href="/" aria-label="iSnap Labs, voltar ao início"><img class="brand-logo" src="/assets/isnap-logo.png" alt="iSnap Labs" width="165" height="40" loading="lazy" /></a>
        <p class="footer-about">Transformando infoprodutores em empreendedores da educação.</p>
      </div>
      <nav class="footer-nav" aria-label="Rodapé">
        <strong>Navegação</strong>
        <a href="/sobre-nos/">Sobre nós</a><a href="/solucoes/">Soluções</a><a href="/blog/">Blog</a><a href="/contato/">Contato</a>
      </nav>
      <nav class="footer-nav" aria-label="Soluções">
        <strong>Soluções</strong>%s
      </nav>
      <div class="footer-contact">
        <strong>Contato</strong>
        <p>%s</p>
        <p>%s</p>
        <p><a href="mailto:%s">%s</a></p>
        <div class="footer-social"><a href="https://www.instagram.com/isnaplabs/" target="_blank" rel="noopener">Instagram ↗</a><a href="https://br.linkedin.com/company/isnaplabs" target="_blank" rel="noopener">LinkedIn ↗</a></div>
      </div>
    </div>
    <div class="container footer-bottom">
      <span>© <span id="year">2026</span> iSnap Labs Educação | Grupo Laço Digital</span>
      <a href="#topo">Voltar ao topo ↑</a>
    </div>
  </footer>""" % (DISCLAIMER,
                  ''.join('<a href="%s">%s</a>' % (h, esc(l)) for h, l in SERVICES),
                  esc(ADDRESS), phones, EMAIL, EMAIL)


def layout(path, seo, body, current=None, home=False):
    return """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="theme-color" content="#0c303d" />
  %s
  <link rel="icon" href="/wp-content/uploads/2023/10/favicon-isnap.png" />
  <link rel="apple-touch-icon" href="/wp-content/uploads/2023/10/favicon-isnap.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/styles.css?v=%s" />
  <link rel="stylesheet" href="/site.css?v=%s" />
  %s
</head>
<body class="%s">
  %s

  <main id="conteudo">
%s
  %s

  <script src="/site.js?v=%s"></script>
</body>
</html>
""" % (seo, VERSION, VERSION, TRACKING, 'home-page' if home else 'inner-page', header_html(current, home), body, footer_html(), VERSION)


VERSION = str(int(time.time()))


def write(path, content):
    """path como '/blog/' -> ROOT/blog/index.html"""
    rel = path.strip('/')
    out = os.path.join(ROOT, rel, 'index.html') if rel else os.path.join(ROOT, 'index.html')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(content)


def cta_button(label='Agendar consultoria', cls='button-primary'):
    return '<a class="button %s" href="%s" target="_blank" rel="noopener">%s <span>↗</span></a>' % (cls, esc(WA_URL), esc(label))
