import os, re, glob, html
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
files = [f for f in glob.glob(ROOT + '/**/*.html', recursive=True) if '/_' not in f.replace(ROOT,'')]
bad = []; n = 0
def exists(path):
    path = path.split('#')[0].split('?')[0]
    if not path: return True
    fp = os.path.join(ROOT, path.lstrip('/'))
    return os.path.isfile(fp) or os.path.isfile(os.path.join(fp, 'index.html'))
for f in files:
    h = open(f, encoding='utf-8').read()
    for attr, val in re.findall(r'\b(href|src)="([^"]+)"', h):
        val = html.unescape(val)
        if re.match(r'(https?:|mailto:|tel:|data:|#|//)', val): continue
        n += 1
        if not exists(val): bad.append((f.replace(ROOT,''), attr, val))
    # H1 único, imagens sem alt
    if len(re.findall(r'<h1[ >]', h)) != 1: bad.append((f.replace(ROOT,''), 'h1', str(len(re.findall(r'<h1[ >]', h)))))
print('links/recursos internos verificados:', n, '| páginas:', len(files)); print('problemas:', len(bad))
for b in bad[:30]: print(' ', b)
