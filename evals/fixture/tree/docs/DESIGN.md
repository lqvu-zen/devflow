---
version: alpha
name: tally
description: Plain, scriptable terminal output.
colors:
  primary: "#000000"
typography:
  body:
    fontFamily: monospace
    fontSize: 1ch
    fontWeight: 400
    lineHeight: 1
spacing:
  sm: 1ch
omitted:
  - section: Elevation & Depth
    reason: terminal output has no layers
  - section: Shapes
    reason: terminal output has no corners
---

# Design system: tally

## Overview

One line of plain text per run, safe to pipe. No colour codes, so the output reads the same in a terminal, a log and a script.

## Colors

`primary` is the terminal's own foreground. The program never sets a colour.

## Typography

The terminal's monospace font. One role.

## Layout

One line: `total=<number> average=<number>`, fields separated by one space.

## Elevation & Depth

Not applicable.

## Shapes

Not applicable.

## Components

The result line is the only component. It has no states beyond success and an error message on standard error.

## Do's and Don'ts

- Do keep the result on one line so it can be parsed.
- Don't add colour, progress bars or spinners.

## Platforms

| Platform | Ships | Unit | Notes |
|---|---|---|---|
| web | no | | |
| desktop | no | | |
| mobile | no | | |
| game | no | | |

## States

Success prints the result line. Failure prints one message to standard error and exits non-zero.

## Inputs

Keyboard only: numbers as command-line arguments.

## Motion

None.
