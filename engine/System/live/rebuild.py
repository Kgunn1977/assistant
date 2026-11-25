r"""Rebuild every open card with the current rules, and put them all back in one step.

    start()       saves every open card whole, owes each one a full writing, and starts run_now() hidden at once.
    run_now()     the card writer, now: every owed card written afresh from its messages and history (title, header,
                  why, story, question, choices, what it waits on, joins), under the owner's rules, then the page
                  refreshed. It takes the pass's own lock, so it never runs beside a pass; cards it has no time for
                  stay owed and the next pass writes them.
                  His answers, presses, states he set and snooze dates stay: the writer never touches them.
    reset(ids, notes) some cards put back to the owner, at his request: saved first (put_back returns them), what they
                  waited on, came back for, his old answer and last press, and any snooze cleared, the history kept with one
                  line added ("Reset <day> at your request", plus his direction for that card), then written afresh by the
                  card writer as his to decide or do, and the page refreshed.
    put_back()    every card saved by the last start (or reset), back exactly as it was, column for column.
    status()      the last rebuild: when, how many cards, whether they were put back.

From the page: Settings, "Rebuild all cards" (id "rebuild", text {"rebuild": "start" | "put_back"}).
From a terminal:  python rebuild.py start | put-back | status | reset <id> [<id>=<his direction for that card>] ...
"""
import datetime as dt
import glob
import json
import os
import sys

import common
import db
import items

FOLDER = os.path.join(common.HOME, "state", "rebuild")
STATE = os.path.join(FOLDER, "last.json")


def _plain(v):
    if isinstance(v, (dt.datetime, dt.date)):
        return {"$t": "ts" if isinstance(v, dt.datetime) else "date", "v": v.isoformat()}
    return v


def _back(v):
    if isinstance(v, dict) and v.get("$t") in ("ts", "date"):
        return dt.datetime.fromisoformat(v["v"]) if v["$t"] == "ts" else dt.date.fromisoformat(v["v"])
    return v


def _save_path(now):
    """A file of its own for each saved set: two saves in the same second (a rebuild, then a press acted on at once) never
    write over each other."""
    path, n = os.path.join(FOLDER, f"saved-{now:%Y%m%d-%H%M%S}.json"), 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(FOLDER, f"saved-{now:%Y%m%d-%H%M%S}-{n}.json")
    return path


def start():
    """(cards owed a writing, plain words)."""
    items.ensure()
    cols = items.COLUMNS
    got = db.query(f"SELECT {', '.join(cols)} FROM live_items WHERE state <> 'done'")
    import rsi_loop     # a rule change card: only its own buttons change it, so it is neither saved nor rebuilt
    import wouldhide    # nor an "I'd hide this" card: the program's own one line about one message
    got = [r for r in got if not rsi_loop.is_card({"source_key": r[cols.index("source_key")]})
           and not wouldhide.is_card({"source_key": r[cols.index("source_key")]})]
    if not got:
        return 0, "There are no open cards to rebuild."
    os.makedirs(FOLDER, exist_ok=True)
    now = common.now()
    path = _save_path(now)
    common.write_json(path, {"saved_at": now.isoformat(timespec="seconds"), "columns": cols,
                             "cards": [[_plain(v) for v in r] for r in got]})
    # a card he pressed Done (or Not yours) on that a pass reopened before Done held: closed again, as he said
    db.execute("UPDATE live_items SET state='done', done_at=?, answered_at=coalesce(answered_at, ?), updated_at=?,"
               " state_changed_at=? WHERE state <> 'done' AND status IN ('Done', 'Not yours')", (now, now, now, now))
    got = [r for r in got if not (r[cols.index("status")] in ("Done", "Not yours"))]
    import mods         # a mod's own cards are the mod's to write: never rebuilt here
    import presses      # the junk question is the engine's own words: never rebuilt
    owed = [r[0] for r in got if json.loads(r[cols.index("source_messages")] or "[]")
            and not mods.owns({"source_key": r[cols.index("source_key")]})
            and not presses.is_junk_ask({"source_key": r[cols.index("source_key")]})]
    items.owe_writing(owed)
    common.write_json(STATE, {"saved": os.path.basename(path), "at": now.isoformat(timespec="seconds"),
                              "cards": len(got), "owed": len(owed), "put_back": None, "running": None, "done_at": None})
    import answers
    started = bool(owed) and answers.start_hidden([sys.executable, os.path.abspath(__file__), "run"])
    if started:
        st = common.read_json(STATE, {}) or {}
        st["running"] = now.isoformat(timespec="seconds")
        common.write_json(STATE, st)
    when = "now; your page shows it while it works and refreshes when it is done" if started else "the next time I check for messages, within a few minutes"
    return len(owed), (f"Your {len(got)} open cards are saved, and {len(owed)} are being written afresh {when}. "
                       "Your answers, what you pressed and snooze dates stay as they are. "
                       "\"Put them back\" in Settings returns every card to how it was.")


def reset(ids, notes=None):
    """(cards reset and written afresh, plain words). Only cards he asked to have reset; the database is changed only here,
    through the program, and the card writer then writes each one from its messages and history."""
    items.ensure()
    notes = notes or {}
    ids = [str(i) for i in ids if str(i).strip()]
    cols = items.COLUMNS
    got = db.query(f"SELECT {', '.join(cols)} FROM live_items WHERE id IN ({', '.join('?' for _ in ids)})", tuple(ids)) if ids else []
    import rsi_loop     # a rule change card is never reset: only its own buttons change it
    import wouldhide    # nor an "I'd hide this" card
    got = [r for r in got if not rsi_loop.is_card({"source_key": r[cols.index("source_key")]})
           and not wouldhide.is_card({"source_key": r[cols.index("source_key")]})]
    if not got:
        return 0, "None of those cards is there."
    os.makedirs(FOLDER, exist_ok=True)
    now = common.now()
    path = _save_path(now)
    common.write_json(path, {"saved_at": now.isoformat(timespec="seconds"), "columns": cols,
                             "cards": [[_plain(v) for v in r] for r in got]})
    con = db.connect()
    try:
        for r in got:
            row = dict(zip(cols, r))
            try:
                ex = json.loads(row.get("extra") or "{}") if isinstance(row.get("extra"), str) else dict(row.get("extra") or {})
            except ValueError:
                ex = {}
            for k in ("waiting_on", "came_back"):
                ex.pop(k, None)
            line = (f"Reset {now.month}/{now.day} at your request: the earlier plans and promises on this card are dropped; "
                    f"it is yours to decide or do." + (f" {notes[row['id']].strip()}" if notes.get(row["id"]) else ""))
            did = row.get("assistant_did") or ""
            con.execute("UPDATE live_items SET state='yours', status=NULL, answer=NULL, answered_at=NULL, last_press=NULL,"
                        " checkback_date=NULL, shelf=NULL, later_until=NULL, extra=?, assistant_did=?, updated_at=?,"
                        " state_changed_at=? WHERE id=?",
                        (json.dumps(ex), f"{did}\n{line}" if did else line, now, now, row["id"]))
    finally:
        con.close()
    common.write_json(STATE, {"saved": os.path.basename(path), "at": now.isoformat(timespec="seconds"), "cards": len(got),
                              "owed": len(got), "put_back": None, "running": None, "done_at": None, "reset": [r[0] for r in got]})
    items.owe_writing([r[0] for r in got])
    n = run_now()
    return n, (f"{len(got)} card{'s' if len(got) != 1 else ''} reset and written afresh as yours to decide or do"
               + ("" if n == len(got) else f" ({n} written now; the rest the next time I check for messages)")
               + ". \"Put them back\" in Settings returns them to how they were.")


def run_now(wait=17 * 60):
    """Write every owed card now (the card writer, think.write_items), then refresh the page. Returns how many."""
    import time
    import gather
    import limits
    import think
    st = common.read_json(STATE, {}) or {}
    end = time.time() + wait
    while not gather.take_lock():           # a pass is running: wait for it, then go
        if time.time() > end:
            st.update(running=None)
            common.write_json(STATE, st)
            return 0
        time.sleep(10)
    n = 0
    try:
        pid = "rebuild-" + common.now().strftime("%Y%m%d-%H%M%S")
        limits.begin(pid)
        think._current["pass"] = pid
        ts = common.read_json(common.THINK_STATE, {}) or {}
        owed = set(ts.get("rewrite_items") or [])
        if owed:
            think.write_items([], [], owed)
            left = set(think.left["items"]) if think.left["ran"] else owed
            n = len(owed - left)
            ts = common.read_json(common.THINK_STATE, {}) or {}
            ts["rewrite_items"] = sorted(set(ts.get("rewrite_items") or []) - (owed - left))
            common.write_json(common.THINK_STATE, ts)
        import items
        items.export(pid)
    finally:
        gather.drop_lock()
        st = common.read_json(STATE, {}) or {}
        st.update(running=None, done_at=common.now().isoformat(timespec="seconds"), rebuilt=n)
        common.write_json(STATE, st)
        try:        # the page shows the rebuilt cards now
            import subprocess
            subprocess.run([sys.executable, os.path.join(os.path.dirname(common.HERE), "live_page", "publish.py")],
                           capture_output=True, timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:  # noqa: BLE001  the next pass shows them
            pass
    return n


def put_back():
    """(cards put back, plain words). Every card the last start saved, exactly as it was."""
    st = common.read_json(STATE, {}) or {}
    path = os.path.join(FOLDER, str(st.get("saved") or ""))
    saved = common.read_json(path, None) if st.get("saved") else None
    if not saved:
        return 0, "There is no saved set of cards to put back."
    cols = saved["columns"]
    keep = [c for c in cols if c != "id" and c in items.COLUMNS]
    con = db.connect()
    try:
        import rsi_loop
        import wouldhide
        for row in saved["cards"]:
            r = dict(zip(cols, [_back(v) for v in row]))
            if rsi_loop.is_card(r) or wouldhide.is_card(r):
                continue        # a rule change card saved by an older start: only its own buttons change it
            con.execute(f"UPDATE live_items SET {', '.join(c + '=?' for c in keep)} WHERE id=?",
                        (*[r[c] for c in keep], r["id"]))
    finally:
        con.close()
    ts = common.read_json(common.THINK_STATE, {}) or {}       # nothing of the rebuild is still owed
    ids = {row[cols.index("id")] for row in saved["cards"]}
    ts["rewrite_items"] = [i for i in ts.get("rewrite_items") or [] if i not in ids]
    common.write_json(common.THINK_STATE, ts)
    st["put_back"] = common.now().isoformat(timespec="seconds")
    common.write_json(STATE, st)
    return len(saved["cards"]), f"All {len(saved['cards'])} cards are back as they were on {saved['saved_at'][:16].replace('T', ' at ')}."


def status():
    return common.read_json(STATE, {}) or {}


def for_page():
    """What the page's Settings shows of the last rebuild."""
    st = status()
    return {k: st.get(k) for k in ("at", "cards", "running", "done_at", "rebuilt", "put_back")} if st else None


def covered(rec):
    """True when a saved Rebuild press needs nothing more: a rebuild was started at or after the press, or was
    still running when it was pressed. Put back is never covered."""
    try:
        what = (json.loads(rec.get("text") or "{}") or {}).get("rebuild")
        when = dt.datetime.fromisoformat(str(rec.get("at")))
    except (ValueError, TypeError, AttributeError):
        return False
    st = common.read_json(STATE, {}) or {}
    if what != "start" or not st.get("at"):
        return False
    began = dt.datetime.fromisoformat(st["at"])
    ended = st.get("done_at")
    return began >= when or not ended or dt.datetime.fromisoformat(ended) >= when


def act(rec):
    """A press from the page's Settings, in the shape answers.act_on_answer returns."""
    try:
        what = (json.loads(rec.get("text") or "{}") or {}).get("rebuild")
    except (ValueError, TypeError, AttributeError):
        what = None
    if what == "start":
        _n, said = start()
    elif what == "put_back":
        _n, said = put_back()
    else:
        said = "That is not something this button can do."
    return {"ok": True, "items": [], "result": said, "thought": False, "secs": {}}


def main():
    what = (sys.argv[1:] or ["status"])[0]
    if what == "run":
        print(f"{run_now()} cards rebuilt")
    elif what == "start":
        print(start()[1])
    elif what == "put-back":
        print(put_back()[1])
    elif what == "reset":
        ids, notes = [], {}
        for a in sys.argv[2:]:
            iid, _, note = a.partition("=")
            ids.append(iid.strip())
            if note.strip():
                notes[iid.strip()] = note.strip()
        print(reset(ids, notes)[1])
    else:
        print(json.dumps(status(), indent=1))
        print("saved sets:", len(glob.glob(os.path.join(FOLDER, "saved-*.json"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
