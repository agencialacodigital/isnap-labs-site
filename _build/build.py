#!/usr/bin/env python3
"""Gera o site estático da iSnap Labs a partir do conteúdo exportado do WordPress.

Uso:  python3 _build/build.py            (gera HTML)
      python3 _build/build.py --images   (também baixa as imagens de /wp-content/uploads)
"""
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from core import *  # noqa: F401,F403
import core

PAGES = {p['slug']: p for p in load('pages')}
POSTS = sorted(load('posts'), key=lambda p: p['date'], reverse=True)
CATS = {c['id']: c for c in load('categories')}
TAGS = {t['id']: t for t in load('tags')}
POST_BY_ID = {p['id']: p for p in POSTS}

TIER_CLASSES = ('', ' x-section--black', ' x-section--light')

DECOR_NAMES = ('traco', 'carraca', 'assinale-dentro', 'foguete', 'conselheiro-financeiro',
               'curso-online', 'certificado-digital', '/curso.png', 'elementor/thumbs', 'ai2-contact-pic')


# Textos que faltavam no site original (fornecidos pela iSnap)
BENEFIT_TEXT = {
    'Vantagem competitiva para Programas e Cursos': 'Infoprodutores que transformam seus cursos em programas acadêmicos reconhecidos ganham uma vantagem competitiva única, destacando-se no mercado.',
}


# Vitrine "De especialistas a empreendedores da educação" — PLACEHOLDER.
# Troque por nome, nicho e foto reais de cada expert (ver _build/README das imagens em assets/experts/).
EXPERTS = [
    ('Matheus Moretti - NaFazenda', 'Pecuária', 'assets/experts/matheus-moretti.jpg'),
    ('Carmen Perez', 'Bem-Estar Animal', 'assets/experts/carmen-peres.jpg'),
    ('Nathalia Durval', 'Leilão de Imóveis', 'assets/experts/nathalia-durval.jpg'),
    ('Victor Oliveira', 'Leilão de Imóveis', 'assets/experts/victor-oliveira.jpg'),
    ('Prof. Dra. Sandra Puliezi', 'Educação', 'assets/experts/sandra-puliezi.jpg'),
]


def page_path(p):
    return '/' if p['slug'] == 'home' else '/%s/' % p['slug']


def is_decor(b):
    src = b['src']
    return any(n in src for n in DECOR_NAMES) or (0 < b['width'] < 300)


def paras(h, single_br=False):
    """Divide um bloco em vários parágrafos onde o editor usou <br><br> (ou <br>, se single_br)."""
    parts = [x.strip() for x in re.split(r'(?:<br>)+' if single_br else r'(?:<br>){2,}', h) if x.strip()]
    return ['<p>%s</p>' % re.sub(r'^(<br>)+|(<br>)+$', '', x) for x in parts]


def thumb(post, size='medium_large'):
    """URL local da imagem destacada (usa um tamanho intermediário quando existir)."""
    media = (post.get('_embedded', {}).get('wp:featuredmedia') or [None])[0]
    if not media or 'source_url' not in media:
        return None, 0, 0, ''
    sizes = (media.get('media_details') or {}).get('sizes') or {}
    pick = sizes.get(size) or sizes.get('large') or sizes.get('medium') or {}
    url = pick.get('source_url') or media['source_url']
    w = pick.get('width') or (media.get('media_details') or {}).get('width') or 0
    h = pick.get('height') or (media.get('media_details') or {}).get('height') or 0
    core.IMAGES.add(url)
    return upload_path(url), w, h, media.get('alt_text') or ''


def excerpt(p, n=28):
    t = html.unescape(re.sub(r'<[^>]+>', ' ', p.get('excerpt', {}).get('rendered', '')))
    w = re.sub(r'\s+', ' ', t).strip().split(' ')
    return ' '.join(w[:n]) + ('…' if len(w) > n else '')


def post_card(p, featured=False, summary=False):
    src, w, h, alt = thumb(p)
    cats = [CATS[c]['name'] for c in p['categories'] if c in CATS and CATS[c]['slug'] != 'uncategorized']
    img = ('<img src="%s" alt="%s" width="%s" height="%s" loading="lazy" />' % (src, esc(alt), w, h)) if src else ''
    return """<a class="article-card%s reveal" href="/%s/">
          <div class="article-art has-img">%s</div>
          <div class="article-meta"><span>%s</span><time datetime="%s">%s</time></div>
          <h3>%s</h3>%s
          <span class="article-arrow">↗</span>
        </a>""" % (' article-featured' if featured else '', p['slug'], img, esc(cats[0] if cats else 'Blog'),
                   p['date'][:10], fmt_date(p['date']), html.unescape(p['title']['rendered']),
                   ('<p class="x-excerpt">%s</p>' % esc(excerpt(p))) if summary else '')


def hero(title, lede='', crumbs=None):
    crumb = ''
    if crumbs:
        crumb = '<div class="breadcrumb"><a href="/">Início</a>%s</div>' % ''.join(
            '<span>/</span>' + ('<a href="%s">%s</a>' % (h, esc(l)) if h else '<span>%s</span>' % esc(l)) for h, l in crumbs)
    return """    <section class="inner-hero">
      <div class="container">
        %s
        <h1>%s</h1>
        %s
      </div>
    </section>""" % (crumb, title, ('<p>%s</p>' % lede) if lede else '')


def cta_section(title, text='', buttons=None, eyebrow=''):
    btns = ''
    if buttons:
        for n, (label, href) in enumerate(buttons):
            ext = ' target="_blank" rel="noopener"' if href.startswith('http') else ''
            btns += '<a class="button %s" href="%s"%s>%s <span>↗</span></a>' % (
                'button-primary' if n == 0 else 'button-light', esc(href), ext, esc(label))
    else:
        btns = cta_button('Falar com um consultor', 'button-primary')
    return """    <section class="x-cta">
      <div class="container">
        <div class="page-cta">
          <div>%s<h2>%s</h2>%s</div>
          <div class="x-cta-btns">%s</div>
        </div>
      </div>
    </section>""" % (eyebrow, title, ('<p>%s</p>' % text) if text else '', btns)


def big_cta_section(title, text, buttons, eyebrow):
    """CTA final no mesmo layout grande da home (hero escuro com círculo decorativo)."""
    btns = ''
    for n, (label, href) in enumerate(buttons):
        ext = ' target="_blank" rel="noopener"' if href.startswith('http') else ''
        if n == 0:
            btns += '<a class="button button-light" href="%s"%s>%s <span>↗</span></a>' % (esc(href), ext, esc(label))
        else:
            btns += '<a class="text-link" href="%s"%s>%s <span>↗</span></a>' % (esc(href), ext, esc(label))
    return """    <section class="cta-section cta-section--page">
      <div class="cta-noise"></div>
      <div class="container cta-content reveal">
        %s
        <h2>%s</h2>
        <p>%s</p>
        <div class="cta-actions">%s</div>
      </div>
    </section>""" % (eyebrow, title, text, btns)


# ---------------------------------------------------------------- páginas genéricas (Elementor)
def render_generic(page, start_tier=0, big_cta=False, cta_text=''):
    B = parse_blocks(localize(page['content']['rendered']))
    B = [b for b in B if not (b['kind'] == 'img' and is_decor(b))]
    i = 0
    title = ''
    lede = ''
    if B and B[0]['kind'] == 'h' and B[0]['level'] == 1:
        title = B[0]['html']
        i = 1
        if i < len(B) and B[i]['kind'] == 'p':
            lede = B[i]['html']
            i += 1
        elif i < len(B) and B[i]['kind'] == 'h' and B[i]['level'] == 2 and not plain(B[i]['html']).isdigit():
            lede = B[i]['html']
            i += 1
    out = []
    sec = []          # blocos HTML do corpo da seção corrente
    shead = []        # rótulo + título da seção corrente
    pending = []      # rótulo (H6) que antecede o próximo H2
    tier = [start_tier]  # alterna o fundo das seções: azul / preto / cinza-claro

    def next_tier():
        cls = TIER_CLASSES[tier[0] % len(TIER_CLASSES)]
        tier[0] += 1
        return cls

    def close():
        if shead and sec:
            out.append('    <section class="x-section%s"><div class="container x-split"><div class="x-split-head">%s</div>'
                       '<div class="x-split-body">%s</div></div></section>' % (next_tier(), ''.join(shead), '\n'.join(sec)))
        elif shead:
            out.append('    <section class="x-section%s"><div class="container x-statement">%s</div></section>' % (next_tier(), ''.join(shead)))
        elif sec:
            out.append('    <section class="x-section%s"><div class="container x-prose">%s</div></section>' % (next_tier(), '\n'.join(sec)))
        del shead[:]
        del sec[:]

    n = len(B)
    while i < n:
        b = B[i]
        k = b['kind']
        # cartões numerados: H2 "1" + H5 + P
        if k == 'h' and b['level'] == 2 and plain(b['html']).isdigit():
            cards = []
            while i < n and B[i]['kind'] == 'h' and B[i]['level'] == 2 and plain(B[i]['html']).isdigit():
                num = plain(B[i]['html'])
                i += 1
                head = ''
                body = []
                if i < n and B[i]['kind'] == 'h':
                    head = B[i]['html']
                    i += 1
                while i < n and B[i]['kind'] == 'p':
                    body += paras(B[i]['html'])
                    i += 1
                cards.append('<article class="x-card"><span class="x-num">%02d</span><h3>%s</h3>%s</article>'
                             % (int(num), head, ''.join(body)))
            close()
            out.append('    <section class="x-section x-benefits%s"><div class="container"><div class="x-grid x-grid-%d">%s</div></div></section>'
                       % (next_tier(), min(len(cards), 3), ''.join(cards)))
            continue
        # FAQ
        if k == 'q':
            items = []
            while i < n and B[i]['kind'] == 'q':
                q = B[i]['html']
                i += 1
                ans = []
                while i < n and B[i]['kind'] == 'a':
                    ans += paras(B[i]['html'])
                    i += 1
                items.append('<details><summary>%s</summary><div>%s</div></details>' % (q, ''.join(ans)))
            sec.append('<div class="x-faq">%s</div>' % ''.join(items))
            continue
        # H2 = nova seção; H2 seguido só de botões (até o fim) = CTA final
        if k == 'h' and b['level'] == 2:
            j = i + 1
            btns = []
            while j < n and B[j]['kind'] in ('btn', 'p'):
                if B[j]['kind'] == 'btn':
                    label, href = plain(B[j]['html']), B[j]['href']
                else:
                    m = re.fullmatch(r'<a href="([^"]*)"[^>]*>(.*?)</a>', B[j]['html'].strip(), re.S)
                    if not m:
                        break
                    href, label = html.unescape(m.group(1)), re.sub(r'\s+', ' ', m.group(2)).strip()
                if all(label != x[0] for x in btns):
                    btns.append((label, href))
                j += 1
            if j == n and btns:
                close()
                final_btns = [x for x in btns if x[1] not in ('#', '')]
                if big_cta and final_btns:
                    out.append(big_cta_section(b['html'], cta_text, list(reversed(final_btns)), ''.join(pending)))
                else:
                    out.append(cta_section(b['html'], buttons=final_btns or None, eyebrow=''.join(pending)))
                del pending[:]
                i = j
                continue
            close()
            shead.extend(pending)
            del pending[:]
            shead.append('<h2>%s</h2>' % b['html'])
            i += 1
            continue
        # grupos de H3/H4/H5 + P (+ botão) -> grade de cartões
        if k == 'h' and b['level'] in (3, 4, 5):
            run = []
            j = i
            while j < n and B[j]['kind'] == 'h' and B[j]['level'] in (3, 4, 5):
                head = B[j]['html']
                j += 1
                body = []
                link = None
                while j < n and B[j]['kind'] in ('p', 'img') and not (B[j]['kind'] == 'img'):
                    body += paras(B[j]['html'])
                    j += 1
                if j < n and B[j]['kind'] == 'btn':
                    link = B[j]
                    j += 1
                if not body:
                    break
                run.append((head, body, link))
            if len(run) >= 2:
                cards = []
                for head, body, link in run:
                    a = ''
                    if link and link['href'] not in ('#', ''):
                        a = '<a class="x-more" href="%s">%s <span>↗</span></a>' % (esc(link['href']), esc(plain(link['html'])))
                    cards.append('<article class="x-card"><h3>%s</h3>%s%s</article>' % (head, ''.join(body), a))
                sec.append('<div class="x-grid x-grid-3">%s</div>' % ''.join(cards))
                i = j
                continue
            sec.append('<h3>%s</h3>' % b['html'])
            i += 1
            continue
        if k == 'h':  # H1 extra / H6
            if b['level'] == 6:
                eb = '<span class="eyebrow"><i></i> %s</span>' % b['html']
                nxt = B[i + 1] if i + 1 < n else None
                if nxt and nxt['kind'] == 'h' and nxt['level'] == 2 and not plain(nxt['html']).isdigit():
                    pending.append(eb)
                else:
                    sec.append(eb)
            else:
                sec.append('<h%d>%s</h%d>' % (b['level'], b['html'], b['level']))
            i += 1
            continue
        if k == 'p':
            m = re.fullmatch(r'<a href="([^"]*)"([^>]*)>(.*?)</a>', b['html'].strip(), re.S)
            if m:  # parágrafo que é só um link vira botão secundário
                label = re.sub(r'\s+', ' ', m.group(3)).strip()
                sec.append('<div class="x-actions"><a class="button button-light" href="%s"%s>%s <span>↗</span></a></div>'
                           % (m.group(1), m.group(2), label))
            else:
                sec += paras(b['html'])
            i += 1
            continue
        if k == 'img':
            imgs = []
            while i < n and B[i]['kind'] == 'img':
                m = B[i]
                imgs.append('<img src="%s" alt="%s" width="%s" height="%s" loading="lazy" />'
                            % (upload_path(m['src']), esc(m['alt']), m['width'] or '', m['height'] or ''))
                i += 1
            sec.append('<figure class="x-figure x-figure-%d">%s</figure>' % (len(imgs), ''.join(imgs)))
            continue
        if k == 'btn':
            btns = []
            seen = set()
            while i < n and B[i]['kind'] == 'btn':
                if B[i]['href'] not in seen and B[i]['href'] not in ('#', ''):
                    seen.add(B[i]['href'])
                    ext = ' target="_blank" rel="noopener"' if B[i]['href'].startswith('http') else ''
                    btns.append('<a class="button button-primary" href="%s"%s>%s <span>↗</span></a>'
                                % (esc(B[i]['href']), ext, esc(plain(B[i]['html']))))
                i += 1
            if btns:
                sec.append('<div class="x-actions">%s</div>' % ''.join(btns))
            continue
        i += 1
    close()
    return title, lede, '\n'.join(out)


# Destaque em laranja no título (H1) e na primeira headline de cada página de serviço —
# mesmo tratamento usado na home, para as páginas pararem de parecer monocromáticas.
HEADLINE_H1 = {
    'pos-graduacao-ou-mba': ('Pós-Graduação ou MBA', 'Pós-Graduação <em>ou MBA</em>'),
    'extensao-universitaria': ('Extensão Universitária', 'Extensão <em>Universitária</em>'),
    'consultoria-metep': ('Consultoria METEP', 'Consultoria <em>METEP</em>'),
    'consultoria-mentoria': ('Consultoria Educacional', 'Consultoria <em>Educacional</em>'),
}
HEADLINE_H2 = {
    'pos-graduacao-ou-mba': ('impacta positivamente na educação e carreira dos seus alunos.',
                             'impacta positivamente na <span>educação e carreira</span> dos seus alunos.'),
    'extensao-universitaria': ('reconhecimento com a Extensão Universitária da iSnap Labs.',
                               'reconhecimento com a <span>Extensão Universitária</span> da iSnap Labs.'),
    'consultoria-metep': ('a se tornarem verdadeiros Empreendedores da Educação.',
                          'a se tornarem verdadeiros <span>Empreendedores da Educação</span>.'),
    'consultoria-mentoria': ('Transforme Seus Infoprodutos em Ofertas Educacionais de Sucesso',
                             'Transforme Seus Infoprodutos em <span>Ofertas Educacionais de Sucesso</span>'),
}

# Páginas cujo CTA final usa o layout grande da home (hero escuro + círculo), não a caixa
# pequena padrão — hoje só Sobre nós, cujo CTA original tem 2 botões e nenhum texto de apoio.
# Cada valor é (texto de apoio, (trecho do título, versão com <em> em laranja)).
BIG_CTA = {
    'sobre-nos': ('Fale com a nossa equipe e descubra o melhor caminho para dar o próximo passo.',
                  ('Pronto para transformar seu conhecimento em uma jornada educacional de impacto?',
                   'Pronto para transformar seu conhecimento em uma <em>jornada educacional de impacto?</em>')),
}


def build_generic(slug, crumbs_label=None, start_tier=0):
    page = PAGES[slug]
    big_cta = slug in BIG_CTA
    title, lede, body = render_generic(page, start_tier, big_cta=big_cta,
                                       cta_text=BIG_CTA.get(slug, ('', ''))[0])
    if slug in HEADLINE_H1:
        title = title.replace(*HEADLINE_H1[slug])
    if slug in HEADLINE_H2:
        body = body.replace(*HEADLINE_H2[slug], 1)
    if slug in BIG_CTA:
        body = body.replace(*BIG_CTA[slug][1], 1)
    path = page_path(page)
    crumbs = [(None, plain(title) or page['title']['rendered'])]
    if slug in ('pos-graduacao-ou-mba', 'extensao-universitaria', 'consultoria-metep', 'consultoria-mentoria'):
        crumbs = [('/solucoes/', 'Soluções'), (None, plain(title))]
    html_body = hero(title, lede, crumbs) + '\n' + body
    seo = head_seo(page.get('yoast_head_json'), path, plain(title) + ' - iSnap Labs')
    write(path, layout(path, seo, html_body, current='/solucoes/' if slug != 'sobre-nos' else '/sobre-nos/'))


# ---------------------------------------------------------------- home
def build_home():
    page = PAGES['home']
    B = [b for b in parse_blocks(localize(page['content']['rendered']))]

    def first(kind, startswith, level=None):
        for b in B:
            if b['kind'] == kind and plain(b['html']).lower().startswith(startswith.lower()) and (level is None or b.get('level') == level):
                return b
        raise KeyError(startswith)

    def para_after(head):
        idx = B.index(head)
        return B[idx + 1]['html'] if idx + 1 < len(B) and B[idx + 1]['kind'] == 'p' else ''

    h1 = 'A <em>Educação do futuro</em> começa com você!'
    about_h2 = first('h', 'Ajudamos Infoprodutores', 2)
    about_p = para_after(about_h2)
    about_h2_html = re.sub(r'(metodologia reconhecida)', r'<span>\1</span>', about_h2['html'], count=1, flags=re.I)
    lede = 'Engenharia educacional para experts, infoprodutores e empresas que querem transformar conhecimento em produtos educacionais de maior valor.'

    # benefícios numerados (H2 digit + H5 + P?)
    ben = []
    for idx, b in enumerate(B):
        if b['kind'] == 'h' and b['level'] == 2 and plain(b['html']).isdigit() and idx + 1 < len(B) and B[idx + 1]['kind'] == 'h':
            title = B[idx + 1]['html']
            txt = B[idx + 2]['html'] if idx + 2 < len(B) and B[idx + 2]['kind'] == 'p' else ''
            if plain(txt).lower() in ('saiba mais', ''):
                txt = BENEFIT_TEXT.get(plain(title), '')
            ben.append((plain(b['html']), title, txt))
    icons = ['icon-orbit', 'icon-diamond', 'icon-spark', 'icon-bars']
    ben_html = ''.join(
        '<article class="benefit-card reveal%s"><span class="benefit-number">%02d</span><div class="benefit-icon %s" aria-hidden="true">%s</div><h3>%s</h3>%s</article>'
        % (' delay-%d' % (n % 4) if n % 4 else '', int(num), icons[n % 4], '<i></i><i></i><i></i>' if n % 4 == 3 else '', t,
           ('<p>%s</p>' % x) if x else '')
        for n, (num, t, x) in enumerate(ben))

    help_h2 = first('h', 'Infoprodutores e empreendedores educacionais', 2)
    help_p = para_after(help_h2)
    solutions_note = '<p class="lead">%s</p><p>%s</p>' % (help_h2['html'], help_p)

    # por que se tornar empreendedor da educação (toggles)
    rotation_html = ''.join(
        '<article class="rotation-card"><div class="portrait-photo"><img src="/%s" alt="%s" width="700" height="700" loading="lazy" /></div>'
        '<div><small>%s</small><h3>%s</h3></div></article>'
        % (photo, esc(name), niche, name)
        for name, niche, photo in EXPERTS * 2)

    why_h2 = first('h', 'Por que se tornar', 2)
    why_intro = para_after(why_h2)
    outcomes = []
    for idx, b in enumerate(B):
        if b['kind'] == 'q' and idx + 1 < len(B) and B[idx + 1]['kind'] == 'a':
            outcomes.append((b['html'], B[idx + 1]['html']))
    out_html = ''.join('<article><span>%02d</span><div><h3>%s</h3><p>%s</p></div></article>' % (n + 1, t, x)
                       for n, (t, x) in enumerate(outcomes))
    rev_h2 = first('h', 'Faça parte da revolução', 2)['html']
    blog_h2 = 'Conteúdo para quem quer <span>liderar a transformação.</span>' 

    posts = POSTS[:3]
    cards = ''.join(post_card(p, featured=(n == 0)) for n, p in enumerate(posts))

    body = """    <section class="hero hero-has-banner" aria-labelledby="hero-title">
      <img class="hero-banner" src="/assets/hero-banner.jpg" alt="Equipe de especialistas trabalhando em conteúdo educacional" width="1536" height="1024" />
      <div class="hero-banner-fade"></div>
      <div class="container hero-layout">
        <div class="hero-copy reveal">
          <span class="eyebrow"><i></i> Educação. Estratégia. Transformação.</span>
          <h1 id="hero-title">%s</h1>
          <p>%s</p>
          <div class="hero-actions">
            %s
            <a class="text-link" href="/solucoes/">Conheça nossas soluções <span>↓</span></a>
          </div>
        </div>
      </div>
      <div class="hero-footer container">
        <span>Role para descobrir</span>
        <div class="scroll-line"><i></i></div>
        <span class="hero-index">ISNAP LABS</span>
      </div>
    </section>

    <section class="section about" id="sobre">
      <div class="container about-layout x-stack">
        <div class="section-label reveal"><span>01</span> O que é a iSnap Labs?</div>
        <div class="about-content">
          <h2 class="display-title reveal">%s</h2>
          <div class="about-body reveal">
            %s
            <a class="arrow-link" href="/sobre-nos/">Conheça a iSnap Labs <span>→</span></a>
          </div>
        </div>
      </div>
      <div class="container benefits-grid">%s</div>
    </section>

    <section class="section solutions" id="solucoes">
      <div class="container section-heading x-stack reveal">
        <div class="section-label light"><span>02</span> Nossas soluções</div>
        <div>
          <h2 class="display-title">Uma estrutura para cada <span>próximo nível.</span></h2>
          <p>Estratégia educacional, modelagem acadêmica e visão de negócio reunidas em uma jornada personalizada.</p>
        </div>
      </div>
      <div class="container solution-grid">
        <article class="solution-card solution-featured reveal">
          <div class="solution-card-head"><span class="solution-tag">Estruturação acadêmica</span><span class="solution-code">S.01</span></div>
          <div class="solution-main">
            <div>
              <h3>Pós-Graduação ou MBA</h3>
              <p>A iSnap Labs oferece serviços de consultoria especializada para transformar infoprodutos em metodologias de ensino.</p>
              <a href="/pos-graduacao-ou-mba/">Conhecer solução <span>↗</span></a>
            </div>
            <div class="degree-visual" aria-hidden="true"><div class="degree-ring"><span>MBA</span></div><div class="degree-line"></div></div>
          </div>
        </article>
        <article class="solution-card solution-blue reveal delay-1">
          <div class="solution-card-head"><span class="solution-tag">Validação</span><span class="solution-code">S.02</span></div>
          <div class="solution-mini-icon" aria-hidden="true"><span>✓</span></div>
          <h3>Extensão Universitária</h3>
          <p>Apoio na modelagem de cursos compatíveis com as normas educacionais legais, para produtos de baixa carga horária.</p>
          <a href="/extensao-universitaria/">Conhecer solução <span>↗</span></a>
        </article>
        <article class="solution-card reveal">
          <div class="solution-card-head"><span class="solution-tag">Estratégia</span><span class="solution-code">S.03</span></div>
          <div class="metep-word" aria-hidden="true">M</div>
          <h3>Consultoria METEP</h3>
          <p>Método Estratégico de Transformação e Performance para transformar infoprodutores em empreendedores da educação.</p>
          <a href="/consultoria-metep/">Conhecer solução <span>↗</span></a>
        </article>
        <article class="solution-card solution-wide reveal delay-1">
          <div class="solution-card-head"><span class="solution-tag">Crescimento</span><span class="solution-code">S.04 — S.05</span></div>
          <div class="wide-copy">
            <div><h3>Consultoria / Mentoria para Lançamentos e Vendas</h3><p>Consultoria projetada para ajudar infoprodutores a maximizar o sucesso de seus cursos e produtos educacionais.</p></div>
            <div><h3>Cursos Rápidos para Infoprodutores</h3><p>Cursos rápidos que ajudam a enfrentar as principais dificuldades do mercado de infoprodutos.</p></div>
          </div>
          <a class="wide-link" href="/consultoria-mentoria/">Explorar consultoria <span>↗</span></a>
        </article>
      </div>
      <div class="container x-note reveal"><div>%s<p><a class="arrow-link" href="/solucoes/">Ver todas as soluções <span>→</span></a></p></div></div>
    </section>

    <section class="section method method-light" id="metodo">
      <div class="container method-layout">
        <div class="method-intro">
          <div class="section-label reveal"><span>03</span> Como fazemos</div>
          <h2 class="display-title reveal">Conhecimento com método. <span>Negócio com direção.</span></h2>
          <p class="reveal">Cada projeto começa pela sua essência e avança com estratégia, rigor acadêmico e uma leitura clara das oportunidades de mercado.</p>
          <div class="method-badge reveal" aria-hidden="true">
            <svg viewBox="0 0 160 160"><defs><path id="circle" d="M80,80 m-58,0 a58,58 0 1,1 116,0 a58,58 0 1,1 -116,0" /></defs><text><textPath href="#circle">ESTRATÉGIA • EDUCAÇÃO • IMPACTO • </textPath></text><path d="M58 80h44M83 61l19 19-19 19" /></svg>
          </div>
        </div>

        <div class="steps">
          <article class="step reveal">
            <span>01</span>
            <div><small>Diagnóstico</small><h3>Entendemos sua expertise e seu momento.</h3><p>Analisamos produto, público, proposta de valor, estrutura atual e objetivos.</p></div>
          </article>
          <article class="step reveal">
            <span>02</span>
            <div><small>Modelagem</small><h3>Organizamos o conhecimento em uma jornada.</h3><p>Desenhamos matriz, módulos, ementas, carga horária e referenciais.</p></div>
          </article>
          <article class="step reveal">
            <span>03</span>
            <div><small>Estruturação</small><h3>Construímos a documentação acadêmica.</h3><p>Preparamos o projeto para diálogo com faculdades e centros universitários.</p></div>
          </article>
          <article class="step reveal">
            <span>04</span>
            <div><small>Evolução</small><h3>Apoiamos o crescimento do negócio.</h3><p>Conectamos estratégia educacional, lançamento, oferta e melhoria contínua.</p></div>
          </article>
        </div>
      </div>
    </section>

    <section class="education-section">
      <div class="education-grid"></div>
      <div class="container education-layout">
        <div class="education-copy reveal">
          <span class="eyebrow"><i></i> Torne-se um empresário da educação</span>
          <h2>Não venda apenas um curso. <em>Construa um legado.</em></h2>
          <p>%s</p>
          %s
        </div>
        <div class="outcomes reveal delay-1">%s</div>
      </div>
    </section>

    <section class="creator-rotation" aria-labelledby="creator-rotation-title">
      <div class="container rotation-heading">
        <div>
          <span class="eyebrow"><i></i> Histórias em movimento</span>
          <h2 id="creator-rotation-title">De especialistas a <em>empreendedores da educação.</em></h2>
        </div>
        <p>Experts que já estão transformando conhecimento em negócios educacionais mais sólidos com a iSnap Labs.</p>
      </div>
      <div class="rotation-viewport" aria-label="Vitrine em movimento de experts parceiros da iSnap Labs">
        <div class="rotation-track">%s</div>
      </div>
    </section>

    <section class="section insights" id="conteudos">
      <div class="container section-heading x-stack reveal">
        <div class="section-label"><span>04</span> iSnap Insights</div>
        <div>
          <h2 class="display-title">%s</h2>
          <p>Conhecimento prático sobre estruturação acadêmica, posicionamento e negócios educacionais.</p>
          <p><a class="arrow-link" href="/blog/">Ver todos os posts <span>→</span></a></p>
        </div>
      </div>
      <div class="container article-grid">%s</div>
    </section>

    <section class="cta-section" id="contato">
      <div class="cta-noise"></div>
      <div class="container cta-content reveal">
        <span class="eyebrow"><i></i> Seu próximo capítulo</span>
        <h2>A educação do futuro<br />começa <em>com você.</em></h2>
        <p>Converse com um especialista e descubra o melhor caminho para transformar seu conhecimento em um negócio educacional forte.</p>
        <div class="cta-actions">
          %s
          <small>Atendimento personalizado<br />para o seu momento.</small>
        </div>
      </div>
    </section>
""" % (h1, lede, cta_button('Agendar consultoria estratégica'),
       about_h2_html, ''.join(paras(about_p, True)), ben_html,
       solutions_note,
       why_intro, cta_button('Quero saber mais'), out_html,
       rotation_html, blog_h2, cards, cta_button('Agendar consultoria estratégica', 'button-light'))
    seo = head_seo(page.get('yoast_head_json'), '/', 'iSnap Labs')
    write('/', layout('/', seo, body, current='/', home=True))


# ---------------------------------------------------------------- contato
def build_contact():
    page = PAGES['contato']
    path = '/contato/'
    phones = ''.join('<a href="tel:%s">%s</a>' % (t, l) for l, t in PHONES)
    body = hero('Fale Conosco', 'Converse com nossa equipe, sem compromisso, e descubra como podemos ajudar você.',
                [(None, 'Contato')]) + """
    <section class="x-section">
      <div class="container x-contact">
        <div class="x-contact-info">
          <h2>iSnap</h2>
          <div class="x-info-item"><span>Endereço</span><p>%s</p></div>
          <div class="x-info-item"><span>Telefones</span><p class="x-phones">%s</p></div>
          <div class="x-info-item"><span>E-mail</span><p><a href="mailto:%s">%s</a></p></div>
          <div class="x-info-item"><span>WhatsApp</span><p><a href="%s" target="_blank" rel="noopener">Chamar no WhatsApp ↗</a></p></div>
        </div>
        <form class="x-form" id="contact-form" data-wa="%s" novalidate>
          <h2>Envie sua mensagem</h2>
          <label>Nome<input name="nome" type="text" autocomplete="name" required /></label>
          <label>E-mail<input name="email" type="email" autocomplete="email" required /></label>
          <label>Telefone / WhatsApp<input name="telefone" type="tel" autocomplete="tel" /></label>
          <label>Mensagem<textarea name="mensagem" rows="5" required></textarea></label>
          <button class="button button-primary" type="submit">Enviar agora <span>↗</span></button>
          <p class="x-form-note">Ao enviar, abriremos o WhatsApp com a sua mensagem pronta para a equipe da iSnap Labs.</p>
        </form>
      </div>
    </section>""" % (esc(ADDRESS), phones, EMAIL, EMAIL, esc(core.WA_URL), WHATSAPP)
    seo = head_seo(dict(page.get('yoast_head_json') or {}, description='Fale com a iSnap Labs, em Maringá/PR: WhatsApp (44) 99992-2804 ou e-mail %s. Agende uma consultoria estratégica.' % EMAIL, og_description='Fale com a iSnap Labs, em Maringá/PR: WhatsApp (44) 99992-2804 ou e-mail %s. Agende uma consultoria estratégica.' % EMAIL), path, 'Contato - iSnap Labs')
    write(path, layout(path, seo, body, current='/contato/'))


# ---------------------------------------------------------------- blog / posts / taxonomias
def build_blog():
    page = PAGES['blog']
    path = '/blog/'
    cards = ''.join(post_card(p, summary=True) for p in POSTS)
    body = hero('Blog e Notícias', 'Fique por dentro dos nossos conteúdos educacionais!', [(None, 'Blog')]) + """
    <section class="x-section"><div class="container">
      <div class="x-post-grid">%s</div>
    </div></section>
""" % cards + cta_section('Dúvidas? Converse com nossa equipe sem compromisso e descubra como podemos lhe ajudar!')
    seo = head_seo(page.get('yoast_head_json'), path, 'Blog - iSnap Labs')
    write(path, layout(path, seo, body, current='/blog/'))


def reading_time(h):
    words = len(re.sub(r'<[^>]+>', ' ', h).split())
    return max(1, round(words / 200))


def build_post(p):
    path = '/%s/' % p['slug']
    title = html.unescape(p['title']['rendered'])
    content = localize(p['content']['rendered'])
    content = re.sub(r'\s(srcset|sizes)="[^"]*"', '', content)
    content = re.sub(r'<img ', '<img loading="lazy" ', content) if 'loading=' not in content else content
    cats = [CATS[c] for c in p['categories'] if c in CATS and CATS[c]['slug'] != 'uncategorized']
    src, w, h, alt = thumb(p, 'large')
    hero_img = ('<figure class="x-post-cover"><img src="%s" alt="%s" width="%s" height="%s" /></figure>'
                % (src, esc(alt or title), w, h)) if src else ''
    others = [o for o in POSTS if o['id'] != p['id']][:3]
    meta = '<span>%s</span><span>%d min de leitura</span>' % (fmt_date(p['date']), reading_time(content))
    catlinks = ''.join('<a href="/category/%s/">%s</a>' % (c['slug'], esc(c['name'])) for c in cats)
    side_list = ''.join('<li><a href="/%s/">%s</a></li>' % (o['slug'], html.unescape(o['title']['rendered'])) for o in others)
    body = hero(esc(title), '', [('/blog/', 'Blog'), (None, esc(title)[:60] + ('…' if len(title) > 60 else ''))]) + """
    <section class="x-section"><div class="container x-article-wrap">
      <div class="x-post-layout">
        <div>
          <div class="x-post-meta">%s<span class="x-cats">%s</span></div>
          %s
          <article class="x-article">%s</article>
        </div>
        <aside class="x-post-side">
          <div class="x-side-card">
            <h2>Quer transformar seu conhecimento em um negócio educacional?</h2>
            <p>Converse com um especialista da iSnap Labs e descubra o melhor caminho para o seu projeto.</p>
            %s
          </div>
          <div class="x-side-card">
            <h2>Leia também</h2>
            <ul class="x-side-list">%s</ul>
          </div>
        </aside>
      </div>
    </div></section>
""" % (meta, catlinks, hero_img, content, cta_button('Falar com um consultor'), side_list)
    seo = head_seo(p.get('yoast_head_json'), path, title + ' - iSnap Labs')
    write(path, layout(path, seo, body, current='/blog/'))


def build_archive(kind, term):
    slug = term['slug']
    path = '/%s/%s/' % (kind, slug)
    name = 'Sem categoria' if slug == 'uncategorized' else term['name']
    key = 'categories' if kind == 'category' else 'tags'
    posts = [p for p in POSTS if term['id'] in p[key]]
    label = 'Categoria' if kind == 'category' else 'Tag'
    body = hero(esc(name), 'Artigos %s “%s”.' % ('da categoria' if kind == 'category' else 'com a tag', esc(name)),
                [('/blog/', 'Blog'), (None, esc(name))]) + """
    <section class="x-section"><div class="container"><div class="x-post-grid">%s</div></div></section>
""" % ''.join(post_card(p, summary=True) for p in posts)
    d = 'Artigos sobre %s no blog da iSnap Labs: conteúdos para infoprodutores e empreendedores da educação.' % name
    seo = head_seo(dict(term.get('yoast_head_json') or {}, description=d, og_description=d), path, '%s: %s - iSnap Labs' % (label, name))
    write(path, layout(path, seo, body, current='/blog/'))


def build_author():
    path = '/author/admin_isnap/'
    body = hero('Artigos de <em>iSnap Labs</em>', '', [('/blog/', 'Blog'), (None, 'Autor')]) + """
    <section class="x-section"><div class="container"><div class="x-post-grid">%s</div></div></section>
""" % ''.join(post_card(p, summary=True) for p in POSTS)
    d = 'Todos os artigos publicados pela iSnap Labs sobre infoprodutos, certificação e educação.'
    seo = head_seo({'description': d, 'og_description': d}, path, 'Artigos de iSnap Labs - iSnap Labs')
    write(path, layout(path, seo, body, current='/blog/'))


# ---------------------------------------------------------------- sitemap / robots / imagens
def build_404():
    body = hero('Página não encontrada', 'O endereço que você acessou não existe ou foi movido. Use o menu ou volte para o início.') + \
        cta_section('Quer falar com a nossa equipe?', 'Converse com um especialista da iSnap Labs e descubra o melhor caminho para o seu projeto.')
    seo = head_seo({'title': 'Página não encontrada - iSnap Labs', 'robots': {'index': 'noindex'}}, '/404.html', 'Página não encontrada - iSnap Labs')
    with open(os.path.join(ROOT, '404.html'), 'w', encoding='utf-8') as f:
        f.write(layout('/404.html', seo, body))


def build_sitemap():
    urls = []
    for p in PAGES.values():
        urls.append((ORIGIN + page_path(p), p['modified'][:10], '1.0' if p['slug'] == 'home' else '0.8'))
    for p in POSTS:
        urls.append(('%s/%s/' % (ORIGIN, p['slug']), p['modified'][:10], '0.7'))
    for c in CATS.values():
        urls.append(('%s/category/%s/' % (ORIGIN, c['slug']), max(p['modified'] for p in POSTS)[:10], '0.4'))
    for t in TAGS.values():
        urls.append(('%s/tag/%s/' % (ORIGIN, t['slug']), max(p['modified'] for p in POSTS)[:10], '0.3'))
    x = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, d, pr in urls:
        x.append('  <url><loc>%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>' % (u, d, pr))
    x.append('</urlset>')
    with open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(x) + '\n')
    with open(os.path.join(ROOT, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write('User-agent: *\nDisallow:\n\nSitemap: %s/sitemap.xml\n' % ORIGIN)


def download_images():
    imgs = sorted({u if u.startswith('http') else ORIGIN + u for u in core.IMAGES})

    def get(url):
        dest = os.path.join(ROOT, upload_path(url).lstrip('/'))
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            return url, True
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        r = subprocess.run(['curl', '-sfL', '-m', '60', '-A', 'Mozilla/5.0', '-o', dest, url])
        if r.returncode != 0 and os.path.exists(dest):
            os.remove(dest)
        return url, r.returncode == 0

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(get, imgs))
    bad = [u for u, ok in res if not ok]
    print('imagens: %d ok, %d falharam' % (len(res) - len(bad), len(bad)))
    for u in bad:
        print('  falhou:', u)


def main():
    build_home()
    for slug in ('sobre-nos', 'pos-graduacao-ou-mba', 'extensao-universitaria',
                 'consultoria-metep', 'consultoria-mentoria'):
        build_generic(slug)
    build_generic('solucoes', start_tier=2)  # página com um único bloco: abre em cinza-claro, não em azul
    build_contact()
    build_blog()
    for p in POSTS:
        build_post(p)
    for c in CATS.values():
        build_archive('category', c)
    for t in TAGS.values():
        build_archive('tag', t)
    build_author()
    build_404()
    build_sitemap()
    core.IMAGES.add('https://isnap.com.br/wp-content/uploads/2023/10/favicon-isnap.png')
    print('páginas geradas; imagens referenciadas: %d' % len(core.IMAGES))
    if '--images' in sys.argv:
        download_images()


if __name__ == '__main__':
    main()
