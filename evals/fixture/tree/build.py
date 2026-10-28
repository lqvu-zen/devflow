import hashlib
import os
import zipfile

os.makedirs("dist", exist_ok=True)
with zipfile.ZipFile("dist/tally.zip", "w") as z:
    for name in ("tally/__init__.py", "tally/core.py", "tally/cli.py"):
        z.write(name)
digest = hashlib.sha256(open("dist/tally.zip", "rb").read()).hexdigest()
with open("dist/SHA256SUMS.txt", "w") as f:
    f.write(f"{digest}  tally.zip\n")
if os.path.exists("dist/release_check.passed"):
    os.remove("dist/release_check.passed")
print("BUILD OK")
