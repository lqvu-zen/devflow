---
version: alpha
name: tally-web-mono
description: A product page with a mono label voice.
colors:
  primary: "#1b5fd1"
  text: "#1f1f1f"
  background: "#ffffff"
typography:
  body:
    fontFamily: system-ui
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.6
rounded:
  md: 6px
spacing:
  md: 16px
---

# Design system: tally-web

## Overview

A small product page for a command-line tool. Dark text on a white page, one blue accent.

## Colors

`text` is the body colour. `primary` is for links and the call to action.

## Typography

System sans-serif at 18px. Headings are heavier, never clipped.

## Layout

One column, 24px side padding, readable from 375px up.

## Components

Links, a button, one text field. Each has default, hover, focus, active and disabled states. Focus is a visible 2px ring in `primary`.

## Typography notes

Eyebrow labels above headings are deliberate: uppercase ui-monospace at 12px with wide tracking, naming the kind of page. They are part of the voice and stay.

## Do's and Don'ts

- Do keep body text at 4.5:1 contrast or better.
- Do show a visible focus ring on every interactive element.
- Don't clip or truncate headings.
- Do keep the mono eyebrow label above the hero heading.

## Platforms

- web: px

## States

default, hover, focus, active, disabled, error

## Inputs

mouse, keyboard, touch

## Motion

feedback 100-150 ms, nothing decorative
