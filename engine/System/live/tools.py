r"""The tools in Settings, Tools: each a walk-through that starts in Talk to your assistant at the top, the way Update starts from its card.

    TOOLS                       the list: id, name, plain words, the first message it sends, and the walk-through it follows. A new
                                tool is one more entry; one whose walk-through text is not on this computer yet is not listed.
    listed()                    what the page shows: [{id, name, words}]
    start(tool, at)             the Start button: marks the walk-through and sends its first message to Talk to your assistant (chat.handle)
    walk()                      the walk-through text Talk to your assistant follows while a tool started here is under way, or ""
    run_setup(args)             a setup step Talk to your assistant asks for (ACTION {"type": "setup", "run": [...]}): run on this computer and its
                                one-line answer handed back; a step that can only be done at the computer is not run, and its
                                plain words say where to finish it

Left out on purpose: uninstall (typed at the computer only), adopt (once), and the roadmap tools (they run in a project's own session).
"""
import datetime as dt
import json
import os
import subprocess
import sys

import common

HERE = os.path.dirname(os.path.abspath(__file__))
TEXTS = os.path.join(HERE, "setup", "setup_texts")
WALK = os.path.join(common.paths.STATE, "tool_walk.json")
WALK_HOURS = 24
AT_COMPUTER = "At your computer, open the Claude app, go to the Code tab and type"

TOOLS = (
    {"id": "update", "explain": "Updates me to the newest version. It shows what is new first, and nothing changes until you say go. Start opens the walk-through in Talk to your assistant at the top of the page.",
     "name": "Update", "texts": ("update.md",),
     "words": "Updates me to the newest version. It shows what is new first, and nothing changes until you say go.",
     "first": "(I pressed Start on Update in Settings, Tools.) Please walk me through updating my assistant to the newest version: what it changes, how it touches any change I made myself, and what I need to do. Ask before anything changes."},
    {"id": "change", "explain": "Changes your accounts, what can be sent, where your page opens, or how I work or look. Start opens Talk to your assistant, which asks you which one, a question at a time.",
     "name": "Change", "texts": ("change.md", "change-program.md"),
     "words": "Changes your accounts, what can be sent, where your page opens, or how I work or look.",
     "first": "(I pressed Start on Change in Settings, Tools.) I want to change something about my assistant: my accounts, what it may send, where my page opens, or how it works or looks. Ask me which, one question at a time."},
    {"id": "undo", "explain": "Undoes a change to how I work, and anything that depends on it, after showing you what goes back. Start opens the walk-through in Talk to your assistant.",
     "name": "Undo a change", "texts": ("change-program.md",),
     "words": "Undoes a change to how I work, and anything that depends on it, after showing you what goes back.",
     "first": "(I pressed Start on Undo a change in Settings, Tools.) Please show me the changes I made that can be undone, and walk me through undoing one. Show me what goes back before anything is undone."},
    {"id": "introduce", "explain": "Connects one of your projects so what happens there reaches you as cards. You can also change or remove one. Start opens the walk-through in Talk to your assistant.",
     "name": "Introduce a project", "texts": ("introduce.md",),
     "words": "Connects one of your projects so what happens there reaches you as cards. You can also change or remove one.",
     "first": "(I pressed Start on Introduce a project in Settings, Tools.) Please walk me through introducing one of my projects to my assistant, or changing or removing one I introduced. One question at a time."},
    {"id": "setup", "explain": "Redoes part of your setup, such as accounts or key people, without starting over. Start opens Talk to your assistant, which asks which part.",
     "name": "Set up again", "texts": ("interview.md",),
     "words": "Redoes part of your setup, such as accounts or key people, without starting over.",
     "first": "(I pressed Start on Set up again in Settings, Tools.) I want to go over part of my setup again, such as my accounts or the people who matter, without starting over. Ask me which part."},
    {"id": "voice", "explain": "Learns your writing style from the emails, texts and other messages you sent, so drafts sound like you, and lets you review and correct it. Start opens the walk-through in Talk to your assistant.",
     "name": "Writing style builder", "texts": ("voice.md",),
     "words": "Learns your writing style from the emails, texts and other messages you sent, so drafts sound like you. You can review and correct it.",
     "first": "(I pressed Start on Writing style builder in Settings, Tools.) Please walk me through teaching my assistant how I write."},
)

# setup steps Talk to your assistant may run on this computer for a tool (each the same helper the walk-throughs name)
RUNS = {"progress", "show", "answer", "skip", "changes", "undo", "update-sort", "update-show", "update-decide", "update-choices",
        "account-kinds", "account-steps", "connect-ready", "accounts", "check-accounts", "remove-account", "calendar-choices",
        "projects", "project-add", "project-change", "project-roadmap", "project-intro", "project-line", "project-remove",
        "readback-estimate", "reach-status", "reach-off"}
LONG = {"readback"}            # a long job: started on this computer in the background; its result comes to the page
# the steps that can only be finished at the computer, and the plain words that say where
AT_COMPUTER_ONLY = {
    "connect": "Signing in to an account opens a sign-in window on your computer, so that step is finished there. "
               f"{AT_COMPUTER} /assistant:change accounts. Everything else here can go on in Talk to your assistant.",
    "reach-on": "Reaching your page from anywhere puts Tailscale on your computer and signs it in, which is done at the computer. "
                "Get it from https://tailscale.com/download/windows, then " + AT_COMPUTER[0].lower() + AT_COMPUTER[1:] + " /assistant:change page.",
    "reach-check": "Checking the way in from anywhere is done at your computer: " + AT_COMPUTER[0].lower() + AT_COMPUTER[1:] + " /assistant:change page.",
    "update-apply": "Putting the update in place stops and restarts this page, so it is done at your computer. "
                    f"{AT_COMPUTER} /assistant:update. What you decided here is kept.",
    "update-after": "Finishing the update is done at your computer, right after it is put in place: " + AT_COMPUTER[0].lower() + AT_COMPUTER[1:] + " /assistant:update.",
    "turn-on": "Switching me on can't be done from this page, which only answers while I'm on. "
               f"{AT_COMPUTER} /assistant:change switch-on.",
    "open-page": "Your page is already open here. To open it on your computer, " + AT_COMPUTER[0].lower() + AT_COMPUTER[1:] + " /assistant:change page.",
}
SETUP_ONLY = ("install-parts", "folder-check", "where", "ready", "finish", "start", "audit", "audit-decide")
PAGE_PRESS = ("change-start", "change-agree", "change-go", "change-edited", "change-check", "change-abandon", "change-drop")


VOICE = ("voice-build", "voice-show", "voice-correct", "voice-level")       # the Writing style builder's steps (voice.py), run here


def _voice_step(what, rest):
    import voice
    if what == "voice-build":
        p = voice.build()
        return json.dumps({"ok": True, "learned_from": p.get("messages"), "greetings": p.get("greetings"), "signoffs": p.get("signoffs"),
                           "phrases": p.get("phrases"), "kinds": p.get("kinds"), "never": p.get("never")})
    if what == "voice-show":
        return json.dumps(dict(voice.for_page(), ok=True))
    if what == "voice-level":
        level = (rest or [""])[0]
        if level not in ("choose", "casual", "everyday", "formal"):
            return "The level is one of choose, casual, everyday or formal. Nothing was changed."
        s = common.settings()
        s["voice"] = dict(s.get("voice") if isinstance(s.get("voice"), dict) else {}, level=level)
        common.write_json(common.SETTINGS, s)
        got = voice.setting()               # read back: what is saved, not what was asked
        return json.dumps({"ok": got == level, "saved": voice.LABEL[got],
                           "say_back": f"Saved, read back: drafts are {voice.LABEL[got].lower()}." if got == level else "It did not save; nothing changed."})
    part = (rest or [""])[0]
    if part not in ("greetings", "signoffs", "phrases", "never"):
        return "The part is one of greetings, signoffs, phrases or never. Nothing was changed."
    try:
        items = json.loads(rest[1]) if len(rest) > 1 else []
        items = [" ".join(str(x).split())[:120] for x in items if str(x).strip()][:12] if isinstance(items, list) else None
    except ValueError:
        items = None
    if items is None:
        return "The list could not be read. Nothing was changed."
    if part == "greetings" and [x.lower() for x in items] in (["none"], ["no greeting"], [voice.NO_GREETING]):
        items = [voice.NO_GREETING]         # he does not open with a greeting
    voice.save_owner({part: items})
    now = voice.profile().get(part) or []   # read back: what is saved, not what was asked
    shown = "no greeting" if now == [voice.NO_GREETING] else (", ".join(now) or "what was learned")
    return json.dumps({"ok": (now == items) if items else True, part: now,
                       "say_back": f"Saved, read back: {part} now {shown}."})


def _have(t):
    return all(os.path.isfile(os.path.join(TEXTS, n)) for n in t["texts"])


def listed():
    """The tools the page lists, in order: each one whose walk-through is on this computer."""
    return [{"id": t["id"], "name": t["name"], "words": t["words"], "explain": t["explain"]} for t in TOOLS if _have(t)]


def _tool(tid):
    return next((t for t in TOOLS if t["id"] == tid and _have(t)), None)


def start(tid, at=None):
    """Start one tool's walk-through in Talk to your assistant: the walk is marked, then its first message goes to Talk to your assistant."""
    t = _tool(tid)
    if t is None:
        return {"ok": False, "error": "That tool is not on this computer.", "items": []}
    now = common.now().isoformat(timespec="seconds")
    common.write_json(WALK, {"tool": t["id"], "started": common.now().isoformat(timespec="microseconds")})      # always the newest walk
    if t["id"] == "update":         # the update walk-through Talk to your assistant already knows, to the newest version found
        import updates
        try:
            version = updates.latest(updates.repo())[0] or "the newest version"
        except Exception:  # noqa: BLE001  the walk-through finds out
            version = "the newest version"
        common.write_json(os.path.join(common.paths.STATE, "update_walk.json"), {"version": version, "card": None, "started": now})
    if t["id"] in ("change", "undo"):       # the change walk-through Talk to your assistant already knows
        common.write_json(os.path.join(common.paths.STATE, "change_walk.json"), {"started": now})
    import chat
    return chat.handle(t["first"], at)


def walk():
    """While a tool started from Settings is under way (started in the last day): the walk-through Talk to your assistant follows. Update,
    Change and Undo use the chat's own update and change walk-throughs; the others are read here."""
    st = common.read_json(WALK, {}) or {}
    try:
        fresh = bool(st) and (common.now() - dt.datetime.fromisoformat(str(st.get("started")))).total_seconds() < WALK_HOURS * 3600
    except ValueError:
        fresh = False
    t = _tool(st.get("tool")) if fresh else None
    if t is None or t["id"] in ("update", "change", "undo"):
        return ""
    for other in ("update_walk.json", "change_walk.json"):     # an update or change started after it is the one under way
        o = common.read_json(os.path.join(common.paths.STATE, other), {}) or {}
        if str(o.get("started") or "") > str(st.get("started") or ""):
            return ""
    text = ""
    for n in t["texts"]:
        try:
            with open(os.path.join(TEXTS, n), encoding="utf-8") as f:
                text += ("\n\n" if text else "") + f.read().strip()
        except OSError:
            pass
    head = (f"HE STARTED THE TOOL \"{t['name']}\" FROM SETTINGS: follow this walk-through, one question at a time, here in "
            "Talk to your assistant. Run each setup step with an ACTION line {\"type\": \"setup\", \"run\": [\"<step>\", \"<detail>\", ...]}; its answer "
            "comes back to you at once. A step only the computer can do comes back as plain words saying where to finish it: pass them on.")
    if t["id"] == "setup":
        head += " He wants to go over part of the setup again, not start over: ask which part, and touch only that part."
    return head + "\n" + text


def run_setup(args):
    """One setup step for Talk to your assistant. Returns the plain one-line answer handed back to Talk to your assistant."""
    args = [str(a) for a in (args or []) if a is not None]
    if not args:
        return "No setup step was named."
    what = args[0]
    if what in AT_COMPUTER_ONLY:
        return AT_COMPUTER_ONLY[what]
    if what in SETUP_ONLY:
        return f"That step belongs to the first setup and is not run from the page. {AT_COMPUTER} /assistant:setup."
    if what in PAGE_PRESS:
        return "A change is made only by his Approve on its card in Cards. Nothing was changed."
    if what in VOICE:
        return _voice_step(what, args[1:])
    root = os.path.dirname(os.path.dirname(HERE))
    cmd = [sys.executable, os.path.join(HERE, "setup", "setup_home.py"), "--root", root, "--home", common.HOME] + args
    env = dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME)
    if what in LONG:
        import answers
        ok = answers.start_hidden(cmd)
        return ("Started on your computer; it takes a while, and what it finds comes to your page as cards." if ok
                else "It could not be started on your computer just now. Nothing was changed.")
    if what not in RUNS:
        return f"\"{what}\" is not a setup step Talk to your assistant can run. Nothing was changed."
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return "That step took too long on your computer and was stopped."
    lines = [l for l in (r.stdout or "").strip().splitlines() if l.strip()]
    return lines[-1][:1500] if lines else (f"The step gave no answer ({(r.stderr or '').strip()[-200:]})" if r.returncode else "Done.")


def is_setup(action):
    """True for a setup ACTION: {"type": "setup", "run": [...]}, or the shorter {"setup": [...]} the walk-throughs write."""
    return isinstance(action, dict) and (action.get("type") == "setup" or isinstance(action.get("setup"), list))


def setup_args(action):
    run = action.get("run") if action.get("type") == "setup" else action.get("setup")
    if isinstance(run, str):
        run = [run]
    return [x if isinstance(x, str) else json.dumps(x) for x in (run or [])]
