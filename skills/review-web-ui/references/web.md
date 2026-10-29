# Web layer

Read after `core.md` for a web page or site. The numbers here are the web defaults; the project's design system overrides them. Sources are keyed as in `core.md`; the WCAG criteria are WCAG 2.2 AA. Each rule ends with **(M)** measurable or **(T)** taste.

## 1. Inspector rule ids

The inspector (`vendor/taste-skill/scripts/`) measures the real page. Its ids map to the core passes:

| Pass in `core.md` | Inspector ids |
|---|---|
| §1.5 Space | `empty-screens` (desktop) |
| §1.6 Type | `size-count`, `headline-lines`, `measure` |
| §1.12 Collisions | `covered-text`, `clipped-text`, `overflow`, `side-scroll` |
| Generated-look tells | `emoji` and the house rules listed in SKILL.md |

The measurement ids are never waived for taste (SKILL.md). (M)

## 2. Accessibility specifics (WCAG 2.2 AA)

- **Contrast** (W 1.4.3, 1.4.11). Body ≥4.5:1; large text (24 px+, or 18.66 px bold) ≥3:1; controls, focus rings and meaningful graphics ≥3:1. (M)
- **Size and resize** (W 1.4.4, 1.4.12). Body around 16 px, nothing important under about 13 px. (M)
- **Targets** (W 2.5.8). 24×24 px minimum or enough spacing; 44 px if the project asks. Icon buttons, close buttons, carousel arrows, inline links in dense lists. (M)
- **Keyboard** (W 2.1.1, 2.1.2, 2.4.3, 2.4.7, 2.4.11). Visible `:focus-visible`; focus not hidden under sticky headers or fixed buttons; modals trap and return focus; Esc closes. (M)
- **Names and roles** (W 4.1.2, 1.1.1). Toggles expose `aria-expanded`/`aria-pressed`; decorative images `alt=""` or `aria-hidden`; meaningful images have real `alt`. (M)
- **Structure** (W 1.3.1, 2.4.6, 3.1.1). One `h1`, no skipped heading levels, correct `lang`, landmarks, lists as lists, tables with headers. (M)
- **Status** (W 4.1.3). Results announced through `aria-live` or `role=status`. (M)
- **Motion** (W 2.2.2, 2.3.3). Decorative motion calms under `prefers-reduced-motion`; a JS-driven loop or scrub trigger is killed or set to `duration: 0` (GSAP skills `aed9cfd`, MIT). (M)
- **Reflow and orientation** (W 1.4.10, 1.3.4). 320 px with no horizontal scroll; landscape works. (M)
- **Forms** (W 1.3.5, 3.3.2). Correct input types and `autocomplete`. (M)

## 3. Devices and browsers

- The target browsers from PR (in-app WebViews of Messenger/Zalo/Instagram/TikTok, old iOS Safari, kiosks…): no reliance on hover, popups or file downloads that WebViews block; flag CSS/JS newer than the baseline without a fallback. (M)
- Inputs under 16 px zoom the page on iOS Safari. (M)
- On-screen keyboard covering the lower half: the focused field and the submit button stay reachable; fixed bottom bars don't ride up over the input. (M)
- Safe areas: fixed controls clear of the notch and home indicator (`env(safe-area-inset-*)`). (M)
- `100vh` on mobile: use `dvh`/`svh` with a fallback (HM gate 6a). (M)
- First paint light: images sized (`width`/`height` or `aspect-ratio`, no layout jump), below-the-fold images lazy, fonts with `font-display`, no heavy media before it is needed (UP performance). (M)
- A page that renders unchanged without the enhancement (WebGPU, a shader, an observer) is the baseline; the enhancement is progressive.

## 4. Motion mechanics

- Animate `transform` and `opacity`, not layout properties (`width`, `height`, `top`, `left`, `margin`, `padding`); `filter`, `backdrop-filter` and `clip-path` are allowed but costly, so call out each use (HM gates 10a/10b, GSAP skills, Impeccable `5e745ac`). (M)
- Reveal-on-scroll never leaves a blank band if the observer does not fire, or with JS off: visible by default, hidden only under a `.js` class (HM gate 62, TS cap). (M)
- Off-screen animations are killed or paused. (GSAP skills) (M)
