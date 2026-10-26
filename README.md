# SchengenCalc

Free Schengen 90/180-day calculator in English, German, French and Chinese.

## Structure

- `src/i18n/*.py` – page text per language (titles, guide, FAQ, UI strings)
- `src/countries.py` – Schengen member list
- `src/template.html` – page layout
- `assets/` – shared CSS and calculator logic (`app.js`)
- `build.py` – generates `index.html`, `de/`, `fr/`, `zh/`, `sitemap.xml`, `robots.txt`

Generated files are committed so GitHub Pages can serve them directly.

## Build

```bash
python build.py
```

Set `SITE_URL` in `build.py` when the site moves to a custom domain, then rebuild.
