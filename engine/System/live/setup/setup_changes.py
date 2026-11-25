r"""Changes the owner makes to their assistant's program, and undoing them.

The record is the one in the guardrails contract (RULEBOOK.md, section 4c): one file per change,
<home>\changes\<id>.json, with its undo copy in <home>\changes\<id>\before\. Fields 4c does not name yet
(asked of the guardrails' makers 11/17/26) are written alongside and ignored by a check that reads only 4c's.

The agreed way: a change is talked through until it is exactly clear, never edited without a very clear go,
gets every step it needs (undo copy, edit, rebuild the page, restart the listener, run a check, look at the
page), is done only when seen working, and undoes itself completely when any step is blocked or fails. Every
change is listed with the owner's words, what changed and when. Undo puts the touched files back, warns about
later changes built on it, and says what cannot be taken back.

This file keeps the record and does the steps. The talking is in setup_texts\change-program.md. Edits are made
by Claude (Write/Edit), which the hooks allow only for a change in state "go" or "doing" naming that file.
The owner's personal part (settings, lists, own rules) is not changed this way: it has its own saves.
"""
import datetime as dt
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

PARTS = {"mods": ("Live/mods/",), "taught": ("Live/taught/",)}     # the owner's own; the program's files are written only by an update
STEPS = ("rebuild the page", "restart the listener", "run a check", "look at the page")
OPEN = ("go", "doing")
NO_WINDOW = 0x08000000


class Refused(Exception):
    pass


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def sha(path):
    """The file's checksum with Windows line endings read as plain ones, so a copy that git or an editor saved
    with different line endings never looks changed."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


class Book:
    """The change records of one assistant (ROOT holds System and Live)."""

    def __init__(self, root, home):
        self.root, self.home = os.path.abspath(root), os.path.abspath(home)
        self.folder = os.path.join(self.home, "changes")

    # --- the records ------------------------------------------------------------------------------------
    def path(self, cid):
        return os.path.join(self.folder, cid + ".json")

    def all(self):
        out = []
        for p in sorted(glob.glob(os.path.join(self.folder, "ch-*.json"))):
            try:
                with open(p, encoding="utf-8") as f:
                    out.append(json.load(f))
            except (OSError, ValueError):
                continue
        return out

    def get(self, cid):
        try:
            with open(self.path(cid), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            raise Refused(f"There is no change {cid}.")

    def put(self, c):
        os.makedirs(self.folder, exist_ok=True)
        tmp = self.path(c["id"]) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.path(c["id"]))

    def open_one(self):
        return next((c for c in self.all() if c.get("state") in OPEN), None)

    def full(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def undo_dir(self, cid):
        return os.path.join(self.folder, cid, "before")

    def copy_of(self, cid, rel, which="before"):
        """Where the copy of a file is kept: under the change's folder, by the file's full path without its drive
        (RULEBOOK.md 4c, as rulebook.check_program_edit reads it)."""
        full = os.path.splitdrive(os.path.normcase(os.path.abspath(self.full(rel))))[1].lstrip("\\/")
        return os.path.join(self.folder, cid, which, full)

    @staticmethod
    def clean(rel):
        rel = rel.replace("\\", "/").lstrip("/")
        while rel.startswith("./"):
            rel = rel[2:]
        if ".." in rel.split("/"):
            raise Refused(f"\"{rel}\" reaches outside the assistant.")
        return rel

    # --- the talking-through ---------------------------------------------------------------------------
    def start(self, asked):
        if not str(asked or "").strip():
            raise Refused("Say what you want changed, in your own words.")
        n = 1 + max([int(c["id"].split("-")[1]) for c in self.all()] or [0])
        c = {"id": f"ch-{n:04d}", "asked": asked.strip(), "agreed": "", "part": "", "files": [], "go": None,
             "undo": self.undo_dir(f"ch-{n:04d}"), "state": "talking",
             "agreed_at": None, "created": now(), "before": {}, "after": {}, "steps": [], "built_on": []}
        self.put(c)
        return c

    def agree(self, cid, part, agreed, files):
        c = self.get(cid)
        if c["state"] != "talking":
            raise Refused(f"Change {cid} is past agreeing ({c['state']}).")
        if part == "personal":
            raise Refused("A change to your own settings, lists or rules is made through Settings or /assistant:change, not as a program change.")
        if part not in PARTS:
            raise Refused("The part is mods or taught. The program's own files are never changed here: make the change as a mod.")
        if not str(agreed or "").strip():
            raise Refused("Write the change out in full, as it was said back.")
        rels = []
        for f in files:
            rel = self.clean(f)
            if not rel.startswith(PARTS[part]):
                raise Refused(f"\"{rel}\" is not in the {part} part.")
            rels.append(rel)
        if not rels:
            raise Refused("Name at least one file the change touches.")
        rels = list(dict.fromkeys(rels))
        c.update(part=part, agreed=agreed.strip(), paths=rels, files=[os.path.abspath(self.full(x)) for x in rels], agreed_at=now())
        self.put(c)
        return c

    def go(self, cid, words):
        """The owner's very clear go: save the undo copy, then let the edits through."""
        c = self.get(cid)
        if c["state"] != "talking" or not c.get("agreed"):
            raise Refused(f"Change {cid} is not agreed yet. Say it back and agree it first.")
        other = self.open_one()
        if other:
            raise Refused(f"Change {other['id']} is still being made. Finish or undo it first.")
        if not str(words or "").strip():
            raise Refused("The go must be the owner's own words.")
        before = {}
        for rel in c["paths"]:
            src = self.full(rel)
            before[rel] = sha(src)
            dest = self.copy_of(cid, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if before[rel]:
                shutil.copy2(src, dest)
                if sha(dest) != before[rel]:
                    raise Refused(f"The undo copy of \"{rel}\" did not save correctly; nothing was changed.")
            else:
                open(dest + ".new", "w").close()           # the note that this file is new
        c["built_on"] = [o["id"] for o in self.all() if o.get("state") == "done" and set(o.get("paths") or []) & set(c["paths"])]
        c.update(go={"words": words.strip(), "at": now()}, before=before, state="go")
        c["steps"] = [{"name": "undo copy", "ok": True, "why": "", "at": now()}]
        self.put(c)
        return c

    # --- doing it -----------------------------------------------------------------------------------------
    def put_back(self, c, which="before"):
        """Every touched file back to how it was before this change; a file that was new is removed."""
        for rel in c["paths"]:
            dest = self.full(rel)
            if c["before"].get(rel):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(self.copy_of(c["id"], rel, which), dest)
            elif os.path.exists(dest):
                os.remove(dest)
        bad = [rel for rel in c["paths"] if sha(self.full(rel)) != c["before"].get(rel)]
        if bad:
            raise RuntimeError("These could not be put back exactly: " + ", ".join(bad))

    def _fail(self, c, step, why, runner):
        c["steps"].append({"name": step, "ok": False, "why": why, "at": now()})
        try:
            self.put_back(c)
            c["steps"].append({"name": "put back", "ok": True, "why": "", "at": now()})
            for s in ("rebuild the page", "restart the listener"):          # the program as it was, running again
                ok, w = runner(s)
                c["steps"].append({"name": s + " (after putting back)", "ok": ok, "why": w, "at": now()})
        except Exception as e:  # noqa: BLE001
            c["steps"].append({"name": "put back", "ok": False, "why": str(e)[:300], "at": now()})
        c["state"], c["after"] = "failed", {}
        self.put(c)
        return {"id": c["id"], "state": c["state"], "failed_step": step, "why": why,
                "put_back": all(sha(self.full(r)) == c["before"].get(r) for r in c["paths"])}

    def edited(self, cid, ok, why, runner):
        c = self.get(cid)
        if c["state"] != "go":
            raise Refused(f"Change {cid} is not at its editing step ({c['state']}).")
        if not ok:
            return self._fail(c, "edit", why or "the edit could not be made", runner)
        untouched = [rel for rel in c["paths"] if sha(self.full(rel)) == c["before"].get(rel)]
        c["steps"].append({"name": "edit", "ok": True, "why": ("not changed: " + ", ".join(untouched)) if untouched else "", "at": now()})
        c["state"] = "doing"
        self.put(c)
        return {"id": cid, "state": "doing", "unchanged_files": untouched}

    def check(self, cid, runner):
        """Rebuild the page, restart the listener, run a check, look at the page. The first step that fails puts
        everything back and is named."""
        c = self.get(cid)
        if c["state"] != "doing":
            raise Refused(f"Change {cid} is not ready to check ({c['state']}).")
        for step in STEPS:
            ok, why = runner(step)
            if not ok:
                return self._fail(c, step, why, runner)
            c["steps"].append({"name": step, "ok": True, "why": why, "at": now()})
        c["after"] = {rel: sha(self.full(rel)) for rel in c["paths"]}
        for rel in c["paths"]:                                   # keep the result too
            src = self.full(rel)
            if os.path.isfile(src):
                dest = self.copy_of(cid, rel, "after")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
        c["state"], c["done_at"] = "done", now()
        self.put(c)
        return {"id": cid, "state": "done"}

    def abandon(self, cid, why, runner):
        """The owner, looking at the page, says it is not working: the same complete undo."""
        c = self.get(cid)
        if c["state"] not in ("go", "doing", "done"):
            raise Refused(f"Change {cid} is {c['state']}.")
        if c["state"] == "done" and self.later_on(c):
            raise Refused("Later changes were built on this one; use undo for it.")
        return self._fail(c, "look at the page", why or "the owner saw it was not working", runner)

    def drop(self, cid):
        """A change talked about but never given its go is set aside (nothing was edited)."""
        c = self.get(cid)
        if c["state"] != "talking":
            raise Refused(f"Change {cid} is {c['state']}; only a change not yet started can be set aside.")
        c["state"] = "dropped"
        c["steps"].append({"name": "set aside", "ok": True, "why": "set aside before the go; nothing was edited", "at": now()})
        self.put(c)
        return c

    # --- undo ---------------------------------------------------------------------------------------------
    def later_on(self, c):
        return [o for o in self.all() if o.get("state") == "done" and o["id"] > c["id"] and set(o.get("paths") or []) & set(c["paths"])]

    def undo(self, cid, runner, with_later=False, plan_only=False):
        c = self.get(cid)
        if c["state"] != "done":
            raise Refused(f"Change {cid} is {c['state']}; only a change that is working can be undone.")
        if c.get("undo_note"):
            raise Refused(c["undo_note"])
        other = self.open_one()
        if other:
            raise Refused(f"Change {other['id']} is being made. Finish or undo it first.")
        later = self.later_on(c)
        plan = {"id": cid, "later": [{"id": o["id"], "asked": o["asked"]} for o in later],
                "changed_since": [rel for rel in c["paths"] if sha(self.full(rel)) != c["after"].get(rel)
                                  and not any(rel in (o.get("paths") or []) for o in later)],
                "cannot_take_back": "Cards it made, and anything sent on an approval given while it was working, stay as they are.",
                "working_since": c.get("done_at"), "files": c["paths"]}
        if plan_only:
            return plan
        if later and not with_later:
            raise Refused("Later changes were built on this one: " + ", ".join(o["id"] for o in later)
                          + ". Undo them too (newest first), or leave this one.")
        if plan["changed_since"]:
            raise Refused("These files were changed since, outside any change: " + ", ".join(plan["changed_since"])
                          + ". Putting them back would lose that.")
        done = []
        for o in sorted(later, key=lambda x: x["id"], reverse=True) + [c]:
            o = self.get(o["id"])
            self.put_back(o)
            o["steps"].append({"name": "undone", "ok": True, "why": "", "at": now()})
            o["state"], o["undone_at"] = "undone", now()
            self.put(o)
            done.append(o["id"])
        results = []
        for step in STEPS:
            ok, why = runner(step)
            results.append({"name": step, "ok": ok, "why": why})
            if not ok:
                break
        c = self.get(cid)
        c["steps"] += [dict(r, at=now()) for r in results]
        self.put(c)
        return dict(plan, undone=done, steps=results, working=all(r["ok"] for r in results))

    def listing(self):
        return [{k: c.get(k) for k in ("id", "asked", "agreed", "part", "paths", "state", "done_at", "undone_at", "built_on")}
                for c in self.all()]


# --- the rule the hooks enforce (RULEBOOK.md 4c) ------------------------------------------------------------
GUARDED = ("System/", "Live/taught/", "Live/mods/")


def may_edit(root, path):
    """(allowed, plain reason) for an edit to path. Uses the guardrails' own check when the program has it
    (System\\live\\rules\\rulebook.py); otherwise reads 4c the same way (used by the stand-in tests)."""
    root = os.path.abspath(root)
    full = os.path.abspath(path)
    try:
        inside = os.path.normcase(os.path.commonpath([os.path.normcase(root), os.path.normcase(full)])) == os.path.normcase(root)
    except ValueError:
        inside = False
    if not inside:
        return True, "outside the assistant"
    rel = os.path.relpath(full, root).replace("\\", "/")
    if not rel.startswith(GUARDED):
        return True, "not part of the program or the owner's taught part"
    book = Book(root, os.path.join(root, "Live"))
    c = book.open_one()
    rb = os.path.join(root, "System", "live", "rules", "rulebook.py")
    if os.path.isfile(rb):
        import importlib.util
        spec = importlib.util.spec_from_file_location("rulebook", rb)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        v = mod.check_program_edit(full, c or {})
        return bool(v.get("ok")), "; ".join(b.get("says", "") for b in v.get("broken") or []) or "allowed"
    if not c:
        return False, "C1: The program is changed only on an agreed change with the owner's clear go, its undo copy saved first, only the files it names."
    if rel not in c.get("paths", []):
        return False, f"C1: the change being made ({c['id']}) does not name this file."
    if not (c.get("go") or {}).get("words"):
        return False, "C1: the change has no go from the owner."
    if not rel.startswith(PARTS.get(c.get("part"), ("-",))):
        return False, f"C1: this file is not in the {c.get('part')} part the change names."
    note = book.copy_of(c["id"], rel)
    if not (os.path.isfile(note) or os.path.isfile(note + ".new")):
        return False, "C1: the undo copy of this file is not saved."
    return True, f"allowed by change {c['id']}"


# --- the steps, done the engine's own way ------------------------------------------------------------------
def default_runner(ss, expect=""):
    """(ok, plain why) for each step, using the engine's own pieces. The listener is restarted by its job."""
    live_page = os.path.join(os.path.dirname(ss.common.HERE), "live_page")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=ss.common.HOME)

    def run(step):
        try:
            if step == "rebuild the page":
                r = subprocess.run([sys.executable, os.path.join(live_page, "build_site.py")], capture_output=True, text=True,
                                   env=env, creationflags=NO_WINDOW, timeout=300)
                return (r.returncode == 0, "" if r.returncode == 0 else (r.stderr or r.stdout).strip()[-300:])
            if step == "restart the listener":
                fn = getattr(ss, "restart_listener", None)
                if fn:
                    return fn()
                name = ss.job_names()[1]
                if name not in ss.tasks_on():
                    return False, "the listener is not switched on, so the change cannot be seen on the page"
                subprocess.run(["schtasks", "/End", "/TN", name], capture_output=True, creationflags=NO_WINDOW)
                r = subprocess.run(["schtasks", "/Run", "/TN", name], capture_output=True, text=True, creationflags=NO_WINDOW)
                if r.returncode:
                    return False, "Windows would not start the listener again"
                served = ss.local_page_served(wait=60)
                return (True, "") if served else (False, "the page did not answer within a minute")
            if step == "run a check":
                fn = getattr(ss, "check_once", None)
                ok, lines = fn() if fn else ss.first_pass(say=lambda *_: None)
                return ok, "" if ok else "; ".join(lines)[:300]
            if step == "look at the page":
                if not ss.local_page_served(wait=10):
                    return False, "the page is not answering"
                if expect:
                    app = os.path.join(live_page, "site", "app")
                    text = ""
                    for n in os.listdir(app) if os.path.isdir(app) else []:
                        with open(os.path.join(app, n), encoding="utf-8", errors="replace") as f:
                            text += f.read()
                    if expect not in text:
                        return False, f"the page does not show \"{expect}\""
                return True, ""
        except Exception as e:  # noqa: BLE001
            return False, f"{type(e).__name__}: {e}"[:300]
        return False, f"unknown step {step}"
    return run
