r"""Acceptance (quick): one background job. The listener runs the 15-minute check itself, as its own program; the page keeps
answering while a check runs; a check that raises or hangs leaves the listener serving; a second copy started beside it
ends at once with 0 (so the job's 5-minute start never shows a refused start); setup makes only the listener's job, and an
update deletes an older home's pass job (Sync kept off when the owner had it off). On a scratch home
laid down from this plugin, with a stand-in check so no account is read; no scheduled job is made on this computer.

    python tests\one_server_acceptance.py
"""
import importlib.util
import json
import os
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PORT = 47961
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
results = []

STAND_IN = r'''import os, sys, time
home = os.environ["ASSISTANT_LIVE_HOME"]
mode = open(os.path.join(home, "pass_mode.txt")).read().strip() if os.path.isfile(os.path.join(home, "pass_mode.txt")) else "sleep"
with open(os.path.join(home, "stand_in.log"), "a") as f:
    f.write(f"start {mode} {time.time()}\n")
if mode == "raise":
    raise RuntimeError("a made-up check that fails")
time.sleep(60 if mode == "hang" else 8)
with open(os.path.join(home, "stand_in.log"), "a") as f:
    f.write(f"end {mode} {time.time()}\n")
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def page_up():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/login", timeout=5) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def lines(path):
    return open(path, encoding="utf-8").read().splitlines() if os.path.isfile(path) else []


def wait_for(fn, secs):
    end = time.time() + secs
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.5)
    return fn()


def main():
    tmp = tempfile.mkdtemp(prefix="oneserver-")
    data, root = os.path.join(tmp, "data"), os.path.join(tmp, "Assistant")
    home, live, page = os.path.join(root, "Live"), os.path.join(root, "System", "live"), os.path.join(root, "System", "live_page")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_one", os.path.join(PKG, "hooks", "assistant_copy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    lst = None
    try:
        m.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", str(PORT), "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        os.replace(os.path.join(live, "messages_link", "messages-link.exe"), os.path.join(tmp, "messages-link.exe"))  # no texts link here
        os.replace(os.path.join(live, "pass.py"), os.path.join(tmp, "real pass.py"))
        with open(os.path.join(live, "pass.py"), "w", encoding="utf-8") as f:
            f.write(STAND_IN)
        stand_in, listen_log = os.path.join(home, "stand_in.log"), os.path.join(home, "page_state", "listen.log")
        # the listener with its check timings shortened for the test: first check 2 s after start, then every 25 s, ended at 12 s
        run_it = ("import sys; sys.path.insert(0, sys.argv[1]); import listen; "
                  "listen.PASS_FIRST, listen.PASS_EVERY, listen.PASS_MOST = 2, 25, 12; sys.exit(listen.main())")
        t0 = time.time()
        lst = subprocess.Popen([sys.executable, "-c", run_it, page], cwd=page, env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        check("the page answers", wait_for(page_up, 60), True)

        # (2) the listener starts a check on its schedule, and the page answers while it runs
        started = wait_for(lambda: [ln for ln in lines(stand_in) if ln.startswith("start sleep")], 30)
        check("the listener started a check on its own, soon after it started", bool(started) and time.time() - t0 < 40, True)
        during = [page_up() for _ in range(3)]
        still_running = not [ln for ln in lines(stand_in) if ln.startswith("end sleep")]
        check("the page answered while the check was running", (during, still_running), ([True] * 3, True))
        check("the check finished and the listener logged it",
              bool(wait_for(lambda: [ln for ln in lines(listen_log) if "check done (exit 0)" in ln], 20)), True)

        # a second copy, as the job's 5-minute start makes beside the running one, ends at once with 0
        r2 = subprocess.run([sys.executable, os.path.join(page, "listen.py")], cwd=page, env=env, capture_output=True,
                            timeout=60, creationflags=NO_WINDOW)
        check("a second copy started beside it ends at once with 0", r2.returncode, 0)

        # (3) a check that raises leaves the listener serving, and is said as a problem
        with open(os.path.join(home, "pass_mode.txt"), "w") as f:
            f.write("raise")
        check("the next check ran on schedule and raised",
              bool(wait_for(lambda: [ln for ln in lines(stand_in) if ln.startswith("start raise")], 40)), True)
        said = wait_for(lambda: [ln for ln in lines(listen_log) if "ended without finishing" in ln and "RuntimeError" in ln], 15)
        check("the failed check is logged as a problem with its error", bool(said), True)
        check("after the failed check the listener runs and the page answers", (lst.poll(), page_up()), (None, True))

        # a check that hangs is ended at its limit, and the listener still serves
        with open(os.path.join(home, "pass_mode.txt"), "w") as f:
            f.write("hang")
        check("a hanging check is ended at its limit",
              bool(wait_for(lambda: [ln for ln in lines(listen_log) if "check ended at its limit" in ln], 60)), True)
        check("after the hung check the listener runs and the page answers", (lst.poll(), page_up()), (None, True))
        check("the hung check's program was ended with it", [ln for ln in lines(stand_in) if ln.startswith("end hang")], [])
        lst.kill()
        lst.wait(30)
        lst = None

        # (4) setup makes only the listener's job; an update retires an older home's pass job. Windows is stood in for:
        # no scheduled job is made, changed or removed on this computer.
        sys.path.insert(0, live)
        os.environ["ASSISTANT_LIVE_HOME"] = home
        import setup_steps as ss
        names = ss.job_names()
        made, ran = set(), []

        def fake_run(cmd, *a, **k):
            ran.append(list(cmd))
            out = ""
            if cmd[:2] == ["schtasks", "/Query"] and "/XML" in cmd:
                out = "<Task>made-up</Task>"
            elif cmd[:2] == ["schtasks", "/Query"] and "/FO" in cmd and "LIST" in cmd:
                out = "Status: Disabled"
            elif cmd[:2] == ["schtasks", "/Query"]:
                out = "".join(f'"\\{n}","",""\n' for n in made)
            elif cmd[0] == "powershell":
                made.add(names[1])
            elif cmd[:2] == ["schtasks", "/Delete"]:
                made.discard(cmd[cmd.index("/TN") + 1])
            return subprocess.CompletedProcess(cmd, 0, out, "")
        real = ss.subprocess.run
        ss.subprocess.run = fake_run
        try:
            ss.turn_on(say=lambda *_: None)
            scripts = sorted(os.listdir(os.path.join(home, "personal", "install")))
            text = open(os.path.join(home, "personal", "install", "install_listener.ps1"), encoding="utf-8").read()
            check("setup runs one install script and makes only the listener's job",
                  ([c[-1].endswith("install_listener.ps1") for c in ran if c[0] == "powershell"], sorted(made), scripts),
                  ([True], [names[1]], ["install_listener.ps1"]))
            check("the job starts side by side (no refused start) and makes one task",
                  ("-MultipleInstances Parallel" in text, "IgnoreNew" in text, text.count("Register-ScheduledTask -TaskName")), (True, False, 1))
            made.add(names[0])                          # an older home's pass job, switched off by its owner (Sync off)
            open(os.path.join(home, "personal", "install", "install_task.ps1"), "w").write("old")
            gone = ss.retire_pass_job(owner_off=True)
            sync_off = bool((ss.common.settings().get("gathering") or {}).get("paused"))
            check("an update deletes the old pass job and its script outright, with no To Delete folder; Sync stays off",
                  (gone, os.path.isfile(os.path.join(home, "personal", "install", "install_task.ps1")), sorted(made), sync_off,
                   os.path.exists(os.path.join(home, "To Delete"))),
                  (names[0], False, [names[1]], True, False))
        finally:
            ss.subprocess.run = real
    finally:
        if lst is not None:
            lst.kill()
    bad = [r for r in results if not r[1]]
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n     got {got!r}\n     want {want!r}"))
    print(f"{len(results) - len(bad)}/{len(results)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
