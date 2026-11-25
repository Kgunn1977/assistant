r"""Acceptance: the chat panel of the Texts part (fixed-height panel, list left, conversation right), which a part a mod brings
can use too (an addition's own test covers its part).

- The page's door gives a long thread in pages: the texts thread door takes a limit (a longer window brings older texts).
- The page is built as a panel: the Texts part is closed before the next part begins, the panel is one fixed height of about 70%
  of the window, each side scrolls by itself, a phone shows list or conversation with a Back button, and the part is drawn
  through the panel's parts, never by replacing the whole part.
- Opening a conversation highlights it at once and keeps the one on show until the new one has arrived.
- The dead-pointer check passes (every message that points somewhere names something that exists).

The look and the scroll behaviour are proved in a browser against tests\chat_panels_server.py (300-message threads, 2 second answers).

    python tests\chat_panels_acceptance.py
"""
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SYS = os.path.join(PKG, "engine", "System")
tmp = tempfile.mkdtemp(prefix="chatpanels-test-")
os.environ["ASSISTANT_LIVE_HOME"] = os.path.join(tmp, "Live")
os.makedirs(os.path.join(tmp, "Live", "personal"))
with open(os.path.join(tmp, "Live", "personal", "settings.json"), "w") as f:
    json.dump({"page_port": 47935}, f)
sys.path.insert(0, os.path.join(SYS, "live"))
sys.path.insert(0, os.path.join(SYS, "live_page"))
import texts  # noqa: E402

results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


# the texts thread door takes a limit
LIMITS = []
texts.thread = lambda conv, limit=200, before="": LIMITS.append(limit) or {"ok": True, "id": conv, "messages": [], "more": False}
import local_site  # noqa: E402
srv = local_site.start()
tok, csrf = secrets.token_urlsafe(48), secrets.token_hex(32)
with local_site.changed:
    local_site._save("sessions", {hashlib.sha256(tok.encode()).hexdigest(): {"made": int(time.time()), "seen": int(time.time()), "exp": int(time.time()) + 3600, "len": 3600, "csrf": csrf}})
port = srv.server_address[1]


def door(path):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"Cookie": f"{local_site.cookie_name()}={tok}", "Host": f"127.0.0.1:{port}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


codes = [door("/api/texts/thread?id=p1&limit=50"), door("/api/texts/thread?id=p1&limit=100"), door("/api/texts/thread?id=p1"),
         door("/api/texts/thread?id=p1&limit=1"), door("/api/texts/thread?id=p1&limit=99999"), door("/api/texts/thread?id=p1&limit=abc")]
check("the texts thread door gives a page of the newest, a longer window for older ones, is clamped, and keeps its old default", [codes, LIMITS], [[200] * 6, [50, 100, 200, 20, 5000, 200]])
srv.shutdown()

# the page
page = open(os.path.join(SYS, "live_page", "page.html"), encoding="utf-8").read()
sec_t, sec_s = page.index('id="sec-texts"'), page.index('id="sec-calendar"')
check("the Texts part is closed before the next part begins", "</section>" in page[sec_t:sec_s], True)
css = re.search(r"\.cp-body\{[^}]*\}", page).group(0)
check("the panel is one fixed height of about 70% of the window, with a 360px list left and the conversation right", [
    "height:70vh" in css, "grid-template-columns:360px minmax(0,1fr)" in css, "overflow:hidden" in css], [True, True, True])
check("the list and the messages each scroll by themselves", [bool(re.search(r"\.cp-lscroll\{[^}]*overflow-y:auto", page)), bool(re.search(r"\.cp-msgs,\.cp-alt\{[^}]*overflow-y:auto", page))], [True, True])
check("on a phone the list and the conversation take turns, with a Back button", [
    ".cp:not(.cp-open) .cp-conv{display:none}" in page, ".cp.cp-open .cp-list{display:none}" in page, ".cp-back{display:inline-flex}" in page], [True, True, True])
for name, fn in (("Texts", "renderTexts"),):
    i = page.index("function %s() {" % fn)
    body = page[i:page.index("\n  }\n", i)]
    check("%s is drawn through the panel's parts, never by replacing the whole part" % name,
          ["cpMake(" in body, "cpSync(" in body, "cpList(" in body, "setHtml(box, o)" in body], [True, True, True, False])
# opening: highlight at once, the one on show stays until the new one arrives
for name, fn, shown in (("Texts", "txOpen", "t.shown"),):
    i = page.index("function %s(" % fn)
    body = page[i:page.index("\n  }\n", i)]
    first_render = re.search(r"renderTexts\(\);", body)
    pre = body[:first_render.start()] if first_render else body
    check("%s: pressing a conversation selects it and shows a loading line before anything is fetched, and keeps the one on show" % name,
          [("s.cur = id" in pre) or ("t.open = id" in pre), "Opening" in pre, shown + " = " not in pre], [True, True, True])
check("older messages load in pages as the conversation is scrolled up, and new ones wait behind a tag", [
    "p.msgs.addEventListener('scroll'" in page, "sc.scrollTop < 120 && p.more && p.onOlder" in page, "new messages" in page, "'1 new message'" in page], [True, True, True, True])

check("rows have round avatars, a relative time, a pin and a bold unread name; bubbles bundle by sender within five minutes with a date line after an hour", [
    "function cpRow(" in page, "function cpRel(" in page, "m.d - q.d >= 3600000" in page, "m.d - q.d > 300000" in page, ".cp-row.unread .cp-rname" in page, "cp-pin" in page], [True] * 6)
check("his own bubbles use the accent colour on the right and others the grey on the left, in both colour schemes through the page's own variables", [
    ".cp-m.out .cp-bub{background:var(--accent)" in page, ".cp-bub{" in page and "background:var(--sunk)" in page, "#" + "fff" not in re.search(r"\.cp-bub\{[^}]*\}", page).group(0)], [True, True, True])

# the dead-pointer check
r = subprocess.run([sys.executable, os.path.join(HERE, "pointers_check.py")], capture_output=True, text=True)
check("no message on the page points at something that does not exist", [r.returncode, r.stdout.strip()[:200]], [0, ""])

import _cleanup  # noqa: E402
_cleanup.remove(tmp, wait=5)            # the scratch home goes when the test ends
bad = [x for x in results if not x[1]]
for name, ok, got, want in results:
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        print("   got ", got, "\n   want", want)
print("\n%d of %d passed" % (len(results) - len(bad), len(results)))
sys.exit(1 if bad else 0)
