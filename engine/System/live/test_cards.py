r"""Made-up cards to try the page with, kept apart from the owner's real ones.

    python test_cards.py add       puts the set on the page (each titled "TEST: ...", its source key starting "test:")
    python test_cards.py remove    takes every test card off, with the answer records its presses left

A press on a test card changes only that card (answers.is_test): Done, Snooze, Bring back and the like work as on any card;
Junk, Never junk, Not needed, Always show, Approve, Send and typed words are recorded on the card and do nothing else, so no
email is sent, no account is touched, no Claude run is made, and the junk, never-junk and ignore lists and the rules stay as
they are. A test card has no message behind it, so its Context names its papers in words; nothing is opened from the owner's
mail. Run with ASSISTANT_LIVE_HOME naming the home (assistant.py test-cards does)."""
import datetime as dt
import json
import os
import sys

import common
import db
import items

PREFIX = "test:"
PASS_ID = "test-cards"


def _day(n):
    return (dt.date.today() + dt.timedelta(days=n)).isoformat()


def cards():
    """(source key, columns) for each test card: every kind the page draws, made-up names and amounts."""
    send_off = "Sending from the page is off for test cards: Send records the press on the card and sends nothing."
    return [
        ("test:came-back", dict(
            kind="question", area="Work", state="question", title="TEST: Acme Supply owes $6,000 on invoices 1101 and 1102", recommended="Send Dana a short reminder about both invoices.",
            why="Two made-up invoices to Acme, $6,000 in all, are unpaid; no reply in two weeks.",
            detail="You emailed Dana Invoice 1101.pdf ($3,000, due 10/1) and Invoice 1102.pdf ($3,000) on 11/3. No payment or reply since. "
                   "(A test card has no real email or paper behind it, so these are named here, not opened.)",
            asks=["Remind Dana about the $6,000?"], source_who="Dana (made up)",
            extra=json.dumps({"sender": {"key": "email:dana@example.com", "address": "dana@example.com", "name": "Dana (made up)", "can_junk": True},
                              "came_back": {"why": "waited", "who": "Dana (made up)", "waited_days": 14, "wait_days": 5},
                              "choices": [{"label": "Send reminder (recommended)", "text": "Send reminder", "recommended": True},
                                          {"label": "Keep waiting", "text": "Keep waiting"}]}))),
        ("test:calendar", dict(
            kind="question", area="Work", state="question", title="TEST: The inspector visits the shop", recommended="Put the visit on your calendar for " + _day(2) + ", 9:00 to 9:30 AM.",
            why="A made-up inspector set a time.", asks=["Put it on your calendar?"], source_who="Inspector (made up)",
            calendar=json.dumps({"title": "TEST: Inspector visit", "date": _day(2), "start": "09:00", "end": "09:30", "certain": True}))),
        ("test:two-questions", dict(
            kind="question", area="Work", state="question", title="TEST: Two things to settle on the Corner Kitchen job", recommended="Order from Supplier A and keep Friday.", why="Two made-up choices are open on one job.",
            asks=["Which supplier for the replacement head?", "Keep the Friday visit?"], source_who="Shop (made up)",
            extra=json.dumps({"sender": {"key": "email:shop@example.com", "address": "shop@example.com", "name": "Shop (made up)", "can_junk": True},
                              "choices": [{"label": "Supplier A (recommended)", "text": "Supplier A", "recommended": True},
                                          {"label": "Supplier B", "text": "Supplier B"}],
                              "questions": [{"ask": "Keep the Friday visit?",
                                             "choices": [{"label": "Keep Friday", "text": "Keep Friday", "recommended": True},
                                                         {"label": "Move to Monday", "text": "Move to Monday"}]}]}))),
        ("test:fyi", dict(
            kind="fyi", area="Work", state="handled", title="TEST: A shipment went out",
            why="A made-up supplier says the order shipped.", source_who="Supplier (made up)",
            extra=json.dumps({"sender": {"key": "email:shipping@example.com", "address": "shipping@example.com", "name": "Supplier (made up)",
                                         "can_junk": True}}))),
        ("test:draft", dict(
            kind="approval", area="Work", state="question", title="TEST: A reply to Pat about the delivery",
            recommended="Send it.", why="Pat (made up) asked for a delivery date. " + send_off,
            extra=json.dumps({"sender": {"key": "email:pat@example.com", "address": "pat@example.com", "name": "Pat (made up)", "can_junk": True}}),
            draft=json.dumps({"to": ["pat@example.com"], "cc": [], "subject": "Re: Delivery (test)",
                              "body": "Hi Pat,\n\nFriday works for the delivery.\n\nThanks,", "attach": [], "test": True}))),
        ("test:rule", dict(
            kind="approval", area="Work", state="question", title="TEST: New rule: hide sale emails from vendors",
            why="A made-up Not needed press proposed it. Saving it on a test card saves no rule.", asks=["Save this rule?"],
            extra=json.dumps({"rule": {"text": "Hide sale emails from vendors (test).", "way": "show_less", "from": "Roof sale (made up)"}}))),
        ("test:junk", dict(
            kind="question", area="Work", state="question", title="TEST: Is news@example.com junk?",
            why="A made-up sender I marked as junk three times. Junk and Never junk on a test card change no list.",
            asks=["Junk, or never junk?"], source_who="news@example.com (made up)",
            extra=json.dumps({"sender": {"key": "email:news@example.com", "address": "news@example.com", "name": "news@example.com", "can_junk": True},
                              "choices": ["Junk", "Never junk"]}))),
    ]


def ids(con=None):
    own = con is None
    con = con or db.connect(read_only=True)
    try:
        return [r[0] for r in con.execute("SELECT id FROM live_items WHERE starts_with(source_key, ?)", [PREFIX]).fetchall()]
    finally:
        if own:
            con.close()


def publish():
    """The page's data made again from the cards, the step a pass ends with (live_page\\publish.py), so the page shows the
    change on its next reload. Returns words for the result."""
    import subprocess
    if not os.path.exists(common.PUBLISH):
        return "the page is not set up here, so nothing was published"
    r = subprocess.run([sys.executable, common.PUBLISH], capture_output=True, text=True, timeout=300,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return "the page is updated" if r.returncode == 0 else "the page could not be updated: " + (r.stderr or r.stdout).strip()[-300:]


def add():
    made = []
    for key, cols in cards():
        cols = dict(cols, importance=0, source_when=common.now())       # never important: no phone notification
        later = {k: cols.pop(k) for k in ("extra", "calendar", "draft") if k in cols}
        iid, _ = items.upsert(key, PASS_ID, **cols)
        if later:
            items.update(iid, PASS_ID, **later)
        made.append(iid)
    n = items.export(PASS_ID)
    page = publish()
    print(json.dumps({"ok": True, "added": len(made), "ids": made, "open_on_page": n, "page": page,
                      "says": f"{len(made)} test cards are on your page, each titled TEST: ({page}). Remove them with test-cards remove."}))


def _made_up(con):
    """Test cards made by hand before this tool: a card titled TEST: whose every message is titled TEST: and comes from a
    made-up address (example.com, .org or .net, the domains kept for examples). (card ids, message ids, sender keys)"""
    cards_, mids, senders = [], [], set()
    for iid, srcs in con.execute("SELECT id, source_messages FROM live_items WHERE starts_with(title, 'TEST:') "
                                 "AND NOT starts_with(coalesce(source_key, ''), ?)", [PREFIX]).fetchall():
        try:
            ms = [int(m) for m in json.loads(srcs or "[]")]
        except (ValueError, TypeError):
            continue
        rows = con.execute(f"SELECT id, subject, from_key FROM messages WHERE id IN ({','.join('?' for _ in ms)})", ms).fetchall() if ms else []
        fake = len(rows) == len(ms) and all(str(sj or "").startswith("TEST:") and
                                            str(fk or "").lower().endswith(("@example.com", "@example.org", "@example.net")) for _i, sj, fk in rows)
        if fake:
            cards_.append(iid)
            mids += ms
            senders |= {str(fk).lower() for _i, _s, fk in rows}
    return cards_, mids, sorted(senders)


def _drop_made_up(con, cards_, mids, senders):
    """The hand-made test cards and their made-up messages, with what hangs off those messages; a made-up sender's contact
    only when no other message is theirs."""
    q = lambda xs: ",".join("?" for _ in xs)       # noqa: E731
    have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}
    if mids:
        atts = [r[0] for r in con.execute(f"SELECT id FROM attachments WHERE message_id IN ({q(mids)})", mids).fetchall()]
        docs = [r[0] for r in con.execute(f"SELECT id FROM documents WHERE message_id IN ({q(mids)})" +
                                          (f" OR attachment_id IN ({q(atts)})" if atts else ""), mids + atts).fetchall()]
        if docs and "pages" in have:
            con.execute(f"DELETE FROM pages WHERE document_id IN ({q(docs)})", docs)
        if docs:
            con.execute(f"DELETE FROM documents WHERE id IN ({q(docs)})", docs)
        if atts:
            con.execute(f"DELETE FROM attachments WHERE id IN ({q(atts)})", atts)
        if "mail_state" in have:
            con.execute(f"DELETE FROM mail_state WHERE message_id IN ({q(mids)})", mids)
        keys = [f"msg:{m}" for m in mids]
        con.execute(f"DELETE FROM answered WHERE key IN ({q(keys)})", keys)
        con.execute(f"DELETE FROM messages WHERE id IN ({q(mids)})", mids)
    for k in senders:
        if not con.execute("SELECT 1 FROM messages WHERE lower(from_key) = ? LIMIT 1", [k]).fetchone():
            con.execute("DELETE FROM contacts WHERE lower(key) = ?", [k])
    if cards_:
        con.execute(f"DELETE FROM live_items WHERE id IN ({q(cards_)})", cards_)


def remove():
    gone = ids()
    con = db.connect()
    try:
        made_up = _made_up(con)
        if gone:
            con.execute("DELETE FROM live_items WHERE starts_with(source_key, ?)", [PREFIX])
        _drop_made_up(con, *made_up)
        every = gone + made_up[0]
        if every and con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'live_answers'").fetchone():
            con.execute(f"DELETE FROM live_answers WHERE item_id IN ({','.join('?' for _ in every)})", every)
    finally:
        con.close()
    every = set(gone) | set(made_up[0])
    left = 0
    for folder in (common.ANSWERS, common.ANSWERS_APPLIED):
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for n in names:
            p = os.path.join(folder, n)
            if not n.endswith(".json") or not os.path.isfile(p):
                continue
            rec = common.read_json(p, {}) or {}
            if rec.get("id") in every:
                os.remove(p)                # the answer records of test-card presses: test data
                left += 1
    items.export(PASS_ID)
    page = publish()
    print(json.dumps({"ok": True, "removed": len(gone), "made_up_removed": {"cards": made_up[0], "messages": made_up[1], "senders": made_up[2]},
                      "answer_records_removed": left, "page": page,
                      "says": f"{len(gone) + len(made_up[0])} test cards are off your page ({page}); nothing else was changed."}))


if __name__ == "__main__":
    {"add": add, "remove": remove}[sys.argv[1]]()
