# App layer (desktop and mobile)

Read after `core.md` for a desktop or mobile application: Qt/QML, iOS, Android, Windows, macOS. Evidence is a screenshot of each state at each size or scale, plus the UI source (D5: no measuring tool). The numbers are defaults per platform; the design system overrides them. Sources were read on 2026-10-29. Apple's Human Interface Guidelines, Material 3 and parts of the Fluent and Qt pages were read only in part or not at all: a rule resting on one of those says **not verified**. Each rule ends with **(M)** measurable or **(T)** taste.

Source keys: HIG Apple Human Interface Guidelines; AND Android developer docs and Google Accessibility Help; FLU Fluent 2 and Microsoft Learn; QT Qt 6.12 docs; QTS `qt-ui-design` 1.7.3; QMR `qt-qml-review` lint ids (cited, not restated); UP ui-ux-pro-max `app-interface.csv`.

## 1. Platform conventions

- Follow the platform's own conventions for navigation, controls and dialogs (HIG, AND, FLU); a custom control that replaces a native one needs a reason the design system states. (T)
- Use semantic or system colours and fonts where the platform has them; hard-coded colours block dark mode and high-contrast themes (HIG, FLU). (M)
- Material 3 specifics (colour roles, elevation, window size classes at 600/840 dp) are **not verified**: no M3 page was read. (T)

## 2. Window size and DPI scaling

- Sizes are device-independent (QT). Test at `QT_SCALE_FACTOR=2` as a screenshot aid; Windows uses per-monitor DPI v2 with 25% steps, integer scales preferred; provide `@2x` assets. (QT) (M)
- The window resizes without clipping or overlap down to its stated minimum; text reflows down to 320 px wide (FLU, W 1.4.10). (M)
- Text can be enlarged to 200% (HIG, FLU: text scale factor [1, 2.25]) without loss. (M)
- Window size classes and multi-window layouts that fill the space: a gap with no number. (T)

## 3. Desktop

- Keyboard shortcuts and menus follow the platform; every command reachable from a menu has a shortcut where the platform expects one: a gap, no number. (T)
- macOS control height 28 pt (20 pt minimum); Windows touch-and-pointer target about 40 px (7.5 mm at 135 PPI), larger for frequent or severe-consequence targets (HIG, FLU). (M)
- Focus is not lost after a dialog closes; it returns to the control that opened it (FLU). (M)

## 4. Mobile

- Touch targets: iOS 44 pt (28 pt is a floor, not a target); Android 48 dp with 8 dp between targets; physical size about 9 mm (HIG, AND, UP). (M)
- Space around controls: about 12 pt around bezeled and 24 pt around unbezeled elements on iOS (HIG). (M)
- Content stays inside the safe areas; full-bleed backgrounds may extend outside. iOS margin point values are **not verified**. (HIG, UP) (M)
- System gestures (back, home, notification edges) are not shadowed by custom gestures: a gap, no number. (T)
- Swipe actions have an accessibility action (AND). (M)
- Press feedback within 80–150 ms (UP `app-interface.csv`). (M)

## 5. Text and contrast

- Minimum text: iOS 11 pt (17 pt default), macOS 10 pt (13 pt default) (HIG). (M)
- Contrast 4.5:1 for text up to 17 pt, 3:1 at 18 pt or bold; icons and non-text 3:1 (HIG, FLU, UP). Large text for FLU is 18.5 px bold or 24 px. (M)
- Dark mode: 4.5:1 floor, with a 7:1 target for small custom colours; test with Increase Contrast and Reduce Transparency on (HIG). Material dark theme is a gap, **not verified**. (M)

## 6. Accessibility in source

- Every control has an accessible name (`contentDescription` on Android, `Accessible.name` in Qt, an accessibility label on iOS); decorative images are hidden (`null` description) (AND, QT, FLU). (M)
- Qt: `Accessible.role`, `Accessible.name` and `Accessible.focusable` on custom items; `name` is short, bound to the visible label and omits the control type; `announce()` for status (6.8+); `labelledBy` (6.10+) (QT). (M)
- Qt touch and mouse target sizes are chosen separately, since the scaling model does not distinguish them (QT); touch 48 px, 60–72 px with gloves (QTS §4). (M)
- Qt has no system reduced-motion switch, so the app exposes a setting (QTS §1.1). (M)
- Optional lint: `qt-qml-review` ids (PRF-1..6, IMG-1/3, LAY-1/2) are cited when that skill is installed, not restated here (QMR). (M)
- Headings are marked, so screen-reader users can jump between sections (AND). (M)
