r"""The assistant's own program in the plugin: lay it down, turn it on and off, update it, take it off.

    python assistant.py lay-down  --root <folder> [--port N] [--sending yes|no]
    python assistant.py turn-on   --root <folder>       make the two hidden jobs (only after the person said yes)
    python assistant.py turn-off  --root <folder>       stop the listener, remove the two jobs
    python assistant.py status    --root <folder>
    python assistant.py update-plan  --root <folder>    what an update would do to each general file
    python assistant.py update-apply --root <folder> [--choices <file>] [--wait <minutes>]
                                                        waits (default 10 minutes) for a check already running to finish;
                                                        runs no pass (check-pass runs one when wanted)
    python assistant.py check-pass --root <folder>      one check pass by hand: the page stopped for it, then started again
    python assistant.py uninstall --root <folder> [--remove-data]
    python assistant.py adopt-plan --from <old folder> --root <folder>   an existing copy (System and Live) against the plugin
    python assistant.py adopt --from <old folder> --root <folder> [--choices <file>] [--no-jobs]
    python assistant.py adopt-back --root <folder>                        the way back from adopt, in one step

<folder> is the assistant's own folder (default Documents\Assistant): the program runs from <folder>\System, the
owner's data is in <folder>\Live, and <folder>\Shipped holds the general part exactly as last shipped (the base an
update merges against). The plugin's own copy of the general part is its engine folder. See reference\layout.md.
Everything started here runs hidden.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(PLUGIN, "engine")
DOCS = os.path.join(PLUGIN, "docs")                  # the manual; laid down beside System, the page serves it from there
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DEFAULT_ROOT = os.path.join(os.path.expanduser("~"), "Documents", "Assistant")


def say(*lines):
    for line in lines:
        print(line, flush=True)


def sha(path):
    """A file's checksum with Windows line endings read as plain ones: git on Windows often converts them when the
    plugin is installed, and an unchanged file must never look like one the owner changed. The package's own list
    (shipped_doc) is made the same way, so the two agree."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def _rm(path):
    def unlock(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if os.path.isdir(path):
        shutil.rmtree(path, onerror=unlock)


class Copy:
    """One laid-down copy of the assistant."""

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.system = os.path.join(self.root, "System")
        self.live = os.path.join(self.system, "live")
        self.page = os.path.join(self.system, "live_page")
        self.home = os.path.join(self.root, "Live")
        self.shipped = os.path.join(self.root, "Shipped")
        self.docs = os.path.join(self.root, "docs")
        self.install = os.path.join(self.home, "personal", "install.json")

    def engine(self):
        """The laid-down engine's setup steps, for this copy's home."""
        os.environ["ASSISTANT_LIVE_HOME"] = self.home
        if self.live not in sys.path:
            sys.path.insert(0, self.live)
        os.chdir(self.live)
        import setup_steps
        return setup_steps

    def jobs(self):
        got = read_json(os.path.join(self.home, "personal", "jobs.json"), {}) or {}
        if got.get("pass") and got.get("listener"):
            return [got["pass"], got["listener"]]
        tag = hashlib.sha1(os.path.normcase(os.path.abspath(self.home)).encode("utf-8")).hexdigest()[:6]
        return [f"Assistant live pass {tag}", f"Assistant live listener {tag}"]

    def jobs_on(self):
        r = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/NH"], capture_output=True, text=True, creationflags=HIDDEN)
        return [t for t in self.jobs() if f'"\\{t}",' in (r.stdout or "")]

    def processes(self, include_home=False):
        """Process ids of this copy's own programs that are running (listener, pass and what they start): only those
        whose command line names System\\live or System\\live_page (with include_home also its data folder), never
        anything else kept in System, and never this helper itself or any program above it (the shell or Claude session
        that started it): their command lines may name the same folders."""
        ps = ("Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, CommandLine | "
              "ConvertTo-Json -Compress")
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
                           capture_output=True, text=True, creationflags=HIDDEN)
        try:
            rows = json.loads(r.stdout or "[]")
        except ValueError:
            rows = []
        rows = rows if isinstance(rows, list) else [rows]
        parent = {row.get("ProcessId"): row.get("ParentProcessId") for row in rows if isinstance(row, dict)}
        mine, pid = set(), os.getpid()
        while pid and pid not in mine:                  # this helper and every program above it
            mine.add(pid)
            pid = parent.get(pid)
        wanted = [p.lower() + "\\" for p in (self.live, self.page) + ((self.home,) if include_home else ())]
        out = []
        for row in rows:
            if not isinstance(row, dict) or row.get("ProcessId") in mine:
                continue
            cmd = str(row.get("CommandLine") or "").lower().replace("/", "\\")       # a path written with / names the same folder
            if cmd and any(w in cmd for w in wanted):
                out.append(int(row["ProcessId"]))
        return out

    def stop_programs(self, include_home=False):
        """Stop this copy's own programs; with include_home also any program whose command line names its data folder
        (the short Claude runs it starts), never anything else."""
        pids = self.processes(include_home)
        for pid in pids:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=HIDDEN)
        return pids


SKIPPED = 3                     # pass.py's answer when another pass still holds the lock
PASS_WAIT_MINUTES = 10          # how long an update waits for a check already running before it says so and changes nothing


def _alive(pid):
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], capture_output=True, text=True,
                             creationflags=HIDDEN, timeout=20).stdout
    except (OSError, subprocess.SubprocessError, ValueError):
        return True                 # cannot tell: treated as running, so nothing is cut short
    return str(int(pid)) in out


def pass_running(c):
    """The minutes a check (pass) has been running when one holds the pass lock now, else None."""
    lock = read_json(os.path.join(c.home, "pass.lock"), None)
    if not isinstance(lock, dict) or not lock.get("pid") or not _alive(lock["pid"]):
        return None
    return max(0.0, (time.time() - float(lock.get("at") or time.time())) / 60)


def _hold_pass_lock(c):
    """Takes the pass lock for this helper, so a check the listener starts in the moments before its programs are stopped
    answers "another check is running" instead of being ended mid-run. True when held; False when a check took it first;
    None when a program that is gone left it (not held: the next check takes it over and logs that one)."""
    path = os.path.join(c.home, "pass.lock")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False if pass_running(c) is not None else None
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"pid": os.getpid(), "at": time.time(), "pass": "update", "step": "stopping the programs"}))
    return True


def release_pass(c):
    """Lets go of the pass lock wait_for_pass took, once this copy's programs are stopped (or the helper stops early)."""
    path = os.path.join(c.home, "pass.lock")
    if (read_json(path, None) or {}).get("pid") == os.getpid():
        try:
            os.remove(path)
        except OSError:
            pass


def wait_for_pass(c, minutes):
    """Waits while a check is running, up to the limit. Returns None when none is running (any more), with the pass lock
    then held by this helper (release_pass lets go of it once the programs are stopped); else the words for the owner:
    the update did not start and nothing was changed."""
    end = time.time() + minutes * 60
    ran, told = pass_running(c), False
    while True:
        if ran is None and _hold_pass_lock(c) is not False:
            return None
        ran = pass_running(c) or 0.0
        if not told:
            say("Your assistant is in the middle of a check; the update starts as soon as it finishes.")
            told = True
        if time.time() >= end:
            return (f"Not updated yet: your assistant's regular check has been running for {ran:.0f} minutes and has not "
                    f"finished, so the update did not start and nothing was changed. Run the update again once the check "
                    f"is done (it usually takes a few minutes).")
        time.sleep(min(10, max(1, end - time.time())))
        ran = pass_running(c)


def _copy_db(db, dest, tries=12):
    """The database's safety copy; the page's listener can hold it for a moment, so a held file is tried again for
    about a minute before the update gives up."""
    for i in range(tries):
        try:
            return shutil.copy2(db, dest)
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(5)


def _job_on(name):
    """True when this scheduled job exists and is switched on."""
    r = subprocess.run(["schtasks", "/Query", "/TN", name, "/FO", "LIST"], capture_output=True, text=True, creationflags=HIDDEN)
    return r.returncode == 0 and "disabled" not in (r.stdout or "").lower()


def pause_jobs(c):
    """Switches this copy's scheduled jobs off and ends what they are running, so neither a regular pass nor the job that
    keeps the listener going can start while the update works on the program and the database. Returns the jobs it
    switched off (resume_jobs switches those, and only those, back on)."""
    paused = []
    for name in c.jobs():
        if _job_on(name):
            subprocess.run(["schtasks", "/Change", "/TN", name, "/DISABLE"], capture_output=True, creationflags=HIDDEN)
            paused.append(name)
        subprocess.run(["schtasks", "/End", "/TN", name], capture_output=True, creationflags=HIDDEN)
    return paused


def resume_jobs(paused, only=None):
    for name in paused:
        if only is None or name == only:
            subprocess.run(["schtasks", "/Change", "/TN", name, "/ENABLE"], capture_output=True, creationflags=HIDDEN)


def jobs_back_on(c, tries=6, paused=None):
    """At the end of an update or a restore: this copy's own scheduled jobs switched on and checked (Windows may refuse the
    change while a pass is running: it is asked again). With paused (the jobs this run switched off itself): the listener's
    job always (an earlier update cut off can leave it off, and the page must be served), the timed pass only if this run
    switched it off; a pass the owner switched off stays off. Without paused, each job that exists. Returns the jobs still off."""
    have = c.jobs_on()
    if paused is not None:
        have = [n for n in have if n == c.jobs()[1] or n in paused]
    left = []
    for name in have:
        for i in range(tries):
            if _job_on(name):
                break
            subprocess.run(["schtasks", "/Change", "/TN", name, "/ENABLE"], capture_output=True, creationflags=HIDDEN)
            if i:
                time.sleep(3)
        else:
            if not _job_on(name):
                left.append(name)
    return left


HOLD_MINUTES = 20                       # an update's hold on the listener ends by itself after this, if the update was cut off


def _hold_path(c):
    return os.path.join(c.home, "state", "update_hold.json")


def hold_on(c):
    """The listener (restarted so the check pass also updates the page) answers no door that opens the database until
    hold_off: the extension's texts and the page wait, so nothing else holds the database while the check pass runs."""
    os.makedirs(os.path.dirname(_hold_path(c)), exist_ok=True)
    until = (dt.datetime.now() + dt.timedelta(minutes=HOLD_MINUTES)).isoformat(timespec="seconds")
    write_json(_hold_path(c), {"until": until, "pid": os.getpid()})


def hold_off(c):
    try:
        os.remove(_hold_path(c))
    except OSError:
        pass


def say_jobs(c, paused=None):
    left = jobs_back_on(c, paused=paused)
    if left:
        say("Could not switch back on: " + ", ".join(left) + ". Switch it on in Task Scheduler (or run turn-on); nothing runs on its own until then.")


def put_back(c, aside, names=("System", "Shipped", "docs")):
    """Puts the program back from an update's safety copy, file by file (a whole folder cannot be moved while anything has
    it open, even as its working folder). The copy's own programs (the page's listener, a pass) are stopped first. Each file
    the failed update changed or added is deleted outright, and the safety copy's file is copied into its place. Returns
    the parts put back, and the files that could not be replaced (each still held open by something)."""
    import filecmp
    for name in c.jobs():
        subprocess.run(["schtasks", "/End", "/TN", name], capture_output=True, creationflags=HIDDEN)
    c.stop_programs()

    def set_aside(path, rel):
        """The failed update's file deleted; True when it is gone."""
        for i in range(6):          # a program just stopped can take a moment to let go of its files
            try:
                os.remove(path)
                return True
            except PermissionError:
                if i < 5:
                    c.stop_programs()
                    time.sleep(2)
        return False

    done, stuck = [], []
    for name in names:
        src, here = os.path.join(aside, name), os.path.join(c.root, name)
        if not os.path.isdir(src):
            continue
        for dirpath, _dirs, files in os.walk(here, topdown=False):      # what the safety copy does not have
            for fn in files:
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, c.root)
                if not os.path.isfile(os.path.join(aside, rel)) and not set_aside(path, rel):
                    stuck.append(rel)
            rel = os.path.relpath(dirpath, c.root)
            if dirpath != here and not os.path.isdir(os.path.join(aside, rel)) and not os.listdir(dirpath):
                try:
                    os.rmdir(dirpath)
                except OSError:
                    pass
        for dirpath, _dirs, files in os.walk(src):                      # the safety copy's files, into place
            os.makedirs(os.path.join(c.root, os.path.relpath(dirpath, aside)), exist_ok=True)
            for fn in files:
                from_ = os.path.join(dirpath, fn)
                rel = os.path.relpath(from_, aside)
                path = os.path.join(c.root, rel)
                if os.path.isfile(path):
                    if filecmp.cmp(from_, path, shallow=False):
                        continue
                    set_aside(path, rel)
                try:
                    shutil.copy2(from_, path)
                except OSError:
                    stuck.append(rel)
        done.append(name)
    return done, sorted(set(stuck))


def restore(c, aside):
    """After an update that failed and could not put itself back: the program back from its safety copy, then the page
    and the background job running again. No pass is run (check-pass runs one by hand). The database is left as it is (it
    holds the mail gathered since); it is checked to open, before the page comes back."""
    if not os.path.isdir(os.path.join(aside, "System")):
        say(f"Refused: {aside} holds no System folder, so it is not an update's safety copy. Nothing was changed.")
        return 1
    done, stuck = put_back(c, aside)
    say("Put back from " + aside + ": " + ", ".join(done) + ". What the failed update had put there was deleted.")
    if stuck:
        say("Could not be replaced (still held open by another program): " + ", ".join(stuck[:20])
            + (f" and {len(stuck) - 20} more" if len(stuck) > 20 else "") + ". Close what holds them and run restore again.")
    paused = pause_jobs(c)                  # nothing else has the database while it is checked to open
    c.stop_programs()
    db_ok = True
    try:
        import duckdb
        con = duckdb.connect(os.path.join(c.home, "Resources", "Database", "assistant.duckdb"), read_only=True)
        n = con.execute("SELECT count(*) FROM messages").fetchone()[0]
        con.close()
        say(f"Database: opens, {n} messages.")
    except Exception as e:  # noqa: BLE001
        db_ok = False
        say(f"Database: could not be read ({type(e).__name__}: {e}).")
    resume_jobs(paused)
    say_jobs(c, paused)                     # the listener's job on; the timed pass only if it was on
    on, page = c.jobs_on(), None
    if c.jobs()[1] in on:                   # the listener's job: it serves the page and runs the check
        subprocess.run(["schtasks", "/Run", "/TN", c.jobs()[1]], capture_output=True, creationflags=HIDDEN)
        page = listener_answers(c)
        if page is False:
            say("The page did not answer once it was started again.")
    else:
        say("The background jobs are not set up (" + (", ".join(on) or "none") + " found); run turn-on to make them.")
    say(NO_PASS)
    status(c)
    return 0 if db_ok and page is not False else 1


NO_PASS = "No pass was run; run check-pass when you want one."


def retire_pass_job(c, paused):
    """After an update that succeeded: an older home's separate pass job is deleted, since the listener now runs the
    check itself. One the owner had switched off (Sync off; not in paused, the jobs this update
    switched off) keeps Sync off in Settings. Only after success, so an update put back still has its pass job."""
    name = c.jobs()[0]
    if name not in c.jobs_on():
        return
    try:
        c.engine().retire_pass_job(owner_off=name not in paused)
        say("The separate check job is no longer needed (the page's job runs the check); it was deleted.")
    except Exception as e:  # noqa: BLE001  the update itself is done; the old job only adds a second check
        say(f"The separate check job could not be removed ({type(e).__name__}: {e}); remove \"{name}\" in Task Scheduler.")
UPDATE_COPIES = "Update copies"         # the home's folder of an update's (and a take-over's) own safety copies
UPDATE_COPIES_KEPT = 2                  # an update's own safety copies kept there (each a whole program and database)


def _writable_again(fn, path, _exc):
    try:
        os.chmod(path, stat.S_IWRITE)
        fn(path)
    except OSError:
        pass


def prune_update_copies(c, keep=UPDATE_COPIES_KEPT):
    """After an update went through: only the newest `keep` of the updates' own safety copies stay (Live\\Update copies\\
    <date>\\update <version> <time>); the older ones are deleted outright, and a date folder they leave empty goes with
    them. Nothing else there is touched. Returns how many were removed."""
    base = os.path.join(c.home, UPDATE_COPIES)
    found = []
    for day in (os.listdir(base) if os.path.isdir(base) else []):
        d = os.path.join(base, day)
        if not (os.path.isdir(d) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)):
            continue
        for name in os.listdir(d):
            m = re.fullmatch(r"update \S+ (\d{6})", name)
            if m and os.path.isdir(os.path.join(d, name)):
                found.append((day, m.group(1), os.path.join(d, name)))
    found.sort()
    gone = 0
    for day, _t, path in (found[:-keep] if keep > 0 else found):
        shutil.rmtree(path, onerror=_writable_again)
        if not os.path.exists(path):
            gone += 1
        d = os.path.join(base, day)
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
    return gone
IMPORT_CHECK = r"""
import importlib.util, json, os, sys
live, page, files = sys.argv[1], sys.argv[2], sys.argv[3:]
for p in (page, os.path.join(live, "setup"), os.path.join(live, "connections"), os.path.join(live, "core"), live):
    sys.path.insert(0, p)
os.chdir(live)
bad = []
for i, f in enumerate(files):
    try:
        spec = importlib.util.spec_from_file_location("update_check_%d" % i, f)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
    except BaseException as e:  # noqa: BLE001  a file that stops its own load is a file that does not load
        bad.append("%s (%s: %s)" % (os.path.relpath(f, os.path.dirname(os.path.dirname(live))), type(e).__name__, str(e)[:160]))
print(json.dumps(bad))
"""


def imports_fail(c, rels):
    """The program files among rels (Python, in System) that do not load, each with why; [] when all load. Run apart, with
    the home named, so a file is loaded as the program loads it; nothing here opens the database."""
    files = sorted({os.path.join(c.root, r) for r in rels if str(r).endswith(".py") and str(r).startswith("System/")
                    and os.path.isfile(os.path.join(c.root, r))})
    if not files:
        return []
    r = subprocess.run([sys.executable, "-c", IMPORT_CHECK, c.live, c.page, *files], capture_output=True, text=True,
                       creationflags=HIDDEN, env=dict(os.environ, ASSISTANT_LIVE_HOME=c.home), timeout=300)
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return ["the check itself did not run: " + ((r.stderr or r.stdout or "").strip()[-300:] or f"exit {r.returncode}")]


def listener_answers(c, wait=60):
    """True when the page this computer serves answers (200) within wait seconds of being started; False when it does not;
    None when this home serves no page on this computer."""
    r = subprocess.run([sys.executable, "-c", "import json, publish; print(json.dumps([publish.hosting(), publish.page_port()]))"],
                       capture_output=True, text=True, creationflags=HIDDEN, cwd=c.page, timeout=60,
                       env=dict(os.environ, ASSISTANT_LIVE_HOME=c.home))
    try:
        hosting, port = json.loads((r.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError, TypeError):
        return False
    if hosting not in ("own_pc", "both") or not port:
        return None
    end = time.time() + wait
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/login", timeout=5) as got:
                if got.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        if time.time() >= end:
            return False
        time.sleep(1)


def listener_back(c, tries=3):
    """At the end of an update: whenever the listener's job is switched on, the listener is running and the page answers;
    started again (and waited for) when it does not. Says so when it still does not answer."""
    name = c.jobs()[1]
    if name not in c.jobs_on() or not _job_on(name):
        return None
    for _ in range(tries):
        if listener_answers(c, wait=5) is not False:
            return True
        subprocess.run(["schtasks", "/Run", "/TN", name], capture_output=True, creationflags=HIDDEN)
        if listener_answers(c, wait=60) is not False:
            return True
    say("The page did not answer after the update. Start it with turn-on, or restart the computer.")
    return False


def check_pass_now(c):
    """By hand, when the owner wants one: one check pass on purpose. The listener's job is switched off and this copy's
    programs stopped first, so nothing but the pass touches the database; then the pass; then the listener back. Says the
    pass's own line."""
    busy = wait_for_pass(c, PASS_WAIT_MINUTES)       # a pass already running finishes first
    if busy:
        say(busy)
        return 1
    try:
        listener = c.jobs()[1]
        was_on = _job_on(listener)
        if was_on:
            subprocess.run(["schtasks", "/Change", "/TN", listener, "/DISABLE"], capture_output=True, creationflags=HIDDEN)
        subprocess.run(["schtasks", "/End", "/TN", listener], capture_output=True, creationflags=HIDDEN)
        was_running = c.stop_programs()
    finally:
        release_pass(c)         # the pass below takes the lock itself
    try:
        r = check_pass(c, page_later=True)
    finally:
        if was_on:
            subprocess.run(["schtasks", "/Change", "/TN", listener, "/ENABLE"], capture_output=True, creationflags=HIDDEN)
            subprocess.run(["schtasks", "/Run", "/TN", listener], capture_output=True, creationflags=HIDDEN)
    log = os.path.join(c.home, "logs", "pass.log")
    lines = open(log, encoding="utf-8", errors="replace").read().strip().splitlines() if os.path.isfile(log) else []
    say("Check: " + (lines[-1] if lines else f"no line written (exit {r.returncode})"))
    if was_on:
        page = listener_answers(c)
        say("The page is back and answering." if page else "The page did not answer once it was started again." if page is False
            else "This home serves no page on this computer.")
    elif was_running:
        say("The page was running without its job; it was stopped for the check. Run turn-on to start it again.")
    return 0 if r.returncode == 0 else 1


def check_pass(c, wait=17 * 60, quick=False, page_later=False):
    """One check pass. A pass the background job started may still be running (1 to 4 minutes in every 15); the check
    waits for it to finish instead of counting its "another pass is running" answer as a failure. 17 minutes covers
    the longest a pass may hold the lock before it is ended. quick (an update's check): the pass leaves out its slow
    upkeep (the contacts recount, learning the owner's voice), which the next regular pass does. page_later: the listener
    is stopped, so the pass does not refresh the page (the listener refreshes it itself when it starts again)."""
    end = time.time() + wait
    env = dict(os.environ, ASSISTANT_LIVE_HOME=c.home, **({"ASSISTANT_QUICK_PASS": "1"} if quick else {}),
               **({"ASSISTANT_PAGE_LATER": "1"} if page_later else {}))
    while True:
        r = subprocess.run([sys.executable, os.path.join(c.live, "pass.py")], capture_output=True, text=True,
                           creationflags=HIDDEN, env=env, timeout=20 * 60)
        if r.returncode != SKIPPED or time.time() > end:
            return r
        time.sleep(10)


SOURCE_WORDS = {"email": "your mail", "calendar": "your calendar", "sms": "your phone's texts"}      # another kind: its own name


def good_sources(c):
    """The sources the last pass read fine: {name: when}, from the home's health record."""
    got = (read_json(os.path.join(c.home, "health.json"), {}) or {}).get("sources") or {}
    return {k: v.get("at") for k, v in got.items() if isinstance(v, dict) and v.get("status") == "ok"}


def newly_failed(c, before):
    """Sources that read fine before an install or update and did not read fine on its check pass, in plain words."""
    now = (read_json(os.path.join(c.home, "health.json"), {}) or {}).get("sources") or {}
    bad = []
    for name in sorted(before):
        v = now.get(name) if isinstance(now.get(name), dict) else {}
        if v.get("status") == "skipped":        # left out of the check pass on purpose (an update's quick check): not compared
            continue
        if v.get("status") != "ok" and v.get("at") != before[name]:
            kind, _, who = name.partition(":")
            bad.append(f"the mailbox {who}" if kind == "email" and who else (who or SOURCE_WORDS.get(kind, kind[:1].upper() + kind[1:])))
    whole = [b for b in bad if b in SOURCE_WORDS.values()]
    parts = [b for b in bad if b not in SOURCE_WORDS.values()]
    return parts + [w for w in whole if not (w == "your mail" and any(p.startswith("the mailbox ") for p in parts))]


def load_choices(path):
    """(choices, None), or ({}, a plain reason) when a choices file was named but cannot be used: a file the person
    chose with should never be read as "nothing chosen"."""
    if not path:
        return {}, None
    if not os.path.isfile(path):
        return {}, f"Refused: the choices file is not there ({path}). Nothing was changed."
    try:
        with open(path, encoding="utf-8") as f:
            got = json.load(f)
    except ValueError as e:
        return {}, (f"Refused: the choices file could not be read ({e}). Places in it must be written with forward "
                    "slashes. Nothing was changed.")
    if not isinstance(got, dict):
        return {}, "Refused: the choices file must list each part with its choice. Nothing was changed."
    return got, None


# files every complete engine has: a snapshot or a shipped record without them was taken while the engine was being replaced
CORE = ("System/live/answers.py", "System/live/items.py", "System/live/pass.py", "System/live/card.py", "System/live/chat.py",
        "System/live/db.py", "System/live/common.py", "System/live_page/page.html", "System/live_page/publish.py")


def snapshot_engine(tries=3):
    """One complete, unchanging copy of the plugin's engine for this run (lay-down, update, adopt), so what is laid down
    and what is recorded as shipped are the same files. None when the engine kept changing or is not whole."""
    import tempfile
    for i in range(tries):
        before = tree(os.path.join(ENGINE, "System"))
        snap = tempfile.mkdtemp(prefix="assistant-engine-")
        shutil.copytree(os.path.join(ENGINE, "System"), os.path.join(snap, "System"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        got = tree(os.path.join(snap, "System"))
        if got == before == tree(os.path.join(ENGINE, "System")) and all(k[len("System/"):] in got for k in CORE):
            return snap
        shutil.rmtree(snap, ignore_errors=True)
        if i < tries - 1:
            time.sleep(5)
    return None


def owner_paths(c):
    """Every program file the owner's own recorded changes name (Live/changes/ch-*.json): never taken as unchanged."""
    out = set()
    folder = os.path.join(c.home, "changes")
    for n in (os.listdir(folder) if os.path.isdir(folder) else []):
        if n.startswith("ch-") and n.endswith(".json"):
            rec = read_json(os.path.join(folder, n), {}) or {}
            out |= {p for p in rec.get("paths") or [] if str(p).startswith("System/")}
    return out


def tree(folder):
    out = {}
    for d, dirs, files in os.walk(folder):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for n in files:
            if n.endswith(".pyc"):
                continue
            p = os.path.join(d, n)
            out[os.path.relpath(p, folder).replace("\\", "/")] = sha(p)
    return out


def plugin_version():
    """The plugin's version: its plugin.json is the one place it is written."""
    return str((read_json(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), {}) or {}).get("version") or "")


def shipped_doc():
    """What this plugin ships, measured from its engine folder itself, with its version: the base an update merges
    against, kept in <root>/Shipped/shipped.json."""
    return {"version": plugin_version(), "files": {"System/" + k: v for k, v in sorted(tree(os.path.join(ENGINE, "System")).items())}}


def made_files():
    """The page's files its build remakes on each computer (build_site.MADE): never the owner's change, never asked
    about; an update remakes them from the files it lays down."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_site_made", os.path.join(ENGINE, "System", "live_page", "build_site.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {"System/live_page/site/app/" + n for n in mod.MADE} | {ROADMAP_COPY}


ROADMAP_COPY = "System/live_page/roadmap.html"      # the plugin's roadmap page as laid down for the page's build (build_site.ROADMAP_PAGE)


def put_roadmap_page(c):
    """The plugin's own roadmap page, laid down beside the page's build: the one source of how a roadmap looks on the
    page. Put at every lay-down, update, take-over and rebuild; nothing on the owner's computer names another."""
    src = os.path.join(PLUGIN, "page", "roadmap.html")
    if os.path.isfile(src) and os.path.isdir(os.path.join(c.system, "live_page")):
        shutil.copy2(src, os.path.join(c.root, *ROADMAP_COPY.split("/")))


def rebuild_page(c):
    """Remake the page's built files in this copy from its page and the plugin's own roadmap page."""
    put_roadmap_page(c)
    env = dict(os.environ, ASSISTANT_LIVE_HOME=c.home)
    env.pop("ROADMAP_PAGE_SOURCE", None)
    r = subprocess.run([sys.executable, os.path.join(c.system, "live_page", "build_site.py")], capture_output=True,
                       text=True, env=env, creationflags=HIDDEN, timeout=300)
    if r.returncode:
        raise RuntimeError("the page's files could not be remade: " + (r.stderr or r.stdout).strip()[-300:])


def keep_shipped(c):
    """The engine as shipped now, and its list, as the copy's base for the next update."""
    _rm(c.shipped)
    shutil.copytree(os.path.join(ENGINE, "System"), os.path.join(c.shipped, "System"))
    write_json(os.path.join(c.shipped, "shipped.json"), shipped_doc())


# --- lay down ---------------------------------------------------------------------------------------------
def put_docs(c):
    """The plugin's docs (the manual) beside System, replaced whole: nobody edits them on their own computer. The
    manual's version line is filled in here from plugin.json, never typed into the manual. The roadmap page goes down
    with it."""
    put_roadmap_page(c)
    if os.path.isdir(DOCS):
        _rm(c.docs)
        shutil.copytree(DOCS, c.docs, ignore=shutil.ignore_patterns("looks"))      # the styles' pictures stay with the plugin
        for d, _dirs, names in os.walk(c.docs):
            for n in names:
                if n.endswith(".html"):
                    p = os.path.join(d, n)
                    with open(p, encoding="utf-8", newline="") as f:
                        text = f.read()
                    with open(p, "w", encoding="utf-8", newline="") as f:
                        f.write(text.replace("<span data-version></span>",
                                             f"<span data-version>For version {plugin_version()}, </span>"))


def repo():
    """"owner/name" of the repository this plugin comes from, from its own manifest (the weekly update look reads it)."""
    url = str((read_json(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), {}) or {}).get("repository") or "")
    m = re.search(r"github\.com[/:]([^/\s]+/[^/\s.]+)", url)
    return m.group(1) if m else None


ROOTS = os.path.join(PLUGIN, "roots.json")        # every laid-down copy on this computer, for the guard hooks to find


def register_root(c, on=True):
    if os.path.exists(os.path.join(PLUGIN, ".git")):    # run from the plugin's source, not its working copy: never written there
        say("Refused: the list of laid-down copies is kept in the plugin's own data folder, not in its source folder; run the "
            "plugin's working copy of this script (as its skills do). The copy at " + c.root + " was not recorded.")
        return
    got = read_json(ROOTS, {}) or {}
    roots = [r for r in got.get("roots") or [] if os.path.normcase(r) != os.path.normcase(c.root)]
    if on:
        roots.append(c.root)
    write_json(ROOTS, {"about": "Folders where the assistant is laid down; the guard hooks read the guardrails in each.",
                       "roots": roots})


def write_guard_settings(c):
    """The settings file holding only the guard hooks, for the assistant's hidden Claude runs (which load no other
    settings). Its hook is the plugin's working copy of the guard, told which copy of the assistant it guards."""
    guard = os.path.join(PLUGIN, "hooks", "rulebook_guard.py")
    hook = {"type": "command", "command": "python", "args": [guard, "--root", c.root], "timeout": 30}
    write_json(os.path.join(c.home, "personal", "guard_settings.json"),
               {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [hook]}]}})


def lay_down(c, port=None, sending=None):
    if os.path.isdir(c.system):
        raise SystemExit(f"Refused: the assistant is already laid down in {c.root}. Use /assistant:update.")
    shutil.copytree(os.path.join(ENGINE, "System"), c.system)
    keep_shipped(c)
    put_docs(c)
    s = c.engine()
    s.make_home()
    if port:
        settings = s.common.settings()
        settings["page_port"] = int(port)
        s.common.write_json(s.common.SETTINGS, settings)
    s.set_hosting("own_pc")
    if sending is not None:
        s.allow(sending == "yes")
    version = plugin_version()
    write_json(c.install, {"root": c.root, "version": version, "repo": repo(), "jobs": c.jobs(),
                           "page_port": s.common.settings().get("page_port"),
                           "laid_down": dt.datetime.now().isoformat(timespec="seconds")})
    register_root(c)
    write_guard_settings(c)
    say(f"Laid down version {version} in {c.root}", f"Program: {c.system}", f"Your data: {c.home}",
        f"Page address: {s.local_page_address()}", "No background job was made.")


# --- jobs -------------------------------------------------------------------------------------------------
def turn_on(c):
    s = c.engine()
    made = s.turn_on(say=say)
    rec = read_json(c.install, {}) or {}
    rec["jobs"] = c.jobs()
    write_json(c.install, rec)
    say("Jobs on: " + ", ".join(c.jobs_on()))
    return made


def turn_off(c):
    for name in c.jobs():
        subprocess.run(["schtasks", "/End", "/TN", name], capture_output=True, creationflags=HIDDEN)
    pids = c.stop_programs()
    for name in c.jobs():
        subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"], capture_output=True, creationflags=HIDDEN)
    try:
        s = c.engine()
        if (s.reach() or {}).get("on"):
            s.reach_off(say=say)
    except Exception as e:                       # a copy that never set up its page reach has nothing to switch off
        say(f"Reach from anywhere: not switched off ({type(e).__name__}); it was not set up by this copy.")
    left = c.jobs_on()
    say(f"Stopped {len(pids)} running program(s).", "Jobs left: " + (", ".join(left) if left else "none"))
    return not left


def status(c):
    import urllib.request
    port = (read_json(os.path.join(c.home, "personal", "settings.json"), {}) or {}).get("page_port")
    serving = False
    if port:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
                serving = r.status < 500
        except urllib.error.HTTPError as e:
            serving = e.code < 500
        except OSError:
            serving = False
    cards = (read_json(os.path.join(c.home, "items.json"), {}) or {}).get("items") or []
    got = {"root": c.root, "program": os.path.isdir(c.system), "shipped_base": os.path.isdir(c.shipped),
           "manual": os.path.isfile(os.path.join(c.docs, "Assistant manual.html")),
           "data_home": os.path.isdir(c.home), "jobs": c.jobs_on(), "running": len(c.processes()),
           "page_port": port, "page_answers": serving,
           "last_pass": ((read_json(os.path.join(c.home, "health.json"), {}) or {}).get("last_pass") or {}).get("outcome"),
           "cards": len(cards), "cards_open": sum(1 for i in cards if isinstance(i, dict) and i.get("state") not in ("done", "handled")),
           "version": (read_json(c.install, {}) or {}).get("version")}
    print(json.dumps(got, indent=1))
    return got


# --- update guards: one update per home at a time; no half-merged files taken ---------------------------------
COPY_LOCK_STALE = 300                   # seconds: the same limit hooks/assistant_copy.py uses for its refresh lock


def copy_refreshing():
    """True while the plugin's working copy is being refreshed (hooks/assistant_copy.py holds its lock)."""
    try:
        return time.time() - os.path.getmtime(os.path.join(PLUGIN, "assistant-copy.lock")) < COPY_LOCK_STALE
    except OSError:
        return False


def take_update_lock(c):
    """One update at a time on a home. Returns None when this process now holds the lock, else the plain line to say."""
    path = os.path.join(c.home, "update.lock")
    os.makedirs(c.home, exist_ok=True)
    for _ in range(3):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps({"pid": os.getpid(), "at": time.time()}).encode())
            os.close(fd)
            return None
        except FileExistsError:
            held = read_json(path, None)
            if isinstance(held, dict) and held.get("pid") and _alive(held["pid"]):
                started = time.strftime("%H:%M", time.localtime(float(held.get("at") or time.time())))
                return f"Another update is running on this assistant, started {started}; try again when it finishes."
            try:
                os.remove(path)         # left by an update that died
            except OSError:
                pass
    return "Another update is running on this assistant; try again when it finishes."


def release_update_lock(c):
    path = os.path.join(c.home, "update.lock")
    held = read_json(path, None)
    if isinstance(held, dict) and held.get("pid") == os.getpid():
        try:
            os.remove(path)
        except OSError:
            pass


def marker_file(rels):
    """The first of these engine files (text only) holding a line that starts a merge-conflict marker, else None."""
    for rel in rels:
        p = os.path.join(ENGINE, *rel.split("/"))
        try:
            with open(p, "rb") as f:
                data = f.read()
        except OSError:
            continue
        if data[:8192].count(0):
            continue
        for line in data.decode("utf-8", errors="replace").splitlines():
            if line.startswith(("<<<<<<< ", ">>>>>>> ")) or line.rstrip() == "=======":
                return rel
    return None


def _taking(plan, choices=None):
    return sorted(set(plan["take"] + plan["added"] + plan["fits"] + [r for r, v in (choices or {}).items() if v == "new"]))


# --- update -------------------------------------------------------------------------------------------------
def _setup_update():
    """The update's own judgment of each file (engine setup_update.judge), the same one the change list's sorting uses."""
    import importlib.util
    folder = os.path.join(ENGINE, "System", "live", "setup")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    spec = importlib.util.spec_from_file_location("setup_update_plan", os.path.join(folder, "setup_update.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _judged(c, rel):
    """(kind, why, merged lines or None) for a file both the owner and the update changed."""
    su = _setup_update()
    at = lambda top: su._lines(os.path.join(top, *rel.split("/")))       # noqa: E731
    return su.judge(at(c.shipped), at(c.root), at(ENGINE))


def update_plan(c):
    # every side measured the same way, from the files themselves (line endings read as plain): a list written by an
    # older version may have counted Windows line endings, which would make unchanged files look like the owner's
    shipped_sys = os.path.join(c.shipped, "System")
    base = ({"System/" + k: v for k, v in tree(shipped_sys).items()} if os.path.isdir(shipped_sys) else
            (read_json(os.path.join(c.shipped, "shipped.json"), {}) or {}).get("files") or {})
    new_doc = shipped_doc()
    new = new_doc["files"]
    mine = {"System/" + k: v for k, v in tree(c.system).items()}
    plan = {"from": (read_json(os.path.join(c.shipped, "shipped.json"), {}) or {}).get("version"),
            "to": new_doc.get("version"), "take": [], "keep": [], "same": [], "conflict": [], "added": [],
            "dropped": [], "yours": [], "made": sorted(made_files()), "fits": [], "why": {}, "repaired": []}
    if not all(k in base for k in CORE if k in mine and k in new):
        # the record of what was last shipped was taken while the engine was being replaced, so it lacks files every copy
        # has: a program file both this copy and the update have, that the record lacks and no change of the owner's
        # names, is taken as shipped as it stands here (unchanged), not as one the owner added
        theirs = owner_paths(c)
        for rel in sorted(set(mine) & set(new)):
            if rel not in base and rel not in theirs and rel not in plan["made"]:
                base[rel] = mine[rel]
                plan["repaired"].append(rel)
    for rel in sorted(set(base) | set(new) | set(mine)):
        if rel in plan["made"]:
            continue
        b, m, n = base.get(rel), mine.get(rel), new.get(rel)
        if n and not b and not m:
            plan["added"].append(rel)
        elif b and not n:
            plan["dropped"].append(rel)                 # kept until the person says to remove it
        elif m and not b and not n:
            plan["yours"].append(rel)                   # a file only the person has: kept
        elif m == n:
            plan["same"].append(rel)
        elif m == b or m is None:
            plan["take"].append(rel)
        elif n == b:
            plan["keep"].append(rel)
        else:           # both changed it: the same judgment the change list's sorting makes, with its reason
            kind, why, _merged = _judged(c, rel)
            if kind == "now built in":
                plan["take"].append(rel)
            elif kind == "needs adjusting":
                plan["fits"].append(rel)
            elif kind == "untouched":
                plan["keep"].append(rel)
            else:
                plan["conflict"].append(rel)
            plan["why"][rel] = why
    return plan


def update_apply(c, choices_file=None, wait_minutes=PASS_WAIT_MINUTES):
    plan = update_plan(c)
    bad = marker_file(_taking(plan))
    if bad:
        say(f"Not updated: {bad} in the plugin's copy has unfinished merge markers; nothing was changed. Try again once the plugin is fixed.")
        return 1
    if plan["from"] == plan["to"] and not (plan["take"] or plan["added"] or plan["conflict"] or plan["fits"]):
        if plan["repaired"]:            # the program is current; only the record of what was shipped was incomplete
            keep_shipped(c)
            say("Nothing to update: this copy is already version " + str(plan["to"]) + ", file for file. The record of what "
                "was last shipped was incomplete; it is whole again.")
            return 0
        say("Nothing to update: this copy is already version " + str(plan["to"]) + ", file for file.")
        return 0
    choices, why = load_choices(choices_file)
    if why:
        say(why)
        return 1
    bad = marker_file(_taking(plan, choices))
    if bad:
        say(f"Not updated: {bad} in the plugin's copy has unfinished merge markers; nothing was changed. Try again once the plugin is fixed.")
        return 1
    open_ = [r for r in plan["conflict"] if r not in choices]
    if open_:
        say("Refused: these files were changed by you and by the update in a way that clashes; choose for each first:",
            *[f"{r}: {plan['why'].get(r, '')}" for r in open_])
        return 1
    busy = wait_for_pass(c, wait_minutes)        # a check running now holds the database the safety copy needs
    if busy:
        say(busy)
        return 1
    # nothing of this copy runs from here on: the jobs are off and its programs stopped, so the safety copy of the
    # database is whole and nothing opens the database while the update brings it forward
    # the listener's job, switched on before the update, comes back with it whether or not the listener was running just now
    # (pause_jobs ends the job's run, so the programs found stopped below no longer include the listener)
    try:
        listener_on = _job_on(c.jobs()[1])
        paused = pause_jobs(c)
        was_running = c.stop_programs()
    finally:
        release_pass(c)         # nothing can start a check now: the lock held since the wait is let go
    now = dt.datetime.now()
    aside = os.path.join(c.home, UPDATE_COPIES, now.date().isoformat(), f"update {plan['from']} {now:%H%M%S}")
    db = os.path.join(c.home, "Resources", "Database", "assistant.duckdb")
    # 1. the safety copy: System, Shipped, docs, the install record and the database. If this fails, nothing has
    #    been changed yet.
    try:
        os.makedirs(aside, exist_ok=True)
        shutil.copytree(c.system, os.path.join(aside, "System"))
        shutil.copytree(c.shipped, os.path.join(aside, "Shipped"))
        if os.path.isdir(c.docs):
            shutil.copytree(c.docs, os.path.join(aside, "docs"))
        if os.path.isfile(c.install):
            shutil.copy2(c.install, os.path.join(aside, "install.json"))
        if os.path.isfile(db):
            _copy_db(db, os.path.join(aside, "assistant.duckdb"))
        if os.path.isfile(db + ".wal"):         # changes not yet folded into the file: part of the database
            _copy_db(db + ".wal", os.path.join(aside, "assistant.duckdb.wal"))
    except OSError as e:
        say(f"Nothing was changed: the safety copy could not be made ({type(e).__name__}: {e}).")
        resume_jobs(paused)
        say_jobs(c, paused)
        listener_back(c)
        return 1
    step, code = "writing the new version", 1
    try:
        for rel in plan["take"] + plan["added"]:
            dest = os.path.join(c.root, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(os.path.join(ENGINE, rel), dest)
        for rel in plan["fits"]:            # the owner's change fits beside the update's: both kept, unless chosen otherwise
            if rel in choices:
                continue
            _kind, _why, merged = _judged(c, rel)
            with open(os.path.join(c.root, rel), "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
                f.writelines(merged)
        step = "writing the changes you chose"
        for rel, choice in choices.items():
            dest = os.path.join(c.root, rel)
            if choice == "new":
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(os.path.join(ENGINE, rel), dest)
            elif choice not in ("mine", None):
                if not os.path.isfile(choice):
                    raise RuntimeError(f"the file chosen for {rel} is not there: {choice}")
                shutil.copy2(choice, dest)              # a combination Claude wrote and the person saw
        step = "remaking the page's files"
        rebuild_page(c)
        step = "keeping the new shipped copy"
        keep_shipped(c)
        step = "the manual"
        put_docs(c)
        step = "bringing the data home forward"         # new tables and columns the new version reads, before anything runs
        c.engine().make_home()
        # no pass is run (the owner runs check-pass when he wants one): the checks below never open the database
        step = "checking that the program loads"
        bad = imports_fail(c, plan["take"] + plan["added"] + plan["fits"] + list(choices))
        if bad:
            raise RuntimeError("these program files do not load: " + "; ".join(bad[:5]))
        step = "bringing the background job up to date"     # made again from the install script; off stays off
        c.engine().renew_listener_job(was_off=not listener_on)
        if (listener_on or was_running) and c.jobs_on():
            step = "starting the page again"
            # the timed pass back on (if the update switched it off) before the page starts: the page reads Sync from the job,
            # and a page drawn while it was off showed Sync Off, and the next save of Sources wrote that Off back (11/22 16:12)
            resume_jobs(paused)
            subprocess.run(["schtasks", "/Run", "/TN", c.jobs()[1]], capture_output=True, creationflags=HIDDEN)
            if listener_answers(c) is False:
                raise RuntimeError("the page did not answer once it was started again")
        step = "recording the new version"
        rec = read_json(c.install, {}) or {}
        rec["version"] = plan["to"]
        rec["repo"] = repo() or rec.get("repo")
        write_json(c.install, rec)
        say(f"Updated {'within version ' + str(plan['to']) if plan['from'] == plan['to'] else 'from ' + str(plan['from']) + ' to ' + str(plan['to'])}: "
            f"{len(plan['take']) + len(plan['added'])} files taken, "
            f"{len(plan['keep']) + len(plan.get('yours', []))} of yours kept, {len(choices)} chosen by you. Old copy kept in {aside}.")
        say(NO_PASS)
        code = 0
        retire_pass_job(c, paused)
        gone = prune_update_copies(c)
        if gone:
            say(f"{gone} older update copies deleted; the newest {UPDATE_COPIES_KEPT} are kept.")
    except Exception as e:  # noqa: BLE001 - any failed step puts everything back
        os.chdir(c.home if os.path.isdir(c.home) else os.path.dirname(c.root))   # out of the program folder, so it can be put back
        why = f"{type(e).__name__}: {e}"
        try:
            _done, stuck = put_back(c, aside)  # anything of this copy still running is stopped first
            if os.path.isfile(os.path.join(aside, "install.json")):
                shutil.copy2(os.path.join(aside, "install.json"), c.install)
            if os.path.isfile(os.path.join(aside, "assistant.duckdb")):
                if os.path.isfile(db + ".wal"):     # the failed run's own log would be replayed onto the old file: set aside
                    os.replace(db + ".wal", os.path.join(aside, "failed-run.duckdb.wal"))
                shutil.copy2(os.path.join(aside, "assistant.duckdb"), db)
                if os.path.isfile(os.path.join(aside, "assistant.duckdb.wal")):
                    shutil.copy2(os.path.join(aside, "assistant.duckdb.wal"), db + ".wal")
            if stuck:
                say(f"The update failed at {step} ({why}). It was put back except these files, still held open by another "
                    f"program: {', '.join(stuck[:20])}" + (f" and {len(stuck) - 20} more" if len(stuck) > 20 else "")
                    + f". Close what holds them and run restore with the safety copy in {aside}. Nothing was lost.")
            else:
                say(f"The update failed at {step} ({why}). Everything is back as it was before; nothing was lost.")
        except Exception as e2:  # noqa: BLE001
            say(f"The update failed at {step} ({why}), and putting it back also failed ({type(e2).__name__}: {e2}). "
                f"The safety copy is complete in {aside}.")
        code = 1
    resume_jobs(paused)                     # the regular pass and the listener's job on again, as they were
    say_jobs(c, paused)                     # and checked: the listener's job on, the timed pass as it was found
    listener_back(c)
    return code


# --- uninstall ------------------------------------------------------------------------------------------------
def uninstall(c, remove_data=False):
    turn_off(c)
    # Off every project's list of readers, as the roadmap's agreement says: only this copy's own entry, the file
    # written whole and renamed. Done without the engine, so a copy that was half removed is still cleaned.
    me = "assistant " + hashlib.sha1(os.path.normcase(os.path.abspath(c.home)).encode("utf-8")).hexdigest()[:6]
    settings = read_json(os.path.join(c.home, "personal", "settings.json"), {}) or {}
    for folder in [e.get("folder") for e in settings.get("roadmaps") or [] if isinstance(e, dict) and e.get("folder")]:
        path = os.path.join(folder, "Roadmap page", "readers.json")
        got = read_json(path)
        if isinstance(got, dict) and isinstance(got.get("readers"), dict) and me in got["readers"]:
            got["readers"].pop(me)
            write_json(path, got)
            say(f"{folder}: taken off its list of readers; its roadmap is untouched.")
    intro = read_json(os.path.join(c.home, "personal", "projects.json"), {}) or {}
    for p in intro.get("projects") or []:
        for ch in p.get("changes") or []:
            say(f"Left in place, for you to decide: {p.get('folder')}: {ch}")
    register_root(c, on=False)
    os.chdir(os.path.dirname(c.root))
    for folder in (c.system, c.shipped, c.docs) + ((c.home,) if remove_data else ()):
        try:
            _rm(folder)
        except OSError as e:
            say(f"Could not remove {folder}: a program has it open ({type(e).__name__}). Close any window or terminal "
                "open in that folder and run this again.")
    note = os.path.join(c.root, "CLAUDE.md")        # the folder's note for a Claude session there, while it is still the plugin's own
    try:
        with open(note, encoding="utf-8") as f:
            ours = f.read().startswith("# This folder is your assistant (written by the assistant plugin")
        if ours:
            os.remove(note)
    except OSError:
        pass
    if os.path.isdir(c.root) and not os.listdir(c.root):
        try:
            os.rmdir(c.root)
        except OSError:                              # most often this very session is open in it
            say(f"The empty folder {c.root} is left: something has it open (this Claude session, if it was opened "
                "there). It holds nothing; delete it after closing that.")
    left = [p for p in (c.system, c.shipped, c.docs, c.home) if os.path.exists(p)]
    say("Program removed." + (" Your data is kept in " + c.home if os.path.isdir(c.home) else " Your data was removed."),
        "Jobs left: " + (", ".join(c.jobs_on()) or "none"))
    return left


# --- adopt: an existing copy (System and Live in one folder, from before the plugin) taken over by the plugin ---------
PARTS = ("live", "live_page")                  # the parts of System the plugin ships; anything else in System is left
NOT_PROGRAM = re.compile(r"(^|/)(__pycache__|state|runs|\.scratch)(/|$)|\.(pyc|tmp|lock|log)$|^System/live_page/(manual|roadmap)\.html$")


def reader_name(home):
    return "assistant " + hashlib.sha1(os.path.normcase(os.path.abspath(home)).encode("utf-8")).hexdigest()[:6]


def adopt_plan(old, c):
    """Each program file of the old copy against the plugin's: same, the plugin's only (added), the owner's only
    (kept), or different (the owner chooses, as in an update; an old copy has no record of what it was shipped)."""
    new = shipped_doc()["files"]
    mine = {}
    for part in PARTS:
        for rel, h in tree(os.path.join(old.system, part)).items():
            rel = f"System/{part}/{rel}"
            if not NOT_PROGRAM.search(rel):
                mine[rel] = h
    plan = {"from": old.root, "to": c.root, "version": plugin_version(),
            "same": [], "added": [], "yours": [], "differ": []}
    for rel in sorted(set(mine) | set(new)):
        m, n = mine.get(rel), new.get(rel)
        plan["same" if m == n else "added" if not m else "yours" if not n else "differ"].append(rel)
    return plan


def _schtasks(*args):
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, creationflags=HIDDEN)


def adopt(old, c, choices_file=None, jobs=True):
    """Take an existing copy over: the plugin's program in <new root>\\System with the owner's own edits as chosen,
    Shipped and docs beside it, the data home moved (a rename on the same drive, nothing copied), the hidden jobs
    swapped to this copy's names, one check pass. Any failed step after the old copy is stopped puts it all back.
    The old program folders are left as they were: they are the way back (adopt-back)."""
    plan = adopt_plan(old, c)
    choices, why = load_choices(choices_file)
    if why:
        say(why)
        return 1
    open_ = [r for r in plan["differ"] if r not in choices]
    if os.path.normcase(os.path.abspath(old.root)) == os.path.normcase(os.path.abspath(c.root)):
        if open_:
            say("Refused: these program files differ from the plugin's; choose for each first (mine, new, or a combined file):", *open_)
            return 1
        return adopt_in_place(c, plan, choices)
    if os.path.exists(c.system) or os.path.exists(c.home):
        say(f"Refused: {c.root} already holds a program or a data home.")
        return 1
    if not os.path.isdir(old.home):
        say(f"Refused: there is no data home at {old.home}.")
        return 1
    if os.path.splitdrive(os.path.abspath(old.home))[0].lower() != os.path.splitdrive(os.path.abspath(c.home))[0].lower():
        say("Refused: the new folder must be on the same drive, so the data home moves without being copied.")
        return 1
    if open_:
        say("Refused: these program files differ from the plugin's; choose for each first (mine, new, or a combined file):", *open_)
        return 1
    old_jobs = read_json(os.path.join(old.home, "personal", "jobs.json"), {}) or {}
    old_names = [n for n in (old_jobs.get("pass"), old_jobs.get("listener")) if n] or old.jobs()
    had_jobs = [n for n in old_names if _schtasks("/Query", "/TN", n).returncode == 0]
    t0 = dt.datetime.now()
    say(f"Adopting {old.root} into {c.root} (version {plan['version']}): {len(plan['same'])} files the same, "
        f"{len(plan['added'])} new, {len(plan['yours'])} of yours kept, {len(plan['differ'])} chosen by you.")
    # 1. the new program, beside the old one; nothing of the old copy is touched yet
    try:
        shutil.copytree(os.path.join(ENGINE, "System"), c.system)
        for rel in plan["yours"]:
            dest = os.path.join(c.root, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(os.path.join(old.root, rel), dest)
        for rel, choice in choices.items():
            dest = os.path.join(c.root, rel)
            if choice == "mine":
                shutil.copy2(os.path.join(old.root, rel), dest)
            elif choice != "new":
                if not os.path.isfile(choice):
                    raise RuntimeError(f"the file chosen for {rel} is not there: {choice}")
                shutil.copy2(choice, dest)
        keep_shipped(c)
        put_docs(c)
    except Exception as e:  # noqa: BLE001
        for d in (c.system, c.shipped, c.docs):
            _rm(d)
        say(f"Nothing was changed: the new program could not be laid down ({type(e).__name__}: {e}).")
        return 1
    # 2. the switch: stop the old copy, move the home, bring it forward, check; any failure puts everything back
    saved_jobs_json = read_json(os.path.join(old.home, "personal", "jobs.json"))
    saved_install = read_json(os.path.join(old.home, "personal", "install.json"))
    step, moved, made = "stopping the old copy", False, []
    stopped_at = None
    try:
        for n in had_jobs:
            _schtasks("/End", "/TN", n)
            _schtasks("/Change", "/TN", n, "/DISABLE")
        old.stop_programs(include_home=True)
        stopped_at = dt.datetime.now()
        step = "moving the data home"
        for tries in range(31):                      # a virus scan or the search index can hold it for a moment
            try:
                os.rename(old.home, c.home)
                break
            except PermissionError:
                if tries == 30:
                    raise RuntimeError("Windows says something still has the assistant's data folder open (a File "
                                       "Explorer window, an editor, a terminal opened in it, or a program started from it). "
                                       "Close it and try again.")
                if tries in (5, 15):
                    old.stop_programs(include_home=True)
                time.sleep(1)
        moved = True
        step = "recording the copy"
        old_reader, new_reader = reader_name(old.home), reader_name(c.home)
        jobs_json = os.path.join(c.home, "personal", "jobs.json")
        if os.path.exists(jobs_json):
            os.remove(jobs_json)                     # the new names come from the new home (job_names)
        write_json(c.install, {"root": c.root, "version": plan["version"], "repo": repo(), "jobs": c.jobs(),
                               "page_port": (read_json(os.path.join(c.home, "personal", "settings.json"), {}) or {}).get("page_port"),
                               "laid_down": dt.datetime.now().isoformat(timespec="seconds"),
                               "adopted": {"from": old.root, "at": t0.isoformat(timespec="seconds"), "old_jobs": had_jobs,
                                           "old_jobs_json": saved_jobs_json, "old_reader": old_reader}})
        register_root(c)
        write_guard_settings(c)
        for folder in [e.get("folder") for e in (read_json(os.path.join(c.home, "personal", "settings.json"), {}) or {}).get("roadmaps") or []
                       if isinstance(e, dict) and e.get("folder")]:
            path = os.path.join(folder, "Roadmap page", "readers.json")
            got = read_json(path)
            if isinstance(got, dict) and isinstance(got.get("readers"), dict) and old_reader in got["readers"]:
                got["readers"][new_reader] = got["readers"].pop(old_reader)
                write_json(path, got)
        step = "bringing the data home forward"
        c.engine().make_home()                       # creates only what is missing; the database gains new columns only
        step = "the check"
        before = good_sources(c)        # what the data home's last pass read fine, before this install's own pass
        r = check_pass(c)
        last = ((read_json(os.path.join(c.home, "health.json"), {}) or {}).get("last_pass") or {}).get("outcome")
        if r.returncode or last not in ("ok", "problems"):
            tail = " ".join(((r.stderr or "") + (r.stdout or "")).strip().splitlines()[-3:])[-400:]
            raise RuntimeError(f"the check ended {last or 'with an error'}, exit {r.returncode}" + (f": {tail}" if tail else ""))
        lost = newly_failed(c, before)
        if lost:            # something that read fine before the install does not now: not a success
            raise RuntimeError("the check could not read " + ", ".join(lost) + ", which read fine before the install")
        if jobs:
            step = "making the hidden jobs"
            made = c.engine().turn_on(say=say) or []
            _schtasks("/Run", "/TN", c.jobs()[1])
    except Exception as e:  # noqa: BLE001 - any failed step puts everything back
        os.chdir(c.home if os.path.isdir(c.home) else os.path.dirname(c.root))   # out of the program folder, so it can be put back
        why = f"{type(e).__name__}: {e}"
        back = adopt_back(old, c, quiet=True, made=made, moved=moved, saved_jobs_json=saved_jobs_json,
                          saved_install=saved_install, old_jobs=had_jobs)
        if back and not os.path.exists(c.home):
            # the program this attempt laid down goes too, so trying again starts clean
            for d in (c.system, c.shipped, c.docs):
                try:
                    _rm(d)
                except OSError:
                    pass
            try:
                if os.path.isdir(c.root) and not os.listdir(c.root):
                    os.rmdir(c.root)
            except OSError:
                pass
        say(f"The switch failed at {step} ({why}). " + ("The old copy is back as it was and running." if back else
            f"Putting it back also failed; the old program is untouched in {old.system} and the data home is at "
            f"{c.home if os.path.isdir(c.home) else old.home}."))
        return 1
    say(f"Adopted. The old copy stopped at {stopped_at:%H:%M:%S}; the new one checked and "
        + ("its jobs are on." if jobs else "no jobs were made (as asked)."),
        f"Program: {c.system}. Data: {c.home}. The old program is left in {old.system} as the way back: adopt-back.")
    return 0


def adopt_in_place(c, plan, choices):
    """"Where it is now": the assistant stays in its folder and only its program is replaced, as in an update with no
    record of what it was shipped. Its jobs run the same program files, so they stay as they are. The old program is
    saved first in the data home's Update copies folder; that copy is the way back (adopt-back), and any failed step puts
    it back by itself."""
    now = dt.datetime.now()
    aside = os.path.join(c.home, UPDATE_COPIES, now.date().isoformat(), f"adopt {now:%H%M%S}")
    saved_install = read_json(c.install)
    say(f"Taking over {c.root} where it is (version {plan['version']}): {len(plan['same'])} files the same, "
        f"{len(plan['added'])} new, {len(plan['yours'])} of yours kept, {len(plan['differ'])} chosen by you.")
    try:
        for part in PARTS:
            shutil.copytree(os.path.join(c.system, part), os.path.join(aside, "System", part),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    except OSError as e:
        say(f"Nothing was changed: the old program could not be saved first ({type(e).__name__}: {e}).")
        return 1
    jobs = c.jobs()
    had_jobs = [n for n in jobs if _schtasks("/Query", "/TN", n).returncode == 0]
    step = "stopping it"
    try:
        for n in had_jobs:
            _schtasks("/End", "/TN", n)
        c.stop_programs(include_home=True)
        step = "writing the plugin's program"
        for rel in plan["same"] + plan["added"]:
            dest = os.path.join(c.root, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(os.path.join(ENGINE, rel), dest)
        for rel, choice in choices.items():
            dest = os.path.join(c.root, rel)
            if choice == "new":
                shutil.copy2(os.path.join(ENGINE, rel), dest)
            elif choice != "mine":
                if not os.path.isfile(choice):
                    raise RuntimeError(f"the file chosen for {rel} is not there: {choice}")
                shutil.copy2(choice, dest)
        keep_shipped(c)
        put_docs(c)
        step = "recording the copy"
        write_json(c.install, {"root": c.root, "version": plan["version"], "repo": repo(), "jobs": jobs,
                               "page_port": (read_json(os.path.join(c.home, "personal", "settings.json"), {}) or {}).get("page_port"),
                               "laid_down": now.isoformat(timespec="seconds"),
                               "adopted": {"from": c.root, "at": now.isoformat(timespec="seconds"), "in_place": True,
                                           "saved": aside, "old_install": saved_install}})
        register_root(c)
        write_guard_settings(c)
        step = "bringing the data home forward"
        c.engine().make_home()
        step = "the check"
        before = good_sources(c)        # what the data home's last pass read fine, before this install's own pass
        r = check_pass(c)
        last = ((read_json(os.path.join(c.home, "health.json"), {}) or {}).get("last_pass") or {}).get("outcome")
        if r.returncode or last not in ("ok", "problems"):
            tail = " ".join(((r.stderr or "") + (r.stdout or "")).strip().splitlines()[-3:])[-400:]
            raise RuntimeError(f"the check ended {last or 'with an error'}, exit {r.returncode}" + (f": {tail}" if tail else ""))
        lost = newly_failed(c, before)
        if lost:            # something that read fine before the install does not now: not a success
            raise RuntimeError("the check could not read " + ", ".join(lost) + ", which read fine before the install")
    except Exception as e:  # noqa: BLE001 - any failed step puts the old program back
        os.chdir(c.home if os.path.isdir(c.home) else os.path.dirname(c.root))   # out of the program folder, so it can be put back
        why = f"{type(e).__name__}: {e}"
        try:
            back = adopt_back_in_place(c, {"saved": aside, "old_install": saved_install}, quiet=True)
        except Exception:  # noqa: BLE001
            back = False
        say(f"The switch failed at {step} ({why}). " + ("The old program is back as it was and running." if back else
            f"Putting it back also failed; the old program is saved whole in {aside}."))
        return 1
    if had_jobs:
        _schtasks("/Run", "/TN", jobs[1])
    say(f"Taken over where it is. Its background jobs run the new program from the same place"
        + (" and the page has been started." if had_jobs else " (it had none)."),
        f"The old program is saved in {aside} as the way back: adopt-back.")
    return 0


def adopt_back_in_place(c, adopted, quiet=False):
    """The way back from adopt_in_place: stop it, put the saved program back, remove what the plugin added
    (Shipped, docs, its record), and start it again."""
    aside = adopted.get("saved") or ""
    if not os.path.isdir(os.path.join(aside, "System")):
        raise RuntimeError(f"the saved old program is not there ({aside})")
    jobs = c.jobs()
    for n in jobs:
        _schtasks("/End", "/TN", n)
    c.stop_programs(include_home=True)
    for part in PARTS:
        _rm(os.path.join(c.system, part))
        shutil.copytree(os.path.join(aside, "System", part), os.path.join(c.system, part))
    for d in (c.shipped, c.docs):
        _rm(d)
    register_root(c, on=False)
    if adopted.get("old_install") is None:
        if os.path.exists(c.install):
            os.remove(c.install)
    else:
        write_json(c.install, adopted["old_install"])
    gs = os.path.join(c.home, "personal", "guard_settings.json")
    if os.path.exists(gs):
        os.remove(gs)
    if _schtasks("/Query", "/TN", jobs[1]).returncode == 0:
        _schtasks("/Run", "/TN", jobs[1])
    if not quiet:
        say("Back: the old program is in place again and running from the same folder.")
    return True


def adopt_back(old, c, quiet=False, made=None, moved=None, saved_jobs_json=None, saved_install=None, old_jobs=None):
    """The way back from adopt, in one step: stop the new copy, remove its jobs, move the data home back, put its
    records back, and start the old copy's jobs again. The new program folders are left in place, unused."""
    rec = read_json(c.install, {}) or {}
    adopted = rec.get("adopted") or {}
    if adopted.get("in_place"):
        try:
            return adopt_back_in_place(c, adopted, quiet)
        except Exception as e:  # noqa: BLE001
            say(f"The way back stopped ({type(e).__name__}: {e}).")
            return False
    old_jobs = old_jobs if old_jobs is not None else adopted.get("old_jobs") or []
    saved_jobs_json = saved_jobs_json if saved_jobs_json is not None else adopted.get("old_jobs_json")
    try:
        for n in c.jobs():
            _schtasks("/End", "/TN", n)
            _schtasks("/Delete", "/TN", n, "/F")
        c.stop_programs()
        register_root(c, on=False)
        if os.path.isdir(c.home) and not os.path.exists(old.home):
            os.rename(c.home, old.home)
        home = old.home
        old_reader, new_reader = adopted.get("old_reader") or reader_name(old.home), reader_name(c.home)
        for folder in [e.get("folder") for e in (read_json(os.path.join(home, "personal", "settings.json"), {}) or {}).get("roadmaps") or []
                       if isinstance(e, dict) and e.get("folder")]:
            path = os.path.join(folder, "Roadmap page", "readers.json")
            got = read_json(path)
            if isinstance(got, dict) and isinstance(got.get("readers"), dict) and new_reader in got["readers"]:
                got["readers"][old_reader] = got["readers"].pop(new_reader)
                write_json(path, got)
        for name, saved in (("jobs.json", saved_jobs_json), ("install.json", saved_install)):
            p = os.path.join(home, "personal", name)
            if saved is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                write_json(p, saved)
        for n in old_jobs:
            _schtasks("/Change", "/TN", n, "/ENABLE")
        if old_jobs:
            _schtasks("/Run", "/TN", old_jobs[-1])  # the listener: the page answers again at once
        if not quiet:
            say(f"Back: the data home is at {old.home} and the old copy's jobs are on again ({', '.join(old_jobs) or 'none had been made'}).",
                f"The plugin's program is left unused in {c.system}.")
        return True
    except Exception as e:  # noqa: BLE001
        say(f"The way back stopped ({type(e).__name__}: {e}).")
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["lay-down", "turn-on", "turn-off", "status", "update-plan", "update-apply", "uninstall",
                                        "adopt-plan", "adopt", "adopt-back", "restore", "test-cards", "voice-learn", "check-pass"])
    ap.add_argument("what", nargs="?", choices=["add", "remove"], help="test-cards: add or remove the made-up cards")
    ap.add_argument("--from", dest="old", help="adopt: the folder of the existing copy (it holds System and Live); "
                                                    "restore: the update's safety copy")
    ap.add_argument("--no-jobs", action="store_true", help="adopt: make no hidden jobs (for a test)")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--port", type=int)
    ap.add_argument("--sending", choices=["yes", "no"])
    ap.add_argument("--choices")
    ap.add_argument("--remove-data", action="store_true")
    ap.add_argument("--wait", type=float, default=PASS_WAIT_MINUTES, help="update-apply: minutes to wait for a running check")
    a = ap.parse_args(argv)
    c = Copy(a.root)
    global ENGINE
    snap = None
    if a.command in ("update-plan", "update-apply") and copy_refreshing():
        print("Not started: the plugin's copy is being refreshed this moment, so it may be half written. Nothing was changed. Try again in a minute.")
        return 1
    locked = False
    if a.command in ("update-plan", "update-apply", "check-pass"):
        busy = take_update_lock(c)
        if busy:
            print(busy)
            return 1
        locked = True
    if a.command in ("lay-down", "update-plan", "update-apply", "adopt-plan", "adopt"):
        snap = snapshot_engine()
        if snap is None:
            print("Not started: the plugin's own copy of the program is being refreshed this moment, so it could not be read "
                  "whole. Nothing was changed. Try again in a minute.")
            if locked:
                release_update_lock(c)
            return 1
        ENGINE = snap
    try:
        return _run(a, c)
    finally:
        if snap:
            shutil.rmtree(snap, ignore_errors=True)
        if locked:
            release_update_lock(c)


def _run(a, c):
    if a.command == "check-pass":
        return check_pass_now(c)
    if a.command == "lay-down":
        lay_down(c, a.port, a.sending)
    elif a.command == "turn-on":
        turn_on(c)
    elif a.command == "turn-off":
        return 0 if turn_off(c) else 1
    elif a.command == "status":
        status(c)
    elif a.command == "update-plan":
        plan = update_plan(c)
        bad = marker_file(_taking(plan))
        if bad:
            say(f"Not planned: {bad} in the plugin's copy has unfinished merge markers; nothing was changed. Try again once the plugin is fixed.")
            return 1
        print(json.dumps({k: (v if not isinstance(v, list) or k in ("conflict", "dropped", "fits", "yours") else len(v))
                          for k, v in plan.items()}, indent=1))
    elif a.command == "update-apply":
        return update_apply(c, a.choices, a.wait)
    elif a.command == "uninstall":
        return 1 if uninstall(c, a.remove_data) else 0
    elif a.command == "voice-learn":       # the owner's voice learned now and saved, as Learn my voice now does
        code = ("import sys; sys.path.insert(0, '.'); import voice; print(voice.learn_now()); "
                "p = voice.profile(); print('Greetings: ' + ', '.join(p.get('greetings') or []) + ' | Sign-offs: ' + ', '.join(p.get('signoffs') or []) + "
                "' | Phrases: ' + ', '.join(p.get('phrases') or []))")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, creationflags=HIDDEN, cwd=c.live,
                           env=dict(os.environ, ASSISTANT_LIVE_HOME=c.home))
        print((r.stdout or "").strip() or (r.stderr or "").strip()[-800:])
        return r.returncode
    elif a.command == "test-cards":
        script = os.path.join(c.live, "test_cards.py")
        if not os.path.isfile(script):
            say("Not done: this copy of the assistant has no test cards yet; update it first (/assistant:update).")
            return 1
        r = subprocess.run([sys.executable, script, a.what or "add"], capture_output=True, text=True, creationflags=HIDDEN,
                           cwd=c.live, env=dict(os.environ, ASSISTANT_LIVE_HOME=c.home))
        print((r.stdout or "").strip() or (r.stderr or "").strip()[-800:])
        return r.returncode
    elif a.command == "restore":
        if not a.old:
            raise SystemExit("Name the update's safety copy with --from.")
        return restore(c, os.path.abspath(a.old))
    elif a.command in ("adopt-plan", "adopt", "adopt-back"):
        old = Copy(a.old or (((read_json(c.install, {}) or {}).get("adopted") or {}).get("from") or ""))
        if not a.old and a.command != "adopt-back":
            raise SystemExit("Name the existing copy's folder with --from.")
        if a.command == "adopt-plan":
            plan = adopt_plan(old, c)
            print(json.dumps({k: (v if not isinstance(v, list) or k in ("differ", "yours") else len(v)) for k, v in plan.items()}, indent=1))
        elif a.command == "adopt":
            return adopt(old, c, a.choices, jobs=not a.no_jobs)
        else:
            return 0 if adopt_back(old, c) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
