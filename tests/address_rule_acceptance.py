r"""Acceptance: a person's address is looked for before the owner is asked (people.py, ready.make), on a scratch copy with made-up mail.

- A draft that names a person whose address is only in an older gathered email (they wrote once; the owner never answered, so
  they are not a contact) uses that address, does not ask, and says where it was found.
- A question for the owner about that person's address is dropped, and the line that replaces it says where it was found.
- Someone whose address is nowhere on file is still asked about, in plain words, and no email is put on the page.
Nothing outside the scratch folder changes.

    python tests\address_rule_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []

INSIDE = r'''
import datetime as dt, json, os, sys
live = sys.argv[1]
sys.path.insert(0, live)
import common, db, people, ready, voice
from connections import _store
voice._claude = lambda prompt: (None, "not in this test", 0, {})     # the humanize pass is not what this test is about
w = _store.MailWriter("me@one.example")
w.add("old1", dt.datetime(2026, 9, 3, 10, 0), "in", "jamie.lee@bakery.example", "me@one.example", "Rye order", "Can you send the rye order form?",
      thread_id="b1", attachments=[], state={"unread": False, "inbox": True, "trashed": False, "labels": [], "cc": "", "from_name": "Jamie Lee",
                                             "header_id": "<old1@bakery.example>", "refs": ""})
w.commit()
people.write_people()
out = {}
iid, said = ready.make({"type": "draft", "kind": "new", "to": ["Jamie Lee"], "subject": "Rye order form", "body": "Hi Jamie, the form is attached."},
                       dt.datetime.now(), 1, "ar")
c = db.connect(read_only=True)
row = c.execute("SELECT draft, why FROM live_items WHERE id = ?", [iid]).fetchone() if iid else None
c.close()
d = json.loads(row[0]) if row else {}
out["draft"] = {"made": bool(iid), "said": said, "to": d.get("to"), "why": row[1] if row else None}
keep, found, _used = people.settle_asks(["What is Jamie Lee's email address?"])
out["ask"] = {"kept": keep, "found": found}
iid2, said2 = ready.make({"type": "draft", "kind": "new", "to": ["Morgan Hale"], "subject": "Hello", "body": "Hi Morgan."}, dt.datetime.now(), 2, "ar")
out["not on file"] = {"made": bool(iid2), "said": said2}
print(json.dumps(out, default=str))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="address-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_address", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47927", "--sending", "no", "--root", root],
                           capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o = {}
            check("the checks ran", r.stderr.strip()[-2000:], "")
        d = o.get("draft") or {}
        check("a draft naming a person whose address is only in an older email uses it and does not ask",
              [d.get("made"), d.get("said"), d.get("to")], [True, "", ["jamie.lee@bakery.example"]])
        check("... and says where the address was found", "Jamie Lee's address, jamie.lee@bakery.example, is from their email of 9/3/26." in (d.get("why") or ""), True)
        check("a question about that address is not asked; what replaces it says where it was found",
              o.get("ask"), {"kept": [], "found": ["Jamie Lee's email is on file: jamie.lee@bakery.example (found in their email of 9/3/26)."]})
        check("someone not on file anywhere is asked about in plain words, and nothing is put on the page",
              o.get("not on file"), {"made": False, "said": "I did not put one email on your page: I need Morgan Hale's email address and it isn't on file. What is it?"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
