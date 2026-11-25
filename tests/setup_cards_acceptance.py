r"""Acceptance (quick): the judgment rebuild's setup and contacts phase. On a scratch copy laid down from this plugin, with a
made-up home, a made-up mail connection (taught connection type) and made-up people; no real account is signed in (a real
sign-in cannot be tested here), Claude is stood in for, nothing is sent.

- The desktop interview hands the rest to the page (setup_home.py cards): its next question is no longer the name.
- A made-up new home walks the setup cards in order (welcome, email, texts, calendar, other channels, how far back, about
  you, the catalog's progress, here's what I noticed, learning levels) and no new mail is pulled in before the catalog is
  built; the catalog holds envelopes only (no body) until a look-back reads one.
- Once built, today's mail comes in; a new sender is looked up in the catalog and its context built (with the history
  read), and the judge's payload carries it.
- A noticed card's yes saves a rule; the about-you interview keeps going until I'm done and saves the name.
- Tips: the first card with a pick gets the tip, a second never does.
- Contacts in Settings data lists a one-time sender, a phone-book entry and a mail address-book entry, each with last in
  touch, how often, open matters both ways, history, notes and what was learned; a note saves.

    python tests\setup_cards_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []

FAKE = r'''
"""A made-up mail type for a test: no network, made-up people only."""
import datetime as dt
from connections import _store
TYPE = "fake_mail"
NAME = "Made-up mail"
KIND = "email"
CAN_SEND = False
ASKS = []
SETUP = "A made-up mailbox for a test."
ME = "me@example.test"

def connect(conn, say=print, answers=None):
    conn["address"] = ME
    conn["label"] = ME
    return conn

def check(conn):
    return ME + ": reachable"

def gather(conn, ctx):
    import common, os, json
    p = os.path.join(common.paths.STATE, "fake_gather_calls.json")
    n = (common.read_json(p, {}) or {}).get("n", 0) + 1
    common.write_json(p, {"n": n})
    w = _store.MailWriter(ME)
    w.add("today-1", dt.datetime.now().replace(microsecond=0) - dt.timedelta(minutes=5), "in", "pat.lane@example.test", ME,
          "Porch railing quote, round two", "Here is the new price for the porch railing. Can you confirm by Friday?",
          thread_id="t-pat-2")
    return f"{w.commit()} new"

def _hist():
    now = dt.datetime.now().replace(microsecond=0)
    d = lambda days, h=0: now - dt.timedelta(days=days, hours=h)
    rows = []
    for i, days in enumerate((200, 120, 40)):
        rows.append({"provider_id": f"pat-in-{i}", "ts": d(days), "direction": "in", "from_key": "pat.lane@example.test",
                     "from_name": "Pat Lane", "to": [ME], "subject": "Porch railing quote", "thread_id": f"t-pat-{i}"})
        rows.append({"provider_id": f"pat-out-{i}", "ts": d(days, -3), "direction": "out", "from_key": ME, "from_name": "",
                     "to": ["pat.lane@example.test"], "subject": "Re: Porch railing quote", "thread_id": f"t-pat-{i}"})
    for i in range(6):
        rows.append({"provider_id": f"news-{i}", "ts": d(10 + i * 20), "direction": "in", "from_key": "news@example.test",
                     "from_name": "Garden News", "to": [ME], "subject": f"Garden tips {i}", "thread_id": f"t-news-{i}"})
    rows.append({"provider_id": "once-1", "ts": d(90), "direction": "in", "from_key": "once.only@example.test",
                 "from_name": "Kit Once", "to": [ME], "subject": "One question about the fence", "thread_id": "t-once"})
    for i in range(3):
        rows.append({"provider_id": f"sent-{i}", "ts": d(30 + i), "direction": "out", "from_key": ME, "from_name": "",
                     "to": [f"friend{i}@example.test"], "subject": f"Saturday plan {i}", "thread_id": f"t-sent-{i}"})
    return rows

def envelopes(conn, since, cursor, end):
    rows = [r for r in _hist() if r["ts"].date() >= since]
    half = len(rows) // 2
    if not cursor:
        return {"rows": rows[:half], "cursor": "page-2", "done": False, "total": len(rows)}
    return {"rows": rows[half:], "cursor": None, "done": True}

def envelope_text(conn, provider_id):
    if provider_id.startswith("sent-"):
        return "Hi there,\n\nSaturday works for me, see you at the yard.\n\nThanks,\nRobin"
    return f"Made-up text of {provider_id}: the porch railing price and the dates."

def address_book(conn):
    return [{"name": "Robin Field", "emails": ["robin.field@example.test"], "phones": ["+1 555 010 2233"]}]
'''

INSIDE = r'''
import datetime as dt, json, os, re, sys, time
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
os.environ["ASSISTANT_PAGE_LATER"] = "1"; os.environ["ASSISTANT_QUICK_PASS"] = "1"; os.environ["ASSISTANT_NO_PASS_NOW"] = "1"
import common, db, items, answers, onboard, catalog, lookback, think, updates, setup_steps, contacts_book, settings_data, filters
P = __import__("pass")
out = {}
import traceback
def _dump(t, v, tb):        # a check that stops still says how far it got
    traceback.print_exception(t, v, tb, file=sys.stderr); out["stopped"] = f"{t.__name__}: {v}"; print(json.dumps(out, default=str))
sys.excepthook = _dump
updates.check = lambda pass_id: None
think.needed = lambda g: None                   # no card writer in this test: the judge is not what is checked here
def connect_inline(args):                       # the sign-in a Connect press starts, run here with the made-up type
    setup_steps.add_connection(args[-1], say=lambda *_: None)
    return True
onboard._start = connect_inline
onboard._claude = lambda prompt: None           # no Claude: the interview follows its own starting list
lookback._claude = lambda prompt: "Pat Lane is a contractor who quotes porch work; you answer within hours."
common.write_json(os.path.join(common.paths.STATE, "phone_book.json"), {"people": [{"name": "Sam Brook", "number": "+1 555 010 9988"}]})

def card_of(step):
    st = onboard.state()
    return items.card_for(st["cards"][step], wait=True)

def press(iid, text):
    return answers.act_on_answer({"id": iid, "action": "answer", "text": text, "at": dt.datetime.now().isoformat(timespec="milliseconds")})

def msgs():
    return db.query("SELECT count(*) FROM messages")[0][0]

def calls():
    return (common.read_json(os.path.join(common.paths.STATE, "fake_gather_calls.json"), {}) or {}).get("n", 0)

order = []
def seen():
    st = onboard.state()
    if st.get("step") and (not order or order[-1] != st["step"]):
        order.append(st["step"])

seen()
c = card_of("welcome"); out["welcome card has Start"] = c.get("choices")
press(c["id"], "Start"); seen()
c = card_of("email"); out["email card offers the made-up mail"] = "Connect Made-up mail" in (c.get("choices") or [])
press(c["id"], "Connect Made-up mail")
c = card_of("email"); out["email connected, card ticks it"] = ["me@example.test" in (c.get("detail") or ""), "That's all my email" in (c.get("choices") or [])]
P.main(); held1 = [msgs(), calls()]
press(c["id"], "That's all my email"); seen()
press(card_of("texts")["id"], "Skip for now"); seen()
press(card_of("calendar")["id"], "Skip for now"); seen()
ch = card_of("channels"); out["channels card asks about other channels"] = [ch["title"], "None for now" in (ch.get("choices") or [])]
press(ch["id"], "None for now"); seen()
lb = card_of("lookback"); out["lookback card: one year first, envelopes explained"] = [(lb.get("choices") or [None])[0], "envelopes" in (lb.get("detail") or "")]
press(lb["id"], "One year (recommended)"); seen()
P.main()                                        # the catalog's first portion: still no new mail
out["no new mail pulled before the catalog is built"] = held1 + [msgs(), calls(), catalog.building()]
ab = card_of("about")
press(ab["id"], "Call me Robin. Robin Field.")
ab = card_of("about"); q2 = (ab.get("asks") or [""])[0]
press(ab["id"], "I run a small carpentry shop.")
press(ab["id"], "Mostly my partner Pat and a few regular customers.")
ab = card_of("about"); out["the interview goes on until I'm done"] = [ab["state"], "I'm done" in (ab.get("choices") or []), q2.startswith("What do you do")]
press(ab["id"], "I'm done"); seen()
out["the name is saved"] = common.personal().get("owner")
pr = card_of("progress"); out["progress card shows the time left"] = ["minute" in (pr.get("detail") or "") or "Built" in (pr.get("detail") or ""), pr["state"]]
P.main(); seen()                                # the catalog finishes: progress closes, noticed cards made
out["catalog built, still no mail in that pass, envelopes have no body"] = [
    catalog.built(), msgs(), db.query("SELECT count(*), count(body) FROM envelopes")[0][0] > 0]
st = onboard.state()
noticed = [items.card_for(i, wait=True) for (i,) in db.query("SELECT id FROM live_items WHERE starts_with(source_key, 'live:setup-noticed-') AND state <> 'done' ORDER BY id")]
out["noticed cards include the writing voice"] = [len(noticed) >= 2, any("how you write" in (n.get("detail") or "") for n in noticed)]
first = noticed[0]
press(first["id"], "Yes, that's right")
out["a yes saves a rule"] = any(r.get("from", "").startswith("You said yes") for r in filters.rules())
for n in noticed[1:]:
    press(n["id"], "Skip this one")
seen()
lv = card_of("levels"); out["levels card explains levels, all start at 1"] = "Everything starts at Level 1" in (lv.get("detail") or "")
press(lv["id"], "Got it")
out["setup finished"] = bool(onboard.state().get("finished"))
out["cards in order"] = order

# today's mail now comes in, and a new sender is looked up
lookback.ensure(); db.execute("DELETE FROM sender_context")
P.main()
ctx = lookback.context("email:pat.lane@example.test") or {}
fetched = db.query("SELECT count(*) FROM envelopes WHERE body IS NOT NULL AND provider_id LIKE 'pat-%'")[0][0]
out["today's mail pulled once the catalog is built"] = [msgs() >= 1, calls() >= 1]
mid = db.query("SELECT id FROM messages WHERE from_key LIKE '%pat.lane%' ORDER BY id DESC LIMIT 1")[0][0]
con = db.connect(read_only=True)
try:
    words = lookback.words_for(con, mid) or ""
finally:
    con.close()
out["look-back built context for the new sender"] = [ctx.get("found", 0) >= 6, ctx.get("in_count"), ctx.get("out_count"),
    "within" in (ctx.get("summary") or ""), "contractor" in (ctx.get("summary") or ""), fetched >= 1, "Pat Lane" in words]
out["daily cap counted"] = lookback.used_today() >= 1

# tips: the first card with a pick gets it, a second never does
a, _ = items.upsert("test:tip-a", "t", kind="question", state="question", area="Personal", title="Made-up card A", asks=["A?"],
                    extra=json.dumps({"pick": {"do": "press", "press": "done", "label": "Done", "by": "program"}}))
items.export("t")
b, _ = items.upsert("test:tip-b", "t", kind="question", state="question", area="Personal", title="Made-up card B", asks=["B?"],
                    extra=json.dumps({"pick": {"do": "press", "press": "done", "label": "Done", "by": "program"}}))
items.export("t")
snap = {i["id"]: i for i in common.read_json(common.ITEMS_JSON, {})["items"]}
out["tip on the first card with a pick only"] = [bool(snap[a].get("tip")), bool(snap[b].get("tip"))]

# contacts
import subprocess
rc = subprocess.run([sys.executable, os.path.join(live, "core", "refresh_contacts.py")], capture_output=True, text=True)
subprocess_ok = rc.returncode == 0
if not subprocess_ok:
    out["refresh_contacts said"] = (rc.stderr or rc.stdout)[-1500:]
cdef = settings_data.defs()["contacts"]
pg1, pg2 = contacts_book.page(limit=4), contacts_book.page(offset=4, limit=50)
people = pg1["people"] + pg2["people"]
out["contacts: Settings sends a count, the people come in pages"] = ["people" in cdef, cdef["count"] == pg1["total"], len(pg1["people"]),
                                                                    len(people) == pg1["total"], contacts_book.page(q="robin")["total"]]
def who(addr):
    return next((p for p in people if addr in p["addresses"]), None)
once, robin, sam = who("once.only@example.test"), who("robin.field@example.test"), who("5550109988")
fields = ("last_in_touch", "how_often", "open_matters", "history", "notes", "learned")
out["contacts: one-time sender, address book and phone book listed with the fields"] = [
    subprocess_ok, bool(once and once["one_time"]), bool(robin) and "the address book of me@example.test" in robin["where"],
    bool(robin) and "5550102233" in robin["addresses"], bool(sam) and "your phone's contacts" in sam["where"],
    all(f in (once or {}) for f in fields), sorted((once or {}).get("open_matters", {}).keys()),
    sorted((once or {}).get("history", {}).keys())]
pat = who("pat.lane@example.test") or {"person": None}
out["contacts: history and what was learned"] = [bool(pat.get("history", {}).get("messages")), "contractor" in pat.get("learned", ""),
                                                 bool(pat.get("last_in_touch"))]
r = answers.act_on_answer({"id": "contact-note:1", "action": "answer", "at": dt.datetime.now().isoformat(),
                           "text": json.dumps({"contact_note": {"person": str(pat.get("person")), "notes": "Prefers a call before noon."}})})
pat2 = next((p for p in contacts_book.for_settings() if p["person"] == pat.get("person")), {})
out["contacts: a note saves"] = [r.get("result"), pat2.get("notes")]
print(json.dumps(out, default=str))
'''

EXISTING = r'''
import datetime as dt, json, os, sys
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
os.environ["ASSISTANT_PAGE_LATER"] = "1"; os.environ["ASSISTANT_QUICK_PASS"] = "1"; os.environ["ASSISTANT_NO_PASS_NOW"] = "1"
import common, db, items, onboard, catalog, think, updates, setup_steps, gather, mail
P = __import__("pass")
updates.check = lambda pass_id: None
think.needed = lambda g: None
out = {}
db.init_schema(); items.ensure()
setup_steps.add_connection("fake_mail", say=lambda *_: None)
now = dt.datetime.now().replace(microsecond=0)
con = db.connect()
for i in range(120):            # months of mail already stored, as on a home that has been running
    con.execute("INSERT INTO messages (channel, account, provider_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
                " VALUES ('email', 'me@example.test', ?, ?, 'in', 'email:old.friend@example.test', 'me@example.test', ?, 'old', ?)",
                (f"old-{i}", now - dt.timedelta(days=i), f"Old subject {i}", now))
con.close()
db.set_watermark("email:me@example.test", now - dt.timedelta(hours=1))
def calls():
    return (common.read_json(os.path.join(common.paths.STATE, "fake_gather_calls.json"), {}) or {}).get("n", 0)
n0 = db.query("SELECT count(*) FROM messages")[0][0]
P.main()                        # the first pass after the update
out["an existing home keeps pulling mail after the update"] = [onboard.holding(), calls(), db.query("SELECT count(*) FROM messages")[0][0] - n0,
                                                               catalog.started(), mail.pull_now().startswith("Not pulled yet")]
onboard.begin()                 # even setup cards begun over stored mail never hold it
P.main()
out["setup cards over stored mail hold nothing"] = [onboard.state().get("fresh"), onboard.holding(), calls(), catalog.started()]
print(json.dumps(out, default=str))
'''

WANT = {
    "welcome card has Start": ["Start"],
    "email card offers the made-up mail": True,
    "email connected, card ticks it": [True, True],
    "channels card asks about other channels": ["What other channels do you want to connect?", True],
    "lookback card: one year first, envelopes explained": ["One year (recommended)", True],
    "no new mail pulled before the catalog is built": [0, 0, 0, 0, True],
    "the interview goes on until I'm done": ["question", True, True],
    "the name is saved": "Robin",
    "progress card shows the time left": [True, "in_motion"],
    "catalog built, still no mail in that pass, envelopes have no body": [True, 0, True],
    "noticed cards include the writing voice": [True, True],
    "a yes saves a rule": True,
    "levels card explains levels, all start at 1": True,
    "setup finished": True,
    "cards in order": ["welcome", "email", "texts", "calendar", "channels", "lookback", "about", "progress", "noticed", "levels"],
    "today's mail pulled once the catalog is built": [True, True],
    "look-back built context for the new sender": [True, 3, 3, True, True, True, True],
    "daily cap counted": True,
    "tip on the first card with a pick only": [True, False],
    "contacts: one-time sender, address book and phone book listed with the fields": [
        True, True, True, True, True, True, ["theirs", "yours"], ["cards", "decisions", "messages"]],
    "contacts: history and what was learned": [True, True, True],
    "contacts: a note saves": ["Your notes are saved.", "Prefers a call before noon."],
    "contacts: Settings sends a count, the people come in pages": [False, True, 4, True, 1],
}
WANT_EXISTING = {
    "an existing home keeps pulling mail after the update": [False, 1, 1, False, False],
    "setup cards over stored mail hold nothing": [False, False, 2, False],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="setupcards-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    env.pop("ASSISTANT_REPLAY", None)
    spec = importlib.util.spec_from_file_location("ac_setupcards", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47941", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        os.makedirs(os.path.join(home, "taught", "connections"), exist_ok=True)
        with open(os.path.join(home, "taught", "connections", "fake_mail.py"), "w", encoding="utf-8") as f:
            f.write(FAKE)
        r = subprocess.run([sys.executable, os.path.join(live, "setup", "setup_home.py"), "--root", root, "cards"],
                           capture_output=True, text=True, env=env, timeout=300)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {"says": (r.stderr or r.stdout)[-500:]}
        check("the desktop interview hands the rest to the page", [got.get("ok"), bool(got.get("cards")), got.get("next") not in ("name", "work", "accounts")],
              [True, True, True])
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=900)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o = {}
            check("the checks ran", (r.stderr or r.stdout)[-3000:], "")
        if o.get("stopped"):
            check("the checks ran to the end", o["stopped"] + " | " + (r.stderr or "")[-1500:], "")
        for name, want in WANT.items():
            check(name, o.get(name), want)
        # a made-up existing home: stored mail, no catalog, no setup cards; laid down with this version
        root2 = os.path.join(tmp, "Existing")
        home2, live2 = os.path.join(root2, "Live"), os.path.join(root2, "System", "live")
        env2 = dict(env, ASSISTANT_LIVE_HOME=home2)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47942", "--sending", "no",
                            "--root", root2], capture_output=True, text=True)
        check("lay-down of an existing home", r.returncode, 0)
        os.makedirs(os.path.join(home2, "taught", "connections"), exist_ok=True)
        with open(os.path.join(home2, "taught", "connections", "fake_mail.py"), "w", encoding="utf-8") as f:
            f.write(FAKE)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", EXISTING, live2], capture_output=True, text=True, env=env2, timeout=600)
        try:
            o2 = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o2 = {}
            check("the existing-home checks ran", (r.stderr or r.stdout)[-3000:], "")
        for name, want in WANT_EXISTING.items():
            check(name, o2.get(name), want)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
