# Public demo deployment

`src/build_site.py` builds `_site/index.html` from the self-contained dashboard. `_site/` is ignored by Git. Only `_site/` is deployed; no source data, prediction rows, model pickles or warehouse are uploaded to the site.

GitHub Pages URL: **https://jvaisag.github.io/Football-Scouting/**

The workflow `.github/workflows/pages.yml` deploys on dashboard-related pushes to `master` and on manual dispatch. Repository Pages settings must use the **GitHub Actions** publishing source. The deployment workflow exposes the actual `page_url`, so deployment success should be checked before treating the link as live.

For a local preview:

```bash
python src/build_site.py
python -m http.server 8000 --directory _site
```

Then open http://localhost:8000/.

To update README screenshots, install the pinned Playwright version documented in `TESTING.md` and run `node tests/capture_previews.cjs` with Playwright Chromium installed. The screenshots show the actual dashboard; they are not mockups.
