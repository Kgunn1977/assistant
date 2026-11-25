r"""Acceptance (quick): a draft a desktop Claude session adds (python System\live\ready.py draft <file>, as the home's CLAUDE.md
says) is in Ready to send on the page at once, the way one from the page's chat is: the page's data is refreshed by the same
command, not left for the next check. On a scratch home laid down from this plugin, made-up mail; nothing is sent.

    python tests\desktop_draft_acceptance.py
"""
import glob
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


def main():
    tmp = tempfile.mkdtemp(prefix="desktopdraft-")
    data, root = os.path.join(tmp, "data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_desk", os.path.join(PKG, "hooks", "assistant_copy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    try:
        m.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47945", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import db; db.init_schema(); con = db.connect(); "
                        "con.execute(\"INSERT INTO contacts (key, person_id, name) VALUES ('email:lee@acme.example', 901, 'Lee Made-up')\"); con.close()", live],
                       env=env, cwd=live, check=True)
        subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)   # a home after its first check
        f = os.path.join(tmp, "draft.json")
        with open(f, "w", encoding="utf-8") as fh:
            json.dump({"kind": "new", "to": ["lee@acme.example"], "subject": "Prices for the heads", "body": "The prices are below.\n\nThanks,",
                       "why": "a made-up test draft"}, fh)
        r = subprocess.run([sys.executable, os.path.join(live, "ready.py"), "draft", f], capture_output=True, text=True, env=env, cwd=live, timeout=300)
        said = r.stdout.strip()
        check("the draft is put in Ready to send and the command says so", said.startswith("In Drafts, in the Email part of the page ("), True)
        iid = said.split("(", 1)[1].split(")", 1)[0] if "(" in said else ""
        pages = [p for p in glob.glob(os.path.join(home, "page_state", "**", "*.json"), recursive=True) if "local_site" not in p]
        on_page = any(iid and iid in open(p, encoding="utf-8").read() for p in pages)
        check("the page's data is refreshed by the same command (no waiting for the next check)",
              (bool(iid), on_page, "could not be refreshed" in said), (True, True, False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
