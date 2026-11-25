r"""Acceptance (quick): a pass that runs out of time partway leaves its work for the next pass, not for an hour later, and
its page refresh still gets time to finish. A thinking step cut short by the pass's time is put off, not failed, so the next
pass judges what is left at once (a real failure still waits before it is tried again); the page refresh, the pass's last
step, may run past the point where new work stops. On a scratch copy laid down from this plugin; no Claude run.

    python tests\pass_time_acceptance.py
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

INSIDE = r'''
import json, os, sys, time
live, slow = sys.argv[1], sys.argv[2]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import common, limits, think, gather
out = {}
limits.begin("t")
cut = think._step("judge", lambda: (False, "FAILED: the judging payload could not be made: judgment_payload.py not started: the check was out of time"))
out["cut short"] = [cut["ok"], bool(cut.get("put_off"))]
bad = think._step("judge", lambda: (False, "FAILED: the judge could not be read"))
out["a real failure"] = [bad["ok"], bool(bad.get("put_off"))]
g = {"unjudged": 30, "pages_waiting": 0, "texted_images_waiting": 0, "new_messages": 0, "new_attachments": 0}
common.write_json(common.THINK_STATE, {"failed_at": None, "rewrite_items": [], "pending_items": [], "pending_msgs": [7], "last": []})
out["next pass after a put-off"] = bool(think.needed(g))
common.write_json(common.THINK_STATE, {"failed_at": common.now().isoformat(), "rewrite_items": [], "pending_items": [], "pending_msgs": [7], "last": []})
out["next pass after a real failure"] = bool(think.needed(g))
# the Errors part: a step that only ran out of time (as recorded before this change) is not carried to later passes; a real
# failure is, until thinking runs again
import importlib
passmod = importlib.import_module("pass")
old_cut = "AI step 'judge' failed: FAILED: the judging payload could not be made: judgment_payload.py not started: the check was out of time"
real = "AI step 'judge' failed: FAILED: the verdicts could not be read"
common.write_json(common.HEALTH_JSON, {"problems": [old_cut, real], "ai_steps": []})
passmod.write_health({"id": "t2", "outcome": "ok"}, None, None, [])
out["carried"] = (common.read_json(common.HEALTH_JSON, {}) or {}).get("problems")
limits._state["start"] = time.time() - 700          # past the point where new work stops (as the 716 s pass was)
out["caps"] = [limits.cap(90), limits.finish_cap(90) > 10]
out["refresh, finishing"] = gather.run_script(slow, timeout=90, finishing=True)[0]
out["a new step then"] = gather.run_script(slow, timeout=90)[0]
print(json.dumps(out))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="passtime-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    slow = os.path.join(tmp, "slow.py")
    with open(slow, "w", encoding="utf-8") as f:
        f.write("import time\ntime.sleep(7)\nprint('done')\n")
    spec = importlib.util.spec_from_file_location("ac_passtime", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47936", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, slow], capture_output=True, text=True, env=env, timeout=300)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        check("a step cut short by the pass's time is put off, not failed", o.get("cut short"), [True, True])
        check("a real failure is still a failure", o.get("a real failure"), [False, False])
        check("after a put-off the next pass thinks at once", o.get("next pass after a put-off"), True)
        check("after a real failure it still waits before trying again", o.get("next pass after a real failure"), False)
        check("a step that only ran out of time stays off the Errors part; a real failure stays on it", o.get("carried"),
              ["AI step 'judge' failed: FAILED: the verdicts could not be read"])
        check("past the work limit a new step gets 5 seconds, the page refresh more", o.get("caps"), [5, True])
        check("the page refresh finishes past the work limit", o.get("refresh, finishing"), True)
        check("a new step there is still cut off", o.get("a new step then"), False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
