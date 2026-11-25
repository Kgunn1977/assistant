r"""The live listener: acts on the owner's answers the moment they give them.

    pythonw listen.py        runs until stopped; started at sign-in by the task "Assistant live listener", the one background job

The owner's page is served from this computer, from their web host, or from both (publish.hosting()). When
this computer serves it, the page server (local_site.py) runs here as threads of this program. For a web host
it holds one line open to the site (its address from the personal folder, then /api/wait, with the feed key).
Either page answers the moment the owner presses a button or saves their words. This program then
  1. marks the card "working on it",
  2. hands the answer to the engine (System\live\answers.py, act_on_answer),
  3. sends the changed items and the result back to the page.
Each time a wait comes back (about every 25 seconds when nothing happens) it also looks at the dates of
the roadmap piece's files, when that optional piece is applied to any project, and sends the page a
roadmap that changed (roadmaps.py).
While nothing happens it sits inside one waiting network call and uses no processor. The engine
decides whether an answer needs thinking, and the RSI jobs' runs are the engine's, under their own daily cap. One copy runs at a time. Every event
is one line in state\listen.log. The feed key is never printed or logged.
It also runs the 15-minute check (System\live\pass.py) on its own thread, each time as a separate hidden program
it waits for (passes()), so a check that hangs or crashes never takes the page down with it. And after each answer it
runs the RSI jobs a press queued (rsi_worker(), System\live\rsi_loop.py) on a thread of their own.
"""
import datetime as dt
import json
import os
import queue
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish  # noqa: E402  the same folder's sender: settings, building the feed, answer shapes

ENGINE = os.path.join(publish.ROOT, "System", "live")
LOG = os.path.join(publish.STATE, "listen.log")
ONE_COPY = os.path.join(publish.STATE, "listen.lock")
WAIT_TIMEOUT = 75            # the site holds the line about 25 seconds; this is the give-up time
NOT_ACTED = "Saved. I couldn't act on it just now. I'll do it the next time I check for messages."
PASS_EVERY = 15 * 60         # a check starts this long after the last one started (start to start)
PASS_FIRST = 2 * 60          # the soonest a check starts after this program starts
PASS_MOST = 20 * 60          # a check still running after this is ended with everything it started (pass.py ends itself sooner)
PASS_BUSY = 3                # pass.py's answer when another check (one run by hand) still holds the lock

ALL = []                     # every place the page is served from (publish.targets())
jobs = queue.Queue()
state_lock = threading.Lock()
acted_on = {}                # item key -> the answer the engine acted on, so an Undo can be passed on at once


def problem(key, text):
    """A trouble the owner should be able to see: in the listener's own log, in the error log, and on the page's status line
    (publish.note_problem) until the same thing works again."""
    log(text)
    try:
        publish.note_problem(key, text)
    except BaseException:  # noqa: BLE001  recording a trouble never makes another
        pass


def fine(key):
    try:
        publish.clear_problem(key)
    except BaseException:  # noqa: BLE001
        pass


def log(text):
    os.makedirs(publish.STATE, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {text}\n")


def only_one_copy():
    """Keep a lock on a file for as long as this program lives; a second copy cannot take it."""
    import msvcrt
    os.makedirs(publish.STATE, exist_ok=True)
    handle = open(ONE_COPY, "a+")
    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return None
    return handle


def site(cfg, path, body=None, since=None, timeout=publish.TIMEOUT):
    """One request with the feed key. Returns the reply, or raises. This computer's own page is asked directly."""
    if cfg.get("local"):
        import local_site
        if path == "wait":
            return local_site.wait(-1 if since is None else since)
        if path == "feed":
            return local_site.take_feed(body) or {}
        return local_site.mark((body or {}).get("marks") or [])
    url = cfg["site"].rstrip("/") + "/api/" + path
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"X-Brief-Key": cfg["feed_key"], "Content-Type": "application/json; charset=utf-8",
               "Accept": "application/json", "User-Agent": "live-page-listen/1"}
    if since is not None:
        headers["X-Brief-Since"] = str(since)
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def load_state(cfg):
    s = publish.read_json(cfg["state"]) or {}
    return {"delivered": s.get("delivered") or {}, "actions": s.get("actions") or {},
            "to_remove": s.get("to_remove") or []}


def engine():
    """The engine's function for acting on an answer, or None with the reason logged."""
    try:
        if ENGINE not in sys.path:
            sys.path.insert(0, ENGINE)
        import answers
        fine("engine")
        return answers.act_on_answer
    except BaseException as e:  # noqa: BLE001  the engine refusing to load must not stop the listener
        problem("engine", f"the engine's answer function could not be loaded: {type(e).__name__}: {str(e)[:200]}")
        return None


def push(cfg, changed, marks):
    """Send the current items (with the ones just changed) to every place the page is served from, so a press
    on one shows on the other; how far the answer has got goes to the page it was given on."""
    docs, _ = publish.build(publish.ITEMS_JSON, changed)
    ok = False
    for where in ALL or [cfg]:
        mine = where is cfg or where["name"] == cfg["name"]
        try:
            reply = site(where, "feed", {"docs": docs, "clear": [], "progress": marks if mine else []})
            ok = ok or (mine and bool(reply.get("ok")))
        except Exception:  # noqa: BLE001  the other page being away never loses this one's result
            if mine:
                raise
    return ok


def act(cfg, act_on_answer, key, rec):
    """One answer, start to finish. Runs on the worker thread."""
    t0 = time.time()
    at = rec.get("at")
    try:
        site(cfg, "progress", {"marks": [[key, at, "working", ""]]})
    except Exception as e:  # noqa: BLE001
        log(f"{rec.get('id')}: could not mark it as being worked on ({type(e).__name__})")
    answer = publish.engine_file(rec)

    def on_update(items):
        try:
            push(cfg, items, [[key, at, "working", ""]])
        except Exception:  # noqa: BLE001
            pass

    out = None
    if str(rec.get("id") or "").startswith("rm:"):      # a press on a roadmap: queued for the project's main session (roadmap_press.py)
        try:
            import roadmap_press
            out = dict(roadmap_press.handle(answer), items=[])
        except BaseException as e:  # noqa: BLE001
            out = {"ok": False, "error": f"Not saved on the roadmap: {type(e).__name__}.", "items": []}
    elif act_on_answer:
        try:
            out = act_on_answer(answer, on_update=on_update)
        except BaseException as e:  # noqa: BLE001
            out = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}", "items": []}
    acted = time.time() - t0
    ok = bool(out and out.get("ok"))
    refusal = str((out or {}).get("error") or "").startswith("Not saved on the roadmap")      # a press the roadmap may not take is not a fault
    if ok:
        fine("answer")
    elif not refusal:
        problem("answer", f"an answer could not be acted on: {(out or {}).get('error') or 'the engine is not available'}"[:300])
    words = (out or {}).get("result") if ok else ((out or {}).get("error") if str(rec.get("id") or "").startswith("rm:") else NOT_ACTED)
    if ok:
        with state_lock:                 # the engine has it; the 15-minute pass must not hand it over again
            s = load_state(cfg)
            s["delivered"][key] = at
            s["actions"][key] = rec.get("action")
            publish.write_json(cfg["state"], s)
            acted_on[(cfg["name"], key)] = rec
    changed = (out or {}).get("items") or []
    as_of = next((str(i.get("updated_at") or "") for i in changed if isinstance(i, dict) and i.get("id") == rec.get("id")), "")
    try:
        push(cfg, changed, [[key, at, "done" if ok else "failed", words or "Done", as_of]])
        shown = "result on the page"
    except Exception as e:  # noqa: BLE001
        shown = f"result NOT sent to the page ({type(e).__name__})"
    why = "" if ok else f" FAILED: {(out or {}).get('error') or 'the engine is not available'}"
    log(f"{rec.get('id')} {rec.get('action')}: acted in {acted:.1f}s, {shown} after {time.time() - t0:.1f}s"
        + (", thought" if (out or {}).get("thought") else "") + why)


def take_back(cfg, act_on_answer, key, rec):
    """The owner pressed Undo on an answer the engine had already acted on: tell the engine now."""
    t0 = time.time()
    out = None
    if act_on_answer:
        try:
            out = act_on_answer({"id": rec.get("id"), "action": "reopen", "text": "", "page_action": "reopen",
                                 "label": "Undo", "at": dt.datetime.now().isoformat(timespec="seconds")})
        except BaseException as e:  # noqa: BLE001
            out = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}", "items": []}
    ok = bool(out and out.get("ok"))
    with state_lock:                     # either way it is no longer an answer we hold as handed over
        s = load_state(cfg)
        if ok:
            s["delivered"].pop(key, None)
            s["actions"].pop(key, None)
        publish.write_json(cfg["state"], s)
    try:
        push(cfg, (out or {}).get("items") or [], [])
    except Exception:  # noqa: BLE001
        pass
    log(f"{rec.get('id')} undo: " + (f"taken back in {time.time() - t0:.1f}s" if ok else
                                     "could not be taken back now; the next check will (" + str((out or {}).get("error"))[:120] + ")"))


def worker():
    act_on_answer = engine()
    while True:
        cfg, key, rec = jobs.get()
        if act_on_answer is None:
            act_on_answer = engine()
        try:
            if rec.get("_undo"):
                take_back(cfg, act_on_answer, key, rec)
                continue
            act(cfg, act_on_answer, key, rec)
        except BaseException as e:  # noqa: BLE001
            problem("answer", f"an answer ran into trouble and waits for the next time I check for messages ({type(e).__name__}: {str(e)[:200]})")
        finally:
            rsi_due.set()           # the press is handled: the RSI worker looks at its queue


rsi_due = threading.Event()         # set after each answer is handled, and once at start


def rsi_worker():
    """The RSI jobs a press queued (System\\live\\rsi_loop.py), run here after the press is handled, one section at a time, in
    this thread of their own: never in the answers' worker or the chat's queue, so neither waits for them. It sleeps until
    an answer has been handled; no timer. A rule change card it makes is sent to the page at once."""
    while True:
        rsi_due.wait()
        rsi_due.clear()
        try:
            if ENGINE not in sys.path:
                sys.path.insert(0, ENGINE)
            import rsi_loop
            made = rsi_loop.run()
            fine("rsi")
            if made:
                push(ALL[0], made, [])
                log(f"rule change card{'s' if len(made) > 1 else ''} made: {', '.join(str(c.get('id')) for c in made)}")
        except BaseException as e:  # noqa: BLE001  the RSI loop never stops the listener; its jobs wait in their queue
            problem("rsi", f"my learning jobs could not be run now ({type(e).__name__}: {str(e)[:200]}); they wait for the next answer")


def new_answers(cfg, answers, queued):
    """Answers on the page that nobody has acted on yet."""
    with state_lock:
        delivered = load_state(cfg)["delivered"]
    out = []
    for key, rec in (answers or {}).items():
        if not isinstance(rec, dict) or not rec.get("id") or not rec.get("action"):
            continue
        mark = (key, rec.get("at"))
        if delivered.get(key) == rec.get("at") or mark in queued or rec.get("status") in ("done", "working"):
            continue
        queued.add(mark)
        out.append((key, rec))
    return out


tidied = [0.0]               # when presses on roadmaps were last tidied and retried


def tidy_presses():
    """Every ten minutes: drop presses whose effect the roadmap shows, try again those unsent for 15 minutes (roadmap_press.py)."""
    if time.time() - tidied[0] < 600:
        return
    tidied[0] = time.time()
    try:
        import roadmap_press
        started = roadmap_press.retry_due()
        fine("presses")
        if started:
            log("roadmap presses tried again for: " + ", ".join(started))
    except BaseException as e:  # noqa: BLE001
        problem("presses", f"what you pressed on a roadmap could not be tidied ({type(e).__name__})")


roadmaps_seen = []            # the roadmap piece's files as last looked at; empty until the first look


def roadmaps_changed():
    """True when a project's plain copy of its roadmap, or the list of projects, changed since the last look.
    One look at each file's date; with the piece applied to nothing there is nothing to look at."""
    try:
        import roadmaps
        now = roadmaps.signature()
    except BaseException:  # noqa: BLE001
        return False
    with state_lock:
        first, same = not roadmaps_seen, roadmaps_seen == [now]
        roadmaps_seen[:] = [now]
    return not first and not same


def line(cfg):
    """Listen to one place the page is served from, for as long as this program runs."""
    wait, av, queued = 2, -1, set()
    while True:
        try:
            reply = site(cfg, "wait", since=av, timeout=WAIT_TIMEOUT)
            if wait > 2:
                log(f"line to {cfg['name']} is open again")
            wait = 2
            if cfg is ALL[0]:
                tidy_presses()
            if roadmaps_changed():                    # between waits: a roadmap changed, so the page is sent it now
                try:
                    push(cfg, [], [])
                    log("a roadmap changed: sent to the page")
                    fine("page push")
                except BaseException as e:  # noqa: BLE001  the next pass sends it
                    problem("page push", f"a roadmap changed but could not be sent to the page now ({type(e).__name__}); I'll send it the next time I check for messages")
            av = reply.get("av", av)
            for key, rec in new_answers(cfg, reply.get("answers"), queued):
                log(f"{rec.get('id')} {rec.get('action')}: answer arrived")
                jobs.put((cfg, key, rec))
            # Only an Undo the owner pressed counts; an answer the engine's pass cleared from the page is not one.
            undone = reply.get("undone") or {}
            with state_lock:
                delivered = load_state(cfg)["delivered"]
            for key, info in (undone.items() if isinstance(undone, dict) else []):
                at = (info or {}).get("at")
                if (key, at, "undo") in queued or delivered.get(key) != at:
                    continue
                queued.add((key, at, "undo"))
                rec = acted_on.pop((cfg["name"], key), None) or {"id": key, "at": at}
                log(f"{rec.get('id')} undo: the owner took the answer back")
                jobs.put((cfg, key, dict(rec, _undo=True)))
            if not reply.get("held"):
                time.sleep(2.5)                       # the line was not held: check every few seconds
        except urllib.error.HTTPError as e:
            if wait == 2:
                log(f"{cfg['name']} answered {e.code}; trying again with longer pauses")
            time.sleep(wait if e.code not in (403, 429) else max(wait, 60))
            wait = min(wait * 2, 60)
        except Exception as e:  # noqa: BLE001
            if wait == 2:
                log(f"line to {cfg['name']} dropped ({type(e).__name__}); trying again with longer pauses")
            time.sleep(wait)
            wait = min(wait * 2, 60)


def refresh_once():
    """Once, when the listener starts: the page brought up to date from what is there now (the health record, the checks
    switched on or off), so it never keeps showing troubles from before it stopped when no pass runs to refresh it."""
    import subprocess
    time.sleep(3)
    try:
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish.py")],
                           capture_output=True, text=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode:
            log(f"refresh at start failed: {((r.stdout or '') + (r.stderr or '')).strip()[-300:]}")
    except Exception as e:  # noqa: BLE001  the next pass refreshes it
        log(f"refresh at start failed ({type(e).__name__})")


def first_pass_at():
    """When the first check runs: 15 minutes after the last check started (from the health record), but never sooner than
    PASS_FIRST from now, so a restart of this program neither adds a check nor skips one."""
    soonest = time.time() + PASS_FIRST
    try:
        last = (publish.read_json(publish.HEALTH_JSON) or {}).get("last_pass") or {}
        started = dt.datetime.fromisoformat(str(last.get("started"))).timestamp()
        return max(soonest, started + PASS_EVERY)
    except (TypeError, ValueError, AttributeError, OSError):
        return soonest


def run_pass():
    """One check, start to finish: pass.py as its own hidden program, waited for here. Only its own lock decides whether it
    runs (one at a time; a check run by hand makes it answer PASS_BUSY), and only its own Settings check decides whether it
    gathers (Sync off stands it down). Returns its exit code, or None when it was ended for running past PASS_MOST."""
    import subprocess
    p = subprocess.Popen([sys.executable, os.path.join(ENGINE, "pass.py")], cwd=ENGINE, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        _out, err = p.communicate(timeout=PASS_MOST)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        p.communicate()
        problem("pass", f"a check was still running after {PASS_MOST // 60} minutes and was ended; the next one starts on time")
        return None
    said = (err or b"").decode("utf-8", "replace").strip()
    if p.returncode in (0, PASS_BUSY) or (p.returncode == 1 and "Traceback" not in said):   # 1 alone: the check recorded what went wrong
        fine("pass")
    else:
        last = said.splitlines()[-1][-300:] if said else ""          # the error itself, on the one log line
        problem("pass", f"a check ended without finishing (exit {p.returncode}){': ' + last if last else ''}")
    return p.returncode


def passes():
    """The 15-minute check, run by this program instead of a job of its own. A check that fails, hangs or crashes is its own
    program's trouble: this thread logs it and carries on, and nothing here can stop the page or the answers."""
    due = first_pass_at()
    while True:
        try:
            wait = due - time.time()
            if wait > 0:
                time.sleep(min(wait, 60))
                continue
            due = time.time() + PASS_EVERY
            t0 = time.time()
            code = run_pass()
            log(f"check {'ended at its limit' if code is None else 'skipped: another check is running' if code == PASS_BUSY else f'done (exit {code})'}"
                f" in {time.time() - t0:.0f}s")
        except BaseException as e:  # noqa: BLE001  a check that cannot start never stops the listener
            problem("pass", f"a check could not be started ({type(e).__name__}: {str(e)[:200]}); the next one is tried on time")
            time.sleep(60)


def start_texts_link():
    """The link to Google Messages (the engine's textlink.py) runs with this program: started here, hidden; it ends when this
    program ends (its input closes), and is stopped on the way out."""
    try:
        if ENGINE not in sys.path:
            sys.path.insert(0, ENGINE)
        import atexit
        import textlink
        if textlink.start():
            atexit.register(textlink.stop)
            log("texts link started")
        fine("texts link")
    except BaseException as e:  # noqa: BLE001  texts never stop the page
        problem("texts link", f"the texts link could not be started ({type(e).__name__}: {str(e)[:200]})")


def main():
    held = only_one_copy()
    if held is None:
        return 0                                      # another copy is already listening
    log("listener started")
    wait, serving = 2, False
    while True:
        try:
            if not serving and publish.hosting() in ("own_pc", "both"):
                import local_site
                local_site.start()                    # the page itself, on this computer's own address only
                serving = True
                log(f"this computer is serving the page at {local_site.address()}")
            ALL[:] = publish.targets()
            if ALL:
                break
            raise SystemExit("no page is set up yet")
        except (SystemExit, OSError) as e:            # settings missing or unusable, or the page's port is taken
            if wait == 2:
                log(f"cannot start listening: {e}")
            time.sleep(wait)
            wait = min(wait * 2, 60)
    start_texts_link()
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=rsi_worker, daemon=True).start()
    rsi_due.set()                                     # jobs left queued when this program last stopped
    threading.Thread(target=refresh_once, daemon=True).start()
    threading.Thread(target=passes, daemon=True).start()
    for cfg in ALL[1:]:
        threading.Thread(target=line, args=(cfg,), daemon=True).start()
    line(ALL[0])


if __name__ == "__main__":
    sys.exit(main())
