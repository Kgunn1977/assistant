r"""Acceptance: the Errors box shows only what is true now. Made-up data, scratch home laid down from this plugin.

- The last pass's own problems show; its "the live page could not be updated" does not, since a page that receives the
  refresh was updated.
- While the scheduled pass is switched off, no old pass problem shows, only what is true right now (the listener's own
  troubles), and the Errors block is marked paused, so the page's one "Sync is off" line says it; no second line repeats it.
- A source whose latest reading is fine shows nothing, whatever an earlier reading said.
- When the listener starts, it refreshes the page by itself from what is there now, so a page left from before it stopped
  never keeps showing old troubles when no pass runs.

    python tests\errors_now_acceptance.py
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
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PORT = 47953
results = []
JUDGE = "AI step 'judge' failed: a made-up failure"
STALE = "The live page could not be updated from the scheduled job"


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="errnow-")
    data, root = os.path.join(tmp, "data"), os.path.join(tmp, "Assistant")
    home = os.path.join(root, "Live")
    os.environ["ASSISTANT_LIVE_HOME"] = home
    spec = importlib.util.spec_from_file_location("ac_errnow", os.path.join(PKG, "hooks", "assistant_copy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    lst = None
    try:
        m.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", str(PORT), "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(root, "System", "live", "pass.py")], capture_output=True, text=True, timeout=600)
        check("a first pass makes the page's items", r.returncode, 0)
        health = {"written_at": "2026-11-20T20:13:08", "last_pass": {"started": "2026-11-20T20:01:08", "outcome": "problems"},
                  "problems": [JUDGE, STALE],
                  "sources": {"email": {"status": "ok", "at": "2026-11-20T20:01:58", "detail": "all ok"},
                              "email-sync": {"status": "ok", "at": "2026-11-20T20:03:13", "detail": "fine now"}}}
        with open(os.path.join(home, "health.json"), "w", encoding="utf-8") as f:
            json.dump(health, f)
        sys.path.insert(0, os.path.join(root, "System", "live_page"))
        sys.path.insert(0, os.path.join(root, "System", "live"))
        import publish
        publish.listener_problems = lambda: ["Listening: a made-up trouble that is true now"]
        publish.pass_job_off = lambda: False
        _g, on = publish.health_lines(health, None)
        check("the check on: the last pass's problems, without its 'page could not be updated'", on,
              ["Listening: a made-up trouble that is true now", JUDGE])
        publish.pass_job_off = lambda: True
        _g, off = publish.health_lines(health, None)
        check("the pass off: no old pass problems and no second Sync-off line, only what is true now", off,
              ["Listening: a made-up trouble that is true now"])
        check("... the Errors block is marked paused, so the page says Sync is off once", publish.about(health, None, off, {}, True)["paused"], True)
        check("a source whose latest reading is fine shows nothing", [p for p in on if "email-sync" in p], [])

        # the listener refreshes the page by itself when it starts
        feed = os.path.join(home, "page_state", "local_site", "feed.json")
        os.makedirs(os.path.dirname(feed), exist_ok=True)
        with open(feed, "w", encoding="utf-8") as f:
            json.dump({"docs": [{"problems": ["database busy, from before"]}], "received": "2026-11-20T19:52:00"}, f)
        t0 = time.strftime("%Y-%m-%dT%H:%M:%S")
        lst = subprocess.Popen([sys.executable, os.path.join(root, "System", "live_page", "listen.py")], env=dict(os.environ),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        got = {}
        for _ in range(90):
            time.sleep(1)
            got = json.load(open(feed, encoding="utf-8")) if os.path.isfile(feed) else {}
            if str(got.get("received") or "") >= t0:
                break
        text = json.dumps(got)
        if str(got.get("received") or "") < t0:
            lg = os.path.join(home, "page_state", "listen.log")
            print("LISTEN LOG:", open(lg, encoding="utf-8", errors="replace").read()[-1500:] if os.path.isfile(lg) else "none")
        check("the listener refreshed the page by itself when it started", str(got.get("received") or "") >= t0, True)
        check("... and the page now holds what is true now, not what it held before",
              ("database busy, from before" in text, STALE in text, JUDGE in text), (False, False, True))
    finally:
        if lst and lst.poll() is None:
            subprocess.run(["taskkill", "/PID", str(lst.pid), "/T", "/F"], capture_output=True)
            time.sleep(2)
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
