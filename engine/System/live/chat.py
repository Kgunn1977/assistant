r"""The box at the top of the page: the owner types to the assistant, and it answers there.

It rides the path every answer already takes: the page saves the words under
the key "chat", the listener hands them to answers.act_on_answer, which hands
them here. handle() adds the words to ONE ongoing Claude session (named in the
owner's personal settings, so they can open the same conversation in their
Claude app), by a short run that can only read, and shows the reply on the
page. A new copy with no session named starts its own on the first message
and remembers it.

Each run is given its working instructions again (prompts\chat.md, with the
owner's personal facts) and what a search of their gathered data found for
these words. The run cannot edit, run commands, send or reach outside: it has
only reading and searching tools, and may read only the assistant's home.

When the owner asks for something to be done (a task kept, an item marked, an
email or text sent, a calendar event added, changed or taken off, a card's
button pressed), the session does not do it: it ends its reply with one ACTION
line per thing asked for, and this program does each in turn through the same
code the page's own buttons use (one that fails never stops the others). A
send or a calendar change goes only when the owner's own words in that same
message ask for it (rule B11), and the reply says exactly what was done. A short conversation is kept in <home>\chat.json for the
page.

    python chat.py "what is on my calendar tomorrow"      # try it from a shell
"""
import datetime as dt
import json
import os
import re
import sys
import threading
import time

import common

CHAT_JSON = os.path.join(common.HOME, "chat.json")
KEEP_TURNS = 40          # kept on disk
SHOW_TURNS = 12          # sent to the page
MODEL = "haiku"
_lock = threading.Lock()
_one = threading.Lock()         # one message to the session at a time
SMALL = set("""the and for you your are was not but have has had with that this from they them then than what when where who why
how can could would should will did does about into its his her him she just need want know said say tell show give get got out all
any more there here been were their also only still some please thanks thank assistant mine does doing done today tomorrow""".split())


# Each card is its own conversation (his plan of 11/23: "each card is its own invisible session"): a card's turns are kept
# here by card and run in that card's own session (convo.py); they are never written into chat.json, never shown in Talk to
# your assistant and never read by the box's session. Card turns chat.json holds from before stay in the file, left out of both.
CARD_TALK = os.path.join(common.HOME, "chat_cards.json")
KEEP_CARD_TURNS, KEEP_CARDS = 30, 300


def load(card_id=None):
    """The box's conversation (chat.json), or with card_id that card's own."""
    if card_id:
        d = common.read_json(CARD_TALK, None)
        turns = ((d or {}).get("cards") or {}).get(card_id) if isinstance(d, dict) else None
        return {"turns": turns if isinstance(turns, list) else []}
    d = common.read_json(CHAT_JSON, None)
    return d if isinstance(d, dict) and isinstance(d.get("turns"), list) else {"turns": []}


def box_turns(turns):
    """The box's own turns: none typed on a card."""
    return [t for t in turns if not t.get("card")]


def for_page():
    """The short running conversation the page shows: the box's own."""
    return {"turns": [{k: t.get(k) for k in ("who", "text", "source", "at", "change", "scan", "desktop", "cards") if k not in ("change", "scan", "desktop", "cards") or t.get(k)}
                      for t in box_turns(load()["turns"])[-SHOW_TURNS:]]}


def _add(turn):
    with _lock:
        cid = (turn.get("card") or {}).get("id") if isinstance(turn.get("card"), dict) else None
        if cid:         # a card's turn: that card's own conversation
            d = common.read_json(CARD_TALK, None)
            d = d if isinstance(d, dict) and isinstance(d.get("cards"), dict) else {"cards": {}}
            cards = d["cards"]
            cards[cid] = ((cards.get(cid) if isinstance(cards.get(cid), list) else []) + [turn])[-KEEP_CARD_TURNS:]
            d["cards"] = dict(sorted(cards.items(), key=lambda kv: str((kv[1][-1] if kv[1] else {}).get("at") or ""))[-KEEP_CARDS:])
            common.write_json(CARD_TALK, d)
            return
        d = load()
        d["turns"] = (d["turns"] + [turn])[-KEEP_TURNS:]
        common.write_json(CHAT_JSON, d)


def note_exchange(text, said, card, at=None):
    """Words typed on a card that the program answered itself (a rule proposed from them): both turns go into that card's
    own conversation, as a card reply's do."""
    about = {"id": card.get("id"), "title": str(card.get("short_header") or card.get("title") or "")[:200]} if card else None
    now = common.now().isoformat(timespec="seconds")
    _add({k: v for k, v in {"who": "you", "text": (text or "").strip()[:3000], "at": at or now, "card": about}.items() if v})
    _add({k: v for k, v in {"who": "assistant", "text": said, "at": now, "card": about}.items() if v})


def _words(text):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9'\-]{2,}", (text or "").lower()) if w not in SMALL]


# --- what the assistant holds that may bear on the words ------------------------------------------------
def found_for(text, turns, card=None):
    """A small pile of the owner's own data that the words may be about. Never waits long on anything."""
    words = set(_words(text))
    leans = re.search(r"\b(it|that|this|those|them|there|one|same)\b", (text or "").lower())
    if len(words) < 3 or leans:                      # "and tomorrow?", "what about it?" lean on what was just said
        for t in turns[-3:]:
            words |= set(_words(t.get("text")))
    out = {}
    items = (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or []
    scored = []
    for it in items:
        if it.get("state") == "done":
            continue
        hay = " ".join(str(it.get(k) or "") for k in ("id", "title", "detail", "source_who", "source_ref", "area", "status",
                                                      "recommended", "answer", "assistant_did")).lower()
        n = sum(1 for w in words if w in hay)
        if n:
            scored.append((n, it))
    scored.sort(key=lambda s: (-s[0], str(s[1].get("source_when") or "")), reverse=False)
    out["items_on_the_page"] = [{"id": it["id"], "title": it.get("title"), "where_it_stands": it.get("state"),
                                 "status": it.get("status"), "from": it.get("source_ref") or it.get("source_who"),
                                 "story": (it.get("detail") or "")[:500], "asks": it.get("asks") or [],
                                 "recommended": it.get("recommended"), "your_answer": it.get("answer"),
                                 "already_done": (it.get("assistant_did") or "")[-300:] or None, "due": it.get("due_date")}
                                for _n, it in scored[:8]]
    out["open_items_in_all"] = sum(1 for it in items if it.get("state") != "done")
    # only the open cards whose words best match: to count or list cards, or find a closed one, the chat asks for the cards
    # search (its cards ACTION, card_search.py), which reads every card, open and closed
    out["items_on_the_page_are"] = f"the {len(scored[:8])} open card(s) whose words best match; the cards ACTION searches every card"
    out["emails_sent_lately"] = sent_lately()       # what really went out: read before saying anything about sending
    out["waiting_in_ready_to_send"] = [{"id": it["id"], "subject": (it.get("draft") or {}).get("subject") or it.get("title"),
                                        "to": (it.get("draft") or {}).get("to") or []}
                                       for it in items if isinstance(it.get("ready"), dict) and it.get("state") != "done"]
    try:        # the people named, from his contacts and the names his mail gives them (people.py): never ask him for these
        import people
        out["people_on_file"] = people.held_for(card or {"asks": [], "assistant_did": ""}, text)
        out["addresses_on_file_for_the_names_here"] = people.for_prompt(text)
    except Exception:  # noqa: BLE001
        out["people_on_file"] = []
    today = common.read_json(os.path.join(common.HOME, "today.json"), {}) or {}
    out["calendar_today_and_tomorrow"] = today.get("days") or []
    if re.search(r"calendar|schedul|meeting|appointment|event|lunch|dinner|call\b|book|cancel|move|tomorrow|monday|tuesday|wednesday|"
                 r"thursday|friday|saturday|sunday|\d{1,2}/\d{1,2}|\b\d{1,2}(:\d\d)?\s*(am|pm)\b", (text or "").lower()):
        try:        # the calendars an event can go on, by name (calendar_view.py); the first named "main" when no name is said
            import calendar_view
            cals = calendar_view.writable()
            main = calendar_view.default_calendar()
            out["calendars_you_can_change"] = [c["name"] + (" (main)" if main and c is main else "") for c in cals]
        except Exception:  # noqa: BLE001
            pass
    health = common.read_json(common.HEALTH_JSON, {}) or {}
    out["last_gathered"] = (health.get("last_pass") or {}).get("started")
    out["today_is"] = common.now().strftime("%A %m/%d/%Y %I:%M %p")
    out["mail_and_messages"] = _messages(words)
    try:        # how he writes email, texts and to the people named: every draft is written in it (voice.py)
        import voice
        out["how_the_owner_writes_draft_in_this"] = voice.for_chat(text)
    except Exception:  # noqa: BLE001
        pass
    try:        # his text conversations, when the words are about texts or name someone he texts (texts.py)
        import texts
        got = texts.for_chat(words, text)
        if got:
            out["text_conversations"] = got
            out["text_drafts"] = [{k: d.get(k) for k in ("id", "conv", "name", "text")} for d in texts._drafts()][-10:]
            out["texts_waiting_to_go"] = [{k: q.get(k) for k in ("id", "conv", "name", "text")} for q in texts._outbox()
                                          if q.get("status") in ("queued", "failed")][-10:]
    except Exception:  # noqa: BLE001  texts never stop an answer
        pass
    low = (text or "").lower()
    if re.search(r"folder|label|organi[sz]|move|file (it|them|these)|sort|tidy|clean", low):
        try:        # each mailbox's folders and labels, by path, for moving mail and changing folders (mail.folders)
            import mail
            out["mail_folders"] = [{"account": a["address"], "folders": [f["path"] for f in a["folders"]][:200]}
                                   for a in mail.folders().get("accounts", [])]
        except Exception:  # noqa: BLE001
            pass
    if re.search(r"roadmap|check|works|doesn'?t work|question|project|session|note on", low):
        try:        # the roadmaps on the page (rows, checks, open questions) and the projects Settings, Tools offers
            out["roadmaps"] = roadmaps_for_chat()
            import project_tools
            out["projects"] = [{"folder": p["folder"], "name": p["name"], "roadmap_on": p["roadmap"], "questions_on": p["questions"],
                                "sessions": [{"session": s["id"], "name": s["name"]} for s in p["sessions"]]} for p in project_tools.projects()][:30]
        except Exception:  # noqa: BLE001
            pass
    return out


def sent_lately(days=2, most=20):
    """The emails sent in the last days, newest first, from the send log: when, from, to, subject, and whether it went."""
    import send
    cut = (common.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    got = []
    try:
        with open(send.SENT_LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if str(r.get("at") or "") >= cut and (r.get("channel") or "email") == "email":
                    got.append({"at": r.get("at"), "from": r.get("account"), "to": r.get("to"), "subject": r.get("subject"),
                                "went": r.get("result") == "sent", "card": r.get("item")})
    except OSError:
        return []
    return got[::-1][:most]


def _messages(words):
    """Newest messages that mention the words. The database may be held by a pass; then say so rather than wait."""
    import answers
    picks = sorted((w for w in words if len(w) >= 4), key=len, reverse=True)[:4]
    if not picks:
        return []
    con = None
    for _ in range(8):                               # about two seconds at most
        con = answers._connect()
        if con is not None:
            break
        time.sleep(0.25)
    if con is None:
        return "the mail search could not be reached this minute"
    try:
        like = " OR ".join("(lower(coalesce(m.subject,'')) LIKE ? OR lower(coalesce(m.body,'')) LIKE ?)" for _ in picks)
        args = [x for w in picks for x in (f"%{w}%", f"%{w}%")]
        rows = con.execute(
            f"""SELECT m.ts, m.channel, m.direction, coalesce(c.name, m.from_key), m.subject, substr(coalesce(m.body, ''), 1, 500),
                       m.id, m.account, (SELECT string_agg(a.original_filename || ' = att:' || a.id, ' | ') FROM attachments a WHERE a.message_id = m.id)
                FROM messages m LEFT JOIN contacts c ON c.key = m.from_key
                WHERE ({like}) ORDER BY m.ts DESC LIMIT 6""", args).fetchall()
    except Exception as e:  # noqa: BLE001
        return f"the mail search failed this minute ({type(e).__name__})"
    finally:
        con.close()
    return [dict({"message": mid, "when": ts.strftime("%m/%d/%Y %I:%M %p") if ts else None, "by": ch,
                  "from": "you" if direction == "out" else who, "subject": subj, "text": " ".join((body or "").split())},
                 **({"to_your_address": acct, "attachments": files.split(" | ")} if ch == "email" and files else
                    {"to_your_address": acct} if ch == "email" else {}))
            for ts, ch, direction, who, subj, body, mid, acct, files in rows]


def card_emails(card):
    """The emails behind a card, by number, so a reply or forward can name the one it answers or forwards."""
    ids = [int(x) for x in (card.get("source_messages") or []) if str(x).isdigit()][-6:]
    if not ids:
        return []
    import answers
    con = answers._connect()
    if con is None:
        return []
    try:
        rows = con.execute("SELECT m.id, m.ts, m.from_key, m.subject, m.account, (SELECT string_agg(a.original_filename, ' | ') FROM attachments a"
                           " WHERE a.message_id = m.id) FROM messages m WHERE m.channel = 'email' AND m.id IN (" + ",".join("?" for _ in ids) + ")"
                           " ORDER BY m.ts", ids).fetchall()
    except Exception:  # noqa: BLE001  the card's other facts still go
        return []
    finally:
        con.close()
    return [{"message": mid, "when": ts.strftime("%m/%d/%Y %I:%M %p") if ts else None, "from": str(frm or "").split(":", 1)[-1],
             "subject": subj, "to_your_address": acct, "attachments": files.split(" | ") if files else []}
            for mid, ts, frm, subj, acct, files in rows]


def about_me():
    """Plain facts about the assistant as it stands this minute, for questions about itself."""
    me = common.personal()
    health = common.read_json(common.HEALTH_JSON, {}) or {}
    items = (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or []
    out = {"gathers_from": me.get("sources") or [], "gathers_every": "15 minutes",
           "last_gathered": (health.get("last_pass") or {}).get("started"),
           "problems_right_now": health.get("problems") or [],
           "open_items_on_the_page": sum(1 for i in items if i.get("state") != "done"),
           "this_box_is_answered_by": f"a short hidden run of Claude ({MODEL}) started on the owner's computer for each message",
           "phone_alerts": "on" if ((common.settings().get("alerts") or {}).get("topic") or "").strip() else "off (no notification channel is set)"}
    try:        # what was kept off the page today and why, and the owner's own rules (held.py, filters.py)
        import filters
        held = common.read_json(os.path.join(common.HOME, "held.json"), {}) or {}
        today = (held.get("days") or [{}])[0]
        out["held_back_today"] = {"count": today.get("count") or 0,
                                  "rows": [{k: r.get(k) for k in ("key", "who", "what", "at", "why")} for r in (today.get("rows") or [])[:40]]}
        out["held_back_last_7_days"] = {d.get("date"): d.get("count") for d in held.get("days") or []}
        out["the_owners_rules"] = [{"rule": r["text"], "kind": "show less" if r["way"] == "show_less" else "always show",
                                    "on": bool(r.get("on", True)), "made": str(r.get("made") or "")[:10], "from": r.get("from")}
                                   for r in filters.rules()]
        f = filters.get()
        out["filter_settings"] = {k: f[k] for k in ("strict", "nothing_needed", "first_time", "newsletters", "kept_mailings", "notices",
                                                    "copied_only", "unknown_texts", "short_texts", "waiting_back_days", "old_card_days")}
        out["people_who_always_get_through"] = f["always_through"]
        import standing
        out["standing_approvals"] = [{"does": e["label"], "in_area": e["area"], "level": {"tell": "do it and notify me", "quiet": "do it quietly"}.get(e["level"], "ask first"),
                                      "on": e["on"], "used": e["used"]} for e in standing.for_page()]
        feed = common.read_json(standing.FEED, {}) or {}
        out["done_for_them_today_by_standing_approval"] = feed.get("today") or 0
    except Exception:  # noqa: BLE001
        pass
    try:        # where the page can be opened (never its password or a key)
        import settings_page
        out["the_page_can_be_opened_at"] = settings_page.for_page()["pc_only"]["lives"]
    except Exception:  # noqa: BLE001
        pass
    return out


# --- doing the things the words ask for -------------------------------------------------------------------
MOST_ACTIONS = 8         # ACTION lines acted on from one reply
TASK_KEY = "chat"        # tasks kept from the box are named <TASK_KEY>:<when>[-n]


_batch = [""]           # the reply being acted on: drafts written in one reply share it, for Send all
CLAIM = re.compile(r"\b(i'?ve|i have|i|they'?re|they are|it'?s|it is|emails? (is|are)|drafts? (is|are))\b[^.?!]*\b(put|placed|added|made|drafted|written|wrote|waiting|in|on)\b[^.?!]*"
                   r"(ready to send|drafts|your page)", re.I)
NOT = re.compile(r"\b(can'?t|cannot|couldn'?t|not|haven'?t|didn'?t|won'?t|no|nothing|unable|if|will|would|could|can|shall|when|once|tell me|ask)\b|'ll\b", re.I)   # a promise or a condition is not a claim


def claims_draft(said):
    """True when a sentence of the reply says an email was put on the page (Ready to send), and does not say it was not."""
    for sentence in re.split(r"(?<=[.?!])\s+", str(said or "")):
        if CLAIM.search(sentence) and not NOT.search(sentence):
            return True
    return False


def items_mod():
    import items
    return items


def _do_all(actions, text, when, first=0):
    """Every ACTION line of one reply, in order. One that cannot be read or fails never stops the others.
    Returns (items changed, a line to add to the reply or '')."""
    changed, extras = {}, []
    for n, action in enumerate(actions[:MOST_ACTIONS], first):
        if not isinstance(action, dict):
            extras.append("One of the things you asked for could not be read, so I skipped it.")
            continue
        try:
            got, extra = _do(action, text, when, n)
        except Exception as e:  # noqa: BLE001
            got, extra = [], "One of the things you asked for failed, so I left it unchanged."
            common.log_line(os.path.join(common.LOGS, "errors.log"), f"chat: {type(e).__name__}: {e}")
        for it in got or []:
            changed[it.get("id")] = it
        if extra:
            extras.append(extra)
    if len(actions) > MOST_ACTIONS:
        extras.append(f"I did the first {MOST_ACTIONS} things you asked for; tell me the rest again.")
    return list(changed.values()), " ".join(extras)


def _do(action, text, when, n=0):
    """One ACTION line; n is its place in the reply. Returns (items changed, a line to add to the reply or '')."""
    import answers
    kind = (action or {}).get("type")
    if kind == "item":
        iid, do = str(action.get("id") or ""), str(action.get("do") or "")
        snap = (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or []
        if do not in ("done", "not_mine", "later", "note") or not any(i.get("id") == iid for i in snap):
            return [], "I could not tell which item you meant, so I left that one alone."
        rec = {"id": iid, "at": when.isoformat(timespec="seconds"), "text": str(action.get("text") or ""), "label": "Direct",
               "origin": "chat"}       # never a Send press: the box cannot send
        rec.update({"done": {"action": "done"}, "not_mine": {"action": "not_mine"},
                    "later": {"action": "note", "page_action": "later"}, "note": {"action": "note"}}[do])
        out = answers.act_on_answer(rec)
        return (out.get("items") or []), ("" if out.get("ok") else "That did not go through: " + str(out.get("error")))
    if kind == "rule":         # his correction of how cards are written or handled: a card of its own, saved on his Approve there
        return _asked(text, action.get("text"), "rule", when, n)
    if kind == "draft":        # an email the chat wrote: a card in Ready to send; sent only by a send ACTION on his words
        import ready
        if action.get("attach_paths"):      # files from his computer that his own words name: kept like a file he adds on the page
            got, why = _files_from_paths(action.get("attach_paths"), text)
            if why:
                return [], why
            action = dict(action, files=list(action.get("files") or []) + got)
        iid, said = ready.make(action, when, n, _batch[0])
        if not iid:
            return [], said
        _made_now.append(iid)
        item = items_mod().card_for(iid)
        if item is None:
            return [], ""
        answers._patch_snapshot([item])
        return [item], ""
    if kind == "text_draft":   # a text the chat wrote: kept in the Texts part to edit and send there; never sent from here
        import texts
        return [], texts.draft(action.get("conversation"), action.get("to"), action.get("name"), action.get("text"), action.get("why"))
    if kind == "task":
        import items
        title = " ".join(str(action.get("title") or "").split())
        if not title:
            return [], ""
        due = None
        try:
            due = dt.date.fromisoformat(str(action.get("due"))) if action.get("due") else None
        except ValueError:
            pass
        for _ in range(40):                          # a pass may hold the database for a moment
            con = answers._connect()
            if con is not None:
                con.close()
                break
            time.sleep(0.5)
        else:
            return [], "I could not put it on your page just now; tell me again in a minute."
        key = f"{TASK_KEY}:{when:%Y%m%d-%H%M%S}" + (f"-{n}" if n else "")      # two tasks in one reply stay two
        iid, _ = items.upsert(key, "chat", kind="task", area="From you", state="yours", title=title,
                              detail=" ".join(str(action.get("detail") or "").split()) or None, due_date=due,
                              source_who=common.owner(), source_when=when,
                              source_ref=f"You told me, {when.month}/{when.day} {when.strftime('%I:%M %p').lstrip('0')}")
        item = items.card_for(iid)
        if item is None:
            return [], ""
        answers._patch_snapshot([item])
        return [item], ""
    if kind in ("change_start", "change_agree"):    # a change to how it works: a card of its own, made on his Approve there
        return _change_action(kind, action, text, when, n)
    if kind in ("mail_plan", "mail_go", "mail_folder"):     # mail handled in bulk, and folders: planned and shown first, done only on the owner's yes (mail_handle.py)
        import mail_handle
        mail_handle.done_now[0] = False
        line = mail_handle.chat_action(action, when, text)
        if mail_handle.done_now[0]:     # one email, done at once: the program's line says what was done
            _sent_now.append({"what": "mail", "ok": True})
        return [], line
    if kind == "calendar":     # add, change or take off an event, on his own words (calendar_view.py, the page's Calendar code)
        return [], _calendar(action, text)
    if kind == "send":         # an email the assistant wrote, sent on his own words by the page's own Send code (send.py)
        return _send(action, text, when)
    if kind == "text_send":    # a text sent on his own words by the Texts part's own Send code (texts.queue_send)
        return [], _text_send(action, text)
    if kind == "press":        # one of a card's own buttons, pressed for him (answers.act_on_answer, as the page's press)
        return _press(action, when)
    if kind == "page":         # one of the page's own tool buttons (Refresh mail, Learn style now, Reload all email history)
        return _page_button(action, when, text)
    if kind == "cards":        # a search of every card (card_search.py): in the box it runs the chat again with what was found
        import card_search
        got = card_search.for_action(action)
        return [], (f"{got['count']} card(s) found ({got['open']} open, {got['closed']} closed): "
                    + ", ".join(f"{c['id']} {c['header']}" for c in got["cards"][:10]))[:900]
    if kind == "cards_done":   # every open card on a topic closed as done, and the list of what was closed (spec 1.3)
        return _cards_done(action, text, when)
    if kind == "mail":         # one email's own buttons: label, mark read or unread, star, archive, delete (mail.act, as pressed)
        return _mail_press(action, when)
    if kind == "text":         # the Texts part's own presses: mark read, take back a text waiting to go, throw away a text draft
        return [], _text_press(action)
    if kind == "signature":    # an account's email signature, as the writing screen saves it (mail_compose.set_signature)
        return [], _signature(action)
    if kind == "roadmap":      # a mark, an answer or a note on a project's roadmap shown on the page (roadmap_press.handle)
        return [], _roadmap(action, when) if text else "A roadmap press goes only on your own words, so nothing was sent to it."
    if kind == "project_tool":  # Settings, Tools: turn a project's roadmap or questions file on or off (project_tools.handle)
        return [], _project_tool(action, when) if text else "That goes only on your own words, so nothing was changed."
    import mods
    said = mods.chat_action(action, when)          # an action one of the owner's mods carries out
    return [], said or ""


_made_now = []          # the Ready to send cards drafted in this message: "send" with no id sends these
_sent_now = []          # what this message really sent or changed: {"what": "email" | "text" | "calendar" | "mail", "ok": bool}
# his words that ask for a calendar change, and words that put it off or only ask about it (rule B11)
CAL_WORDS = {"add": r"\b(add|put|schedule|book|set up|block( out| off)?|calendar)\b",
             "change": r"\b(move|change|reschedule|push|shift|rename|make it|switch|instead)\b",
             "delete": r"\b(cancel|delete|remove|clear|take\b[^.!?]{0,40}\boff)\b"}
CAL_NOT = r"\b(don'?t|do not|never|not yet|hold off|should i|should we|whether)\b|\b(did|has|have|had|does|is|was)\b[^.!?]{0,30}\b(cancell?ed|moved|added)\b"
_typed = [None]         # when the owner typed this message (the page's own time): his words are the authority only while fresh
PRESSES_FOR_HIM = ("done", "got_it", "later", "bring_back", "junk", "never_junk", "undo", "not_needed", "always_show", "wait_longer",
                   "write_them", "drop", "old_keep", "read", "discard", "should_have_seen")  # never a yes he gives only on a card (standing, write, rule_offer)
PAGE_BUTTONS = {"refresh_mail": ("mail-pull:", "Refresh mail"), "learn_voice": ("voice-learn", "Learn style now"),
                "reload_mail_history": ("mail-reload", "Reload all email history"),
                "rebuild_cards": ("rebuild", json.dumps({"rebuild": "start"})), "rebuild_put_back": ("rebuild", json.dumps({"rebuild": "put_back"}))}
PAGE_WORDS = {"rebuild_cards": r"\brebuild", "rebuild_put_back": r"\b(put\b[^.!?]{0,30}\bback|undo|take\b[^.!?]{0,30}\bback)\b"}   # his words needed for these
MAIL_ACTS = ("label", "unlabel", "read", "unread", "star", "unstar", "archive", "trash", "restore")
NO_READ = re.compile(r"(^|[\\/])(personal[\\/](local_settings|settings)\.json|personal[\\/]keys\.dat|Resources[\\/]Database|page_state|sent)([\\/]|$)", re.I)


def _his_words_refuse(text, want=None, not_words=None):
    """'' when the owner's own words of this message ask for it (rule B11), else the plain reason."""
    return common.rulebook().said_refusal(text, _typed[0], common.now().isoformat(timespec="seconds"), None, want,
                                          not_words).replace("the owner's", "your")


def _calendar(action, text):
    """{"type": "calendar", "do": "add" | "change" | "delete", ...}: done by the page's own calendar code on his words."""
    import calendar_view
    do = str(action.get("do") or "").lower()
    if do not in ("add", "change", "delete"):
        return "I could not tell what to do on your calendar, so nothing was changed."
    why = _his_words_refuse(text, CAL_WORDS[do], CAL_NOT)
    if why:
        return f"Nothing was changed on your calendar: {why}. Tell me plainly to do it."
    body = {k: action.get(k) for k in ("title", "calendar", "day", "all_day", "start", "end", "place", "notes", "find", "on_day") if k in action}
    if do == "add":
        out = calendar_view.add(dict(body, default_ok=True))
    elif do == "change":
        out = calendar_view.change(body)
    else:
        out = calendar_view.delete(body)
    _sent_now.append({"what": "calendar", "ok": bool(out.get("ok")), "do": do, "id": (out.get("event") or {}).get("id")})
    return calendar_view.said(out, do)


DONE_WORDS = r"\b(close|done|finish|finished|clear|mark|complete|completed|dismiss|wrap)\b"


def _cards_done(action, text, when):
    """{"type": "cards_done", "words": "the topic", "kind", "button", "ids": [...]}: every open card the search finds (card_search.py,
    every card) or the ids name is closed as done by Done's own code, and the reply lists each card closed. On his own words."""
    import answers
    import card_search
    why = _his_words_refuse(text, DONE_WORDS, CAL_NOT)
    if why:
        return [], f"No card was closed: {why}. Tell me plainly to close them."
    ids = [str(i) for i in action.get("ids") or [] if str(i or "").strip()]
    words, kind, button = str(action.get("words") or ""), str(action.get("kind") or ""), str(action.get("button") or "")
    if not ids and not (words.strip() or kind.strip() or button.strip()):
        return [], "I could not tell which cards you meant, so I closed none."
    found = card_search.search(words, kind, button, "open", 200)["cards"] if (words.strip() or kind.strip() or button.strip()) else []
    if ids:
        snap = {i.get("id"): i for i in (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or []}
        found = [c for c in found if c["id"] in ids] if found else \
            [{"id": i, "header": (snap.get(i) or {}).get("header") or (snap.get(i) or {}).get("title")} for i in ids if i in snap]
    if not found:
        return [], "I found no open card like that, so I closed none."
    changed, closed, failed = {}, [], []
    for c in found:
        rec = {"id": c["id"], "at": when.isoformat(timespec="seconds"), "text": "", "label": "Done", "origin": "chat", "action": "done"}
        try:
            out = answers.act_on_answer(rec)
        except Exception as e:  # noqa: BLE001  one card that fails never stops the rest
            out = {"ok": False, "error": type(e).__name__}
        if out.get("ok"):
            closed.append(c)
            for it in out.get("items") or []:
                changed[it.get("id")] = it
        else:
            failed.append(c)
    _sent_now.append({"what": "cards", "ok": bool(closed)})
    line = f"Closed {len(closed)} card{'s' if len(closed) != 1 else ''} as done" + (": " + "; ".join(
        f"{c.get('header') or c['id']}" for c in closed) if closed else "") + "."
    if failed:
        line += f" {len(failed)} could not be closed: " + "; ".join(str(c.get("header") or c["id"]) for c in failed) + "."
    return list(changed.values()), line[:2000]


def _ready_card(iid):
    snap = (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or []
    card = next((i for i in snap if i.get("id") == iid), None)
    if card is None:
        card = items_mod().card_for(iid)
    return card


def _send(action, text, when):
    """{"type": "send", "id": "<a card in Drafts>"} or {"type": "send"} for the emails drafted earlier in this same reply. Each goes
    through the page's own Send code (answers._owner_send, send.py) with his words as its authority; nothing goes without them."""
    import answers
    import ready
    iid = str(action.get("id") or "").strip()
    ids = [iid] if iid else list(_made_now)
    if not ids:
        return [], "I could not tell which email to send, so nothing was sent."
    why = _his_words_refuse(text)
    if why:
        return [], f"Nothing was sent: {why}. Say \"send it\" when you want it to go."
    changed, lines = [], []
    for one in ids[:8]:
        card = _ready_card(one)
        d = (card or {}).get("draft") if isinstance((card or {}).get("draft"), dict) else None
        if not card or not str(card.get("source_key") or "").startswith(ready.KEY) or not d or card.get("state") == "done":
            lines.append("That email is not waiting in Drafts (it was already sent or put away), so nothing was sent.")
            continue
        src = d.get("source") if isinstance(d.get("source"), dict) else None
        kind = d.get("type") if d.get("type") in ("new", "reply", "reply_all", "forward") and (src or d.get("type") == "new") else "new"
        files = [{"name": f.get("name"), "ref": f.get("ref")} for f in d.get("files") or [] if isinstance(f, dict) and f.get("ref")]
        names = [f["name"] for f in files] + [n for n in d.get("attach") or [] if n not in [f["name"] for f in files]]
        p = {"account": d.get("account") or "", "to": list(d.get("to") or []), "cc": list(d.get("cc") or []), "bcc": list(d.get("bcc") or []),
             "subject": str(d.get("subject") or "").strip(), "body": str(d.get("body") or ""), "type": kind,
             "source": src.get("message") if src and kind != "new" else None, "files": files, "attach": names}
        p["shown"] = {"account": p["account"], "to": p["to"], "cc": p["cc"], "bcc": p["bcc"], "type": kind, "attach": names}
        rec = {"id": one, "action": "answer", "origin": "chat", "label": "Talk to your assistant", "at": when.isoformat(timespec="seconds"),
               "said": {"words": text, "at": _typed[0] or when.isoformat(timespec="seconds")}, "text": json.dumps({"send_email": p})}
        out = answers._owner_send(rec)
        changed += out.get("items") or []
        _sent_now.append({"what": "email", "ok": bool(out.get("sent")), "id": one})
        lines.append(str(out.get("result") or ""))
        if out.get("sent"):
            body = " ".join(p["body"].split())
            lines.append(f"What went: \"{body[:400]}{'...' if len(body) > 400 else ''}\"" + (f" With: {', '.join(names)}." if names else ""))
    return changed, " ".join(x for x in lines if x)


def _text_send(action, text):
    """{"type": "text_send", "conversation", "to", "text"}: queued by the Texts part's own Send code, on his words."""
    import texts
    words = str(action.get("text") or "").strip()
    if not words:
        return "I could not tell what the text should say, so nothing was sent."
    why = _his_words_refuse(text)
    if why:
        return f"Nothing was sent: {why}. Say \"send it\" when you want it to go."
    out = texts.queue_send(action.get("conversation"), words, action.get("to"), action.get("name"), learn=False)
    _sent_now.append({"what": "text", "ok": bool(out.get("ok"))})
    if not out.get("ok"):
        return "The text was not sent: " + str(out.get("error") or ("your texts are busy this moment; ask again in a minute" if out.get("busy") else "it was refused"))
    q = next((s for s in texts._outbox() if s.get("id") == out.get("id")), {})
    who = " ".join(x for x in (q.get("name") or str(action.get("to") or ""), f"({texts._pretty(q['phone'])})" if q.get("phone") else "") if x)
    return (f"Sending from your phone, through Google Messages, to {who or 'that conversation'}: \"{words.rstrip('.')}.\" "
            "It shows under Texts as sent once your phone has sent it.")


def _press(action, when):
    """{"type": "press", "id": "<card>", "name": "<one of the card's own buttons>", ...}: the press, as the page sends it."""
    import answers
    iid, name = str(action.get("id") or ""), str(action.get("name") or "")
    import held
    if name not in PRESSES_FOR_HIM:
        return [], "That one is yours to press on the card itself, so nothing was changed."
    if name == "should_have_seen" or held.KEY.match(iid):       # a row of the Hidden list: its own press (answers._held_press)
        if name not in ("should_have_seen", "read") or not held.KEY.match(iid):
            return [], "I could not tell which hidden message you meant, so nothing was changed."
    else:
        snap = (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or []
        if not any(i.get("id") == iid for i in snap):
            return [], "I could not tell which card you meant, so I left it alone."
    press = {"name": name}
    for k in ("when", "until", "scope", "days", "part", "words"):
        if action.get(k) not in (None, ""):
            press[k] = action[k]
    out = answers.act_on_answer({"id": iid, "action": "answer", "text": json.dumps({"press": press}), "label": "Talk to your assistant",
                                 "at": when.isoformat(timespec="seconds"), "origin": "chat"})
    if not out.get("ok"):
        return (out.get("items") or []), "That did not go through: " + str(out.get("error"))
    happened = [str((i.get("last_press") or {}).get("happened") or "") for i in out.get("items") or [] if isinstance(i.get("last_press"), dict)]
    return (out.get("items") or []), next((h for h in happened if h), str(out.get("result") or ""))


def _page_button(action, when, text=""):
    """{"type": "page", "do": "refresh_mail" | "learn_voice" | "reload_mail_history"}: the page's own button, pressed for him."""
    import answers
    do = str(action.get("do") or "")
    got = PAGE_BUTTONS.get(do)
    if not got:
        return [], "That button is not one I can press for you."
    if do in PAGE_WORDS:        # rebuilding every card, or putting them back, only on his own words for it
        why = _his_words_refuse(text, PAGE_WORDS[do], CAL_NOT)
        if why:
            return [], f"Nothing was changed: {why}."
    key = got[0] + (f"{when:%Y%m%d%H%M%S}" if got[0].endswith(":") else "")
    out = answers.act_on_answer({"id": key, "action": "answer", "text": got[1], "at": when.isoformat(timespec="seconds"), "origin": "chat"})
    return (out.get("items") or []), str(out.get("result") or out.get("error") or "")


def _files_from_paths(paths, text):
    """([{"name", "ref", "size"}], '') for files on his computer that his own words in this message name by path, kept the way a
    file he adds on the page is kept (mail.upload); or ([], the plain reason). Never a file of the assistant's own keys,
    settings, database or page state."""
    import mail
    out = []
    said = str(text or "").replace("/", "\\").lower()
    for p in [str(x or "").strip().strip('"') for x in (paths if isinstance(paths, list) else [paths])][:10]:
        if not p:
            continue
        full = os.path.abspath(os.path.expanduser(p))
        if p.replace("/", "\\").lower() not in said and full.lower() not in said:
            return [], f"I attach only a file your own words name by its place on your computer, so I did not use {os.path.basename(p)}."
        if NO_READ.search(full) or os.path.abspath(full).lower().startswith(os.path.abspath(common.PERSONAL).lower()):
            return [], "That file is one of my own private files, so I didn't attach it."
        if not os.path.isfile(full):
            return [], f"There is no file at {p}, so the email was not written. Check the place and tell me again."
        try:
            with open(full, "rb") as f:
                data = f.read(mail.MOST_UPLOAD + 1)
            out.append(mail.upload(os.path.basename(full), data))
        except (OSError, ValueError) as e:
            return [], f"{os.path.basename(full)} could not be attached: {e}"
    return out, ""


def _mail_press(action, when):
    """{"type": "mail", "do": "label | unlabel | read | unread | star | unstar | archive | trash | restore", "message": <number>,
    "label": "..."}: the email's own button, through the same press code (answers.act_on_answer, mail.act)."""
    import answers
    do, mid = str(action.get("do") or ""), str(action.get("message") or "").lstrip("#")
    if do not in MAIL_ACTS or not mid.isdigit():
        return [], "I could not tell which email or what to do with it, so nothing was changed."
    act = {"message": int(mid), "act": do}
    if do in ("label", "unlabel"):
        act["label"] = str(action.get("label") or "").strip()[:100]
    if do == "restore":
        act["label"] = str(action.get("from") or "archive")
    out = answers.act_on_answer({"id": f"mail:chat-{when:%Y%m%d%H%M%S%f}", "action": "answer", "text": json.dumps({"mail_act": act}),
                                 "at": when.isoformat(timespec="seconds"), "origin": "chat", "label": "Talk to your assistant"})
    return (out.get("items") or []), str(out.get("result") or out.get("error") or "")


def _text_press(action):
    """{"type": "text", "do": "read | cancel | discard", "conversation" | "id"}: the Texts part's own presses."""
    import texts
    do = str(action.get("do") or "")
    try:
        if do == "read" and action.get("conversation"):
            texts.mark_read(str(action["conversation"]))
            return "Marked read."
        if do == "cancel" and action.get("id"):
            out = texts.cancel(str(action["id"]))
            return "I took that text back, so it won't be sent." if out.get("ok") else str(out.get("error"))
        if do == "discard" and action.get("id"):
            if not any(d.get("id") == str(action["id"]) for d in texts._drafts()):
                return "I could not find that text draft, so nothing was thrown away."
            texts.discard_draft(str(action["id"]))
            return "I threw away that text draft."
    except texts.Busy:
        return "Your texts are busy this moment; ask again in a minute."
    return "I could not tell which text or what to do with it, so nothing was changed."


def _signature(action):
    """{"type": "signature", "account": "...", "text": "the signature's words, or empty to remove it"}."""
    import html as html_mod
    import mail_compose
    words = str(action.get("text") or "").strip()
    body = "<div>" + html_mod.escape(words).replace("\n", "<br>") + "</div>" if words else ""
    out = mail_compose.set_signature(action.get("account"), body)
    if not out.get("ok"):
        return str(out.get("error"))
    return (f"Your signature for {str(action.get('account') or '').strip().lower()} is now: \"{words}\"." if words
            else f"The signature for {str(action.get('account') or '').strip().lower()} is removed.")


def _roadmaps_path():
    page = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "live_page")
    if page not in sys.path:
        sys.path.insert(0, page)


def roadmaps_for_chat():
    """The roadmaps shown on the page, as the chat needs them to press for him: rows with their checks, open questions."""
    _roadmaps_path()
    import roadmaps
    out = []
    for doc in roadmaps.full_docs().values():
        rows = []
        for rid, r in (doc.get("steps") or {}).items():
            rows.append({"row": rid, "name": r.get("name"), "status": r.get("status"),
                         "checks": [{"check": c.get("id"), "text": c.get("text")} for c in r.get("checks") or [] if isinstance(c, dict)]})
        qs = [{"question": qid, "row": q.get("row"), "topic": q.get("topic"), "asks": q.get("question"), "choices": q.get("choices") or []}
              for qid, q in (doc.get("questions") or {}).items() if q.get("status") == "open"]
        out.append({"project": doc.get("key"), "name": doc.get("name"), "rows": rows[:80], "open_questions": qs[:30]})
    return out


def _roadmap(action, when):
    """{"type": "roadmap", "project": <key>, "do": "works | fails | clear | note | answer", "row", "check", "note", "question",
    "choice": "a", "text"}: built into the press the roadmap's own page would send (its database contract) and passed to the
    project's own session by the page's press code (roadmap_press.handle)."""
    _roadmaps_path()
    import roadmap_press
    import roadmaps
    key, do = str(action.get("project") or ""), str(action.get("do") or "")
    doc = roadmaps.full_docs().get("roadmap-" + key)
    if not doc:
        return "I could not tell which project's roadmap you meant, so nothing was sent to it."
    now = when.strftime("%Y-%m-%dT%H:%M")
    row, words = str(action.get("row") or ""), " ".join(str(action.get("note") or action.get("text") or "").split())[:4000]
    if do in ("works", "fails", "clear"):
        step = (doc.get("steps") or {}).get(row) or {}
        chk = next((c for c in step.get("checks") or [] if isinstance(c, dict) and c.get("id") == action.get("check")), None)
        if not chk:
            return "I could not find that check on the roadmap, so nothing was sent to it."
        path = f"marks/{row}--{chk['id']}"
        op, data = ("delete", {}) if do == "clear" else ("set", {"row": row, "check": chk["id"], "text": chk.get("text") or "",
                                                                 "result": do, "note": words, "marked": now})
    elif do == "note":
        if row not in (doc.get("steps") or {}) or not words:
            return "I could not tell which row or what to write, so nothing was sent to the roadmap."
        path, op, data = f"notes/{row}--c{when:%H%M%S}", "set", {"row": row, "text": words, "written": now, "status": "open"}
    elif do == "answer":
        qid = str(action.get("question") or "")
        q = (doc.get("questions") or {}).get(qid)
        if not q:
            return "I could not find that question on the roadmap, so nothing was sent to it."
        letter = str(action.get("choice") or "").strip().lower()[:1]
        choices = q.get("choices") or []
        picked = choices[ord(letter) - 97] if letter and 0 <= ord(letter) - 97 < len(choices) else None
        if not picked and not words:
            return "I could not tell your answer, so nothing was sent to the roadmap."
        answer = (f"{letter}. {picked}" + (f"\n{words}" if words else "")) if picked else words
        path, op, data = f"questions/{qid}", "update", {"status": "answered", "answer": answer, "choice": letter if picked else "",
                                                       "note": words if picked else "", "answered": now}
    else:
        return "I could not tell what to do on the roadmap, so nothing was sent to it."
    rec = {"id": f"rm:{key}:{int(when.timestamp() * 1000)}-1", "action": "answer", "at": when.isoformat(timespec="seconds"), "origin": "chat",
           "text": json.dumps({"roadmap": {"key": key, "op": op, "path": path, "data": data}})}
    out = roadmap_press.handle(rec)
    return str(out.get("result") or out.get("error") or "")


def _project_tool(action, when):
    """{"type": "project_tool", "op": "add | remove", "tool": "roadmap | questions", "folder", "session"}: Settings, Tools' own press."""
    import project_tools
    op, tool = str(action.get("op") or ""), str(action.get("tool") or "")
    if op not in ("add", "remove") or tool not in ("roadmap", "questions"):
        return "I could not tell what to turn on or off, so nothing was changed."
    out = project_tools.handle({"id": f"pt:{op}-{tool}:{int(when.timestamp() * 1000)}", "action": "answer", "origin": "chat",
                                "text": json.dumps({"folder": str(action.get("folder") or ""), "session": str(action.get("session") or "")})})
    return str(out.get("result") or "")


SENT_CLAIM = re.compile(r"\b(i'?ve|i have|i)\s+(just\s+|now\s+)?(sent|texted|emailed|added|put|moved|changed|rescheduled|removed|deleted|cancell?ed)\b|"
                        r"\b(it'?s|it is|it has been|has been|have been|was just|is now)\s+(sent|added|moved|changed|removed|deleted|cancell?ed|on your calendar)\b", re.I)
SENT_ABOUT = re.compile(r"\b(emails?|texts?|messages?|calendar|event|meeting|appointment|sent|texted|emailed)\b", re.I)


def claims_done(said):
    """True when a sentence of the reply says the assistant itself sent an email or text or changed the calendar, and does not
    say it did not."""
    for sentence in re.split(r"(?<=[.?!])\s+", str(said or "")):
        if SENT_CLAIM.search(sentence) and SENT_ABOUT.search(sentence) and not NOT.search(sentence):
            return True
    return False


MOD_NAME = re.compile(r"^[a-z][a-z0-9-]{1,30}$")


_asked_now = []         # the rule and change cards made in this message (card_rules.asked_card)


def _asked(text, sentence, made, when, n, mod="", files=None):
    """A rule or change he asked for: its own card in Cards with Approve, Disapprove, Discuss and Cancel. (items, the line)."""
    import answers
    import card_rules
    words = text if text and not str(text).startswith("(") else sentence       # his own words title it; a press's lead never does
    item = card_rules.asked_card(words, sentence, made, when, n, mod=mod, files=files)
    if item is None:
        return [], f"I could not put that {made} on a card just now; tell me again in a minute. Nothing was {'changed' if made == 'change' else 'saved'}."
    _asked_now.append(item.get("id"))
    answers._patch_snapshot([item])
    return [item], card_rules.asked_said(item, made)


def _change_action(kind, action, text="", when=None, n=0):
    """A change to how the assistant works, asked for here: its own card (card_rules.asked_card), the change said back in one
    sentence, made only on his Approve there (answers._change_from_offer, then change_job.py). Nothing is recorded or edited here."""
    when = when or common.now()
    if _asked_now:          # one change card per message: a change_agree after its change_start is the same change
        return [], ""
    sentence = action.get("change") or action.get("agreed") or action.get("words") or ""
    return _asked(text or action.get("words") or "", sentence, "change", when, n,
                  mod=str(action.get("mod") or ""), files=action.get("files"))


# a reply that speaks of a change or rule as noted, recorded or waiting on a button: true only when a card was made for it
BUTTON = re.compile(r"yes,? make this change|cancel this change|just under this box", re.I)
NOTED = re.compile(r"\b(noted|recorded|logged|saved)\b[^.?!]*\b(change|rule)\b|\b(change|rule)\b[^.?!]*\b(noted|recorded|saved|is waiting)\b", re.I)


# his own words plainly asking for a change or a standing rule: the only words a card is made from when no ACTION line asked
ASKS_CHANGE = re.compile(r"\b(from now on|going forward|in (the )?future|always|never|every time|whenever|make (it|this|that|these|those|the|a|an|my|sure)|"
                         r"change|stop|start|add|remove|turn (it |this |that )?(on|off)|set up|rules?|i want|i'?d like|please)\b", re.I)


def _claims(p):
    return bool(BUTTON.search(p) or (NOTED.search(p) and not NOT.search(p)))


def asked_check(said, text, when, own_step, card, acted):
    """The reply's words about a change or rule against what the program did in this message: a sentence naming a button
    that is not on the page is dropped, and so is one saying a change or rule was noted when nothing made its card. A card is
    made here only when his own words plainly ask for a change or rule (ASKS_CHANGE) and the reply is not asking him
    anything: never from the reply's wording alone (acted: it had ACTION lines, which make their own cards).
    Returns (said, the program's line or "", items)."""
    parts = [p for p in re.split(r"(?<=[.?!])\s+", str(said or "").strip()) if p.strip()]
    claimed = [p for p in parts if _claims(p)]
    said = " ".join(p for p in parts if not BUTTON.search(p)).strip()
    if not claimed or acted or _asked_now or own_step or card or not str(text or "").strip():
        return said, "", []
    said = " ".join(p for p in parts if p not in claimed).strip()
    if any(p.rstrip().endswith("?") for p in parts) or not ASKS_CHANGE.search(str(text)):
        return said, "", []
    made = "rule" if any(re.search(r"\brule\b", p, re.I) for p in claimed) and not any(re.search(r"\bchange\b", p, re.I) for p in claimed) else "change"
    got, line = _asked(text, text, made, when, 0)
    return said, line, got


def mods_text(which):
    """What the owner's mods add to the chat's instructions ("chat") or to its guide to the page ("page")."""
    try:
        import mods
        return mods.chat_text() if which == "chat" else mods.page_text()
    except Exception:  # noqa: BLE001  a mod's words never stop the chat
        return ""


# --- the session the box talks to -----------------------------------------------------------------------------
TOOLS = "Read,Grep,Glob"         # everything a run has: it can read and search, nothing else exists for it
RUN_SECONDS = 120


def _rule(path):
    p = os.path.abspath(path)
    return "//" + p[0].lower() + p[2:].replace("\\", "/")


def _run(words, instructions, sess):
    """One run of the session: the owner's words in, the reply out. Hard limits are the flags:
    --tools gives it reading and searching only (no editing, no commands, no web, no connectors);
    --allowedTools lets it read the assistant's home and nothing else outside its own project folder;
    the deny rules keep the key, the settings, the database files and old saved program files out of reach;
    --strict-mcp-config and --setting-sources "" keep connectors and any wider permissions from loading."""
    import ai_steps
    import subprocess
    home = common.HOME
    deny = [f"Read({_rule(os.path.join(common.PERSONAL, n))})" for n in ("local_settings.json", "settings.json", "keys.dat")] + \
           [f"Read({_rule(home)}/Resources/Database/**)", f"Read({_rule(home)}/builds/**)", f"Read({_rule(home)}/sent/**)", f"Read({_rule(home)}/page_state/**)"]
    path = os.path.join(home, "chat", "instructions.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(instructions)
    import mods
    allow, refuse = mods.chat_tools()       # the owner's mods may name connector tools for the chat, and only those
    if allow:       # connectors load, but in dontAsk mode no tool runs unless named here: reading the home and the mods' tools
        reach = ["--tools", TOOLS + ",ToolSearch", "--allowedTools", ",".join([f"Read({_rule(home)}/**)"] + allow),
                 "--permission-mode", "dontAsk"] + (["--disallowedTools", ",".join(refuse)] if refuse else [])
    else:
        reach = ["--tools", TOOLS, "--allowedTools", f"Read({_rule(home)}/**)", "--strict-mcp-config"]
    flags = reach + ["--setting-sources", ""] + ai_steps.run_settings("chat", {"permissions": {"deny": deny}}) + [
             "--append-system-prompt-file", path,
             "--system-prompt-snapshot", "off"]     # without this a resumed session reuses the instructions of its first job
    import convo
    # the day's conversation session, one job at a time; a card's words go to that card's own session, never the box's
    return convo.run("chat", words, flags, MODEL, RUN_SECONDS, key=(sess or {}).get("card"))


def _split(reply):
    """The words for the page, the source line, and every thing asked for (in the order written; None for an
    ACTION line that could not be read), from a reply's last lines."""
    lines, source, actions = reply.strip().split("\n"), None, []
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
        elif last.upper().startswith("SOURCE:"):
            source = last[7:].strip() or None
            lines.pop()
        elif last.upper().startswith("ACTION:"):
            try:
                got = json.loads(last[7:].strip())
                actions.append(got if isinstance(got, dict) else None)
            except ValueError:
                actions.append(None)
            lines.pop()
        else:
            break
    actions.reverse()
    return "\n".join(lines).strip(), source, actions


PAGE_GUIDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "page.md")     # how the page works: part of the guardrails
NO_GUIDE = "(The guide to the page cannot be read right now. Answer what you can from WHAT YOU ARE, and say plainly when you do not know.)"


def page_guide():
    """The plain guide to the page's layout and buttons, so the box can answer questions about the page.
    A missing or unreadable guide never stops an answer."""
    try:
        with open(PAGE_GUIDE, encoding="utf-8") as f:
            return f.read().strip() or NO_GUIDE
    except OSError:
        return NO_GUIDE


UPDATE_TEXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup", "setup_texts", "update.md")


def update_walk():
    """While the owner is updating (he pressed Update in the last day): the walk-through to follow, or what to tell him."""
    st = common.read_json(os.path.join(common.paths.STATE, "update_walk.json"), {}) or {}
    try:
        fresh = st and (common.now() - dt.datetime.fromisoformat(str(st.get("started")))).total_seconds() < 86400
    except ValueError:
        fresh = False
    if not fresh:
        return ""
    try:
        with open(UPDATE_TEXT, encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        text = ""
    head = f"THE UPDATE HE STARTED (to version {st.get('version')}): "
    if text:
        return head + "follow this walk-through, one question at a time.\n" + text
    return head + ("the update walk-through is not on this computer yet. Tell him plainly, in one or two sentences, to finish it "
                   "at his computer: open Claude there and type /assistant:update. Nothing has been changed.")


CHANGE_TEXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup", "setup_texts", "change.md")
PROGRAM_TEXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup", "setup_texts", "change-program.md")


def change_walk():
    """While he is asking for a change (pressed Change in the last day, or a change is being talked through or made): the
    change skill's walk-through to follow, or what to tell him when it is not on this computer."""
    st = common.read_json(os.path.join(common.paths.STATE, "change_walk.json"), {}) or {}
    try:
        fresh = bool(st) and (common.now() - dt.datetime.fromisoformat(str(st.get("started")))).total_seconds() < 86400
    except ValueError:
        fresh = False
    import changes_feed
    open_one = any(c.get("state") in ("go", "doing") for c in changes_feed.records())     # a change waiting is a card now
    if not (fresh or open_one):
        return ""
    text = ""
    for path in (CHANGE_TEXT, PROGRAM_TEXT):        # the walk-through, and its part for how the assistant works (choice 6)
        try:
            with open(path, encoding="utf-8") as f:
                text += ("\n\n" if text else "") + f.read().strip()
        except OSError:
            pass
    if text:
        return "A CHANGE TO HOW THE ASSISTANT WORKS IS BEING TALKED THROUGH: follow this walk-through, one question at a time.\n" + text
    return ("A CHANGE TO HOW THE ASSISTANT WORKS WAS ASKED FOR, but the change walk-through is not on this computer yet. Tell him "
            "plainly, in one or two sentences, to ask for it at his computer: open Claude there and type /assistant:change. Nothing has been changed.")


def walk_now():
    """The walk-through under way: of a tool started in Settings, an update and a change, the one started last (a change
    being talked through or made counts as just started)."""
    import tools

    def started(name):
        return str((common.read_json(os.path.join(common.paths.STATE, name), {}) or {}).get("started") or "")
    texts = [(started("tool_walk.json"), tools.walk()), (started("update_walk.json"), update_walk())]
    ch = change_walk()
    if ch:
        import changes_feed
        busy = any(c.get("state") in ("go", "doing") for c in changes_feed.records())
        texts.append(("9999" if busy and not started("change_walk.json") else started("change_walk.json"), ch))
    live = [(x[0], n, x[1]) for n, x in enumerate(texts) if x[1]]       # started in the same second: the later kind is the newer
    return max(live)[2] if live else ""


def instructions(found, turns, me=None, card=None, open_card=None):
    """The working instructions for one run: prompts\\chat.md with the owner's facts, the page guide,
    the assistant's facts about itself, what was found and the latest stretch of the conversation."""
    with open(os.path.join(common.PROMPTS, "chat.md"), encoding="utf-8") as f:
        text = f.read()
    about = str(common.personal().get("about") or "").strip()
    extra = mods_text("chat")
    if extra:           # the owner's mods: what each adds to these instructions (mods.py)
        text += "\n\nWHAT THE OWNER'S MODS ADD (follow them as you follow everything above):\n" + extra
    return text.replace("{OWNER}", common.owner()).replace("{ABOUT}", about).replace("{HOME}", common.HOME) \
        .replace("{PAGE_GUIDE}", "\n\n".join(x for x in (page_guide(), mods_text("page")) if x)) \
        .replace("{RULEBOOK}", common.rulebook().as_text()) \
        .replace("{UPDATE_WALK}", walk_now()) \
        .replace("{SELF_JSON}", json.dumps(about_me() if me is None else me, default=str)) \
        .replace("{FOUND_JSON}", json.dumps(found, indent=1, default=str)) \
        .replace("{CARD}", card_block(card)) \
        .replace("{OPEN_CARD}", open_card_block(card, open_card)) \
        .replace("{THREAD_JSON}", json.dumps(thread(turns, card), indent=1, default=str))


CARD_TEXT = os.path.join(common.PROMPTS, "chat_card.md")


def card_block(card):
    """When the message was typed on a card: that card, and how to answer about it (prompts, chat_card.md). Else nothing."""
    if not card:
        return ""
    import filters
    with open(CARD_TEXT, encoding="utf-8") as f:
        text = f.read()
    return text.replace("{OWNER}", common.owner()).replace("{CARD_JSON}", json.dumps(card_facts(card), indent=1, default=str)) \
        .replace("{CARD_RULES}", filters.lines_for_writing())


THREAD_TURNS = 16        # how much of the page's own conversation goes with every message


def open_card_block(card, open_card):
    """In the box (not on a card): the card open on his page, which "this card" means; or that none is open (his plan of
    11/23, points 3 and 4)."""
    if card:
        return ""
    if not open_card:
        return ("THE OPEN CARD: no card is open on his page. If his words say \"this card\" (or \"this one\", \"it\" about a card) and "
                "do not name it, ask him to open the card he means; do nothing to any card until he has.")
    return ("THE OPEN CARD: \"this card\" (or \"this one\", \"it\" about a card) means this card, open on his page now:\n"
            + json.dumps(card_facts(open_card), indent=1, default=str))


def take_cards(reply):
    """(the reply without its CARDS line, the card ids it names): the cards this exchange in the box was about."""
    out, keep = [], []
    for line in str(reply or "").split("\n"):
        if line.strip().upper().startswith("CARDS:"):
            out += re.findall(r"\bL\d{1,7}\b", line)
        else:
            keep.append(line)
    return "\n".join(keep), list(dict.fromkeys(out))


def copy_to_cards(ids, text, said, at):
    """What he and the assistant said about cards in the box is added to each card's own conversation too (his plan of
    11/23, point 5): its talk (so the card's own session knows it) and its history (so the page shows it). Returns the cards."""
    import answers
    import items
    snap = {i.get("id"): i for i in (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or []}
    stamp = common.now()
    done = []
    for cid in ids[:MOST_ACTIONS]:
        it = snap.get(cid)
        if not it:
            continue
        about = {"id": cid, "title": str(it.get("short_header") or it.get("title") or "")[:200]}
        _add({"who": "you", "text": text, "at": at, "card": about, "from_box": True})
        if said:
            _add({"who": "assistant", "text": said, "at": stamp.isoformat(timespec="seconds"), "card": about, "from_box": True})
        did = f"You wrote in Talk to your assistant, {stamp.month}/{stamp.day} {stamp.strftime('%I:%M %p').lstrip('0')}: \"{text[:600]}\""
        if said:
            did += "\nI answered: " + " ".join(said.split())[:1500]
        try:
            item, _ = answers._land(answers._set(cid, did=did))
            if item:
                done.append(item)
        except Exception as e:  # noqa: BLE001  the box's own answer stands either way
            common.log_line(os.path.join(common.LOGS, "errors.log"), f"chat copy to card {cid}: {type(e).__name__}: {e}")
    return done


def thread(turns, card=None):
    """The latest stretch of the conversation as the page holds it. The app shortens a long session to a
    summary of its own, and a summary can drop what the owner said a moment ago; this cannot. card: that card's own
    conversation; without it, the box's own, with no card's turns in it."""
    turns = [t for t in turns if (t.get("card") or {}).get("id") == card.get("id")] if card else box_turns(turns)
    return [{k: v for k, v in {"who": t.get("who"), "at": t.get("at"), "said": str(t.get("text") or "")[:600],
                                "on_card": t.get("card"), "in_the_claude_app": bool(t.get("desktop"))}.items() if v} for t in turns[-THREAD_TURNS:]]


# --- nothing promised that is not done -------------------------------------------------------------------
# A reply that says it will do something (search, write, put on the page) either does it in the same message (one more
# run, given a fresh search for it) or the promise becomes a real job: kept in QUEUE, run by the next pass, and its
# result said here in the chat.
PROMISE = re.compile(r"\b(?:i will|i'll|i am going to|i'm going to|let me|next,? i will|i can now|i shall)\b[^.?!]*?\b"
                     r"(search|look|find|check|write|draft|put|make|add|prepare|send|follow up|get back|let you know|update|go through)\b", re.I)
DRAFT_VERBS = {"write", "draft", "put", "make", "prepare", "add"}
FOLLOW_UPS = 2           # more runs in one message to do what the reply said it would
QUEUE = os.path.join(common.HOME, "chat", "queue.json")
QUEUED_SAYS = "I'll finish this the next time I check for messages, within 15 minutes, and tell you here."
NO_DRAFT_SAYS = "I did not put any email on your page this time. Ask me again and I will write it."
NOT_DONE_SAYS = "Nothing was sent or changed on your calendar this time. Tell me plainly what to do and I will do it."


def promises(said, made_drafts, did_task):
    """The sentences of a reply that say it will do something no ACTION line of the same reply did. A step that waits on
    the owner ("once you tell me ...", "when you press Send") is not a promise of the assistant's own."""
    out = []
    for sentence in re.split(r"(?<=[.?!])\s+", str(said or "")):
        m = PROMISE.search(sentence)
        if not m:
            continue
        verb = m.group(1).lower()
        if (verb in DRAFT_VERBS and made_drafts) or (verb in ("follow up", "get back", "let you know") and did_task) or verb == "send":
            continue
        if re.search(r"\b(when you|once you|if you|after you|until you)\b", sentence, re.I):
            continue
        out.append(sentence.strip())
    return out


def queue_job(do, text, card_id):
    """A promise the runs could not keep in this message: a real job the next pass runs (run_queue)."""
    jobs = common.read_json(QUEUE, {}) or {}
    jobs.setdefault("jobs", []).append({"at": common.now().isoformat(timespec="seconds"), "do": do, "words": text, "card": card_id})
    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    common.write_json(QUEUE, jobs)


def run_queue(limit=3):
    """The pass: each job a reply promised is run now, as the assistant's own next step, and its result is said in the chat
    (and on the card it was about). Returns (jobs run, problems)."""
    jobs = (common.read_json(QUEUE, {}) or {}).get("jobs") or []
    if not jobs:
        return 0, []
    import items
    import limits
    take = []
    for job in jobs[:limit]:
        if not limits.enough((FOLLOW_UPS + 1) * RUN_SECONDS + 30):
            break
        take.append(job)
    n, problems = 0, []
    common.write_json(QUEUE, {"jobs": jobs[len(take):]})
    for job in take:
        card = None
        if job.get("card"):
            rows = items.rows("id = ?", (job["card"],))
            card = items.finish(rows[0]) if rows else None
        try:
            out = handle(f"{job.get('do')}", card=card, own_step=f"(your own next step, promised {job.get('at')} in answer to: "
                                                                 f"\"{str(job.get('words') or '')[:300]}\")", queue=False)
            n += 1
            if card is not None and out.get("card_record"):
                import answers
                answers._save(out["card_record"])
                answers.land_now()
        except Exception as e:  # noqa: BLE001
            problems.append("Something I promised in Talk to your assistant couldn't be done. I said so there.")
            _add({"who": "assistant", "text": "I could not finish what I said I would do: " + str(job.get("do"))[:200] +
                  ". Ask me again.", "source": None, "at": common.now().isoformat(timespec="seconds")})
    return n, problems


def _answered(card):
    import answers
    try:
        return answers.answered_of(card)
    except Exception:  # noqa: BLE001  a card's facts never fail on this
        return []


def card_facts(card):
    """What a run is shown about the card a message is about: the same facts the card's own reading had."""
    if not card:
        return None
    asks = [str(a) for a in card.get("asks") or []]
    return {"id": card.get("id"), "title": card.get("title"), "story": card.get("detail"), "recommended": card.get("recommended"),
            "open_questions_numbered": {str(i): a for i, a in enumerate(asks, 1)},
            "questions_already_answered": [{k: a.get(k) for k in ("ask", "answer", "did")} for a in _answered(card)],
            "state": card.get("state"), "kind": card.get("kind"),
            "area": card.get("area"), "from": card.get("source_ref") or card.get("source_who"),
            "newest_message": (card.get("source_text") or "")[:3000],
            "an_old_draft_on_the_card": card.get("draft") or None, "emails": card_emails(card),
            "calendar": card.get("calendar") or None, "asked_by": (card.get("reply") or {}).get("to") or None,
            "history": (card.get("assistant_did") or "").split("\n")[-10:]}


_scan_note = [None]         # what a rule saved in this message did to other cards: its Undo goes on the reply's turn


def handle(text, at=None, card=None, own_step=None, queue=True, rules=True, open_card=None):
    """One message from the owner, in the box at the top or typed on a card (card: that card, decorated). Returns what
    act_on_answer returns: ok, items changed, the reply as result; for a card also card_action (what the run decided
    about the card) and made (the Ready to send cards written for it). own_step: the run is the assistant's own next
    step (a job it promised), not the owner's words. rules False: no rule is saved from this message (the owner already
    answered a rule proposed on the card: Approve saved it, Disapprove said this is one time only)."""
    t0 = time.time()
    when = common.now()
    text = (text or "").strip()[:3000]
    if not text:
        return {"ok": False, "error": "There were no words to answer.", "items": []}
    about = {"id": card.get("id"), "title": str(card.get("short_header") or card.get("title") or "")[:200]} if card else None
    with _one:                  # one message at a time, in order: a second one waits for the first reply
        turns = load((card or {}).get("id"))["turns"]       # a card's own conversation, or the box's
        if at and any(t.get("who") == "you" and t.get("at") == at and t.get("text") == text for t in turns):      # the same message, delivered twice
            last = next((t for t in reversed(turns) if t.get("who") == "assistant"), {})
            return {"ok": True, "items": [], "result": last.get("text") or "", "thought": False, "duplicate": True, "secs": {}}
        if not own_step:
            _add({k: v for k, v in {"who": "you", "text": text, "at": at or when.isoformat(timespec="seconds"), "card": about}.items() if v})
        import settings_page
        if settings_page.at_limit():        # the day's limit on thinking runs: said plainly, nothing is run
            said = settings_page.LIMIT_SAYS + " Your words are kept; ask again tomorrow, or raise the limit in Settings."
            _add({k: v for k, v in {"who": "assistant", "text": said, "source": None, "at": common.now().isoformat(timespec="seconds"), "card": about}.items() if v})
            return {"ok": True, "items": [], "result": said, "thought": False, "secs": {}, "limit": True}
        found = found_for(text + " " + " ".join(str((card or {}).get(k) or "") for k in ("title", "detail")), turns, card)
        t_found = time.time() - t0
        _batch[0] = when.strftime("%Y%m%d-%H%M%S-%f")       # one message, one batch: two messages in a second never share it
        _scan_note[0] = None
        _made_now.clear()
        _sent_now.clear()
        _asked_now.clear()
        _typed[0] = at or when.isoformat(timespec="seconds")
        false_done = False
        # a line starting with "/" would be taken as a command to the session itself, not as the owner's words
        words = ("(typed on the page) " + text) if text.startswith("/") else text
        if card:
            words = f"(about card {card.get('id')}: {about['title']}) {words}"
        if own_step:
            words = f"{own_step} {words}"
        said_parts, source, changed, made, card_action, actions, think, denied, why = [], None, [], [], None, [], 0.0, [], ""
        false_claim = False
        about_cards = []
        held_rules, asked_rule = [], ""      # on a card: rule ACTIONs held, and a rule question taken out of the words
        n_run = 0
        while True:
            told = instructions(found, load((card or {}).get("id"))["turns"], card=card, open_card=open_card)
            reply, why, secs_run, rep = _run(words, told, {"card": card.get("id")} if card else {})
            think += secs_run
            n_run += 1
            with open(common.AI_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": common.now().isoformat(timespec="seconds"), "pass": "chat", "step": "chat", "model": MODEL,
                                    "ok": reply is not None, "secs": round(secs_run, 1), "why": "" if reply is not None else why,
                                    "follow_up": n_run > 1}) + "\n")
            denied += [str((d.get("tool_input") or {}).get("file_path") or d.get("tool_name")) for d in rep.get("permission_denials") or []]
            if reply is None:
                said_parts.append(f"I could not answer just now ({why}). Your words are kept; ask again in a moment.")
                break
            reply, named = take_cards(reply)        # the cards this exchange in the box is about (point 5)
            about_cards += named
            said, src, acts = _split(reply)
            source = source or src
            actions += acts
            mine = [a for a in acts if isinstance(a, dict) and a.get("type") == "card"]
            if mine:
                card_action = mine[-1]
            looks = [a for a in acts if isinstance(a, dict) and a.get("type") == "look"]
            finds = [a for a in acts if isinstance(a, dict) and a.get("type") == "cards"][:MOST_ACTIONS]
            import tools
            setups = [a for a in acts if tools.is_setup(a)]     # a tool's setup steps: run here, their answers handed back
            rest = [a for a in acts if not (isinstance(a, dict) and a.get("type") in ("card", "look", "cards")) and not tools.is_setup(a)]
            if not rules:       # a rule was already answered on the card: nothing more is saved as one
                rest = [a for a in rest if not (isinstance(a, dict) and a.get("type") == "rule")]
            elif card:          # on a card a rule is never saved at once: it is proposed under the box (answers.py)
                held_rules += [str(a.get("text") or "") for a in rest if isinstance(a, dict) and a.get("type") == "rule"]
                rest = [a for a in rest if not (isinstance(a, dict) and a.get("type") == "rule")]
            if card:            # a draft written on a card answers that card
                for a in rest:
                    if isinstance(a, dict) and a.get("type") == "draft" and not a.get("about"):
                        a["about"] = card.get("id")
            # his own words are the authority for a send or a calendar change (rule B11): the assistant's own next step has none
            k_sent = len(_sent_now)
            got, extra = _do_all(rest, "" if own_step else text, when, len(actions) - len(acts))
            changed += got
            new = [i for i in got if str(i.get("source_key") or "").startswith("live:ready-")]
            made += new
            drafts = [a for a in rest if (a or {}).get("type") == "draft"]
            if drafts:
                # an email's own words are never shown in the chat: they are on the page, in Ready to send
                bodies = [str(a.get("body") or "") for a in drafts]
                if any(len(b) > 40 and (b[:40] in said or b[-40:] in said) for b in bodies) or len(said) > 600 or len(new) != len(drafts):
                    said = ""       # its own words could misstate what is on the page: the program's count and reasons say it
            elif claims_draft(said) and not made:
                # it says it put an email on the page, but no draft ACTION put one there: never claim what was not done
                said, false_claim = "", True
            if any((a or {}).get("type") in ("send", "text_send", "calendar", "cards_done") for a in rest) or any(s["what"] == "mail" for s in _sent_now[k_sent:]):
                said = ""       # what was sent or changed, to whom and from where, is said by the program's own lines alone
            elif claims_done(said) and not any(s["ok"] for s in _sent_now) and not got and not made:
                said, false_done = "", True     # it says it sent or changed something no ACTION line did
            said, asked_line, asked_items = asked_check(said, text, when, own_step, card, bool(acts))
            if asked_line:      # a change or rule it said it noted: its card is made now, and the program says where
                changed += asked_items
                extra = " ".join(x for x in (extra, asked_line) if x)
            # what it said it would do and did not, an address it asked for that is on file, or a search it asked for
            owed = promises(said, bool(made), any((a or {}).get("type") == "task" for a in rest))
            ask = str((card_action or {}).get("ask") or "").strip()
            on_file = []
            if ask:
                import people
                keep, on_file, _used = people.settle_asks([ask], text + " " + json.dumps(card_facts(card) or {}, default=str))
                if on_file:
                    card_action["ask"] = keep[0] if keep else ""
            ran = [f"setup {' '.join(tools.setup_args(a))[:200]}: {tools.run_setup(tools.setup_args(a))}" for a in setups[:MOST_ACTIONS]]
            next_step = [str(a.get("for") or "") for a in looks] + owed + on_file
            searched = []
            if finds:           # the cards search it asked for: every card, open and closed, handed back in this same message
                import card_search
                searched = [card_search.for_action(a) for a in finds]
                next_step.append("(the cards search you asked for is in card_search: answer from its count and cards; do not ask for it again)")
            if owed:            # what it only promised is not shown: it is done below, or becomes a job
                said = " ".join(x for x in re.split(r"(?<=[.?!])\s+", said or "") if x.strip() not in owed).strip()
            if card and rules:  # a rule is never asked about in words on a card: the page asks under the box (answers.py)
                import card_rules
                said, asked = card_rules.offer_in(said)
                asked_rule = " ".join(x for x in (asked_rule, asked) if x)
            if said:
                said_parts.append(said)
            if extra:
                said_parts.append(extra)
            if ran:             # the walk-through goes on from what the setup steps answered, in this same message
                if n_run > FOLLOW_UPS + 2:
                    said_parts.append("I stopped there for now; tell me to go on.")
                    break
                words = ("(the setup steps you asked for ran on this computer; their answers follow. Go on with the walk-through "
                         "from them, in plain words, and ask the next question if there is one.) " + " | ".join(ran) +
                         (" (also still owed: " + " ".join(next_step) + ")" if next_step else ""))
                continue
            if not next_step:
                break
            if n_run > FOLLOW_UPS:
                if queue:
                    queue_job(" ".join(next_step)[:600], text, (card or {}).get("id"))
                    said_parts.append(QUEUED_SAYS)
                break
            # one more run, now: told what it still owes, with a fresh search for it
            words = ("(your own next step, now, in this same message: do it and end with the ACTION lines that do it; "
                     "if it cannot be done, say plainly what is missing; never say you will do it later) " + " ".join(next_step))
            found = found_for(" ".join(next_step) + " " + text, load((card or {}).get("id"))["turns"], card)
            if searched:
                found["card_search"] = searched
        gone = {s.get("id") for s in _sent_now if s["what"] == "email" and s["ok"]}
        waiting = [i for i in made if i.get("id") not in gone]
        if waiting:
            said_parts.append(f"I put {len(waiting)} email{'s' if len(waiting) != 1 else ''} in Drafts, in the Email part of your page; "
                              "it goes when you press Send there or tell me to send it.")
        elif false_claim:
            said_parts.append(NO_DRAFT_SAYS)
        if false_done:
            said_parts.append(NOT_DONE_SAYS)
        said = " ".join(dict.fromkeys(p for p in said_parts if p))
        _add({k: v for k, v in {"who": "assistant", "text": said, "source": source, "at": common.now().isoformat(timespec="seconds"),
                                "card": about, "scan": _scan_note[0]}.items() if v})
    if about_cards and not card and not own_step:       # what was said about cards up top goes on each card too
        changed += copy_to_cards(about_cards, text, said, at or when.isoformat(timespec="seconds"))
    secs = {"own": round(t_found, 2), "waited": 0, "think": round(think, 2), "all": round(time.time() - t0, 2), "runs": n_run}
    common.log_line(os.path.join(common.LOGS, "answers.log"),
                    f"chat{' on ' + about['id'] if about else ''} | found {secs['own']}s runs {n_run} run {secs['think']}s all {secs['all']}s"
                    f" | action {','.join(str((a or {}).get('type')) for a in actions) or None} | refused reads {len(denied)}")
    out = {"ok": True, "items": changed, "result": said[:1900], "thought": True, "secs": secs, "denied": denied,
           "card_action": card_action, "made": [i.get("id") for i in made], "failed": reply is None and n_run == 1}
    if card is not None:
        import answers
        out["card_record"] = answers.card_record(card, card_action, text, said, out["made"], when)
        added = next((s for s in _sent_now if s["what"] == "calendar" and s["ok"] and s.get("do") == "add"), None)
        if added and isinstance(card.get("calendar"), dict):        # the card's event is on the calendar now: never added twice
            out["card_record"]["fields"]["calendar"] = dict(card["calendar"], added=added.get("id"))
        if held_rules or asked_rule:        # the rule it gave or asked about: proposed under the card's box (answers.py)
            out["rule_offer"] = " ".join(x for x in held_rules + [asked_rule] if x)[:900]
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["--instructions"]:      # a Claude session in the assistant's folder reads what the page's chat is given
        sys.stdout.reconfigure(encoding="utf-8")
        turns = load()["turns"]
        print(instructions(found_for("", turns), turns))
        sys.exit(0)
    r = handle(" ".join(sys.argv[1:]))
    print(json.dumps({k: r.get(k) for k in ("ok", "result", "secs", "error")}, indent=1))
    print(json.dumps(load()["turns"][-1], indent=1))
