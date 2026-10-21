---
name: review-web-ui
description: One evidence-based UI/UX review of a web page or site. Measures the real page in headless Chrome (taste-skill's inspector: contrast, text sizes, overflow, side-scroll, covered/clipped text, headline lines, empty screens, type-size count), reads the screenshots at phone and desktop width, drives the interactive states, audits accessibility (WCAG 2.2 AA), checks consistency with the site's own design system, and returns one prioritized, located report (P0–P3, file:line, fix, effort). Merges design-critique (Nielsen, UX laws, Krug), accessibility-review/-audit, design-review (visual, motion), frontend-design and taste-skill (generated-look tells, juror score), with ui-ux-pro-max as an optional rule database, all ranked below the project's own rules. Use for "review the UI", "UX review", "is this page any good", "what looks off", "check it on mobile", "a11y audit", "contrast check", "does this look AI-generated", "what would make it look better", or before launching or sharing a page. Read-only: it reports, it does not fix. Not for code or security review of a diff, and not for building new UI.
---

# Review web UI/UX

One review instead of five generic skills that each know nothing about the site and some of which would tell you to delete its deliberate style. You collect evidence (measurements, screenshots, interactive states, the source line), judge it with one merged checklist, and hand back one report.

## Project layer

Before anything else, find what this project has already decided. In order:

1. A project skill that wraps this one (e.g. `.claude/skills/review-*-ui/SKILL.md`). If the user invoked one, it has already told you its rules file, paths, states and report language; follow it where it differs from this file.
2. The project's rules: `CLAUDE.md`, and any design/architecture rules doc it points to. Read them in full.
3. `.claude/ui-review.json`, the inspector config (see **Config**). Its `allow` map is the list of design decisions you must not re-raise.
4. The design tokens: `:root` custom properties, a Tailwind config, a theme file. Note the colour pairs and the type scale.

If none exist, say so in the report header and review against the checklist alone. Ask the user only for what you can't learn by looking (usually: who the main user is and their one or two key tasks, if the page doesn't make it obvious).

## Where the rules come from, and who wins

| Source | What it contributes | Where it lives |
|---|---|---|
| The project's rules | Audience, devices, brand, deliberate style choices, known contrast pairs | the project (see above) |
| taste-skill (Leonxlnx, MIT, commit `c924fad`) | The real-browser inspector, the 14 critique passes, the juror score, the dated tells registry | `vendor/taste-skill/` (inspector + `references/critique.md`, `tells.md` only) |
| ui-ux-pro-max (optional) | ~119 UX rules searchable by outcome; pre-delivery checklist | a `ui-ux-pro-max` skill in the project or `~/.claude/skills/`, if installed |
| design-critique | First-impression scan, Nielsen H1–H10, UX laws, Krug's checks, feedback formula | distilled into `references/checklist.md` |
| accessibility-review / -audit | WCAG 2.2 AA, layered audit, severity triage | distilled into `references/checklist.md` |
| design-review | Visual and motion passes, P0–P3 with effort, "what's working" first, systemic roll-up | distilled into the report format below |
| frontend-design | Generated-look traits, "spend boldness in one place", copy rules | distilled into `references/checklist.md` |

**Precedence when they disagree:** the user's words → the project's rules (and its wrapper skill) → `references/checklist.md` → a ui-ux-pro-max result → taste-skill's house rules. A finding that only a lower source supports and a higher one contradicts is not a finding; don't report it.

### taste-skill's house rules are opinions, not standards

taste-skill was written to steer generated landing pages away from a stock look. Several of its inspector rules flag things that are legitimate style choices: `mono`, `gradient`, `shadow`, `button-fx`, `text-shadow`, `palette-cream`, `all-centred`, `few-pictures`, `no-real-pictures`, `no-footage`, `still-page`, `eyebrow`. When the project's style uses one on purpose (a pixel or terminal theme in monospace, a skeuomorphic UI with shadows, a centred invitation, a page with no photos yet), add the rule id to `allow` in `.claude/ui-review.json` with a one-line reason, and don't raise it in prose either. Do this before the first run, from what you learned in **Project layer**; don't waive a rule just because it fails.

The measurement rules are never waived for taste: `contrast`, `small-text`, `body-size`, `overflow`, `side-scroll`, `broken-image`, `headline-lines`, `covered-text`, `clipped-text`, `emoji`, `size-count`, `empty-screens`, `measure`. A FAIL among those is either a finding or goes under "Considered, not fixing" with a one-sentence defence from the project's rules.

## Config

`inspect-site.mjs` reads `.claude/ui-review.json` from the current directory (override with `--config`). All keys are optional:

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

Defaults: base `http://localhost:3000`, paths `["/"]`, widths `375,1440`, out `<os tmp>/review-web-ui/<project folder>/`. If you set `out` inside the repo, make sure it is gitignored. CLI flags override the file: `--base`, `--widths`, `--out`, `--allow` (added to the file's list), `--json`. A target can be a path on `base`, a full URL, or a local `.html` file (served from a throwaway local server).

## The run

### 0. Scope

Default is the whole page or site as its main user sees it, phone first unless the project says otherwise. If the user names a section, state or device, review that and say what you left out. Don't ask questions you can answer by looking.

### 1. Measure

Start or reuse the dev server (use the project's run skill or its `dev` script, in the background). Then:

```bash
node "${CLAUDE_PLUGIN_ROOT}/skills/review-web-ui/inspect-site.mjs" "/" "/other-page"
```

Each target gets its own folder under `out` with `mobile-fold.jpg`, `mobile-page-NN.jpg`, `desktop-*.jpg` and `report.json`. Add `--widths 320,375,768,1440` when layout is in scope. Every remaining FAIL/WARN goes into the report unless you can defend it in one sentence from the project's rules; write that sentence under "Considered, not fixing". If `${CLAUDE_PLUGIN_ROOT}` is not set in your shell, use the directory this SKILL.md is in. The inspector needs Node 22+ and an installed Chrome/Edge/Chromium. If it can't run, say so and continue with browser screenshots.

### 2. Look

Open **every** screenshot the inspector listed with the Read tool, mobile first. Judge the pictures, not the code: you will read intentions into code. Run the visual passes in `references/checklist.md` §A on them.

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

### 4. Judge

Go through `references/checklist.md` §A–§H in order. When a finding needs backing or you're unsure of a threshold and ui-ux-pro-max is installed, run **one** focused search for that outcome and cite the rule id:

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
Ran: inspector (<targets>, <widths>, waived: <ids>), <states tried>, <what was skipped and why>
Score (taste-skill scale, only for comparing rounds): design _ · usability _ · originality _ · content _ → _._

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
- **Severity:** P0 blocks a key task (can't read key info, can't submit, keyboard trap, body text below 4.5:1, horizontal scroll at 375 px, broken on a target browser). P1 hurts it (target under 24 px per WCAG 2.5.8, or under 44 px if the project asks; inputs under 16 px on iOS; missing label or status announcement; layout breaking at 320 px or with long content). P2 is inconsistency (off-token colour, one-off component, too many type sizes). P3 is polish.
- **Effort** S/M/L. **One root cause, one row**: mark `[systemic]` and give the instance count instead of repeating it per section.
- **Placeholder content** (lorem, `[ … ]`, TODO copy) is known; report only how the layout copes with it, never "replace this text".
- Score honestly: if your first score is 9, score again as someone who didn't build it. Leave the score out if only one section was reviewed.

### 7. Hand off

Stop after the report; this skill never edits. Offer next steps through the project's own workflows if it has them (bug-fix vs feature skills), or offer to fix the top items directly. After fixes land, run the review again on the same targets and report **Improved / Regressed / Verdict** instead of a fresh table.

## Files

| File | Use |
|---|---|
| `references/checklist.md` | The merged passes §A–§H. Read it every run. |
| `inspect-site.mjs` | Wrapper: reads `.claude/ui-review.json`, checks the server, passes waivers, one output folder per target. |
| `vendor/taste-skill/references/critique.md` | Original 14 passes, juror rubric and caps. Read it when scoring. Caps tied to waived rules don't apply. |
| `vendor/taste-skill/references/tells.md` | Dated registry of generated-page tells; ignore rows for waived rules. |
| `vendor/taste-skill/scripts/` | Unmodified inspector (`inspect.mjs`, `lib/`). Update by re-copying from upstream and noting the commit above. |
