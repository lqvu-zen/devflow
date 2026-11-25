# Motion (what moves, how long, and how it stops)

For a designer planning motion in new or changed UI, and for a reviewer checking it. It holds for every platform; the mechanics for CSS, QML and Unity are in section 4. `core.md` §6 gives the principles and `web.md` §4 the web mechanics; this file gives the numbers. It ranks with `core.md` in the SKILL.md precedence, below the platform layer. Where two numbers for the same thing differ, the platform layer's wins on its platform (`app.md` 80-150 ms for press feedback), then this file's band, then `core.md` §6's "about 100-200 ms", which is approximate. The design system's Motion section overrides every default here.

Source keys: EK Emil Kowalski skills `a81dbca` (MIT); GSAP GSAP skills `aed9cfd` (MIT); OD Open Design `5e9a5e6` (Apache-2.0); QTS Qt `qt-ui-design` 1.7.3; HM Hallmark `8f6969f` (MIT); W WCAG 2.2. Rules are restated in devflow's words (D1, D7). **(M)** measurable, **(T)** taste. Where a source gives no number, none is invented here.

## 1. What motion is for

- **Feedback**: the interface acknowledges an action. Always worth having. (T)
- **Orientation**: shows where something came from or went, so a change of place is not a jump. (T)
- **Focus**: draws the eye to the one thing that changed. (T)
- **Delight**: allowed once, in the one place boldness is spent (`build.md` §2). (T)
- Not for: anything a person triggers dozens of times a day, such as a command palette or a keyboard-opened menu, where the motion becomes a wait; decoration that competes with reading or with a form; filling a screen that has no idea (EK, OD). (T)
- At most one or two things move at once. (T)

## 2. Duration and easing (D7)

| What moves | Duration |
|---|---|
| Feedback to a press or toggle | 50-150 ms |
| Small element (tooltip, chip, switch) | 100-150 ms |
| Medium element (menu, dropdown, card) | 200-300 ms |
| Full screen or large panel | 300-400 ms |
| Anything over 500 ms | only with a reason stated in the plan |

- On mobile, 20 to 30% shorter than the same motion on desktop. (T)
- Entrances decelerate (ease-out). Exits may accelerate (ease-in). Bounce and overshoot on UI state are a tell (`tells.md`, Motion). (T)
- Durations come from the design system's Motion section; a literal duration where a token exists is a finding. (M)
- These bands are defaults. A number from a source that disagrees with them is cited in the plan, with the source, and the design system decides.

## 3. Reduced motion

- Under the system's reduced-motion setting, decorative motion is skipped or set to zero duration. Opacity fades may stay. (W 2.3.3, 2.2.2) (M)
- On web, JS-driven loops, scrub triggers and scroll-linked animation are killed or set to `duration: 0` (GSAP). (M)
- Qt has no system switch, so the app exposes a setting and every animation reads it (QTS). (M)
- Unity: the same, through a project setting the transitions read. Not verified against a platform switch. (T)
- Nothing flashes more than 3 times a second. (W 2.3.1) (M)
- The plan's Motion line says what happens under reduced motion for each thing that moves. A motion with no answer is an open question.

## 4. Mechanics by platform

- **CSS**: animate `transform` and `opacity`; layout properties (`width`, `height`, `top`, `left`, `margin`, `padding`) are barred; `filter`, `backdrop-filter` and `clip-path` are allowed but each use is called out as costly. List the properties in `transition`, never `all` (HM; `web.md` §4). A `prefers-reduced-motion` rule on every keyframe or transform transition. (M)
- **QML**: `Behavior` and `Animation` types on the properties that change; never animate `pixelSize`, which relays out text on every frame (QTS). Durations from the theme singleton. (M)
- **Unity UI Toolkit**: put the `transition` on the base class, not on `:hover`, so the way out animates as well as the way in. Durations from the theme style sheet variables. (`unity` UI skills, `game.md`) (M)
- **uGUI**: tween with the project's one tween utility; do not mix several. Not verified against the docs for a rule beyond that. (T)

## 5. For the reviewer

- Check each moving thing in the diff against section 2's bands and the design system's Motion section, and against section 3.
- Judge motion from the code and the plan; a screenshot shows one frame. Say so when a finding rests on a still. (T)
