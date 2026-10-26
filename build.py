"""Generate the static multi-language site.

    python build.py

Outputs index.html (English), de/, fr/, zh/, guide pages from src/guides/, sitemap.xml, robots.txt and a redirect
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


def jsonld(c, url):
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
    return data


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


def load_guides():
    """Single-language landing pages (e.g. /spain/) that reuse a home page's UI strings."""
    guides = []
    for f in sorted((SRC / 'guides').glob('*.py')):
        g = load_module(f)
        base = CONTENT[g.BASE]
        c = {**base, **g.C, 't': {**base['t'], **g.C.get('t', {})}}
        guides.append({'id': f.stem, 'lang': g.BASE, 'path': g.PATH, 'c': c,
                       'link_title': g.LINK_TITLE, 'link_desc': g.LINK_DESC})
    return guides


GUIDES = load_guides()


def script_json(data):
    # '</' must not appear inside a <script> block
    return json.dumps(data, ensure_ascii=False).replace('</', '<\\/')


def nav_html(c, sections):
    labels = {'calculator': c['nav_calc'], 'rule': c['nav_rule'], 'countries': c['nav_countries'], 'faq': c['nav_faq']}
    return '\n  '.join(f'<a href="#{s}">{esc(labels[s])}</a>' for s in sections)


def countries_section(lang, c):
    return (f'  <section class="card prose" id="countries">\n    <h2>{esc(c["countries_title"])}</h2>\n'
            f'    <p>{esc(c["countries_intro"])}</p>\n'
            f'    <ul class="countries-grid">{countries_html(lang, c)}</ul>\n  </section>')


def guides_section(c, lang, root, exclude=None):
    items = [g for g in GUIDES if g['lang'] == lang and g['id'] != exclude]
    if not items:
        return ''
    links = ''.join(
        f'<li><a href="{root + g["path"]}">{esc(g["link_title"])}</a><span>{esc(g["link_desc"])}</span></li>'
        for g in items)
    return (f'  <section class="card" id="guides">\n    <h2>{esc(c["guides_title"])}</h2>\n'
            f'    <ul class="guide-links">{links}</ul>\n  </section>\n')


def build_page(page_id, lang, c, path, template, is_home):
    root = '../' * path.count('/')
    url = SITE_URL + path
    home_href = root + PATHS[lang] or './'

    hreflang = []  # guide pages have no translations (yet)
    if is_home:
        hreflang = [f'<link rel="alternate" hreflang="{CONTENT[l]["hreflang"]}" href="{SITE_URL + PATHS[l]}">' for l in LANGS]
        hreflang.append(f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}">')
    lang_links = ''.join(
        f'<a class="lang-btn{" active" if l == lang else ""}" href="{root + PATHS[l] or "./"}" hreflang="{CONTENT[l]["hreflang"]}"'
        f' lang="{CONTENT[l]["html_lang"]}"{" aria-current=\"page\"" if is_home and l == lang else ""}>{esc(CONTENT[l]["label"])}</a>'
        for l in LANGS)

    ld = jsonld(c, url)
    breadcrumb = ''
    if not is_home:
        ld.append({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': CONTENT[lang]['brand'], 'item': SITE_URL + PATHS[lang]},
            {'@type': 'ListItem', 'position': 2, 'name': c['crumb'], 'item': url}]})
        breadcrumb = (f'  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="{home_href}">'
                      f'{esc(CONTENT[lang]["brand"])}</a> › {esc(c["crumb"])}</nav>')

    sc = {
        'lang': page_id,
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
        'self_href': home_href,
        'hreflang_links': '\n'.join(hreflang),
        'lang_links': lang_links,
        'nav_html': nav_html(c, ['calculator', 'rule', 'countries', 'faq'] if is_home else ['calculator', 'rule', 'faq']),
        'breadcrumb_html': breadcrumb,
        'jsonld': script_json(ld),
        'countries_section': countries_section(lang, c) if is_home else '',
        'guides_section': guides_section(c, lang, root, exclude=None if is_home else page_id),
        'faq_html': faq_html(c),
        'qf_html': ''.join(f'<div class="qf"><span>{esc(k)}</span><span class="qf-val">{esc(v)}</span></div>' for k, v in c['qf']),
        'sc_json': script_json(sc),
    })
    out = ROOT / path / 'index.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(template, values), encoding='utf-8')
    print('wrote', out.relative_to(ROOT))


def build_extras():
    today = datetime.date.today().isoformat()
    alts = ''.join(f'\n    <xhtml:link rel="alternate" hreflang="{CONTENT[l]["hreflang"]}" href="{SITE_URL + PATHS[l]}"/>' for l in LANGS)
    alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE_URL}"/>'
    urls = ''.join(f'\n  <url>\n    <loc>{SITE_URL + PATHS[l]}</loc>\n    <lastmod>{today}</lastmod>{alts}\n  </url>' for l in LANGS)
    urls += ''.join(f'\n  <url>\n    <loc>{SITE_URL + g["path"]}</loc>\n    <lastmod>{today}</lastmod>\n  </url>' for g in GUIDES)
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
        build_page(l, l, CONTENT[l], PATHS[l], tpl, is_home=True)
    for g in GUIDES:
        build_page(g['id'], g['lang'], g['c'], g['path'], tpl, is_home=False)
    build_extras()
