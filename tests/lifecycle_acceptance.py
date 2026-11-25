r"""Acceptance of a copy's life, from the built package, on a scratch folder: lay down, a pass, an update that fails
half way and one that goes through, uninstall. No scheduled job is made; nothing outside the scratch folder changes.

    python tests\lifecycle_acceptance.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def tree(d):
    h = hashlib.sha256()
    for f, dirs, n in sorted(os.walk(d)):
        dirs.sort()
        for x in sorted(n):
            if not x.endswith(".pyc"):
                h.update(x.encode() + open(os.path.join(f, x), "rb").read())
    return h.hexdigest()[:16]


def main():
    tmp = tempfile.mkdtemp(prefix="life-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home = os.path.join(root, "Live")
    sys.path.insert(0, os.path.join(PKG, "hooks"))
    import assistant_copy
    check("working copy made", assistant_copy.sync(data), True)
    a = os.path.join(data, "scripts", "assistant.py")

    def run(*args):
        r = subprocess.run([sys.executable, a, *args, "--root", root], capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()

    check("lay-down", run("lay-down", "--port", "47895", "--sending", "no")[0], 0)
    shipped = json.load(open(os.path.join(root, "Shipped", "shipped.json"), encoding="utf-8"))
    bad = [r for r, h in shipped["files"].items()
           if hashlib.sha256(open(os.path.join(root, r), "rb").read().replace(b"\r\n", b"\n")).hexdigest() != h]
    check(f"laid-down files match the shipped checksums ({len(shipped['files'])} files)", bad, [])
    rec = json.load(open(os.path.join(home, "personal", "install.json"), encoding="utf-8"))
    check("install record: version and repository", (rec.get("version"), rec.get("repo")), (shipped["version"], "Kgunn1977/assistant"))
    check("the manual is laid down beside the program", os.path.isfile(os.path.join(root, "docs", "Assistant manual.html")), True)
    ver = json.load(open(os.path.join(PKG, ".claude-plugin", "plugin.json"), encoding="utf-8"))["version"]
    check("the manual names the version from plugin.json", f"<span data-version>For version {ver}, </span>Windows only" in
          open(os.path.join(root, "docs", "Assistant manual.html"), encoding="utf-8").read(), True)
    check("the shipped list carries the version from plugin.json", shipped["version"], ver)
    # the page's build takes the roadmap page from the plugin, and only from there
    laid_rm = os.path.join(root, "System", "live_page", "roadmap.html")
    check("the plugin's roadmap page is laid down beside the page's build",
          os.path.isfile(laid_rm) and open(laid_rm, "rb").read() == open(os.path.join(PKG, "page", "roadmap.html"), "rb").read(), True)
    env_b = {k: v for k, v in os.environ.items() if k != "ROADMAP_PAGE_SOURCE"}
    env_b["ASSISTANT_LIVE_HOME"] = home
    r = subprocess.run([sys.executable, os.path.join(root, "System", "live_page", "build_site.py")], capture_output=True, text=True,
                       env=env_b, cwd=tmp)          # the rebuild a program change runs
    js = open(os.path.join(root, "System", "live_page", "site", "app", "app.js"), encoding="utf-8").read()
    check("a rebuild after a program change draws the plugin's roadmap page", (r.returncode, "window.RM_SRC = null" not in js), (0, True))
    plan = json.loads(run("update-plan")[1] or "{}")
    check("the laid-down roadmap page is never the owner's change", (plan.get("yours"), plan.get("conflict")), ([], []))
    check("the hidden runs' settings file is written", os.path.isfile(os.path.join(home, "personal", "guard_settings.json")), True)
    r = subprocess.run([sys.executable, os.path.join(root, "System", "live", "pass.py")], capture_output=True, text=True,
                       env=dict(os.environ, ASSISTANT_LIVE_HOME=home), timeout=600)
    last = (json.load(open(os.path.join(home, "health.json"), encoding="utf-8")).get("last_pass") or {}).get("outcome")
    check("a pass ends ok", (r.returncode, last), (0, "ok"))
    # an update that fails half way puts everything back; then a clean one keeps the owner's own change
    sj = os.path.join(root, "Shipped", "shipped.json")
    d = json.load(open(sj, encoding="utf-8"))
    d["version"] = "0.0.9"
    json.dump(d, open(sj, "w", encoding="utf-8"))
    # the page's built files were remade here and differ from both the old and the new shipped ones: never a question
    app = os.path.join("System", "live_page", "site", "app")
    for n in ("manifest.json", "app.js"):
        open(os.path.join(root, "Shipped", app, n), "w", encoding="utf-8").write("as an older version shipped it")
        open(os.path.join(root, app, n), "w", encoding="utf-8").write("as this computer's rebuild made it")
    target = os.path.join(root, "System", "live", "items.py")
    open(target, "a", encoding="utf-8").write("\n# the owner's own change\n")
    before = (tree(os.path.join(root, "System")), tree(os.path.join(root, "Shipped")))
    ch = os.path.join(tmp, "choices.json")
    json.dump({"System/live/items.py": os.path.join(tmp, "missing.py")}, open(ch, "w"))
    code, out = run("update-apply", "--choices", ch)
    check("an update failing half way: refused and put back exactly",
          (code, before == (tree(os.path.join(root, "System")), tree(os.path.join(root, "Shipped")))), (1, True))
    json.dump({"System/live/items.py": "mine"}, open(ch, "w"))
    code, out = run("update-apply", "--choices", ch)
    check("a clean update the same day goes through", code, 0)
    check("the owner's own change is kept", "the owner's own change" in open(target, encoding="utf-8").read(), True)
    try:
        made = json.load(open(os.path.join(root, app, "manifest.json"), encoding="utf-8"))
    except ValueError:
        made = {}
    check("the page's built files are remade by the update, not asked about",
          (sorted(made), "rebuild" in open(os.path.join(root, app, "app.js"), encoding="utf-8").read()[:60]),
          (sorted(["app.css", "app.js", "shell.html", "login.css", "login.js", "index.php"]), False))
    # uninstall
    code, out = run("uninstall", "--remove-data")
    check("uninstall", code, 0)
    check("nothing left of the copy", os.path.exists(root), False)
    roots = json.load(open(os.path.join(data, "roots.json"), encoding="utf-8")).get("roots")
    check("the copy is off the hooks' list", roots, [])
    shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
