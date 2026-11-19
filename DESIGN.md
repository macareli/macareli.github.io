# MaiChat website design

The portfolio presents MaiChat, a universal AI roleplay harness for Android built with Flutter. The primary path is to understand the product, then download the actual public Android release from `/release/` on maichat.me.

## Recorded direction

The user explicitly requested Material Design 3 Expressive, playful shapes, the original README palette, interactive product exploration, and responsive desktop/mobile layouts. The established recommendation is implemented; no additional approval is needed.

- Source color: plum `#462957`; Material Color Utilities fidelity scheme in `src/tokens/generated-scheme.css`.
- Exact artwork samples: shape purple `#5E3775`, lavender `#BDA5C7`, lilac `#C5A4D6`. Brand override roles live in `src/tokens/theme.css` as `--md-sys-color-brand-*`.
- Hero: plum primary container with lavender on-container text. Lilac buttons use plum text. Shape purple carries decoration, not small lavender body text.
- Fonts: Outfit display with DM Sans body, locally hosted variable Latin woff2 fonts, weights 400–700, `font-display: swap`. System sans-serif fallback remains available.
- Native semantic HTML components with token CSS; no web component framework or runtime dependency. The project did not have a component library.
- Navigation: compact static portfolio header, visible download link at all widths, in-page exploration and question links on desktop. This is a public two-page website, so a persistent Android navigation bar/desktop navigation rail would be inappropriate.
- Main interaction: four primary feature tabs, showing actual Android app screenshots. ARIA tabs, roving tab index, Left/Right/Home/End keyboard behavior, native buttons and focusable panels.
- Native `details` elements for questions, install instructions, and updates. No custom modal, dropdown, carousel, or scroll library.
- Light and dark themes respect system preference, with a persistent manual theme toggle. Brand hero panels retain the original plum/lavender combination across themes.
- Desktop: editorial text beside an actual phone screenshot, asymmetrical decorative shapes. Smooth four-lobed clover and eight-lobed flower SVG masks echo the rounded silhouettes in the README artwork. Mobile: source order remains text then app preview; smaller phone frame, responsive typography, stacked feature panels.
- Delivery bar: zero serious/critical axe violations, no horizontal overflow at 320px+, keyboard and theme checks, 200% text/zoom checks, reduced motion. Target Lighthouse mobile performance/accessibility/best practices/SEO ≥90, LCP <2.5s, CLS <0.1; actual test reports are recorded by the integration/testing agents.

## Deliberate deviations

- Exact branded hero colors override selected generated container roles to preserve the user's existing identity. Measured plum/lavender normal-text contrast is 5.46:1; plum/lilac is 5.63:1.
- Expressive marketing headline sizes, page corners, phone outlines, and decorative silhouettes extend the baseline type/shape tokens. They are named token overrides; they do not change Material control geometry.
- Decorative shapes are more prominent than a utility app, in direct response to the user's request for a playful portfolio full of shapes. They are hidden from assistive technology and never contain essential text.
- Source photographs/screenshots are not altered. App content is illustrative product content captured in the running public Android app; it is not an in-browser AI chat or a simulated live session.
- The download page uses an ordinary same-origin download anchor and works without JavaScript. Click feedback reports that the browser request was made, never that download completed.
- Header/footer render at build time; JavaScript is only for theme preference, tabs, checksum copying, and download feedback.
- Original SVG mark is displayed as a CSS mask so its `currentColor` artwork adapts correctly to light/dark themes. The SVG remains the site's favicon.

## Ownership and source layout

`src/pages` composes the UI, `src/layouts` supplies shared header/footer and shell, `src/components` owns controls and page components, `src/lib/app.js` supplies behavior. Release version, date, file size, filename, download URL, notes, checksum, and source URL come from build-time release metadata; there is no client-side release API fetch.

Icons use the official Google Material Symbols Rounded SVG subset (download, auto_awesome, chat_bubble, dark_mode, check, grid_view, explore) from google/material-design-icons, with Apache 2.0 license in assets/material-icons-LICENSE.txt. The compact header and checksum actions intentionally paint a 48px control to match their touch target; this marketing site favors a clear compact action over a 40px painted area plus invisible hit padding. Feature tabs use 48px inline / 64px stacked containers, 24px icons, and label-width primary indicators.
