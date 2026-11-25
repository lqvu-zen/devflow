# Game layer

Read after `core.md` for game UI: HUD, menus, settings, pause, in any engine (Unity named where the source was read). Evidence is a screenshot of each state at each resolution, plus the UI source (D5: no measuring tool). Numbers are defaults; the design system overrides them. Sources were read on 2026-10-29. Each rule ends with **(M)** measurable or **(T)** taste; a gap is marked as a gap, with no number.

Source keys: XAG Xbox Accessibility Guidelines v3.2 (licence not confirmed; paraphrased); GAG gameaccessibilityguidelines.com (licence not stated; paraphrased); UNI Unity 6000.0 UI Toolkit and ugui docs (terms unverified); UP ui-ux-pro-max.

## 1. Readability

- **Body text, TV:** at least 28 px at 1080p (GAG, citing the 10-foot UI); XAG's console minimum is 26 px at 1080p (52 px at 4K), measured ascender to descender. (M)
- **Body text, PC and VR:** at least 18 px at 1080p (36 px at 4K) (XAG). Mobile scales linearly with DPI. (M)
- **Subtitles:** larger than body text, at least 46 px at 1080p (GAG); at most 40 characters per line and 2 lines; mixed case; speaker name shown; size scalable to 200%; background configurable; on by default or settable before the first sound; live preview in the settings (XAG). (M)
- **Resize:** every text scales to 200% with no two-way scrolling (XAG). (M)
- **Line length** at most 80 characters (40 for CJK), line spacing at least 1.5, letter spacing 0.12 em, word spacing 0.16 em (XAG). (M)
- **Contrast:** 4.5:1 for text and HUD, 3:1 for large text and inactive elements, a 7:1 high-contrast mode; measured against the worst background area behind the element (XAG). (M)
- **Colour** is never the only signal. A colour-blind mode comes from XAG 103 only (GAG has no such guideline). (M)

## 2. Layout and safe zones

- A declared reference resolution and a justified scaling choice (Canvas Scaler *Scale With Screen Size*, or Panel Settings) (UNI). (M)
- The HUD sits under a safe-area root and full-bleed backgrounds sit outside it. `Screen.safeArea` has its origin at the bottom-left, UI Toolkit at the top-left (UNI). (M)
- TV safe-zone percentages, viewing distance and diegetic versus non-diegetic UI: gaps, no source gives a number. Judge by screenshot and mark as taste. (T)
- HUD readability: judge each element at play distance and at TV distance; a HUD element outside the safe area or hidden by a bright background is a finding. (T)

## 3. Input and navigation

- The whole UI is operable by keyboard or controller; focus order follows the layout; every focusable element shows a focus state (XAG). (M)
- Linear menus wrap at the ends and grids do not; there is a route back to the main menu (XAG). (M)
- Activate on release, with a way to cancel by moving off the control (XAG). (M)
- Every control is remappable, and the on-screen hints update when it is (XAG). (M)
- Input glyphs switch with the active device. Switching through `PlayerInput.onControlsChanged` and `GetBindingDisplayString` is **not verified** (secondary sources only). (T)
- Touch targets on a phone at least 15 mm, on a tablet 24 mm (XAG). (M)
- An accessibility prompt at first launch (XAG). (T)

## 4. Menus, settings and pause

- Settings are reachable from the main menu and from pause, and take effect in a live preview where they change what is on screen (XAG). (T)
- Pause-menu structure: a gap, no source; judge consistency with the rest of the menus. (T)
- Non-interactive elements do not block input: Raycast Target is off on non-interactive images, there is one EventSystem and a GraphicRaycaster (UNI, `unity` skill). (M)

## 5. Unity UI Toolkit and uGUI, from source

- A theme style sheet with USS variables, not literal values (UNI). (M)
- Focusable elements carry a `tabIndex` that matches the visual order; a `VisualElement` is not focusable by default (UNI). (M)
- USS has no `gap`, `z-index` or `box-shadow`; transitions go on the base class, not on `:hover` (`unity` skill). (M)
- Text expansion and a CJK fallback font are planned for (`unity` skill, Qt `qt-ui-design` §1.5). (M)
