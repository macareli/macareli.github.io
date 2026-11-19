# MaiChat website

Source for [maichat.me](https://maichat.me/), maintained in
[`macareli/macareli.github.io`](https://github.com/macareli/macareli.github.io).
GitHub Pages publishes the `_site` artifact produced by the deployment workflow.
Set **Settings → Pages → Build and deployment → Source** to **GitHub Actions**,
keep the custom domain `maichat.me`, and keep HTTPS enforcement enabled.

## Edit and preview

- Pages: `src/pages/index.html` and `src/pages/release.html`.
- Shared navigation: `src/layouts/header.html` and `src/layouts/footer.html`.
- Styles, scripts, and tokens: `src/`; images and artwork: `assets/`.
- Build: `python3 scripts/build.py` (Python 3.10+, standard library only).
- Preview: `python3 -m http.server 4173 --directory _site`.
- Integrity and rendering tests: `python3 -m unittest discover -s tests -v`.
- Browser checks: install development dependencies with `npm ci` and `npx playwright install chromium`, then `npm test` against the running preview. `CHROME_PATH` can select an existing Chrome binary; `BASE_URL` can select another preview URL.
- Material checks: `python3 scripts/check_material.py --site-root _site _site`.
- HTML validation: `npx html-validate _site/index.html _site/release/index.html _site/404.html`.

Full-resolution Android captures remain unchanged in `assets/images/`; see
`assets/images/CAPTURES.md` for provenance. After replacing those native PNGs,
run `node scripts/optimize-images.mjs` to regenerate responsive WebP delivery
copies. The page selects the appropriate copy for the screen's pixel density.

The build reads the latest **public stable** release from
[`macareli/Maichat`](https://github.com/macareli/Maichat), downloads its APK into
the ignored `.cache/releases` directory, and checks its size and GitHub-provided
SHA-256 digest. Set `GITHUB_TOKEN` when needed for API rate limits. The token is
only sent to `api.github.com`; no credentials are used to download the public APK.
For offline metadata or repeatable builds, use:

```sh
gh api repos/macareli/Maichat/releases/latest > /tmp/maichat-release.json
python3 scripts/build.py --release-json /tmp/maichat-release.json
```

The APK must still be downloaded or already exist in the verified cache.
`--cache-dir /path/to/cache` selects an external cache. Cached bytes are rehashed
on every build. Files larger than 512 MiB, missing digests, prereleases, draft
releases, mismatched source URLs, and incomplete downloads stop the build.

## Release downloads and deployment

`/release/` contains the current version, release notes, file size, and SHA-256.
The download is an ordinary same-origin link to a versioned file such as
`/release/files/MaiChat-1.19.4.apk`; JavaScript and GitHub navigation are unnecessary.
`/release/manifest.json` exposes the same release metadata for inspection.
Only the current stable APK is included; older release files remain available
from the upstream repository.

`.github/workflows/deploy.yml` builds on pushes to `main`, manual dispatch, and
every six hours. It caches APKs by SHA-256, verifies each cache hit, uploads the
whole site with its APK as a Pages artifact, and deploys only after a successful
build. The large APK is never committed to Git. API outages or verification errors
fail the workflow, preserving the previous deployment. The build itself stages
all files before replacing `_site`, preserving the previous local build on errors.

Keep `CNAME` set to `maichat.me`. The build includes `CNAME`, `.nojekyll`, a 404
page, `robots.txt`, and `sitemap.xml` in every artifact. No server, PHP, Git LFS,
or runtime release lookup is required.
