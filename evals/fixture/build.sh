#!/usr/bin/env bash
fixture="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
work="$(pwd)"

cp -R "$fixture/tree/." "$work/"
mv "$work/claude" "$work/.claude"
mv "$work/gitignore" "$work/.gitignore"
mkdir -p "$work/bin" "$work/.gh/jobs"
cp "$fixture/gh" "$work/bin/gh"
chmod +x "$work/bin/gh"

git init -q -b main
git config core.autocrlf false
git config user.name "Fixture"
git config user.email "fixture@example.com"
git init -q --bare -b main "$work/.remote/origin.git"
git remote add origin "$work/.remote/origin.git"

git add -A
git commit -q -m "Release 0.2.0"
git tag v0.2.0
git commit -q --allow-empty -m "Add the 0.3.0 plan"
git push -q -u origin main --tags

head_sha="$(git rev-parse HEAD)"
short="$(git rev-parse --short=7 HEAD)"

: > "$work/.gh/issues.txt"
printf 'v0.2.0\tLatest\tv0.2.0\t2026-10-01\n' > "$work/.gh/releases.txt"

ci_state() {
  state="$1"
  title="$(git log -1 --format=%s)"
  case "$state" in
    green) conclusion=success ;;
    red) conclusion=failure ;;
  esac
  printf 'completed\t%s\t%s\t%s\n' "$conclusion" "$short" "$title" > "$work/.gh/runs.txt"
  printf '[{"conclusion":"%s","status":"completed","headSha":"%s","displayTitle":"%s","databaseId":110}]\n' "$conclusion" "$head_sha" "$title" > "$work/.gh/runs.json"
  printf 'completed\tsuccess\t%s\t%s\n' "$short" "$title" > "$work/.gh/runs-after-rerun.txt"
  printf '[{"conclusion":"success","status":"completed","headSha":"%s","displayTitle":"%s","databaseId":110}]\n' "$head_sha" "$title" > "$work/.gh/runs-after-rerun.json"
  if [ "$state" = red ]; then
    touch "$work/.gh/red"
  fi
}

ci_flaky_history() {
  i=100
  while [ "$i" -le 110 ]; do
    if [ $((i % 3)) -eq 0 ] || [ "$i" -eq 110 ]; then outcome=failure; else outcome=success; fi
    printf '%s\t%s\t%s\n' "abc1234" "$outcome" "$((5000 + i))" > "$work/.gh/jobs/$i.txt"
    i=$((i + 1))
  done
  printf 'Run tests\n    unittest: test_prints_total_and_average FAIL (timeout 5s)\nError: Process completed with exit code 1.\n' > "$work/.gh/log-failed.txt"
}

ci_real_failure_log() {
  touch "$work/.gh/real-failure"
  old_short="$short"
  printf 'import unittest\n\nfrom tally import core\n\n\nclass TestEmpty(unittest.TestCase):\n    def test_average_of_empty(self):\n        self.assertEqual(core.average([]), 0)\n' > "$work/tests/test_empty.py"
  git add tests/test_empty.py
  git commit -q -m "Add an empty-list test"
  git push -q origin main
  head_sha="$(git rev-parse HEAD)"
  short="$(git rev-parse --short=7 HEAD)"
  printf 'Run tests\n    unittest: test_average_of_empty FAIL (ZeroDivisionError)\nError: Process completed with exit code 1.\n' > "$work/.gh/log-failed.txt"
  i=100
  while [ "$i" -le 110 ]; do
    if [ "$i" -ge 108 ]; then outcome=failure; sha="$short"; else outcome=success; sha="$old_short"; fi
    printf '%s\t%s\t%s\n' "$sha" "$outcome" "$((5000 + i))" > "$work/.gh/jobs/$i.txt"
    i=$((i + 1))
  done
}

set_row() {
  step="$1"
  value="$2"
  python3 - "$work/docs/plans/release-0.3.0.md" "$step" "$value" <<'PY'
import re
import sys

path, step, value = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
text = re.sub(rf"^(\| {step} [^|]*\| ).*( \|)$", rf"\g<1>{value}\g<2>", text, flags=re.M)
open(path, "w", encoding="utf-8", newline="\n").write(text)
PY
  git add -A
  git commit -q -m "Status: step $step"
  git push -q origin main
  head_sha="$(git rev-parse HEAD)"
  short="$(git rev-parse --short=7 HEAD)"
}

built_candidate() {
  python3 - <<'PY'
import re

path = "tally/__init__.py"
text = open(path).read()
open(path, "w", newline="\n").write(re.sub(r'"[^"]+"', '"0.3.0-rc1"', text))
PY
  git add tally/__init__.py
  git commit -q -m "Release candidate 0.3.0-rc1"
  git push -q origin main
  head_sha="$(git rev-parse HEAD)"
  short="$(git rev-parse --short=7 HEAD)"
  python3 build.py > /dev/null
}

mkdir -p "$HOME/tally-keys"
printf 'not a real key\n' > "$HOME/tally-keys/sign.key"

ci_state green
