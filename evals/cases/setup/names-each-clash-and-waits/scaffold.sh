#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
git rm -q .claude/devflow.md .claude/devflow.json
printf '\n## Working habits\n\n- Commit straight to `main`; we don'\''t use feature branches.\n- Bump the version in every PR.\n' >> CLAUDE.md
git add CLAUDE.md
git commit -q -m "Our own working habits, before devflow"
git push -q origin main
head_sha="$(git rev-parse HEAD)"
short="$(git rev-parse --short=7 HEAD)"
ci_state green
