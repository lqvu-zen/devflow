---
version: alpha
name: <Project>
description: <one line: what the product looks and feels like>
colors:
  primary: "<#RRGGBB>"
  secondary: "<#RRGGBB>"
  surface: "<#RRGGBB>"
  on-surface: "<#RRGGBB>"
  error: "<#RRGGBB>"
typography:
  body:
    fontFamily: <family>
    fontSize: <16px>
    fontWeight: 400
    lineHeight: <1.5>
  heading:
    fontFamily: <family>
    fontSize: <24px>
    fontWeight: 600
    lineHeight: <1.25>
rounded:
  sm: <4px>
  md: <8px>
spacing:
  sm: <8px>
  md: <16px>
  lg: <24px>
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm}"
  button-primary-hover:
    backgroundColor: "{colors.secondary}"
  button-primary-disabled:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
omitted:
  - section: <a section left out, e.g. Elevation & Depth>
    reason: <why this product has none>
---

# Design system: <Project>

Format: Google's DESIGN.md (`google-labs-code/design.md`, spec `alpha`). The front matter holds the tokens; the sections say how to use them. Unknown headings are kept, so the four devflow sections at the end are part of the file. Where the project has the Node tooling, `npx @google/design.md lint docs/DESIGN.md` checks the file.

Token tiers: reference tokens hold raw values (`#1A73E8`); semantic tokens say what a value is for (`primary`, `error`); component tokens bind semantic tokens to a part (`button-primary`). Components reference semantic tokens, never raw values.

## Overview

<The personality in a few sentences: who it is for, the tone, the one thing the design spends its boldness on. Example: "A calm, dense tool for people who use it all day. Quiet neutrals; the accent appears only on the primary action.">

## Colors

<Each colour token and its role. Example: "`primary` marks the one main action per screen. `error` is for failures and is never the only signal: pair it with text or an icon.">

## Typography

<The type roles and when each is used. Example: "Two roles: `heading` for screen and section titles, `body` for everything else.">

## Layout

<The grid, the spacing scale, the breakpoints or window classes, the content width. Example: "An 8 px base. Content at most 720 px wide; below 600 px the sidebar becomes a drawer.">

## Elevation & Depth

<How layers are shown: shadows, borders, blur, or none. Say which, and when.>

## Shapes

<The corner radii and where each applies. Example: "`md` on buttons and inputs, `sm` on chips.">

## Components

<One short paragraph per component the project has, naming its tokens and its states. Example: "Primary button: `button-primary`; hover and disabled have their own entries above.">

## Do's and Don'ts

The list the reviewer checks a UI change against.

- Do <a rule the design follows, e.g. use `primary` once per screen>.
- Don't <a rule it breaks never, e.g. put text on a photo without a scrim>.

## Platforms

The platforms the project ships to, each with the unit it uses.

| Platform | Ships | Unit | Notes |
|---|---|---|---|
| web | <yes / no> | px, rem | <breakpoints, browsers> |
| desktop | <yes / no> | px or pt | <OS, DPI scaling, window sizes> |
| mobile | <yes / no> | pt (iOS), dp (Android) | <devices, orientations, safe areas> |
| game | <yes / no> | px at a stated reference resolution, or physical mm | <engine, target displays, TV distance> |

## States

Every interactive component covers the states below, or says why one does not apply. Error is never collapsed into empty.

- default, hover, focus, active/pressed, disabled
- loading, empty, error, success
- selected, expanded, dragging
- forms: untouched, dirty, submitted-pending

<Add or remove states here for this product.>

## Inputs

<The inputs the product supports: mouse, keyboard, touch, controller. For each: the smallest target, how focus is shown, and what is not supported. Example: "Mouse and keyboard. Targets at least 24 px; focus is a 2 px ring in `primary`.">

## Motion

<What moves and why. Durations by purpose, for example: feedback 50-150 ms, small elements 100-150 ms, medium 200-300 ms, full screen 300-400 ms; more than 500 ms needs a stated reason. Say what happens under reduced motion.>
