r"""A mod proves itself on the owner's page: its check cards.

When a mod is made or changed (the chat's change flow, /assistant:change), its checks are written beside it, in
<home>\mods\<name>\checks.json:
    {"checks": [{"id": "c1", "try": "what to try", "expect": "what should happen",
                 "state": "open | passed | fixing | dropped", "card": "<card source key>", "round": 1, "words": "..."}],
     "proven": false, "proven_at": ""}
The writer of the mod gives only "try" and "expect" (and keeps an existing check's id and state); this module adds the rest.

Each open check is a plain card (source key live:modcheck-<mod>-<id>r<round>), a numbered question with two choices:
    Works           the check passed; when every check of the mod has passed the mod is proven (Settings shows it)
    Doesn't work    opens the card's box, "What happened?"; the words go to the assistant, which fixes the mod through the
                    normal change path (an undo copy first, only the mod's own files), then puts a new card up for that check
Done drops the check without passing it (the mod then stays unproven); Snooze, Other and the box are the page's usual ones.
The cards belong to this module (mods.owns): the card writer and the rebuild leave them alone.
"""
import json
import os
import re
import sys

import common

PREFIX = "live:modcheck-"
KEY = re.compile(r"^live:modcheck-([a-z][a-z0-9-]*)-(c\d+)r(\d+)$")
PASS_ID = "mod-checks"
GO = "Yes, make this change (your words on a check card that did not work)"
WORDS = {"works": "Works", "doesnt": "Doesn't work"}


def is_check(item):
    return bool(KEY.match(str((item or {}).get("source_key") or "")))


def _folder(name):
    return os.path.join(common.HOME, "mods", name)


def load(name):
    return common.read_json(os.path.join(_folder(name), "checks.json"), None)


def save(name, doc):
    common.write_json(os.path.join(_folder(name), "checks.json"), doc)


def _title(name):
    try:
        import mods
        m = next((m for m in mods.listed() if m["name"] == name), {})
        return str(m.get("title") or name)
    except Exception:  # noqa: BLE001
        return name


def _normal(doc):
    """The document with every check complete: ids, states. Returns (doc, changed)."""
    before = json.dumps(doc, sort_keys=True)
    doc = doc if isinstance(doc, dict) else {}
    out, seen = [], set()
    for c in doc.get("checks") or []:
        if not isinstance(c, dict) or not str(c.get("try") or "").strip():
            continue
        cid = str(c.get("id") or "")
        if not re.fullmatch(r"c\d+", cid) or cid in seen:
            n = 1
            while f"c{n}" in seen or any(f"c{n}" == str(x.get("id")) for x in doc["checks"] if x is not c):
                n += 1
            cid = f"c{n}"
        seen.add(cid)
        out.append(dict(c, id=cid, state=c.get("state") if c.get("state") in ("open", "passed", "fixing", "dropped") else "open"))
    doc["checks"] = out
    doc["proven"] = bool(out) and all(c["state"] == "passed" for c in out)
    if not doc["proven"]:
        doc["proven_at"] = ""
    elif not doc.get("proven_at"):
        doc["proven_at"] = common.now().isoformat(timespec="seconds")
    return doc, json.dumps(doc, sort_keys=True) != before


def _card_state(key):
    import db
    con = db.connect(read_only=True)
    try:
        r = con.execute("SELECT state FROM live_items WHERE source_key=?", [key]).fetchone()
    finally:
        con.close()
    return r[0] if r else None


def _put_card(name, c):
    import items
    key = f"{PREFIX}{name}-{c['id']}r{c['round']}"
    again = " (again, after a fix)" if c["round"] > 1 else ""
    iid, _ = items.upsert(
        key, PASS_ID, kind="question", area=_title(name), state="question", importance=0, source_when=common.now(),
        title=f"Check {_title(name)}: {c['try']}", source_who=_title(name),
        recommended="Try it and tell me what happens.",
        why=f"What should happen: {c['expect']}{again}", asks=["Did it work?"],
        extra=json.dumps({"check": {"mod": name, "id": c["id"]},
                          "choices": [{"label": "Works", "text": "Works", "recommended": True},
                                      {"label": "Doesn't work (say which)", "text": "Doesn't work"}]}))
    return key, iid


def sync(name, put=True):
    """One mod's checks made whole: complete the file, a card for each open check that has none, and a check whose card was
    closed with Done dropped. Returns the document (None when the mod has no checks)."""
    doc = load(name)
    if doc is None:
        return None
    doc, changed = _normal(doc)
    for c in doc["checks"]:
        if c["state"] == "open" and c.get("card"):
            if _card_state(c["card"]) == "done":
                c["state"], changed = "dropped", True
        if put and c["state"] == "open" and not c.get("card"):
            c["round"] = int(c.get("round") or 0) + 1
            c["card"], _ = _put_card(name, c)
            changed = True
    doc, _c = _normal(doc)
    if changed or _c:
        save(name, doc)
    return doc


def sync_all(put=True):
    """Every mod's checks (the pass does this). The page's cards are written by the caller's export."""
    import mods
    out = {}
    for m in mods.listed():
        if os.path.isfile(os.path.join(m["folder"], "checks.json")):
            out[m["name"]] = sync(m["name"], put)
    return out


def proven(name):
    doc = load(name)
    return bool(doc and doc.get("proven"))


def status(name):
    """(proven, passed, total) for Settings, or None when the mod has no checks."""
    doc = load(name)
    if not doc or not doc.get("checks"):
        return None
    cs = doc["checks"]
    return bool(doc.get("proven")), sum(c["state"] == "passed" for c in cs), len(cs)


# --- the card's own buttons and answers (mods.py asks) ------------------------------------------------
def answer(item, rec, on_update=None):
    """Works, or the words of a Doesn't work. {"said", "fields", "claude"}; None leaves it to the program."""
    m = KEY.match(str(item.get("source_key") or ""))
    name, cid = m.group(1), m.group(2)
    doc = load(name) or {}
    c = next((x for x in doc.get("checks") or [] if x.get("id") == cid), None)
    text = " ".join(str(rec.get("text") or "").split())
    if c is None or c.get("state") != "open" or not text:
        return {"said": "That check is not open any more. Nothing was changed.", "fields": {}}
    if text.lower() == "works":
        c["state"] = "passed"
        doc, _ = _normal(doc)
        save(name, doc)
        said = f"Passed: {c['try']}"
        if doc["proven"]:
            said += f" Every check of {_title(name)} has passed: it is proven."
        return {"said": said, "fields": {"state": "done", "status": "Done"}}
    if text.lower() == WORDS["doesnt"].lower():
        return {"said": "What happened? Say it in the box on the card.", "fields": {}}
    c["state"], c["words"] = "fixing", text
    save(name, doc)
    said = fix(name, c, text)
    return {"said": said, "fields": {"state": "done", "status": "Done"}, "claude": True}


def fix(name, c, words):
    """The owner's words about a check that did not work, taken to the normal change path: recorded (an undo copy is
    saved first), then change_job.py edits only the mod's own files and checks the page. Returns a line for the owner."""
    setup = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup")
    if setup not in sys.path:
        sys.path.insert(0, setup)
    import setup_changes as sc
    import answers
    book = sc.Book(os.path.dirname(common.HOME), common.HOME)
    files = sorted(f for f in os.listdir(_folder(name)) if os.path.isfile(os.path.join(_folder(name), f))
                   and f != "checks.json" and not f.startswith("."))
    try:
        ch = book.start(f"Fix the mod {name}: this check did not work.")
        book.agree(ch["id"], "mods",
                   f"Fix the mod {name} only in its own files. What was tried: {c['try']} What should have happened: {c['expect']} "
                   f"What happened instead, in the owner's words: {words}",
                   [f"Live/mods/{name}/{f}" for f in files])
        book.go(ch["id"], GO)
    except sc.Refused as e:
        reopen(name, c["id"], f"The fix could not be started ({e}). Nothing was changed.")
        return f"The fix could not be started: {e} Nothing was changed. The check is up again."
    doc = load(name)
    for x in doc["checks"]:
        if x["id"] == c["id"]:
            x["change"] = ch["id"]
    save(name, doc)
    if not answers.start_hidden([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "change_job.py"), ch["id"]]):
        reopen(name, c["id"], "The fix could not be started on this computer. Nothing was changed.")
        return "The fix could not be started on this computer. Nothing was changed. The check is up again."
    return "Thank you. I am fixing it now, only in this mod's own files, with a copy to undo to. The check comes back when it is done."


def reopen(name, cid, why=""):
    """The check is open again with a new card (after a fix, or when the fix could not be made)."""
    doc = load(name)
    for x in (doc or {}).get("checks") or []:
        if x["id"] == cid and x["state"] in ("fixing", "open"):
            x["state"], x["card"] = "open", ""
            x.pop("change", None)
    if doc:
        save(name, doc)
        sync(name)


def _own_check(c):
    """The check a change gets when its edit wrote none: try what was asked for, expect what was agreed."""
    asked = " ".join(str(c.get("asked") or "").split()).rstrip(".")
    agreed = " ".join(str(c.get("agreed") or "").split()).rstrip(".")
    return {"try": f"Use the change you asked for: {asked or agreed}.", "expect": f"{agreed or asked}.", "for": c.get("id")}


def after_change(c, ok):
    """change_job.py and the computer's change-check (setup_home.py) call this when a change ends: a fix puts a new card up
    for its check; a change that made or changed a mod puts up the cards for the checks it wrote, and a change that wrote no
    new check gets one of its own, so every change shows check cards on the page (spec 8.2)."""
    paths = c.get("paths") or []
    home = os.path.basename(os.path.normpath(common.HOME)) or "Live"
    names = {p.split("/")[2] for p in paths if p.split("/")[:2] in (["Live", "mods"], [home, "mods"]) and p.count("/") >= 3}
    for name in names:
        doc = load(name)
        if doc is None and not ok:
            continue
        doc = doc if isinstance(doc, dict) else {"checks": []}
        doc["checks"] = [x for x in doc.get("checks") or [] if isinstance(x, dict)]
        for x in doc["checks"]:
            if x.get("change") == c.get("id"):
                x["state"], x["card"] = "open", ""
                x.pop("change", None)
        if ok and not any(x.get("state", "open") == "open" and not x.get("card") or x.get("for") == c.get("id") for x in doc["checks"]):
            doc["checks"].append(_own_check(c))
        save(name, doc)
        sync(name)
    if names:
        try:
            import items
            items.export(PASS_ID)
        except Exception:  # noqa: BLE001  the next pass shows them
            pass
