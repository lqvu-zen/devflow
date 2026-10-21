---
name: release
description: 'Cut a release the devflow way, through a release candidate: ask the maintainer for the version, commit it, build every artifact, pass the release gate, publish vX.Y.Z-rcN as a pre-release, have the tester agent and the maintainer test it, then promote the same commit to vX.Y.Z after a fresh release review. Reads the build, gate, publish and lineup details from the Release section of .claude/devflow.md. Use whenever the user wants to ship: "cut a release", "release v1.6.5", "make a release candidate", "cut an rc", "promote the rc", "publish a new version", "ship it", "tag a release". Do NOT use it to write features (add-feature), fix bugs (fix-bug), or for status (secretary).'
---

# Releasing

Every release goes out in two parts. **A. A release candidate**: the artifacts are built, pass the release gate, are published as a **pre-release** `vX.Y.Z-rcN`, are tested by the `devflow:tester` agent, and are used by the maintainer on real work until they have ticked their checklist. **B. Promotion**: the same commit, with only the version changed, is rebuilt, checked again, release-reviewed and published as `vX.Y.Z`. Bugs that a build-and-ship-in-an-hour release lets through tend to surface in the candidate phase.

Releasing is **not a design problem**. It's a deterministic runbook, so there is no design subagent here, and you run the steps inline. The safety comes from **hard gates**: CI green on the commit you build, the build succeeding, the release gate passing, the tester reporting `TESTER: PASS`, every box of the maintainer's checklist ticked, and the release review printing `READY TO PUBLISH`. Stop and report at any gate that fails rather than publishing. (Drafting release notes from the commit log is the one step you may hand to a cheap Haiku or Sonnet subagent.)

## The project profile

Read **`.claude/devflow.md`** first, above all its **Release** and **Try it** sections. **Release** gives:

- **Repo**: `owner/name` for `gh`, and the main branch.
- **Version files**: each file that holds the version, the line to change, and whether it takes the `-rcN` suffix or numbers only.
- **Build**: the command that builds every artifact from clean, and how it says it succeeded.
- **Gate**: the command that checks the built artifacts on throwaway data, and the line it ends with on success.
- **Stamp**: the pass stamp **Gate** writes, if the project has one (the guard reads it from `guard.release_stamp` in `.claude/devflow.json`).
- **Sign**: whether the maintainer signs anything, and the command **they** run. Claude never signs, never reads a key, never asks for a passphrase.
- **Artifacts**: the files to attach to the release.
- **Lineup**: each artifact, what it must contain and what it must not.
- **Notes**: sections every release's notes carry (which download to pick, how to check a download, how to update).
- **Checklist**: the maintainer's manual checks for every candidate.
- **After**: what to clean, archive or add after a release (build folders, fixtures for a new schema).

If `.claude/devflow.md` has no **Release** section, stop and ask the maintainer to fill it in (or run `/devflow:setup`); don't improvise a release.

If you're somewhere the artifacts can't be built or checked (the wrong OS, no display the build needs, no `gh` login), say so plainly and stop; do not fake a release.

## Version scheme

The version changes **only here**, never per feature or fix, and never with a `-dev` suffix.

- **Release candidate** `X.Y.Z-rcN`: the version files say `X.Y.Z-rcN`, except those **Release** marks numbers-only, which say `X.Y.Z`. Tag `vX.Y.Z-rcN`, published as a **pre-release**.
- **Final** `X.Y.Z`: the version files say `X.Y.Z`. Tag `vX.Y.Z`, published as the latest release.
- Tags carry the `v` prefix; the version files do not.
- N is one more than the highest number among the existing `vX.Y.Z-rc*` tags (`git tag -l "vX.Y.Z-rc*"`) and any `-rcN` already in the version files at HEAD; 1 when there is none. A failed candidate's number is never reused or re-tagged.
- The commit titles are exactly `Release candidate X.Y.Z-rcN` and `Release X.Y.Z`. The `devflow_checks.py version` CI check fails any other commit that changes a version file.

## A. Release candidate

**Claim your step before anything else**, when the release is a plan step: as in `add-feature` (this plugin's `skills/add-feature/SKILL.md`, "Before you start, and where you stop").

### A1. Check CI, then ask for the version and draft notes

```bash
git status --porcelain && gh run list -L 3 --json conclusion,status,headSha,displayTitle \
  --jq '.[] | "\(.status)\t\(.conclusion // "-")\t\(.headSha[0:7])\t\(.displayTitle)"'
```

The tree must be clean and HEAD must have a **successful** run. Wait for a run still in progress (`gh run watch <id> --exit-status`). Triage a red run as in `fix-bug` ("When the bug is a red CI run") before treating it as a blocker; a flaky run is rerun once with `gh run rerun <id> --failed`, and if it goes green you carry on with your task and tell the maintainer that the flaky test's fix is the next step; the secretary adds it first in Order. If the candidate commit's CI went green only on a rerun, the release report says so. Any other failure is a stop.

Then check the latest published tags (`gh release list -R <repo> -L 5`) and **ask the maintainer for the version number X.Y.Z, and wait for the answer** before changing anything. You may suggest one (patch for fixes, minor for notable features), but the maintainer names it. A bare "release" or "go ahead" is not approval of a version suggested earlier in the conversation. Work out N. Gather release notes; if the maintainer didn't give any, draft them from `git log <last final tag>..HEAD --oneline` and show them for approval. Notes are for users, not a changelog: say what changed for someone using the product, and flag anything that will behave differently.

### A2. Set the versions, commit and push, before building

Set every version file as the scheme says. Commit **before** building, so each build records the commit it was built from:

```bash
git add <version files> && git commit -m "Release candidate X.Y.Z-rcN" && git push
```

Stage deliberately: only the version files. Wait for CI to go green on this commit (`gh run watch <id> --exit-status`); the build can run meanwhile, but nothing is published until it is green.

### A3. Build every artifact (hard gate)

Run **Build**. If it fails, stop and report. Don't package anything by hand.

### A3b. The maintainer signs (hard gate, only if **Sign** says so)

Stop and ask the maintainer to run **Sign** themselves. The key and its passphrase stay with them; never ask for either, never look for the key file, never sign for them. Wait for them to say it is done, and check the signature file exists. Every rebuild changes what is signed, so it is signed again; a signature left over from an earlier build is deleted first.

### A4. Release gate (hard gate)

Run **Gate**, with nothing else running that touches the data it checks. It must end with the success line **Gate** names. **Any failure is a stop**: fix it with `fix-bug`, and start again from A2 with N+1.

If **Stamp** is set, a passing run leaves the stamp: HEAD, the hash of the bound artifact file and the case count. Never write, edit or copy the stamp yourself; only **Gate** makes it. A rebuild or a new commit makes it stale, so build, sign if needed, and run **Gate** last, on the commit you publish.

### A5. Publish the pre-release

Only once CI is green on the candidate commit. Write the notes to a file in your scratchpad (backticks and `$` get mangled on the command line), with the sections **Notes** lists, and a first line saying this is a release candidate for testing:

```bash
gh release create vX.Y.Z-rcN <artifacts> -R <repo> --prerelease --latest=false \
  --target <full sha of HEAD> --title "vX.Y.Z-rcN" --notes-file <notes.md>
```

The guard hook asks the maintainer before any `gh release` write; that is expected. If **Stamp** is set, it first refuses to publish (`gh release create`, `upload`, a publishing `edit`, `gh api` writes) unless the stamp names the current HEAD and the current hash of the bound file; if it refuses, run A4 again, don't work around it. Record the time it was published.

### A6. Test the candidate (hard gate)

Spawn the tester, which hasn't seen this session:

```
Agent({ description: "Test vX.Y.Z-rcN", subagent_type: "devflow:tester", prompt: <brief> })
```

The brief gives: the candidate version and tag; `git log <last final tag>..HEAD --oneline`; the paths of the built artifacts; and the whole release-gate output from A4. It reads `docs/BEHAVIOUR.md` and **Try it** itself. Its last line is `TESTER: PASS` or `TESTER: FAIL (n)`. **Any FAIL blocks promotion**: fix it, and start again from A2 with N+1.

### A7. The maintainer's manual checklist

Write the checklist into the release plan's Status table (or the release's plan): every item of **Checklist**, plus the tester's "not testable by an agent" items, and the publish time from A5.

### A8. The maintainer uses the candidate

The maintainer uses it on real work and ticks the checklist, for as long as the **Standing rules** say (no minimum unless they name one). Any bug found is fixed through `fix-bug`, and a new candidate starts from A2 with N+1. Between a candidate's tag and its promotion, **only `docs/`-only commits may land on the main branch**; any other change means a new candidate.

## B. Promote

Only when the maintainer says so, with the gate passed, the tester's PASS in hand and every checklist box ticked.

### B1. The candidate is what ships (hard gate)

```bash
git diff --stat vX.Y.Z-rcN..HEAD -- . ':(exclude)docs'
```

Before the version commit (B2) this must print nothing; after it, only the version files, with only `-rcN` dropped. Anything else is a stop: it is a new candidate, not a promotion.

### B2. Set the final version, commit and push

Set the version files to `X.Y.Z`. Run B1 again, then:

```bash
git add <version files> && git commit -m "Release X.Y.Z" && git push
```

Wait for CI to go green on it.

### B3. Rebuild and check again (hard gate)

A3, A3b and A4 again, on this commit; **Gate** makes a fresh **Stamp**, and B5 needs it.

### B4. Release review (hard gate)

Spawn a fresh reviewer:

```
Agent({ description: "Release review vX.Y.Z", subagent_type: "devflow:reviewer", prompt: <brief> })
```

(If `devflow:reviewer` isn't listed, use `subagent_type: "general-purpose"`, `model: "opus"`, `effort: "high"`, and paste the plugin's `agents/reviewer.md` at the top of the brief.)

The brief starts with **"Release mode."** and includes, verbatim: the version, the candidate tag it promotes, and the last released tag; the approved release notes; the **Lineup**; the build output and the whole gate output from B3; the tester's last report and the state of the checklist; the B1 diff; and the release plan's final step with its "Done when" items, if there is one.

If the reviewer reports BLOCKERS, fix them (a fix to anything outside `docs/` is a new candidate, from A2) and review again. Go on only on `READY TO PUBLISH`. Show the maintainer every **needs a human** item it listed that the checklist does not already cover, and **wait for them to confirm each one** before publishing.

### B5. Create the release

```bash
gh release create vX.Y.Z <artifacts> -R <repo> --latest --target <full sha of HEAD> \
  --title "vX.Y.Z" --notes-file <notes.md>
```

with the approved notes and every section **Notes** lists.

### B6. After the release

Do everything **After** lists (clear build folders, so a stale build is never checked or attached next time; add a fixture for a new schema; and so on).

### B7. Archive the plan, only if it is complete

Set the plan's own release row to `done, vX.Y.Z published <date>` (a `docs/`-only edit), then check the plan is complete; this prints nothing when it is:

```bash
plan=<plans folder>/release-X.Y.Z.md
awk -F'|' '/^## Status/{t=1} t && /^\| [0-9]+ /{s=tolower($3); sub(/^ +/,"",s); if (s !~ /^(done|not needed)/) print "OPEN: " $2}' $plan
grep -n -i '\[ \]\|needs a human' $plan
```

Any output means the plan is **not** complete: leave it where it is and list the open rows in the report. When it prints nothing, `git mv` the plan (and its brief, if any) into `docs/archive/`, point every reference at the archived path, commit only those paths as `docs: archive release-X.Y.Z plan`, and push. The status file is left to the secretary.

### B8. Report

Give the maintainer the release URL, the version shipped, the candidate it promotes, the artifacts attached, and a one-line confirmation that the gate passed, the tester reported `TESTER: PASS`, the checklist is ticked and the release review printed `READY TO PUBLISH`. Say whether the plan was archived, or which rows kept it open. Note anything you skipped or that needs follow-up.
