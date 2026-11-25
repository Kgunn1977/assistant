r"""Acceptance (quick): the mail's slow work as its own step, with stand-in mailboxes (no real mailbox is called). Each mailbox's
seconds are written as it finishes, so a step stopped at its limit still says what each took; each pass starts with the next
mailbox, so a slow one never keeps the others waiting; a step stopped at its limit is a progress line, not a problem.

    python tests\mail_sync_step_acceptance.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
results = []

INSIDE = r'''
import sys, time, types
sys.argv = ["run.py", "--kind", "email-sync", "--run-id", sys.argv[1], "--sync-seconds", "2"]
sys.path.insert(0, LIVE); sys.path.insert(0, LIVE + "/core")
import connections
from connections import run
MB = [{"id": "a", "type": "fast", "address": "pat@one.example"}, {"id": "b", "type": "slow", "address": "pat@two.example"},
      {"id": "c", "type": "fast", "address": "pat@three.example"}]
fast = types.SimpleNamespace(sync=lambda c, ctx, end: "3 changes read")
slow = types.SimpleNamespace(sync=lambda c, ctx, end: (time.sleep(float(SLOW)), "1 change read")[1])
connections.listed = lambda kind=None, everything=False: MB
connections.module = lambda t: {"fast": fast, "slow": slow}[t]
import mail
mail.rethread = lambda: 0
mail.wake = lambda: 0
sys.exit(run.main())
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    home = tempfile.mkdtemp(prefix="syncstep-")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, r'{LIVE}'); sys.path.insert(0, r'{LIVE}\\core'); import db; db.init_schema()"],
                   env=env, check=True, cwd=LIVE)

    def step(run_id, slow, timeout=None):
        code = INSIDE.replace("LIVE", repr(LIVE)).replace("SLOW", repr(str(slow)))
        try:
            subprocess.run([sys.executable, "-c", code, run_id], env=env, cwd=LIVE, timeout=timeout, capture_output=True, text=True)
            stopped = False
        except subprocess.TimeoutExpired:
            stopped = True
        got = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, r'{LIVE}'); sys.path.insert(0, r'{LIVE}\\core'); import db; "
                              f"print(db.query(\"SELECT status, detail FROM source_status WHERE run_id='{run_id}' AND source='email-sync'\"))"],
                             env=env, cwd=LIVE, capture_output=True, text=True).stdout.strip()
        return stopped, got

    stopped, got = step("p1", 0)
    check("a full step: every mailbox with its seconds", ("pat@one.example: 3 changes read (" in got and "pat@two.example: 1 change read (" in got
                                                          and "pat@three.example: 3 changes read (" in got and "'ok'" in got), True)
    stopped, got = step("p2", 60, timeout=12)        # the slow mailbox outlasts the step's limit
    check("a step stopped at its limit has still written the mailboxes it finished and the one it was reading",
          (stopped, "now reading pat@two.example" in got, "'ok'" in got), (True, True, True))
    stopped, got = step("p3", 0)
    first = got.split("'ok', '", 1)[-1].split(":", 1)[0]
    check("the next pass starts after the mailbox that was stopped", first, "pat@three.example")
    # the pass: a stopped step is a progress line, not a problem
    src = open(os.path.join(LIVE, "gather.py"), encoding="utf-8").read()
    check("the pass treats a stopped step as progress (it goes on next pass) and shows the line in its summary",
          ('"limit" in tail' in src and "goes on the next time I check" in src and '| {name}:' in src), True)
    shutil.rmtree(home, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
