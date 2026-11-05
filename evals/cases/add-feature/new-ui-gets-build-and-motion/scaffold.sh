#!/usr/bin/env bash
. "$(dirname "$0")/../../../fixture/build.sh"
ui_fixture web "web (px)" "index.html and style.css"
head_sha="$(git rev-parse HEAD)"
short="$(git rev-parse --short=7 HEAD)"
ci_state green
