r"""Reading back: from a start date, read every connected source and record what happened to the owner's matters.

The owner's words: reading back "should start to create the history of things that have been done ... It sees
tasks coming in, it sees answers, it sees things getting completed, and records them as such."

ITEMS.md ("Reading back") is the contract. For each conversation from the start date on, in order:
  1. the sources are read from that date (connections read as far back as the date says; nothing else changes);
  2. the mechanical filters settle junk, the owner's ignore list and what they sent themselves, with no Claude;
  3. what is left is read in batches by the fastest model, which says for each conversation whether it was a task
     for the owner, whether they answered, and whether it was completed;
  4. history is written: `came_in`, `answered`, `completed`, each once; a card is made only for what is still open
     (one card per conversation); every message read is marked judged, so the next pass does not read it again;
  5. one summary card says how far back, how many came in, were answered, were completed, are open, and what was
     unsure.
It is safe to run twice (a conversation already read is never read again) and to run again from an earlier date.

    python readback.py plan --since 2026-09-01             what it would read and what it would cost; reads no Claude
    python readback.py run  --since 2026-09-01 --go        does it (--max-runs N stops after N Claude runs; run again to go on)
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import subprocess
import sys

import card
import common
import dates
import db
import gather
import settings_page

BATCH = 20                  # conversations per Claude run
MODEL = "haiku"             # the fastest model; the choice in Settings is for what needs care
SAYS = 500                  # characters of one message shown
MESSAGES = 8                # messages of one conversation shown (the first, then the newest)
SECS_A_RUN = 75             # a rough time for one run, for the estimate
LOG = os.path.join(common.LOGS, "readback.log")
SUMMARY = os.path.join(common.HOME, "readback_summary.json")
SUMMARY_KEY = "live:readback-summary"
CARD_PREFIX = "live:readback-"
KINDS = ("came_in", "answered", "completed")

DDL = """
CREATE SEQUENCE IF NOT EXISTS seq_live_history START 1;
CREATE TABLE IF NOT EXISTS live_history (
  id BIGINT PRIMARY KEY DEFAULT nextval('seq_live_history'), happened_at TIMESTAMP NOT NULL, kind VARCHAR NOT NULL,
  ref VARCHAR NOT NULL UNIQUE, thread VARCHAR NOT NULL, title VARCHAR NOT NULL, who VARCHAR, channel VARCHAR,
  message_ids VARCHAR, note VARCHAR, unsure VARCHAR, source VARCHAR NOT NULL, run_id VARCHAR NOT NULL, recorded_at TIMESTAMP NOT NULL);
CREATE TABLE IF NOT EXISTS live_readback_threads (
  thread VARCHAR PRIMARY KEY, run_id VARCHAR NOT NULL, read_at TIMESTAMP NOT NULL, was_task BOOLEAN NOT NULL, state VARCHAR, unsure VARCHAR);
CREATE TABLE IF NOT EXISTS live_readback_runs (
  run_id VARCHAR PRIMARY KEY, started_at TIMESTAMP NOT NULL, since DATE NOT NULL, threads INTEGER, claude_runs INTEGER, note VARCHAR);
"""


def say(text):
    common.log_line(LOG, text)
    print(text, flush=True)


def ensure():
    con = db.connect()
    try:
        con.execute(DDL)
    finally:
        con.close()


def thread_key(channel, thread_id, mid):
    return f"{channel}|{thread_id or mid}"


# --- 1. reading the sources from the date ---------------------------------------------------------------
def fetch(since, run_id):
    """Read every connected source from the date. Returns plain lines for the log. The sources' own watermarks are not
    moved (ASSISTANT_READ_SINCE tells them to read from the date and to leave their place alone)."""
    import connections
    run = os.path.join(common.paths.CONNECTIONS, "run.py")
    kinds = sorted({c.get("kind") for c in connections.listed() if c.get("kind") in set(common.channels()) - {"calendar"}})
    env = dict(os.environ, ASSISTANT_READ_SINCE=since.isoformat())
    out = []
    for kind in kinds:
        ok, tail = _run(run, kind, env, run_id)
        out.append(f"{kind}: {'ok' if ok else 'FAILED'} {tail}")
    return out


def _run(run, kind, env, run_id):
    try:
        r = subprocess.run([sys.executable, run, "--kind", kind, "--limit", "20000", "--run-id", run_id], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, type(e).__name__
    tail = " | ".join(l.strip() for l in (r.stdout or r.stderr or "").splitlines()[-3:] if l.strip())
    return r.returncode == 0, tail[:300]


# --- 2. what is left to read -------------------------------------------------------------------------------
def settle_mechanically():
    """The junk lists, the ignore list, short numbers: no Claude. Mail he sent is marked read too."""
    import sys as _sys
    if common.paths.CORE not in _sys.path:
        _sys.path.insert(0, common.paths.CORE)
    import judgment_payload as jp
    jp.prefilter_noise()


def threads_to_read(since):
    """{thread key: [message rows]} for conversations from the date with an incoming message nothing has ruled on,
    that were not read back before. Newest message last."""
    rows = db.query(
        """SELECT m.id, m.channel, m.thread_id, m.ts, m.direction, m.from_key, m.subject, substr(m.body, 1, 6000),
                  (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL),
                  EXISTS (SELECT 1 FROM answered a WHERE a.domain='judged' AND a.key = 'msg:' || m.id)
           FROM messages m WHERE m.ts >= ? AND list_contains(?, m.channel) AND coalesce(m.from_key, '') <> 'assistant'
           ORDER BY m.ts, m.id""", (dt.datetime.combine(since, dt.time()), sorted(set(common.channels()) - {"calendar"})))
    done = {r[0] for r in db.query("SELECT thread FROM live_readback_threads")}
    out = {}
    for mid, channel, tid, ts, direction, fk, subject, body, name, judged in rows:
        key = thread_key(channel, tid, mid)
        out.setdefault(key, []).append({"id": mid, "channel": channel, "ts": ts, "direction": direction, "from": name or str(fk or "").split(":", 1)[-1],
                                        "subject": subject, "body": body, "judged": bool(judged)})
    keep = {}
    for key, msgs in out.items():
        if key in done:
            continue
        if any(m["direction"] == "in" and not m["judged"] for m in msgs):
            keep[key] = msgs
        else:       # only mail he sent, or only mail already ruled on: settled, never a task here
            keep[key] = None
    return keep


def plan(since):
    """What reading back from this date would do and cost. Reads the messages already in the database (run `fetch` first
    for a date earlier than what is held). No Claude."""
    ensure()
    found = threads_to_read(since)
    todo = {k: v for k, v in found.items() if v}
    runs = math.ceil(len(todo) / BATCH)
    total = db.query("SELECT count(*) FROM messages WHERE ts >= ?", (dt.datetime.combine(since, dt.time()),))[0][0]
    return {"since": since.isoformat(), "messages": total, "conversations_found": len(found), "conversations_to_read": len(todo),
            "settled_without_claude": len(found) - len(todo), "claude_runs": runs, "model": MODEL, "per_run": BATCH,
            "minutes": round(runs * SECS_A_RUN / 60, 1),
            "words": (f"From {since:%m/%d/%y}: {total} messages in {len(found)} conversations. {len(found) - len(todo)} are settled without Claude "
                      f"(junk, your ignore list, mail you sent). {len(todo)} need reading: {runs} Claude run{'s' if runs != 1 else ''} on the fastest model "
                      f"({BATCH} conversations a run), about {round(runs * SECS_A_RUN / 60, 1)} minutes in all, counted toward your daily limit. "
                      "Nothing else uses Claude. You can stop at any time and run it again to go on.")}


# --- 3. the reading ---------------------------------------------------------------------------------------------
def _prompt(batch, areas):
    import think
    import sys as _sys
    if common.paths.MODULE_A not in _sys.path:
        _sys.path.insert(0, common.paths.MODULE_A)
    import cleantext
    threads = []
    for key, msgs in batch:
        first_in = next((m for m in msgs if m["direction"] == "in"), msgs[0])
        reply = next((m for m in msgs if m["direction"] == "out" and m["ts"] > first_in["ts"]), None)
        shown = msgs if len(msgs) <= MESSAGES else msgs[:2] + msgs[-(MESSAGES - 2):]
        threads.append({"thread": key, "first_message_at": first_in["ts"].isoformat(timespec="minutes"),
                        "you_replied_at": reply["ts"].isoformat(timespec="minutes") if reply else None,
                        "last_message_at": msgs[-1]["ts"].isoformat(timespec="minutes"), "messages": len(msgs),
                        "shown": [{"when": m["ts"].isoformat(timespec="minutes"), "from": "YOU" if m["direction"] == "out" else m["from"],
                                   "subject": m["subject"], "says": cleantext.new_text(m["body"] or "", limit=SAYS, subject=m["subject"] or "")} for m in shown]})
    path = os.path.join(common.paths.STATE, "live_readback_payload.json")
    common.write_json(path, {"today": dt.date.today().isoformat(), "areas": areas, "threads": threads})
    return think._prompt("readback", PAYLOAD_PATH=path, AREAS=", ".join(areas)), path


def classify(batch, areas, run_no):
    """One Claude run for up to BATCH conversations. Returns {thread key: classification}, or {} when the run failed."""
    import ai_steps
    import think
    think._current.update({"pass": f"readback-{run_no}", "step": "readback"})
    prompt, _ = _prompt(batch, areas)
    out = os.path.join(common.paths.STATE, "live_readback_out.json")
    res = ai_steps.agent(prompt, MODEL, out, 900)
    if not res.ok:
        say(f"a reading run failed ({res.why}); those conversations stay unread and a second run will try them again")
        return {}
    got = {}
    for e in (common.read_json(out, {}) or {}).get("threads") or []:
        if isinstance(e, dict) and e.get("thread") in {k for k, _ in batch}:
            got[e["thread"]] = e
    return got


# --- 4. writing the history -----------------------------------------------------------------------------------------
def _when(v, fallback):
    try:
        return dt.datetime.fromisoformat(str(v)[:19].replace("Z", ""))
    except ValueError:
        return fallback


def _hist(con, kind, key, at, title, who, channel, ids, note, unsure, run_id):
    con.execute("INSERT INTO live_history (happened_at, kind, ref, thread, title, who, channel, message_ids, note, unsure, source, run_id, recorded_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,'readback',?,?) ON CONFLICT (ref) DO NOTHING",
                (at, kind, f"{key}|{kind}", key, title[:300], who, channel, json.dumps(ids), note, unsure or None, run_id, common.now()))


def commit(batch, got, run_id):
    """Write what the reading said. A conversation the run did not answer is left unread. Returns how many were read."""
    import items
    items.ensure()
    wrote = 0
    for key, msgs in batch:
        c = got.get(key)
        if c is None:
            continue
        ids = [m["id"] for m in msgs]
        first_in = next((m for m in msgs if m["direction"] == "in"), msgs[0])
        newest_in = next((m for m in reversed(msgs) if m["direction"] == "in"), msgs[-1])
        reply = next((m for m in msgs if m["direction"] == "out" and m["ts"] > first_in["ts"]), None)
        task = bool(c.get("task"))
        title = " ".join(str(c.get("title") or first_in["subject"] or "A conversation").split())
        state = c.get("state") if c.get("state") in ("open", "waiting", "completed") else "open"
        unsure = " ".join(str(c.get("unsure") or "").split())
        who = " ".join(str(c.get("who") or first_in["from"] or "").split())
        con = db.connect()
        try:
            con.execute(DDL)
            if task:
                _hist(con, "came_in", key, first_in["ts"], title, who, first_in["channel"], ids, "A task came in.", unsure, run_id)
                if reply:
                    _hist(con, "answered", key, reply["ts"], title, who, first_in["channel"], ids, "You answered.", unsure, run_id)
                if state == "completed":
                    _hist(con, "completed", key, _when(c.get("completed_at"), msgs[-1]["ts"]), title, who, first_in["channel"], ids,
                          " ".join(str(c.get("why") or "It was completed.").split())[:300], unsure, run_id)
            source = "readback: a task" if task else "readback: not a task"
            for m in msgs:
                con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, ?, ?, ?) ON CONFLICT (domain, key) DO NOTHING",
                            (f"msg:{m['id']}", "task" if task else "ignore", source if m["direction"] == "in" else "readback: sent by you", common.now()))
            con.execute("INSERT INTO live_readback_threads VALUES (?,?,?,?,?,?) ON CONFLICT (thread) DO NOTHING",
                        (key, run_id, common.now(), task, state if task else None, unsure or None))
        finally:
            con.close()
        if task and state in ("open", "waiting"):
            asks = [" ".join(str(a).split()) for a in (c.get("asks") or []) if str(a or "").strip()][:3]
            area = str(c.get("area") or "").strip() if str(c.get("area") or "").strip() in common.personal().get("areas", []) + ["Personal", "System"] else "Personal"
            waiting = state == "waiting"
            fields = dict(kind="waiting" if waiting else ("question" if asks else "task"), area=area,
                          state="in_motion" if waiting else ("question" if asks else "yours"), title=title,
                          short_header=card.whole(c.get("header")) or None, detail=" ".join(str(c.get("detail") or "").split()) or None, asks=[] if waiting else (asks or [f"Your next step: {c.get('next') or 'read it and decide what it needs.'}"]),
                          why=" ".join(str(c.get("why") or "").split()) or "It is still open from before.", source_who=who, source_when=newest_in["ts"],
                          source_ref=f"{who}, {first_in['channel']}, {newest_in['ts'].month}/{newest_in['ts'].day} ({newest_in['id']})", source_messages=[str(i) for i in reversed(ids)][:25])
            items.upsert(CARD_PREFIX + hashlib.sha1(key.encode()).hexdigest()[:12], run_id, **fields)
        wrote += 1
    return wrote


# --- 5. the summary -----------------------------------------------------------------------------------------------------
def summary():
    """The counts over everything read back so far."""
    ensure()
    count = lambda kind: db.query("SELECT count(*) FROM live_history WHERE kind=?", (kind,))[0][0]  # noqa: E731
    runs = db.query("SELECT min(since), count(*), coalesce(sum(claude_runs), 0) FROM live_readback_runs")[0]
    state = dict(db.query("SELECT coalesce(state, 'none'), count(*) FROM live_readback_threads WHERE was_task GROUP BY 1"))
    not_tasks = db.query("SELECT count(*) FROM live_readback_threads WHERE NOT was_task")[0][0]
    unsure = [{"title": t, "why": u} for t, u in db.query("SELECT title, unsure FROM live_history WHERE kind='came_in' AND unsure IS NOT NULL ORDER BY happened_at")]
    unsure += [{"title": "(not a task)", "why": u} for (u,) in db.query("SELECT unsure FROM live_readback_threads WHERE NOT was_task AND unsure IS NOT NULL")]
    out = {"since": str(runs[0]) if runs[0] else None, "written_at": common.now(), "tasks_came_in": count("came_in"), "answered": count("answered"),
           "completed": count("completed"), "still_open": state.get("open", 0), "waiting_on_others": state.get("waiting", 0), "not_tasks": not_tasks,
           "unsure": unsure[:30], "claude_runs": int(runs[2]), "runs": int(runs[1])}
    common.write_json(SUMMARY, out)
    return out


def summary_card(s, run_id):
    import items
    if not s["since"]:
        return
    since = dt.date.fromisoformat(s["since"])
    lines = [f"Read back from {since.month}/{since.day}/{since:%y}: {s['tasks_came_in']} tasks came in, you answered {s['answered']}, {s['completed']} were completed, "
             f"{s['still_open']} are still open and {s['waiting_on_others']} wait on others. {s['not_tasks']} conversations were not tasks.",
             f"It took {s['claude_runs']} Claude run{'s' if s['claude_runs'] != 1 else ''}."]
    if s["unsure"]:
        lines.append("Not sure about: " + "; ".join(f"{u['title']} ({u['why']})" for u in s["unsure"][:8]) + ("." if len(s["unsure"]) <= 8 else f", and {len(s['unsure']) - 8} more."))
    else:
        lines.append("Nothing it was unsure about.")
    items.upsert(SUMMARY_KEY, run_id, kind="fyi", area="System", state="handled", status=None,
                 title=f"Reading back from {since.month}/{since.day}: {s['tasks_came_in']} tasks found, {s['completed']} completed, {s['still_open']} still open",
                 detail="\n".join(lines), why="You asked me to read it back.", assistant_did="Made by reading back.")


# --- the run ------------------------------------------------------------------------------------------------------------
def run(since, go=False, max_runs=None, fetch_first=True):
    ensure()
    p = plan(since)
    say(p["words"])
    if not go:
        return p
    if not gather.take_lock():
        say("I'm checking for messages right now; try again in a few minutes")
        return None
    run_id = "readback-" + common.now().strftime("%Y%m%d-%H%M%S")
    try:
        con = db.connect()
        try:
            con.execute("INSERT INTO live_readback_runs VALUES (?,?,?,?,?,?)", (run_id, common.now(), since, 0, 0, "started"))
        finally:
            con.close()
        if fetch_first:
            for line in fetch(since, run_id):
                say(line)
            settle_mechanically()
        found = threads_to_read(since)
        todo = [(k, v) for k, v in found.items() if v]
        # conversations with nothing to read are settled now (mail he sent, mail already ruled on)
        con = db.connect()
        try:
            for k, v in found.items():
                if v is None:
                    con.execute("INSERT INTO live_readback_threads VALUES (?,?,?,FALSE,NULL,NULL) ON CONFLICT (thread) DO NOTHING", (k, run_id, common.now()))
            for k, v in found.items():
                if v is None:
                    for (mid,) in con.execute("SELECT id FROM messages WHERE channel || '|' || coalesce(thread_id, CAST(id AS VARCHAR)) = ?", (k,)).fetchall():
                        con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, 'ignore', 'readback: nothing to read', ?) ON CONFLICT (domain, key) DO NOTHING", (f"msg:{mid}", common.now()))
        finally:
            con.close()
        areas = [a for a in common.personal().get("areas") or [] if a] + ["Personal"]
        runs = read = 0
        for n in range(0, len(todo), BATCH):
            if max_runs is not None and runs >= max_runs:
                say(f"stopped after {runs} Claude run(s) as asked; run it again to go on")
                break
            if settings_page.at_limit():
                say("today's limit on AI use is reached; run it again tomorrow to go on")
                break
            batch = todo[n:n + BATCH]
            runs += 1
            settings_page.count_run()
            got = classify(batch, areas, runs)
            read += commit(batch, got, run_id)
            say(f"run {runs}: {len(got)} of {len(batch)} conversations read")
        con = db.connect()
        try:
            con.execute("UPDATE live_readback_runs SET threads=?, claude_runs=?, note='done' WHERE run_id=?", (read, runs, run_id))
        finally:
            con.close()
        s = summary()
        summary_card(s, run_id)
        import items
        items.export(run_id)
        say(f"summary: {s['tasks_came_in']} tasks came in, {s['answered']} answered, {s['completed']} completed, {s['still_open']} open, {s['waiting_on_others']} waiting, "
            f"{s['not_tasks']} not tasks, {len(s['unsure'])} unsure")
        return s
    finally:
        gather.drop_lock()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("plan", "run"))
    ap.add_argument("--since", required=True)
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--max-runs", type=int)
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args()
    since = dt.date.fromisoformat(a.since)
    if a.what == "plan":
        ensure()
        if not a.no_fetch:             # reading the sources costs no Claude, so the plan can be made from what is really there
            if not gather.take_lock():
                say("I'm checking for messages right now; try again in a few minutes")
                return 1
            try:
                run_id = "readback-plan-" + common.now().strftime("%Y%m%d-%H%M%S")
                for line in fetch(since, run_id):
                    say(line)
                settle_mechanically()
            finally:
                gather.drop_lock()
        p = plan(since)
        print(json.dumps(p, indent=1, default=str))
        return 0
    return 0 if run(since, go=a.go, max_runs=a.max_runs, fetch_first=not a.no_fetch) is not None else 1


if __name__ == "__main__":
    sys.exit(main())
