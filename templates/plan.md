# <Project> vX.Y.Z: <one-line theme>

_Created <YYYY-MM-DD> by the secretary from <the brief / the maintainer's decisions>. Replaces <nothing / the earlier plan>. Each code step goes through the devflow agent team via its skill._

## Goals

1. <Goal, in the user's terms.>
2. Ship **X.Y.Z** through the release-candidate phase.

## Decisions

| # | Question | Default | Why | Confirm? |
|---|---|---|---|---|
| D1 | <open question> | <the default the team uses> | <reason> | <maintainer must confirm / no> |

## Who does what

| Step | Who | How |
|---|---|---|
| 1 <title> | coding session | `/devflow:fix-bug` |
| 2 <title> | coding session | `/devflow:add-feature` |
| 3 Release X.Y.Z | coding session + maintainer | `/devflow:release`; the maintainer names the version |

## Steps

### 1 — <Fix #NN: short title>

<What and why. Facts for the team: files, modules, existing helpers, related commits. Not a diagnosis.>

Behaviour map: <IDs and their surfaces>.

**Needs** nothing.
**Done when** a regression test reproduces the bug on the old code and passes on the fix; <every surface>; the map entry <ID> names the test.

### 2 — <Feature: short title>

<What and why.>

Behaviour map: <IDs to add or update, and their surfaces>.

**Needs** <step numbers>.
**Escalate:** <only for an area Escalate names>.
**Gate:** <only when the maintainer must do or decide something first>.
**Done when** <what a test proves>; <every surface>; the new map entries with their tests.
**Tried:** <optional; written by a coding session that stopped. One clause per approach: what it was and why it failed (output: <path>); a later stop adds to the end>.

### 3 — Release X.Y.Z

**Needs** every step above, plus green CI.
Run `/devflow:release`. The maintainer names the version. The release gate passes; `vX.Y.Z-rc1` is published as a pre-release; the tester reports no FAIL; the maintainer ticks the checklist; the same commit is promoted after the release review prints `READY TO PUBLISH`.
**Done when** vX.Y.Z is published with every artifact in the lineup, and the issues it fixes are closed with a link to the release.

## Order

Bug fixes first: 1. Then 2. Then 3, the release, through the candidate phase.

## Status

| Step | State |
| --- | --- |
| 1 <title> | — |
| 2 <title> | — |
| 3 Release X.Y.Z | — |
