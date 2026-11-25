r"""Acceptance: the page listener and a pass never lock each other out. On a scratch copy laid down from this plugin,
the listener's own way in (answers._connect) holds a write while a whole pass runs: the pass waits and ends ok. And the
listener, finding the database held (by another process, or by its own program the other way), gets "busy" at once
instead of an error. Nothing outside the scratch folder changes.

    python tests\database_busy_acceptance.py
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
HOLD_SECONDS = 8
results = []

HOLDER = r'''
import sys, time
sys.path.insert(0, sys.argv[1])
import answers
con = answers._connect()
if con is None:
    print("busy", flush=True); sys.exit(3)
con.execute("CREATE TABLE IF NOT EXISTS hold_test (x INTEGER)")
con.execute("INSERT INTO hold_test VALUES (1)")
print("held", flush=True)
time.sleep(float(sys.argv[2]))
con.close()
print("released", flush=True)
'''

LISTENER_SIDE = r'''
import sys, time, json
sys.path.insert(0, sys.argv[1])
import answers, db
out = {}
t = time.time(); con = answers._connect(); out["other_process"] = [con is None, round(time.time() - t, 2)]
print(json.dumps(out), flush=True)
'''

SAME_PROGRAM = r'''
import sys, time, json
sys.path.insert(0, sys.argv[1])
import answers, db
reader = db.connect(read_only=True)
t = time.time()
try:
    con = answers._connect(); got = con is None
except Exception as e:
    got = type(e).__name__ + ": " + str(e)[:80]
reader.close()
print(json.dumps({"same_program": [got, round(time.time() - t, 2)]}), flush=True)
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="db-busy-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_busy", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47897",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        # 1. the listener holds a write while a pass runs
        holder = subprocess.Popen([sys.executable, "-c", HOLDER, live, str(HOLD_SECONDS)], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, env=env)
        check("the listener's way in takes the database", holder.stdout.readline().strip(), "held")
        t = time.time()
        side = subprocess.run([sys.executable, "-c", LISTENER_SIDE, live], capture_output=True, text=True, env=env)
        got = (json.loads(side.stdout or "{}").get("other_process") or [None, 99])
        check("held by another process: the listener hears busy at once, no error", (got[0], got[1] < 1.5, side.stderr.strip()[-200:]),
              (True, True, ""))
        p = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        took = time.time() - t
        holder.wait(timeout=60)
        last = (json.load(open(os.path.join(home, "health.json"), encoding="utf-8")).get("last_pass") or {}).get("outcome")
        check("a pass started while the listener held it waits and ends ok", (p.returncode, last), (0, "ok"))
        check(f"the pass really waited for the hold (took {took:.1f}s, hold {HOLD_SECONDS}s)", took >= HOLD_SECONDS - 1, True)
        errs = os.path.join(home, "logs", "errors.log")
        text = open(errs, encoding="utf-8").read() if os.path.isfile(errs) else ""
        check("no 'database busy' or 'different configuration' in the error log",
              ("database busy" in text, "different configuration" in text), (False, False))
        # 2. the listener's own program holds it the other way (reading only): busy, not an error
        same = subprocess.run([sys.executable, "-c", SAME_PROGRAM, live], capture_output=True, text=True, env=env)
        got = (json.loads(same.stdout or "{}").get("same_program") or [None, 99])
        check("held the other way by the same program: busy at once, no error", (got[0], got[1] < 1.5), (True, True))
        subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "uninstall", "--remove-data",
                        "--root", root], capture_output=True, text=True)
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
