r"""The weekly look for a newer version of the assistant (the owner's decision of 11/17/26).

Every Sunday after midnight, the first background pass compares the version laid down on this computer with the version in
the plugin's repository. When the repository's is newer, one card asks whether to update, listing the changes in plain words.
No Claude run and no job of its own: it is one step of the pass. With no network, or no way to read the repository, it says
nothing and tries again at the next pass that Sunday (and the Sundays after).

    check(pass_id)    the pass's step: returns "" or one plain line for the pass log
    start(item)       the owner pressed Update: the update walk-through starts in Talk to your assistant

Where things are read:
- The version laid down here: <home>\personal\install.json "version" (written by lay-down and update), else
  <root>\Shipped\shipped.json.
- The repository: <home>\personal\install.json "repo" ("owner/name") when lay-down wrote it, else the marketplace Claude
  installed the plugin from (~\.claude\plugins\installed_plugins.json and known_marketplaces.json).
- Its version and notes: the repository's .claude-plugin/plugin.json "version", and CHANGES.json {"<version>": ["plain
  sentence", ...]} beside it. Read through the GitHub command line (gh) when it is signed in, so a private repository the
  person can read works; else the public raw address.
"""
import datetime as dt
import json
import os
import re
import subprocess
import urllib.request

import common

STATE = os.path.join(common.paths.STATE, "update_check.json")
INSTALL = os.path.join(common.PERSONAL, "install.json")
KEY = "live:update-"
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _vt(v):
    return tuple(int(x) if x.isdigit() else 0 for x in re.findall(r"\d+", str(v or "")))


def installed():
    v = (common.read_json(INSTALL, {}) or {}).get("version")
    if not v:
        root = os.path.dirname(common.HOME)
        v = (common.read_json(os.path.join(root, "Shipped", "shipped.json"), {}) or {}).get("version")
    return str(v or "")


def repo():
    r = str((common.read_json(INSTALL, {}) or {}).get("repo") or "")
    if REPO.match(r):
        return r
    base = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"), "plugins")
    plugins = (common.read_json(os.path.join(base, "installed_plugins.json"), {}) or {}).get("plugins") or {}
    known = common.read_json(os.path.join(base, "known_marketplaces.json"), {}) or {}
    for name in plugins:
        if str(name).split("@")[0] == "assistant" and "@" in str(name):
            src = (known.get(str(name).split("@", 1)[1]) or {}).get("source") or {}
            r = str(src.get("repo") or "")
            if REPO.match(r):
                return r
    return ""


def _read(rp, path):
    """One file of the repository, or None when it cannot be read now (no network, not signed in, no such file)."""
    try:
        r = subprocess.run(["gh", "api", f"repos/{rp}/contents/{path}", "-H", "Accept: application/vnd.github.raw"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=NO_WINDOW)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{rp}/HEAD/{path}", timeout=20) as f:
            return f.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001  no network or a private repository without gh: try again next run
        return None


def latest(rp):
    """(version, [plain sentences]) from the repository, or (None, []) when it cannot be read now."""
    raw = _read(rp, ".claude-plugin/plugin.json")
    try:
        v = str(json.loads(raw).get("version") or "") if raw else ""
    except ValueError:
        v = ""
    if not v:
        return None, []
    notes = []
    raw = _read(rp, "CHANGES.json")
    try:
        got = json.loads(raw) if raw else {}
        mine = _vt(installed())
        for ver, lines in sorted(got.items(), key=lambda kv: _vt(kv[0])):
            if mine < _vt(ver) <= _vt(v):
                notes += [" ".join(str(x).split())[:300] for x in lines or [] if str(x).strip()]
    except (ValueError, AttributeError):
        notes = []
    return v, notes[:20]


def this_sunday(now=None):
    d = (now or common.now()).date()
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)       # Monday 0 .. Sunday 6: the Sunday this week began


def due(now=None):
    """True from Sunday midnight until this week's look has been made."""
    st = common.read_json(STATE, {}) or {}
    return st.get("looked") != this_sunday(now).isoformat()


def check(pass_id, now=None):
    if not due(now):
        return ""
    mine, rp = installed(), repo()
    if not mine or not rp:
        return ""                     # not laid down by the plugin (or no repository known): nothing to compare
    v, notes = latest(rp)
    if v is None:
        return ""                     # no network or no access: say nothing, try again at the next pass
    st = common.read_json(STATE, {}) or {}
    st.update(looked=this_sunday(now).isoformat(), at=common.now().isoformat(timespec="seconds"), latest=v, installed=mine)
    common.write_json(STATE, st)
    if _vt(v) <= _vt(mine):
        return ""
    import db
    import items
    have = db.query("SELECT id, state FROM live_items WHERE source_key = ?", (KEY + v,))
    words = {"from": mine, "version": v, "changes": notes or ["The notes for this version could not be read; Update shows them before anything changes."]}
    if have and have[0][1] != "done":
        return ""
    if have:            # Not now was pressed last week and the version still waits: the card comes back
        db.execute("UPDATE live_items SET state='question', status=NULL, answer=NULL, answered_at=NULL, done_at=NULL, updated_at=?, "
                   "state_changed_at=?, last_pass=? WHERE id=?", (common.now(), common.now(), pass_id, have[0][0]))
        return f"version {v} still waits (you have {mine}): the update card is back"
    # a card for this version (again, if Not now was pressed last week and it is still waiting)
    items.upsert(KEY + v, pass_id, kind="question", area="System", state="question", status=None,
                 title=f"An update is ready: version {v}",
                 detail="It brings:\n" + "\n".join(f"- {n}" for n in words["changes"]) +
                        f"\n\nYou have {mine}. Update walks you through it in Talk to your assistant on this page, shows how it would touch any change you made yourself, and asks before anything changes. Not now puts this away until next Sunday.",
                 asks=["Update now?"], why="I look for a newer version each week, and found one.", extra={"update": words})
    return f"version {v} is ready (you have {mine}): update card made"


def not_now(item):
    """Not now: left until next Sunday's look, when it comes back if still waiting."""
    return "Not now. If this version is still waiting next Sunday, it comes back."


def start(item, version):
    """Update pressed: the update walk-through starts in Talk to your assistant, in today's conversation session."""
    import chat
    import threading
    common.write_json(os.path.join(common.paths.STATE, "update_walk.json"),
                      {"version": version, "card": item.get("id"), "started": common.now().isoformat(timespec="seconds")})
    words = (f"(I pressed Update on the update card.) Please walk me through updating to version {version}: "
             "what it changes, how it touches any change I made myself, and what I need to do. Ask before anything changes.")
    threading.Thread(target=chat.handle, args=(words,), daemon=True).start()
    return f"The update to {version} is starting in Talk to your assistant at the top of your page."
