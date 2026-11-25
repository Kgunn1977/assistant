r"""Acceptance: the record of what was last shipped (<root>\Shipped), which an update merges against.

On 11/18 an update recorded it while the plugin's working copy of the engine was being replaced file by file, so the record
held only the files from "readback.py" on, and the next update plan saw every core file before that (answers.py, card.py,
chat.py, items.py, mail.py, the prompts...) as "you added this file and the update adds its own".

- A home whose record is broken that way gets a clean plan: no false clashes; the missing files are taken as shipped as they
  stand (listed under "repaired"), and update-apply then writes the record whole again.
- A file the owner's own recorded change names is never taken as unchanged, even in a broken record: it still clashes.
- With a whole record, a file the owner added that the update also adds still clashes.
- Lay-down, update and adopt read the plugin's engine from one complete, unchanging snapshot; an engine missing core files is
  refused with plain words and nothing changes.
- The working copy's engine is swapped whole: after a refresh it is complete and nothing is left beside it.
On scratch copies laid down from this plugin; nothing outside the scratch folder changes.

    python tests\shipped_record_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def plan(script, root):
    r = subprocess.run([sys.executable, script, "update-plan", "--root", root], capture_output=True, text=True, timeout=600)
    return json.loads(r.stdout) if r.returncode == 0 else {"error": (r.stdout + r.stderr)[-600:]}


def break_record(root):
    """Make the record like the one taken mid-replacement: only the engine files from "readback" on in System/live."""
    sj = os.path.join(root, "Shipped", "shipped.json")
    d = json.load(open(sj, encoding="utf-8"))
    cut = [k for k in d["files"] if k.startswith("System/live/") and k[len("System/live/"):] < "readback"]
    for k in cut:
        del d["files"][k]
        p = os.path.join(root, "Shipped", *k.split("/"))
        if os.path.exists(p):
            os.remove(p)
    json.dump(d, open(sj, "w", encoding="utf-8"), indent=1)
    return cut


def main():
    tmp = tempfile.mkdtemp(prefix="shipped-")
    data = os.path.join(tmp, "plugin-data")
    spec = importlib.util.spec_from_file_location("assistant_copy_shipped", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        script = os.path.join(data, "scripts", "assistant.py")
        lay = lambda root: subprocess.run([sys.executable, script, "lay-down", "--port", "47919", "--sending", "no", "--root", root],
                                          capture_output=True, text=True, timeout=600).returncode
        # 1. a broken record like the one of 11/18
        a = os.path.join(tmp, "A")
        check("lay-down", lay(a), 0)
        cut = break_record(a)
        p = plan(script, a)
        check("the broken record lacks the core files, as on 11/18",
              all(f"System/live/{n}" in cut for n in ("answers.py", "card.py", "chat.py", "items.py", "mail.py", "presses.py", "prompts/items.md",
                                                       "connections/_oauth.py", "core/refresh_contacts.py")), True)
        check("a broken record gets a clean plan: no false clashes, nothing to take, every missing file repaired",
              [p.get("conflict"), p.get("take"), p.get("repaired") == len(cut)], [[], 0, True])
        r = subprocess.run([sys.executable, script, "update-apply", "--root", a], capture_output=True, text=True, timeout=900)
        whole = json.load(open(os.path.join(a, "Shipped", "shipped.json"), encoding="utf-8"))["files"]
        check("update-apply then writes the record whole again",
              [r.returncode, "it is whole again" in r.stdout, all(k in whole for k in cut), plan(script, a).get("repaired")], [0, True, True, 0])
        # 2. a file the owner's own change names still clashes, even with a broken record
        b = os.path.join(tmp, "B")
        lay(b)
        break_record(b)
        with open(os.path.join(b, "System", "live", "mail.py"), "a", encoding="utf-8") as f:
            f.write("\n# the owner's own change\n")
        os.makedirs(os.path.join(b, "Live", "changes"), exist_ok=True)
        json.dump({"id": "ch-0009", "state": "done", "paths": ["System/live/mail.py"]}, open(os.path.join(b, "Live", "changes", "ch-0009.json"), "w"))
        p = plan(script, b)
        check("a file the owner's recorded change names is not taken as unchanged: it still clashes",
              [p.get("conflict"), "System/live/mail.py" in json.dumps(p)], [["System/live/mail.py"], True])
        # 3. with a whole record, a file the owner added that the update also adds still clashes
        c = os.path.join(tmp, "C")
        lay(c)
        sj = os.path.join(c, "Shipped", "shipped.json")
        d = json.load(open(sj, encoding="utf-8"))
        del d["files"]["System/live/tools.py"]
        json.dump(d, open(sj, "w", encoding="utf-8"), indent=1)
        os.remove(os.path.join(c, "Shipped", "System", "live", "tools.py"))
        with open(os.path.join(c, "System", "live", "tools.py"), "w", encoding="utf-8") as f:
            f.write("# a tools.py the owner wrote before the update brought one\n")
        p = plan(script, c)
        check("with a whole record, a file the owner added that the update also adds still clashes",
              [p.get("conflict"), p.get("repaired")], [["System/live/tools.py"], 0])
        # 4. an engine missing core files is refused, with plain words, and nothing changes
        bad = os.path.join(tmp, "bad-plugin")
        shutil.copytree(data, bad)
        os.remove(os.path.join(bad, "engine", "System", "live", "answers.py"))
        before = json.load(open(os.path.join(a, "Shipped", "shipped.json"), encoding="utf-8"))
        r = subprocess.run([sys.executable, os.path.join(bad, "scripts", "assistant.py"), "update-apply", "--root", a], capture_output=True, text=True, timeout=600)
        check("an engine missing core files: refused in plain words, nothing changed",
              [r.returncode, "could not be read whole" in r.stdout, json.load(open(os.path.join(a, "Shipped", "shipped.json"), encoding="utf-8")) == before],
              [1, True, True])
        # 5. the working copy's engine is swapped whole
        with open(os.path.join(data, "assistant-copy.stamp"), "w") as f:
            f.write("old")
        copier.sync(data)
        check("after a refresh the working copy's engine is whole and nothing is left beside it",
              [os.path.isfile(os.path.join(data, "engine", "System", "live", "answers.py")), os.path.exists(os.path.join(data, "engine.old")),
               os.path.exists(os.path.join(data, "engine.new"))], [True, False, False])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
