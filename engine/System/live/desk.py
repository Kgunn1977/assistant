r"""A Claude desktop session in the assistant's folder, as one with Talk to your assistant (the box at the top of the page).

A session joins once (/assistant:talk runs `python System\live\desk.py join`; the plugin's hook sees that command and
records the session). From then on, for that session only:
  - each message the owner types there is added to the one shared conversation (chat.json), marked "desktop" with the
    session's id, and the session is shown what was said in the box since it last spoke (hook: UserPromptSubmit);
  - each reply it gives is added the same way, once per message (hook: Stop), and the page is refreshed;
  - what it does goes through the box's own handling: `python System\live\desk.py act` with the ACTION lines on stdin runs
    them through chat._do_all, with the owner's own words of his latest message there as their authority, taken from what
    the hook recorded, never from the session.
Other sessions in the folder (a helper, a session that never joined) are left alone. Nothing here keeps running.

    python desk.py join | leave              # run by the session; the hook records it
    python desk.py heard | said              # the hooks, with the hook's JSON on stdin
    python desk.py act <file>                # ACTION: {...} lines, as the box ends a reply (or on stdin)
"""
import json
import os
import re
import subprocess
import sys

import common
import chat

JOINED = os.path.join(common.paths.STATE, "desk_sessions.json")
SHOW = 12            # the box's turns shown at most at the start of a message


NOT_HIS = ("<task-notification", "<system-reminder", "[Artifact comment", "<command-", "<local-command", "<teammate-message")


def joined():
    """{session id: {"at": when it joined, "open": his message is waiting for its reply, "acting": when it last ran act}}"""
    d = common.read_json(JOINED, {})
    return {k: v for k, v in d.items() if isinstance(v, dict)} if isinstance(d, dict) else {}


def _put(d):
    os.makedirs(os.path.dirname(JOINED), exist_ok=True)
    common.write_json(JOINED, d)


def mark(sid, on):
    """Record a session joining (on) or leaving. Called by the hook, which knows the session's id."""
    d = joined()
    if on:
        d[sid] = {"at": common.now().isoformat(timespec="seconds")}
    else:
        d.pop(sid, None)
    _put(d)


def _note(sid, **kv):
    d = joined()
    if sid in d:
        d[sid].update(kv)
        _put(d)


def typed(data, text):
    """True when the prompt is words the owner typed, not a notice, a reminder or a message another session or tool put
    there (the hook's own origin fields when it gives them, and the shapes those notices take)."""
    for k in ("origin", "turnOrigin", "promptSource"):
        v = data.get(k)
        v = v.get("kind") if isinstance(v, dict) else v
        if v and str(v) not in ("human", "sdk", "user"):
            return False
    return not text.startswith(NOT_HIS)


def _mine(data):
    sid = str(data.get("session_id") or "")
    if not sid or data.get("agent_id") or data.get("agent_type") or sid not in joined():
        return ""
    return sid


def _save(turns):
    d = chat.load()
    d["turns"] = turns[-chat.KEEP_TURNS:]
    common.write_json(chat.CHAT_JSON, d)


def _refresh(wait):
    """The page brought up to date (publish.py, as ready.py does for a desktop draft), hidden. wait False: started and left
    to finish by itself, so the owner's message is not held up; it ends when done."""
    if not os.path.exists(common.PUBLISH):
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        if wait:        # one already running (code 3, it stood down) may hold older words: this one runs when it is done
            import time
            end = time.time() + 90
            while True:
                code = subprocess.run([sys.executable, common.PUBLISH], capture_output=True, timeout=90, creationflags=flags).returncode
                if code != 3 or time.time() > end:
                    return code == 0
                time.sleep(2)
        try:
            subprocess.Popen([sys.executable, common.PUBLISH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=flags | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
        except OSError:
            subprocess.Popen([sys.executable, common.PUBLISH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def heard(data):
    """The owner's message in a joined session: added to the shared conversation; returns what the box said since this
    session last spoke, for the session to read before it answers."""
    sid = _mine(data)
    text = str(data.get("prompt") or "").strip()[:3000]
    if not sid or not text:
        return ""
    if not typed(data, text):           # not his words: never added, and the reply to it is not his conversation's
        _note(sid, open=False)
        return ""
    _note(sid, open=True, did={}, tries=0, kept="")     # a new message: what act did, follow-ups and kept words start over
    with chat._lock:
        turns = chat.load()["turns"]
        last = max((n for n, t in enumerate(turns) if t.get("desktop") == sid), default=-1)
        # what the box said since: the box's own talk, no card's (chat.box_turns, the box's own filter)
        since = chat.box_turns([t for t in turns[last + 1:] if not t.get("desktop")] if last >= 0 else turns)
        turns.append({"who": "you", "text": text, "at": common.now().isoformat(timespec="seconds"), "desktop": sid})
        _save(turns)
    _refresh(False)
    shown = since[-SHOW:]
    if not shown:
        return "Talk to your assistant: nothing new was said on the page since your last reply here."
    return ("Talk to your assistant: what was said on the page " + ("since your last reply here" if last >= 0 else "lately") +
            " (oldest first; this conversation and the page's are one):\n" + json.dumps(chat.thread(shown), ensure_ascii=False, indent=0))


def _reply_from(data):
    """The words of this message's reply: the hook's own copy when it gives one, else the text after his last message in
    the session's transcript."""
    said = data.get("last_assistant_message")
    if isinstance(said, str) and said.strip():
        return said.strip()
    parts = []
    try:
        with open(data.get("transcript_path") or "", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("isSidechain") or e.get("isMeta"):
                    continue
                c = (e.get("message") or {}).get("content")
                if e.get("type") == "user" and isinstance(c, str):
                    parts = []                  # his message: the reply starts after it
                elif e.get("type") == "assistant" and isinstance(c, list):
                    if any(isinstance(b, dict) and b.get("type") == "tool_use" for b in c):
                        parts = []              # words before a step it took are its working, not the answer
                    parts += [str(b.get("text") or "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
    except OSError:
        return ""
    return "\n\n".join(p.strip() for p in parts if p.strip())


def checked(said, did):
    """The box's own checks on a reply's words (as chat.handle runs them), given what act did in this message: (words to
    show, the program's lines, sentences it only promised)."""
    made, lines = int(did.get("made") or 0), list(did.get("lines") or [])
    false_claim = false_done = False
    if did.get("drafts"):
        # an email's own words are never shown in the chat: they are on the page, in Drafts
        bodies = did.get("bodies") or []
        if any(len(b) > 40 and (b[:40] in said or b[-40:] in said) for b in bodies) or len(said) > 600 or made != did["drafts"]:
            said = ""
    elif chat.claims_draft(said) and not made:
        said, false_claim = "", True            # it says it put an email on the page, but no draft ACTION put one there
    if did.get("sends"):
        said = ""                               # what was sent or changed is said by the program's own lines alone
    elif chat.claims_done(said) and not did.get("sent_ok") and not did.get("changed") and not made:
        said, false_done = "", True             # it says it sent or changed something no ACTION line did
    owed = chat.promises(said, bool(made), bool(did.get("task")))
    if owed:
        said = " ".join(x for x in re.split(r"(?<=[.?!])\s+", said or "") if x.strip() not in owed).strip()
    waiting = int(did.get("waiting") or 0)
    if waiting:
        lines.append(f"I put {waiting} email{'s' if waiting != 1 else ''} in Drafts, in the Email part of your page; "
                     "it goes when you press Send there or tell me to send it.")
    elif false_claim:
        lines.append(chat.NO_DRAFT_SAYS)
    if false_done:
        lines.append(chat.NOT_DONE_SAYS)
    return said, lines, owed


def _join(kept, words):
    """What was kept from earlier in this message, then the new words' sentences it does not already hold."""
    have = set(re.split(r"(?<=[.?!])\s+", kept)) if kept else set()
    new = " ".join(x for x in re.split(r"(?<=[.?!])\s+", words or "") if x and x not in have)
    return " ".join(x for x in (kept, new) if x)


def said(data):
    """The reply in a joined session, after the box's own checks: added after his message, or put in place of the one
    already added for it (a reply held by a check and finished later is still one reply). A sentence promising what no
    ACTION did sends the session back to do it now, as the box runs again (up to chat.FOLLOW_UPS times); after that it
    becomes a job for the next check, as in the box. Returns the hook's answer when the session is sent back, else ''."""
    sid = _mine(data)
    st = joined().get(sid) or {}
    raw = _reply_from(data)[-3000:] if sid and st.get("open") else ""
    if not raw:
        return ""
    words, lines, owed = checked(raw, st.get("did") or {})
    kept, tries, back = str(st.get("kept") or ""), int(st.get("tries") or 0), ""
    if owed and tries < chat.FOLLOW_UPS:
        _note(sid, tries=tries + 1, kept=_join(kept, words))
        back = json.dumps({"decision": "block", "reason": (
            "(your own next step, now, in this same message: do it and run desk.py act with the ACTION lines that do it; "
            "if it cannot be done, say plainly what is missing; never say you will do it later) " + " ".join(owed))})
    elif owed:
        his, _at = _words_of(sid)
        chat.queue_job(" ".join(owed)[:600], his, None)
        lines.append(chat.QUEUED_SAYS)
    text = " ".join(dict.fromkeys(p for p in [_join(kept, words)] + lines if p))
    if not text:
        return back
    with chat._lock:
        turns = chat.load()["turns"]
        me = [n for n, t in enumerate(turns) if t.get("desktop") == sid]
        turn = {"who": "assistant", "text": text, "at": common.now().isoformat(timespec="seconds"), "desktop": sid}
        if me and turns[me[-1]].get("who") == "assistant":
            turns[me[-1]] = turn
        else:
            turns.append(turn)
        _save(turns)
    _refresh(not back)
    return back


def _words_of(sid):
    for t in reversed(chat.load()["turns"]):
        if t.get("desktop") == sid and t.get("who") == "you":
            return str(t.get("text") or ""), t.get("at")
    return "", None


def his_words():
    """(text, at, session) of the owner's latest message in the session that is running act now (the hook noted it a moment ago, and
    the note is used once), as the hook recorded it; ("", None, None) when there is none: no words from another session count."""
    import datetime as dt
    d, sid, best = joined(), None, ""
    for k, v in d.items():
        if str(v.get("acting") or "") > best:
            sid, best = k, str(v["acting"])
    if not sid or (common.now() - dt.datetime.fromisoformat(best)).total_seconds() > 60:
        return "", None, None
    d[sid].pop("acting", None)
    _put(d)
    return _words_of(sid) + (sid,)


def act(lines):
    """ACTION lines, done by the box's own handling (chat._do_all) with his latest words as their authority. Returns the
    program's own lines, which the session says as they are."""
    _, _, acts = chat._split(lines)
    if not acts:
        return "No ACTION line was given, so nothing was done."
    text, at, sid = his_words()
    when = common.now()
    chat._batch[0] = "desk-" + when.strftime("%Y%m%d-%H%M%S-%f")
    chat._scan_note[0] = None
    chat._made_now.clear()
    chat._sent_now.clear()
    chat._typed[0] = at         # his words count only while fresh (rule B11), timed from when the hook recorded them
    import tools
    out = []
    asides = [a for a in acts if isinstance(a, dict) and a.get("type") in ("card", "look")]
    if asides:
        out.append("A card or look line is for the page's own runs; here, answer or search directly.")
    setups = [a for a in acts if tools.is_setup(a)]
    for a in setups[:chat.MOST_ACTIONS]:
        out.append(f"setup {' '.join(tools.setup_args(a))[:200]}: {tools.run_setup(tools.setup_args(a))}")
    rest = [a for a in acts if a not in asides and a not in setups]
    changed, extra = chat._do_all(rest, text, when) if rest else ([], "")
    made = [i for i in changed if str(i.get("source_key") or "").startswith("live:ready-")]
    gone = {x.get("id") for x in chat._sent_now if x.get("what") == "email" and x.get("ok")}
    waiting = [i for i in made if i.get("id") not in gone]
    drafts = [a for a in rest if (a or {}).get("type") == "draft"]
    if sid:             # what this message's ACTIONs did, for the box's checks on the reply (said)
        did = (joined().get(sid) or {}).get("did") or {}
        did.update({"made": int(did.get("made") or 0) + len(made), "waiting": int(did.get("waiting") or 0) + len(waiting),
                    "drafts": int(did.get("drafts") or 0) + len(drafts),
                    "bodies": (did.get("bodies") or []) + [str(a.get("body") or "")[:3000] for a in drafts],
                    "sends": bool(did.get("sends")) or any((a or {}).get("type") in ("send", "text_send", "calendar") for a in rest),
                    "sent_ok": bool(did.get("sent_ok")) or any(x.get("ok") for x in chat._sent_now),
                    "changed": int(did.get("changed") or 0) + len(changed),
                    "task": bool(did.get("task")) or any((a or {}).get("type") == "task" for a in rest),
                    "lines": (did.get("lines") or []) + ([extra] if extra else [])})
        _note(sid, did=did)
    if waiting:
        out.append(f"I put {len(waiting)} email{'s' if len(waiting) != 1 else ''} in Drafts, in the Email part of your page; "
                   "it goes when you press Send there or tell me to send it.")
    elif changed:
        out.append(f"Done on the page: {len(changed)} card{'s' if len(changed) != 1 else ''} changed.")
    if extra:
        out.append(extra)
    if chat._scan_note[0]:          # a rule just saved went over the open cards: its Undo shows with his message on the page
        with chat._lock:
            turns = chat.load()["turns"]
            for t in reversed(turns):
                if t.get("desktop") and t.get("who") == "you":
                    t["scan"] = chat._scan_note[0]
                    break
            _save(turns)
    if changed or chat._scan_note[0]:
        _refresh(True)
    return " ".join(out) or "Done."


def hook(event):
    """The plugin's hook hands the hook's JSON here; for UserPromptSubmit the box's latest talk goes back as context."""
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return
    if event == "heard":
        ctx = heard(data)
        if ctx:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}))
    elif event == "said":
        back = said(data)
        if back:
            print(back)
    elif event in ("join", "leave"):
        sid = str(data.get("session_id") or "")
        if sid and not data.get("agent_id"):
            mark(sid, event == "join")
    elif event == "acting":         # this session is about to run act: its own words, and only its own, are the authority
        sid = _mine(data)
        if sid:
            _note(sid, acting=common.now().isoformat(timespec="seconds"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    arg = sys.argv[1:2]
    if arg in (["heard"], ["said"], ["join-hook"], ["leave-hook"], ["act-hook"]):
        hook({"act-hook": "acting"}.get(arg[0], arg[0].replace("-hook", "")))
    elif arg == ["join"]:       # the hook recorded this session a moment ago, before this command ran
        import datetime as dt
        newest = max((str(v.get("at") or "") for v in joined().values()), default="")
        fresh = bool(newest) and (common.now() - dt.datetime.fromisoformat(newest)).total_seconds() < 120
        print("This session is now Talk to your assistant: what you say here and what I answer show in the box on your page."
              if fresh else "This session could not be joined: the assistant plugin's hook did not record it. Nothing was changed.")
    elif arg == ["leave"]:
        print("This session no longer shares Talk to your assistant.")
    elif arg == ["act"]:
        if sys.argv[2:]:
            with open(sys.argv[2], encoding="utf-8") as f:
                print(act(f.read()))
        else:
            print(act(sys.stdin.read()))
    else:
        print(__doc__)
