#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
ui_fixture web "web (px)" "index.html and style.css"
printf '.cta { transition: transform 900ms ease-in-out; }\n.cta:hover { transform: scale(1.12); }\n' >> style.css
git add style.css
git commit -q -m "Grow the Get Tally button on hover"
git push -q origin main
head_sha="$(git rev-parse HEAD)"
short="$(git rev-parse --short=7 HEAD)"
ci_state green
