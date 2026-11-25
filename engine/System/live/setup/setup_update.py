r"""An update meets the owner's own changes. The agreed way: the update reads the change list first, sorts each
change as untouched / needs adjusting / now built in / clashes, works through each with the owner before writing
(for "now built in" it always asks and encourages the built-in one), checks taught add-ons against the new
guardrails, applies the update and the kept changes together, and any failed step puts everything back.

This file only sorts and prepares (read only, plus merged files written into the home for the owner to see).
The update itself is written by assistant.py update-apply, which takes the choices file made here, and puts
everything back if its check fails. The talking is in setup_texts\update-changes.md.
"""
import difflib
import json
import os

import setup_changes as sc

ORDER = {"clashes": 3, "needs adjusting": 2, "now built in": 1, "untouched": 0}


def _lines(path):
    try:
        with open(path, encoding="utf-8", errors="surrogateescape") as f:
            return f.read().splitlines(keepends=True)
    except OSError:
        return None


def _edits(a, b):
    """(start, end, replacement lines) for each place b differs from a, in a's line numbers."""
    return [(i1, i2, b[j1:j2]) for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if tag != "equal"]


def merge3(base, mine, new):
    """(merged lines, clashes). Edits on different lines of base are both kept; the same edit on both sides is kept
    once; different edits touching the same or neighbouring lines are a clash."""
    ours, theirs = _edits(base, mine), _edits(base, new)
    clashes, take = [], []
    for o in ours:
        for t in theirs:
            touch = not (o[1] < t[0] or t[1] < o[0]) or (o[0] == o[1] == t[0] == t[1])
            if touch and not (o[0] == t[0] and o[1] == t[1] and o[2] == t[2]):
                clashes.append((o, t))
    if clashes:
        return None, clashes
    for e in ours + theirs:
        if e not in take:
            take.append(e)
    out, pos = [], 0
    for s, e, rep in sorted(take, key=lambda x: (x[0], x[1])):
        out += base[pos:s] + rep
        pos = max(pos, e)
    return out + base[pos:], []


def _owner_edit_in(base, mine, new):
    """True when everything the owner added is in new and everything they took out is gone from new."""
    added, removed = [], []
    for s, e, rep in _edits(base, mine):
        added += [ln for ln in rep if ln.strip()]
        removed += [ln for ln in base[s:e] if ln.strip()]
    new_set = set(new)
    return all(ln in new_set for ln in added) and not any(ln in new_set and ln not in mine for ln in removed)


def judge(base, mine, new):
    """The one judgment of a file the owner changed and the update brings (lines, or None for no such file), used by the
    change list's sorting here and by assistant.py update-plan alike: (kind, why, merged lines or None)."""
    if new == base:
        return "untouched", "the update does not change this file", None
    if base is None and new is not None and mine is not None:
        return "clashes", "you added this file and the update adds its own", None
    if new is None:
        return "clashes", "the update takes this file out", None
    if mine == new or (base is not None and mine is not None and _owner_edit_in(base, mine, new)):
        return "now built in", "the update makes the same change", None
    merged, clashes = merge3(base or [], mine or [], new)
    if merged is None:
        lines = sorted({o[0] + 1 for o, _ in clashes})
        return "clashes", "you and the update changed the same lines (about line " + ", ".join(map(str, lines[:5])) + ")", None
    return "needs adjusting", "the update changes other lines of this file; your change fits beside them", merged


def sort(book, shipped_root, new_root, work):
    """Each live change, sorted. shipped_root and new_root are folders holding System/ as last shipped and as the
    update brings it. Merged files for "needs adjusting" go under work/merged/<path>."""
    out = []
    for c in [x for x in book.all() if x.get("state") == "done"]:
        files = []
        for rel in c["paths"]:
            if not rel.startswith("System/"):
                files.append({"file": rel, "kind": "untouched", "why": "your own part; an update never writes there",
                              "check_rule_book": True})
                continue
            base = _lines(os.path.join(shipped_root, *rel.split("/")))
            mine = _lines(book.full(rel))
            new = _lines(os.path.join(new_root, *rel.split("/")))
            kind, why, merged = judge(base, mine, new)
            if kind == "needs adjusting":
                dest = os.path.join(work, "merged", *rel.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
                    f.writelines(merged)
                files.append({"file": rel, "kind": kind, "merged": dest, "why": why})
            else:
                files.append({"file": rel, "kind": kind, "why": why})
        kind = max((f["kind"] for f in files), key=ORDER.get) if files else "untouched"
        out.append({"id": c["id"], "asked": c["asked"], "agreed": c["agreed"], "part": c["part"], "kind": kind, "files": files})
    return out


def choices(sorted_changes, decisions, work):
    """The file assistant.py update-apply takes: {path: "new" | "mine" | merged or combined file}. decisions is
    {change id: "built in" | "keep" | "drop" | path of a combination the owner saw}."""
    pick = {}
    for c in sorted_changes:
        d = decisions.get(c["id"])
        if c["kind"] != "untouched" and d is None:
            raise sc.Refused(f"Decide change {c['id']} first.")
        for f in c["files"]:
            rel = f["file"]
            if not rel.startswith("System/") or f["kind"] == "untouched":
                continue
            if d in ("built in", "drop"):
                pick[rel] = "new"
            elif f["kind"] == "needs adjusting" and d == "keep":
                pick[rel] = f["merged"]
            elif d == "keep":
                pick[rel] = "mine"
            elif d and os.path.isfile(d):
                pick[rel] = d
            else:
                raise sc.Refused(f"For change {c['id']} the choice is built in, keep, drop, or a combination file.")
    path = os.path.join(work, "choices.json")
    os.makedirs(work, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pick, f, indent=1)
    return path, pick


def after(book, sorted_changes, decisions, version):
    """Once the update is in and checked: the change list says what became of each change."""
    for s in sorted_changes:
        c = book.get(s["id"])
        d = decisions.get(s["id"], "keep")
        c.setdefault("updates", []).append({"to": version, "kind": s["kind"], "decided": d, "at": sc.now()})
        if d == "built in":
            c["state"] = "built in"
        elif d == "drop":
            c["state"] = "dropped in update"
        else:
            c["after"] = {rel: sc.sha(book.full(rel)) for rel in c["paths"]}
            c["undo_note"] = f"Made before version {version}; to take it out now, ask for a new change."
        book.put(c)
    return [{"id": s["id"], "state": book.get(s["id"])["state"]} for s in sorted_changes]
