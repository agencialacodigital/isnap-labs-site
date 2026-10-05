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
WA_POPUP_TEXT = 'Olá, estou vindo do site da iSnap Labs e gostaria de mais informações.'
WA_POPUP_URL = 'https://api.whatsapp.com/send?phone=%s&text=%s' % (WHATSAPP, WA_POPUP_TEXT.replace(' ', '%20'))
EMAIL = 'voe@isnap.com.br'

# Script de captação de leads do CRM para o pop-up de WhatsApp (presente em todas as
# páginas via whatsapp_widget_html). Carrega de forma assíncrona e não altera o
# comportamento do formulário, que continua abrindo o WhatsApp normalmente.
WA_LEAD_CAPTURE_SCRIPT = """<script>!function(){var k="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9tbnB2cml4ZHF0c2R6bWxyY2xqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg5ODkzMTcsImV4cCI6MjA5NDU2NTMxN30.cYOoc_iillMB-2RuJSj7H5SG5KAw2QmB8Rj6YfmL9S8",u="https://omnpvrixdqtsdzmlrclj.supabase.co/functions/v1/leadcapture-script/ffba4a5f-da30-48d0-ad38-5d697f1b5db9/4fe09358-b15d-41b3-b5c4-9bcbf1e7acfd";var x=new XMLHttpRequest;x.open("GET",u,!0),x.setRequestHeader("apikey",k),x.onload=function(){if(200===x.status){var s=document.createElement("script");s.textContent=x.responseText;(document.head||document.body).appendChild(s)}};x.send()}();</script>"""
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


# Auditoria de SEO: a Organization/WebSite herdada do WordPress tinha o nome preso ao
# posicionamento antigo ("...Pós Graduação ou MBA") e o logo apontando para um arquivo que
# não existe mais no site novo. Corrige só esses 3 campos; o resto do schema (datas, autor,
# breadcrumb, sameAs etc.) fica exatamente como veio do WordPress.
STALE_ORG_NAME = 'iSnap Labs - Transformando Infoprodutos em Pós Graduação ou MBA'
STALE_SITE_DESC = 'Transformando Infoprodutores em Empreendedores da Educação'
CURRENT_TAGLINE = ('Engenharia educacional para experts, infoprodutores e empresas que querem '
                    'transformar conhecimento em produtos educacionais de maior valor.')


def fix_stale_org_schema(graph):
    for node in graph:
        t = node.get('@type')
        if t in ('Organization', 'WebSite') and node.get('name') == STALE_ORG_NAME:
            node['name'] = 'iSnap Labs'
        if t == 'WebSite' and html.unescape(node.get('description', '')).strip() == STALE_SITE_DESC:
            node['description'] = CURRENT_TAGLINE
        if t == 'Organization':
            logo = node.get('logo')
            if isinstance(logo, dict) and 'logo-isnap-site.png' in (logo.get('url') or ''):
                logo['url'] = logo['contentUrl'] = ORIGIN + '/assets/isnap-logo.png'
                logo['width'], logo['height'] = 660, 220
                logo['caption'] = 'iSnap Labs'
    return graph


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
        if isinstance(y['schema'].get('@graph'), list):
            fix_stale_org_schema(y['schema']['@graph'])
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
            ('/faculdade-para-experts/', 'Faculdade para Experts'), ('/faculdade-in-company/', 'Faculdade In Company'),
            ('/universidade-corporativa/', 'Universidade Corporativa'), ('/arquitetura-educacional/', 'Arquitetura Educacional')]


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
      <a class="brand" href="/" aria-label="iSnap Labs, início"><img class="brand-logo" src="/assets/isnap-logo.png?v=%s" alt="iSnap Labs" width="165" height="40" /></a>
      <nav class="desktop-nav" aria-label="Navegação principal">%s</nav>
      <a class="nav-cta" href="%s" target="_blank" rel="noopener">Área do cliente <span>↗</span></a>
      <a class="header-button" href="%s" target="_blank" rel="noopener">Falar com especialista</a>
      <button class="menu-toggle" aria-label="Abrir menu" aria-expanded="false" aria-controls="mobile-menu"><span></span><span></span></button>
    </div>
    <div class="mobile-menu" id="mobile-menu" aria-hidden="true">
      <nav aria-label="Navegação móvel">%s%s<a href="%s" target="_blank" rel="noopener">Área do cliente</a><a href="%s" target="_blank" rel="noopener">Falar com especialista</a></nav>
    </div>
  </header>""" % (cls, VERSION, nav_links(current), esc(CLIENT_AREA_URL), esc(WA_URL), nav_links(current, True),
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
        <a class="brand footer-brand" href="/" aria-label="iSnap Labs, voltar ao início"><img class="brand-logo" src="/assets/isnap-logo.png?v=%s" alt="iSnap Labs" width="165" height="40" loading="lazy" /></a>
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
  </footer>""" % (DISCLAIMER, VERSION,
                  ''.join('<a href="%s">%s</a>' % (h, esc(l)) for h, l in SERVICES),
                  esc(ADDRESS), phones, EMAIL, EMAIL)


WA_ICON = ('<svg viewBox="0 0 32 32" fill="currentColor" aria-hidden="true"><path d="M16.004 3C9.096 3 3.48 8.56 3.48 15.4c0 2.42.666 4.68 1.823 6.62L3 29l7.2-2.26a12.98 12.98 0 0 0 5.8 1.37h.004c6.906 0 12.522-5.56 12.522-12.4C28.526 8.56 22.91 3 16.004 3Zm0 22.66h-.003a10.5 10.5 0 0 1-5.35-1.47l-.384-.23-4.273 1.34 1.36-4.17-.25-.43a10.28 10.28 0 0 1-1.58-5.5c0-5.68 4.63-10.3 10.483-10.3 5.85 0 10.48 4.62 10.48 10.3 0 5.68-4.63 10.46-10.483 10.46Zm5.74-7.73c-.31-.156-1.84-.91-2.126-1.015-.286-.104-.494-.156-.702.157-.207.312-.806 1.014-.988 1.222-.182.208-.364.234-.675.078-.31-.156-1.31-.486-2.496-1.55-.923-.828-1.546-1.85-1.728-2.163-.182-.312-.02-.48.137-.636.14-.14.311-.364.467-.546.156-.182.207-.312.311-.52.104-.208.052-.39-.026-.546-.078-.156-.702-1.705-.962-2.335-.253-.61-.51-.527-.702-.537l-.598-.01c-.207 0-.546.078-.832.39-.286.312-1.09 1.07-1.09 2.61 0 1.54 1.116 3.028 1.272 3.237.156.208 2.195 3.38 5.318 4.74.743.323 1.323.516 1.775.66.746.238 1.424.205 1.96.124.598-.09 1.84-.753 2.1-1.48.26-.728.26-1.352.182-1.482-.078-.13-.285-.208-.597-.364Z"/></svg>')


def whatsapp_widget_html():
    return """<a class="wa-float" href="%s" target="_blank" rel="noopener" aria-label="Falar no WhatsApp" data-wa-fallback>
    <span class="wa-float-ping" aria-hidden="true"></span>
    %s
  </a>

  <div class="wa-modal" id="wa-modal" aria-hidden="true">
    <div class="wa-modal-backdrop" data-wa-close></div>
    <div class="wa-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="wa-modal-title">
      <header class="wa-modal-head">
        <h2 id="wa-modal-title">Olá! Preencha os campos abaixo para iniciar a conversa no WhatsApp</h2>
        <button type="button" class="wa-modal-close" data-wa-close aria-label="Fechar">×</button>
      </header>
      <form class="wa-modal-body" id="wa-popup-form" novalidate>
        <label class="wa-field"><span class="sr-only">Nome</span><input type="text" name="nome" placeholder="Nome" autocomplete="name" required /></label>
        <label class="wa-field"><span class="sr-only">E-mail</span><input type="email" name="email" placeholder="E-mail" autocomplete="email" required /></label>
        <label class="wa-field"><span class="sr-only">WhatsApp</span><input type="tel" name="telefone" placeholder="WhatsApp" autocomplete="tel" required /></label>
        <label class="wa-robot"><input type="checkbox" name="robo" required /><span>Não sou um robô</span></label>
        <button type="submit" class="wa-submit">%s Iniciar a conversa</button>
        <p class="wa-consent">Ao informar meus dados, eu concordo com a <a href="/politica-de-privacidade/">Política de Privacidade</a>.</p>
      </form>
    </div>
  </div>

  """ % (esc(WA_POPUP_URL), WA_ICON, WA_ICON)


def layout(path, seo, body, current=None, home=False, extra_scripts=''):
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

  %s
  <script src="/site.js?v=%s"></script>
  %s
  %s
</body>
</html>
""" % (seo, VERSION, VERSION, TRACKING, 'home-page' if home else 'inner-page', header_html(current, home), body, footer_html(),
       whatsapp_widget_html(), VERSION, WA_LEAD_CAPTURE_SCRIPT, extra_scripts)


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
