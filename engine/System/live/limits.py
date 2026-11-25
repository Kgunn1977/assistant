r"""Time limits, so a pass can never hang the schedule.

Three layers:
  1. every step has its own limit (a source fetch, a filing script, a Claude
     run, the page refresh), and no step is given more time than
     the pass has left;
  2. the pass stops starting new work at PASS_LIMIT and finishes cleanly: what
     it did not reach is left for the next pass, which is 15 minutes away;
  3. a watchdog ends the whole process at HARD_LIMIT whatever it is doing,
     after writing the problem to the health record and releasing the lock.
And gather.take_lock ends a pass still holding the lock past STALE_LOCK, so
the next one always starts.

The scheduled task runs at below-normal priority, where a busy machine can
starve it (on 11/10/26 a pass got 26 seconds of processor in 38 minutes).
raise_priority() puts the pass and everything it starts at normal priority.
"""
import ctypes
import os
import subprocess
import threading
import time

PASS_LIMIT = 11 * 60     # no new work starts after this many seconds
HARD_LIMIT = 13 * 60     # the process is ended here, whatever it is doing
STALE_LOCK = HARD_LIMIT + 90

SOURCE = {"email": 150, "calendar": 90, "sms": 120}       # a taught connection type says its own (SECONDS)
FOLLOW = 120             # each filing script after new mail
SYNC = 120               # the mail's slow work, its own step after the new mail and its filing
RELOAD = 120             # the full history reload's own step (Settings, Tools), after the new mail and its filing
CATALOG = 480            # a portion of the setup's envelope catalog (catalog.py): the whole gathering while it is built
LOOKBACK = 120           # the look-back for today's new senders and topics (lookback.py), before the judge
SCRIPT = 180             # an engine script run for an AI step (payload, commit)
AI = 300                 # one Claude run
PUBLISH = 90             # the page refresh
ANSWER_AI = 60           # reading one typed answer

_state = {"start": time.time(), "step": "starting", "pass_id": None}


def begin(pass_id):
    _state.update(start=time.time(), step="starting", pass_id=pass_id)


def step(name):
    _state["step"] = name
    try:            # kept in the pass lock too, so a pass that ends suddenly is said with the step it was in (gather.take_lock)
        import common
        held = common.read_json(common.LOCK) or {}
        if held.get("pid") == os.getpid():
            held["step"] = name
            common.write_json(common.LOCK, held)
    except Exception:  # noqa: BLE001  a label never stops a pass
        pass


def current_step():
    return _state["step"]


def used():
    return time.time() - _state["start"]


def left():
    return PASS_LIMIT - used()


def enough(seconds):
    """Is there time left to start something that needs this long?"""
    return left() >= seconds


def cap(seconds):
    """A step's limit, never more than the pass has left (and never under 5)."""
    return max(5, min(seconds, left()))


def finish_cap(seconds):
    """The page refresh's limit: it finishes the pass, so it may run past PASS_LIMIT, up to a minute before HARD_LIMIT."""
    return max(5, min(seconds, HARD_LIMIT - 60 - used()))


def raise_priority():
    """Normal priority for this process; what it starts inherits it."""
    try:
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x00000020))
    except Exception:  # noqa: BLE001
        return False


def end_tree(pid):
    """End a process and everything it started."""
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        pass


def watchdog(on_limit):
    """Start the backstop. At HARD_LIMIT it calls on_limit(step, seconds used),
    which must record the problem and release the lock; then the process and
    everything it started is ended."""
    def run():
        while used() < HARD_LIMIT:
            time.sleep(min(5, max(0.2, HARD_LIMIT - used())))
        try:
            on_limit(current_step(), used())
        finally:
            end_tree(os.getpid())
            os._exit(4)
    t = threading.Thread(target=run, name="pass-watchdog", daemon=True)
    t.start()
    return t
