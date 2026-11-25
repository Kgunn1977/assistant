"""Run once in a clone: python githooks/install.py. Points this repo's git at the tracked githooks folder, so a commit or merge commit is refused while a message points at something missing."""
import os, subprocess
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
subprocess.run(["git", "-C", root, "config", "core.hooksPath", "githooks"], check=True)
print("hooks installed: pre-commit and pre-merge-commit now run tests/pointers_check.py")
