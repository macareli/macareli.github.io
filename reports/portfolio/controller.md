# Portfolio controller review

Reviewed the assembled public home, release and 404 pages and their owning source against `DESIGN.md`, `notes.md`, the Material component overview, buttons, tabs and icon-button references, style references, and engineering architecture, quality, metadata and performance guidance. This is a source/controller review; browser and Lighthouse delivery checks belong to the independent tester report.

| Page or file | Severity | Kind | Detail | How to reproduce |
| --- | --- | --- | --- | --- |
| Reviewed feature | — | Final recheck | No outstanding findings. The previous three warnings are resolved as recorded below. | Inspected the changed source, recorded design decisions and current assembled-site checker output. |

The component choices fit the needs: two-page public-site navigation, feature tabs for related content, native details for optional instructions, native anchors for navigation and the same-origin file download. The documented brand, display typography, shapes and website-navigation exceptions were honored. Color pairs are token-based, the shared focus rule is 3px, the controls have 48px minimum targets, and tabs expose roving keyboard focus, selection and panel relationships. The shell supplies one main landmark, one h1 per page, skip links, names and image alt text.

Release metadata comes from validated official GitHub release data at build time, rather than hardcoded release figures in the page. The pipeline validates the expected official asset URL, uploaded state, size and SHA-256, verifies the mirrored APK, escapes release content and publishes atomically. Downloads use an ordinary same-origin link; click feedback explicitly reports a request, not completed delivery. Checksum copy includes visible success and fallback feedback. No client secret or growing runtime list/form is present. The pending final screenshot integration was not treated as a finding about the supplied provisional image content.

Checker command and complete output:

```text
$ python3 scripts/check_material.py --site-root _site _site

0 finding(s).
```

Release checks:

```text
$ python3 -m unittest discover -s tests -v
Ran 13 tests in 0.042s
OK
```

Current measured source payloads: JavaScript 3,159 bytes / 1,224 bytes gzip; home CSS 76,744 bytes / 12,757 bytes gzip across its six stylesheets; release CSS 67,625 bytes / 11,277 bytes gzip. Both are below the reference's 200KB JS and 50KB CSS gzip budgets. These measurements exclude fonts and images; final image delivery and mobile LCP remain browser-test responsibilities.

Recheck: the builder corrected HTML validation details and added the assembled Material checker as a CI step at `.github/workflows/deploy.yml:51`. The checker was rerun after these changes and still reports zero findings. The initial CI-gate warning is resolved.

Final focused recheck: `src/components/controls.css:85` now defines 48px inline tabs; `:156` defines 64px stacked tabs with 24px icons. The selected indicator is attached to `.tab-label` at `:97`, giving label-width geometry. `src/pages/index.html:58` supplies the label spans. `src/layouts/header.html:3` now embeds the official Google Material Symbols Rounded subset, with provenance in `DESIGN.md:35` and its Apache 2.0 license in `assets/material-icons-LICENSE.txt`. The 48px painted compact actions are an explicit, reasoned design exception at `DESIGN.md:35`, resolving the prior undocumented-deviation warning. All three previous warnings are closed. The assembled Material checker was rerun and still reports `0 finding(s).`

Verdict: PASS — no outstanding findings.
