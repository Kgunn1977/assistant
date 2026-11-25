r"""Acceptance: an update runs no pass and never meets a database held by another program; a pass is run by hand with
check-pass. On a scratch home laid down from this plugin, its page server running as the owner's would, and a stand-in for the
Google Messages extension posting texts all through. The scheduled jobs are stood in for (the job that starts the page server
starts it here); nothing on this computer's real jobs is touched. Made-up data.

- An update whose new program file does not load is put back, and names the file.
- An update that loads goes through: no pass is run (the pass record and log are untouched), it says "No pass was run; run
  check-pass when you want one.", nothing met a database another program holds, and the page server answers again after.
- check-pass: the page server is not running at all during the pass (texts sent and answered within it are refused at the
  door), the pass runs and its line is said, and the page server answers again after.

    python tests\update_no_pass_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PORT = 47951
BUSY = ("database busy", "already open", "could not set lock")
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def post(path, body, headers):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/{path}", data=json.dumps(body).encode(), method="POST",
                                 headers=dict({"Content-Type": "application/json"}, **headers))
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except OSError:
        return "refused"


def main():
    tmp = tempfile.mkdtemp(prefix="updnopass-")
    data, root = os.path.join(tmp, "data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    os.environ["ASSISTANT_LIVE_HOME"] = home
    spec = importlib.util.spec_from_file_location("ac_nopass", os.path.join(PKG, "hooks", "assistant_copy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    servers, stop = [], threading.Event()
    seen = []                                   # (sent, the door's answer, answered) for every text the stand-in extension posts

    def start_server():
        servers.append(subprocess.Popen([sys.executable, os.path.join(root, "System", "live_page", "listen.py")],
                                        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))

    def up(wait=60):
        for _ in range(wait):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/login", timeout=2) as r:
                    return r.status == 200
            except OSError:
                time.sleep(1)
        return False

    def logs():
        out = ""
        for name in ("errors.log", "crash.log"):
            p = os.path.join(home, "logs", name)
            out += open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
        return out.lower()
    try:
        m.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", str(PORT), "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        sj = os.path.join(root, "Shipped", "shipped.json")
        d = json.load(open(sj, encoding="utf-8"))
        d["version"] = "0.0.9"                  # an older copy, so there is an update to apply
        json.dump(d, open(sj, "w", encoding="utf-8"))
        start_server()
        check("the page server answers 200 before the update", up(), True)

        def asker():                        # the page asked for all through: answered while the server runs, refused while it is stopped
            while not stop.is_set():
                t = time.time()
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/login", timeout=10) as r:
                        got = r.status
                except urllib.error.HTTPError as e:
                    got = e.code
                except OSError:
                    got = "refused"
                seen.append((t, got, time.time()))
                time.sleep(0.4)
        threading.Thread(target=asker, daemon=True).start()
        time.sleep(3)

        # the helper, in this process, with the scheduled jobs stood in for: the listener's job starts the page server here
        spec2 = importlib.util.spec_from_file_location("assistant_nopass", os.path.join(data, "scripts", "assistant.py"))
        a = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(a)
        real_run, said = a.subprocess.run, []
        c = a.Copy(root)
        jobs = c.jobs()

        def run(cmd, *args, **kw):
            if isinstance(cmd, list) and cmd and cmd[0] == "schtasks":
                if "/Run" in cmd and jobs[1] in cmd:
                    start_server()
                out = ("\n".join(f'"\\{j}","x","Ready"' for j in jobs) + "\n") if "/Query" in cmd and "/TN" not in cmd else "Status: Ready\n"
                return subprocess.CompletedProcess(cmd, 0, out, "")
            return real_run(cmd, *args, **kw)
        a.subprocess.run = run
        a.say = lambda *lines: said.extend(lines)
        health = os.path.join(home, "health.json")
        plog = os.path.join(home, "logs", "pass.log")
        size = lambda p: os.path.getsize(p) if os.path.isfile(p) else 0    # noqa: E731

        # 1. a new program file that does not load: put back
        held = os.path.join(data, "engine", "System", "live", "held.py")
        good = open(held, encoding="utf-8").read()
        open(held, "w", encoding="utf-8").write('raise RuntimeError("a made-up file that does not load")\n' + good)
        code = a.update_apply(c)
        out = "\n".join(str(x) for x in said)
        check("a new program file that does not load: the update is put back and names the file",
              (code, "do not load" in out, "held.py" in out, "Everything is back" in out,
               "raise RuntimeError" in open(os.path.join(live, "held.py"), encoding="utf-8").read()), (1, True, True, True, False))
        check("... and the page server answers after", up(60), True)

        # 2. an update that loads: no pass, nothing held, the page back
        open(held, "w", encoding="utf-8").write(good + "\n# a made-up line the update brings\n")
        said.clear()
        before = (os.path.getmtime(health), size(plog))
        code = a.update_apply(c)
        t1 = time.time()
        out = "\n".join(str(x) for x in said)
        check("an update that loads goes through", (code, "Updated" in out,
                                                    "a made-up line the update brings" in open(os.path.join(live, "held.py"), encoding="utf-8").read()),
              (0, True, True))
        check("... runs no pass: the pass record and the pass log are untouched", (os.path.getmtime(health), size(plog)), before)
        check("... and says so", (a.NO_PASS in out, a.NO_PASS), (True, "No pass was run; run check-pass when you want one."))
        check("... nothing on the way met a database another program holds", [w for w in BUSY if w in out.lower() + logs()], [])
        time.sleep(3)
        check("... and the page server answers again", (up(30), [s for t, s, t2 in seen if t > t1][-1:]), (True, [200]))

        # 3. check-pass by hand: the page server stopped for the pass, the pass's line said, the page back
        said.clear()
        window, real_check = {}, a.check_pass

        def check_pass(*args, **kw):
            window["start"] = time.time()
            window["alive"] = [x.pid for x in servers if x.poll() is None]     # page servers still running as the pass starts
            try:
                return real_check(*args, **kw)
            finally:
                window["alive"] += [x.pid for x in servers if x.poll() is None]
                window["end"] = time.time()
        a.check_pass = check_pass
        a._job_on = lambda name: True
        n_before = size(plog)
        code = a.check_pass_now(c)
        out = "\n".join(str(x) for x in said)
        # the page server's processes, looked at as the pass starts and as it ends (a pass on a small home lasts about 2
        # seconds, shorter than one refused ask on Windows, so asks to the door cannot show it); asks that began and ended
        # inside the pass are refused too
        during = [s for t, s, t2 in seen if window.get("start", 0) <= t and t2 <= window.get("end", 0)]
        check("check-pass runs one pass and says its line", (code, size(plog) > n_before, out.startswith("Check: ")), (0, True, True))
        check("... with the page server not running at all through the pass: no server process, and every ask within it refused",
              (window.get("alive"), sorted({str(x) for x in during} - {"refused"})), ([], []))
        check("... and the page server back and answering after", ("The page is back and answering." in out, up(30)), (True, True))
        check("... nothing met a database another program holds", [w for w in BUSY if w in out.lower() + logs()], [])
        open(held, "w", encoding="utf-8").write(good)
    finally:
        stop.set()
        time.sleep(1)
        for s in servers:
            if s.poll() is None:
                subprocess.run(["taskkill", "/PID", str(s.pid), "/T", "/F"], capture_output=True)
        time.sleep(2)
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
