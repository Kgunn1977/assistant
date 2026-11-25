r"""Acceptance (quick): while an update's check pass runs, the page's listener answers no door that opens the database (the
Google Messages extension's texts and the page wait and ask again), the doors the check pass itself uses stay open, and a hold
left by an update that was cut off ends by itself. On a scratch home laid down from this plugin, made-up data.

    python tests\update_hold_acceptance.py
"""
import datetime as dt
import importlib.util
import json
import os
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PORT = 47943
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def post(path, body, headers):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/{path}", data=json.dumps(body).encode(), method="POST",
                                 headers=dict({"Content-Type": "application/json"}, **headers))
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main():
    tmp = tempfile.mkdtemp(prefix="uphold-")
    data, root = os.path.join(tmp, "data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_hold", os.path.join(PKG, "hooks", "assistant_copy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    lst = None
    try:
        m.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", str(PORT), "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        lst = subprocess.Popen([sys.executable, os.path.join(root, "System", "live_page", "listen.py")], env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2)
                break
            except urllib.error.HTTPError:
                break
            except OSError:
                time.sleep(1)
        beat, hdr = {}, {}                  # a door that opens the database (sending a text); not signed in, so never more than refused
        hold = os.path.join(home, "state", "update_hold.json")
        os.makedirs(os.path.dirname(hold), exist_ok=True)
        with open(hold, "w", encoding="utf-8") as f:
            json.dump({"until": (dt.datetime.now() + dt.timedelta(minutes=5)).isoformat(timespec="seconds")}, f)
        check("held: a door that opens the database is told to ask again", post("api/texts/send", beat, hdr), 503)
        check("held: the check pass's own door still answers (a wrong key is refused, not held)", post("api/feed", {}, {}) != 503, True)
        os.remove(hold)
        check("the hold taken away: that door answers again", post("api/texts/send", beat, hdr) != 503, True)
        with open(hold, "w", encoding="utf-8") as f:
            json.dump({"until": (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat(timespec="seconds")}, f)
        check("a hold past its time (an update cut off) ends by itself", post("api/texts/send", beat, hdr) != 503, True)
        src = open(os.path.join(PKG, "scripts", "assistant.py"), encoding="utf-8").read()
        body = src[src.index("def update_apply("):]
        body = body[:body.index(chr(10) + "def ", 10)]
        check("the update runs no pass of its own (check-pass runs one by hand) and says so",
              ("check_pass(" not in body, "say(NO_PASS)" in body), (True, True))
        # the page reads Sync from the timed pass's job: a page started while the update still had that job off showed Sync Off,
        # and the owner's next save of Sources wrote the Off back (11/22 16:12)
        start = body.index('"/Run", "/TN", c.jobs()[1]')
        check("the update switches the timed pass back on before it starts the page",
              "resume_jobs(paused)" in body[:start] and "resume_jobs(paused, only=" not in body[:start], True)
        # an update's comparison: a step its check pass leaves out on purpose is not compared; a source that failed still is
        spec2 = importlib.util.spec_from_file_location("assistant_cmp", os.path.join(PKG, "scripts", "assistant.py"))
        helper = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(helper)
        fake = type("C", (), {"home": tmp})()
        with open(os.path.join(tmp, "health.json"), "w", encoding="utf-8") as f:
            json.dump({"sources": {"email-reload": {"status": "skipped", "at": "2"}, "calendar": {"status": "failed", "at": "2"},
                                   "email": {"status": "ok", "at": "2"}}}, f)
        check("the update does not count a step its check pass skips on purpose; a failed one still counts",
              helper.newly_failed(fake, {"email-reload": "1", "calendar": "1", "email": "1"}), ["your calendar"])
        # the jobs after an update: the owner's switched-off pass stays off; the listener's job is on again
        state = {"made-up pass": False, "made-up listener": False}
        jobs = type("J", (), {"jobs": lambda self: ["made-up pass", "made-up listener"], "jobs_on": lambda self: list(state)})()
        real_run, real_on = helper.subprocess.run, helper._job_on

        def run(cmd, *a, **k):
            if cmd[:2] == ["schtasks", "/Change"] and "/ENABLE" in cmd:
                state[cmd[cmd.index("/TN") + 1]] = True
            return subprocess.CompletedProcess(cmd, 0, "", "")
        helper.subprocess.run, helper._job_on = run, lambda name: state[name]
        try:
            left = helper.jobs_back_on(jobs, tries=1, paused=["made-up listener"])     # the pass was off before the update
        finally:
            helper.subprocess.run, helper._job_on = real_run, real_on
        check("after an update a pass the owner switched off stays off, and the listener's job is on", (state, left),
              ({"made-up pass": False, "made-up listener": True}, []))
        # after an update the listener runs whenever its job is on, even when it was not running when the update began
        runs, up_now = [], {"v": False}

        def run2(cmd, *a, **k):
            if cmd[:2] == ["schtasks", "/Run"]:
                runs.append(cmd[cmd.index("/TN") + 1])
                up_now["v"] = True
            return subprocess.CompletedProcess(cmd, 0, "", "")
        real_ans = helper.listener_answers
        helper.subprocess.run, helper._job_on = run2, lambda name: True
        helper.listener_answers = lambda c, wait=60: up_now["v"]
        try:
            back = helper.listener_back(jobs)
        finally:
            helper.subprocess.run, helper._job_on, helper.listener_answers = real_run, real_on, real_ans
        check("after an update a listener not running is started when its job is on, and answers", (back, runs), (True, ["made-up listener"]))
        # after an update: only the newest 2 update copies stay; everything else in Update copies is left alone
        td = os.path.join(tmp, helper.UPDATE_COPIES)
        for day, name in (("2026-11-18", "update 0.1.2 101500"), ("2026-11-19", "update 0.1.3 090000"), ("2026-11-19", "update 0.1.3 180000"),
                          ("2026-11-20", "update 0.1.4 201050"), ("2026-11-19", "something of the owner's")):
            os.makedirs(os.path.join(td, day, name, "System"), exist_ok=True)
            open(os.path.join(td, day, name, "System", "a.txt"), "w").write("x")
        open(os.path.join(td, "2026-11-18", "a loose file.txt"), "w").write("x")
        gone = helper.prune_update_copies(fake)
        left = sorted(os.path.relpath(os.path.join(d, n), td).replace(os.sep, "/") for d, ds, _f in os.walk(td) for n in ds
                      if os.path.dirname(os.path.join(d, n)) != td and os.path.dirname(os.path.dirname(os.path.join(d, n))) == td)
        check("after an update only the newest 2 update copies are kept; the rest of Update copies is untouched",
              (gone, left, os.path.isfile(os.path.join(td, "2026-11-18", "a loose file.txt"))),
              (2, ["2026-11-19/something of the owner's", "2026-11-19/update 0.1.3 180000", "2026-11-20/update 0.1.4 201050"], True))
    finally:
        if lst:
            lst.kill()
            time.sleep(1)
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
