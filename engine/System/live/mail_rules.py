r"""Mail rules in Settings: the rules the mail services run on their side (Outlook inbox rules, Gmail filters). The page lists
each mailbox's rules in plain words, makes one from a simple form after the owner has seen it in words and pressed Save, and
deletes one after a confirm. The service runs each rule, so this module only asks and writes. A sign-in that lacks the
permission is said so plainly, with the way to allow it, and nothing else fails.

    listing()              every connected mailbox: what it may do, its folders, and its rules in plain words
    words(rule, paths)     one rule in plain words, as the page shows it
    act(rec, dry)          one press {"mail_rule": {"op": "create"|"delete", ...}}: the change, made once
"""
import json
import os

import common

ACTIONS = ("move", "archive", "read", "star")
PICK_KINDS = ("inbox", "archive", "folder", "label")         # the folders a rule may move mail to
ALLOW = "To allow it, open Setup, pick that mailbox and press Sign in again."
ARROW = " → "


def _permitted(conn, need):
    """Whether the sign-in on this computer allows these permissions. Not known yet counts as yes; a refused call then says so."""
    import connections
    scope = connections._granted().get(conn.get("id"))
    return scope is None or any(n in str(scope).split() for n in need)


def _folders(addr):
    """The folders a rule may move mail to, from the stored folder list (the mail service's own ids and paths)."""
    import mail
    got = mail.folders(addr)
    rows = next((a["folders"] for a in got.get("accounts", []) if a.get("address") == addr), [])
    return [f for f in rows if f.get("kind") in PICK_KINDS]


def words(rule, paths):
    """One rule in plain words: "From acme.example → move to Inbox/Suppliers"."""
    w, t = rule.get("when") or {}, rule.get("then") or {}
    when = [("from " + w["from"]) if w.get("from") else "", ('subject contains "' + w["subject"] + '"') if w.get("subject") else "",
            ("sent to " + w["to"]) if w.get("to") else ""]
    acts = [("move to " + paths.get(str(t["move"]), "a folder")) if t.get("move") else "",
            "archive it" if t.get("archive") and not t.get("move") else "", "mark as read" if t.get("read") else "",
            "star it" if t.get("star") else ""]
    text = " and ".join(x for x in when if x) or "any mail"
    text += ARROW + (" and ".join(x for x in acts if x) or "nothing this page shows")
    if rule.get("enabled") is False:
        text += " (turned off)"
    return text[:1].upper() + text[1:]


def listing():
    """{ok, accounts: [{address, type, can_read, can_write, note, error, folders, rules: [{id, words, read_only, can_delete}]}]}."""
    import connections
    import mail
    try:
        out = []
        for c in connections.listed("email"):
            addr = str(c.get("address") or "").lower()
            mod = connections.module(c["type"])
            if not addr or not hasattr(mod, "rules_list"):
                continue
            can_read, can_write = _permitted(c, mod.RULE_READ), _permitted(c, mod.RULE_WRITE)
            folders = _folders(addr)
            paths = {str(f["id"]): f["path"] for f in folders}
            item = {"address": addr, "type": c["type"], "can_read": can_read, "can_write": can_write, "folders": folders,
                    "note": "", "error": "", "rules": []}
            if not can_read:
                item["error"] = f"The sign-in for {addr} does not allow reading its mail rules yet. " + ALLOW
            elif not can_write:
                item["note"] = f"Making and deleting rules needs a new sign-in for {addr}. " + ALLOW
            if can_read:
                try:
                    for r in mod.rules_list(c):
                        item["rules"].append({"id": r["id"], "words": words(r, paths), "read_only": r["read_only"],
                                              "can_delete": can_write and not r["read_only"]})
                except Exception as e:  # noqa: BLE001
                    item["error"] = _refused_words(e, addr, "read its mail rules")
            out.append(item)
        import settings_page
        return {"ok": True, "accounts": settings_page.mail_ordered(out, lambda x: x["address"])}
    except mail.Busy:
        return {"ok": False, "busy": True}


def _refused_words(e, addr, doing):
    if _refusal(e):
        return f"The sign-in for {addr} does not allow it yet. " + ALLOW
    return f"Could not {doing} for {addr} just now ({type(e).__name__}). Try again in a minute."


def _refusal(e):
    from connections import _http
    return type(e).__name__ == "NotAllowed" or (isinstance(e, _http.Refused) and e.status in (401, 403))


def _no(text):
    return {"ok": True, "items": [], "result": "Not done: " + text if not text.startswith("Not done") else text}


def act(rec, dry=False):
    """One press from Settings, Mail rules. Returns the act_on_answer result. dry: a Create is only checked and put in words
    (the assistant shows a rule before it is made; nothing is sent to the mail service)."""
    import connections
    try:
        got = json.loads(rec.get("text") or "")["mail_rule"]
        op, addr = str(got["op"]), str(got["account"]).strip().lower()
    except (ValueError, KeyError, TypeError):
        return _no("that press could not be read. Nothing was changed.")
    conn, mod = connections.mailbox(addr)
    if conn is None or not hasattr(mod, "rules_list"):
        return _no(f"{addr} is not connected.")
    if op == "create":
        return _create(conn, mod, addr, got, dry)
    if op == "delete":
        return _delete(conn, mod, addr, got)
    return _no("that press could not be read. Nothing was changed.")


def _create(conn, mod, addr, got, dry=False):
    if not _permitted(conn, mod.RULE_WRITE):
        return _no(f"the sign-in for {addr} does not allow rules yet. " + ALLOW)
    when = {k: str((got.get("when") or {}).get(k) or "").strip()[:200] for k in ("from", "subject", "to")}
    if not any(when.values()):
        return _no("a rule needs a sender, words in the subject or a recipient.")
    if getattr(mod, "RULE_NEEDS_ADDRESS", False) and any("@" not in when[k] for k in ("from", "to") if when[k]):
        return _no("Outlook needs a full email address for sender and recipient, such as name@example.com.")
    do = str(got.get("do") or "")
    if do not in ACTIONS:
        return _no("that action is not one the page makes.")
    folders = _folders(addr)
    paths = {str(f["id"]): f["path"] for f in folders}
    folder = ""
    if do == "move":
        folder = str(got.get("folder") or "")
        if folder not in paths:
            return _no(f"{addr} has no such folder.")
    elif do == "archive":
        folder = next((str(f["id"]) for f in folders if f.get("kind") == "archive"), "")
        if not folder and getattr(mod, "RULE_NEEDS_ADDRESS", False):
            return _no(f"{addr} has no Archive folder to move mail to.")
    rule = {"when": when, "then": {"move": folder if do == "move" else None, "archive": do == "archive",
                                   "read": do == "read", "star": do == "star"}}
    spec = {"when": when, "do": do, "folder": folder, "name": words(rule, paths)}
    if dry:
        return {"ok": True, "items": [], "result": spec["name"] + ".", "dry": True}
    try:
        mod.rule_create(conn, spec)
    except Exception as e:  # noqa: BLE001
        return _no(_refused_words(e, addr, "make the rule") if _refusal(e) else f"{addr} refused it ({type(e).__name__}). Nothing was made.")
    common.log_line(os.path.join(common.LOGS, "mail.log"), f"mail rule made for {addr}")
    return {"ok": True, "items": [], "result": f"Rule saved: {spec['name']}."}


def _delete(conn, mod, addr, got):
    if not _permitted(conn, mod.RULE_WRITE):
        return _no(f"the sign-in for {addr} does not allow rules yet. " + ALLOW)
    rid = str(got.get("rule") or "")
    paths = {str(f["id"]): f["path"] for f in _folders(addr)}
    try:
        rules = mod.rules_list(conn)
    except Exception as e:  # noqa: BLE001
        return _no(_refused_words(e, addr, "read its mail rules"))
    rule = next((r for r in rules if str(r["id"]) == rid), None)
    if rule is None:
        return _no("that rule is not there any more.")
    if rule["read_only"]:
        return _no("that rule does more than this page shows, so it can only be changed in " + ("Outlook" if conn["type"] == "microsoft_mail" else "Gmail") + ".")
    try:
        mod.rule_delete(conn, rid)
    except Exception as e:  # noqa: BLE001
        return _no(_refused_words(e, addr, "delete the rule") if _refusal(e) else f"{addr} refused it ({type(e).__name__}). Nothing was deleted.")
    common.log_line(os.path.join(common.LOGS, "mail.log"), f"mail rule deleted for {addr}")
    return {"ok": True, "items": [], "result": f"Deleted the rule: {words(rule, paths)}."}
