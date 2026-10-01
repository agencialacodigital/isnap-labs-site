"""Auditoria de SEO: compara o site no ar (isnap.com.br) com o gerado localmente."""
import os, re, subprocess, html, json, glob

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
def live(url):
    return subprocess.run(['curl','-sL','-m','30','-A','Mozilla/5.0',url],capture_output=True,text=True).stdout
def tag(h, pat, flags=re.S|re.I):
    m = re.search(pat, h, flags); return html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',m.group(1))).strip()) if m else ''
def meta(h, name):
    m = re.search(r'<meta[^>]+(?:name|property)="%s"[^>]+content="([^"]*)"' % re.escape(name), h) or re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:name|property)="%s"' % re.escape(name), h)
    return html.unescape(m.group(1)) if m else ''
def words(h):
    m = re.search(r'<main.*?</main>', h, re.S) or re.search(r'<body.*?</body>', h, re.S)
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>','',m.group(0) if m else h,flags=re.S)
    return len(re.sub(r'<[^>]+>',' ',t).split())

urls = re.findall(r'<loc>([^<]+)', open(os.path.join(ROOT,'sitemap.xml')).read())
print('%-58s %-6s %-6s %-6s %-6s %s' % ('URL','title','desc','h1','canon','palavras (live→novo)'))
for u in urls:
    path = u.replace('https://isnap.com.br','')
    f = os.path.join(ROOT, path.strip('/'), 'index.html') if path!='/' else os.path.join(ROOT,'index.html')
    if not os.path.exists(f): print('FALTA', u); continue
    new = open(f, encoding='utf-8').read(); old = live(u)
    t1,t2 = tag(old,r'<title[^>]*>(.*?)</title>'), tag(new,r'<title[^>]*>(.*?)</title>')
    d1,d2 = meta(old,'description'), meta(new,'description')
    h1a,h1b = tag(old,r'<h1[^>]*>(.*?)</h1>'), tag(new,r'<h1[^>]*>(.*?)</h1>')
    c = re.search(r'rel="canonical" href="([^"]+)"',new)
    ok = lambda a,b: 'ok' if a==b else 'DIFF'
    print('%-58s %-6s %-6s %-6s %-6s %d→%d' % (path[:57], ok(t1,t2), ok(d1,d2) if d1 else 'n/a', ok(h1a,h1b), 'ok' if c and c.group(1)==u else 'DIFF', words(old), words(new)))
    if t1!=t2: print('    title live:',t1[:90],'\n    title novo:',t2[:90])
    if h1a!=h1b: print('    h1 live:',h1a[:90],'\n    h1 novo:',h1b[:90])
