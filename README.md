# iSnap Labs — site institucional

Site estático (HTML, CSS e JS puros) com o conteúdo do isnap.com.br (WordPress) e as **mesmas URLs**, para preservar o ranqueamento no Google.

## Ver no computador

As URLs são absolutas a partir da raiz (`/blog/`), então use um servidor local:

```bash
python3 -m http.server 4173
```

Acesse `http://localhost:4173`.

## Estrutura

- `index.html`, `<slug>/index.html`: páginas geradas (não edite à mão, elas são sobrescritas)
- `styles.css`: identidade visual · `site.css`: componentes das páginas internas, blog e rodapé
- `site.js`: menu móvel, animações, formulário de contato (abre o WhatsApp) e eventos de conversão
- `assets/`: logo e imagens do design · `wp-content/uploads/`: imagens do site antigo (mesmos caminhos)
- `sitemap.xml`, `robots.txt`
- `_build/`: gerador (`build.py`, `core.py`) e o conteúdo exportado do WordPress (`source/*.json`)
- `_backup-modelo/`: arquivos do modelo anterior (landing page)

## Regerar o site

```bash
python3 _build/build.py            # páginas
python3 _build/build.py --images   # páginas + baixa imagens que faltarem
```

Textos vêm de `_build/source/*.json`; layout e rodapé de `_build/core.py`; a home de `_build/build.py`.
Deploy: publique o conteúdo da pasta, exceto `_build/` e `_backup-modelo/`.
