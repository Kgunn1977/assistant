r"""Mods: the owner's own changes, kept apart from the program. A mod takes the program's place where it applies and
never changes a program file; the program loads it beside itself.

WHERE A MOD LIVES. <home>\mods\<name>\ (the owner's data: an update never writes there). It holds:
    mod.json    what the mod is and what it claims (below)
    mod.py      its code, with any of the functions below; it may import its own files from the same folder
    chat.md     optional: words added to the chat's instructions
    page.md     optional: lines added to the chat's guide to the page
    rules.json  optional: its own rules on top of the guardrails (rules\rulebook.py reads it, with "loosens" below)

mod.json: {"name": "receipts", "title": "Receipts", "on": true,
           "card_prefixes": ["live:receipts-"],             cards it owns: their buttons and answers are its own, and
                                                            the card writer and the rebuild leave them alone
           "pass_seconds": 240,                             time a pass must have left before its step runs
           "chat_tools": {"allow": ["mcp__...__tool"], "deny": [...]},    the only extra tools the chat may use
           "chat_actions": ["receipt_find"],                ACTION types of the chat it carries out
           "settings": {"title": "...", "fields": [{"id", "label", "control", "help", "choices", "explain"}]},   "explain":
                                                            what the field is for, shown by the (i) beside its name; none, no (i)
           "hold_reasons": {"room": "the plain line for a message it held this way"},
           "page": {"id": "chat", "title": "Chat", "script": "page.js", "style": "page.css"},    a part of the page of its own
                                                            (its Tools entries, drawn by tools(), put lib.info(name, words)
                                                            beside a name for the same (i); none, no (i))
           "loosens": [{"rule": "B9", "yes": "the owner's words, and when"}]}     a core rule it loosens, with his yes

mod.py may define:
    pass_step(pass_id) -> str                      a line for the pass log, or ""
    choices(item) -> [str | {"label", "text"}]     the buttons on one of its cards
    answer(item, rec, on_update) -> dict | None    an answer or button on one of its cards: {"said": "...", "fields":
                                                   {...card columns...}, "made": [card ids], "claude": bool}; None
                                                   leaves it to the program
    chat_action(action, when) -> str               one of its chat actions; the line to add to the chat's reply
    check_settings(values) -> values               its Settings section checked; raises ValueError with plain words
    hold(message) -> str | None                    a reason key from its hold_reasons when a message it knows is held
                                                   from you (message: id, channel, from_key, subject, text, named)
    door(route, method, query, body) -> (code, dict)   its own doors, at api/mod/<name>/<route>, for its page part:
                                                   reading needs the signed-in page; a POST also its address and check

WHERE THE PROGRAM CHECKS FOR A MOD: the pass (pass.py, after gathering), a card's buttons (items.lift), an answer on a
card (answers.act_on_answer, before the program's own handling), the card writer and the rebuild (they skip a mod's
cards), the chat (its tools, its instructions, its actions, its page guide), the guardrails (rulebook.book), Settings
(settings_data.defs, settings_page.save), the filters (filters.holds, held.why), the page server (its doors and page
files) and the page (its part, placed like Texts; the page's script lends it the page's helpers). A mod that fails to load
is switched off and says why; the program goes on.
"""
import importlib.util
import json
import os
import sys

import common

FOLDER = os.path.join(common.HOME, "mods")
_loaded = {}            # name -> (mark, module or None, why)


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def listed():
    """Every mod folder's mod.json, switched on or not, with "folder" and "why" (why it is off, when it failed)."""
    out = []
    if not os.path.isdir(FOLDER):
        return out
    for name in sorted(os.listdir(FOLDER)):
        d = os.path.join(FOLDER, name)
        m = _read(os.path.join(d, "mod.json"), None)
        if isinstance(m, dict) and m.get("name") == name:
            out.append(dict(m, folder=d))
    return out


def _mark(d):
    try:
        return tuple(os.path.getmtime(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.endswith((".py", ".json", ".md")))
    except OSError:
        return ()


def _module(m):
    """The mod's code, loaded once (again when its files change). None when it has no mod.py or failed (logged)."""
    d, name = m["folder"], m["name"]
    mark = _mark(d)
    got = _loaded.get(name)
    if got and got[0] == mark:
        return got[1]
    path = os.path.join(d, "mod.py")
    mod, why = None, ""
    if os.path.isfile(path):
        if d not in sys.path:
            sys.path.insert(0, d)
        try:
            spec = importlib.util.spec_from_file_location(f"mod_{name}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:  # noqa: BLE001  a broken mod never stops the program
            mod, why = None, f"{type(e).__name__}: {e}"
            common.log_line(os.path.join(common.LOGS, "errors.log"), f"mod {name} did not load: {why}")
    _loaded[name] = (mark, mod, why)
    return mod


def on():
    """The mods switched on: [(mod.json, module or None)]."""
    return [(m, _module(m)) for m in listed() if m.get("on", True)]


def _call(m, mod, fn, *args, default=None):
    f = getattr(mod, fn, None) if mod else None
    if not callable(f):
        return default
    try:
        return f(*args)
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"mod {m['name']} {fn}: {type(e).__name__}: {e}")
        raise


# --- cards -------------------------------------------------------------------------------------------
def owner(item):
    """(mod.json, module) of the mod that owns this card, or (None, None)."""
    key = str((item or {}).get("source_key") or "")
    for m, mod in on():
        if any(key.startswith(p) for p in m.get("card_prefixes") or [] if p):
            return m, mod
    return None, None


def owns(item):
    import mod_checks
    return mod_checks.is_check(item) or owner(item)[0] is not None


def choices(item):
    m, mod = owner(item)      # a check card's choices are kept on the card itself (mod_checks.py)
    if not m:
        return None
    try:
        return _call(m, mod, "choices", item)
    except Exception:  # noqa: BLE001  the card still shows, without its buttons
        return None


def answer(item, rec, on_update=None):
    """An answer on a mod's card, handled by the mod; None when it is not a mod's card or the mod leaves it."""
    import mod_checks
    if mod_checks.is_check(item):       # a check card: Works, or the words of a Doesn't work (mod_checks.py)
        return mod_checks.answer(item, rec, on_update)
    m, mod = owner(item)
    if not m:
        return None
    try:
        return _call(m, mod, "answer", item, rec, on_update)
    except Exception as e:  # noqa: BLE001
        return {"said": f"Your mod \"{m.get('title') or m['name']}\" could not act on that ({type(e).__name__}). Nothing was changed.",
                "fields": {}}


# --- the pass ----------------------------------------------------------------------------------------
def pass_steps(pass_id, enough=None):
    """Each mod's step, in name order. Returns (lines for the pass log, problems)."""
    lines, problems = [], []
    try:        # the mods' check cards: made whole, a check whose card was closed with Done dropped (mod_checks.py)
        import mod_checks
        mod_checks.sync_all()
    except Exception as e:  # noqa: BLE001
        problems.append(f"mod checks: {type(e).__name__}: {e}")
    for m, mod in on():
        if not callable(getattr(mod, "pass_step", None)):
            continue
        if enough and not enough(int(m.get("pass_seconds") or 60)):
            continue
        try:
            got = mod.pass_step(pass_id)
            if got:
                lines.append(str(got))
            _log(f"{pass_id} {m['name']}: ran" + (f": {str(got)[:200]}" if got else ", nothing to do"))
        except Exception as e:  # noqa: BLE001
            problems.append(f"mod {m['name']}: {type(e).__name__}: {e}")
            _log(f"{pass_id} {m['name']}: failed: {type(e).__name__}: {e}"[:300])
    return lines, problems


def _log(line):
    """One line per mod per pass in the home's logs folder (mods.log), so a mod that had nothing to do is still seen to have run."""
    try:
        common.log_line(os.path.join(common.LOGS, "mods.log"), line)
    except Exception:  # noqa: BLE001  the log never stops a pass
        pass


# --- the chat -----------------------------------------------------------------------------------------
def chat_tools():
    """(allowed, denied): exactly the tools the switched-on mods name for the chat; nothing else is added."""
    allow, deny = [], []
    for m, _mod in on():
        t = m.get("chat_tools") if isinstance(m.get("chat_tools"), dict) else {}
        allow += [str(x) for x in t.get("allow") or [] if str(x).startswith("mcp__")]
        deny += [str(x) for x in t.get("deny") or [] if str(x).startswith("mcp__")]
    return list(dict.fromkeys(allow)), list(dict.fromkeys(deny))


def _texts(name):
    out = []
    for m, _mod in on():
        try:
            with open(os.path.join(m["folder"], name), encoding="utf-8") as f:
                t = f.read().strip()
        except OSError:
            continue
        if t:
            out.append(f"From your mod \"{m.get('title') or m['name']}\":\n{t}")
    return "\n\n".join(out)


def chat_text():
    return _texts("chat.md")


def page_text():
    return _texts("page.md")


def chat_action(action, when):
    """A chat ACTION a mod carries out: the line for the reply, or None when no mod claims its type."""
    kind = str((action or {}).get("type") or "")
    for m, mod in on():
        if kind and kind in (m.get("chat_actions") or []):
            try:
                return str(_call(m, mod, "chat_action", action, when, default="") or "")
            except Exception as e:  # noqa: BLE001
                return f"Your mod \"{m.get('title') or m['name']}\" could not do that ({type(e).__name__})."
    return None


# --- the filters ----------------------------------------------------------------------------------------
def hold(message):
    """"mod:<name>:<reason>" when a switched-on mod holds this message from the owner, else None."""
    for m, mod in on():
        try:
            got = _call(m, mod, "hold", message)
        except Exception:  # noqa: BLE001  a mod that fails holds nothing
            got = None
        if got:
            return f"mod:{m['name']}:{got}"
    return None


def hold_reason(source):
    """The plain line for a message a mod held ("mod:<name>:<reason>"), or None."""
    _x, name, key = (str(source).split(":", 2) + ["", ""])[:3]
    m = next((m for m, _mod in on() if m["name"] == name), None)
    return str(((m or {}).get("hold_reasons") or {}).get(key) or "") or None


# --- its own part of the page ---------------------------------------------------------------------------
NAME_OK = __import__("re").compile(r"^[a-z][a-z0-9_-]{0,40}$")


def page_parts():
    """[{"mod", "id", "title", "script", "style", "mark"}] for each switched-on mod with a part of the page."""
    out = []
    for m, _mod in on():
        p = m.get("page") if isinstance(m.get("page"), dict) else None
        if not p or not NAME_OK.match(str(p.get("id") or "")) or not p.get("script"):
            continue
        d = m["folder"]
        files = [f for f in (p.get("script"), p.get("style")) if f]
        try:
            mark = "-".join(str(int(os.path.getmtime(os.path.join(d, f)))) for f in files)
        except OSError:
            continue
        out.append({"mod": m["name"], "id": str(p["id"]), "title": str(p.get("title") or m.get("title") or m["name"]),
                    "script": str(p["script"]), "style": str(p.get("style") or ""), "mark": mark})
    return out


def page_file(name, file):
    """(bytes, kind) of a file a mod's part names (its script or stylesheet), else None."""
    m = next((m for m, _mod in on() if m["name"] == name), None)
    p = (m or {}).get("page") if isinstance((m or {}).get("page"), dict) else {}
    if not m or file not in (p.get("script"), p.get("style")) or "/" in file or "\\" in file or file.startswith("."):
        return None
    try:
        with open(os.path.join(m["folder"], file), "rb") as f:
            return f.read(), "text/javascript" if file.endswith(".js") else "text/css"
    except OSError:
        return None


def door(name, route, method, query, body):
    """(code, dict) from a switched-on mod's own door, or None when it has none."""
    m = next(((m, mod) for m, mod in on() if m["name"] == name), None)
    if not m or not callable(getattr(m[1], "door", None)):
        return None
    try:
        got = _call(m[0], m[1], "door", route, method, query, body)
    except Exception as e:  # noqa: BLE001  said plainly, never a crash of the page server
        return 500, {"ok": False, "error": f"{m[0].get('title') or name} did not answer ({type(e).__name__})."}
    return got if isinstance(got, tuple) and len(got) == 2 else (404, {"error": "not here"})


# --- Settings -------------------------------------------------------------------------------------------
def settings_groups():
    """[(group id, label)] for each switched-on mod with a Settings section."""
    import mod_checks
    return [("mod:" + m["name"], (m.get("settings") or {}).get("title") or m.get("title") or m["name"])
            for m, _mod in on() if (isinstance(m.get("settings"), dict) and (m["settings"].get("fields") or [])) or mod_checks.status(m["name"])]


def settings_values(name):
    got = common.settings().get(name)
    return got if isinstance(got, dict) else {}


def settings_defs():
    """Each mod's Settings fields, in the shape settings_data gives the page."""
    import mod_checks
    out = []
    for m, _mod in on():
        st = m.get("settings") if isinstance(m.get("settings"), dict) else {}
        vals = settings_values(m["name"])
        got = mod_checks.status(m["name"])
        if got:
            out.append({"group": "mod:" + m["name"], "id": "proven", "can_change": False, "control": "text", "label": "Proven by its checks",
                        "value": "Proven: every check passed" if got[0] else f"Not yet proven: {got[1]} of {got[2]} checks passed",
                        "help": "Each check is a card on your page. Works passes it; Done drops it and leaves the mod unproven."})
        for f in st.get("fields") or []:
            if not isinstance(f, dict) or not f.get("id"):
                continue
            x = {"group": "mod:" + m["name"], "id": str(f["id"]), "label": str(f.get("label") or f["id"]),
                 "help": str(f.get("help") or ""), "explain": str(f.get("explain") or ""), "control": str(f.get("control") or "text"), "value": vals.get(f["id"]),
                 "can_change": True}
            if f.get("choices"):
                x["choices"] = f["choices"]
            out.append(x)
        for ls in m.get("loosens") or []:
            if isinstance(ls, dict) and ls.get("rule"):
                out.append({"group": "mod:" + m["name"], "id": "loosens-" + str(ls["rule"]), "can_change": False,
                            "label": f"Rule {ls['rule']} loosened by this mod", "control": "text",
                            "value": f"With your yes: {ls.get('yes') or 'not recorded'}", "help": str(ls.get("what") or "")})
    return out


def save_settings(name, values):
    """(saved, the plain line). Only the fields the mod names; the mod checks them; written to its own part."""
    m = next((m for m, _mod in on() if m["name"] == name), None)
    if not m:
        return False, "Not saved. That mod is not switched on. Nothing was changed."
    fields = {str(f.get("id")) for f in (m.get("settings") or {}).get("fields") or [] if isinstance(f, dict)}
    if not isinstance(values, dict) or not values or set(values) - fields:
        return False, "Not saved. That is not something this section holds. Nothing was changed."
    mod = _module(m)
    try:
        clean = _call(m, mod, "check_settings", dict(values), default=dict(values))
    except ValueError as e:
        return False, f"Not saved. {e} Nothing was changed."
    s = common.settings()
    part = s.get(name) if isinstance(s.get(name), dict) else {}
    part.update(clean)
    s[name] = part
    common.write_json(common.SETTINGS, s)
    return True, f"Saved: {(m.get('settings') or {}).get('title') or m['name']}. It starts the next time I check for messages."
