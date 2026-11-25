r"""Acceptance: the change list's sorting (update-sort) and the update's own plan (assistant.py update-plan) judge an
owner's change the same way, from one judgment (setup_update.judge). On a scratch copy laid down from this plugin, with
an owner change that fits beside the update in one file and clashes with it in another: both name only the clashing
file, with its reason; the update keeps both changes in the file that fits. Nothing outside the scratch folder changes.

    python tests\update_agree_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
FITS, CLASH = "System/live/dates.py", "System/live/filters.py"
results = []

SORT = r'''
import json, os, sys, tempfile
sys.path.insert(0, sys.argv[1])
import setup_changes as sc, setup_update as su
root = sys.argv[2]
book = sc.Book(root, os.path.join(root, "Live"))
got = su.sort(book, os.path.join(root, "Shipped"), sys.argv[3], tempfile.mkdtemp())
print(json.dumps([{f["file"]: [f["kind"], f["why"]] for f in c["files"]} for c in got]))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def _swap(path, n, text):
    with open(path, encoding="utf-8", newline="") as f:
        lines = f.read().split("\n")
    lines[n] = text
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))


def main():
    tmp = tempfile.mkdtemp(prefix="agree-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    spec = importlib.util.spec_from_file_location("assistant_copy_agree", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    a = os.path.join(data, "scripts", "assistant.py")
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, a, "lay-down", "--port", "47903", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        # the update brings changes the copy does not have yet: the shipped base is made older at two places
        _swap(os.path.join(root, "Shipped", *FITS.split("/")), 2, "# an older line the update replaces")
        _swap(os.path.join(root, "Shipped", *CLASH.split("/")), 2, "# an older line the update replaces")
        sj = os.path.join(root, "Shipped", "shipped.json")
        d = json.load(open(sj, encoding="utf-8"))
        d["version"] = "0.0.9"
        json.dump(d, open(sj, "w", encoding="utf-8"))
        for rel in (FITS, CLASH):     # the copy as shipped then: the older line too
            _swap(os.path.join(root, *rel.split("/")), 2, "# an older line the update replaces")
        # the owner's change: far from that line in one file, on the same line in the other
        with open(os.path.join(root, *FITS.split("/")), "a", encoding="utf-8", newline="") as f:     # a line of its own, far from it
            f.write("# the owner's own line" + chr(10))
        _swap(os.path.join(root, *CLASH.split("/")), 2, "# the owner's own line on the same place")
        os.makedirs(os.path.join(root, "Live", "changes"), exist_ok=True)
        json.dump({"id": "ch-0001", "asked": "a", "agreed": "b", "part": "general", "paths": [FITS, CLASH], "state": "done"},
                  open(os.path.join(root, "Live", "changes", "ch-0001.json"), "w", encoding="utf-8"))
        plan = json.loads(subprocess.run([sys.executable, a, "update-plan", "--root", root], capture_output=True, text=True).stdout or "{}")
        check("update-plan: only the clashing file needs a choice", plan.get("conflict"), [CLASH])
        check("update-plan: the file that fits is kept beside the update", plan.get("fits"), [FITS])
        check("update-plan: the clash says why", "same lines" in (plan.get("why") or {}).get(CLASH, ""), True)
        r = subprocess.run([sys.executable, "-c", SORT, os.path.join(data, "engine", "System", "live", "setup"), root,
                            os.path.join(data, "engine")], capture_output=True, text=True)
        got = (json.loads(r.stdout or "[]") or [{}])[0]
        check("update-sort: the same judgment of both files", {k: v[0] for k, v in got.items()},
              {FITS: "needs adjusting", CLASH: "clashes"})
        check("both give the same reason for the clash", got.get(CLASH, [None, None])[1], (plan.get("why") or {}).get(CLASH))
        r = subprocess.run([sys.executable, a, "update-apply", "--root", root], capture_output=True, text=True)
        check("update-apply without a choice: refused, naming the clash and its reason",
              (r.returncode, CLASH in r.stdout and "same lines" in r.stdout, FITS in r.stdout), (1, True, False))
        ch = os.path.join(tmp, "choices.json")
        json.dump({CLASH: "mine"}, open(ch, "w"))
        r = subprocess.run([sys.executable, a, "update-apply", "--root", root, "--choices", ch], capture_output=True, text=True)
        check("update-apply with the one choice goes through", r.returncode, 0)
        text = open(os.path.join(root, *FITS.split("/")), encoding="utf-8").read()
        check("the file that fits holds both the owner's line and the update's",
              ("# the owner's own line" in text, "# an older line the update replaces" not in text), (True, True))
        subprocess.run([sys.executable, a, "uninstall", "--remove-data", "--root", root], capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got_, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got_!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
