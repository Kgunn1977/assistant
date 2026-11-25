r"""Acceptance: the dead-pointer check (tests/pointers_check.py) flags a message that points at something missing, passes
once it is removed, and raises no false alarm on the real code. Works on a scratch copy; nothing outside it changes.

    python tests\pointers_acceptance.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pointers_check as pc

results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


real = pc.scan()
# "in Settings, under Tools" is read as pointing into Tools
check("real code: nothing flagged", real, [])

tmp = tempfile.mkdtemp()
try:
    pc.SYS = os.path.join(tmp, "System")
    shutil.copytree(os.path.join(pc.PKG, "engine", "System", "live"), os.path.join(pc.SYS, "live"))
    os.makedirs(os.path.join(pc.SYS, "live_page"))
    shutil.copy(pc.PAGE, os.path.join(pc.SYS, "live_page", "page.html"))
    pc.PAGE, pc.LIVE = os.path.join(pc.SYS, "live_page", "page.html"), os.path.join(pc.SYS, "live")
    base = len(pc.scan())
    path = os.path.join(pc.LIVE, "texts.py")
    src = open(path, encoding="utf-8").read()
    open(path, "w", encoding="utf-8").write(src + '\nFAKE = "Open Widgets in Settings to turn it on."\n')
    planted = [b for b in pc.scan() if "Widgets" in b[2]]
    check("planted 'Open Widgets in Settings' is flagged with file and line", len(planted) == 1 and planted[0][0].endswith("texts.py") and planted[0][1] > 1, True)
    open(path, "w", encoding="utf-8").write(src)
    check("removed, back to the same result", len(pc.scan()), base)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

bad = [r for r in results if not r[1]]
for n, ok, got, want in results:
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"  got {got!r} want {want!r}"))
sys.exit(1 if bad else 0)
