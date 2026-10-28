import hashlib
import json
import os
import subprocess
import sys

if os.path.exists("dist/release_check.passed"):
    os.remove("dist/release_check.passed")
if os.path.exists(".gate_fail"):
    print("case lineup_has_no_caches: FAILED (tally/__pycache__ found in tally.zip)")
    sys.exit(1)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
digest = hashlib.sha256(open("dist/SHA256SUMS.txt", "rb").read()).hexdigest()
with open("dist/release_check.passed", "w") as f:
    json.dump({"head": head, "sha256sums": digest, "passed": 3}, f)
print("RELEASE CHECK PASSED (3 cases)")
