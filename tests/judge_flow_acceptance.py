r"""Acceptance (quick): the judge step gets through a backlog without losing or stalling what it owes. On a scratch copy laid
down from this plugin, with 150 made-up texts; no Claude run (the Claude steps are stood in for).

- The judging payload for 150 messages opens the database a handful of times, not once per message (each open of a large
  home's database costs about a second: on 11/22/26 a 146-message payload took 210 s, and the pass cut it off).
- A day too big for one Claude run (150 texts, one 50,000-character email, one email with six 20,000-character
  attachments) is judged in rounds that each fit the round's caps, every message in exactly one round; the huge body and
  attachments arrive cut, each with its marker (on 10/15/26 a 142-message day timed out at 300 s twice and stopped the
  rebuild).
- A round that times out is asked for again at half its size, and the size goes back to full once the backlog is judged.
- With little time left after a judging round, the judge stops and leaves the rest for the next pass, put off, not failed,
  so the cards for what it judged are written first.
- A script cut off by the pass's own limit says it ran out of the pass's time (put off, not failed).
- After a failed judge, the cards owed for messages already judged are still written at the next pass.
- What was judged is on the owed list before the cards are written, and stays there when writing is cut off.

    python tests\judge_flow_acceptance.py
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
import datetime as dt, json, os, shutil, sys, time
live, slow = sys.argv[1], sys.argv[2]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import duckdb, common, db, limits, think, gather, ai_steps
out = {}
now = dt.datetime.now()
con = db.connect()
for i in range(150):
    con.execute("INSERT INTO messages (channel, account, thread_id, ts, direction, from_key, to_keys, body, ingested_at)"
                " VALUES ('sms', 'phone', ?, ?, 'in', ?, '[]', ?, ?)",
                (f"sms:t{i % 12}", now - dt.timedelta(minutes=i), f"sms:+1555000{i % 12:04d}", f"made-up text {i} about the trailer", now))
huge = " ".join(f"line {k} of a very long made-up quote for the trailer job." for k in range(900))       # about 50,000 characters
con.execute("INSERT INTO messages (channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
            " VALUES ('email', 'work', 'e:huge', ?, 'in', 'email:quotes@example.com', '[]', 'Quote', ?, ?)",
            (now - dt.timedelta(minutes=151), huge, now))
con.execute("INSERT INTO messages (channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
            " VALUES ('email', 'work', 'e:docs', ?, 'in', 'email:po@example.com', '[]', 'Six POs', 'See the six POs attached.', ?)",
            (now - dt.timedelta(minutes=152), now))
huge_id = con.execute("SELECT id FROM messages WHERE thread_id='e:huge'").fetchone()[0]
docs_id = con.execute("SELECT id FROM messages WHERE thread_id='e:docs'").fetchone()[0]
for k in range(6):
    att = con.execute("INSERT INTO attachments (message_id, original_filename, saved_filename, saved_path) VALUES (?, ?, ?, ?)"
                      " RETURNING id", (docs_id, f"po{k}.pdf", f"po{k}.pdf", f"po{k}.pdf")).fetchone()[0]
    doc = con.execute("INSERT INTO documents (message_id, attachment_id, doc_type, created_at) VALUES (?, ?, 'po', ?) RETURNING id",
                      (docs_id, att, now)).fetchone()[0]
    con.execute("INSERT INTO pages (document_id, page_no, text) VALUES (?, 1, ?)", (doc, f"PO {k} line item, " * 1200))
con.close()
ids = [r[0] for r in db.query("SELECT id FROM messages WHERE body LIKE 'made-up text %' ORDER BY id")]

# 1. the payload: a handful of opens, whatever the number of messages
import judgment_payload as jp
opened, real = [], duckdb.connect
duckdb.connect = lambda *a, **k: (opened.append(1), real(*a, **k))[1]
pl = os.path.join(common.paths.STATE, "payload_made_up.json")
sys.argv = ["judgment_payload.py", "--out", pl]
jp.main()
duckdb.connect = real
n1 = len(common.read_json(pl, {}).get("messages") or [])
out["payload"] = [0 < n1 <= jp.ROUND_MESSAGES, len(opened) <= 8]

# 1b. the big day in rounds: each round fits, every message in exactly one round, the huge ones cut with their markers
import contextlib, io
everyone = set(ids) | {huge_id, docs_id}
rounds_seen, over_cap, fits, marks = [], [], [], {}
for _ in range(20):
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        jp.main()
    if "days with unjudged" in said.getvalue():        # nothing left: no payload made
        break
    p = common.read_json(pl, {})
    got = [m["id"] for m in p.get("messages") or []]
    if not got:
        break
    rounds_seen.append(got)
    over_cap.append("OVER CAP" in said.getvalue())
    chars = sum(len(m.get("body") or "") for m in p["messages"]) + sum(len(d.get("text") or "") for d in p["documents"])
    fits.append(len(got) <= jp.ROUND_MESSAGES and chars <= jp.ROUND_CHARS)
    for m in p["messages"]:
        if m["id"] == huge_id:
            marks["body"] = [m["body"].endswith("[...]"), len(m["body"]) <= jp.MAX_BODY_CHARS + 10]
    texts = [d["text"] for d in p["documents"] if d["message_id"] == docs_id]
    if texts:
        marks["docs"] = [len(texts), all("characters of this attachment left out]" in t and len(t) < jp.MAX_DOC_CHARS + 80 for t in texts)]
    c = db.connect()
    for i in got:
        c.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, 'noise', 'test', ?)",
                  (f"msg:{i}", dt.datetime.now()))
    c.close()
flat = [i for r in rounds_seen for i in r]
left = [r[0] for r in db.query("SELECT id FROM messages m WHERE NOT EXISTS (SELECT 1 FROM answered a"
                                " WHERE a.domain='judged' AND a.key = 'msg:' || m.id)")]
out["rounds"] = [len(rounds_seen) >= 4, all(fits), len(flat) == len(set(flat)), sorted(everyone & set(left)),
                 over_cap == [True] * (len(rounds_seen) - 1) + [False]]
out["marks"] = marks
c = db.connect()            # the backlog again for what follows
c.execute("DELETE FROM answered WHERE domain='judged' AND source='test'")
c.close()
with contextlib.redirect_stdout(io.StringIO()):
    jp.main()                # the payload file holds the first round again

# 2. a backlog: one round, then the rest waits when what is left of the pass is kept for writing cards
rounds, real_script = [], think._engine_script
think._engine_script = lambda path, *a, timeout=0: (rounds.append(os.path.basename(path)),
    (True, f"payload: 150 messages in 12 conversations\n   1 KB at {pl}\n   OVER CAP: 3 day(s) left"))[1]
ai_steps.agent = lambda *a, **k: ai_steps.Result(True)
ai_steps.commit_with_fixes = lambda *a, **k: (True, "")
limits.begin("t")
limits._state["start"] = time.time() - (limits.PASS_LIMIT - 250)       # 250 s left: one round, not two
s = think._step("judge", think.judge)
out["backlog"] = [rounds.count("judgment_payload.py"), s["ok"], bool(s.get("put_off"))]

# 2b. a round that times out: asked again at half its size, back to full once nothing is left
asked, tries = [], []
outs = [f"payload: {n1} messages in 4 conversations\n   1 KB at {pl}\n   OVER CAP: 111 message(s) of today for the next round",
        f"payload: 19 messages in 2 conversations\n   1 KB at {pl}"]
think._engine_script = lambda path, *a, timeout=0: ((asked.append(list(a)), (True, outs[min(len(asked) - 1, 1)]))[1]
                                                    if path.endswith("judgment_payload.py") else (True, "committed"))
def judge_all():           # the smaller round's run: it judges what is left, so the backlog is done
    c = db.connect()
    c.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) SELECT 'judged', 'msg:' || m.id, 'noise',"
              " 'test', now() FROM messages m WHERE NOT EXISTS (SELECT 1 FROM answered a WHERE a.domain='judged'"
              " AND a.key = 'msg:' || m.id)")
    c.close()
    return ai_steps.Result(True)
ai_steps.agent = lambda *a, **k: (tries.append(1), judge_all() if len(tries) > 1 else ai_steps.Result(False, why="timed out after 300s"))[1]
limits.begin("t3")
size_file = os.path.join(common.paths.STATE, "judge_round.json")
s = think._step("judge", think.judge)
out["timed out round"] = [asked[0], asked[1] if len(asked) > 1 else None, s["ok"], common.read_json(size_file, {}) or {}]
out["half"] = str(max(think.JUDGE_SMALLEST, n1 // 2))
c = db.connect()            # the backlog again for what follows
c.execute("DELETE FROM answered WHERE domain='judged' AND source='test'")
c.close()

# 3. a script cut off by the pass's limit says so where it is cut
think._engine_script = real_script
limits._state["start"] = time.time() - (limits.PASS_LIMIT - 12)
ok, said = think._limited_script(slow)
out["cut"] = [ok, think.OUT_OF_TIME in said]
cut = think._step("judge", lambda: (False, "FAILED: the judging payload could not be made: " + said))
out["cut step"] = [cut["ok"], bool(cut.get("put_off"))]

# 4. after a failed judge, cards owed for judged mail are written; the judge alone rests
g = {"unjudged": 30, "pages_waiting": 0, "texted_images_waiting": 0, "new_messages": 0, "new_attachments": 0}
common.write_json(common.THINK_STATE, {"failed_at": common.now().isoformat(), "rewrite_items": [], "pending_items": [],
                                       "pending_msgs": [ids[0]], "last": [{"step": "judge", "ok": False}]})
out["after a failure"] = [sorted(think.resting(g)), bool(think.needed(g))]

# 5. owed before writing, and kept when writing is cut off
common.write_json(common.THINK_STATE, {"failed_at": None, "rewrite_items": [], "pending_items": [], "pending_msgs": [], "last": []})
limits.begin("t2")
judged = ids[:5]

def judge():
    c = db.connect()
    for i in judged:
        c.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, 'task', 'test', ?)",
                  (f"msg:{i}", dt.datetime.now()))
    c.close()
    return True, "judged 5"
seen = {}

def write_items(owed_items, owed_msgs, forced=()):
    seen["owed"] = (common.read_json(common.THINK_STATE) or {}).get("pending_msgs")
    return False, f"0 item(s) written; the rest wait: {think.OUT_OF_TIME}"
think.judge, think.write_items = judge, write_items
t = think.think("t2")
st = common.read_json(common.THINK_STATE) or {}
out["owed"] = [sorted(set(judged) - set(seen.get("owed") or [])), sorted(set(judged) - set(st.get("pending_msgs") or [])),
               st.get("failed_at"), t["ok"]]
print(json.dumps(out))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="judgeflow-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    slow = os.path.join(tmp, "slow.py")
    with open(slow, "w", encoding="utf-8") as f:
        f.write("import time\ntime.sleep(40)\n")
    spec = importlib.util.spec_from_file_location("ac_judgeflow", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47937", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, slow], capture_output=True, text=True, env=env, timeout=300)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        if "error" in o:
            print(o["error"])
        check("the payload for 150 messages is one round's worth and opens the database a handful of times", o.get("payload"),
              [True, True])
        check("a day too big for one run is judged in rounds: each fits, each message once, none left, OVER CAP until the last",
              o.get("rounds"), [True, True, True, [], True])
        check("the 50,000-character body and the six long attachments arrive cut, each with its marker", o.get("marks"),
              {"body": [True, True], "docs": [6, True]})
        h = o.get("half")
        check("a timed-out round is asked again at half its size; back to full once the backlog is judged",
              o.get("timed out round"), [[], ["--round-messages", h], True, {}])
        check("a backlog: one round, then the rest is put off so the cards get time", o.get("backlog"), [1, True, True])
        check("a script cut off by the pass's limit says it ran out of the pass's time", o.get("cut"), [False, True])
        check("... and that step is put off, not failed", o.get("cut step"), [True, True])
        check("after a failed judge only the judge rests; the owed cards are still written", o.get("after a failure"),
              [["first sort", "judge"], True])
        check("what was judged is owed before the cards are written, and stays owed when writing is cut off", o.get("owed"),
              [[], [], None, True])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
