# Design QA — comparación de portafolio ideal

## Artifacts

- Source visual truth: user-provided reference image in the current conversation (no local filesystem path available).
- Source pixels: 1536 × 1024; source CSS size and device density are unknown.
- Implementation: `/portfolio`, default `grouped` state plus the `rings` and `stacked` tab states.
- Implementation screenshot path: unavailable because no in-app or connected browser was available in this session.
- Intended desktop viewport: 1536 × 1024 at device scale factor 1; density normalization could not be completed without a browser capture.

## Findings

- [P2] Browser-rendered comparison is unavailable.
  - Location: the complete `#portfolio-ideal` section in all three tab states.
  - Evidence: the local Flask response rendered successfully and the rendered JavaScript passed `node --check`, but browser discovery returned no available browser, so there is no implementation screenshot to place beside the source reference.
  - Impact: fonts, final canvas sizing, chart label collisions, color rendering, responsive spacing, and click/keyboard behavior could not be confirmed visually.
  - Fix: open the local app in an available browser, capture the default grouped view plus the rings and stacked states at 1536 × 1024, then compare those captures together with the source image.

## Fidelity surfaces

- Fonts and typography: implementation retains the product's IBM Plex Sans hierarchy; browser-level wrapping and antialiasing remain unverified.
- Spacing and layout rhythm: the selector, comparison chart, and persistent rebalance panel use the existing card spacing and responsive grid tokens; final rendered rhythm remains unverified.
- Colors and visual tokens: grouped bars use blue for Ideal and maple red for Actual as in the reference; stacked bars reuse the product's allocation palette; browser color output remains unverified.
- Image quality and asset fidelity: no raster imagery or custom icons are required for this data-visualization section; Chart.js renders the chart canvases.
- Copy and content: the default and alternate choices are present in Spanish, and all values come from the live strategic-allocation payload.

## Interaction and automated evidence

- Local route response: HTTP 200.
- Rendered JavaScript syntax: passed `node --check`.
- Primary interactions tested in a browser: not available; click and keyboard tab switching remain a visual/browser test gap.
- Console errors checked: not available without a connected browser.
- Automated suite: 285 tests passed, including 17 portfolio-view tests.
- Focused comparison evidence: unavailable for the same browser-capture blocker; code-only inspection was not treated as visual evidence.
- Comparison history: no visual iteration was possible because the first required implementation capture was blocked.

## Implementation checklist

- Connect an in-app or external browser.
- Capture all three comparison states at the matching desktop viewport.
- Check canvas labels, wrapping, responsive behavior, focus styles, and console output.
- Resolve any P0/P1/P2 visual mismatches and repeat the comparison.

## Follow-up polish

- Consider persisting the user's last selected view only if product behavior should favor preference memory over always opening in the requested default view.

---

# Design QA — comparador de acciones

## Artifacts

- Source visual truth 1: first comparator reference embedded in the user request (dense four-company indicator columns), displayed at 1500 × 779 px.
- Source visual truth 2: `/Users/manuel/Desktop/Screenshot 2026-08-20 at 12.55.39 PM.png` (normalized-performance chart and investment calculator), 1232 × 844 px.
- Source visual truth 3: latest comparator empty-state screenshot embedded in the user request, including the persistent top search, displayed at 1361 × 658 px.
- Implementation: `/tools/comparator` empty state and company-selector dialog, `/tools/comparator?asset=1` company-entry state and add-column dialog, and `/tools/comparator?asset=1&asset=2&asset=3&asset=4` authenticated four-company state.
- Implementation screenshot path: unavailable because browser discovery returned no connected in-app or external browser.
- Intended comparison viewport: 1500 × 900 CSS px at device scale factor 1. Density normalization could not be completed without a browser capture.

## Findings

- [P2] Browser-rendered visual comparison is unavailable.
  - Location: complete comparator, including the independent company columns, empty/one/four-company states, company-selector dialog, range selector, Chart.js canvas, investment calculator and both asset pickers.
  - Evidence: authenticated route tests cover the empty, one-company and four-company comparator states; browser setup completed but discovery returned an empty browser list, so the open-dialog implementation state could not be captured beside the latest source screenshot.
  - Impact: final modal placement, dropdown stacking, focus return, backdrop rendering, mobile fit, remote Material Symbols loading and pointer/keyboard interactions cannot be confirmed visually.
  - Fix: connect the in-app Browser, capture the modal from the empty-state button and the add-column slot at 1361 × 658, then capture a narrow 390 px state and compare them jointly with the source references.

## Fidelity surfaces

- Fonts and typography: implementation preserves TrueNorth's IBM Plex Sans/Mono and Instrument Serif hierarchy; final wrapping and antialiasing remain unverified.
- Spacing and layout rhythm: the reference's fixed label rail plus equal, separated company cards is implemented as a horizontally scrollable flex board with identical fixed row heights; browser-level proportions remain unverified.
- Colors and visual tokens: four distinct muted series colors, warm white surfaces, maple accent and semantic semaphores use the existing product tokens; browser output remains unverified.
- Image quality and asset fidelity: company identities reuse the product's real favicon/logo pipeline with an initial fallback. Material Symbols is used for search/close icons; no generated raster asset was needed for these data-driven screens.
- Copy and content: Spanish product copy covers comparison, periods, rankings, coverage, hypothetical investment, educational disclaimer and the new ticker/company selector guidance.
- Responsive behavior: CSS includes a compact mobile grid and intentional horizontal scrolling, but the browser state could not be captured.

## Interaction and automated evidence

- Authenticated local comparator responses: HTTP 200 for explicit empty, one-company and four-company states; the board contains 27 aligned indicators and never auto-selects a company.
- Authenticated company response: HTTP 200 with a `/tools/comparator?asset=<id>` entry point.
- Authenticated local rankings response: HTTP 200 with all three ranking families.
- Real provider smoke test: HTTP 200; RY returned 19 points and ENB returned 20 points for 1M, both normalized with ending returns.
- Primary interactions tested in a browser: unavailable; modal opening from the empty CTA and add-column slot, search results, keyboard selection, Escape/backdrop close, focus return, range switching, removal and investment-input updates remain browser test gaps.
- Console errors checked: unavailable without a connected browser.
- Automated suite: 296 tests passed; the reusable autocomplete script passed `node --check`; full Ruff check passed; `git diff --check` passed.
- Focused comparison evidence: unavailable for the same browser-capture blocker; source inspection and code/HTTP checks were not treated as visual evidence.
- Comparison history: no visual iteration was possible because the first implementation capture was blocked.

## Implementation checklist

- Connect the in-app Browser and capture desktop plus mobile states.
- Open the same selector dialog from the primary CTA, one-company secondary CTA and empty comparison column.
- Verify duplicate companies are excluded while the persistent top search remains usable.
- Verify column alignment, sticky metric labels, chart legend/axes and profile-menu links.
- Exercise add/remove, every period control and the investment calculator with keyboard and pointer.
- Check console output and remote font/icon loading.
- Resolve any resulting P0/P1/P2 findings and repeat the joint visual comparison.

## Follow-up polish

- If more date ranges become available in the market-data provider, extend the current 1M/6M/1A/5A control without changing the comparison layout.

final result: blocked

---

# Design QA — cintillo animado de mercados

## Artifacts

- Source visual truth path: `/Users/manuel/Documents/FinanceTracker/.claude/disenho/Comunidad.dc.html`, market strip at lines 29–37.
- Source dimensions: 1440 CSS px wide; the target strip is 34 CSS px high. Source density is not applicable to the HTML specification.
- Implementation: `src/templates/partials/market_strip.html` and the `.tn-market-*` rules in `src/static/css/styles.css`.
- Implementation screenshot path: unavailable because neither the in-app Browser nor Chrome was connected in this session.
- Intended comparison viewport: 1440 × 900 CSS px at device scale factor 1.
- State: authenticated page with S&P/TSX, S&P 500, NASDAQ, USD/CAD, BoC rate, and TSX session status populated.

## Findings

- [P2] Browser-rendered animation and visual comparison are unavailable.
  - Location: the global 34 px market ticker above the main navigation.
  - Evidence: browser selection failed for both the in-app surface and Chrome, so neither the source HTML nor the implementation could be captured and placed into a joint comparison.
  - Impact: final animation continuity, font antialiasing, exact gap rhythm, hover pause, clipping, and mobile speed cannot be visually confirmed.
  - Fix: connect a supported browser, capture the source and implementation at 1440 px, capture a second implementation frame after several seconds, and compare the strip region jointly.

## Fidelity surfaces

- Fonts and typography: implementation reuses the source product's IBM Plex Mono numeric style, 11.5 px size, and compact single-line treatment; browser rendering remains unverified.
- Spacing and layout rhythm: source measurements are preserved at 34 px height, 36 px desktop inset, 26 px indicator gaps, and 7 px status-dot gap; browser-level alignment remains unverified.
- Colors and visual tokens: dark ink background, muted warm foreground, green positive state, red negative state, and 7 px market-status dot match the HTML source values.
- Image quality and asset fidelity: the strip contains no raster assets or icons; the status dot is an existing semantic CSS indicator from the source component.
- Copy and content: labels and session copy remain data-backed and match the source component.

## Interaction and automated evidence

- Continuous behavior: two equal feed groups animate linearly from right to left without a reset gap.
- Primary interactions tested in a browser: unavailable. Hover/focus pause and reduced-motion fallback were verified by code and response structure only.
- Console errors checked: unavailable without a connected browser.
- Automated evidence: all 19 market-strip tests passed; Ruff and `git diff --check` passed. Full application visual startup remains unavailable because of unrelated concurrent authentication edits.
- Focused comparison evidence: unavailable because both source and implementation browser captures are missing.
- Comparison history: no visual iteration was possible because the required browser capture was blocked on the first pass.

## Implementation checklist

- Connect the in-app Browser or Chrome.
- Capture source and implementation at 1440 px and the implementation at 390 px.
- Confirm seamless looping, hover pause, reduced-motion behavior, and absence of console errors.
- Fix any resulting P0/P1/P2 mismatch and repeat the joint comparison.

## Follow-up polish

- Tune the 30-second desktop duration only after observing the ticker with production-length data.

final result: blocked
