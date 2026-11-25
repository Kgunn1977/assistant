r"""Acceptance (quick): pictures the day-by-day replay stored are not owed a description, and new texted pictures still are;
a check describes at most one batch, and only after leaving time for judging and the cards. On a scratch copy laid down from
this plugin; no Claude run.

    python tests\describe_backlog_acceptance.py
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
import datetime as dt, json, os, subprocess, sys
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import common, db, gather, think, limits, describe_images, ai_steps
out = {}
now = dt.datetime.now()
yesterday = (now - dt.timedelta(days=1)).date()
con = db.connect()
def picture(tag, ts):
    mid = con.execute("INSERT INTO messages (channel, account, thread_id, ts, direction, from_key, to_keys, body, ingested_at)"
                      " VALUES ('sms', 'phone', ?, ?, 'in', 'sms:+15550001111', '[]', '[image]', ?) RETURNING id", (tag, ts, now)).fetchone()[0]
    att = con.execute("INSERT INTO attachments (message_id, original_filename, saved_filename, saved_path) VALUES (?,?,?,?) RETURNING id",
                      (mid, tag + ".jpg", tag + ".jpg", tag + ".jpg")).fetchone()[0]
    doc = con.execute("INSERT INTO documents (message_id, attachment_id, doc_type, created_at) VALUES (?,?, 'image', ?) RETURNING id",
                      (mid, att, now)).fetchone()[0]
    con.execute("INSERT INTO pages (document_id, page_no, method, text) VALUES (?, 1, 'needs_vision', '')", (doc,))
for i in range(30):                                   # the rebuilt days' pictures
    picture(f"old{i}", dt.datetime.combine(yesterday, dt.time(1)) - dt.timedelta(days=1 + i % 20))
con.close()
out["before any replay"] = gather.texted_images_waiting()
common.write_json(os.path.join(common.paths.STATE, "replay", "state.json"), {"last_done": yesterday.isoformat(), "finished_at": now.isoformat()})
out["after the replay"] = [gather.texted_images_waiting(), len(describe_images.pending())]
con = db.connect()
cutoff = dt.datetime.combine(yesterday + dt.timedelta(days=1), dt.time())     # the replay's days end at today's midnight
for i in range(12):                                   # pictures texted since the replay ended: after the cutoff at any hour
    picture(f"new{i}", cutoff + dt.timedelta(seconds=i))
con.close()
out["new pictures"] = [gather.texted_images_waiting(), len(describe_images.pending())]
pend = describe_images.pending()
out["only new ones queued"] = all(str(r[2]).startswith("new") for r in pend)
r = subprocess.run([sys.executable, os.path.join(live, "core", "describe_images.py"), "--json", "--batch-size", "9", "--limit", "9"],
                   capture_output=True, text=True, cwd=live)
out["a check's cap"] = json.loads(r.stdout)["total"]
out["cap is set"] = ai_steps.DESCRIBE_MOST
print(json.dumps(out))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="descbacklog-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_descbacklog", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47938", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=300)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        if "error" in o:
            print(o["error"])
        check("with no replay, every texted picture is owed a description", o.get("before any replay"), 30)
        check("after the replay, the pictures it stored are not waiting or queued", o.get("after the replay"), [0, 0])
        check("pictures texted since still are", o.get("new pictures"), [12, 12])
        check("... and only those are queued", o.get("only new ones queued"), True)
        check("a check queues at most one batch of nine", [o.get("a check's cap"), o.get("cap is set")], [9, 9])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
