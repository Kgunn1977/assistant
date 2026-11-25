r"""Acceptance: the home update refuses while another update holds the home's update lock, refuses when a file it would
take holds merge-conflict markers (changing nothing), and a normal update still goes through. On a scratch copy laid down
from this plugin; nothing outside the temp folder changes.

    python tests\update_guard_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []

HOLDER = r'''
import json, os, sys, time
with open(sys.argv[1], "w") as f:
    json.dump({"pid": os.getpid(), "at": time.time()}, f)
print("held", flush=True)
time.sleep(float(sys.argv[2]))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def version(root):
    return json.load(open(os.path.join(root, "Shipped", "shipped.json"), encoding="utf-8")).get("version")


def run(a, root, *more):
    r = subprocess.run([sys.executable, a, "update-apply", "--root", root, "--wait", "0.1", *more], capture_output=True, text=True, timeout=900)
    return r, r.stdout + r.stderr


def main():
    tmp = tempfile.mkdtemp(prefix="updguard-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    spec = importlib.util.spec_from_file_location("assistant_copy_guard", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    a = os.path.join(data, "scripts", "assistant.py")
    lock = os.path.join(root, "Live", "update.lock")
    holder = None
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, a, "lay-down", "--port", "47908", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        if r.returncode:
            print((r.stdout + r.stderr)[-1500:])
        new = version(root)
        sj = os.path.join(root, "Shipped", "shipped.json")
        d = json.load(open(sj, encoding="utf-8"))
        d["version"] = "0.0.9"
        json.dump(d, open(sj, "w", encoding="utf-8"))

        # (a) a second update while the first holds the lock
        holder = subprocess.Popen([sys.executable, "-c", HOLDER, lock, "600"], stdout=subprocess.PIPE, text=True)
        holder.stdout.readline()
        r, out = run(a, root)
        check("(a) second update refused with one plain line, non-zero",
              (r.returncode, out.startswith("Another update is running on this assistant, started "), len(out.strip().splitlines()), version(root)),
              (1, True, 1, "0.0.9"))
        holder.kill()
        holder.wait()
        check("(a) the killed holder left its lock file behind (stale, taken over next)", os.path.isfile(lock), True)

        # (b) a file it would take holds a conflict marker: refused, nothing changed
        rel = "live/items.py"
        victim = os.path.join(data, "engine", "System", *rel.split("/"))
        original = open(victim, "rb").read()
        with open(victim, "ab") as f:
            f.write(b"\n<<<<<<< HEAD\nx = 1\n=======\nx = 2\n>>>>>>> other\n")
        os.remove(os.path.join(root, "System", *rel.split("/")))        # so the update would take it
        r, out = run(a, root)
        check("(b) marker file refused, naming the file, nothing changed",
              (r.returncode, rel in out, version(root), os.path.exists(os.path.join(root, "System", *rel.split("/"))), os.path.isfile(lock)),
              (1, True, "0.0.9", False, False))
        with open(victim, "wb") as f:
            f.write(original)

        # (c) a normal update goes through, and the lock is released
        r, out = run(a, root)
        check("(c) normal update goes through, lock released", (r.returncode, version(root), os.path.isfile(lock)), (0, new, False))
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
