r"""Roadmaps, as the page sees them: which project folders the owner chose to show, and what each
project's roadmap says now.

Roadmaps come from a separate Claude plugin (Roadmap). The assistant holds and runs none of its files.
The whole link is the plugin's one written agreement (reference\agreement.md in the plugin): a project's
roadmap lives on its own page, in a store only Claude can read, and while a reader is listed in the
project the roadmap's writer also keeps a small plain summary there:

    <project folder>\Roadmap page\roadmap.json

This file reads those summaries, and works the same whether the plugin is on this computer or not. It reads only; it never writes into a project, starts nothing and
uses no AI. The one file it writes is in the owner's home (page_state\roadmaps_last.json): each roadmap as
last shown, so a plain copy caught between the writer's write and its check keeps showing what it did. The sender (publish.py) adds what it returns to the page's data, and the listener looks at
signature() between its waits so a change shows without waiting for the next pass.

The list of projects is `roadmaps` in the personal folder's settings.json, written by first-time setup
(setup_steps.apply_roadmap): [{"folder": "C:\\...\\My Project", "applied": "2026-03-04T10:05:00"}].
With nothing chosen, for_page() gives None and the page's data carries no trace of roadmaps.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.environ.get("ASSISTANT_LIVE_HOME") or os.path.join(os.path.dirname(os.path.dirname(HERE)), "Live")
SETTINGS = os.path.join(HOME, "personal", "settings.json")
PLAIN_COPY = os.path.join("Roadmap page", "roadmap.json")
FULL_COPY = os.path.join("Roadmap page", "roadmap-full.json")    # agreement part 2: every document the roadmap's page reads
COLLECTIONS = ("steps", "marks", "notes", "questions", "board")
LAST = os.path.join(HOME, "page_state", "roadmaps_last.json")     # each roadmap as last shown; the page's own state
NEXT_MAX, ROWS_MAX, TEXT_MAX = 12, 400, 400
AGREEMENT = 1                 # the agreement number this reader follows
NOT_YET = ("Nothing to show yet. If this project has no roadmap, open its folder in the Claude desktop app's Code tab "
           "and send /assistant:roadmap-setup (Claude needs the Roadmap plugin). If it has one, it shows here after its Roadmap "
           "writer's next change.")
WAITING = ("Waiting for this roadmap's first summary. Its Roadmap writer has been asked to write it; it shows here a few "
           "minutes after that.")
NEWER = "This roadmap is written in a newer form than this assistant reads. A newer assistant will show it."

_cache = {"mark": None, "list": []}


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            got = json.load(f)
        return got if isinstance(got, dict) else None
    except (OSError, ValueError):
        return None


def _mark(path):
    try:
        st = os.stat(path)
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None


def applied():
    """The project folders the owner applied the roadmap to, in the order they applied them."""
    mark = _mark(SETTINGS)
    if mark != _cache["mark"]:
        out, seen = [], set()
        for e in (_read(SETTINGS) or {}).get("roadmaps") or []:
            folder = str(e.get("folder") or "").strip() if isinstance(e, dict) else ""
            if folder and os.path.normcase(folder) not in seen:
                seen.add(os.path.normcase(folder))
                out.append(folder)
        _cache.update(mark=mark, list=out)
    return list(_cache["list"])


def plain_copy(folder):
    return os.path.join(folder, PLAIN_COPY)


def signature():
    """Changes whenever the list of projects or any project's plain or full copy changes. Costs two looks at each project."""
    return tuple((os.path.normcase(f), _mark(plain_copy(f)), _mark(os.path.join(f, FULL_COPY))) for f in applied())


def _text(value, limit=TEXT_MAX):
    return " ".join(str(value if value is not None else "").split())[:limit]


def _number(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def one(folder):
    """One project's roadmap as the page shows it. Never raises: a project that cannot be read says why."""
    out = {"key": hashlib.sha1(os.path.normcase(folder).encode("utf-8")).hexdigest()[:10],
           "name": os.path.basename(folder.rstrip("\\/")) or folder, "folder": os.path.basename(folder.rstrip("\\/")) or folder}
    if not os.path.isdir(folder):
        out["note"] = "This project's folder is not where it was: " + folder
        return out
    doc = _read(plain_copy(folder))
    if os.path.exists(plain_copy(folder)) and not (doc and doc.get("written")):
        kept = (_read(LAST) or {}).get(out["key"])      # the writer is between writing the file and checking it
        if isinstance(kept, dict):
            return kept
    if not doc or not doc.get("written"):         # a roadmap the project keeps, not summarised yet, or none at all
        has = (os.path.isfile(os.path.join(folder, ".claude", "roadmap", "config.json"))
               or os.path.isfile(os.path.join(folder, "Roadmap page", "roadmap.html")))
        out["note"] = WAITING if has else NOT_YET
        return out
    if isinstance(doc.get("agreement"), int) and doc["agreement"] > AGREEMENT:
        out["note"] = NEWER
        return out
    if _text(doc.get("name")):
        out["name"] = _text(doc.get("name"), 120)
    link = str(doc.get("page_url") or "").strip()
    if link.startswith("https://claude.ai/") and not any(c in link for c in "\"'<> \\"):
        out["link"] = link
    out["next"] = [{"label": _text(n.get("label"), 60), "text": _text(n.get("text"))}
                   for n in (doc.get("next") or [])[:NEXT_MAX] if isinstance(n, dict)]
    rows, newest = [], ""
    listed = [r for r in (doc.get("rows") or []) if isinstance(r, dict) and _text(r.get("name"))]
    for r in listed[:ROWS_MAX]:
        changed = _text(r.get("changed"), 25)
        newest = max(newest, changed)
        rows.append({"n": _text(r.get("number"), 12), "name": _text(r.get("name"), 200), "kind": _text(r.get("kind"), 10),
                     "status": _text(r.get("status"), 60), "changed": changed, "sub": bool(_text(r.get("parent")))})
    out["rows"] = rows
    out["rows_total"] = len(listed)
    out["checks_waiting"] = _number(doc.get("checks_waiting"))
    out["questions_open"] = _number(doc.get("questions_open"))
    out["changed"] = newest or _text(doc.get("written"), 25)
    out["written"] = _text(doc.get("written"), 25)
    return out


def for_page():
    """Every chosen project's roadmap, or None when none is chosen. A roadmap connected but not summarised yet shows
    with a line saying it waits for its first summary, so connecting one always shows it on the page."""
    folders = applied()
    if not folders:
        return None
    out = [one(f) for f in folders]
    good = {r["key"]: r for r in out if not r.get("note")}
    if (good or os.path.exists(LAST)) and good != (_read(LAST) or {}):     # what was last shown, for a file caught mid-write
        try:
            os.makedirs(os.path.dirname(LAST), exist_ok=True)
            tmp = LAST + ".tmp" + str(os.getpid())
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(good, f)
            os.replace(tmp, LAST)
        except OSError:
            pass
    return out or None


def full_docs():
    """{"roadmap-<key>": the whole roadmap} for every chosen project whose writer keeps the full copy (agreement part 2),
    in the shape the page's own roadmap script reads (page to engine.md, item 1). A copy not finished yet (no `written`)
    is left out, so the page keeps the one it has. Pictures are passed as the roadmap holds them."""
    out = {}
    for folder in applied():
        doc = _read(os.path.join(folder, FULL_COPY))
        col = doc.get("collections") if doc and doc.get("written") else None
        if not isinstance(col, dict):
            continue
        key = hashlib.sha1(os.path.normcase(folder).encode("utf-8")).hexdigest()[:10]
        page = {"key": key, "name": _text(doc.get("name"), 120) or os.path.basename(folder.rstrip("\\/")),
                "page_url": str(doc.get("page_url") or ""), "as_of": _text(doc.get("written"), 25)}
        for c in COLLECTIONS:
            got = col.get(c)
            page[c] = {k: v for k, v in got.items() if isinstance(v, dict)} if isinstance(got, dict) else {}
        out["roadmap-" + key] = page
    return out
