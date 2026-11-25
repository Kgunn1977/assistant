"""Acceptance for keeping a roadmap's full copy by patching only the documents just written (roadmap_setup.py
full-patch), on a throwaway project whose full copy is over 250 KB. Run: python tests/full_patch_acceptance.py"""
import copy, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP = os.path.join(HERE, "..", "scripts", "roadmap_setup.py")
PARTS = ("steps", "marks", "questions", "notes", "board")
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (": " + detail if detail and not ok else ""))


def run(project, *args, stdin=None):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}
    p = subprocess.run([sys.executable, SETUP, "--project", project] + list(args), capture_output=True, text=True,
                       input=stdin, env=env)
    return p.returncode, (p.stdout + p.stderr).strip()


def make_db():
    """A made-up roadmap database, big enough that its full copy is over 250 KB."""
    db = {p: {} for p in PARTS}
    filler = "This part reads the plans and lays the pieces out in order, one line per piece. " * 32
    for i in range(90):
        rid = "step-%02d" % i
        db["steps"][rid] = {"order": i * 10, "kind": "step" if i % 3 == 0 else "phase", "number": str(i),
                            "name": "Piece %d" % i, "parent": "" if i % 3 == 0 else "step-%02d" % (i - i % 3),
                            "status": "Ready, waiting for your look" if i % 5 == 0 else "Planned, not started",
                            "changed": "2026-11-0%dT10:00" % (1 + i % 9), "does": "Does thing %d." % i,
                            "plan": filler, "checks": [{"id": "c1", "text": "Open sample A, press Go, see it work."},
                                                       {"id": "c2", "text": "Same file. Press Stop, see it stop."}] if i % 5 == 0 else []}
    for i in range(0, 90, 5):
        db["marks"]["step-%02d--c1" % i] = {"row": "step-%02d" % i, "check": "c1", "text": "Open sample A...",
                                             "result": "works", "note": "", "marked": "2026-11-10T09:00"}
    for i in range(40):
        db["questions"]["q-%02d" % i] = {"row": "step-%02d" % i, "topic": "Topic %d" % i, "question": "Which way? " * 30,
                                         "status": "open" if i % 4 else "done", "asked": "2026-11-05T08:00"}
    for i in range(6):
        db["notes"]["step-%02d--n%d" % (i, i)] = {"row": "step-%02d" % i, "text": "Add the cover sheet.", "status": "open",
                                                   "written": "2026-11-09T12:00"}
    db["board"]["next"] = {"facts_as_of": "2026-11-17", "lines": [{"label": "Working on now", "text": "nothing"},
                                                                   {"label": "Next", "text": "Piece 3"}]}
    db["board"]["settings"] = {"title": "Sample roadmap"}
    return db


def apply_db(db, writes):
    """What the database itself does with the writes (the reference the copy must match)."""
    for w in writes:
        col = db[w["collection"]]
        if w["op"] == "delete":
            col.pop(w["doc_id"], None)
        elif w["op"] == "set":
            col[w["doc_id"]] = dict(w["data"])
        else:
            for k, v in w["data"].items():
                if isinstance(v, dict) and v.get("__delete__"):
                    col[w["doc_id"]].pop(k, None)
                else:
                    col[w["doc_id"]][k] = v


def write_whole(project, db):
    """The old way: the full copy written whole from the database, then checked."""
    path = os.path.join(project, "Roadmap page", "roadmap-full.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"collections": db}, fh)
    return run(project, "full")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def without_stamp(doc):
    doc = dict(doc)
    doc.pop("written", None)
    return doc


def plain_reference(project, db):
    """The plain copy as the facts check makes it from the same database (agreement part 1)."""
    sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
    sys.path.insert(0, os.path.join(HERE, "..", "hooks"))
    import roadmap_setup as rs
    tidy, wrong = rs.check_facts(rs.facts_from(db))
    assert not wrong, wrong
    return tidy


def project_with(db):
    project = tempfile.mkdtemp(prefix="full-patch-")
    os.makedirs(os.path.join(project, ".claude", "roadmap"))
    os.makedirs(os.path.join(project, "Roadmap page"))
    with open(os.path.join(project, ".claude", "roadmap", "config.json"), "w", encoding="utf-8") as fh:
        json.dump({"director_session_id": "s-main", "writes": "main", "title": "Sample roadmap",
                   "page_url": "https://claude.ai/code/artifact/0000-sample"}, fh)
    with open(os.path.join(project, "Roadmap page", "readers.json"), "w", encoding="utf-8") as fh:
        json.dump({"readers": {"assistant": {"since": "2026-11-17T10:00:00", "full": True}}}, fh)
    code, out = write_whole(project, db)
    assert code == 0, out
    return project


def patch(project, writes, name="patch.json"):
    path = os.path.join(tempfile.mkdtemp(prefix="scratch-"), name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"writes": writes}, fh)
    cmd = 'python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" full-patch "' + path + '"'
    code, out = run(project, "full-patch", path)
    with open(path, encoding="utf-8") as fh:
        traffic = len(fh.read()) + len(cmd) + len(out)
    return code, out, traffic


def same_as_whole(project, db, label):
    """The patched copies against copies written whole from the same database, in a second throwaway project."""
    full = read(os.path.join(project, "Roadmap page", "roadmap-full.json"))
    ref_project = project_with(db)
    ref = read(os.path.join(ref_project, "Roadmap page", "roadmap-full.json"))
    check(label + ": full copy matches a whole rewrite, parsed", full["collections"] == ref["collections"])
    a = json.dumps(without_stamp(full), indent=1, sort_keys=True)
    b = json.dumps(without_stamp(ref), indent=1, sort_keys=True)
    check(label + ": full copy matches a whole rewrite, byte for byte apart from the time stamp", a == b)
    plain = without_stamp(read(os.path.join(project, "Roadmap page", "roadmap.json")))
    want = plain_reference(project, db)
    check(label + ": plain copy matches the facts worked out from the database",
          all(plain.get(k) == v for k, v in want.items()), json.dumps({k: (plain.get(k), v) for k, v in want.items()
                                                                       if plain.get(k) != v})[:400])


def main():
    db = make_db()
    project = project_with(db)
    full_path = os.path.join(project, "Roadmap page", "roadmap-full.json")
    size = os.path.getsize(full_path)
    check("the throwaway full copy is at least 250 KB", size >= 250 * 1024, str(size))
    print("     full copy size: %d bytes" % size)

    # 1. A write turn that changes one row.
    writes = [{"op": "update", "collection": "steps", "doc_id": "step-07", "if_version": 3,
               "data": {"status": "Being worked on now", "changed": "2026-11-18T09:30"}}]
    apply_db(db, writes)
    code, out, traffic = patch(project, writes)
    check("one-row change: the command succeeds", code == 0, out)
    same_as_whole(project, db, "one-row change")
    tokens = (traffic + 2) // 3
    check("one-row change: the main session's traffic for the copies stays under 5,000 tokens", tokens < 5000, str(tokens))
    print("     traffic: %d characters, at most about %d tokens (at 3 characters a token; about %d at 4)"
          % (traffic, tokens, (traffic + 3) // 4))

    # 2. A row deleted, a mark taken back on the page, a new row, a field removed, an answer the page wrote.
    answered = dict(db["questions"]["q-01"], status="answered", answer="A. The first way", choice="A", answered="2026-11-18T09:40")
    writes = [{"op": "delete", "collection": "steps", "doc_id": "step-89"},
              {"op": "delete", "collection": "marks", "doc_id": "step-05--c1"},
              {"op": "set", "collection": "steps", "doc_id": "item-new",
               "data": {"order": 905, "kind": "item", "number": "", "name": "New piece", "parent": "",
                        "status": "Planned, not started", "changed": "2026-11-18T09:45"}},
              {"op": "update", "collection": "steps", "doc_id": "step-10", "data": {"plan": {"__delete__": True}}},
              {"op": "set", "collection": "questions", "doc_id": "q-01", "data": answered},
              {"op": "update", "collection": "board", "doc_id": "next",
               "data": {"facts_as_of": "2026-11-18", "lines": [{"label": "Working on now", "text": "Piece 7"}]}}]
    apply_db(db, writes)
    code, out, _ = patch(project, writes)
    check("deleted row, taken-back mark, new row: the command succeeds", code == 0, out)
    full = read(full_path)["collections"]
    check("the deleted row is gone from the full copy", "step-89" not in full["steps"])
    check("the new row is in the full copy", full["steps"].get("item-new", {}).get("name") == "New piece")
    plain = read(os.path.join(project, "Roadmap page", "roadmap.json"))
    ids = [r["id"] for r in plain["rows"]]
    check("the plain copy drops the deleted row and lists the new one", "step-89" not in ids and "item-new" in ids)
    same_as_whole(project, db, "deleted and new rows")

    # 3. An update the copy cannot place is refused and changes nothing.
    before = open(full_path, encoding="utf-8").read()
    code, out, _ = patch(project, [{"op": "update", "collection": "steps", "doc_id": "nowhere", "data": {"status": "Done, confirmed"}}])
    check("an update of a document the copy lacks is refused", code != 0 and "no such document" in out, out)
    check("... and the copy is left exactly as it was", open(full_path, encoding="utf-8").read() == before)

    # 4. A missing copy: said once, plainly, nothing made up.
    os.replace(full_path, full_path + ".aside")
    code, out, _ = patch(project, [{"op": "update", "collection": "steps", "doc_id": "step-07", "data": {"name": "X"}}])
    check("a missing copy is refused", code != 0 and "no full copy" in out, out)
    check("... said once", out.count("Not done") == 1 and len(out.splitlines()) == 1, out)
    check("... and no copy is made up", not os.path.exists(full_path))
    os.replace(full_path + ".aside", full_path)

    # 5. A damaged copy (not JSON, and the wrong shape): said once, the file left as it is.
    for label, text in (("not JSON", '{"collections": {"steps": '), ("wrong shape", '{"collections": {"steps": []}}')):
        with open(full_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        code, out, _ = patch(project, [{"op": "update", "collection": "steps", "doc_id": "step-07", "data": {"name": "X"}}])
        check("a damaged copy (" + label + ") is refused", code != 0 and "damaged" in out, out)
        check("... said once", out.count("Not done") == 1 and len(out.splitlines()) == 1, out)
        check("... and left exactly as it was", open(full_path, encoding="utf-8").read() == text)

    print("%d of %d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
