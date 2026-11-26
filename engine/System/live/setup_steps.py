r"""First-time setup, step by step. The setup interview (the plugin's /assistant:setup and /assistant:change) calls these; each can be run again later
to change an answer, add an account or sign one in again.

Everything written here goes into the owner's home (their personal folder, their database, the
locked key store). Nothing is written into the general part, and a secret is only ever handed
straight to the locked store.
"""
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys

import common
import connections

HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PARTS = {"duckdb": "duckdb", "fitz": "pymupdf", "openpyxl": "openpyxl", "PIL": "pillow", "pillow_heif": "pillow-heif"}
LIVE_PAGE = os.path.join(common.SYSTEM, "live_page")
STARTER = common.paths.STARTER


# --- step 0: what this computer needs ----------------------------------------------------
def parts_missing():
    """The add-on parts of Python the assistant needs that are not on this computer yet."""
    return [pip for mod, pip in PARTS.items() if importlib.util.find_spec(mod) is None]


def install_parts(say=print):
    missing = parts_missing()
    if not missing:
        return True
    say("Installing: " + ", ".join(missing) + " (a minute or two)")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", *missing], capture_output=True, text=True,
                       creationflags=HIDDEN)
    importlib.invalidate_caches()
    left = parts_missing()
    say("Installed." if not left else "Could not install: " + ", ".join(left) + ". " + (r.stderr or "").strip()[-300:])
    return not left


def claude_ready():
    """(True, where) when the Claude command the assistant thinks with is on this computer."""
    try:
        import ai_steps
        return True, ai_steps.claude_exe()
    except RuntimeError as e:
        return False, str(e)


# --- step 1: the home ---------------------------------------------------------------------
def make_home():
    """Create the owner's home if it is not there: folders, starter rules, an empty database. Safe to repeat."""
    p = common.paths
    new = not os.path.exists(common.PERSONAL_JSON) and not os.path.exists(p.DB)     # a home being made now, not one brought forward
    for d in (p.PERSONAL, p.TAUGHT, p.STATE, p.ATTACHMENTS, p.BRIEFINGS, p.RULES, p.RULES_DRAFT, p.DATA,
              os.path.dirname(p.DB), common.LOGS, common.ANSWERS_APPLIED):
        os.makedirs(d, exist_ok=True)
    for sub, dest in (("Rules", p.RULES), ("Data", p.DATA)):
        src = os.path.join(STARTER, sub)
        for name in os.listdir(src) if os.path.isdir(src) else []:
            if not os.path.exists(os.path.join(dest, name)):
                shutil.copy2(os.path.join(src, name), os.path.join(dest, name))
    if not os.path.exists(common.PERSONAL_JSON):
        common.write_json(common.PERSONAL_JSON, dict(common.STARTER))
    s = common.settings()
    if new:         # a new user starts with nothing hidden (filters.NEW_HOME); a home made before keeps its settings
        import filters
        f = s.get("filter") if isinstance(s.get("filter"), dict) else {}
        s["filter"] = dict(filters.NEW_HOME, **f)
        common.write_json(common.SETTINGS, s)
    import db
    db.init_schema()
    import items
    items.ensure()
    import answers
    db.execute(answers.DDL)
    desktop_note()
    return common.HOME


DESKTOP_MARK = "# This folder is your assistant (written by the assistant plugin"


def desktop_note():
    """The assistant's folder gets a CLAUDE.md, so a Claude session opened there reads the same instructions, the owner's
    saved rules and the shared conversation as the page's chat. Rewritten while it is still the plugin's own (its first
    line says so); one the owner wrote is left alone."""
    path = os.path.join(common.paths.ROOT, "CLAUDE.md")
    try:
        with open(os.path.join(common.PROMPTS, "desktop.md"), encoding="utf-8") as f:
            text = f.read()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                now = f.read()
            if not now.startswith(DESKTOP_MARK) or now == text:
                return
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(path + ".tmp", path)
    except OSError as e:
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"desktop note: {type(e).__name__}: {e}")


def _me():
    return common.read_json(common.PERSONAL_JSON, None) or dict(common.STARTER)


def _save_me(me):
    common.write_json(common.PERSONAL_JSON, me)


# --- step 2: who the owner is ---------------------------------------------------------------
def you(first_name, full_name, about, areas=()):
    """The owner's name, a sentence or two about them, and the areas of life their items sort into."""
    first_name = first_name.strip()
    if not first_name:
        raise ValueError("A first name is needed.")
    me = _me()
    me["owner"] = first_name
    me["full_name"] = full_name.strip() or first_name
    me["about"] = about.strip()
    me["page_title"] = f"{first_name}'s desk"
    named = [a.strip() for a in areas if a and a.strip()]
    kept = list(dict.fromkeys(named + ["Personal", "System"]))
    me["areas"] = kept
    me["key_prefixes"] = [re.sub(r"[^a-z0-9]", "", a.lower()) + "::" for a in kept]
    words = {first_name, *me["full_name"].split()}
    me["private_words"] = sorted(set(me.get("private_words") or []) | {w for w in words if len(w) > 2})
    _save_me(me)
    return me


def page_heading(title, subtitle=""):
    """The page's heading and the line under it."""
    me = _me()
    me["page_title"] = str(title or "").strip() or f"{me.get('owner') or 'Your'}'s desk"
    me["page_subtitle"] = str(subtitle or "").strip()
    _save_me(me)
    return me


def own_mail_domains(domains):
    """Mail domains that are the owner's own; mail from them is never junk and never ignored."""
    me = _me()
    me["own_domains"] = list(dict.fromkeys(str(d).strip().lower().lstrip("@") for d in domains if str(d).strip()))
    _save_me(me)
    return me["own_domains"]


def ignore_senders(entries):
    """Addresses or domains whose mail makes no card and no notification. An entry inside one of the owner's own
    domains is left out here as well as at judging."""
    own = common.paths.own_domains()
    kept = []
    for e in entries:
        e = str(e).strip().lower().lstrip("@")
        d = e.rsplit("@", 1)[-1]
        if e and e not in kept and not any(d == m or d.endswith("." + m) for m in own):
            kept.append(e)
    me = _me()
    me["ignore_senders"] = kept
    _save_me(me)
    return kept


# --- step 3: connections -----------------------------------------------------------------------
def connection_types():
    """[(type, plain name, kind, setup steps)] for every kind of connection there is."""
    return [(k, m.NAME, m.KIND, m.SETUP) for k, m in connections.types().items()]


def registration_asks(type_name):
    """What must be answered once for this provider before any account can sign in; [] when it is on file."""
    app = getattr(connections.module(type_name), "APP", None)
    if not app or connections.app_ready(app):
        return []
    return connections.app_asks(app)


def save_registration(type_name, answers):
    """Keep the one-time registration answers: plain ones in the owner's list, secret ones locked."""
    app = connections.module(type_name).APP
    plain = connections.app(app)
    for a in connections.app_asks(app):
        value = str(answers.get(a["key"]) or "").strip()
        if not value:
            raise ValueError(f"\"{a['label']}\" is empty.")
        if a.get("secret"):
            connections.put_secret("app_" + app, a["key"].replace("client_", ""), value)
        else:
            plain[a["key"]] = value
    connections.save_app(app, plain)


def connection_asks(type_name):
    return list(getattr(connections.module(type_name), "ASKS", []))


def add_connection(type_name, answers=None, say=print, conn_id=None):
    """Connect one account (or sign an existing one in again when conn_id is given). The provider's
    own sign-in page opens in the browser where the type needs one. Returns the saved connection."""
    mod = connections.module(type_name)
    conn = dict(connections.get(conn_id) or {}) if conn_id else {}
    conn.update({"id": conn_id or connections.new_id(), "type": type_name, "on": True})
    conn = mod.connect(conn, say, answers or {})
    twin = [c for c in connections.listed(everything=True) if c["id"] != conn["id"] and c["type"] == type_name
            and (c.get("address") or c.get("label")) == (conn.get("address") or conn.get("label"))]
    if twin:                         # the same account connected twice: keep one entry, with the new sign-in
        old_id, new_id = twin[0]["id"], conn["id"]
        import keys
        for name in keys.names():
            if name.startswith(new_id + "_"):
                connections.put_secret(old_id, name[len(new_id) + 1:], keys.get(name))
                keys.forget(name)
        conn = dict(twin[0], **{k: v for k, v in conn.items() if k != "id"})
    connections.save(conn)
    me = _me()
    me["sources"] = list(dict.fromkeys(list(me.get("sources") or []) + [mod.KIND]))
    if getattr(mod, "CAN_SEND", False) and conn.get("send") and conn.get("address"):
        me["send_accounts"] = list(dict.fromkeys(list(me.get("send_accounts") or []) + [conn["address"]]))
    _save_me(me)
    say(f"Connected: {conn.get('label') or conn['id']}")
    return conn


def remove_connection(conn_id):
    conn = connections.get(conn_id)
    connections.remove(conn_id)
    if conn:
        me = _me()
        me["send_accounts"] = [a for a in me.get("send_accounts") or [] if a != conn.get("address")]
        left = {c.get("kind") for c in connections.listed(everything=True)}
        me["sources"] = [s for s in me.get("sources") or [] if s in left]
        _save_me(me)


def connected():
    """[(id, plain name of the type, label)] for what is connected now."""
    types = connections.types()
    return [(c["id"], getattr(types.get(c["type"]), "NAME", c["type"]), c.get("label") or c.get("address") or c["id"])
            for c in connections.listed(everything=True)]


def check_connections():
    """One harmless read on each connection: [(label, True or False, plain line)]."""
    import keys
    out = []
    for c in connections.listed():
        label = c.get("label") or c["id"]
        try:
            out.append((label, True, connections.module(c["type"]).check(c)))
        except Exception as e:  # noqa: BLE001
            out.append((label, False, keys.scrub(f"{type(e).__name__}: {e}")[:300]))
    return out


# --- step 4: which calendar shows -------------------------------------------------------------
def calendar_choices():
    """[(calendar name, ticked now)] across every connected calendar account."""
    shown = set(_me().get("today_calendars") or [])
    out, seen = [], set()
    for c in connections.listed("calendar"):
        fn = getattr(connections.module(c["type"]), "calendars", None)
        for name, own in (fn(c) if fn else []):
            if name not in seen:
                seen.add(name)
                out.append((name, name in shown or (not shown and own)))
    return out


def show_calendars(names):
    me = _me()
    me["today_calendars"] = [n for n in names if n]
    _save_me(me)


# --- step 5: what matters ------------------------------------------------------------------------
def what_matters(lines):
    """The owner's own list of what deserves a notification on their phone, one kind of thing per line."""
    lines = [ln.strip().lstrip("-").strip() for ln in lines if ln.strip().lstrip("-").strip()]
    os.makedirs(common.PERSONAL, exist_ok=True)
    with open(common.IMPORTANT, "w", encoding="utf-8", newline="\n") as f:
        f.write("# What is important to me\n\nOne line per kind of thing that deserves a notification.\n\n"
                + "".join(f"- {ln}\n" for ln in lines))
    return lines


def phone_alerts(on):
    """Turn phone notifications on or off. On makes a private channel name; the owner subscribes to it in the
    free ntfy app on their phone. Returns the channel name ("" when off)."""
    s = common.settings()
    alerts = s.setdefault("alerts", dict(common.DEFAULT_SETTINGS["alerts"]))
    if on and not alerts.get("topic"):
        alerts["topic"] = "desk-" + secrets.token_urlsafe(18)
    if not on:
        alerts["topic"] = ""
    common.write_json(common.SETTINGS, s)
    return alerts["topic"]


# --- what it may do ------------------------------------------------------------------------------
SENDING_SAYS = ("Sending email. With Yes, an email that you write on your page and press Send on goes out from your own "
                "connected mail account. Nothing is ever sent automatically, and nothing you did not write and send "
                "yourself. With No, I can't send anything at all.")


def allowed():
    """{"sending": True/False/None}: None means the owner has not been asked yet."""
    s = common.settings()
    get = lambda k: (s.get(k) or {}).get("on") if isinstance(s.get(k), dict) and "on" in s[k] else None  # noqa: E731
    return {"sending": get("owner_send")}


def allow(sending):
    """Record the owner's own yes or no. Nothing else turns it on."""
    if sending is None:
        raise ValueError("Choose Yes or No.")
    s = common.settings()
    s.setdefault("owner_send", {})["on"] = bool(sending)
    common.write_json(common.SETTINGS, s)
    return allowed()


# --- roadmaps (optional) ----------------------------------------------------------------------------
# The roadmap is part of this plugin: a standalone, general-purpose planning tool with its own settings that also
# connects to the assistant. The link is its written agreement (the plugin's reference\agreement.md): a program that wants a project's
# roadmap lists itself in <project>\Roadmap page\readers.json, and the roadmap's writer then keeps a plain
# summary in <project>\Roadmap page\roadmap.json, which the page's reader (live_page\roadmaps.py) shows.
ROADMAP_SAYS = ("Optional. A roadmap is a private page for one project: it lists every step of that project and where "
                "each one stands, and Claude keeps it up to date while you work on the project in the Claude desktop app. "
                "It is part of this assistant plugin: a planning tool of its own, with its own settings, that also shows here. Apply it here to any project folder, and to as "
                "many as you like, and each of those roadmaps also shows, for reading, in a \"Roadmaps\" part of your page.\n\n"
                "Press Next to skip this. Nothing about roadmaps shows anywhere until you apply one, and you can come "
                "back to this step any time.")
READERS_ABOUT = ("Programs that want this project's roadmap kept as a plain file (Roadmap page/roadmap.json). "
                 "Each adds and removes only its own entry.")


def _page_roadmaps():
    """The page's own reader of roadmaps (System\\live_page\\roadmaps.py)."""
    if LIVE_PAGE not in sys.path:
        sys.path.append(LIVE_PAGE)
    import roadmaps
    return roadmaps


def _reader_name():
    """This copy's own name in a project's list of readers; two copies on one computer never share it."""
    import hashlib
    return "assistant " + hashlib.sha1(os.path.normcase(os.path.abspath(common.HOME)).encode("utf-8")).hexdigest()[:6]


def _list_me(folder, wanted):
    """Add this assistant to, or take it out of, the project's list of readers, as the agreement says: only our
    own entry, the file written whole and renamed. Taking out never creates the file."""
    path = os.path.join(folder, "Roadmap page", "readers.json")
    got = common.read_json(path, None)
    if got is None and not wanted:
        return
    got = got if isinstance(got, dict) else {}
    listed = got.get("readers") if isinstance(got.get("readers"), dict) else {}
    if wanted:
        listed.setdefault(_reader_name(), {"since": common.now().isoformat(timespec="seconds")})
        listed[_reader_name()]["full"] = True       # the whole roadmap too (agreement part 2), so the page can draw it
    else:
        listed.pop(_reader_name(), None)
    common.write_json(path, {"about": got.get("about") or READERS_ABOUT, "readers": listed})


def roadmap_in_claude():
    """True when Claude on this computer has the roadmap: it comes with the assistant plugin (an older copy may still
    have the separate roadmap plugin)."""
    return bool(re.search(r"(?m)(^|\s)(assistant|roadmap)@[\w.\-]+", _claude("plugin", "list")[1]))


def _claude(*args):
    import ai_steps
    r = subprocess.run([ai_steps.claude_exe(), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=HIDDEN, timeout=180)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def add_roadmap_to_claude(say=print):
    """The roadmap comes with the assistant plugin: nothing is added separately."""
    if roadmap_in_claude():
        say("Claude already has the roadmap: it comes with the assistant plugin.")
        return True
    raise RuntimeError("The roadmap comes with the assistant plugin. Add the assistant plugin to Claude the way its README says, "
                       "then open this step again.")


def roadmaps_applied():
    """[(project folder, one plain line on where its roadmap stands)] for every project roadmaps are shown for."""
    rm = _page_roadmaps()
    out = []
    for folder in rm.applied():
        got = rm.one(folder)
        out.append((folder, got.get("note") or f"{got['name']}: {len(got.get('rows') or [])} rows, "
                                               f"{got.get('checks_waiting', 0)} checks to try, {got.get('questions_open', 0)} "
                                               f"questions open, last changed {got.get('changed') or 'not yet'}"))
    return out


def apply_roadmap(folder):
    """Show one project's roadmap on this assistant's page: the assistant lists itself as a reader in the
    project (so the roadmap's writer keeps the plain summary) and the folder joins the list the page shows.
    Returns the plain line saying what, if anything, is left for the owner to do in that project."""
    folder = os.path.abspath(str(folder or "").strip().strip('"'))
    if not os.path.isdir(folder):
        raise ValueError("Choose a project folder that is on this computer.")
    rm = _page_roadmaps()
    if os.path.normcase(folder) in {os.path.normcase(f) for f in rm.applied()}:
        raise ValueError("The roadmap is already applied to that folder.")
    _list_me(folder, True)
    s = common.settings()
    s["roadmaps"] = [e for e in s.get("roadmaps") or [] if isinstance(e, dict)] + \
                    [{"folder": folder, "applied": common.now().isoformat(timespec="seconds")}]
    common.write_json(common.SETTINGS, s)
    if (common.read_json(rm.plain_copy(folder), {}) or {}).get("written"):
        return "Applied. This project's roadmap shows on your page within about half a minute."
    has_one = os.path.isfile(os.path.join(folder, "Roadmap page", "roadmap.html")) or \
        bool((common.read_json(os.path.join(folder, ".claude", "roadmap", "config.json"), {}) or {}).get("page_url"))
    if has_one:
        return ("Applied. This project already has a roadmap. It shows on your page now, waiting for its first summary; "
                "that project's main session is reminded to have its Roadmap writer write it, at its next message. To have it "
                "now, say there: \"have the Roadmap writer write the plain copy now\".")
    return ("Applied. One thing is left, in the Claude desktop app: open this folder in the Code tab and send "
            "/assistant:roadmap-setup (the roadmap comes with this assistant plugin). The roadmap shows on your page after its first change.")


def take_roadmap_off(folder):
    """Stop showing one project's roadmap: it leaves this assistant's page and the assistant takes itself off
    the project's list of readers. The roadmap itself, its page and its facts are not touched; switching the
    roadmap off inside a project is the plugin's own business (its README says how). Returns plain lines."""
    folder = os.path.abspath(str(folder or "").strip())
    s = common.settings()
    kept = [e for e in s.get("roadmaps") or []
            if isinstance(e, dict) and os.path.normcase(str(e.get("folder") or "")) != os.path.normcase(folder)]
    if kept:
        s["roadmaps"] = kept
    else:
        s.pop("roadmaps", None)         # applied to nothing leaves no trace
    common.write_json(common.SETTINGS, s)
    said = ["Taken off your page."]
    try:
        _list_me(folder, False)
        said.append("The roadmap itself is untouched and still works in that project.")
    except OSError as e:
        said.append(f"I couldn't take myself off that project's list of readers ({type(e).__name__}); "
                    "its writer goes on keeping the plain summary, which harms nothing.")
    return said


# --- step 7: the page ----------------------------------------------------------------------------------
FIRST_PORT = 47815


def hosting():
    """Where the owner chose for their page: "own_pc", "hosted" or "both"; None until they have chosen."""
    got = common.settings().get("page_hosting")
    return got if got in ("own_pc", "hosted", "both") else None


def _port_free(port):
    import socket
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _port():
    """This copy's port for its page on this computer: the one already in its settings, else the first free one
    (two copies of the assistant on one computer each need their own)."""
    s = common.settings()
    got = s.get("page_port")
    if isinstance(got, int):
        return got
    if s.get("page_hosting") in ("own_pc", "both"):
        return FIRST_PORT       # a page already living here with no port on record is on the default one; never move it
    return next((p for p in range(FIRST_PORT, FIRST_PORT + 200) if _port_free(p)), FIRST_PORT)


def local_page_address(preview=False):
    """The page's address on this computer. With preview nothing is written; the port is settled by set_hosting."""
    return f"http://127.0.0.1:{_port() if preview else (common.settings().get('page_port') or FIRST_PORT)}"


def set_hosting(choice):
    """Record where the page lives. For this computer, also settle the port it answers on."""
    if choice not in ("own_pc", "hosted", "both"):
        raise ValueError("Choose where your page should live.")
    s = common.settings()
    s["page_hosting"] = choice
    if choice in ("own_pc", "both") and not isinstance(s.get("page_port"), int):
        s["page_port"] = _port()
    common.write_json(common.SETTINGS, s)
    return choice


# --- reaching this computer's page from anywhere, through Tailscale ---------------------------------------
# Tailscale is a separate program the owner installs and signs in to themself; this product never downloads
# it, never installs it and never signs anyone in. Its "Funnel" hands requests from the internet to one local
# address. Only this page's own entry is ever made or removed: a public port that already carries anything is
# never taken over, and nothing here resets Tailscale.
REACH_PORTS = (443, 8443, 10000)        # the only public ports Funnel allows
TAILSCALE_GET = "tailscale.com/download"
REACH_SAYS = ("Tailscale is a free program (free for personal use) that gives this computer an encrypted address of its own"
              "on the internet, so your page can be opened from your phone or another computer. Your page stays on this "
              "computer and stays locked with your password.")


def tailscale_exe():
    """The Tailscale command on this computer, or "" when it is not installed."""
    found = shutil.which("tailscale")
    if found:
        return found
    for folder in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles(x86)")):
        path = os.path.join(folder or "", "Tailscale", "tailscale.exe")
        if folder and os.path.isfile(path):
            return path
    return ""


def _tailscale(*args, timeout=20):
    """Run one Tailscale command hidden, with a time limit: (exit code or None when it ran out of time, output)."""
    exe = tailscale_exe()
    if not exe:
        return 127, ""
    try:
        r = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=HIDDEN, timeout=timeout, stdin=subprocess.DEVNULL)
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except subprocess.TimeoutExpired as e:
        out = e.stdout or b""
        err = e.stderr or b""
        text = (out if isinstance(out, str) else out.decode("utf-8", "replace")) + (err if isinstance(err, str) else err.decode("utf-8", "replace"))
        return None, text.strip()
    except OSError as e:
        return 126, type(e).__name__


def _json_in(text):
    try:
        got = json.loads(text[text.index("{"):]) if "{" in text else {}
    except ValueError:
        got = {}
    return got if isinstance(got, dict) else {}


def reach():
    """How this computer's page is reached, from the home's settings: {"how": "this_pc"} or
    {"how": "tailscale", "port", "address", "read_at"}."""
    got = (common.read_json(common.SETTINGS, {}) or {}).get("page_reach")
    if isinstance(got, dict) and got.get("how") == "tailscale" and got.get("port") in REACH_PORTS and str(got.get("address") or "").startswith("https://"):
        return dict(got)
    return {"how": "this_pc"}


def _local_target():
    return f"http://127.0.0.1:{common.settings().get('page_port') or FIRST_PORT}"


def _reach_look():
    """What Tailscale on this computer says right now: installed, signed in, its name, which public ports carry
    something, and which one (if any) already carries this page."""
    if not tailscale_exe():
        return {"installed": False}
    code, out = _tailscale("status", "--json")
    st = _json_in(out)
    name = str((st.get("Self") or {}).get("DNSName") or "").strip().rstrip(".").lower()
    look = {"installed": True, "signed_in": st.get("BackendState") == "Running" and bool(name), "name": name, "taken": [], "mine": None}
    if not look["signed_in"]:
        return look
    code, out = _tailscale("serve", "status", "--json")
    serve = _json_in(out)
    taken = {int(p) for p in (serve.get("TCP") or {}) if str(p).isdigit()}
    for host, web in (serve.get("Web") or {}).items():
        port = host.rsplit(":", 1)[-1]
        if not port.isdigit():
            continue
        taken.add(int(port))
        handlers = (web or {}).get("Handlers") or {}
        if set(handlers) == {"/"} and str((handlers["/"] or {}).get("Proxy") or "").rstrip("/") == _local_target() \
                and (serve.get("AllowFunnel") or {}).get(host):
            look["mine"] = int(port)
    look["taken"] = sorted(taken)
    return look


def _public_address(name, port):
    return f"https://{name}" + ("" if port == 443 else f":{port}")


def reach_status():
    """Where being reached from anywhere stands, in plain words for the setup window:
    {"state": "missing" | "signed_out" | "no_port" | "ready" | "on", "says", "port", "address"}."""
    look = _reach_look()
    if not look["installed"]:
        return {"state": "missing", "says": f"Tailscale is not on this computer yet. Do step 1: get it at {TAILSCALE_GET}, install it and "
                                            "sign in. You do that yourself; I never install it and never sign in for you. "
                                            "Then press \"Look again\"."}
    if not look["signed_in"]:
        return {"state": "signed_out", "says": "Tailscale is installed but not signed in (or it is switched off). Open Tailscale from the "
                                               "Start menu, sign in, and wait until it says Connected. Then press \"Look again\"."}
    if look["mine"]:
        address = _public_address(look["name"], look["mine"])
        return {"state": "on", "port": look["mine"], "address": address,
                "says": "It is on. Your page can be opened from anywhere at the address below."}
    free = [p for p in REACH_PORTS if p not in look["taken"]]
    if not free:
        return {"state": "no_port", "says": "Tailscale on this computer already uses all three public ports it allows (443, 8443 and 10000) "
                                            "for other things, so there is none left for your page. Nothing of theirs was touched. Free one "
                                            "of them in Tailscale, then press \"Look again\"."}
    used = [p for p in REACH_PORTS if p in look["taken"]]
    return {"state": "ready", "port": free[0], "address": _public_address(look["name"], free[0]),
            "says": "Tailscale is installed and signed in. " + (f"Something else on this computer already uses its port "
                    f"{' and '.join(map(str, used))}, which is left alone, so your page will use port {free[0]}. " if used else "")
                    + "Do step 2: press \"Switch it on\"."}


def _save_reach(value):
    s = common.settings()
    if value:
        s["page_reach"] = value
    else:
        s.pop("page_reach", None)
    common.write_json(common.SETTINGS, s)


def reach_on(say=print, port=None):
    """Switch on being reached from anywhere for this home's page: one Tailscale Funnel entry from a free public
    port to this computer's page. Returns reach_status() afterward, with "approve" (a web address) when
    Tailscale first wants the account's owner to approve it in the browser."""
    now = reach_status()
    if now["state"] in ("missing", "signed_out", "no_port"):
        raise RuntimeError(now["says"])
    if now["state"] == "on":
        _save_reach({"how": "tailscale", "port": now["port"], "address": now["address"], "read_at": common.now().isoformat(timespec="seconds")})
        return now
    look = _reach_look()
    port = port if port in REACH_PORTS and port not in look["taken"] else now["port"]
    if port in look["taken"]:
        raise RuntimeError(f"Port {port} already carries something else in Tailscale, and it is never taken over.")
    code, out = _tailscale("funnel", "--bg", f"--https={port}", _local_target(), timeout=30)
    ask = re.search(r"https://login\.tailscale\.com/\S+", out or "")
    after = reach_status()
    if after["state"] != "on":
        if ask:         # the first time: the account's owner approves it once, on Tailscale's own page
            import webbrowser
            webbrowser.open(ask.group(0))
            say("Tailscale wants you to approve this once. Your browser has opened its page; approve it there, then press "
                "\"Switch it on\" again.")
            return dict(after, approve=ask.group(0))
        raise RuntimeError("Tailscale did not switch it on" + (f": {out[-300:]}" if out else " (no answer within 30 seconds).")
                           + " Nothing else in Tailscale was changed.")
    _save_reach({"how": "tailscale", "port": after["port"], "address": after["address"], "read_at": common.now().isoformat(timespec="seconds")})
    say(f"It is on: {after['address']}")
    return after


def reach_off(say=print):
    """Switch it off: remove only this page's own Funnel entry, on its own port. Anything else in Tailscale is
    left exactly as it was."""
    look = _reach_look()
    if look.get("installed") and look.get("signed_in") and look.get("mine"):
        code, out = _tailscale("funnel", f"--https={look['mine']}", "off", timeout=30)
        if _reach_look().get("mine"):
            raise RuntimeError("Tailscale did not switch it off" + (f": {out[-300:]}" if out else "") + ". Nothing else was changed.")
    _save_reach(None)
    say("It is off. Your page can be opened on this computer only.")
    return reach_status()


def reach_check():
    """Fetch the public address the way a phone would and see this page answer: (True or False, plain line)."""
    import urllib.error
    import urllib.request
    now = reach_status()
    if now["state"] != "on":
        return False, "It is not switched on, so there is nothing to check."
    try:
        with urllib.request.urlopen(urllib.request.Request(now["address"] + "/", headers={"User-Agent": "assistant-setup-check"}), timeout=25) as r:
            page = r.read(20000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, f"The address answered, but with an error ({e.code}). Is this computer's page running? It starts with the background job."
    except OSError as e:
        return False, (f"The address did not answer ({type(e).__name__}). The first time it can take up to 10 minutes to appear on "
                       "the internet. Wait a little and press \"Check it\" again.")
    if "Sign in to open the page." in page or "Choose the password for this page." in page or 'src="/s/app.js"' in page:
        return True, f"It works: {now['address']} shows your page's sign-in. Open that address on your phone."
    return False, "The address answered, but not with your page. Something else may be using that address."


def _page_tool(code, timeout=60):
    """Run a few lines against the page's own programs, hidden; returns (exit code, output)."""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=HIDDEN, cwd=LIVE_PAGE, timeout=timeout,
                       env=dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def local_page_served(wait=0):
    """True when this computer is answering at the page's own address (the listener job serves it)."""
    import time
    import urllib.request
    end = time.time() + wait
    while True:
        try:
            with urllib.request.urlopen(local_page_address() + "/", timeout=5) as r:
                return r.status < 500
        except urllib.error.HTTPError as e:
            return e.code < 500
        except OSError:
            if time.time() >= end:
                return False
            time.sleep(2)


def open_local_page(say=print):
    """When the page lives on this computer: wait for the listener to serve it, send it its first data, and open
    the browser once at the one-time address where the owner chooses the password (or at the page itself when a
    password is already set). Returns the page's address, or "" when the page does not live on this computer."""
    if hosting() not in ("own_pc", "both"):
        return ""
    where = local_page_address()
    if not local_page_served(wait=90):
        say(f"Your page at {where} is not answering yet. It starts with the background job; open that address in a "
            "minute. To choose its password, open Setup again and press the button on this step.")
        return where
    _page_tool("import publish, sys; sys.argv=['publish.py']; publish.main()", timeout=120)
    code, out = _page_tool("import local_site; print('SET' if local_site.password_is_set() else 'NOT')")
    if "SET" in out:
        import webbrowser
        webbrowser.open(where)
        say(f"Your page is open in your browser: {where}")
    else:
        code, out = _page_tool("import sys, local_site; sys.argv=['local_site.py','--setup','--open']; "
                               "import runpy; runpy.run_path('local_site.py', run_name='__main__')")
        say(f"Your browser has opened so you can choose your page's password (10 characters or more). "
            f"After that your page is always at {where}" if code == 0 else
            f"The password page could not be opened ({out.strip()[-160:]}). Your page is at {where}.")
    return where


def page_address():
    return str((common.read_json(common.PAGE_KEY, {}) or {}).get("site") or "")


def page(address, replace=False):
    """Make the page's files and its keys for the owner's own web address. Returns
    {"upload": folder to upload, "access": the owner's own access file to upload over the general one,
    "config": file to upload as config.php in the data folder, "open": the one-time address where the
    owner sets their page password}. The owner's files are made in their home. Refuses to replace a page already set up
    unless told to, because new keys cut the old page off."""
    address = address.strip().rstrip("/")
    if not address.startswith("https://"):
        raise ValueError("The page address must start with https://")
    if page_address() and not replace:
        raise ValueError("A page is already set up for this home. Setting it up again makes new keys and the "
                         "old page stops updating until its config file is uploaded again.")
    r = subprocess.run([sys.executable, os.path.join(LIVE_PAGE, "build_site.py"), "--keys", address],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=HIDDEN,
                       env=dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME))
    if r.returncode:
        raise RuntimeError("The page files could not be made: " + (r.stderr or r.stdout).strip()[-300:])
    found = re.search(r"(https://\S+/setup#\S+)", r.stdout)
    state = os.path.join(common.HOME, "page_state")
    made = {"upload": os.path.join(LIVE_PAGE, "site"), "access": os.path.join(state, "site", ".htaccess"),
            "config": os.path.join(state, "site_config.php"), "open": found.group(1) if found else ""}
    missing = [k for k in ("access", "config") if not os.path.exists(made[k])]
    if missing or not made["open"]:
        raise RuntimeError("The page files were not all made (" + ", ".join(missing or ["the one-time address"]) + ").")
    return made


# --- step 7: turn it on ------------------------------------------------------------------------------------
def _pythonw():
    exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return exe if os.path.exists(exe) else sys.executable


def tasks_on():
    """The names of THIS copy's scheduled jobs that exist on this computer: its listener job, and the separate pass job
    only on a home set up before the listener ran the check itself (retire_pass_job removes that one on update)."""
    r = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/NH"], capture_output=True, text=True, creationflags=HIDDEN)
    return [t for t in job_names() if f'"\\{t}",' in (r.stdout or "")]


def job_names():
    """(old pass job, listener job) for this copy; see paths.job_names. Only the listener's job is made now; the pass job's
    name is kept so an older home's one can be found and retired."""
    return common.paths.job_names()


def write_install_scripts():
    """The small script that creates the one scheduled job (the listener, which also runs the 15-minute check), written
    into the owner's personal folder with this computer's own paths filled in. Returns its path in a list."""
    folder = os.path.join(common.PERSONAL, "install")
    os.makedirs(folder, exist_ok=True)
    pass_job, listener_job = job_names()
    # the names are written down once, so the jobs keep theirs even if the home is later moved
    common.write_json(common.paths.JOBS_JSON, {"pass": pass_job, "listener": listener_job})
    fill = {"PYTHONW": _pythonw(), "LIVE": common.HERE, "LIVE_PAGE": LIVE_PAGE, "OWNER": common.owner(), "HOME": common.HOME,
            "PASS_TASK": pass_job, "LISTENER_TASK": listener_job}
    out = []
    for name in ("install_listener.ps1",):
        with open(os.path.join(STARTER, "install", name), encoding="utf-8") as f:
            text = f.read()
        for k, v in fill.items():
            text = text.replace("{" + k + "}", v)
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
        out.append(path)
    return out


def turn_on(say=print):
    """Create the one scheduled job: the listener, which serves the page, acts on page answers at once and runs the
    15-minute check itself. It runs hidden, as the signed-in user, with no admin rights. A job that already exists is
    left alone."""
    have = tasks_on()
    made = []
    for path, task in zip(write_install_scripts(), job_names()[1:]):
        if task in have:
            say(f"\"{task}\" is already on.")
            continue
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                            "-ExecutionPolicy", "Bypass", "-File", path], capture_output=True, text=True, creationflags=HIDDEN)
        if r.returncode or task not in tasks_on():
            raise RuntimeError(f"Windows would not create \"{task}\": {(r.stderr or r.stdout).strip()[-300:]}")
        made.append(task)
        say(f"\"{task}\" is on.")
    return made


def renew_listener_job(was_off=None):
    """On update: the listener's job made again from the current install script (its settings changed: starts side by side,
    so a healthy listener never shows a refused start as its last result). A job that was switched off (was_off; asked of
    Windows when not given) stays off. Returns the job's name, or "" when this copy has no listener job."""
    name = job_names()[1]
    if name not in tasks_on():
        return ""
    if was_off is None:
        q = subprocess.run(["schtasks", "/Query", "/TN", name, "/FO", "LIST"], capture_output=True, text=True, creationflags=HIDDEN)
        was_off = "disabled" in (q.stdout or "").lower()
    script = write_install_scripts()[0]
    with open(script, encoding="utf-8") as f:
        text = f.read()
    text = text.replace("Register-ScheduledTask -TaskName", "Register-ScheduledTask -Force -TaskName")
    again = os.path.join(os.path.dirname(script), "renew_listener.ps1")
    with open(again, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                        "-ExecutionPolicy", "Bypass", "-File", again], capture_output=True, text=True, creationflags=HIDDEN)
    if r.returncode or name not in tasks_on():
        raise RuntimeError(f"Windows would not make \"{name}\" again: {(r.stderr or r.stdout).strip()[-300:]}")
    if was_off:
        subprocess.run(["schtasks", "/Change", "/TN", name, "/DISABLE"], capture_output=True, creationflags=HIDDEN)
    return name


def retire_pass_job(owner_off=False):
    """On update: an older home's separate pass job is no longer needed (the listener runs the check). The job and its
    install script are deleted outright. owner_off: the owner had it switched off (Sync off), so Sync is kept off in
    Settings, the switch the check itself reads. Returns the job's name, or "" when there was none."""
    name = job_names()[0]
    if name not in tasks_on():
        return ""
    if owner_off:
        s = common.settings()
        g = s.get("gathering") if isinstance(s.get("gathering"), dict) else {}
        if not g.get("paused"):
            g["paused"] = True
            g["paused_at"] = common.now().isoformat(timespec="seconds")
            s["gathering"] = g
            common.write_json(common.SETTINGS, s)
    old_script = os.path.join(common.PERSONAL, "install", "install_task.ps1")
    if os.path.isfile(old_script):
        os.remove(old_script)
    subprocess.run(["schtasks", "/End", "/TN", name], capture_output=True, creationflags=HIDDEN)
    r = subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"], capture_output=True, text=True, creationflags=HIDDEN)
    if r.returncode or name in tasks_on():
        raise RuntimeError(f"Windows would not remove \"{name}\": {(r.stderr or r.stdout).strip()[-300:]}")
    return name


PASS_BUSY = 3                # pass.py's answer when the pass before it still holds the lock
BUSY_WAIT_SECONDS = 10


def _one_pass(say=None, most=None):
    """Run pass.py once to the end. While the listener's own check holds the lock (it answers 3), wait and try again,
    for as long as a pass may hold it (limits.STALE_LOCK) or `most` seconds, so a check never fails just because a
    pass was running. Returns the finished run, or None when a pass still held the lock at the end."""
    import time
    import limits
    end = time.time() + (most if most is not None else limits.STALE_LOCK + 60)
    told = False
    while True:
        r = subprocess.run([sys.executable, os.path.join(common.HERE, "pass.py")], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", creationflags=HIDDEN, timeout=20 * 60,
                           env=dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME))
        if r.returncode != PASS_BUSY:
            return r
        if time.time() > end:
            return None
        if say and not told:
            say("I'm reading your accounts right now; this waits for me to finish, then runs.")
            told = True
        time.sleep(BUSY_WAIT_SECONDS)


def check_once(most=None):
    """One whole pass, run now and waited for, as a check after a change: (True or False, plain lines for the owner).
    It waits while the assistant is already reading (a pass holds the lock), then checks once."""
    r = _one_pass(most=most)
    if r is None:
        return False, ["I was still busy reading your accounts, so the check could not run. Nothing is wrong "
                       "with the change itself; it can be checked again in a few minutes."]
    return _pass_said(r)


def restart_listener():
    """Stop and start the job that serves the page, then wait until the page answers: (True or False, one plain line)."""
    name = job_names()[1]
    if name not in tasks_on():
        return False, "The part that serves your page is not switched on, so the change cannot be seen on the page."
    subprocess.run(["schtasks", "/End", "/TN", name], capture_output=True, creationflags=HIDDEN)
    r = subprocess.run(["schtasks", "/Run", "/TN", name], capture_output=True, text=True, creationflags=HIDDEN)
    if r.returncode:
        return False, "Windows would not start the part that serves your page again."
    if not local_page_served(wait=60):
        return False, "Your page did not answer within a minute after it was started again."
    return True, ""


def first_pass(say=print):
    """Run one whole pass now and say how it went: (True or False, plain lines)."""
    say("Reading your accounts for the first time. This can take several minutes.")
    return _pass_said(_one_pass(say))


def _plain(text):
    """A problem line for the owner: no file names and no C:\\ places."""
    import re
    t = re.sub(r"[A-Za-z]:\\[^\s,;]+", "a file on this computer", str(text))
    t = re.sub(r"\b[\w.-]+\.(json|py|log|duckdb|md|txt|tmp)\b", "a file", t)
    return t


def _pass_said(r):
    health = common.read_json(common.HEALTH_JSON, {}) or {}
    last = health.get("last_pass") or {}
    lines = [f"Check finished: {last.get('outcome', 'no result')}, {last.get('new_messages', 0)} new messages read, "
             f"{last.get('open_items', 0)} items on your page."]
    lines += [f"Problem: {_plain(p)}" for p in health.get("problems") or []]
    return r.returncode == 0 and last.get("outcome") == "ok", lines


def status():
    """Where setup stands, for the last screen and for a quick look later."""
    me = _me()
    return {"owner": me.get("owner"), "connections": connected(), "sources": me.get("sources") or [],
            "calendars": me.get("today_calendars") or [], "important": common.important_lines(),
            "page": page_address(), "alerts": bool((common.settings().get("alerts") or {}).get("topic")),
            "may": allowed(), "hosting": hosting(), "reach": reach(), "jobs": tasks_on(),
            "roadmaps": len(_page_roadmaps().applied())}


if __name__ == "__main__":
    print(json.dumps(status(), indent=1, default=str))


# --- reading back to a date (the setup interview calls this) -------------------------------------------------
def read_back(since, estimate_only=False, max_runs=None):
    """Read every connected source back to `since` (a date or 'YYYY-MM-DD') and record the history (readback.py).
    estimate_only: reads the sources into the database (no Claude) and says what the real reading would cost:
    {"messages", "claude_runs", "minutes", "says"}. Otherwise does it and returns
    {"since", "read", "done", "answered", "open", "waiting", "unsure", "not_tasks", "claude_runs", "says"}.
    Hidden, takes the pass lock; safe to run twice and from an earlier date."""
    import datetime as _dt
    import readback
    day = since if isinstance(since, _dt.date) else _dt.date.fromisoformat(str(since)[:10])
    if estimate_only:
        import gather
        if not gather.take_lock():
            return {"says": "I'm checking for messages right now; try again in a few minutes."}
        try:
            readback.ensure()
            run_id = "readback-plan-" + common.now().strftime("%Y%m%d-%H%M%S")
            readback.fetch(day, run_id)
            readback.settle_mechanically()
        finally:
            gather.drop_lock()
        p = readback.plan(day)
        return {"messages": p["messages"], "claude_runs": p["claude_runs"], "minutes": p["minutes"], "says": p["words"]}
    s = readback.run(day, go=True, max_runs=max_runs)
    if s is None:
        return {"says": "I'm checking for messages right now; try again in a few minutes."}
    return {"since": s["since"], "read": s["tasks_came_in"] + s["not_tasks"], "done": s["completed"], "answered": s["answered"], "open": s["still_open"],
            "waiting": s["waiting_on_others"], "not_tasks": s["not_tasks"], "unsure": s["unsure"], "claude_runs": s["claude_runs"],
            "says": f"{s['tasks_came_in']} tasks came in, you answered {s['answered']}, {s['completed']} were completed, {s['still_open']} are open."}
