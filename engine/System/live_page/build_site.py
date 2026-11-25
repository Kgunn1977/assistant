r"""Make the site's page files from page.html, and (with --keys) the one-time keys.

    python build_site.py            writes site\app\app.css, app.js and shell.html from page.html
    python build_site.py --keys     also makes a new feed key and a one-time setup code:
                                    the feed key goes into local_settings.json (never shown),
                                    their hashes go into the home's page_state\site_config.php for upload to
                                    data\config.php in the page's folder on the site, and the setup address is printed once.

Every run also writes the site's access file for this owner into the home's page_state\site\.htaccess:
site\.htaccess here is the general one, and the folder the page lives in comes from the owner's page address.

page.html stays the one source of the page; the site copy only swaps where its data comes from
(site\app\store.js, put in front of the page's own script).
"""
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
APP = os.path.join(SITE, "app")
ROADMAP_PAGE = os.path.join(HERE, "roadmap.html")       # the plugin's roadmap page, as the plugin last laid it down here
def site_url():
    """The page's address: given after --keys, else the one already in the personal folder."""
    given = [a for a in sys.argv[1:] if a.startswith("https://")]
    if given:
        return given[0].rstrip("/")
    home = os.environ.get("ASSISTANT_LIVE_HOME") or os.path.join(os.path.dirname(os.path.dirname(HERE)), "Live")
    try:
        with open(os.path.join(home, "personal", "local_settings.json"), encoding="utf-8") as f:
            return str(json.load(f)["site"]).rstrip("/")
    except (OSError, ValueError, KeyError):
        raise SystemExit("give the page's address after --keys, for example: python build_site.py --keys https://example.com/page")


def page_state():
    home = os.environ.get("ASSISTANT_LIVE_HOME") or os.path.join(os.path.dirname(os.path.dirname(HERE)), "Live")
    return os.path.join(home, "page_state")


def access_file():
    """The site's access file for this owner: the general one with the folder their page lives in, taken from
    their page address. Written to the home, ready to upload; nothing about the owner stays in this folder."""
    from urllib.parse import urlparse
    try:
        folder = "/" + urlparse(site_url()).path.strip("/")
    except SystemExit:
        return None             # no page address yet: first-time setup makes it
    folder = folder if folder.endswith("/") else folder + "/"
    with open(os.path.join(SITE, ".htaccess"), encoding="utf-8", newline="") as f:
        text = f.read().replace("{PAGE_FOLDER}", folder)
    out = os.path.join(page_state(), "site", ".htaccess")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return out


GUARD = "<?php http_response_code(404); exit; ?>\n"
RESET = "body{margin:0}\n[hidden]{display:none!important}\nimg{max-width:100%}\n"


REPO_ROADMAP_PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "page", "roadmap.html")   # the plugin repo's own copy, when this folder is inside a checkout of it


def roadmap_source():
    """The plugin's own roadmap page, read only: the one source of how a roadmap looks and works. Looked for in order:
    ROADMAP_PAGE_SOURCE, the copy the plugin lays down here (ROADMAP_PAGE, put by assistant.py), then the repo's own
    page/roadmap.html (so any checkout of the repo, a worktree included, builds the same page). Stops the build when none
    exists: a page without its roadmap must never be built silently."""
    for path in (os.environ.get("ROADMAP_PAGE_SOURCE"), ROADMAP_PAGE, REPO_ROADMAP_PAGE):
        if path and os.path.isfile(path):
            return path
    raise SystemExit("the roadmap page was not found (looked at ROADMAP_PAGE_SOURCE, " + ROADMAP_PAGE + ", " + REPO_ROADMAP_PAGE + "); the page is not built without it")


def roadmap_parts(path):
    """Its style, markup and script, as they are, with only the changes that let it live in a shadow root of the live page:
    :root and body selectors become :host, and its script runs against a stand-in document (see page.html, "the roadmap").
    Anything the stand-in does not cover stops the build, so the plugin page and the live page cannot drift apart unseen."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    css = re.search(r"<style>(.*?)</style>", src, re.S)
    js = re.search(r"<script>(.*?)</script>", src, re.S)
    if not css or not js:
        raise SystemExit("the roadmap page no longer has one style block and one script block; the live page must be changed first")
    body = src[css.end():src.index("<script>")].strip()
    css = css.group(1)
    css = css.replace(':root[data-theme="dark"]', ':host([data-theme="dark"])').replace(':root:not([data-theme="light"])', ':host(:not([data-theme="light"]))')
    css = re.sub(r"(^|[\s{}])body\s*\{", lambda m: m.group(1) + ":host {", css)
    css = re.sub(r"(^|[\s{}]):root\s*\{", lambda m: m.group(1) + ":host {", css)
    left = re.findall(r"(?:^|[\s{},])(?::root|html|body)\b[^{]*\{", css)
    if left:
        raise SystemExit("the roadmap page's style has a selector the live page does not translate: " + left[0].strip())
    js = js.group(1)
    # what the script may use of the page around it; each is answered by the stand-in document and storage
    allowed = {"document.getElementById", "document.createElement", "document.createTextNode", "document.activeElement",
               "document.querySelector", "document.addEventListener"}
    used = set(re.findall(r"\bdocument\.[A-Za-z]+", js))
    if used - allowed:
        raise SystemExit("the roadmap page now uses " + ", ".join(sorted(used - allowed)) + ", which the live page does not yet stand in for")
    code = re.sub(r"//[^\n]*", "", js)
    code = re.sub(r'"(?:\\.|[^"\\\n])*"' + r"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`", '""', code)     # words inside quotes are text, not the page's globals
    if re.search(r"""(?<![.\w"'])(window|location|history|sessionStorage)\b(?!\s*:)""", code):     # navigator is the same browser's in both pages (the roadmap's Copy)
        raise SystemExit("the roadmap page now uses window, location, history or sessionStorage, which the live page does not yet stand in for")
    if re.search(r"""[\s'"]on[a-z]+\s*=|\bstyle\s*=\s*\\?["']""", body):
        raise SystemExit("the roadmap page's markup now carries an inline handler or style, which the live page's rules would ignore")
    return css, body, js


def roadmap_js():
    path = roadmap_source()
    if not path:
        return "window.RM_SRC = null;\n"
    css, body, js = roadmap_parts(path)
    return ("window.RM_SRC = " + json.dumps({"css": css, "body": body}) + ";\n"
            "window.RM_RUN = function (document, localStorage, claude) {\n" + js.strip("\n") + "\n};\n")


MADE = ("app.css", "app.js", "shell.html", "manifest.json")   # the files build() makes in site/app, remade on each computer


def build():
    with open(os.path.join(HERE, "page.html"), encoding="utf-8") as f:
        page = f.read()
    css = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
    js = re.search(r"<script>(.*?)</script>", page, re.S).group(1)
    shell = page[page.index('<div class="wrap">'):page.index("<script>")].strip()
    with open(os.path.join(APP, "store.js"), encoding="utf-8") as f:
        store = f.read()
    for name, text in (("app.css", RESET + css.strip() + "\n"), ("app.js", store + roadmap_js() + js.strip() + "\n"),
                       ("shell.html", shell + "\n")):
        with open(os.path.join(APP, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    with open(os.path.join(APP, "app.js"), encoding="utf-8") as f:
        built = f.read()
    for part in ("window.RM_SRC = {", "window.RM_RUN = function", js.strip()[:200]):   # the store, the roadmap and the page's own script must all be in
        if part not in built:
            raise SystemExit("the built app.js is missing an expected part: " + part[:40])
    listed = {}
    for name in ("app.css", "app.js", "shell.html", "login.css", "login.js", "index.php"):
        path = os.path.join(SITE if name == "index.php" else APP, name)
        with open(path, encoding="utf-8") as f:
            listed[name] = hashlib.sha256(f.read().replace("\r", "").encode("utf-8")).hexdigest()
    with open(os.path.join(APP, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(listed, f, indent=1)
    if "style=" in shell or re.search(r"style=\\?[\"']", js):
        print("warning: an inline style is left in the page; the site's rules will ignore it")
    print("site page files written")


def keys():
    site = site_url()
    feed_key = secrets.token_urlsafe(48)
    setup = secrets.token_urlsafe(32)
    personal = os.path.join(os.environ.get("ASSISTANT_LIVE_HOME") or os.path.join(os.path.dirname(os.path.dirname(HERE)), "Live"), "personal")
    os.makedirs(personal, exist_ok=True)
    with open(os.path.join(personal, "local_settings.json"), "w", encoding="utf-8") as f:
        json.dump({"site": site, "feed_key": feed_key}, f, indent=1)
    cfg = {"feed_key": hashlib.sha256(feed_key.encode()).hexdigest(),
           "setup": {"hash": hashlib.sha256(setup.encode()).hexdigest(),
                     "exp": int((dt.datetime.now() + dt.timedelta(days=7)).timestamp())}}
    os.makedirs(page_state(), exist_ok=True)
    with open(os.path.join(page_state(), "site_config.php"), "w", encoding="utf-8", newline="\n") as f:
        f.write(GUARD + json.dumps(cfg))
    print("feed key saved to local_settings.json (not shown); hashes are in the home's page_state\\site_config.php")
    print(f"one-time setup address, good for 7 days, for the owner only: {site}/setup#{setup}")


if __name__ == "__main__":
    build()
    access_file()
    if "--keys" in sys.argv:
        keys()
