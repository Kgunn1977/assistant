r"""A change to how the assistant works, made from the page: the hidden job the owner's "Yes, make this change" starts.

The talking (hearing it, making it clear one question at a time, saying it back) happens in Talk to your assistant, which can
only read; Talk to your assistant records the change and its agreed words through its ACTION lines (chat.py, change_start and
change_agree). The owner's press on the page is the go. Then this job, started hidden by the listener, does what
change-program.md sections 5 and 6 say, through the change helper (setup\setup_home.py), so every step is the one the
computer's /assistant:change takes:

    the go (the undo copy is saved first) -> one Claude run that edits only this change's own mod files
    (Live\mods\<name>, never the program's files; its tools allow nothing else and the guardrails' E3 exception holds it to
    them) -> change-edited -> change-check (rebuild the page, restart the listener, run a check, look at the page).
The first step that fails puts everything back by itself. The result, with an Undo button, comes back in the same chat.

    python change_job.py <change id>
"""
import json
import os
import subprocess
import sys

import common

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "sonnet"
EDIT_SECONDS = 900
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LOG = os.path.join(common.LOGS, "changes.log")
PROMPT = """You make one change to {OWNER}'s assistant, already talked through with {OWNER} and given a clear go.

The change, exactly as agreed:
{AGREED}

Make it by writing only these files (the change's own mod, in {OWNER}'s own folder; the program's own files are never changed):
{FILES}

First read the top of {MODS} (how a mod is made and the places the program asks it), and {MOD_JSON_HINT}. Read any program
file you need, but write only the files above. Nothing about {OWNER} beyond what the change needs. Plain code, no secrets.
If checks.json is among the files, write it as well: {{"checks": [{{"try": "what to try, in plain words", "expect": "what should
happen"}}]}}, one check for each thing the change makes or changes that the owner can try on their own (a real use, with when
and where it should show), each a plain sentence. Keep any existing check's "id" and "state" exactly as they are and add new
checks without them. It is not code; do not run anything.
When the files are written, reply with one line of JSON and nothing else: {{"ok": true}}
If the change cannot be made with only those files, or would need to differ from what was agreed, write nothing more and
reply: {{"ok": false, "why": "what is missing, in one plain sentence"}}"""


def _record(cid):
    return common.read_json(os.path.join(common.HOME, "changes", f"{cid}.json"), {}) or {}


def mod_folder(c):
    """The one mod folder every file of the change is in, or None."""
    tops = {"/".join(p.split("/")[:3]) for p in c.get("paths") or []}
    if len(tops) != 1:
        return None
    top = tops.pop()
    return os.path.join(os.path.dirname(common.HOME), *top.split("/")) if top.startswith("Live/mods/") and top.count("/") == 2 else None


def edit(c, folder):
    """One Claude run that may write only the change's own files. (ok, why)."""
    import ai_steps
    files = [os.path.join(os.path.dirname(common.HOME), *p.split("/")) for p in c["paths"]]
    os.makedirs(folder, exist_ok=True)
    prompt = PROMPT.replace("{OWNER}", common.owner()).replace("{AGREED}", str(c.get("agreed") or "")) \
        .replace("{FILES}", "\n".join("- " + f for f in files)).replace("{MODS}", os.path.join(HERE, "mods.py")) \
        .replace("{MOD_JSON_HINT}", "make mod.json name the mod exactly as its folder is named")
    rule = folder.replace("\\", "/").rstrip("/")
    allow = [f"Read({os.path.dirname(common.HOME).replace(chr(92), '/')}/**)", "Glob", "Grep", f"Edit({rule}/**)", f"Write({rule}/**)"]
    cmd = [ai_steps.claude_exe(), "-p", "--model", MODEL, "--output-format", "json", "--tools", "Read,Write,Edit,Glob,Grep",
           "--allowedTools", ",".join(allow), "--permission-mode", "dontAsk", "--strict-mcp-config", "--setting-sources", "",
           "--append-system-prompt", ai_steps.GUARD] + ai_steps.run_settings("change")
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=EDIT_SECONDS, cwd=folder, creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired:
        return False, f"the edit did not finish within {EDIT_SECONDS // 60} minutes"
    try:
        said = json.loads(r.stdout).get("result") or ""
        got = json.loads(said[said.index("{"):said.rindex("}") + 1])
    except (ValueError, AttributeError):
        common.log_line(LOG, f"{c['id']}: the edit's answer could not be read: out {r.stdout.strip()[-600:]!r} err {r.stderr.strip()[-300:]!r}")
        return False, "the edit gave no readable answer"
    return bool(got.get("ok")), str(got.get("why") or "")[:300]


def tell(c, text):
    """The result in Talk to your assistant, with the change's id so the page offers its Undo there."""
    import chat
    chat._add({"who": "assistant", "text": text, "source": "", "at": common.now().isoformat(timespec="seconds"), "change": c["id"]})
    try:            # the page sees it now, not at the next pass
        page = os.path.join(os.path.dirname(HERE), "live_page", "publish.py")
        subprocess.run([sys.executable, page], capture_output=True, timeout=180, creationflags=NO_WINDOW,
                       env=dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME))
    except Exception:  # noqa: BLE001  the next pass shows it
        pass


RUNNER = None           # the steps of the check (setup_changes.default_runner); a test hands its own


def _book():
    setup = os.path.join(HERE, "setup")
    if setup not in sys.path:
        sys.path.insert(0, setup)
    import setup_changes as sc
    return sc, sc.Book(os.path.dirname(common.HOME), common.HOME)


def run(cid):
    sc, book = _book()
    c = _record(cid)
    common.log_line(LOG, f"{cid}: started from the page")
    folder = mod_folder(c)
    if c.get("state") != "go" or not folder:
        why = "it has no go" if c.get("state") != "go" else "its files are not all in one mod folder"
        tell(c or {"id": cid}, f"The change was not made: {why}. Nothing was changed.")
        return 1
    runner = RUNNER
    if runner is None:
        import setup_steps
        runner = sc.default_runner(setup_steps, "")
    ok, why = edit(c, folder)
    try:            # the same steps the change helper takes (setup_home.py change-edited, change-check)
        got = book.edited(cid, ok, why, runner)
        if got.get("state") == "doing":
            got = book.check(cid, runner)
    except sc.Refused as e:
        got = {"failed_step": "the edit", "why": str(e)}
    c = _record(cid)
    common.log_line(LOG, f"{cid}: {c.get('state')} {json.dumps(got)[:300]}")
    try:            # the mod's check cards go up on the page; a fix puts a new card up for its check (mod_checks.py)
        import mod_checks
        mod_checks.after_change(c, c.get("state") == "done")
    except Exception as e:  # noqa: BLE001
        common.log_line(LOG, f"{cid}: check cards: {type(e).__name__}: {e}")
    if c.get("state") == "done":
        tell(c, f"The change is made: {str(c.get('asked') or '').rstrip('.')}. It was checked on your page. You can undo it any time.")
        return 0
    tell(c, f"The change was not made: {got.get('failed_step') or 'the edit'} failed ({got.get('why') or why or 'no reason given'}). "
            "Everything was put back by itself; nothing of it is left.")
    return 1


if __name__ == "__main__":
    sys.exit(run(sys.argv[1]) if len(sys.argv) > 1 else 2)
