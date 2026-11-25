# Building new UI (what the designer follows)

For a change that adds UI rather than editing existing UI. It is the build side of `tells.md`: that file says what reads as generated, this one says what to do instead. It holds for every platform. `motion.md` covers anything that moves. Where a rule here conflicts with the project's design system, the design system wins (SKILL.md precedence), and a rule here never overrides `core.md`.

Source keys: FD frontend-design skill, current text; IMP Impeccable `5e745ac` (Apache-2.0), `craft-floor.md`; HM Hallmark `8f6969f` (MIT); DD Dimensional Drawing `5c45743` (MIT). Rules are restated in devflow's words (D1). **(M)** measurable, **(T)** taste.

## 1. Take the direction from the design system

- Read the design-system file the profile's **Design system** names (`docs/DESIGN.md` by default) first: Overview, tokens, Platforms, States, Inputs, Motion, Do's and Don'ts. The direction of the new UI is the one it states. (T)
- Never invent a palette, typeface, radius or spacing step the design system does not name. A value it lacks is an open question for the maintainer, not a choice for the designer. (FD, IMP) (M)
- Without a design system, say so in the plan and ask before inventing one; the plan names the direction in one sentence and the reason for it. (T)
- Reuse the project's existing components. New UI that restyles what already exists is a finding. (T)

## 2. Spend boldness in one place

- Pick the one thing the screen is remembered for (a layout, a type moment, a motion) and keep everything around it quiet. Several loud devices cancel each other. (FD) (T)
- The idea reaches the whole flow: forms, empty states, error states and the footer carry the same direction as the first screen. (T)
- Removing the tells in `tells.md` is not a direction. A screen with nothing in place of them is the empty version of the same tell. (T)

## 3. Avoid the tells

- Run the plan against `tells.md` before building and again before reporting. A row of any tier is waived when the design system names the thing (`tells.md`, Waiver). A reflex row is also waived by a reason stated in the plan; a floor row is not waived by the plan's reason alone. (T)
- Skip rows flagged marketing when the screen is an app or game screen.
- Placeholder content is fine while building; it is replaced or labelled before the work is reported done. (T)

## 4. Two passes: plan, then build

1. **Compact plan**, before any code: the named colours (as tokens), the type roles, and the layout concept in a few lines, plus the one place boldness is spent. (FD) (T)
2. **Review the plan** against the design system and against what any similar screen would default to. Revise every choice that is the default for its kind of page and has no reason behind it. Use Hallmark's six-axis pre-emit critique as the checklist (HM; the axis names are not verified here, so read them from Hallmark `8f6969f` rather than from this file). The design system's own words always win over the critique. (T)
3. **Build** from the revised plan. The implementer follows the plan, not a fresh idea.

## 5. The floor, before reporting done

Check each on the finished UI (IMP `craft-floor.md`, restated):

- Contrast meets `core.md` §4 for every text and control pair, in every theme the design system names. (M)
- Running text stays within the measure `core.md` §1 gives, and tracking on small text is not wider than the tells registry allows. (M)
- Every interactive element has the states the design system's States section lists: hover where hover exists, focus, active, disabled, and loading, error and empty where the component can be in them. (M)
- Targets meet the platform's size from the design system. (M)
- Every colour, size, spacing, radius and duration comes from a token; a literal where a token exists is a finding. (M)
- The worst-case data from the plan's UI section has been tried: a 200-character title, zero items, a missing image, translated text 30 to 40% longer. (M)
- Nothing that moves breaks the rules in `motion.md`. (M)

## 6. Spec table for a new component

For each new component the plan includes a table the implementer builds from (DD, restated).

| Part | Padding | Gap | Radius | Notes |
|---|---|---|---|---|
| <name of part> | <code> | <code> | <code> | <state, size or input it applies to> |

- Each **code** names a token in the design-system file (for example `spacing.md`, `rounded.sm`). The table never holds the value; the tokens do, so changing a token changes the component.
- A derived value is a formula over codes, for example `icon box = spacing.lg + spacing.sm`, never a hand-computed number.
- A value the plan does not know is written `[TBD]` and listed as an open question. A `[TBD]` is never replaced by a guess. (M)
- Rows cover every state and size the UI section lists, or say which share a row.
