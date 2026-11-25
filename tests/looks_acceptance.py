r"""Acceptance of the page's styles (Workshop, Broadsheet and the fifteen new ones) (Settings, How the page looks, Style). On a scratch copy laid down from this
plugin: each style is saved and reaches the page's data; the laid-down page carries every style, and hands the chosen
one to a connected roadmap; the styles' pictures (docs\looks) stay with the plugin and are never installed.
Nothing outside the scratch folder changes; the page itself is not drawn here.

    python tests\looks_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
LOOKS = ("glass", "workshop", "broadsheet",
         "dense", "expressive", "tiles", "paper", "retro", "soft", "panel", "starship", "terminal", "greenscreen", "grid", "frost",
         "monolith", "haze")
results = []

INSIDE = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import settings_page
out = {}
_f = settings_page.for_page()["page"]
fb = [_f["look"], _f["theme"]]
for look in json.loads(sys.argv[2]):
    ok, _said = settings_page.save({"settings": {"group": "page", "values": {"look": look}}})
    out[look] = [ok, settings_page.for_page()["page"]["look"]]
settings_page._write("page", {"look": "studio", "theme": "light"})
_f = settings_page.for_page()["page"]
out["fallback"] = fb + [_f["look"], _f["theme"]]
out["unknown"] = settings_page.save({"settings": {"group": "page", "values": {"look": "neon"}}})[0]
print(json.dumps(out))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="looks-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_looks", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        check("the plugin keeps the styles' pictures", os.path.isdir(os.path.join(PKG, "docs", "looks")), True)
        copier.sync(data)
        check("the working copy leaves them out", os.path.exists(os.path.join(data, "docs", "looks")), False)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47905", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        check("the laid-down manual is there, the pictures are not", (os.path.isfile(os.path.join(root, "docs", "Assistant manual.html")),
              os.path.exists(os.path.join(root, "docs", "looks"))), (True, False))
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, json.dumps(LOOKS)], capture_output=True, text=True, env=env, timeout=120)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr[-400:]}
        if "error" in got: print(got["error"])
        check("each style is saved and reaches the page's data", {k: got.get(k) for k in LOOKS}, {k: [True, k] for k in LOOKS})
        check("the picker lists 17 styles, Glass first", (len(LOOKS), LOOKS[0]), (17, "glass"))
        check("a saved removed style and a new setup both open Glass dark", got.get("fallback"), ["glass", "dark", "glass", "dark"])
        check("a style that does not exist is refused", got.get("unknown"), False)
        app = os.path.join(root, "System", "live_page", "site", "app")
        css = open(os.path.join(app, "app.css"), encoding="utf-8").read()
        js = open(os.path.join(app, "app.js"), encoding="utf-8").read()
        check("the page carries every style", [x for x in LOOKS if f'html[data-look="{x}"]' not in css], [])
        check("the removed styles are gone", [x for x in ("studio", "midnight", "poster", "chartroom", "classic", "calm", "ledger", "hearth", "contrast") if f'html[data-look="{x}"]' in css], [])
        check("the roadmap is built into the page", "window.RM_SRC = null" in js, False)
        check("a connected roadmap gets the chosen style", ("html[data-look]{--look-bg" in css,
              "hst.setAttribute('data-look', l)" in js, "root.adoptedStyleSheets = [sheet, rmLookSheet()]" in js), (True, True, True))
        subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "uninstall", "--remove-data", "--root", root],
                       capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got_, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got_!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
