r"""Acceptance: an update started while the assistant's regular check (a pass) is running waits for it, then applies;
one whose wait runs out says so plainly and changes nothing. On a scratch copy laid down from this plugin, a stand-in
process holds the pass lock the way a running pass does. Nothing outside the scratch folder changes.

    python tests\update_wait_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []

HOLDER = r'''
import json, os, sys, time
lock = sys.argv[1]
with open(lock, "w") as f:
    json.dump({"pid": os.getpid(), "at": time.time()}, f)
print("held", flush=True)
time.sleep(float(sys.argv[2]))
os.remove(lock)
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def version(root):
    return json.load(open(os.path.join(root, "Shipped", "shipped.json"), encoding="utf-8")).get("version")


def asides(root):
    base = os.path.join(root, "Live", "Update copies")
    return sorted(n for _d, dirs, _f in os.walk(base) for n in dirs if n.startswith("update ")) if os.path.isdir(base) else []


def hold(root, seconds):
    p = subprocess.Popen([sys.executable, "-c", HOLDER, os.path.join(root, "Live", "pass.lock"), str(seconds)],
                         stdout=subprocess.PIPE, text=True)
    p.stdout.readline()                                         # the lock is held from here
    return p


def main():
    tmp = tempfile.mkdtemp(prefix="updwait-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    spec = importlib.util.spec_from_file_location("assistant_copy_wait", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    a = os.path.join(data, "scripts", "assistant.py")
    holder = None
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, a, "lay-down", "--port", "47907", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        new = version(root)
        sj = os.path.join(root, "Shipped", "shipped.json")
        d = json.load(open(sj, encoding="utf-8"))
        d["version"] = "0.0.9"                                  # an older copy, so there is an update to apply
        json.dump(d, open(sj, "w", encoding="utf-8"))

        # 1. a check that runs past the wait: said plainly, nothing changed
        holder = hold(root, 300)
        r = subprocess.run([sys.executable, a, "update-apply", "--root", root, "--wait", "0.1"], capture_output=True, text=True, timeout=300)
        out = r.stdout + r.stderr
        check("a check still running when the wait runs out: refused", r.returncode, 1)
        check("... said plainly: not updated yet, nothing changed, run it again once the check is done",
              ["Not updated yet" in out, "nothing was changed" in out, "Run the update again once the check is done" in out], [True, True, True])
        check("... and nothing changed: the old version, no safety copy", (version(root), asides(root)), ("0.0.9", []))
        holder.kill()
        holder.wait()
        os.remove(os.path.join(root, "Live", "pass.lock"))

        # 2. a check that finishes during the wait: the update waits, then applies
        holder = hold(root, 25)
        t0 = time.time()
        r = subprocess.run([sys.executable, a, "update-apply", "--root", root, "--wait", "3"], capture_output=True, text=True, timeout=1500)
        waited = time.time() - t0
        out = r.stdout + r.stderr
        check("an update started during a check says it waits for it", "starts as soon as it finishes" in out, True)
        check("... waits for the check to end before it starts", waited >= 20, True)
        check("... then applies", (r.returncode, version(root), len(asides(root))), (0, new, 1))
        if r.returncode:
            print(out[-1500:])
    finally:
        if holder and holder.poll() is None:
            holder.kill()
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
