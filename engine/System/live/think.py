r"""The think pass: the AI work, run only when the gather pass found something.

    python think.py            # run now if anything waits (takes the pass lock)

In order: read new pages that arrived as pictures, describe pictures sent by
text, judge only the new messages with the engine's own judge and rules, and in the
same Claude run write the card of every matter it leaves open (one brain: what
it decides, recommends and asks comes from one reading, so they agree), bring
the item store up to date and put those cards on it; the card writer then
writes only what the judging run did not (a card owed a full writing, one left
from an earlier check, a card whose judged card was refused) and places new
mail that has no item yet: attached to an open item, skipped, or made into a
new item.

Every AI call goes through the engine's own way of starting Claude with no
person present (ai_steps: the Claude command, -p, on the owner's subscription).
Each call is logged to Live\logs\ai.jsonl, each step is tried twice, and a
failure is returned so the health record can show it.
"""
import datetime as dt
import json
import os
import re
import sys
import time

import card
import common
import db
import gather
import items
import limits
import replay_guard

import ai_steps  # noqa: E402  the engine's AI steps
sys.path.insert(0, common.paths.MODULE_A)
import cleantext  # noqa: E402

PAGE_BATCH = 8            # pages per AI call
PAGE_MAX_PER_PASS = 40    # the rest wait for the next pass
PAGE_MIN_BYTES = 15_000   # a smaller picture is a logo or signature, not a page
PAGE_PICTURES = os.path.join(common.paths.STATE, "page_pictures")   # PDF pages drawn for the reader, removed once read
RETRY_AFTER_MINUTES = 60  # after a failed think with nothing new since
OUT_OF_TIME = "the check was out of time"     # said by a step cut short by the check's own limit: put off, never failed
JUDGE_ROUND = 150         # one more judging round: its payload, the Claude run and the commit
JUDGE_SMALLEST = 5        # a round that timed out is asked for again at half its size, down to this many messages
WRITE_RESERVE = 180       # kept for writing cards: judging a backlog never takes the whole pass
BODY_LIMIT = 2500
PAGE_LIMIT = 3000
ITEM_BATCH = 10           # cards written per Claude run; every card owed is written, in as many runs as it takes
LOOSE_BATCH = 15          # new messages with no card yet, placed per Claude run; none is ever dropped
# the judge's verdicts that need nothing from the owner: such mail never becomes an item here, except that a judge's
# noise verdict neither the owner's rules nor his settings cover gets the one-line "I'd hide this" card (wouldhide.py, guardrail A13)
QUIET_VERDICTS = ("noise", "ignore", "phishing", "evidence", "judged_by_v1")
# one brain: the cards the judging run wrote with its verdicts, by item key, until the write step puts them on their items
BRAIN_CARDS = os.path.join(common.paths.STATE, "brain_cards.json")
OPEN_STATUSES = ("needs_me", "waiting_them")
BRAIN_KEEP_HOURS = 24     # a judged card whose item never came (its task closed first) is let go after this
brain = {"judged": 0, "writer": 0}      # this pass: cards written with the verdicts, and by the card writer



def model():
    """The model the judging and item writing steps run on: the owner's choice in Settings, else the most careful."""
    import settings_page
    return settings_page.think_model()


def write_model():
    """The model the card writing step runs on: Sonnet during the day-by-day rebuild, else the same as model()."""
    return "sonnet" if replay_guard.on() else model()


_current = {"pass": None, "step": None}
calls = []  # every AI call made by this process

_engine_call = ai_steps._call
_engine_script = ai_steps.script
ai_steps.AGENT_TIMEOUT = limits.AI
ai_steps.DESCRIBE_TIMEOUT = min(ai_steps.DESCRIBE_TIMEOUT, limits.AI)


def _limited_script(path, *args, timeout=limits.SCRIPT):
    """An engine script for an AI step, inside its limit and the pass's."""
    if not limits.enough(10):
        return False, f"{os.path.basename(path)} not started: {OUT_OF_TIME}"
    limits.step(os.path.basename(path))
    want = min(timeout, limits.SCRIPT)
    given = limits.cap(want)
    ok, out = _engine_script(path, *args, timeout=given)
    if not ok and given < want and " timed out after " in str(out):       # cut short by the pass's limit, not its own
        return False, f"{os.path.basename(path)} stopped after {given:.0f}s: {OUT_OF_TIME}"
    return ok, out


ai_steps.script = _limited_script


def _logged_call(prompt, model, timeout, resume=None):
    if not limits.enough(30):
        return ai_steps.Result(False, why=f"not started: {OUT_OF_TIME}")
    limits.step(f"Claude ({_current['step']})")
    want = min(timeout, limits.AI)
    given = limits.cap(want)
    res = _engine_call(prompt, model, given, resume)
    if not res.ok and given < want and str(res.why or "").startswith("timed out"):     # cut short by the pass's limit
        res.why = f"stopped after {given:.0f}s: {OUT_OF_TIME}"
    rec = {"at": common.now().isoformat(timespec="seconds"), "pass": _current["pass"],
           "step": _current["step"], "model": model, "ok": bool(res.ok), "secs": round(res.secs),
           "why": res.why or "", "follow_up": bool(resume), "out_tokens": getattr(res, "out_tokens", None),
           "cost": round(float(getattr(res, "cost", 0) or 0), 4)}
    if _current["step"] == "judge":
        rec["brain"] = True             # the judging run writes the cards too (one brain): brain_cost's "now", never its "before"
    calls.append(rec)
    os.makedirs(common.LOGS, exist_ok=True)
    with open(common.AI_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return res


ai_steps._call = _logged_call


def _prompt(name, **slots):
    with open(os.path.join(common.PROMPTS, f"{name}.md"), encoding="utf-8") as f:
        text = f.read()
    me = common.personal()
    slots = {"OWNER": common.owner(), "ABOUT": str(me.get("about") or "").strip(), **slots}
    if "{CARD_RULES}" in text and "CARD_RULES" not in slots:     # his own rules on how cards are written, for every prompt that writes one
        import filters
        slots["CARD_RULES"] = filters.lines_for_writing()
    for k, v in slots.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def _step(name, fn, needs=0):
    """Run one step; returns its record. A crash is a failed step, not a dead
    pass. A step the pass has no time left for is put off, not failed: what it
    would have worked stays waiting and the next pass takes it."""
    _current["step"] = name
    limits.step(name)
    before = len(calls)
    t0 = time.time()
    if needs and not limits.enough(needs):
        return {"at": common.now().isoformat(timespec="seconds"), "step": name, "ok": True, "secs": 0,
                "tries": 0, "why": "", "detail": "put off to the next check: not enough time left",
                "put_off": True}
    try:
        ok, detail = fn()
    except Exception as e:  # noqa: BLE001
        ok, detail = False, f"{type(e).__name__}: {e}"[:300]
    mine = calls[before:]
    if not ok and OUT_OF_TIME in str(detail):
        # it ran out of time partway: put off, not failed, so the next pass goes on with it at once (a failure waits
        # RETRY_AFTER_MINUTES); what it finished is kept, and what it did not reach stays waiting
        return {"at": common.now().isoformat(timespec="seconds"), "step": name, "ok": True, "secs": round(time.time() - t0),
                "tries": len(mine), "why": "", "detail": "put off to the next check: the check ran out of time partway",
                "put_off": True}
    return {"at": common.now().isoformat(timespec="seconds"), "step": name, "ok": bool(ok),
            "secs": round(time.time() - t0), "tries": len(mine), "why": "" if ok else str(detail)[:300],
            "detail": str(detail)[:300]}


# --- step 1: pages that arrived as pictures --------------------------------------
PAGE_TRIES = 3                  # passes a page may come back with nothing before it is passed over
SEEABLE = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff")
PAGE_DPI = 150           # a PDF page is drawn at this size for the reader: small print stays readable


def page_picture(path, page_no, page_id):
    """A PDF page drawn as a picture for the reader (None when it cannot be drawn). Claude's Read tool opens one page of a
    PDF only through pdftoppm, which a computer may not have; a picture it always opens."""
    try:
        import fitz
        fitz.TOOLS.mupdf_display_errors(False)
        os.makedirs(PAGE_PICTURES, exist_ok=True)
        out = os.path.join(PAGE_PICTURES, f"page_{page_id}.png")
        with fitz.open(path) as doc:
            if not 1 <= int(page_no or 1) <= len(doc):
                return None
            doc[int(page_no or 1) - 1].get_pixmap(dpi=PAGE_DPI).save(out)
        return out
    except Exception:  # noqa: BLE001  a damaged file: that page waits, as one that could not be read
        return None


def pdf_pages_back():
    """Once: PDF pages passed over (or counting tries) only because the reader could not open a single page of a PDF before
    pages were drawn as pictures (page_picture) are put back in line with their tries cleared. Only a page still unread whose
    file is a PDF that is there: a missing file, a small picture or a file that is not a page stays passed over. Returns how
    many came back (0 once it has run)."""
    state = gather.state()
    if state.get("pdf_pages_back_at"):
        return 0
    skipped, tries = list(state.get("pages_skipped") or []), dict(state.get("pages_tries") or {})
    ids = sorted({int(i) for i in skipped} | {int(k) for k in tries})
    back = set()
    for n in range(0, len(ids), 500):
        part = ids[n:n + 500]
        rows = db.query("SELECT p.id, a.saved_path FROM pages p JOIN documents d ON d.id = p.document_id"
                        " JOIN attachments a ON a.id = d.attachment_id"
                        f" WHERE p.method = 'needs_vision' AND p.id IN ({', '.join('?' for _ in part)})", part)
        back |= {r[0] for r in rows if str(r[1] or "").lower().endswith(".pdf") and os.path.exists(r[1])}
    state["pages_skipped"] = [i for i in skipped if int(i) not in back]
    state["pages_tries"] = {k: v for k, v in tries.items() if int(k) not in back}
    state["pdf_pages_back_at"] = common.now().isoformat(timespec="seconds")
    common.write_json(gather.GATHER_STATE, state)
    return len(back)


def read_pages():
    came_back = pdf_pages_back()
    waiting = gather.pending_pages()
    if not waiting:
        return True, "no pages waiting"
    state = gather.state()
    todo, skipped = [], []
    for page_id, doc_id, page_no, path, msg_id in waiting:
        if not path or not os.path.exists(path):
            skipped.append(page_id)
        elif not path.lower().endswith(".pdf") and os.path.getsize(path) < PAGE_MIN_BYTES:
            skipped.append(page_id)
        elif not path.lower().endswith(SEEABLE):     # a spreadsheet or other file queued by mistake: nothing to read by eye
            skipped.append(page_id)
        else:
            todo.append((page_id, doc_id, page_no, path, msg_id))
    if skipped:
        state["pages_skipped"] = sorted(set(state.get("pages_skipped", [])) | set(skipped))
        common.write_json(gather.GATHER_STATE, state)
    todo = todo[:PAGE_MAX_PER_PASS]
    if not todo:
        return True, f"{len(skipped)} small picture(s) or missing file(s) passed over"
    read, failed, missed = 0, 0, []
    for n in range(0, len(todo), PAGE_BATCH):
        batch = todo[n:n + PAGE_BATCH]
        entries, drawn = [], []
        for page_id, _doc, page_no, path, msg_id in batch:
            m = db.query("SELECT from_key, subject FROM messages WHERE id=?", (msg_id,)) if msg_id else []
            if path.lower().endswith(".pdf"):       # the reader is given the page as a picture (see page_picture)
                pic = page_picture(path, page_no, page_id)
                if pic is None:
                    continue
                drawn.append(pic)
                path, page_no = pic, 1
            entries.append({"page_id": page_id, "file": path, "page_no": page_no,
                            "from": m[0][0] if m else None, "subject": m[0][1] if m else None})
        if not entries:
            failed += len(batch)
            missed.extend(b[0] for b in batch)
            continue
        out = os.path.join(common.paths.STATE, f"live_pages_{n // PAGE_BATCH + 1}.json")
        res = ai_steps.agent(_prompt("pages", PAGES_JSON=json.dumps(entries, indent=1)), "sonnet", out,
                             ai_steps.DESCRIBE_TIMEOUT)
        for pic in drawn:           # made only for this reading
            try:
                os.remove(pic)
            except OSError:
                pass
        failed += len(batch) - len(entries)
        missed.extend(b[0] for b in batch if b[0] not in {e["page_id"] for e in entries})
        if not res.ok:
            failed += len(entries)
            continue
        owed = {e["page_id"] for e in entries}
        got = common.read_json(out, {}).get("pages") or []
        now = common.now()
        con = db.connect()
        try:
            for p in got:
                text = (p.get("text") or "").strip()
                if p.get("page_id") in owed and len(text) >= 10:
                    con.execute("UPDATE pages SET text=?, method='vision', extracted_at=?"
                                " WHERE id=? AND method='needs_vision'", (text, now, p["page_id"]))
                    owed.discard(p["page_id"])
                    read += 1
        finally:
            con.close()
        failed += len(owed)
        missed.extend(owed)
    # a page the reader answered nothing for three passes running (a blank page, lines with nothing to say) is passed over
    # and said once, instead of failing every pass
    tries = state.get("pages_tries") or {}
    given_up = []
    for pid in missed:
        tries[str(pid)] = tries.get(str(pid), 0) + 1
        if tries[str(pid)] >= PAGE_TRIES:
            given_up.append(pid)
    if missed:
        state["pages_tries"] = {k: v for k, v in tries.items() if int(k) not in given_up}
        if given_up:
            state["pages_skipped"] = sorted(set(state.get("pages_skipped", [])) | set(given_up))
        common.write_json(gather.GATHER_STATE, state)
    failed -= len(given_up)
    line = (f"{came_back} PDF page(s) back in line, " if came_back else "") + f"{read} page(s) read" + (f", {len(skipped)} passed over" if skipped else "") +         (f", {len(given_up)} passed over after {PAGE_TRIES} tries with nothing read" if given_up else "")
    if failed:
        return False, f"{line}, {failed} page(s) could not be read and will be tried again"
    return True, line


# --- step 2: pictures sent by text, the engine's own step --------------------------
def _own_prompts(*names):
    """The engine's steps read their prompts from one folder. Hand them the live system's own
    general prompts, with the owner's name and description filled in, in place of the stock ones."""
    folder = os.path.join(common.paths.STATE, "prompts")
    os.makedirs(folder, exist_ok=True)
    for name in names:
        with open(os.path.join(folder, f"{name}.md"), "w", encoding="utf-8") as f:
            f.write("The live system's own prompt, filled in for this owner.\n---\n" + _prompt(name))
    common.paths.PROMPTS = folder


def describe_texted():
    if not gather.texted_images_waiting():
        return True, "no texted pictures waiting"
    _own_prompts("describe")
    line = ai_steps.describe(_current["pass"])
    return not line.startswith("FAILED"), line


# --- step 2b: the cheaper first sort (the owner's choice in Settings, off unless they switch it on) ----------
FAST_MODEL = "haiku"
FAST_MOST = 150


# what the first sort reads of each message, in first_sort_input's order (the grader's dry run reads the same, grader.py)
FIRST_SORT_SEES = """m.id, m.channel, m.from_key, m.subject, substr(m.body, 1, 3000),
                  (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL)"""


def first_sort_input(rows):
    """The first sort's payload from (id, channel, from_key, subject, body, name) rows (FIRST_SORT_SEES)."""
    return {"messages": [{"id": i, "channel": ch, "from": name or str(fk).split(":", 1)[-1], "subject": subj,
                          "says": cleantext.new_text(body or "", limit=500, subject=subj or "")}
                         for i, ch, fk, subj, body, name in rows]}


def first_sort_prompt(path, owner_filter=None):
    """The first sort's instructions for the payload at path; owner_filter: the owner's lines, his live ones unless given."""
    return _prompt("first_sort", PAYLOAD_PATH=path, OWNER_FILTER=_owner_filter() if owner_filter is None else owner_filter)


def fast_sort_on():
    return (common.settings().get("thinking") or {}).get("fast_sort") == "on"


def first_sort():
    """The fastest model sets aside what is plainly nothing; everything else is left for the judge.
    The mechanical holds run first, so it only sees what they left. A sender the owner knows (a contact,
    someone they wrote to, their own domain, someone who always gets through) is never set aside here."""
    if common.paths.CORE not in sys.path:
        sys.path.insert(0, common.paths.CORE)
    import judgment_payload as jp
    jp.prefilter_noise()
    guarded = jp.junk_guard()
    bound, upto = common.until_sql()
    rows = [r for r in db.query(
        f"""SELECT {FIRST_SORT_SEES}
           FROM messages m WHERE m.direction = 'in' AND NOT EXISTS
             (SELECT 1 FROM answered a WHERE a.domain='judged' AND a.key = 'msg:' || m.id)""" + bound + " ORDER BY m.id", tuple(upto))
            if not guarded(r[2])][:FAST_MOST]
    if not rows:
        return True, "nothing for the first sort"
    path = os.path.join(common.paths.STATE, "live_fast_payload.json")
    out = os.path.join(common.paths.STATE, "live_fast_out.json")
    common.write_json(path, first_sort_input(rows))
    res = ai_steps.agent(first_sort_prompt(path), FAST_MODEL, out)
    if not res.ok:
        return True, f"the first sort did not run ({res.why}); everything is left for the careful reading"
    owed = {r[0] for r in rows}
    n = 0
    for e in (common.read_json(out, {}) or {}).get("nothing") or []:
        if isinstance(e, dict) and e.get("id") in owed and str(e.get("reason") or "").strip():
            db.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) SELECT 'judged', ?, 'noise', ?, now()"
                       " WHERE NOT EXISTS (SELECT 1 FROM answered a WHERE a.domain='judged' AND a.key = ?)",
                       (f"msg:{e['id']}", "fast: " + " ".join(str(e["reason"]).split())[:180], f"msg:{e['id']}"))
            owed.discard(e["id"])
            n += 1
    return True, f"first sort: {n} of {len(rows)} hidden, {len(rows) - n} left for the careful reading"


# --- step 3: the engine's judge ----------------------------------------------------
# what the judging call is shown of the engine's payload; anything else the engine adds is taken out
JUDGE_SEES = ("days", "goals", "reference", "active_rules", "conversations", "messages", "documents", "calendar",
              "open_tasks", "already_settled")


def judge_view(payload):
    """The engine's payload cut down to what the judging call is shown (JUDGE_SEES), without the engine's own notes."""
    seen = {k: v for k, v in payload.items() if k in JUDGE_SEES}
    if isinstance(seen.get("active_rules"), list):       # the engine's own notes to its judge are not rules
        seen["active_rules"] = [r for r in seen["active_rules"] if not (isinstance(r, dict) and r.get("id") is None)]
    return seen


def judge_prompt(payload, owner_filter=None, cards=False):
    """The judging call's instructions for the payload at that path, with the areas and key prefixes from the owner's
    personal settings; owner_filter: the owner's lines, his live ones unless given. cards: the run also writes the card of
    every matter it leaves open (one brain); the grader's dry runs judge only."""
    me = common.personal()
    areas = [a for a in me.get("areas") or [] if a] or ["Personal", "System"]
    prefixes = [p for p in me.get("key_prefixes") or [] if p] or ["personal::", "system::"]
    return _prompt("judge", PAYLOAD_PATH=payload, TODAY=common.ai_today().strftime("%A, %B %d, %Y"),
                   AREAS=", ".join(areas), KEY_PREFIXES=", ".join(prefixes), CARDS=brain_spec() if cards else "",
                   OWNER_FILTER=_owner_filter() if owner_filter is None else owner_filter)


# --- one brain: the judging run writes the cards (the judgment rebuild, phase 2) ----------------------------------
BRAIN_SAYS = """ONE UNDERSTANDING: you also write the card {OWNER} sees for every matter you leave open, from the same reading that made its verdict, so what you decided, what you recommend, what you ask and the buttons always agree.
Add "cards" to the same file: one entry for every item_key that a "task" verdict names or a task_update leaves at needs_me or waiting_them, and for no other, each `{"item_key": "<that key>", ...the card's fields below}`.
The payload's `cards_now` holds each open matter that already has a card: its key, the card's open questions (`open_asks`), what {OWNER} already answered or decided on it and what was done (`history`, `latest_answer`); never ask again what those answer. `important_list` is what deserves a phone notification. A message's or a card's `owner_last_time` is what {OWNER} did on the last card like it (the same sender) instead of the pick: when it answers the card's first question it is one of your `choices`, word for word; weigh it for the `pick`.
THE CARD'S FIELDS, as the card writer's own instructions give them (where they say an entry in `items`, read the card you write):
"""


def brain_spec():
    """The cards part of the judging instructions: BRAIN_SAYS, then the card's fields and the writing rules exactly as the card
    writer has them (prompts/items.md), so the two never drift apart. The card writer's own bookkeeping (an item's id, joining
    two items, answering every entry) is left out: a judged card is named by its item_key."""
    with open(os.path.join(common.PROMPTS, "items.md"), encoding="utf-8") as f:
        text = f.read()
    a, b = text.index("For every entry in `items`, write:"), text.index("For every entry in `loose_messages`")
    r, w = text.index("\nRules:"), text.index("\nWrite one JSON file")
    fields = [ln for ln in text[a:b].splitlines()[1:] if not ln.startswith(("- `id`:", "- `same_matter_as`:"))]
    rules = [ln for ln in text[r:w].strip().splitlines() if "must be answered exactly once" not in ln]
    me = common.personal()
    return (BRAIN_SAYS + "\n".join(fields).strip() + "\n\n" + "\n".join(rules)).replace("{OWNER}", common.owner()).replace(
        "{ABOUT}", str(me.get("about") or "").strip())


def _sender_of(ids):
    """The outside sender behind these messages, as items.sender_for names one, or None."""
    con = db.reader() or db.connect(read_only=True)
    try:
        return items.sender_for(con, ids)
    finally:
        if con is not db.reader():
            con.close()


def _last_time_label(sender, area=None, kind=None):
    """What he did instead of the pick on the last card like this one, as its button's words, or None."""
    try:
        import picks
        h = picks.habit({"sender": sender, "area": area, "kind": kind})
        return h["label"] if h else None
    except Exception as e:  # noqa: BLE001  one hint less never costs a card
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"pick habit: {type(e).__name__}: {e}")
        return None


def brain_context(seen):
    """What the judging run needs beyond the judge's own payload to write the cards: the open matters' cards (cards_now),
    the notification list, and on each message from outside what he did last time on a card from that sender."""
    keys = {str(t.get("key")) for t in seen.get("open_tasks") or [] if t.get("key")}
    have = {r["source_key"][5:]: r for r in items.rows("state <> 'done' AND starts_with(source_key, 'task:')")
            if r["source_key"][5:] in keys} if keys else {}
    now_cards = []
    with db.reading():
        for k, r in have.items():
            e = {"key": k, "card": r["id"], "title": r["title"], "state": r["state"], "open_asks": list(r.get("asks") or []),
                 "history": _history(r), "latest_answer": r.get("answer")}
            lt = _last_time_label(_sender_of(r["source_messages"]), r.get("area"), r.get("kind"))
            if lt:
                e["owner_last_time"] = lt
            now_cards.append(e)
    msgs = []
    for m in seen.get("messages") or []:
        lt = _last_time_label({"key": str(m.get("from")).strip().lower()}) if m.get("direction") == "in" and m.get("from") else None
        msgs.append(dict(m, owner_last_time=lt) if lt else m)
    return {"cards_now": now_cards, "important_list": common.important_lines(), "messages": msgs}


def _brain_keys(doc):
    """The item keys the verdicts leave open: each a "task" verdict names, or a task_update leaves at needs_me or waiting_them."""
    keys = set()
    for v in doc.get("verdicts") or []:
        t = v.get("task") if isinstance(v, dict) else None
        if isinstance(t, dict) and v.get("disposition") == "task" and str(t.get("item_key") or "").strip():
            keys.add(str(t["item_key"]).strip())
    for u in doc.get("task_updates") or []:
        k = str((u or {}).get("item_key") or "").strip() if isinstance(u, dict) else ""
        if k:
            (keys.add if u.get("status") in OPEN_STATUSES else keys.discard)(k)
    return keys


def _brain_cards(doc, seen):
    """The judged cards that pass the card guardrails, by item key, with the message ids each may cite; and the problems."""
    keys = _brain_keys(doc)
    given = {str(m["id"]) for m in seen.get("messages") or []}
    have = {r["source_key"][5:]: r for r in items.rows("starts_with(source_key, 'task:')") if r["source_key"][5:] in keys} if keys else {}
    good, problems, named = {}, [], set()
    for n, c in enumerate(doc.get("cards") or []):
        k = str(c.get("item_key") or "").strip() if isinstance(c, dict) else ""
        if k not in keys:
            problems.append(f"card {n + 1}: item_key {k!r} is not a matter your verdicts or task_updates leave open")
            continue
        named.add(k)
        known = given | {str(x) for x in (have.get(k) or {}).get("source_messages") or []}
        p = _checked(c, known, f"card {k}")
        if p:
            problems += p
            continue
        good[k] = {"card": c, "known": sorted(known), "at": common.now().isoformat(timespec="seconds")}
    problems += [f"{k}: no card was written for it" for k in sorted(keys - named)]
    return good, problems


def take_brain_cards(res, verdicts, seen):
    """After the verdicts are committed: the cards the same run wrote, checked; refused ones go back to that run once per
    fix allowed (the verdicts stay as committed); the good ones wait in BRAIN_CARDS for the write step. One line for the step."""
    doc = common.read_json(verdicts, {}) or {}
    good, problems = _brain_cards(doc if isinstance(doc, dict) else {}, seen)
    for _ in range(ai_steps.COMMIT_FIXES):
        if not problems or not res.ok:
            break
        ai_steps.fix(res, "Your verdicts are committed; leave them exactly as they are. Only these cards were refused. Fix exactly"
                          " these, nothing else, and rewrite the same file.\n\n" + "\n".join(problems), model())
        doc = common.read_json(verdicts, {}) or {}
        good, problems = _brain_cards(doc if isinstance(doc, dict) else {}, seen)
    if good:
        kept = common.read_json(BRAIN_CARDS, {}) or {}
        kept.update(good)
        common.write_json(BRAIN_CARDS, kept)
    line = f"{len(good)} card(s) written with the verdicts"
    if problems:
        line += f"; {len(problems)} refused, left for the card writer ({'; '.join(problems)[:200]})"
    return line


def judge():
    """The live system's own judging. The engine's scripts gather the payload and commit the
    verdicts; the thinking is done with the live system's general prompt, the areas come from the
    owner's personal settings, and the payload is cut down to what a general assistant judges by."""
    parts, failed, rest = [], "", ""
    # a round's size: smaller after a round timed out (10/15/26: 142 messages timed out twice), back to full once the
    # backlog is judged; kept in a file so the next check goes on at the smaller size
    size_file = os.path.join(common.paths.STATE, "judge_round.json")
    size = int((common.read_json(size_file, {}) or {}).get("messages") or 0) or None
    for round_no in range(1, ai_steps.MAX_JUDGMENT_ROUNDS + 1):
        if round_no > 1 and not limits.enough(JUDGE_ROUND + WRITE_RESERVE):
            # the rest of a backlog waits: what this pass judged gets its cards first (11/22: rounds took the whole pass)
            rest = f"the rest waits for the next check, {OUT_OF_TIME} for another round"
            break
        ok, out = ai_steps.script(ai_steps._a("judgment_payload.py"), *(["--round-messages", str(size)] if size else []))
        if not ok:
            failed = f"FAILED: the judging payload could not be made: {out[:400]}"
            break
        payload = ai_steps._payload_path(out)
        if not payload or re.search(r": 0 messages in", out):
            break
        seen = common.read_json(payload, None)
        if isinstance(seen, dict):
            seen = judge_view(seen)
            seen.update(brain_context(seen))        # one brain: what the same run needs to write the cards
            with open(payload, "w", encoding="utf-8") as f:
                json.dump(seen, f, ensure_ascii=False, indent=1, default=str)
        verdicts = os.path.join(os.path.dirname(payload), os.path.basename(payload).replace("payload_", "verdicts_"))
        res = ai_steps.agent(judge_prompt(payload, cards=True), model(), verdicts)
        commit = lambda: ai_steps.script(ai_steps._a("judgment_commit.py"), verdicts, "--run-id", _current["pass"])  # noqa: E731
        ai_steps.commit_with_fixes(res, commit, model(), "The commit refused your verdicts. Fix exactly these, "
                                   "nothing else, and rewrite the same file.", "judgment commit")
        said = take_brain_cards(res, verdicts, seen) if res.ok and isinstance(seen, dict) else ""
        parts.append(res.line(f"round {round_no}") + (f" ({said})" if said else ""))
        given = len(seen.get("messages") or []) if isinstance(seen, dict) else 0
        if not res.ok and str(res.why or "").startswith("timed out") and given > JUDGE_SMALLEST:
            # too much for one Claude run: the same messages again in smaller rounds, never a stuck day
            size = max(JUDGE_SMALLEST, given // 2)
            common.write_json(size_file, {"messages": size, "since": common.now().isoformat(timespec="seconds")})
            parts.append(f"next rounds take at most {size} messages")
            continue
        if not res.ok:
            failed = "FAILED: " + "; ".join(parts)
            break
        if "OVER CAP" not in out:
            if size:
                common.write_json(size_file, {})
            break
    else:
        if parts and not failed:
            rest = f"the rest waits for the next check after {ai_steps.MAX_JUDGMENT_ROUNDS} rounds"
    line = failed or "; ".join(parts + ([rest] if rest else [])) or "nothing to judge: every message carries a verdict"
    if failed:
        return False, line
    if rest:        # stopped on purpose with some left: not a failure (a failure waits RETRY_AFTER_MINUTES)
        return OUT_OF_TIME not in rest, line
    return not gather.unjudged(), line


def _owner_filter(lines=None):
    """The owner's filter settings and rules as plain lines for the sorting and writing instructions (lines: the sorting
    lines to say, filters.lines_for_sorting() unless given)."""
    import filters
    return "\n".join("- " + x if not x.startswith("  ") else x for x in (filters.lines_for_sorting() if lines is None else lines))


# --- step 4: write the items --------------------------------------------------------
def _message(mid, whole=False):
    row = db.query(
        """SELECT m.id, m.channel, m.account, m.ts, m.direction, m.from_key, m.to_keys, m.subject, m.body,
                  (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL)
           FROM messages m WHERE m.id=?""", (int(mid),))
    if not row:
        return None
    i, channel, account, ts, direction, from_key, to_keys, subject, body, name = row[0]
    pages = db.query(
        """SELECT a.original_filename, p.page_no, p.text FROM documents d
           JOIN pages p ON p.document_id = d.id LEFT JOIN attachments a ON a.id = d.attachment_id
           WHERE d.message_id=? AND coalesce(p.text,'') <> '' ORDER BY d.id, p.page_no LIMIT 12""", (i,))
    contact = ""
    if direction == "in":
        try:
            import contact_strength
            c = db.reader() or db.connect(read_only=True)      # the batch's one reading connection when there is one
            try:
                contact = contact_strength.for_message(c, i)["words"]
            finally:
                if c is not db.reader():
                    c.close()
        except Exception:  # noqa: BLE001  one fact less never costs the card
            contact = ""
    return {"id": i, "channel": channel, "mailbox": account, "when": ts.isoformat(timespec="minutes"),
            "sender_contact": contact or None,
            "direction": direction, "from": common.owner() if direction == "out" else (name or from_key),
            "from_address": from_key, "to": to_keys, "subject": subject,
            "says": (cleantext.clean_body(body or "", limit=BODY_LIMIT) if whole
                     else cleantext.new_text(body or "", limit=BODY_LIMIT, subject=subject or "")),
            "attachments": [{"file": f, "page": n, "text": (t or "")[:PAGE_LIMIT]} for f, n, t in pages]}


def loose_mail(new_ids):
    """New mail with no item yet: messages judged this pass that came in from
    someone else, rest on no item at all, and were not judged as needing
    nothing. Newest first, every one of them: there is no limit."""
    if not new_ids:
        return []
    marks = ",".join("?" for _ in new_ids)
    quiet = ",".join("?" for _ in QUIET_VERDICTS)
    got = [r[0] for r in db.query(
        f"""SELECT m.id FROM messages m JOIN answered a ON a.domain='judged' AND a.key = 'msg:' || m.id
            WHERE m.id IN ({marks}) AND m.direction = 'in' AND a.verdict NOT IN ({quiet})
            ORDER BY m.id DESC""", (*[int(i) for i in new_ids], *QUIET_VERDICTS))]
    if not got:
        return []
    in_items = {m for (sm,) in db.query("SELECT source_messages FROM live_items") for m in json.loads(sm or "[]")}
    return [i for i in got if str(i) not in in_items]


HISTORY_LINES = 12        # the newest lines of an item's history the item writer is shown
SETTLED = re.compile(r'^Answered by you: "(.+)" \(')


def _history(r):
    """The newest lines of what the owner said and the assistant did on an item."""
    return [x for x in (r.get("assistant_did") or "").split("\n") if x.strip()][-HISTORY_LINES:]


def _settled_asks(r):
    """The item's questions its history records as answered by the owner and not since asked again."""
    import answers
    return set(answers.settled_in_force(r.get("assistant_did")))


def _drop_settled(asks, r):
    """The writer's questions without any the owner already answered on this item."""
    done = {a.lower() for a in _settled_asks(r)}
    return [a for a in asks or [] if str(a).strip().lower() not in done]


def _reopened(e, r):
    """The answered questions new information on this item opens again (the writer's `reopen`): each one the owner
    settled here, as his history words it. A question of a card of several is its own small card: it comes back like one."""
    done = {a.lower(): a for a in _settled_asks(r)}
    return [done[str(q).strip().lower()] for q in e.get("reopen") or [] if isinstance(q, str) and str(q).strip().lower() in done]


def _item_entry(r, new_set):
    """One item as the item writer sees it, with the owner's earlier answers on it, and what he did on the last card like it
    when it wasn't my pick (picks.last_time: by its sender, as items.sender_for names one, else its area and kind)."""
    msgs = [m for m in (_message(i, whole=r.get("status") == "Shown at your asking") for i in r["source_messages"][:6]) if m]
    out = {"id": r["id"], "area": r["area"], "kind": r["kind"], "state": r["state"],
           "title": r["title"], "detail": r["detail"], "has_draft_waiting": bool(r["draft"]),
           "open_asks": list(r.get("asks") or []),
           "history": _history(r),
           "latest_answer": r.get("answer"),
           "new_message_ids": sorted(new_set & set(r["source_messages"])),
           "messages": msgs}
    try:
        import picks
        who = next((m["from_address"] for m in sorted(msgs, key=lambda m: m["when"], reverse=True)
                    if m["direction"] == "in" and m["channel"] in ("email", "sms") and m.get("from_address")), None)
        lt = picks.last_time(dict(r, sender={"key": str(who).strip().lower()} if who else None))
        if lt:
            out["owner_last_time"] = lt["label"]
    except Exception as e:  # noqa: BLE001  one hint less never costs the card
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"pick last time: {type(e).__name__}: {e}")
    return out


left = {"ran": False, "items": [], "msgs": []}      # what the last write_items did not get to


def write_items(touched, new_ids, forced=()):
    """touched: item ids made or changed this pass. new_ids: the messages
    judged this pass. Only items resting on a new message are written, and
    new mail with no item yet is placed. Everything owed is worked, in batches
    of one Claude run each; what a batch could not do (no time left, or the run
    failed) is named in `left` and is the next pass's first work."""
    new_set = {str(i) for i in new_ids}
    rows = {r["id"]: r for r in items.rows("state <> 'done'")}
    work = [rows[i] for i in touched if i in rows and new_set & set(rows[i]["source_messages"])]
    work += [rows[i] for i in sorted(set(forced)) if i in rows and rows[i] not in work]      # owed a full writing
    import mods
    work = [r for r in work if not mods.owns(r)]          # a mod's own cards are written by the mod, never here
    import presses
    work = [r for r in work if not presses.is_junk_ask(r)]  # the junk question is the engine's own words, never rewritten
    import rsi_loop
    work = [r for r in work if not rsi_loop.is_card(r)]     # a rule change card: only its own buttons change it
    import wouldhide
    work = [r for r in work if not wouldhide.is_card(r)]    # an "I'd hide this" card is the program's own one line
    work, judged = put_brain_cards(work)        # one brain: the cards the judging run wrote, put on with no Claude run
    loose = loose_mail(new_ids)
    left.update(ran=True, items=[], msgs=[])
    said = f"{judged} card(s) from the judging run put on; " if judged else ""
    if not work and not loose:
        return True, (said + "the card writer was not needed") if judged else "no item needed writing"
    with open(common.paths.GOALS, encoding="utf-8") as f:
        goals = f.read()
    w = [work[n:n + ITEM_BATCH] for n in range(0, len(work), ITEM_BATCH)]
    m = [loose[n:n + LOOSE_BATCH] for n in range(0, len(loose), LOOSE_BATCH)]
    batches = [(w[k] if k < len(w) else [], m[k] if k < len(m) else []) for k in range(max(len(w), len(m)))]
    wrote = placed = 0
    for k, (some, mail) in enumerate(batches):
        why_not = ""
        if k and not limits.enough(150):
            why_not = "not enough time left in this check"
        else:
            ok, said = _write_batch(some, mail, new_set, goals)
            if not ok:
                why_not = said
        if why_not:
            rest_items = [r for b in batches[k:] for r in b[0]]
            rest_mail = [i for b in batches[k:] for i in b[1]]
            left["items"] = [r["id"] for r in rest_items]
            left["msgs"] = sorted({int(x) for r in rest_items for x in new_set & set(r["source_messages"])} | set(rest_mail))
            line = (f"{said}{wrote} item(s) written, {placed} new message(s) placed in {k} Claude run(s); "
                    f"{len(rest_items)} item(s) and {len(rest_mail)} message(s) wait for the next check: {why_not}")
            return (not k or "time left" in why_not) and "time left" in why_not, line
        wrote, placed = wrote + len(some), placed + len(mail)
        brain["writer"] += len(some)
    return True, f"{said}{wrote} item(s) written, {placed} new message(s) placed in {len(batches)} Claude run(s)"


def _write_batch(work, loose, new_set, goals, picked=()):
    """One Claude run: these items written, these loose messages placed. (ok, why not). A rule change card is not among
    the open cards the writer is shown or may attach a message to or join (rsi_loop.is_card), nor is an "I'd hide this" card
    (wouldhide.is_card). picked: loose messages the owner pressed Card on (mail_card.py); the writer may not skip them."""
    import rsi_loop
    import wouldhide
    rows = {r["id"]: r for r in items.rows("state <> 'done'") if not rsi_loop.is_card(r) and not wouldhide.is_card(r)}
    with db.reading():          # one connection for every message read below, never three opens per message
        entries = [_item_entry(r, new_set) for r in work]
        loose_msgs = [m for m in (_message(i) for i in loose) if m]
    for m in loose_msgs:
        if m["id"] in picked:
            m["asked_for_card"] = True
        if m["direction"] == "in" and m.get("from_address"):
            lt = _last_time_label({"key": str(m["from_address"]).strip().lower()})
            if lt:
                m["owner_last_time"] = lt
    payload = {
        "today": common.ai_today().strftime("%A, %B %d, %Y"),
        "goals": goals,
        "important_list": common.important_lines(),
        "items": entries,
        "loose_messages": loose_msgs,
        "open_items": [{"id": r["id"], "area": r["area"], "title": r["title"]} for r in rows.values()
                       if r["id"] not in {w["id"] for w in work}],
    }
    path = os.path.join(common.paths.STATE, "live_items_payload.json")
    out = os.path.join(common.paths.STATE, "live_items_out.json")
    common.write_json(path, payload)
    res = ai_steps.agent(_prompt("items", PAYLOAD_PATH=path, OWNER_FILTER=_owner_filter()), write_model(), out)
    if not res.ok:
        return False, f"item writer failed: {res.why}"
    rows = {r["id"]: r for r in items.rows("state <> 'done'") if not rsi_loop.is_card(r) and not wouldhide.is_card(r)}
    problems = _commit_items(common.read_json(out, {}), payload, rows)
    for _ in range(ai_steps.COMMIT_FIXES):
        if not problems:
            break
        ai_steps.fix(res, "Your output was refused. Fix exactly these, nothing else, and rewrite the"
                          " same file.\n\n" + "\n".join(problems), write_model())
        if not res.ok:
            return False, f"item writer failed on the fix: {res.why}"
        problems = _commit_items(common.read_json(out, {}), payload, rows)
    if problems:
        return False, "item writer output refused: " + "; ".join(problems)[:240]
    return True, ""


def _checked(entry, known_msgs, label, new=False, loose=None):
    """Problems with a written card, by the guardrails (rules\rulebook.py, guard a): each names its rule."""
    rulebook = common.rulebook()
    ctx = {"message_ids": sorted(known_msgs), "new": new}
    if loose is not None:
        ctx["loose_ids"] = sorted(loose)
    v = rulebook.check_card(entry, ctx)
    return [f"{label}: rule {b['rule']}: {b['says']}" for b in v["broken"]]


def _commit_items(out, payload, rows):
    """Check the whole output, then write it. Returns problems; writes nothing
    when there are any."""
    problems = []
    owed = {e["id"]: e for e in payload["items"]}
    loose_owed = {m["id"] for m in payload["loose_messages"]}
    asked = {m["id"] for m in payload["loose_messages"] if m.get("asked_for_card")}
    known = {str(m["id"]) for e in payload["items"] for m in e["messages"]} | {str(i) for i in loose_owed}
    got = {e.get("id"): e for e in out.get("items") or []}
    for iid in owed:
        if iid not in got:
            problems.append(f"item {iid} was not answered")
        else:
            problems += _checked(got[iid], known, iid)
    for iid in got:
        if iid not in owed:
            problems.append(f"{iid} is not an item you were given")
        other = str((got[iid] or {}).get("same_matter_as") or "").strip()
        if other and (other == iid or other not in rows):
            problems.append(f"{iid}: same_matter_as {other} is not another open item")
    placed = set()
    for n, e in enumerate(out.get("new_items") or []):
        ids = {int(i) for i in e.get("messages") or [] if str(i).isdigit()}
        problems += _checked(e, known, f"new item {n + 1}", new=True, loose=loose_owed)
        placed |= ids
    for e in out.get("loose") or []:
        mid = e.get("message")
        if mid not in loose_owed:
            problems.append(f"loose message {mid} is not one you were given")
        elif e.get("attach_to") and e["attach_to"] not in rows:
            problems.append(f"loose message {mid}: {e['attach_to']} is not an open item")
        elif not e.get("attach_to") and not e.get("skip"):
            problems.append(f"loose message {mid}: needs attach_to or skip")
        elif not e.get("attach_to") and mid in asked:
            problems.append(f"loose message {mid}: asked_for_card, so it is never skipped: attach it or make it a new item")
        placed.add(mid)
    for mid in loose_owed - placed:
        problems.append(f"loose message {mid} was not answered")
    if problems:
        return problems

    # the contact rule (people.py): a question for a detail that is on file is
    # never written; one that fits several people names them
    import people
    import answers
    for e in list(got.values()) + list(out.get("new_items") or []):
        people.settle_entry(e)
    pid = _current["pass"]
    for iid, e in got.items():
        _grow(e, rows[iid]["source_messages"], rows[iid].get("area"), rows[iid].get("kind"))
        # a question the owner already answered on this item is never shown again as open
        asks = _drop_settled(e.get("asks"), rows[iid])
        if len(asks) < len(e.get("asks") or []):
            e["asks"] = asks
            if not asks and e["state"] == "question" and not rows[iid]["draft"]:
                e["state"] = "in_motion"
        again = _reopened(e, rows[iid])
        if again:       # new information opens an answered question again, and with it the card
            e["asks"] = list(e.get("asks") or []) + [q for q in again if q.lower() not in {str(a).lower() for a in e.get("asks") or []}]
            e["state"] = "question"
            items.update(iid, pid, assistant_did=answers.reopen_line(rows[iid].get("assistant_did"), again, common.now()))
        # a card left with the owner names the one thing to decide or do, or says nothing is needed
        answers.name_what_is_needed(e, items.lift(dict(rows[iid])))
        plain = (e.get("detail") or "").strip()
        cal = e.get("calendar") if isinstance(e.get("calendar"), dict) and e["calendar"].get("title") else None
        if str(e.get("area") or "").strip() and e["area"].strip() != rows[iid]["area"]:
            items.update(iid, pid, area=e["area"].strip())
        items.update(iid, pid, title=e["title"].strip(), short_header=card.whole(e.get("header")) or None,
                     recommended=e.get("recommended"),
                     **({"detail": plain} if plain else {}),
                     **({"calendar": {k: cal.get(k) for k in ("title", "date", "start", "end", "all_day",
                                                              "certain", "location")}} if cal else {}),
                     asks=e.get("asks") or [], evidence=e["evidence"], state=e["state"],
                     **({"why": card.whole(e["why"])} if str(e.get("why") or "").strip() else {}),
                     importance=1 if e.get("important") else rows[iid]["importance"],
                     important_reason=e.get("important_reason") if e.get("important")
                     else rows[iid]["important_reason"],
                     **({"kind": "question"} if e["state"] == "question" and not rows[iid]["draft"]
                        and rows[iid]["kind"] in ("task", "waiting") else {}))
    now = common.now()
    import dates
    for e in out.get("new_items") or []:
        answers.name_what_is_needed(e)
        dates.store_fields(e)
        ids = sorted({int(i) for i in e["messages"]}, reverse=True)
        _grow(e, ids, e.get("area"), e.get("kind"))
        m = _message(ids[0])
        ts = dt.datetime.fromisoformat(m["when"])
        ref = f"{m['from']}, {m['channel']}, {ts.month}/{ts.day} {ts.strftime('%I:%M %p').lstrip('0')} ({m['id']})"
        con = db.connect()
        try:
            iid = "L" + str(con.execute("SELECT nextval('seq_live_item')").fetchone()[0])
            con.execute(
                f"INSERT INTO live_items ({', '.join(items.BASE_COLUMNS)}) VALUES"
                f" ({', '.join('?' for _ in items.BASE_COLUMNS)})",
                (iid, f"live:msg-{min(ids)}", e["kind"], e["area"].strip(), e["title"].strip(),
                 e.get("detail"), e["state"], 1 if e.get("important") else 0,
                 e.get("important_reason") if e.get("important") else None, m["from"], ts, ref,
                 json.dumps([str(i) for i in ids]), e.get("recommended"), json.dumps(e.get("asks") or []),
                 None, e["evidence"], "[]", None, None, None, None, None, now, now, now, None, pid))
        finally:
            con.close()
        if str(e.get("why") or "").strip() or str(e.get("header") or "").strip():
            items.update(iid, pid, why=card.whole(e.get("why")) or None, short_header=card.whole(e.get("header")) or None)
        w = items.card_extras(e)
        if w:
            items.update(iid, pid, **w)
    for iid, e in got.items():           # one matter on two cards: this one goes into the other, which is written afresh
        other = str(e.get("same_matter_as") or "").strip()
        if other and items.join(iid, other, pid):
            continue
    for iid, e in got.items():           # what a card someone else owes waits on, and when to look again
        w = items.card_extras(e, rows[iid].get("extra"), answered=True)       # written afresh: an old come-back note goes
        if str(rows[iid].get("status") or "").startswith("Back:"):
            w["status"] = None
        if w:
            items.update(iid, pid, **w)
    for e in out.get("loose") or []:
        if e.get("skip") and not e.get("attach_to"):
            db.execute("UPDATE answered SET verdict='ignore', source=?, covered=NULL, leaned_on=NULL"     # no stale judge's mark
                       " WHERE domain='judged' AND key=?",
                       (str(e["skip"])[:200], f"msg:{e['message']}"))
        if e.get("attach_to"):
            r = rows[e["attach_to"]]
            mids = [str(e["message"])] + [x for x in r["source_messages"] if x != str(e["message"])]
            note = (e.get("note") or "").strip()
            # what it adds goes in the card's history; the story stays short
            items.update(r["id"], pid, source_messages=mids,
                         assistant_did=answers.note_in_history(r.get("assistant_did"), note))
    import picks            # the pick's share of the writer's output, for the pass log (picks.cost_line)
    written = list(got.values()) + list(out.get("new_items") or [])
    mine = [e["pick"] for e in written if isinstance(e.get("pick"), dict)]
    picks.note_written(len(mine), sum(len(json.dumps(p, ensure_ascii=False)) for p in mine), len(written))
    return []


def _grow(e, message_ids, area, kind):
    """The choices grow: what he did instead of the pick on the last card from this sender (else of this area and kind) becomes
    one of this card's choices (picks.grow). Never raises."""
    try:
        import picks
        picks.grow(e, {"sender": _sender_of(message_ids), "area": area, "kind": kind})
    except Exception as ex:  # noqa: BLE001  one choice less never costs the card
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"pick grow: {type(ex).__name__}: {ex}")


def put_brain_cards(work):
    """One brain: each card the judging run wrote goes on its item here, through the same checks and writing as the card
    writer's (_commit_items), with no Claude run. Returns (the items left for the card writer, how many were put on). A judged
    card refused here leaves its item to the card writer; one whose item is not open is let go after BRAIN_KEEP_HOURS."""
    kept = common.read_json(BRAIN_CARDS, {}) or {}
    if not kept:
        return work, 0
    import mods
    import presses
    import rsi_loop
    import wouldhide
    rows = {r["id"]: r for r in items.rows("state <> 'done'") if not rsi_loop.is_card(r) and not wouldhide.is_card(r)}
    by_key = {r["source_key"][5:]: r for r in rows.values() if str(r["source_key"]).startswith("task:")
              and not mods.owns(r) and not presses.is_junk_ask(r)}
    put, rest = 0, {}
    for k, v in kept.items():
        r = by_key.get(k)
        if not r:
            try:
                young = (common.now() - dt.datetime.fromisoformat(v.get("at"))).total_seconds() < BRAIN_KEEP_HOURS * 3600
            except (TypeError, ValueError):
                young = False
            if young:
                rest[k] = v
            continue
        entry = {x: y for x, y in (v.get("card") or {}).items() if x != "item_key"}
        entry["id"] = r["id"]
        mids = sorted({str(x) for x in r["source_messages"]} | {str(x) for x in v.get("known") or []})
        payload = {"items": [{"id": r["id"], "messages": [{"id": x} for x in mids]}], "loose_messages": []}
        problems = _commit_items({"items": [entry], "new_items": [], "loose": []}, payload, rows)
        if problems:
            common.log_line(os.path.join(common.LOGS, "errors.log"),
                            f"judged card for {r['id']} refused, the card writer writes it: {'; '.join(problems)[:300]}")
            if r["id"] not in {w["id"] for w in work}:
                work = work + [r]
            continue
        put += 1
        work = [w for w in work if w["id"] != r["id"]]
    common.write_json(BRAIN_CARDS, rest)
    brain["judged"] += put
    return work, put


# --- the pass ------------------------------------------------------------------------
def rewrite(ids, pass_id):
    """Write the named items afresh from all their messages (used once after
    seeding, so day-one items read in plain words)."""
    _current["pass"] = pass_id
    rows = {r["id"]: r for r in items.rows("state <> 'done'")}
    ids = [i for i in ids if i in rows and rows[i]["source_messages"]]
    msgs = sorted({int(m) for i in ids for m in rows[i]["source_messages"][:6]})
    return _step("write items", lambda: write_items(ids, msgs))


def resting(g):
    """The steps that failed in the last think pass and rest for RETRY_AFTER_MINUTES, nothing new having come since. Only
    the step that failed rests: cards owed for mail already judged are written even while a failed judge waits (on 11/22
    a failed judge held back the cards of 173 judged messages for an hour)."""
    last = common.read_json(common.THINK_STATE) or {}
    if not last.get("failed_at") or g["new_messages"] or g["new_attachments"]:
        return set()
    if (common.now() - dt.datetime.fromisoformat(last["failed_at"])).total_seconds() / 60 >= RETRY_AFTER_MINUTES:
        return set()
    failed = {s.get("step") for s in last.get("last") or [] if isinstance(s, dict) and not s.get("ok")}
    if "judge" in failed:
        failed.add("first sort")
    return failed or {"read pages", "describe texted pictures", "first sort", "judge", "write items"}


def needed(g):
    """Why a think pass should run now, or None."""
    reasons = []
    last = common.read_json(common.THINK_STATE) or {}
    rest = resting(g)
    if (last.get("pending_items") or last.get("pending_msgs")) and "write items" not in rest:
        reasons.append("items left unwritten by the last think check")
    if last.get("rewrite_items") and "write items" not in rest:
        reasons.append(f"{len(last['rewrite_items'])} card(s) owed a full writing")
    if g["unjudged"] and "judge" not in rest:
        reasons.append(f"{g['unjudged']} message(s) to judge")
    if g["pages_waiting"] and "read pages" not in rest:
        reasons.append(f"{g['pages_waiting']} page(s) to read")
    if g["texted_images_waiting"] and "describe texted pictures" not in rest and not replay_guard.on():
        reasons.append(f"{g['texted_images_waiting']} texted picture(s)")
    return ", ".join(reasons) or None


def _owed_state(steps, owed_items, owed_msgs, forced, failed_at, kept=()):
    """THINK_STATE as it stands: what was not worked stays owed (all of it when the step never ran, else exactly what it
    named); a card owed while this pass ran (a stand-in made from the page) stays owed too. kept: the failed records of
    steps that rested this pass, so they go on resting until their time is up."""
    now_state = common.read_json(common.THINK_STATE) or {}
    since = set(now_state.get("pending_items") or []) - set(owed_items)
    rewrite = (forced & set(left["items"]) if left["ran"] else forced) | (set(now_state.get("rewrite_items") or []) - forced)
    common.write_json(common.THINK_STATE, {"failed_at": failed_at,
                                           "rewrite_items": sorted(rewrite),
                                           "pending_items": sorted(set(left["items"] if left["ran"] else owed_items) | since),
                                           "pending_msgs": left["msgs"] if left["ran"] else owed_msgs,
                                           "last": list(kept) + steps})


def think(pass_id, rest=()):
    """Run every step but those resting after a failure (resting()). Returns {steps, ai_calls, ok, made, changed, closed}."""
    _current["pass"] = pass_id
    start = len(calls)
    import picks
    picks.reset()
    brain.update(judged=0, writer=0)
    last = common.read_json(common.THINK_STATE) or {}
    kept =[s for s in last.get("last") or [] if isinstance(s, dict) and not s.get("ok") and s.get("step") in rest]
    bound, upto = common.until_sql()         # a replay's day: nothing after its end is judged yet
    waiting = [r[0] for r in db.query(
        """SELECT m.id FROM messages m WHERE NOT EXISTS
           (SELECT 1 FROM answered a WHERE a.domain='judged' AND a.key = 'msg:' || m.id)""" + bound, tuple(upto))]
    owes = bool(waiting or last.get("pending_items") or last.get("pending_msgs") or last.get("rewrite_items"))   # judge and cards come first: describing only runs with their time left over
    steps = []
    if "read pages" not in rest:
        steps.append(_step("read pages", read_pages, needs=120 if gather.pending_pages() else 0))
    if "describe texted pictures" not in rest and not replay_guard.on():   # the rebuild of old days skips it: pictures stay stored and shown, undescribed
        steps.append(_step("describe texted pictures", describe_texted, needs=(120 + (350 if owes else 0)) if gather.texted_images_waiting() else 0))
    if waiting and fast_sort_on() and "first sort" not in rest:
        steps.append(_step("first sort", first_sort, needs=260))
    if waiting and "judge" not in rest:
        steps.append(_step("judge", judge, needs=200))
    made, changed, closed = items.sync_from_tasks(pass_id)
    done = {r[0] for r in db.query("SELECT key FROM answered WHERE domain='judged'"
                                   " AND answered_at >= ?", (common.now() - dt.timedelta(hours=1),))}
    judged = [i for i in waiting if f"msg:{i}" in done]
    if judged and "judge" not in rest:
        try:        # a judge's noise verdict no rule of his covers: the one-line "I'd hide this" card, by program code (A13)
            import wouldhide
            wouldhide.cards(judged, pass_id)
        except Exception as e:  # noqa: BLE001  the cards are never held up by it; the reason is logged
            common.log_line(os.path.join(common.LOGS, "errors.log"), f"would hide: {type(e).__name__}: {e}")
    # what an earlier pass judged but failed to write is still owed
    last = common.read_json(common.THINK_STATE) or {}
    owed_items = sorted(set(made + changed) | set(last.get("pending_items") or []))
    owed_msgs = sorted(set(judged) | set(last.get("pending_msgs") or []))
    forced = set(last.get("rewrite_items") or [])
    left.update(ran=False, items=[], msgs=[])
    # saved before the cards are written: a pass ended at its hard limit, or stopped by an error, while writing them
    # never loses what was judged (it is no longer unjudged, so only this list brings it back)
    held_at = last.get("failed_at") if kept else None
    _owed_state(steps, owed_items, owed_msgs, forced, held_at, kept)
    if "write items" not in rest:
        steps.append(_step("write items", lambda: write_items(owed_items, owed_msgs, forced),
                           needs=150 if (owed_items or owed_msgs or forced) else 0))
    ok = all(s["ok"] for s in steps)
    _owed_state(steps, owed_items, owed_msgs, forced, held_at if ok else common.now().isoformat(), kept)
    wrote = [c for c in calls[start:] if c.get("step") in ("judge", "write items")]
    toks = [c.get("out_tokens") for c in wrote]
    cost = picks.cost_line(sum(toks) if toks and all(isinstance(x, int) for x in toks) else None) if wrote else None
    return {"steps": steps, "ai_calls": len(calls) - start, "ok": ok,
            "made": made, "changed": changed, "closed": closed, "picks": cost,
            "brain": brain_cost(calls[start:]) if wrote or brain["judged"] else None}


BEFORE_PASSES = 20        # the passes on record before one brain that its cost is set against


def _cost_of(recs):
    """(Claude runs, output tokens or None when a run did not say, dollars or None when a run did not say) of these records."""
    toks = [r.get("out_tokens") for r in recs]
    usd = [r.get("cost") for r in recs]
    return (len(recs), sum(toks) if toks and all(isinstance(x, int) for x in toks) else None,
            sum(usd) if usd and all(isinstance(x, (int, float)) for x in usd) else None)


def brain_cost(mine):
    """The pass log's one-brain line: the cards the judging run wrote and those the card writer wrote, what judging and
    writing cost this pass (Claude runs, output tokens, dollars as the Claude command reports them), against the average pass
    on record before one brain, when the judge and the card writer were two runs (the AI log: passes with a card writer run
    and no judging run marked brain)."""
    runs, tok, usd = _cost_of([c for c in mine if c.get("step") in ("judge", "write items")])
    now = (f"one brain: {brain['judged']} card(s) written with the verdicts, {brain['writer']} by the card writer;"
           f" judging and writing took {runs} Claude run(s)" + (f", {tok} output tokens" if tok is not None else "")
           + (f", ${usd:.2f}" if usd is not None else ""))
    by = {}
    try:
        with open(common.AI_LOG, encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("step") in ("judge", "write items") and r.get("pass") != _current["pass"]:
                    by.setdefault(r.get("pass"), []).append(r)
    except OSError:
        pass
    old = [v for v in by.values() if any(r.get("step") == "write items" for r in v) and not any(r.get("brain") for r in v)]
    old = old[-BEFORE_PASSES:]
    if not old:
        return now + "; before (judge and card writer apart): no pass on record to compare"
    costs = [_cost_of(v) for v in old]
    t = [c[1] for c in costs if c[1] is not None]
    d = [c[2] for c in costs if c[2] is not None]
    return (now + f"; before (judge and card writer apart, average of the last {len(old)} pass(es) on record):"
            f" {sum(c[0] for c in costs) / len(costs):.1f} Claude run(s)" + (f", {sum(t) / len(t):.0f} output tokens" if t else "")
            + (f", ${sum(d) / len(d):.2f}" if d else ""))


def summary(t):
    parts = [f"{s['step']} {'put off' if s.get('put_off') else 'ok' if s['ok'] else 'FAILED'} {s['secs']}s"
             for s in t["steps"] if s["tries"] or not s["ok"] or s.get("put_off")]
    return (f"think: {t['ai_calls']} AI call(s)" + (" [" + "; ".join(parts) + "]" if parts else "")
            + (f" | {t['picks']}" if t.get("picks") else "")        # the pick's cost: its share of the card writer's output
            + (f" | {t['brain']}" if t.get("brain") else ""))       # one brain: judging and writing in one run, against before


def main():
    if not gather.take_lock():
        print("another check is running; not starting")
        return 3
    try:
        pass_id = "live-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-think"
        t = think(pass_id)
        items.export(pass_id)
        line = f"pass {pass_id} (think only) {summary(t)}"
        common.log_line(common.PASS_LOG, line)
        print(line)
        for s in t["steps"]:
            print(" ", s)
        return 0 if t["ok"] else 1
    finally:
        gather.drop_lock()


if __name__ == "__main__":
    sys.exit(main())
