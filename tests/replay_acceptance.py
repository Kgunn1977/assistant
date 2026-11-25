r"""Acceptance of the day-by-day rebuild (replay.py), on a throwaway home with stand-ins for every service. No real service is
called: the computer's own web opener is replaced by one that fails the test, so anything that would reach the network does.

1. Erase deletes the working data (no To Delete folder) and keeps the owner's rules, settings, style, sign-ins, mods and contacts (their
   counts back to zero); the fresh database's ids start after the old ones.
2. Day windows are midnight to midnight in Los Angeles: 24 hours, 25 on 2026-11-01, 23 on 2027-03-14.
3. Two stand-in days: each source read for its day only (a mail one second before midnight stays on its day, an added chat
   type's messages read by its own day reader on their own day, an event that started the evening before is left out), texts filed once from two
   backups that overlap; the sort is told the day's end and never sees a later message; a card made on day 1 is closed on
   day 2 when the record shows it paid.
4. Every outbound function refuses under the replay flag.
5. A day that stops partway (a source that fails) is not counted; continue reads it again and nothing is stored twice.

    python tests\replay_acceptance.py
"""
import datetime as dt
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
home = tempfile.mkdtemp(prefix="replay-")
os.environ["ASSISTANT_LIVE_HOME"] = home
sys.path.insert(0, LIVE)
# an added connection type of the owner's own (a made-up team chat, "board"), in the throwaway home's taught connections: the
# replay reads it only through its own day reader (replay_day), as it would any addition
BOARD = """
import datetime as dt
from connections import _store
TYPE = "board"
NAME = WORD = TITLE = "Board"
KIND = "board"
SETUP = "A made-up team chat, for the replay test."
MESSAGES = []           # (id, moment, text), filled by the test
FAIL = {"n": 0}


def gather(conn, ctx):
    return 0


def replay_day(conn, start, end):
    if FAIL["n"]:
        FAIL["n"] -= 1
        raise RuntimeError("could not reach the board (stand-in)")
    rows = [{"provider_id": i, "thread_id": "general", "ts": dt.datetime.fromtimestamp(when.timestamp()), "direction": "in",
             "from_key": "board:ora", "where": "#general", "text": text} for i, when, text in MESSAGES if start <= when < end]
    written, _held = _store.chat_messages("board", conn["label"], rows, "board:" + conn["label"])
    return written, []
"""
os.makedirs(os.path.join(home, "taught", "connections"), exist_ok=True)
with open(os.path.join(home, "taught", "connections", "board.py"), "w", encoding="utf-8") as _f:
    _f.write(BOARD)
sys.path.insert(0, HERE)
LA = ZoneInfo("America/Los_Angeles")
results = []


def check(ok, what):
    results.append((bool(ok), what))
    print(("PASS  " if ok else "FAIL  ") + what, flush=True)


def put(rel, text):
    p = os.path.join(home, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def at(day, h, m=0, s=0):
    return dt.datetime(2026, 9, day, h, m, s, tzinfo=LA)


# --- the throwaway home ----------------------------------------------------------------------------------------------------
texts_dir = os.path.join(home, "phone")
put("personal/personal.json", json.dumps({"owner": "Pat", "sources": ["email", "board", "calendar", "sms"]}))
put("personal/settings.json", json.dumps({"alerts": {"server": "https://ntfy.sh", "topic": ""}}))
put("personal/connections.json", json.dumps({"apps": {}, "connections": [
    {"id": "c1", "type": "google_mail", "kind": "email", "address": "pat@example.com", "label": "pat@example.com", "send": True},
    {"id": "c2", "type": "microsoft_mail", "kind": "email", "address": "pat@work.example", "label": "pat@work.example", "send": True},
    {"id": "c3", "type": "board", "kind": "board", "label": "Team"},
    {"id": "c4", "type": "google_calendar", "kind": "calendar", "address": "pat@example.com", "label": "pat@example.com"},
    {"id": "c5", "type": "phone_texts", "kind": "sms", "label": "Phone texts", "folder": texts_dir}]}))
KEEP = {"personal/filter_rules.json": '{"rules": ["mine"]}', "personal/voice.json": '{"style": "short"}',
        "personal/keys.dat": "locked", "mods/demo/mod.json": '{"name": "demo"}', "Resources/Rules/Junk rules.md": "- spam",
        "chat.json": "[]"}
for rel, text in KEEP.items():
    put(rel, text)
for rel in ("items.json", "held.json", "think_state.json", "state/texts_link_convs.json", "state/mail_cache.duckdb",
            "Resources/Attachments/old.pdf", "state/payload_2026-11-20.json"):
    put(rel, "{}")


def sms(ms, kind, body, address="+15551230000"):
    return f'<sms address="{address}" date="{ms}" type="{kind}" body="{body}" contact_name="Sam" />'


def ms_of(d):
    return int(d.timestamp() * 1000)


T1 = sms(ms_of(at(1, 9)), "1", "Can you call me")
T2 = sms(ms_of(at(2, 8)), "2", "On my way")
put("phone/sms-20260902000000.xml", f'<smses count="3">{T1}{sms(ms_of(at(1, 12)), "1", "Lunch?")}'
                                    f'{sms(ms_of(dt.datetime(2026, 8, 30, 12, tzinfo=LA)), "1", "too early")}</smses>')
put("phone/sms-20260903000000.xml", f'<smses count="2">{T1}{T2}</smses>')

import db  # noqa: E402
import items  # noqa: E402

db.init_schema()
items.ensure()
con = db.connect()
for i in range(30):                 # the old database's ids run past those a fresh one would start at
    con.execute("INSERT INTO messages (channel, account, provider_id, ts, direction, body, ingested_at) VALUES"
                " ('email','old@example.com',?,?, 'in','old', now())", (f"old{i}", dt.datetime(2026, 8, 1)))
con.execute("INSERT INTO contacts (key, person_id, name, company, sent_count, received_count, strength, notes)"
            " VALUES ('email:sam@example.com', 7, 'Sam Lee', 'Acme', 12, 30, 2.5, 'plumber')")
old_max = con.execute("SELECT max(id) FROM messages").fetchone()[0]
con.close()

# --- no real network, ever ----------------------------------------------------------------------------------------------------
def _no_network(*a, **k):
    raise AssertionError("a real network call was attempted")


urllib.request.urlopen = _no_network

import replay  # noqa: E402  (sets the replay flag for this process)
import replay_guard  # noqa: E402
import replay_sources  # noqa: E402
import common  # noqa: E402
import connections  # noqa: E402
from connections import _http  # noqa: E402

gm, ms, gc = (connections.module(t) for t in ("google_mail", "microsoft_mail", "google_calendar"))
board = connections.module("board")
for mod in (gm, ms, board, gc):
    mod.check = lambda c: f"{c['id']}: reachable (stand-in)"
gm.token_for = ms._token = lambda c: "t"
ms._kinds = lambda conn, token: {"inbox": "INBOX1"}

GMAIL = {"g1": (at(1, 10), "client@example.org", "Invoice 104", "Please send the invoice for the August job"),
         "g2": (at(1, 23, 59, 59), "news@example.org", "Late news", "One second before midnight"),
         "g3": (at(2, 0, 0, 30), "client@example.org", "Re: Invoice 104", "Paid, thanks"),
         "g4": (at(3, 9), "client@example.org", "Hello again", "A third day")}
GRAPH = {"m1": (at(1, 15), "boss@work.example", "Schedule", "Meeting moved")}
board.MESSAGES[:] = [("b1", at(1, 11), "Question on day 1"), ("b2", at(2, 7), "Answer on day 2")]
EVENTS = [{"id": "e1", "summary": "Site visit", "start": {"dateTime": at(1, 14).isoformat()}, "end": {"dateTime": at(1, 15).isoformat()}},
          {"id": "e0", "summary": "Late show", "start": {"dateTime": dt.datetime(2026, 8, 31, 23, tzinfo=LA).isoformat()},
           "end": {"dateTime": at(1, 1).isoformat()}}]


def stand_in(url, token=None, params=None, headers=None):
    params = params or {}
    if "gmail.googleapis.com" in url:
        if url.endswith("/labels"):
            return {"labels": []}
        if url.endswith("/messages"):
            a, b = (int(x) for x in re.search(r"after:(\d+) before:(\d+)", params["q"]).groups())
            return {"messages": [{"id": i} for i, v in sorted(GMAIL.items(), key=lambda kv: -kv[1][0].timestamp())
                                 if a < v[0].timestamp() < b]}
        mid = url.rsplit("/", 1)[1]
        when, frm, subj, body = GMAIL[mid]
        import base64
        return {"id": mid, "threadId": "t-" + subj.replace("Re: ", ""), "internalDate": str(ms_of(when)), "labelIds": ["INBOX"],
                "payload": {"mimeType": "text/plain", "headers": [{"name": "From", "value": frm}, {"name": "To", "value": "pat@example.com"},
                            {"name": "Subject", "value": subj}], "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()}}}
    if "graph.microsoft.com" in url:
        q = urllib.parse.unquote(url)
        lo, hi = re.search(r"ge (\S+) and receivedDateTime lt (\S+?)&", q).groups()
        lo, hi = (dt.datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) for x in (lo, hi))
        return {"value": [{"id": i, "receivedDateTime": v[0].astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "from": {"emailAddress": {"address": v[1]}}, "toRecipients": [], "subject": v[2],
                           "body": {"contentType": "text", "content": v[3]}, "parentFolderId": "INBOX1", "isRead": False}
                          for i, v in GRAPH.items() if lo <= v[0] < hi]}
    if "googleapis.com/calendar" in url:
        if url.endswith("/calendarList"):
            return {"items": [{"id": "primary", "summary": "Pat", "primary": True}]}
        lo, hi = dt.datetime.fromisoformat(params["timeMin"]), dt.datetime.fromisoformat(params["timeMax"])
        return {"items": [e for e in EVENTS if dt.datetime.fromisoformat(e["end"]["dateTime"]) > lo
                          and dt.datetime.fromisoformat(e["start"]["dateTime"]) < hi]}
    raise AssertionError(f"no stand-in for {url}")


_http.get_json = stand_in

# --- the sorting's AI steps, stood in: the judge and the card writer -----------------------------------------------------------
import think  # noqa: E402

think._engine_call = _no_network
seen = {"until": [], "today": [], "later": 0}


def fake_judge():
    seen["until"].append(os.environ.get("ASSISTANT_NOW"))
    seen["today"].append(common.ai_today())
    bound, upto = common.until_sql()
    rows = db.query("SELECT id, coalesce(subject,''), coalesce(body,'') FROM messages m WHERE NOT EXISTS (SELECT 1 FROM answered a"
                    " WHERE a.domain='judged' AND a.key='msg:' || m.id)" + bound, tuple(upto))
    now = dt.datetime.now()
    for mid, subj, body in rows:
        if "from the future" in body:
            seen["later"] += 1
        db.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, 'task', 'stand-in', ?)",
                   (f"msg:{mid}", now))
        if "send the invoice" in body:
            w = db.connect()
            try:
                tid = w.execute("INSERT INTO tasks (item_key, area, title, status, created_at, updated_at) VALUES"
                                " ('personal::invoice-104', 'Work', 'Send invoice 104', 'needs_me', ?, ?) RETURNING id", (now, now)).fetchone()[0]
                w.execute("INSERT INTO task_refs (task_id, kind, ref_type, value) VALUES (?, 'source', 'message', ?)", (tid, str(mid)))
            finally:
                w.close()
        if body.startswith("Paid"):
            db.execute("UPDATE tasks SET status='done', resolved_reason='the client paid', updated_at=? WHERE item_key='personal::invoice-104'",
                       (dt.datetime.now(),))
    return True, f"{len(rows)} judged (stand-in)"


def fake_write_items(owed_items, owed_msgs, forced=()):
    think.left.update(ran=True, items=[], msgs=[])
    return True, "written (stand-in)"


think.judge = fake_judge
think.write_items = fake_write_items

# --- 2. day windows ---------------------------------------------------------------------------------------------------------
for day, hours in ((dt.date(2026, 9, 1), 24), (dt.date(2026, 11, 1), 25), (dt.date(2027, 3, 14), 23)):
    s, e = replay.window(day, LA)
    check((e.timestamp() - s.timestamp()) / 3600 == hours and s.hour == 0 and e.hour == 0,
          f"window {day}: midnight to midnight, {hours} hours")

# --- 1. prepare and erase ----------------------------------------------------------------------------------------------------
import settings_page  # noqa: E402

check(settings_page.pass_job_off() is None, "the test home has no scheduled check of its own (Sync's switch touches nothing real)")
replay.dry_run()
check(os.path.isfile(os.path.join(home, "items.json")), "dry run moved nothing")
check(replay.prepare(start="2026-09-01") == 0, "prepare: every stand-in account answered")
check(settings_page.paused_flag(), "Sync is off through the page's own Sync setting")
replay.erase()
moved = ["Resources/Attachments/old.pdf", "items.json", "held.json", "think_state.json",
         "state/texts_link_convs.json", "state/mail_cache.duckdb", "state/payload_2026-11-20.json"]
check(not any(os.path.exists(os.path.join(home, m)) for m in moved) and "moved_to" not in replay.state()
      and not [d for d in os.listdir(home) if d.startswith("replay-erasing") or d == "To Delete"],
      "erase deleted the attachments, cards, held-back list, sorting state, mail copy and texts link matches outright; no To Delete folder")
check(all(open(os.path.join(home, r), encoding="utf-8").read() == t for r, t in KEEP.items()),
      "erase kept rules, writing style, sign-ins, mods, rule documents and the chat as they were")
got = db.query("SELECT name, company, notes, sent_count, received_count, strength, person_id FROM contacts")
check(got == [("Sam Lee", "Acme", "plumber", 0, 0, 0.0, 7)], f"contacts kept, counts back to zero: {got}")
w = db.connect()
next_id = w.execute("SELECT nextval('seq_message_id')").fetchone()[0]
w.close()
check(db.query("SELECT count(*) FROM messages")[0][0] == 0 and next_id > old_max,
      "the fresh database is empty and its ids start after the old ones")

# a text the page's texts link stored meanwhile, dated today: the replay's sorting must never see it
db.execute("INSERT INTO messages (channel, account, provider_id, ts, direction, body, ingested_at) VALUES"
           " ('sms','sms','gl:future', ?, 'in', 'from the future', now())", (dt.datetime.now(),))

# --- 3. two days ------------------------------------------------------------------------------------------------------------
check(replay.run_week(limit_days=2) == 0, "run-week finished two days")
recs = replay.days()
d1, d2 = recs[0], recs[1]
check(d1["sources"] == {"mail pat@example.com": 2, "mail pat@work.example": 1, "Board Team": 1, "calendar pat@example.com": 1, "texts": 2},
      f"day 1 read each source for its day only: {d1['sources']}")
check(d2["sources"] == {"mail pat@example.com": 1, "mail pat@work.example": 0, "Board Team": 1, "calendar pat@example.com": 0, "texts": 1},
      f"day 2: the reply made that day, the mail just after midnight, the text filed once: {d2['sources']}")
check(db.query("SELECT count(*) FROM messages WHERE channel='sms' AND provider_id LIKE 'bk:%'")[0][0] == 3,
      "texts from two overlapping backups stored once each, nothing from before the start")
check(seen["until"][0].startswith("2026-09-01T23:59:59") and seen["today"][0] == dt.date(2026, 9, 1) and seen["later"] == 0,
      "the sort was told it is the end of day 1 and never shown the later text")
check(d1["cards_made"] == 1 and d1["cards_closed"] == 0 and d2["cards_closed"] == 1, f"card made day 1, closed day 2: {d1}, {d2}")
card = items.rows("source_key = 'task:personal::invoice-104'")[0]
check(card["state"] == "done" and "the client paid" in (card.get("assistant_did") or ""), "the card says why it closed")
check(card["created_at"].date() == dt.date(2026, 9, 1) and card["done_at"].date() == dt.date(2026, 9, 2)
      and "9/2" in card["assistant_did"] and f"{dt.date.today().month}/{dt.date.today().day} " not in card["assistant_did"],
      "the card's history is dated by the replay day, not the day the replay ran")
check(all(r[0] for r in db.query("SELECT replayed FROM live_items")), "every replayed card is marked")
import standing  # noqa: E402
w = db.connect()
for iid, rp in (("L90001", "2026-09-02"), ("L90002", None)):
    w.execute("INSERT INTO live_items (id, source_key, kind, area, title, state, created_at, updated_at, state_changed_at, extra, replayed)"
              " VALUES (?, ?, 'waiting', 'Work', 't', 'yours', now(), now(), now(), ?, ?)",
              (iid, "test:" + iid, json.dumps({"came_back": {"why": "date"}}), rp))
w.close()
check([c["id"] for c in standing._candidates({"kind": "drop_waiting", "area": "Work"})] == ["L90002"],
      "standing approvals pass over a replayed card and still take a new one")
db.execute("DELETE FROM live_items WHERE id IN ('L90001', 'L90002')")
check(replay.state()["last_done"] == "2026-09-02", "the last finished day is recorded")

# another program on the computer (the page) while the replay is under way: it imports nothing; its texts wait in the link's file
import textlink  # noqa: E402
import mail  # noqa: E402
from connections import _store  # noqa: E402
os.environ.pop("ASSISTANT_REPLAY")
mw = _store.MailWriter("pat@example.com")
mw.add("page-1", dt.datetime(2026, 11, 22, 9), "in", "x@example.org", "", "Refresh", "pulled by the page")
check(mw.commit() == 0 and not db.query("SELECT 1 FROM messages WHERE provider_id='page-1'"), "the page's Refresh stores nothing beside the replay")
check(textlink.store([{"conv": "c1", "text": "hi"}]) == (0, 0) and common.read_json(textlink.PENDING, {}).get("rows"),
      "a text from the texts link waits in its file, not lost")
check(mail.pull_now().startswith("Not pulled"), "Refresh says plainly why it does not pull")
os.environ["ASSISTANT_REPLAY"] = "1"
check(any(f.startswith("report-") for f in os.listdir(replay.REPORTS)), "a report was written")

# --- 5. stop and resume -----------------------------------------------------------------------------------------------------
board.FAIL["n"] = 1
check(replay.run_week(limit_days=1) == 1, "a day whose added chat type did not answer stops the run")
check(replay.state()["last_done"] == "2026-09-02", "the stopped day is not counted")
n3 = db.query("SELECT count(*) FROM messages WHERE provider_id = 'g4'")[0][0]
check(replay.run_week(limit_days=1) == 0 and replay.state()["last_done"] == "2026-09-03", "continue finishes the stopped day")
check(n3 in (0, 1) and db.query("SELECT count(*) FROM messages WHERE provider_id = 'g4'")[0][0] == 1, "nothing stored twice")
check(replay.days()[-1]["sources"]["mail pat@example.com"] == 1, "the finished day counts what its stopped try stored too")

# the engine's own judging payload script, as the real judge runs it: bounded by the day it is told, unbounded without
import subprocess  # noqa: E402
stats = os.path.join(LIVE, "core", "judgment_payload.py")
env = dict(os.environ, ASSISTANT_NOW="2026-09-03T23:59:59.999999")
bounded = subprocess.run([sys.executable, stats, "--stats"], capture_output=True, text=True, env=env).stdout
env.pop("ASSISTANT_NOW")
free = subprocess.run([sys.executable, stats, "--stats"], capture_output=True, text=True, env=env).stdout
check("unjudged messages: 0," in bounded and "unjudged messages: 1," in free,
      f"the judging payload leaves out what comes after the day it is told ({bounded.strip()[:60]} | {free.strip()[:60]})")

# --- 4. every outbound function refuses -------------------------------------------------------------------------------------
import alert  # noqa: E402
import invites  # noqa: E402
import mail  # noqa: E402
import mail_alerts  # noqa: E402
import ready  # noqa: E402
import send  # noqa: E402
import standing  # noqa: E402
import standing_send  # noqa: E402
import textlink  # noqa: E402

mid = db.query("SELECT id FROM messages WHERE provider_id = 'g1'")[0][0]
OUT = {
    "phone alert": lambda: alert.send({"title": "x"}),
    "alerts for important cards": lambda: alert.alert_important("t"),
    "new-mail alert": lambda: mail_alerts.run("t"),
    "standing approvals": lambda: standing.apply("t"),
    "replies by standing approval": lambda: standing_send.apply("t", [{"id": "s1"}]),
    "card drafts to Drafts": lambda: ready.adopt_card_drafts("t"),
    "Send all": lambda: ready.send_all({"text": "{}"}),
    "snooze return (unread at the service)": lambda: mail.wake(),
    "archive at the mail service": lambda: mail._act_one({"id": "t"}, mid, "archive", None, None),
    "owner's Send": lambda: send.send_owner_email({"id": "t"}),
    "standing send": lambda: send.send_standing({"id": "L1"}, "s1"),
    "connections.send": lambda: connections.send("pat@example.com", ["a@b.c"], [], "s", "b"),
    "connections.send_mime": lambda: connections.send_mime("pat@example.com", b"raw"),
    "Gmail send at the web layer": lambda: _http.post_json("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", "t", {}),
    "a change at the web layer": lambda: _http.call_json("PATCH", "https://graph.microsoft.com/v1.0/me/messages/x", "t", {}),
    "bytes posted at the web layer": lambda: _http.post_raw("https://graph.microsoft.com/v1.0/me/sendMail", "t", b"", "text/plain"),
    "a form post that is not a sign-in": lambda: _http.post_form("https://example.com/hook", {}),
    "calendar event added": lambda: gc.add_event({"id": "c4", "type": "google_calendar"}, "primary", {}),
    "invite answer": lambda: invites.respond({"id": "t"}, {"message": mid, "answer": "accept"}),
    "texts link start": lambda: textlink.start(),
    "texts link spawn": lambda: textlink._spawn(),
    "texts link take-over": lambda: textlink.take_back(),
    "texts link sending": lambda: textlink._send_loop(),
    "texts link take-back request": lambda: textlink.pass_check(),
}
for name, fn in OUT.items():
    try:
        got = fn()
        ok = isinstance(got, dict) and got.get("sent") is False and "replay" in str(got.get("result"))
    except replay_guard.Refused:
        ok = True
    except Exception as e:  # noqa: BLE001  anything else (the network stand-in above among them) is a failure
        ok = False
        name += f" ({type(e).__name__}: {str(e)[:80]})"
    check(ok, f"refused under the replay: {name}")
try:
    _http.post_form("https://oauth2.googleapis.com/token", {})
    token_ok = False
except AssertionError:          # it reached the (stand-in) network: a sign-in's renewal is still allowed, reading needs it
    token_ok = True
check(token_ok, "a sign-in's token renewal is still allowed")

# the picture-description step: not run under the replay, run outside it
ran_describe = []
real_describe = think.describe_texted
think.describe_texted = lambda: (ran_describe.append(1) or (True, "stand-in"))
think.think("describe-check")
check(not ran_describe, "under the replay the describe-texted-pictures step is not run")
os.environ.pop("ASSISTANT_REPLAY")
think.think("describe-check-2")
os.environ["ASSISTANT_REPLAY"] = "1"
check(len(ran_describe) == 1, "outside the replay the describe-texted-pictures step is run")
think.describe_texted = real_describe

# the model per step: under the replay card writing asks for sonnet and judging keeps the setting's model; outside it both use the setting
settings_page.think_model = lambda: "opus"
check(think.write_model() == "sonnet" and think.model() == "opus", "under the replay write items asks for sonnet, judge uses the setting's model")
os.environ.pop("ASSISTANT_REPLAY")
check(think.write_model() == "opus" and think.model() == "opus", "outside the replay write items and judge both use the setting's model")
os.environ["ASSISTANT_REPLAY"] = "1"

bad = [w for ok, w in results if not ok]
print(f"\n{len(results) - len(bad)} of {len(results)} passed")
try:
    import _cleanup
    _cleanup.remove(home)
except Exception:  # noqa: BLE001
    pass
sys.exit(1 if bad else 0)
