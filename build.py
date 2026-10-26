"""Generate the static multi-language site.

    python build.py

Outputs index.html (English), de/, fr/, zh/, sitemap.xml, robots.txt and a redirect
for the old schengen-calculator.html URL. Edit content in src/i18n/*.py, layout in
src/template.html, behaviour in assets/app.js.
"""
import datetime
import hashlib
import html
import importlib.util
import json
import re
import unicodedata
from pathlib import Path

# Public URL of the site root, with trailing slash. Change this when you move to a custom domain.
SITE_URL = 'https://schengencalc.online/'

ROOT = Path(__file__).parent
SRC = ROOT / 'src'
LANGS = ['en', 'de', 'fr', 'zh']           # first one is the default (served at the root)
PATHS = {l: '' if l == LANGS[0] else f'{l}/' for l in LANGS}


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CONTENT = {l: load_module(SRC / 'i18n' / f'{l}.py').C for l in LANGS}
countries = load_module(SRC / 'countries.py')
esc = html.escape


def flag(code):
    return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code)


def sort_key(name):
    return unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()


def countries_html(lang, c):
    rows = countries.COUNTRIES
    if lang != 'zh':
        rows = sorted(rows, key=lambda r: sort_key(r[3][lang]))
    out = []
    for code, year, eu, names in rows:
        note = c['country_bgro'] if code in countries.TWO_STEP else c['country_since'].format(y=year)
        if not eu:
            note = f"{c['country_noneu']} · {note}"
        out.append(f'<li class="country-card"><span class="flag" aria-hidden="true">{flag(code)}</span>'
                   f'<div><div class="cname">{esc(names[lang])}</div><div class="cnote">{esc(note)}</div></div></li>')
    return '\n'.join(out)


def faq_html(c):
    return '\n'.join(
        f'<details class="faq-item"{" open" if i == 0 else ""}><summary><h3>{esc(q)}</h3></summary>'
        f'<div class="faq-a">{esc(a)}</div></details>'
        for i, (q, a) in enumerate(c['faqs']))


def jsonld(lang, c, url):
    data = [
        {
            '@context': 'https://schema.org',
            '@type': 'WebApplication',
            'name': c['h1'],
            'url': url,
            'description': c['description'],
            'inLanguage': c['html_lang'],
            'applicationCategory': 'TravelApplication',
            'operatingSystem': 'Any',
            'isAccessibleForFree': True,
            'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'EUR'},
        },
        {
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            'inLanguage': c['html_lang'],
            'mainEntity': [
                {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}}
                for q, a in c['faqs']],
        },
    ]
    # '</' must not appear inside a <script> block
    return json.dumps(data, ensure_ascii=False).replace('</', '<\\/')


def render(template, values):
    def sub(m):
        raw, key = m.group(1) == '!', m.group(2)
        if key not in values:
            raise KeyError(f'template placeholder {{{{{key}}}}} has no value')
        v = str(values[key])
        return v if raw else esc(v)
    return re.sub(r'\{\{(!?)(\w+)\}\}', sub, template)


def asset_version(name):
    return hashlib.sha1((ROOT / 'assets' / name).read_bytes()).hexdigest()[:8]


def build_page(lang, template):
    c = CONTENT[lang]
    root = '../' * PATHS[lang].count('/')
    url = SITE_URL + PATHS[lang]

    hreflang = [f'<link rel="alternate" hreflang="{CONTENT[l]["hreflang"]}" href="{SITE_URL + PATHS[l]}">' for l in LANGS]
    hreflang.append(f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}">')
    lang_links = ''.join(
        f'<a class="lang-btn{" active" if l == lang else ""}" href="{root + PATHS[l] or "./"}" hreflang="{CONTENT[l]["hreflang"]}"'
        f' lang="{CONTENT[l]["html_lang"]}"{" aria-current=\"page\"" if l == lang else ""}>{esc(CONTENT[l]["label"])}</a>'
        for l in LANGS)

    sc = {
        'lang': lang,
        'locale': c['locale'],
        't': c['t'],
        'langPaths': {l: root + PATHS[l] or './' for l in LANGS},
    }
    values = {k: v for k, v in c.items() if isinstance(v, str)}
    values.update({f't_{k}': v for k, v in c['t'].items()})
    values.update({
        'root': root,
        'css_v': asset_version('style.css'),
        'js_v': asset_version('app.js'),
        'canonical': url,
        'self_href': root + PATHS[lang] or './',
        'hreflang_links': '\n'.join(hreflang),
        'lang_links': lang_links,
        'jsonld': jsonld(lang, c, url),
        'countries_html': countries_html(lang, c),
        'faq_html': faq_html(c),
        'qf_html': ''.join(f'<div class="qf"><span>{esc(k)}</span><span class="qf-val">{esc(v)}</span></div>' for k, v in c['qf']),
        'sc_json': json.dumps(sc, ensure_ascii=False).replace('</', '<\\/'),
    })
    out = ROOT / PATHS[lang] / 'index.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(template, values), encoding='utf-8')
    print('wrote', out.relative_to(ROOT))


def build_extras():
    today = datetime.date.today().isoformat()
    alts = ''.join(f'\n    <xhtml:link rel="alternate" hreflang="{CONTENT[l]["hreflang"]}" href="{SITE_URL + PATHS[l]}"/>' for l in LANGS)
    alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE_URL}"/>'
    urls = ''.join(f'\n  <url>\n    <loc>{SITE_URL + PATHS[l]}</loc>\n    <lastmod>{today}</lastmod>{alts}\n  </url>' for l in LANGS)
    (ROOT / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
        f'{urls}\n</urlset>\n', encoding='utf-8')
    (ROOT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n', encoding='utf-8')

    # The site used to live at schengen-calculator.html — keep old links (and ?trips= shares) working.
    (ROOT / 'schengen-calculator.html').write_text(f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Schengen Calculator</title>
<link rel="canonical" href="{SITE_URL}">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url=./">
<script>location.replace('./' + location.search + location.hash);</script>
</head>
<body><a href="./">Schengen 90/180 Calculator</a></body>
</html>
''', encoding='utf-8')
    print('wrote sitemap.xml, robots.txt, schengen-calculator.html')


if __name__ == '__main__':
    tpl = (SRC / 'template.html').read_text(encoding='utf-8')
    for l in LANGS:
        build_page(l, tpl)
    build_extras()
