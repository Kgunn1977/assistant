r"""Acceptance: connecting a roadmap to the page makes it show there, with no other step. On a scratch copy laid down
from this plugin and a scratch project that keeps a roadmap but has no summary written yet. Nothing outside the scratch
folder changes.

    python tests\roadmap_connect_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []

INSIDE = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2]); sys.path.insert(0, sys.argv[3])
import common, setup_steps, roadmaps, setup_home
project = sys.argv[4]
out = {}
setup_steps.apply_roadmap(project)
shown = roadmaps.for_page() or []
out["connected: the roadmap shows on the page at once"] = [len(shown), "first summary" in (shown[0].get("note") or "") if shown else None]
out["the connecting step learns whom to ask"] = setup_home.roadmap_writer_state(project)
print(json.dumps(out))
'''

REMIND = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import reminder, roadmap_blocks as rb
cfg = rb.load_json(rb.config_path(sys.argv[2]), {})
print(json.dumps(reminder.reader_lines({"session_id": "main-1", "cwd": sys.argv[2]}, cfg, sys.argv[2])))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="rm-connect-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    project = os.path.join(tmp, "Kitchen project")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_rm", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47899",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        os.makedirs(os.path.join(project, ".claude", "roadmap"))
        with open(os.path.join(project, ".claude", "roadmap", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"director_session_id": "main-1", "title": "Kitchen project", "page_url": "https://example.invalid/rm",
                       "writer": {"session_id": "local_writer-1", "name": "roadmap-writer", "title": "Roadmap writer",
                                  "claude_session_id": "writer-1"}}, f)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, os.path.join(root, "System", "live_page"),
                            os.path.join(live, "setup"), project], capture_output=True, text=True, env=env, timeout=120)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        if not got:
            check("the checks ran", r.stderr.strip()[-400:], "")
        check("connected: the roadmap shows on the page at once", got.get("connected: the roadmap shows on the page at once"), [1, True])
        check("the connecting step learns whom to ask", got.get("the connecting step learns whom to ask"),
              {"has_plain_copy": False, "writer_session": "local_writer-1", "has_roadmap": True})
        r = subprocess.run([sys.executable, "-c", REMIND, os.path.join(PKG, "hooks"), project], capture_output=True, text=True)
        lines = json.loads(r.stdout or "[]")
        check("the project's main session is told to have the summary written", any("Write the plain copy" in x for x in lines), True)
        os.makedirs(os.path.join(project, "Roadmap page"), exist_ok=True)
        with open(os.path.join(project, "Roadmap page", "roadmap.json"), "w", encoding="utf-8") as f:
            json.dump({"written": "2026-11-17T18:00", "rows": []}, f)
        r = subprocess.run([sys.executable, "-c", REMIND, os.path.join(PKG, "hooks"), project], capture_output=True, text=True)
        check("once written, no more reminder", json.loads(r.stdout or "[]"), [])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
