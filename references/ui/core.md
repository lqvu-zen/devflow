# Core checklist (every platform)

These rules hold for web pages, desktop and mobile apps, and game UI. The platform layers (`web.md`, `app.md`, `game.md`) add their own numbers and mechanics; `tells.md` holds the generated-look registry. Where an item conflicts with the project's own rules (PR), PR wins (see SKILL.md). Run the sections in order; each catches what the others miss.

Before §1, write down in one or two lines **who the main user is, on what device, and the three to five things they came to do.** Every later judgement is "does this help or hurt that person doing that". If the project's rules describe the user, use that description. For an app or game also note the screen shape, resolution or DPI, viewing distance, locale and input methods (Qt `qt-ui-design` 1.7.3 §0).

## Source keys

Each rule names its source so a finding can cite it, and ends with **(M)** when the standard is measurable or **(T)** when it is one author's taste or a judgement.

| Key | Source |
|---|---|
| PR | the project's own rules and design system |
| TS | taste-skill critique passes, read at `c924fad`; vendored copy `12af471`, same pass numbers |
| N1–N10 | Nielsen's ten heuristics (N1 visibility of system status, N2 match with the real world, N3 user control and freedom, N4 consistency and standards, N5 error prevention, N6 recognition over recall, N7 flexibility and efficiency, N8 minimalist design, N9 help with errors, N10 help and documentation) |
| K1, K3, K5 | Krug, *Don't Make Me Think*: K1 don't make me think, K3 users scan, K5 omit needless words |
| L | UX laws (Fitts, Hick, proximity, similarity, and so on) |
| W | WCAG 2.2 success criterion |
| FD | frontend-design skill, current text |
| UP | ui-ux-pro-max rule database, v2.15.0 (optional) |
| DS | design-skills 1.0.0 (MIT) |
| OD | Open Design `5e9a5e6` (Apache-2.0), `craft/state-coverage.md` |
| EK | Emil Kowalski skills `a81dbca` (MIT), `break-ui` |
| HM | Hallmark `8f6969f` (MIT) |

## 1. Visual passes (look at the screenshots)

Do each on its own; don't blend them.

1. **One second** (TS 1). Glance at the first screen and look away. What did you see? Is the screen's purpose clear without reading? Is the one thing that should dominate actually dominating? (T)
2. **Squint / grayscale** (TS 2). Blur until text is grey bars: two or three large masses with clear size steps? Does hierarchy survive without colour (pastels and same-lightness hues collapse in grayscale)? (T)
3. **The user's first question** (TS 5/12, K3). On the first one or two screens of the primary device, is the answer to the main user's first question visible in large type? Within a few scrolls or taps, the next ones, and the primary action? (T)
4. **Edges and alignment** (TS 4). Blocks share edges or a centre and a width. Look for blocks narrower or wider for no reason, and near-alignment off by a few px. (T)
5. **Space** (TS 5, L proximity). Related things close, sections clearly further apart than items inside them. Look for holes: a short column beside an empty one, a gap under a removed element. (T)
6. **Type** (TS 6, FD). Few sizes far apart: aim for about five roles unless the design system says otherwise. No heading over two lines on the narrowest screen. No orphan word on a heading's last line. Running text at most about 75 characters per line (the game layer uses 80). Only the project's chosen families. (M for the counts, T for the rest)
7. **Colour** (TS 7, PR). Name the proportions: ground, ink, accent. The accent should mark actions or the one important thing, not appear everywhere. Every colour should come from a token. (T)
8. **Images and icons** (TS 8). One icon set, one stroke weight, one illustration style. Anything blurry, stretched, or a grey box? Missing images degrade to an intended state, not a broken-image icon. (T)
9. **Sameness** (TS 9). Write one word per section's layout (cards, list, split, grid, form, quote…). Three identical card rows in a row is the template showing. (T)
10. **Primary-device composition** (TS 10). Is the smallest or primary screen its own layout or the large one squeezed? Spend findings on the primary device first; the secondary one must not look broken. (T)
11. **Fullness and substance** (TS 11/12). Does every section deliver its information fully at a readable size? A section reduced to a heading and a line is underbuilt. (T)
12. **Collisions** (TS 13). Nothing over a heading or a button at any scroll position or window size; sticky or fixed elements and decorations not covering text; nothing cut off at the edge of the narrowest screen. (M, measured by the inspector on web; judged by eye elsewhere)
13. **The idea carried through** (TS 3/14, FD). If the product has a distinctive idea or style, does it reach the forms, empty states and footer, or do they turn stock after the first screen? Is there one memorable thing, and is everything around it quiet? (T)

## 2. States and feedback

For every component that can change, check that each state the design system names exists and is distinguishable from the others. The full list: default, hover, focus, active/pressed, disabled, loading, empty, error, success, selected, expanded, dragging (DS 1.0.0, OD). Hallmark's eight-state table is the cross-check (HM `interaction-and-states.md`).

- **Error is never collapsed into empty.** A failed load and a list with nothing in it look and read differently. (OD) (M)
- Form states: untouched, dirty, submitted-pending, error, success. (OD) (M)
- Disabled is signalled by more than opacity alone. (HM gate 39a) (M)
- Worst-case data: a 200-character title, zero items, thousands of rows, a missing image, non-Latin text, right-to-left. Translated text may run 30–40% longer (Qt `qt-ui-design` §1.5). (EK, OD) (M)
- Every action gets feedback inside about 100 ms, and a task over a second shows progress. (N1, Qt `qt-ui-design` §1.1) (M)

## 3. The user's tasks (usability)

Walk each key task as the main user, on their device. Count taps; note every hesitation. For each task, check:

| Check | Sources |
|---|---|
| The entry point is obvious, labelled with what it does, and big enough to hit | N1, K1, L Fitts, W 2.5.8 |
| The information needed to decide is on screen when deciding (price, date, requirements) | N6, K3 |
| Forms: visible labels, sensible defaults, only the fields needed, conditional fields hide when irrelevant | N5, W 3.3.2, UP forms |
| Errors next to the field, in plain language, with how to fix it; input preserved | N9, W 3.3.1/3.3.3 |
| Success confirmed and announced to assistive technology; repeating the action does what the user expects (update vs duplicate) and says so | N1, W 4.1.3 |
| Anything that auto-plays (audio, video, carousel) can be paused, and the control says what it does | W 1.4.2, 2.2.2, N3 |
| Recovery: back, closing overlays, undo or confirm on destructive actions; no dead ends | N3, N5 |
| Personalised or parameterised views (names, filters) render long or odd values without breaking | PR |

Krug across the screen: everything clickable looks clickable and nothing else does (K1); labels say what they do (K3); no happy talk, splash or interstitial between the user and the content beyond what the project deliberately chose (K5). (T)

## 4. Accessibility principles

Most failures, in order of likelihood. The numbers for each platform are in its own layer.

- **Contrast** (W 1.4.3, 1.4.11). Text 4.5:1; large text, controls, focus indicators and meaningful graphics 3:1. Compute token pairs yourself; check text over images, patterns and gradients, and placeholder text. What counts as large text differs by platform (see the layers). (M)
- **Resize** (W 1.4.4, 1.4.12). Text can be enlarged to 200% and with increased spacing survives without clipping or overlap. (M)
- **Targets** (W 2.5.8). Every control is big enough to hit; the number is per platform and the design system overrides it. (M)
- **Keyboard or controller** (W 2.1.1, 2.1.2, 2.4.3, 2.4.7, 2.4.11). Everything reachable, logical order that follows the layout, a visible focus indicator, focus not hidden under sticky elements, dialogs trap and return focus, a way back out. (M)
- **Names and roles** (W 4.1.2, 1.1.1). Icon-only controls have an accessible name in the product's language; toggles expose their state; decorative images are hidden from assistive technology; meaningful images have a text alternative. (M)
- **Status** (W 4.1.3). Form results, loading and async updates are announced. (M)
- **Motion** (W 2.2.2, 2.3.3). Decorative motion stops or calms under the system's reduced-motion setting; nothing flashes more than 3×/s; moving things don't sit on top of text being read. (M)
- **Single pointer** (W 2.5.1, 2.5.7). Swipe and drag have a single-pointer alternative (buttons). (M)
- **Colour is never the only signal** (W 1.4.1). (M)

## 5. Consistency with the design system

- Colours, spacing, radii and shadows from tokens; a literal value in a component is P2 (PR). (M)
- Components of the same kind share one implementation and look (borders, radii, padding, states). Mismatched border thickness or corner style between boxes is visible in screenshots. (T)
- Buttons look alike for the same role; primary vs secondary vs destructive clear (L similarity, N4). (T)
- Every interactive element has hover (where hover exists), focus, active and disabled states that match. (M)
- Spacing follows a rhythm; same-level things use the same gaps (UP spacing). (T)
- Where the design system's "Do's and Don'ts" name a rule, a violation is a finding and the design system wins over any rule here. (PR)

## 6. Motion principles

- Purpose: feedback, then orientation, then delight (DS, design-review). Decorative motion must not compete with reading or with forms. (T)
- Feedback is quick (about 100–200 ms); entrances are not on every block (FD, TS motion tells). (T)
- Reduced motion is respected everywhere, including scripted loops and autoplaying carousels. (W 2.2.2) (M)
- The platform layers add the mechanics (which properties to animate, how reveal-on-scroll fails).

## 7. Words

- The product's language, correct spelling and diacritics, a register that fits the audience (PR). (T)
- Buttons say what happens ("Send RSVP", not "Submit"); the same action keeps the same name through the flow (FD). (T)
- Errors explain what happened and how to fix it; no blame, no codes, no untranslated framework messages (N9, FD). (T)
- Empty states guide toward the first action (design-critique). (T)
- Placeholder copy is not a finding; how the layout handles it is (PR).
