# Merged UI/UX checklist

Each item names its source so a finding can cite it: **PR** = the project's own rules, **TS** = taste-skill critique pass or inspector id, **N** = Nielsen heuristic, **K** = Krug check, **L** = UX law, **W** = WCAG 2.2, **UP** = ui-ux-pro-max rule, **FD** = frontend-design. Where an item conflicts with PR, PR wins (see SKILL.md). Run the sections in order; each catches what the others miss.

Before §A, write down in one or two lines **who the main user is, on what device, and the three to five things they came to do.** Every later judgement is "does this help or hurt that person doing that". If the project's rules describe the user, use that description.

## A. Look at the screenshots (visual passes)

Do each on its own; don't blend them.

1. **One second** (TS 1, design-critique first impression). Glance at `mobile-fold.jpg` and look away. What did you see? Is the page's purpose clear without reading? Is the one thing that should dominate the fold actually dominating?
2. **Squint / grayscale** (TS 2, design-review). Blur until text is grey bars: two or three large masses with clear size steps? Does hierarchy survive without colour (pastels and same-lightness hues collapse in grayscale)?
3. **The user's first question** (TS 5/12, K3). On the first one or two phone screens, is the answer to the main user's first question visible in large type? Within a few scrolls, the next ones, and the primary action?
4. **Edges and alignment** (TS 4, design-review). Blocks share edges or a centre and a width. Look for blocks narrower or wider for no reason, and near-alignment off by a few px.
5. **Space** (TS 5, L proximity). Related things close, sections clearly further apart than items inside them. Look for holes: a short column beside an empty one, a gap under a removed element, and the inspector's `empty-screens` on desktop.
6. **Type** (TS 6, FD, inspector `size-count`, `headline-lines`, `measure`). Few sizes far apart (aim for about five roles). No heading over two lines at 375 px. No orphan word on a heading's last line. Paragraphs under ~75 characters per line. Only the project's chosen families.
7. **Colour** (TS 7, PR). Name the proportions: ground, ink, accent. The accent should mark actions or the one important thing, not appear everywhere. Every colour should come from a token.
8. **Images and icons** (TS 8). One icon set, one stroke weight, one illustration style. Anything blurry, stretched, or a grey box? Missing images degrade to an intended state, not a broken-image icon.
9. **Sameness** (TS 9). Write one word per section's layout (cards, list, split, grid, form, quote…). Three identical card rows in a row is the template showing.
10. **Phone composition** (TS 10). Is 375 px its own layout or the desktop squeezed? Spend findings on the primary device first; the secondary one must not look broken.
11. **Fullness and substance** (TS 11/12). Does every section deliver its information fully at a readable size? A section reduced to a heading and a line is underbuilt.
12. **Collisions** (TS 13, inspector `covered-text`, `clipped-text`, `overflow`, `side-scroll`). Nothing over a heading or a button at any scroll position; sticky/fixed elements and decorations not covering text; nothing off the right edge at 320/375.
13. **The idea carried through** (TS 3/14, FD). If the site has a distinctive idea or style, does it reach the forms, empty states and footer, or do they turn stock after the hero? Is there one memorable thing, and is everything around it quiet?

## B. The user's tasks (usability)

Walk each key task as the main user, on their device. Count taps; note every hesitation. For each task, check:

| Check | Sources |
|---|---|
| The entry point is obvious, labelled with what it does, and big enough to hit | N1, K1, L Fitts, W 2.5.8 |
| The information needed to decide is on screen when deciding (price, date, requirements) | N6, K3 |
| Forms: visible labels, sensible defaults, only the fields needed, conditional fields hide when irrelevant, correct input types and `autocomplete` | N5, W 1.3.5, 3.3.2, UP forms |
| Errors next to the field, in plain language, with how to fix it; input preserved | N9, W 3.3.1/3.3.3 |
| Success confirmed and announced (`aria-live`/`role=status`); repeating the action does what the user expects (update vs duplicate) and says so | N1, W 4.1.3 |
| Anything that auto-plays (audio, video, carousel) can be paused, and the control says what it does | W 1.4.2, 2.2.2, N3 |
| Recovery: back button, closing overlays, undo or confirm on destructive actions; no dead ends | N3, N5 |
| Personalised or parameterised views (names, filters from the URL) render long or odd values without breaking | PR |

Krug across the page: everything clickable looks clickable and nothing else does (K1); labels say what they do (K3); no happy talk, splash or interstitial between the user and the content beyond what the project deliberately chose (K5).

## C. Accessibility (WCAG 2.2 AA)

Most failures, in order of likelihood:

- **Contrast** (W 1.4.3, 1.4.11). Body ≥4.5:1, large text (24 px+, or 18.66 px bold) ≥3:1, controls, focus rings and meaningful graphics ≥3:1. Compute token pairs yourself; check text over images, patterns and gradients, and placeholder text.
- **Size and resize** (W 1.4.4, 1.4.12). Body around 16 px, nothing important under ~13 px; text at 200% and with increased spacing survives without clipping or overlap.
- **Targets** (W 2.5.8: 24×24 px minimum or enough spacing; 44 px if the project asks). Icon buttons, close buttons, carousel arrows, inline links in dense lists.
- **Keyboard** (W 2.1.1, 2.1.2, 2.4.3, 2.4.7, 2.4.11). Everything reachable, logical order, visible `:focus-visible`, focus not hidden under sticky headers or fixed buttons, modals trap and return focus, Esc closes.
- **Names and roles** (W 4.1.2, 1.1.1). Icon-only buttons have an accessible name in the page's language; toggles expose `aria-expanded`/`aria-pressed`; decorative images `alt=""` or `aria-hidden`; meaningful images have real `alt`.
- **Structure** (W 1.3.1, 2.4.6, 3.1.1). One `h1`, no skipped heading levels, correct `lang`, landmarks, lists as lists, tables with headers.
- **Status** (W 4.1.3). Form results, loading and async updates announced.
- **Motion** (W 2.2.2, 2.3.3). Decorative motion stops or calms under `prefers-reduced-motion`; nothing flashes more than 3×/s; moving things don't sit on top of text being read.
- **Reflow and orientation** (W 1.4.10, 1.3.4). 320 px with no horizontal scroll; landscape works.
- **Input** (W 2.5.1, 2.5.7). Swipe and drag have a single-pointer alternative (buttons).

## D. Devices and browsers

- The target browsers from PR (in-app WebViews of Messenger/Zalo/Instagram/TikTok, old iOS Safari, kiosks…): no reliance on hover, popups or file downloads that WebViews block; flag CSS/JS newer than the baseline without a fallback.
- Inputs under 16 px zoom the page on iOS Safari.
- On-screen keyboard covering the lower half: the focused field and the submit button stay reachable; fixed bottom bars don't ride up over the input.
- Safe areas: fixed controls clear of the notch and home indicator (`env(safe-area-inset-*)`).
- `100vh` on mobile (use `dvh`/`svh` with a fallback).
- First paint light: images sized (`width`/`height` or `aspect-ratio`, no layout jump), below-the-fold images lazy, fonts with `font-display`, no heavy media before it's needed (UP performance).

## E. Consistency with the site's design system

- Colours, spacing, radii and shadows from tokens; a literal value in a component is P2 (PR).
- Components of the same kind share one implementation and look (borders, radii, padding, states). Mismatched border thickness or corner style between boxes is visible in screenshots.
- Buttons look alike for the same role; primary vs secondary vs destructive clear (L similarity, N4).
- Every interactive element has hover (where hover exists), focus, active and disabled states that match.
- Spacing follows a rhythm; same-level things use the same gaps (UP spacing).
- Emoji or text symbols (♪, ✓, →, ★) standing in for icons: use the icon set or a word (TS `emoji`, UP no-emoji-icons).

## F. Motion

- Purpose: feedback > continuity > delight (design-review). Decorative motion must not compete with reading or with forms.
- Animate `transform`/`opacity`, not layout properties. Feedback ~100–200 ms; entrances not on every block (FD, TS motion tells).
- Reduced motion respected everywhere, including JS/canvas animation loops and autoplaying carousels.
- Reveal-on-scroll never leaves a blank band if the observer doesn't fire, or with JS off (TS cap).

## G. Words

- The page's language, correct spelling and diacritics, a register that fits the audience (PR).
- Buttons say what happens ("Send RSVP", not "Submit"); the same action keeps the same name through the flow (FD).
- Errors explain what happened and how to fix it; no blame, no codes, no untranslated framework messages (N9, FD).
- Empty states guide toward the first action (design-critique).
- Placeholder copy is not a finding; how the layout handles it is (PR).
- Small labels above headings (TS `eyebrow`): keep only when they carry information the heading doesn't; say which.

## H. Generated-look check (taste-skill + frontend-design, filtered)

Look for: identical box after identical box with no change of composition; one accent colour on every element so nothing stands out; every section fading up the same way; filler copy ("Unlock the power of…", "Seamless", "Elevate"); a distinctive hero followed by stock sections; too many type sizes; emoji icons; the same three-feature-card row every template has. Skip any tell whose rule id is in the project's `allow` list.
