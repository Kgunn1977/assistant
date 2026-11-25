r"""Acceptance of adopt (an existing copy taken over by the plugin), on a stand-in made from the owner's own copy.

    python tests\adopt_acceptance.py --old-root "<the owner's folder holding System and Live>"

Read only on the owner's copy: it copies System\live and System\live_page, and the data home without the database,
attachments, past builds, To Delete and the locked key store, into a scratch folder in %TEMP%, then makes the stand-in
safe before anything runs: every account switched off, phone alerts and reach from anywhere taken out, its own port,
job names that exist nowhere, and its roadmap list pointing only at a scratch project. Then: the old program serves
the stand-in's page; adopt moves it to a new folder (no jobs made); the new program serves the page; the downtime is
measured; the way back is tried; everything is removed. Prints one line per check and a count.
"""
import hashlib
import json
import os
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
PORT = 47896
results = []
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
SKIP_HOME = {os.path.join("Resources", "Database"), os.path.join("Resources", "Attachments"), "builds", "To Delete"}


def via_shell(args):
    """Run the helper the way a Claude session does: through a shell whose own command line holds the whole command,
    data-folder paths included (the owner's real run of 11/17/26 was stopped by its own helper this way)."""
    line = subprocess.list2cmdline(args)
    return subprocess.run('cmd /s /c "' + line + '"', capture_output=True, text=True)    # /s: cmd keeps the inner quotes


def check(name, got, want):
    results.append((name, got == want, got, want))


def digest(path):
    if os.path.isfile(path):
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    h = hashlib.sha256()
    for f, dirs, n in sorted(os.walk(path)):
        dirs.sort()
        for x in sorted(n):
            h.update(x.encode() + open(os.path.join(f, x), "rb").read())
    return h.hexdigest()[:16]


def serves(timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=3) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except OSError:
            time.sleep(0.25)
    return None


def kill(proc):
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)


def main(old_root):
    tmp = tempfile.mkdtemp(prefix="adopt-")
    try:
        return run(old_root, tmp)
    finally:
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains('"
              + tmp.lower() + "') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
        time.sleep(1)
        _cleanup.remove(tmp)
        print(f"scratch removed: {not os.path.exists(tmp)}")


def run(old_root, tmp):
    old, new, data = os.path.join(tmp, "ClaudeOS stand-in"), os.path.join(tmp, "ClaudeOS stand-in", "Assistant"), os.path.join(tmp, "plugin-data")
    # the new folder sits inside the old one, as the owner chose (ClaudeOS\Assistant): his backup keeps covering it
    for part in ("live", "live_page"):
        shutil.copytree(os.path.join(old_root, "System", part), os.path.join(old, "System", part),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    src = os.path.join(old_root, "Live")

    def skip(folder, names):
        rel = os.path.relpath(folder, src)
        # never the key store, and never a lock: a lock names the owner's own running pass, which a stand-in pass
        # could otherwise judge stale and end
        return [n for n in names if os.path.normpath(os.path.join(rel, n)) in SKIP_HOME or n == "keys.dat" or n.endswith(".lock")]
    shutil.copytree(src, os.path.join(old, "Live"), ignore=skip)
    home = os.path.join(old, "Live")
    # make the stand-in safe before anything runs
    cpath = os.path.join(home, "personal", "connections.json")
    conns = json.load(open(cpath, encoding="utf-8"))
    for cn in conns.get("connections") or []:
        cn["on"] = False
    json.dump(conns, open(cpath, "w", encoding="utf-8"))
    project = os.path.join(tmp, "Stand-in project")
    spath = os.path.join(home, "personal", "settings.json")
    s = json.load(open(spath, encoding="utf-8"))
    s.pop("alerts", None)
    s.pop("page_reach", None)
    s["page_port"] = PORT
    s["roadmaps"] = [{"folder": project, "applied": "2026-11-17T00:00:00"}]
    json.dump(s, open(spath, "w", encoding="utf-8"))
    json.dump({"pass": "Assistant stand-in pass (not made)", "listener": "Assistant stand-in listener (not made)"},
              open(os.path.join(home, "personal", "jobs.json"), "w", encoding="utf-8"))
    old_reader = "assistant " + hashlib.sha1(os.path.normcase(os.path.abspath(home)).encode("utf-8")).hexdigest()[:6]
    os.makedirs(os.path.join(project, "Roadmap page"))
    json.dump({"about": "x", "readers": {old_reader: {"since": "2026-11-17T00:00:00"}, "someone else": {}}},
              open(os.path.join(project, "Roadmap page", "readers.json"), "w", encoding="utf-8"))
    def people(h):
        got = json.load(open(os.path.join(h, "known_people.json"), encoding="utf-8")).get("people") or []
        return sorted((str(p.get("name")), str(p.get("email"))) for p in got)

    def snapshot(h):
        out = {k: digest(os.path.join(h, *k.split("/"))) for k in
               ("Resources/Rules", "personal/settings.json", "personal/personal.json", "page_state/local_site/config.json")}
        # not compared: known_people.json and items.json are each pass's own export from the database
        # (people.write_people, items.export); the stand-in has no database, so any pass empties them, old program or new
        return out
    check("stand-in made: no key store, no database, no lock", (os.path.exists(os.path.join(home, "personal", "keys.dat")),
          os.path.exists(os.path.join(home, "Resources", "Database")), os.path.exists(os.path.join(home, "pass.lock"))), (False, False, False))
    # the old program serves the stand-in's page
    oldl = subprocess.Popen([PYW, os.path.join(old, "System", "live_page", "listen.py")], cwd=os.path.join(old, "System", "live_page"))
    check("before: the old program serves the page", serves(), 200)
    # adopt, from the plugin's working copy, as the switch-over runs it
    sys.path.insert(0, os.path.join(PKG, "hooks"))
    import assistant_copy
    assistant_copy.sync(data)
    a = os.path.join(data, "scripts", "assistant.py")
    plan = json.loads(subprocess.run([sys.executable, a, "adopt-plan", "--from", old, "--root", new], capture_output=True, text=True).stdout)
    choices = os.path.join(home, "state", "adopt-choices.json")      # inside the old data folder, as the real run had it
    json.dump({rel: "new" for rel in plan["differ"]}, open(choices, "w"))
    kept = snapshot(home)                          # just before adopt, with the old program running
    t0 = time.time()
    r = via_shell([sys.executable, a, "adopt", "--from", old, "--root", new, "--choices", choices, "--no-jobs"])
    out = (r.stdout + r.stderr).strip()
    check("adopt ends ok", r.returncode, 0)
    out_text = (r.stdout + r.stderr).strip()
    check("adopt printed what it did (never silent)", bool(out_text), True)
    if r.returncode:
        for name, ok, got, want in results:
            print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
        print("adopt said: " + (out_text[-600:] or "(nothing)"))
        print(f"{sum(x[1] for x in results)} of {len(results)} passed (stopped: adopt failed)")
        return 1
    if r.returncode:
        print(out)
    oldl.poll()
    check("the old program was stopped by adopt", oldl.returncode is not None, True)
    nhome = os.path.join(new, "Live")
    after = snapshot(nhome)                        # before the new page program opens its files
    newl = subprocess.Popen([PYW, os.path.join(new, "System", "live_page", "listen.py")], cwd=os.path.join(new, "System", "live_page"))
    check("after: the new program serves the page", serves(), 200)
    downtime = time.time() - t0
    check("the data home moved (not copied)", (os.path.isdir(nhome), os.path.exists(home)), (True, False))
    check("rules, settings, who you are and the page's password unchanged", after, kept)
    health = json.load(open(os.path.join(nhome, "health.json"), encoding="utf-8")).get("last_pass") or {}
    check("the check pass with the new program ended ok", health.get("outcome"), "ok")
    rec = json.load(open(os.path.join(nhome, "personal", "install.json"), encoding="utf-8"))
    check("install record: version, repository, where it came from", (rec.get("version"), rec.get("repo"), (rec.get("adopted") or {}).get("from")),
          (json.load(open(os.path.join(PKG, ".claude-plugin", "plugin.json")))["version"], "Kgunn1977/assistant", old))
    check("the new copy's job names are its own", rec.get("jobs", [""])[0].startswith("Assistant live pass "), True)
    check("hidden runs' settings file written", os.path.isfile(os.path.join(nhome, "personal", "guard_settings.json")), True)
    readers = json.load(open(os.path.join(project, "Roadmap page", "readers.json"), encoding="utf-8"))["readers"]
    new_reader = "assistant " + hashlib.sha1(os.path.normcase(os.path.abspath(nhome)).encode("utf-8")).hexdigest()[:6]
    check("roadmap reader renamed, others left", sorted(readers), sorted([new_reader, "someone else"]))
    check("the old program folders are left as the way back", os.path.isdir(os.path.join(old, "System", "live")), True)
    # the way back
    kill(newl)
    r = via_shell([sys.executable, a, "adopt-back", "--root", new])
    check("the way back ends ok", r.returncode, 0)
    check("the way back: data home where it was", (os.path.isdir(home), os.path.exists(nhome)), (True, False))
    readers = json.load(open(os.path.join(project, "Roadmap page", "readers.json"), encoding="utf-8"))["readers"]
    check("the way back: roadmap reader name restored", old_reader in readers, True)
    oldl2 = subprocess.Popen([PYW, os.path.join(old, "System", "live_page", "listen.py")], cwd=os.path.join(old, "System", "live_page"))
    check("the way back: the old program serves the page again", serves(), 200)
    kill(oldl2)
    kill(oldl)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"downtime (old copy stopped by adopt, through the check pass, to the new page answering): {downtime:.1f} s")
    print(f"plan: {plan['same']} same, {plan['added']} new, {len(plan['yours'])} kept ({', '.join(plan['yours']) or 'none'}), {len(plan['differ'])} differ ({', '.join(plan['differ']) or 'none'})")
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    if "--old-root" not in sys.argv:       # it needs a copy of an owner's folder to stand in for; never run without one
        print("skipped: needs --old-root <an owner's folder holding System and Live>")
        sys.exit(0)
    i = sys.argv.index("--old-root")
    sys.exit(main(sys.argv[i + 1]))
