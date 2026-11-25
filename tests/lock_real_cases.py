"""The guardrail lock on real commands (Kevin 11/25/26: guards stop only really bad things; the roadmap is not
critical). The release steps, edits that only mention a guard, the roadmap's own files and switching the roadmap off go
through; real writes to a project's settings and hooks and to the plugin's hooks.json and lock are refused."""
import os, sys, tempfile
H = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
sys.path.insert(0, H)
import guard_blocks as g
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace("\\", "/")
L = g.Lock({}, plugin_root=os.path.dirname(H), project=R)
d = tempfile.mkdtemp()
def script(name, body):
    p = os.path.join(d, name); open(p, "w").write(body); return p
reader = script("reader.py", "import json\ncfg = json.load(open('.claude/settings.json'))\nopen('out/report.txt','w').write(str(cfg))\n")
writer = script("writer.py", "from pathlib import Path\np = Path('.claude/settings.json')\np.write_text('{}')\n")
switcher = script("sw.py", "import subprocess\nsubprocess.run(['python','scripts/roadmap_setup.py','switch-off'])\n")
SET = '"' + R + '/.claude/settings.json"'
cases = [
  # the release's own steps: allowed
  ('git add hooks/guard_blocks.py hooks/test_roadmap_blocks.py engine/System/live/rules/rulebook.py tests/guards_acceptance.py && git commit -q -m "Roadmap lock: roadmap_setup.py switch-off examples; .claude/settings.json"', False),
  ("git merge guardrails-review", False),
  ("python hooks/test_roadmap_blocks.py", False),
  ("python -B tests/guards_acceptance.py", False),
  ("python - <<'EOF'\nfrom pathlib import Path\np = Path('skills/x/SKILL.md')\np.write_text(p.read_text().replace('a', 'never edit .claude/settings.json'))\nEOF", False),
  ("python " + reader, False),
  ("cp .claude/settings.json backup/settings-copy.json", False),
  ("Set-Content docs/manual.md \"The lock guards .claude/settings.json.\"", False),
  # 11/25/26: a commit whose message is a PowerShell here-string with ' and <id> in it crashed the lock; it is text
  ('cd "C:\\Users\\pat\\Documents\\Assistant\\Development\\worktrees\\rebuild-1"; git commit -q -m @\'\nJudgment rebuild phase 1: a pick on every card, prediction against what he did, off-page actions, the pick\'s cost\n\n- picks.py: each open card\'s pick (what I predict he will do), written by the card writer (prompts/items.md "pick") or the program\'s; shown on the page as the first button, "My pick"; one press does it, marked as the pick. New press "leave" for "Leave it as it is".\n- Rule book rows carry the pick, what he did and whether they matched, for every press and for typed words (neutral); a card with no messages gets one row (card:<id>). What he did instead is kept by sender or kind (personal/pick_habits.json) and offered on the next card like it ("Last time: ..."); the writer sees it (owner_last_time).\n- offpage.py: each pass records his sent messages on every gathered channel (matched to a card by conversation or person; page sends told apart by send.py\'s log) and calendar answers and moves (calendar_events.my_response) as rule book rows.\n- The pass log line gives the pick\'s cost: picks written, their output tokens (estimate) against the writer\'s output tokens (now kept from the Claude command\'s usage), 0 extra AI runs.\n- Tests: rebuild_picks_acceptance (new); card_plan_page gains pick checks; rsi_signals\' Settings line now names the pick.\n\'@; git log --oneline -1; cd "..\\..\\Plugin repo"; git log --oneline -1 main', False),
  ("echo a >", False),
  # the roadmap is not critical: its files and switching it off or on go through
  ("python " + switcher, False),
  ("python scripts/roadmap_setup.py switch-off", False),
  ("python -c \"import os; os.remove('.claude/roadmap/ids.json')\"", False),
  ("bash -c 'rm -rf .claude/roadmap'", False),
  ("git rm .claude/roadmap/log.json", False),
  # real changes to the guardrails themselves: refused
  ("python " + writer, True),
  ('rm -rf "' + os.path.dirname(H).replace("\\", "/") + '/hooks"', True),
  ("Set-Content .claude/hooks/guard_folders.py 'x'", True),
  ("cp x.json .claude/settings.json", True),
  ("Copy-Item x.json -Destination " + SET, True),
  ('rm "' + os.path.dirname(H).replace("\\", "/") + '/hooks/guard_blocks.py"', True),
  ("python - <<'EOF'\nimport os\nt = os.path.join('.claude', 'settings.json')\nopen(t, 'w').write('{}')\nEOF", True),
  ("echo {} > .claude/settings.json", True),
  ("python - <<'EOF'\nopen('.claude/settings.json','w').write('{}')\nEOF", True),
  ("git checkout main -- .claude/settings.json", True),
  ("@'\nSet-Content .claude/settings.json '{}'\n'@ | iex", True),
]
bad = 0
for c, w in cases:
    got = L.check_command(c, R) is not None
    bad += got != w
    print("ok " if got == w else "BAD", "refuse" if w else "allow", repr(c[:80]))
print("failures:", bad)
