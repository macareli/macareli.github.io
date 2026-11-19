# MaiChat portfolio browser tester

Verdict: PASS with one performance warning; no functional or accessibility blockers.

Tested the built website at http://127.0.0.1:4173 with real Chromium 151.0.7922.34, using browser-visible UI and accessibility snapshots. Production source was not read or changed. Notes and DESIGN.md supplied the intended paths and documented Expressive design exceptions.

| Page / viewport / theme | Severity | Kind | Detail | How to reproduce |
|---|---|---|---|---|
| Home and release; 400/1280px; light/dark | warn | Smoke baseline | Smoke found zero blockers and 100 visual warnings. Expressive headlines, branding, fluid marketing spacing, shape radii, and compact portfolio header differ from generic app-baseline measurements. They agree with DESIGN.md and are not visible usability failures. | [Full smoke report](../../e2e-report/report.md); screenshots in e2e-report. |
| Home and release; 1280px; both themes | warn | Smoke false positive | Smoke claims first-button hover has no change. A browser computed-style check confirms the theme button's state layer changes opacity 0 → 0.08 on hover, 0.1 on keyboard focus; focus outline is 3px. | Hover and keyboard-focus the header theme button. |
| Home; Lighthouse mobile 412px; light | warn | LCP target | Simulated mobile LCP 2.85s exceeds DESIGN.md target <2.5s. Performance score is 95. Largest element is the hero phone image; render-blocking CSS is the main reported opportunity. Preview serves uncompressed files without cache headers. | Run `node reports/portfolio/tester-lighthouse.mjs`; inspect lighthouse-home.html. |

All eight paths from notes.md were exercised at both widths and in both themes. A final pass used real touch `tap()` at 400px and mouse clicks at 1280px. Tabs measure 64px on mobile, 48px desktop, with 24px icons; final release notes render the APK filename as strong text without literal Markdown. [Final checks](final-capture-checks.json). Paths: Home→release→actual APK download; each of four feature tabs; roving keyboard tabs with arrow wrap/Home/End and Tab into the active panel; all five FAQ questions; theme preference persisting through reload; all three install/update accordions; successful checksum copy and a browser with Clipboard API removed for selected-text fallback; source and issue links to the actual public repository. External links were clicked and opened the expected GitHub pages.

The browser completed an actual 166,396,387-byte `MaiChat-1.19.4.apk` download, with honest request feedback. [Download result](browser-download.json). Checksum copy returned the visible 64-digit SHA-256; fallback selected exactly that checksum and announced how to copy it. The main agent independently verifies the downloaded bytes/hash.

Keyboard navigation reaches the main download path. The skip link's native fragment navigation moves the subsequent Tab into main content. All four tabs have names/roles, selected state, keyboard selection, and one exposed named tab panel. Accessibility snapshots are in `accessibility-*.yaml`. No installed screen reader was used.

Axe scans cover Home, release, and 404 at 400/1280px in light/dark: zero violations. No browser console or page errors were observed. The 404 page exposes working Home and download exits. No custom dialog exists; all listed controls and panels are reachable. [Flow evidence](flow-results.json), [clipboard fallback](checksum-fallback.json), [external link navigation](external-link-navigation.json).

Additional checks: 320px routes have no horizontal overflow; all visible controls measure at least 48×48px; a 640 CSS px viewport at DPR2 tests the layout equivalent of 200% desktop zoom; reduced motion is active; JavaScript-disabled navigation, APK link, and native install accordions remain usable. [Additional evidence](additional-browser-checks.json). There are no remote-data lists/forms requiring loading or empty states.

Reviewed screenshots: `screenshots/home-{400,1280}-{light,dark}.png`, `screenshots/release-{400,1280}-{light,dark}.png`, `screenshots/404-{400,1280}-{light,dark}.png`, and `screenshots/zoom200-{home,release,404}.png`. Clear primary download action, coherent light/dark hierarchy, readable page text, and no cut/overlapping content. All four final native app captures were reviewed in their matching feature panels. Final Your space screenshots show the clean Home with shortcuts and no transient snackbar. [Final Home image checks](final-home-image-checks.json). Feature screenshots are `screenshots/panel-{chat,create,discover,your-space}-{400,1280}-{light,dark}.png`.

Lighthouse 13 default mobile, 412×823px at DPR1.75, simulated 4× CPU slowdown and slow 4G, run sequentially after native capture stopped:

- Home: performance **95**, accessibility **100**, best practices **100**, SEO **100**; LCP **2.85s**, CLS **0.00033**.
- Release: performance **100**, accessibility **100**, best practices **100**, SEO **100**; LCP **1.35s**, CLS **0**.

[Home Lighthouse report](lighthouse-home.html), [release Lighthouse report](lighthouse-release.html), [machine-readable summary](lighthouse-summary.json). All scores meet the ≥90 target; Home misses the separate <2.5s LCP target. Six uncompressed render-blocking CSS requests account for an estimated 710ms improvement opportunity, and Lighthouse also flags image delivery, minification, and cache lifetimes. Hosting compression/cache behavior differs from the local Python preview. These are measured local-browser results; they cannot establish physical low-end Android performance.

Targeted image-delivery follow-up: a 400px DPR1 browser now loads `chat-240.webp` successfully (34,438-byte body, down from the 105KB variant). [Low-density check](low-density-hero-check.json). A single Home-only Lighthouse rerun after this change recorded 95/100/100/100 and LCP 2.85s; default mobile DPR1.75 still loads the 480px image. Release was not rerun because it is unchanged.

PASS — no blocking findings. Home LCP remains the documented performance warning.
