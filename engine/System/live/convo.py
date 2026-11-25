r"""The day's conversation: one Claude session for the conversation with the owner in the page's chat box (and his change
and undo requests), and one small session of its own for each card he talks on, resumed for that card's later replies.
Agreed shape of 11/17/26, item 5; cards apart since 11/23 (his plan: "each card is its own invisible session").

    run(kind, words, flags, model, timeout, key)   one job in today's session (key: a card's id, that card's own session);
                                                   returns (reply or None, why, seconds, report)

- One session a day: the first job of the day starts it fresh; every later job that day resumes it, so the session already
  holds the day's talk and the guardrails it was given, and Claude's own cache makes each later job cheaper to read.
- Trimmed when it grows: after MOST_JOBS jobs or MOST_CHARS characters a new session starts (each job still carries what it
  needs: the chat sends the latest stretch of its conversation, a typed answer sends its card).
- One job at a time, in the order they came: a job waits for the one before it to finish.
- Reading mail, texts and other messages stays in fresh short runs (ai_steps): they are not conversations.
Each job brings its own tools, instructions and model (flags); the session only carries the talk.
"""
import datetime as dt
import json
import os
import subprocess
import threading
import time

import common

STATE = os.path.join(common.paths.STATE, "convo.json")
CWD = os.path.join(common.paths.STATE, "convo")
MOST_JOBS = 40               # jobs in one session before a fresh one starts
MOST_CHARS = 250_000         # characters sent and received in one session before a fresh one starts

_turn = threading.Condition()
_queue = []                  # tickets of jobs waiting, in arrival order
_next = [0]


CARDS = os.path.join(common.paths.STATE, "convo_cards.json")     # {card id: that card's own session}
MOST_CARDS = 300            # card sessions kept; the ones talked in longest ago go first


def _record(key=None):
    if key:
        r = (common.read_json(CARDS, {}) or {}).get(key)
    else:
        r = common.read_json(STATE, {}) or {}
    return r if isinstance(r, dict) else {}


def _keep(key, rec):
    if not key:
        common.write_json(STATE, rec)
        return
    all_ = {k: v for k, v in (common.read_json(CARDS, {}) or {}).items() if isinstance(v, dict)}
    all_[key] = dict(rec, last=common.now().isoformat(timespec="seconds"))
    common.write_json(CARDS, dict(sorted(all_.items(), key=lambda kv: str(kv[1].get("last") or ""))[-MOST_CARDS:]))


def today_session(key=None):
    """{"day", "id", "jobs", "chars", "started"} for today, or a blank one when today has none or it has grown too big.
    key: a card's id: that card's own session, resumed for every later reply on it whatever the day (until it grows too big);
    it never holds the box's talk, and the box's session never holds a card's."""
    r, day = _record(key), dt.date.today().isoformat()
    if key and r.get("id") and int(r.get("jobs") or 0) < MOST_JOBS and int(r.get("chars") or 0) < MOST_CHARS:
        return r
    if r.get("day") != day or int(r.get("jobs") or 0) >= MOST_JOBS or int(r.get("chars") or 0) >= MOST_CHARS:
        return {"day": day, "id": None, "jobs": 0, "chars": 0, "trimmed": r.get("day") == day}
    return r


class _InTurn:
    """Waits for this job's turn (first come, first served), and lets the next one go after."""

    def __enter__(self):
        with _turn:
            me = _next[0]
            _next[0] += 1
            _queue.append(me)
            while _queue[0] != me:
                _turn.wait()
        return self

    def __exit__(self, *a):
        with _turn:
            _queue.pop(0)
            _turn.notify_all()


def run(kind, words, flags, model, timeout, key=None):
    """One job in today's session, or (key: a card's id) in that card's own session. flags: the job's own tools,
    instructions and settings (never --resume or --model)."""
    import ai_steps
    import settings_page
    with _InTurn():
        s = today_session(key)
        os.makedirs(CWD, exist_ok=True)
        t0 = time.time()
        settings_page.count_run()       # every Claude run counts toward the owner's daily limit
        for attempt in (0, 1):
            cmd = [ai_steps.claude_exe(), "-p", "--model", model, "--output-format", "json"] + list(flags)
            if s.get("id"):
                cmd += ["--resume", s["id"]]
            try:
                r = subprocess.run(cmd, input=words, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=timeout, cwd=CWD, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired:
                return None, f"no reply within {timeout} seconds", time.time() - t0, {}
            try:
                j = json.loads(r.stdout[r.stdout.index("{"):])
            except ValueError:
                j = {}
            gone = s.get("id") and "No conversation found" in (r.stdout + r.stderr + str(j.get("result") or ""))
            if gone and attempt == 0:
                s = dict(s, id=None, jobs=0, chars=0)      # the session is gone: today's talk starts again
                continue
            break
        secs = time.time() - t0
        if not j:
            return None, f"exit {r.returncode}: {(r.stderr or r.stdout)[:200]}", secs, {}
        if r.returncode or j.get("is_error"):
            return None, str(j.get("result") or j.get("subtype"))[:200], secs, j
        reply = j.get("result") or ""
        made = j.get("session_id") or s.get("id")
        rec = {"day": s["day"], "id": made, "jobs": int(s.get("jobs") or 0) + 1, "chars": int(s.get("chars") or 0) + len(words) + len(reply),
               "started": s.get("started") or common.now().isoformat(timespec="seconds"), "last": kind,
               "cost": round(float(s.get("cost") or 0) + float(j.get("total_cost_usd") or 0), 4)}
        _keep(key, rec)
        return reply, "", secs, j
