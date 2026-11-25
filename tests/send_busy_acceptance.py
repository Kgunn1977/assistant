r"""Acceptance (quick): a Send press while the store is busy is never refused as "already sent" (fault of 11/24: three emails
told to go during a check, two refused). On a scratch home.

  1. the store stays busy past the wait (connect raises TimeoutError): the line says the store is busy and nothing went out,
     and nothing was sent;
  2. the card's row is read and is done: the line still says "already sent or marked Done", and nothing was sent.

    python tests\send_busy_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


INSIDE = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common
assert os.path.abspath(common.HOME).startswith(os.path.abspath(sys.argv[2])), "not a scratch home: " + common.HOME
import db, items, answers, send
db.init_schema()
items.ensure()
iid, _ = items.upsert("live:ready-busytest", "p1", kind="task", area="Personal", title="Busy test draft", state="done", draft=None)
common.write_json(common.ITEMS_JSON, {"items": [{"id": iid, "source_key": "live:ready-busytest"}]})
sent = []
send.send_owner_email = lambda rec, item: (sent.append(1) or {"sent": True, "result": "Sent."})
out = {}
real = db.connect
def busy(*a, **k):
    raise TimeoutError("busy")
db.connect = busy
got = answers._owner_send({"id": iid})
out["busy"] = [got["result"], got["sent"], len(sent)]
db.connect = real
got = answers._owner_send({"id": iid})
out["done"] = [got["result"], got["sent"], len(sent)]
print(json.dumps(out))
'''


def main():
    tmp = tempfile.mkdtemp(prefix="send-busy-")
    live = os.path.join(PKG, "engine", "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, tmp], capture_output=True, text=True, env=env, timeout=300, encoding="utf-8")
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        check("the engine checks ran", (r.stdout + r.stderr).strip()[-3000:], "")
        got = {}
    if got:
        check("busy store: says busy, nothing went out", got["busy"],
              ["Not sent: I'm checking for messages right now, so nothing went out. Try again in a minute.", False, 0])
        check("done card: still says already sent", got["done"], ["Not sent: this email was already sent or marked Done.", False, 0])
    for name, ok, g, w in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {w!r}, got {g!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
