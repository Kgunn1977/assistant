"""Keeps a working copy of the assistant's scripts, its docs and its engine in the plugin's own data folder (CLAUDE_PLUGIN_DATA),
as the roadmap's working_copy.py does for its files, so every skill of this plugin runs that copy and never names the
plugin's own folder. Runs before every message and every terminal command; copies only when the plugin's files
changed (one checksum of them is kept as assistant-copy.stamp). It never stops a session: any fault is ignored.

The setup helper and its texts have one home, the engine's setup folder (the laid-down program's page chat reads them
there too). The skills read the texts from <data>/setup_texts, which this file makes from that folder with the real
data folder filled in; the engine copy itself keeps the plain placeholder, so a laid-down program never holds a path
of this computer."""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS_KEPT_HOME = {"looks"}                         # pictures of the page's styles: kept in the plugin's own folder, never installed
SKIP = {"roadmap_setup.py"}                       # the roadmap's own working copy keeps that one
TEXTS = os.path.join("engine", "System", "live", "setup", "setup_texts")   # the setup texts' one home


def files():
    """Every file under scripts, docs and engine, except the roadmap's own, plus the guard and plugin.json."""
    out = []
    top = os.path.join(ROOT, "scripts")
    for folder, dirs, names in os.walk(top):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for n in sorted(names):
            if n in SKIP or n.endswith(".pyc"):
                continue
            out.append(os.path.relpath(os.path.join(folder, n), ROOT))
    docs = os.path.join(ROOT, "docs")
    for folder, dirs, names in os.walk(docs):
        dirs[:] = sorted(d for d in dirs if d not in DOCS_KEPT_HOME)
        out += [os.path.relpath(os.path.join(folder, n), ROOT) for n in sorted(names)]
    guard = os.path.join("hooks", "rulebook_guard.py")     # the hidden runs' settings file names this copy of it
    if os.path.isfile(os.path.join(ROOT, guard)):
        out.append(guard)
    engine = os.path.join(ROOT, "engine")                  # every engine file: an edit made here reaches the copy
    for folder, dirs, names in os.walk(engine):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        out += [os.path.relpath(os.path.join(folder, n), ROOT) for n in sorted(names) if not n.endswith(".pyc")]
    return out + [os.path.join("page", "roadmap.html"), os.path.join(".claude-plugin", "plugin.json")]   # the roadmap page the program lays down for its page


def stamp():
    h = hashlib.sha256()
    with open(os.path.abspath(__file__), "rb") as f:   # how the copy is made counts too: a changed copier copies afresh
        h.update(f.read())
    for rel in files():
        with open(os.path.join(ROOT, rel), "rb") as f:
            h.update(rel.encode() + b"\0" + f.read() + b"\0")
    return h.hexdigest()


CORE = ("live/pass.py", "live/db.py", "live/items.py", "live/answers.py", "live/ai_steps.py", "live_page/page.html", "live_page/listen.py")
                                    # a copy missing any of these is not whole, whatever its stamp says: it is made again


def sync(dest=None):
    dest = dest or os.environ.get("CLAUDE_PLUGIN_DATA")
    if not dest or os.path.normcase(os.path.abspath(dest)) == os.path.normcase(ROOT):
        return False
    mark = os.path.join(dest, "assistant-copy.stamp")
    want = stamp()
    whole = all(os.path.isfile(os.path.join(dest, "engine", "System", *p.split("/"))) for p in CORE)
    try:
        with open(mark, encoding="utf-8") as f:
            if f.read().strip() == want and whole:
                return False
    except OSError:
        pass
    os.makedirs(dest, exist_ok=True)       # a first copy: its folder is made before the lock is put in it
    lock = _take_lock(dest)
    if not lock:
        return False                # another session's hook is bringing the copy up to date this moment; it finishes the job
    try:
        return _sync(dest, mark, want)
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


LOCK_STALE = 300                    # seconds: a refresh holding the lock longer than this was cut off and is taken over


def _take_lock(dest):
    """One refresh of the copy at a time across every session on this computer (each session's hooks run this). Returns the
    lock's path when this process holds it, else None."""
    import time
    path = os.path.join(dest, "assistant-copy.lock")
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps({"pid": os.getpid(), "at": time.time()}).encode())
            os.close(fd)
            return path
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(path)
            except OSError:
                continue
            if age < LOCK_STALE:
                return None
            try:
                os.remove(path)     # left by a refresh that was cut off
            except OSError:
                return None
        except OSError:
            return None
    return None


def _sync(dest, mark, want):
    for rel in files():
        if rel.startswith(("scripts", "docs", "hooks", "page", ".claude-plugin")):
            os.makedirs(os.path.dirname(os.path.join(dest, rel)), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, rel), os.path.join(dest, rel))
    tmp = os.path.join(dest, "engine.new")
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    shutil.copytree(os.path.join(ROOT, "engine"), tmp, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    old = os.path.join(dest, "engine")
    gone = os.path.join(dest, "engine.old")
    if os.path.isdir(gone):
        shutil.rmtree(gone, ignore_errors=True)
    if os.path.isdir(old):
        try:        # the old engine moves aside in one step, so a reader sees the old one whole or the new one whole
            os.replace(old, gone)
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)
            return False            # something holds it now: the copy stays as it was, and the next run tries again
    os.replace(tmp, old)
    shutil.rmtree(gone, ignore_errors=True)
    texts(dest)
    with open(mark, "w", encoding="utf-8") as f:
        f.write(want)
    return True


def texts(dest):
    """The skills' copy of the setup texts, at <dest>/setup_texts. Claude Code fills ${CLAUDE_PLUGIN_DATA} into a
    skill's own file, but not into the texts a skill reads, and a session's shell does not hold it either; so each
    text gets the real folder here."""
    place = os.path.abspath(dest).replace("\\", "/")
    out = os.path.join(dest, "setup_texts")
    tmp = out + ".new"
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    for folder, _dirs, names in os.walk(os.path.join(ROOT, TEXTS)):
        for n in names:
            src = os.path.join(folder, n)
            to = os.path.join(tmp, os.path.relpath(src, os.path.join(ROOT, TEXTS)))
            os.makedirs(os.path.dirname(to), exist_ok=True)
            with open(src, encoding="utf-8", newline="") as f:
                text = f.read()
            with open(to, "w", encoding="utf-8", newline="") as f:
                f.write(text.replace("${CLAUDE_PLUGIN_DATA}", place))
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.replace(tmp, out)


if __name__ == "__main__":
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    try:
        sync()
    except Exception:
        pass
    sys.exit(0)
