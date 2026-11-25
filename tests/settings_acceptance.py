r"""Acceptance: Settings, in a scratch home (never the owner's; no scheduled job is made or touched: the computer's job list is
stood in for by a stub that answers as Windows' schtasks does).

  1. Gathering is the one real switch: it reads Paused when the scheduled pass is switched off even with nothing saved, a save that
     keeps it Paused leaves the job off, switching it to Running switches the job on, Paused switches it off again; a pass run by
     hand stands down only for a pause chosen on the page;
  2. what is changed only with a command is no longer a Settings part: it is a list of Tools entries, each with a real command
     of the plugin (its skill exists, and a part of /assistant:change exists in the change walk-through);
  3. every setting, command entry and Tools entry carries the explanation its (i) pop-up shows.

    python tests\settings_acceptance.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


INSIDE = r'''
import json, os, sys, types
sys.path.insert(0, sys.argv[1])
import common, db, settings_page, settings_data, paths
db.init_schema()
out = {}
job = {"off": True, "asked": []}           # the scheduled pass, switched off (as on a home where it was switched off by hand)
def fake_run(cmd, **kw):
    job["asked"].append(cmd[1])
    if cmd[1] == "/Query":
        return types.SimpleNamespace(returncode=0, stdout="TaskName: \\" + paths.job_names()[0] + "\nStatus: " + ("Disabled" if job["off"] else "Ready") + "\n", stderr="")
    if cmd[1] == "/Change":
        job["off"] = cmd[-1] == "/DISABLE"
        return types.SimpleNamespace(returncode=0, stdout="SUCCESS", stderr="")
    raise AssertionError(cmd)
settings_page.subprocess.run = fake_run
settings_page.JOB_SECONDS = 0
def shown():
    return settings_page.for_page()["watch"]["paused"]
def save(paused):
    ok, line = settings_page.save({"settings": {"group": "watch", "values": {"paused": paused, "every_minutes": 15}}})
    return [ok, job["off"], line.split(": ", 1)[-1][:70]]
out["reads Paused when the job is off, with nothing saved"] = [shown(), settings_page.paused_flag()]
out["a save that keeps Paused leaves the job off"] = save(True)
out["Running switches the job on"] = save(False) + [shown()]
out["Paused switches it off again"] = save(True) + [shown(), settings_page.paused_flag()]
job["off"] = False
settings_page.save({"settings": {"group": "watch", "values": {"paused": False}}})
out["a pass by hand runs while only the job is off"] = (lambda: (job.update(off=True), [settings_page.paused(), settings_page.paused_flag()])[1])()
os.makedirs(common.PERSONAL, exist_ok=True)
json.dump({"version": "9.9.9"}, open(os.path.join(common.PERSONAL, "install.json"), "w"))
out["the Settings data carries the installed version"] = settings_page.for_page()["version"]
os.remove(os.path.join(common.PERSONAL, "install.json"))
out["no install.json: no version and no error"] = settings_page.for_page()["version"]
d = settings_data.defs()
out["no part changed only with a command"] = [g["id"] for g in d["groups"] if g["id"] == "pc_only"] + [x["id"] for x in d["settings"] if x["group"] == "pc_only"]
out["commands"] = [[c["id"], c["command"]] for c in d["commands"]]
import tools, project_tools
def unexplained(rows):          # an (i) with nothing real behind it: no words, or a note that was never finished
    return [x.get("id") for x in rows if not str(x.get("explain") or "").strip() or str(x.get("explain")).startswith("UNSURE")]
out["settings with no explanation"] = unexplained(d["settings"]) + unexplained(d["commands"]) + unexplained(tools.TOOLS) + unexplained(project_tools.TOOLS)
print(json.dumps(out))
'''

WANT = {
    "the Settings data carries the installed version": "9.9.9",
    "no install.json: no version and no error": "",
    "reads Paused when the job is off, with nothing saved": [True, False],
    "a save that keeps Paused leaves the job off": [True, True, "nothing was different, so nothing was changed."],
    "Running switches the job on": [True, False, "Check for new messages. I'm checking for new messages again, next with", False],
    "Paused switches it off again": [True, True, "Check for new messages. I've stopped checking for new messages. Your a", True, True],
    "a pass by hand runs while only the job is off": [True, False],
    "no part changed only with a command": [],
    "commands": [["accounts", "/assistant:change accounts"], ["sending", "/assistant:change sending"], ["page", "/assistant:change page"],
                 ["projects", "/assistant:introduce"], ["roadmaps", "/assistant:roadmap-setup"]],
    "settings with no explanation": [],
}


def real_command(cmd):
    """A command of the plugin: its skill exists, and a part after /assistant:change is a part of the change walk-through."""
    m = re.fullmatch(r"/assistant:([a-z-]+)(?: ([a-z-]+))?", cmd)
    if not m or not os.path.isfile(os.path.join(PKG, "skills", m.group(1), "SKILL.md")):
        return False
    if m.group(2):
        walk = open(os.path.join(PKG, "engine", "System", "live", "setup", "setup_texts", m.group(1) + ".md"), encoding="utf-8").read()
        return re.search(r"^## " + re.escape(m.group(2)) + r"\b", walk, re.M) is not None
    return True


def engine_part():
    tmp = tempfile.mkdtemp(prefix="set-")
    live = os.path.join(PKG, "engine", "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=120, encoding="utf-8")
    import _cleanup
    _cleanup.remove(tmp)
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        check("the engine checks ran", r.stderr.strip()[-1500:], "")
        return
    for k, v in WANT.items():
        check(k, got.get(k), v)
    check("every command shown is a real command of the plugin", [c for _i, c in got.get("commands") or [] if not real_command(c)], [])


engine_part()
page = open(os.path.join(PKG, "engine", "System", "live_page", "page.html"), encoding="utf-8").read()
check("the Settings header shows the version when the data has one", "st && st.version ? ' <small class=\"set-ver\">Version ' + h(st.version)" in page and "<h2>Settings'" in page, True)
for name, ok, got, want in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n   got  {got}\n   want {want}"))
print(f"{sum(1 for r in results if r[1])}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
