---
name: review-ui
description: One evidence-based UI/UX review of a web page, a desktop or mobile app screen, or game UI (HUD, menus, settings), in one report format. Web: measures the real page in headless Chrome (contrast, text sizes, overflow, clipped text, page frame; an app-screen mode for dashboards), reads phone and desktop screenshots, drives the states. Apps (Qt/QML, iOS, Android, Windows, macOS) and games (Unity or any engine): reads screenshots of each state at each size or resolution, and the UI source. Judges against the project's design system, a platform-free checklist plus a web, app or game layer, and the generated-look tells; returns one prioritized, located report (P0-P3, file:line, fix, effort). Use for "review the UI", "UX review", "is this page any good", "what looks off", "check the mobile screen", "review the HUD", "is this settings dialog any good", "a11y audit", "contrast check", "does this look AI-generated". Read-only: it reports, it does not fix. Not for building or changing UI, nor for code review of a diff.
---

# Review UI/UX

One review instead of five generic skills that each know nothing about the product and some of which would tell you to delete its deliberate style. There is one path per platform (web, app, game) and one report. You collect evidence (measurements or screenshots, interactive states, the source line), judge it with one merged checklist, and hand back one report.

## Project layer

Before anything else, find what this project has already decided. In order:

1. A project skill that wraps this one (e.g. `.claude/skills/review-*-ui/SKILL.md`). If the user invoked one, it has already told you its rules file, paths, states and report language; follow it where it differs from this file.
2. When `.claude/devflow.md` exists, read its **Design system** and **See it working** sections by those exact headings, then read the design-system file the first one names in full (tokens, Platforms, States, Inputs, Motion, Do's and Don'ts). Whatever the design system names is deliberate, and its tell is waived (`references/tells.md`, Waiver). Without a profile, work exactly as before.
3. The project's rules: `CLAUDE.md`, and any design/architecture rules doc it points to. Read them in full.
4. `.claude/ui-review.json`, the inspector config (see **Config**). On the web path read the whole file. On the app and game paths read only its `allow` map, as the list of deliberate choices you must not re-raise.
5. When there is no design-system file, the design tokens: `:root` custom properties, a Tailwind config, a theme file, a QML theme singleton, Android `themes.xml` and `colors.xml`, asset catalogs, Unity USS variables or a theme asset. Note the colour pairs and the type scale.

If none exist, say so in the report header and review against the checklist alone. Ask the user only for what you can't learn by looking (usually: who the main user is and their one or two key tasks, if the screen doesn't make it obvious).

## Platform

Pick the platform in this order: the user's words, then the Design system's **Platforms the project ships to**, then the project's files, then ask once.

| Platform | Path |
|---|---|
| web | web path (inspector) |
| desktop, mobile | app path (screenshots and source) |
| game | game path (screenshots and source) |

If the project ships to several platforms, take the platform of the target the user named, else ask. Web-rendered apps and browser games take the app or game layer with screenshots only, not the inspector.

When you infer it from files, say so in the report. A `package.json` or `.html`/`.css` files with a dev script mean web. `*.qml`, Qt in `CMakeLists.txt`, `*.xcodeproj` or `*.swift`, `AndroidManifest.xml` or `*.xaml` mean app. `ProjectSettings/ProjectVersion.txt`, `Assets/**/*.unity`, `*.uxml` or `*.uss`, `project.godot` or `*.uproject` mean game. The Ran line names the platform and where it came from.

## Where the rules come from, and who wins

| Source | What it contributes | Where it lives |
|---|---|---|
| The project's rules | Audience, devices, brand, deliberate style choices, known contrast pairs | the project (see above) |
| The project's design system | Tokens, platforms, states, inputs, motion, do's and don'ts | the file **Design system** names (see above) |
| taste-skill (Leonxlnx, MIT, commit `12af471`) | The real-browser inspector, the 14 critique passes, the juror score, the dated tells registry | `vendor/taste-skill/` (inspector + `references/critique.md`, `tells.md` only) |
| ui-ux-pro-max (optional) | ~119 UX rules searchable by outcome; pre-delivery checklist | a `ui-ux-pro-max` skill in the project's `.claude/skills/`, `~/.claude/skills/`, or installed by a plugin |
| qt-qml-review, qt-ui-design (optional) | Qt/QML review rules and UI design rules, for the app path | the same places, if installed |
| Unity UI skills `ui`, `ui-uitk`, `ui-ugui` (optional) | Unity UI Toolkit and uGUI rules, for the game path | the same places, if installed |
| design-critique | First-impression scan, Nielsen H1–H10, UX laws, Krug's checks, feedback formula | distilled into `references/core.md` |
| accessibility-review / -audit | WCAG 2.2 AA, layered audit, severity triage | distilled into `references/core.md` and the platform layers (`web.md`, `app.md`, `game.md`) |
| design-review | Visual and motion passes, P0–P3 with effort, "what's working" first, systemic roll-up | distilled into the report format below |
| frontend-design | Generated-look traits, "spend boldness in one place", copy rules | distilled into `references/core.md` and `references/tells.md` |

**Precedence when they disagree:** the user's words → the project's rules, its design system and its wrapper skill → `references/core.md` and the platform layer → an optional rule source (ui-ux-pro-max, qt-qml-review, qt-ui-design, the Unity UI skills) → taste-skill's house rules. Cite an optional source by its rule id or section; do not restate it. A finding that only a lower source supports and a higher one contradicts is not a finding; don't report it.

### taste-skill's house rules are opinions, not standards

taste-skill was written to steer generated landing pages away from a stock look. Several of its inspector rules flag things that are legitimate style choices: `mono`, `gradient`, `shadow`, `button-fx`, `text-shadow`, `palette-cream`, `all-centred`, `few-pictures`, `no-real-pictures`, `no-footage`, `still-page`, `eyebrow`, `off-centre`, `lopsided`, `empty-middle`, `hero-void`, `ragged-edges`, `name-only-title`, `small-title`, `one-sided-bleed`, `no-poster`. In app mode also `heavy-shadow`, `heavy-borders`, `radius-mix`, `icon-chips`, `icon-tiles`, `colour-sprawl`, `kpi-size`, `app-title-size`, `no-data-hue`. When the project's style uses one on purpose (a pixel or terminal theme in monospace, a skeuomorphic UI with shadows, a centred invitation, a page with no photos yet), add the rule id to `allow` in `.claude/ui-review.json` with a one-line reason, and don't raise it in prose either. Do this before the first run, from what you learned in **Project layer**; don't waive a rule just because it fails.

The measurement rules are never waived for taste: `contrast`, `small-text`, `body-size`, `overflow`, `side-scroll`, `broken-image`, `headline-lines`, `covered-text`, `clipped-text`, `emoji`, `size-count`, `empty-screens`, `measure`, `no-title`, `reduced-hidden`, `tiny-text`. A FAIL among those is either a finding or goes under "Considered, not fixing" with a one-sentence defence from the project's rules.

In `--app` mode the inspector skips `small-text`, `body-size`, `measure`, `size-count`, `side-scroll` and `empty-screens`, so check side-scroll at 375 and 320 px and the text sizes yourself in step 3. A `dev-server` warning goes in the Ran line, not as a finding, unless the review is the last check before shipping. If `.taste-skill/direction.json` exists, the inspector applies its allow list and kind; say so in the Ran line.

## Config

`inspect-site.mjs` reads `.claude/ui-review.json` from the current directory (override with `--config`). All keys are optional, and the file applies to the web path:

```json
{
  "base": "http://localhost:8788",
  "paths": ["/", "/pricing"],
  "widths": [375, 1440],
  "out": ".claude/ui-review-out",
  "allow": {
    "mono": "VT323 is the pixel heading face",
    "all-centred": "an invitation is centred by convention"
  }
}
```

Defaults: base `http://localhost:3000`, paths `["/"]`, widths `375,1440`, out `<os tmp>/review-ui/<project folder>/`. If you set `out` inside the repo, make sure it is gitignored. CLI flags override the file: `--base`, `--widths`, `--out`, `--allow` (added to the file's list), `--app`, `--json`. A target can be a path on `base`, a full URL, or a local `.html` file (served from a throwaway local server).

## The run

### 0. Scope

Default is the whole page, screen or site as its main user sees it, phone first on the web unless the project says otherwise. Fix the platform (see **Platform**) and state it. If the user names a section, state or device, review that and say what you left out. Don't ask questions you can answer by looking.

### Web path

### 1. Measure

Start or reuse the dev server (use the project's run skill or its `dev` script, in the background). Then:

```bash
node "${CLAUDE_PLUGIN_ROOT}/skills/review-ui/inspect-site.mjs" "/" "/other-page"
```

Each target gets its own folder under `out` with `mobile-fold.jpg`, `mobile-page-NN.jpg`, `desktop-*.jpg` and `report.json`; when two widths share a class the names carry the width. Add `--app` when the page is an app screen (dashboard, admin, settings, inbox), per the design system or the page itself. Add `--widths 320,375,768,1440` when layout is in scope. Every remaining FAIL/WARN goes into the report unless you can defend it in one sentence from the project's rules; write that sentence under "Considered, not fixing". If `${CLAUDE_PLUGIN_ROOT}` is not set in your shell, use the directory this SKILL.md is in. The inspector needs Node 22+ and an installed Chrome/Edge/Chromium. If it can't run, say so and continue with browser screenshots.

### 2. Look

Open **every** screenshot the inspector listed with the Read tool, mobile first. Judge the pictures, not the code: you will read intentions into code. Run the visual passes in `references/core.md` §1 on them.

### 3. Drive the states the inspector can't reach

With the browser tool you have (Claude in Chrome, the built-in browser, or Playwright), at phone width first. Derive the list from the page; typically:

- Every primary action end to end (sign up, submit, buy, RSVP…): empty submit (errors next to fields, announced), valid submit (success in an `aria-live` region), reload (state kept or deliberately reset).
- Every toggle, disclosure, menu, modal/lightbox: open, close, Esc, backdrop, focus returns.
- Content extremes: very long names and words, empty lists, one item, many items, max-length input, missing images.
- Any URL parameters or personalisation the page supports.
- Keyboard only: Tab order, visible focus, no traps.
- Reduced motion (emulate `prefers-reduced-motion`), landscape phone, 320 px, 200% zoom.
- Degraded: API down or opened as a file, slow network if it matters.
- Console: errors only; name any that are expected.

Screenshot each state you judge. Never trigger `alert`/`confirm`/`prompt` dialogs in an automated browser.

### App path

**A1. Screenshots.** Collect a screenshot of each state from the design system's States list that the screen has, at each size or scale its Platforms row names: window sizes, 100% and 200% scale (`QT_SCALE_FACTOR=2` for Qt), phone portrait and landscape, tablet, light and dark, and the inputs from Inputs. Take them only the way **See it working** says (throwaway data), or use the ones the user supplied. With neither, ask; never start the app on a guess. A state you could not reach goes under Needs a human.

**A2. Source.** Read the UI source (QML or `.ui`, SwiftUI or storyboards, Compose or XML layouts, XAML): accessible names, sizes, theme tokens against literals.

**A3. Look.** Open every screenshot and run the passes in `references/core.md` §1 on them.

### Game path

**G1. Screenshots.** Collect the HUD in play, menus, settings, pause, dialogs, subtitles on, colour-blind modes, controller focus on each focusable element, and the glyphs per input device, at each resolution the design system names, for TV and desk distance. Same rules as A1 for how they are taken.

**G2. Source.** Read UXML and USS, prefabs and scenes (reference resolution, safe-area root), the UI scripts, or another engine's equivalents.

**G3. Look.** Open every screenshot and run the passes in `references/core.md` §1 on them.

The app and game paths do not run the inspector.

### 4. Judge

Steps 4 to 7 apply to every path.

Go through `references/core.md` §1–§7 in order, then the platform layer (`references/web.md`, `references/app.md` or `references/game.md`), then `references/tells.md`. Skip waived rows; on the app and game paths, and in `--app` mode, also skip rows flagged marketing. When a finding needs backing or you're unsure of a threshold and an optional source (ui-ux-pro-max, qt-qml-review, qt-ui-design, a Unity UI skill) is installed, run at most **one** focused query to it and cite the rule id or section. For ui-ux-pro-max: run **one** focused search for that outcome and cite the rule id:

```bash
python <ui-ux-pro-max dir>/scripts/search.py "focus not obscured" --domain ux
```

Don't put names or other private data in queries.

### 5. Locate

For every finding, open the source and name the line that causes it (`src/styles.css:123`, a token, a component, a config key). A finding without a location is a guess: either find the line or mark it **needs a human** (e.g. only reproducible on a real device or inside an in-app browser).

### 6. Report

In chat, in the language the user or project uses. Save it to a file only if asked. Shape:

```
## UI/UX review — <scope>, <date>
Ran: web path (from <the user's words | Design system | project files>): inspector (<targets>, <widths>, mode page|app, waived: <ids>), <states tried>, <what was skipped and why>
Ran: <app|game> path (from <...>): screenshots (<states> x <sizes>, taken by <See it working | the user>), source read (<files>), <what was skipped and why>
Score (web path only; taste-skill scale, only for comparing rounds): design _ · usability _ · originality _ · content _ → _._

### Working well (at least 3, specific, so nobody "fixes" them)
- …

### P0 — Blocking: the main user can't do the main task, or a project rule is broken
| # | Area | Location (file:line) | Seen at | Problem → why it matters to the user | Fix | Effort |
### P1 — Major: hard to use or read, broken on phones
### P2 — Minor: inconsistency, polish
### P3 — Cosmetic, when there's time
(A level with no findings: write "None".)

### Considered, not fixing
- [rule-id] … — kept because …

### Needs a human
- …

### Do these three first
1. …
```

Rules for findings:

- **Formula:** what's wrong + which rule (project rule, WCAG criterion, Nielsen H#, UX law, inspector id, or ui-ux-pro-max rule id) + why it matters to the user + a concrete fix that keeps the site's style.
- **Specific:** "the caption is `--ink-soft` on `--mint`, 4.49:1" beats "contrast is weak". "Could be more polished" is not a finding.
- **Severity:** P0 blocks a key task (can't read key info, can't submit, keyboard trap, body text below 4.5:1, horizontal scroll at 375 px, broken on a target browser). P1 hurts it (target under the platform floor: web 24 px per WCAG 2.5.8, or 44 px if the project asks; the `app.md` and `game.md` numbers elsewhere; inputs under 16 px on iOS; missing label or status announcement; layout breaking at 320 px or with long content). P2 is inconsistency (off-token colour, one-off component, too many type sizes). P3 is polish.
- **Effort** S/M/L. **One root cause, one row**: mark `[systemic]` and give the instance count instead of repeating it per section.
- **Placeholder content** (lorem, `[ … ]`, TODO copy) is known; report only how the layout copes with it, never "replace this text".
- Score honestly: if your first score is 9, score again as someone who didn't build it. Leave the score out if only one section was reviewed.

### 7. Hand off

Stop after the report; this skill never edits. Offer next steps through the project's own workflows if it has them (bug-fix vs feature skills), or offer to fix the top items directly. After fixes land, run the review again on the same targets and report **Improved / Regressed / Verdict** instead of a fresh table.

## Files

| File | Use |
|---|---|
| `references/core.md` | The platform-free passes §1–§7. Read it every run. |
| `references/web.md` | WCAG 2.2 AA specifics, devices and browsers, motion mechanics, inspector rule ids. Read it for a web page. |
| `references/app.md` | Desktop and mobile app layer. Read for the app path. |
| `references/game.md` | Game layer. Read for the game path. |
| `references/tells.md` | The dated generated-look registry. Read it every run; skip rows for waived rules. |
| `inspect-site.mjs` | Wrapper: reads `.claude/ui-review.json`, checks the server, passes waivers, one output folder per target. |
| `vendor/taste-skill/references/critique.md` | Original 14 passes, juror rubric and caps. Read it when scoring. Caps tied to waived rules don't apply. |
| `vendor/taste-skill/references/tells.md` | Dated registry of generated-page tells; ignore rows for waived rules. |
| `vendor/taste-skill/scripts/` | Unmodified inspector (`inspect.mjs`, `lib/{cdp,probe,rules,inspection-files}.mjs`). Update by re-copying from upstream and noting the commit above. |
