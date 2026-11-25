r"""Acceptance (quick): an email whose id changes at the service (Outlook's permanent ids, a move) keeps its stored row; the
new id becomes its current one. With an attachment pointing at the row (which made the database refuse to change the row's
id), the change, a move into a folder and finding it by either id all work, and the same email arriving under its new id is
not stored twice. On a scratch copy laid down from this plugin, made-up mail.

    python tests\mail_ids_acceptance.py
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
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import db
from connections import _store
ACC = "pat@work.example"
w = _store.MailWriter(ACC)
w.add("OLD-1", dt.datetime(2026, 11, 10, 9, 0), "in", "lee@acme.example", ACC, "Invoice", "Please see the invoice.", thread_id="t1",
      attachments=[("Invoice 77.pdf", b"%PDF-1.4 made up")], state={"unread": True, "inbox": True, "trashed": False, "labels": [], "cc": "",
      "from_name": "Lee", "header_id": "<m1@acme.example>", "refs": ""})
w.commit()
c = db.connect(read_only=True)
mid = c.execute("SELECT id FROM messages WHERE provider_id = 'OLD-1'").fetchone()[0]
pointed = c.execute("SELECT count(*) FROM attachments WHERE message_id = ?", [mid]).fetchone()[0]
c.close()
out = {"pointed at": pointed}
try:
    _store.remap_ids(ACC, [("OLD-1", "NEW-1")])
    _store.put_folders(ACC, [{"id": "F1", "path": "Inbox/Suppliers", "kind": "folder"}])
    _store.apply_states(ACC, [{"pid": "NEW-1", "state": {"inbox": False}, "folders": ["F1"]}])
    w = _store.MailWriter(ACC)
    w.add("NEW-1", dt.datetime(2026, 11, 10, 9, 0), "in", "lee@acme.example", ACC, "Invoice", "Please see the invoice.", thread_id="t1",
          attachments=[], state={"unread": False, "inbox": False, "trashed": False, "labels": [], "cc": "", "from_name": "Lee",
          "header_id": "<m1@acme.example>", "refs": ""})
    w.commit()
    c = db.connect(read_only=True)
    out.update({"row keeps its id": c.execute("SELECT provider_id FROM messages WHERE id = ?", [mid]).fetchone()[0],
                "current id": c.execute("SELECT provider_id FROM mail_state WHERE message_id = ?", [mid]).fetchone()[0],
                "in the folder": bool(c.execute("SELECT 1 FROM mail_folder_members WHERE message_id = ? AND folder_id = 'F1'", [mid]).fetchone()),
                "by either id": [_store.find_email(c, ACC, "NEW-1") == mid, _store.find_email(c, ACC, "OLD-1", also_old=True) == mid,
                               _store.find_email(c, ACC, "OLD-1") is None],
                "stored once": c.execute("SELECT count(*) FROM messages WHERE subject = 'Invoice'").fetchone()[0]})
    c.close()
except Exception as e:
    out["error"] = f"{type(e).__name__}: {str(e)[:200]}"
print(json.dumps(out))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="mailids-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_mailids", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47940", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        check("the email's row is pointed at by its attachment", o.get("pointed at"), 1)
        check("the id change and the move go through", o.get("error"), None)
        check("the row keeps the id it was stored under; the new one is its current id", (o.get("row keeps its id"), o.get("current id")), ("OLD-1", "NEW-1"))
        check("it is in the folder it moved to; found by its new id, and by its old one only where asked (a state for the old id is not applied)", (o.get("in the folder"), o.get("by either id")), (True, [True, True, True]))
        check("the same email arriving under its new id is not stored twice", o.get("stored once"), 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
