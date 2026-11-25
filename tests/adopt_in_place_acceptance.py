r"""Acceptance of adopt "where it is now": the assistant stays in its folder and only its program is replaced.

    python tests\adopt_in_place_acceptance.py --old-root "<the owner's folder holding System and Live>"

Same stand-in as adopt_acceptance.py (made safe by make_standin.py, in a scratch folder under %TEMP%, no jobs), then:
the old program serves the page; adopt with the same folder as old and new; the program is the plugin's, the data is
where it was and unchanged, the page serves; the way back puts the old program back byte for byte. Removed after.
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
PORT = 47898
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
results = []


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
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for x in sorted(n):
            if not x.endswith(".pyc"):
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


def run(old_root, tmp):
    subprocess.run([sys.executable, os.path.join(HERE, "make_standin.py"), old_root, tmp, str(PORT)], check=True, capture_output=True)
    old = os.path.join(tmp, "ClaudeOS stand-in")
    home = os.path.join(old, "Live")
    data = os.path.join(tmp, "plugin-data")
    sys.path.insert(0, os.path.join(PKG, "hooks"))
    import assistant_copy
    assistant_copy.sync(data)
    a = os.path.join(data, "scripts", "assistant.py")
    page = os.path.join(old, "System", "live_page")
    oldl = subprocess.Popen([PYW, os.path.join(page, "listen.py")], cwd=page)
    check("before: the old program serves the page", serves(), 200)
    before_prog = {p: digest(os.path.join(old, "System", p)) for p in ("live", "live_page")}
    rec_path = os.path.join(home, "personal", "install.json")
    before_rec = open(rec_path, "rb").read() if os.path.exists(rec_path) else None   # an earlier copy may already have one
    kept = {k: digest(os.path.join(home, *k.split("/"))) for k in
            ("Resources/Rules", "personal/settings.json", "personal/personal.json", "page_state/local_site/config.json")}
    plan = json.loads(subprocess.run([sys.executable, a, "adopt-plan", "--from", old, "--root", old], capture_output=True, text=True).stdout)
    ch = os.path.join(home, "state", "adopt-choices.json")           # inside the data folder, as the real run had it
    json.dump({rel: "new" for rel in plan["differ"]}, open(ch, "w"))
    t0 = time.time()
    r = via_shell([sys.executable, a, "adopt", "--from", old, "--root", old, "--choices", ch, "--no-jobs"])
    check("adopt where it is now ends ok", r.returncode, 0)
    out_text = (r.stdout + r.stderr).strip()
    check("adopt printed what it did (never silent)", bool(out_text), True)
    if r.returncode:
        for name, ok, got, want in results:
            print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
        print("adopt said: " + (out_text[-600:] or "(nothing)"))
        print(f"{sum(x[1] for x in results)} of {len(results)} passed (stopped: adopt failed)")
        return 1
    if r.returncode:
        print(r.stdout + r.stderr)
    after = {k: digest(os.path.join(home, *k.split("/"))) for k in kept}
    newl = subprocess.Popen([PYW, os.path.join(page, "listen.py")], cwd=page)
    check("after: the page serves from the same place", serves(), 200)
    downtime = time.time() - t0
    shipped = json.load(open(os.path.join(old, "Shipped", "shipped.json"), encoding="utf-8"))["files"]
    bad = [rel for rel, h in shipped.items() if rel not in plan["yours"]
           and hashlib.sha256(open(os.path.join(old, rel), "rb").read().replace(b"\r\n", b"\n")).hexdigest() != h]
    check("the program is now the plugin's, file for file", bad, [])
    check("the data stayed where it was", os.path.isdir(home), True)
    check("rules, settings, who you are and the page's password unchanged", after, kept)
    check("Shipped, docs and the install record written", (os.path.isdir(os.path.join(old, "Shipped")),
          os.path.isfile(os.path.join(old, "docs", "Assistant manual.html")),
          (json.load(open(os.path.join(home, "personal", "install.json"))).get("adopted") or {}).get("in_place")), (True, True, True))
    check("the check pass ended ok", (json.load(open(os.path.join(home, "health.json"))).get("last_pass") or {}).get("outcome"), "ok")
    subprocess.run(["taskkill", "/PID", str(newl.pid), "/T", "/F"], capture_output=True)
    r = via_shell([sys.executable, a, "adopt-back", "--root", old])
    check("the way back ends ok", r.returncode, 0)
    check("the old program is back byte for byte", {p: digest(os.path.join(old, "System", p)) for p in ("live", "live_page")}, before_prog)
    after_rec = open(rec_path, "rb").read() if os.path.exists(rec_path) else None
    check("Shipped and docs taken away, the install record back as it was before",
          (os.path.exists(os.path.join(old, "Shipped")), os.path.exists(os.path.join(old, "docs")), after_rec == before_rec),
          (False, False, True))
    oldl2 = subprocess.Popen([PYW, os.path.join(page, "listen.py")], cwd=page)
    check("the way back: the old program serves the page again", serves(), 200)
    for p in (oldl, oldl2):
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"downtime (old stopped, program replaced, check pass, page answering): {time.time() and downtime:.1f} s")
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


def main(old_root):
    tmp = tempfile.mkdtemp(prefix="adopt-here-")
    try:
        return run(old_root, tmp)
    finally:
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains('"
              + tmp.lower() + "') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
        time.sleep(1)
        _cleanup.remove(tmp)
        print(f"scratch removed: {not os.path.exists(tmp)}")


if __name__ == "__main__":
    if "--old-root" not in sys.argv:       # it needs a copy of an owner's folder to stand in for; never run without one
        print("skipped: needs --old-root <an owner's folder holding System and Live>")
        sys.exit(0)
    sys.exit(main(sys.argv[sys.argv.index("--old-root") + 1]))
