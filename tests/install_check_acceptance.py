r"""Acceptance: an update runs no check pass (since 0.1.4; check-pass runs one by hand), so a source that would now fail
neither stops it nor puts the old program back, and a source already failing does not stop it either. On a scratch copy laid
down from this plugin, with a stand-in mailbox (a connection type written into the scratch home's taught folder) that reads
fine until it is told to fail. Nothing outside the scratch folder changes.

    python tests\install_check_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []

STANDIN = r'''
import os
TYPE = "standin_box"
NAME = "Stand-in mailbox"
KIND = "email"
CAN_SEND = False
ASKS = []
SETUP = "A stand-in mailbox for the acceptance test."


def check(conn):
    return "reachable"


def gather(conn, ctx):
    if os.path.exists(os.environ["STANDIN_FAIL"]):
        raise RuntimeError("the stand-in mailbox refused")
    return "0 new"
'''

SETUP = r'''
import os, sys
sys.path.insert(0, sys.argv[1])
import common, connections
os.makedirs(os.path.join(common.HOME, "taught", "connections"), exist_ok=True)
with open(os.path.join(common.HOME, "taught", "connections", "standin_box.py"), "w", encoding="utf-8") as f:
    f.write(sys.argv[2])
connections.save({"id": "c1", "type": "standin_box", "address": "me@one.example", "label": "me@one.example", "on": True})
connections.save({"id": "c2", "type": "standin_box", "address": "me@two.example", "label": "me@two.example", "on": True})
p = common.read_json(common.PERSONAL_JSON, {}) or {}
p["sources"] = ["email"]
common.write_json(common.PERSONAL_JSON, p)
print("ok")
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="installcheck-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    fail = os.path.join(tmp, "fail-now")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home, STANDIN_FAIL=fail)
    a = os.path.join(data, "scripts", "assistant.py")
    spec = importlib.util.spec_from_file_location("assistant_copy_ic", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)

    def older():
        sj = os.path.join(root, "Shipped", "shipped.json")
        d = json.load(open(sj, encoding="utf-8"))
        d["version"] = "0.0.9"
        json.dump(d, open(sj, "w", encoding="utf-8"))

    def version():
        return (json.load(open(os.path.join(home, "personal", "install.json"), encoding="utf-8")) if os.path.isfile(os.path.join(home, "personal", "install.json"))
                else {}).get("version")
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, a, "lay-down", "--port", "47895", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-c", SETUP, live, STANDIN], capture_output=True, text=True, env=env)
        check("two stand-in mailboxes connected", r.stdout.strip(), "ok")
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        h = json.load(open(os.path.join(home, "health.json"), encoding="utf-8"))
        check("a pass reads both fine", [(h["sources"].get(k) or {}).get("status") for k in ("email:me@one.example", "email:me@two.example")], ["ok", "ok"])

        # a clean update ends as a success
        older()
        r = subprocess.run([sys.executable, a, "update-apply", "--root", root], capture_output=True, text=True, env=env, timeout=1200)
        check("a clean update ends as a success", (r.returncode, "Updated" in r.stdout), (0, True))

        # the next update runs no pass: a source that would fail now does not stop it, and the new program stays
        older()
        open(fail, "w").close()
        r = subprocess.run([sys.executable, a, "update-apply", "--root", root], capture_output=True, text=True, env=env, timeout=1200)
        said = (r.stdout + r.stderr).strip()
        check("an update runs no pass, so a source that would fail now does not stop it",
              (r.returncode, "Updated" in said, "No pass was run; run check-pass when you want one." in said, "Everything is back as it was before" in said),
              (0, True, True, False))
        sj = json.load(open(os.path.join(root, "Shipped", "shipped.json"), encoding="utf-8"))
        want = json.load(open(os.path.join(PKG, ".claude-plugin", "plugin.json"), encoding="utf-8"))["version"]
        check("the new program stays", sj.get("version"), want)

        # a source that was already failing before the update does not stop it
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        older()
        r = subprocess.run([sys.executable, a, "update-apply", "--root", root], capture_output=True, text=True, env=env, timeout=1200)
        check("a source already failing before the update does not stop it", (r.returncode, "Updated" in r.stdout), (0, True))
        os.remove(fail)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
