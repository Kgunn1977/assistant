r"""Acceptance: the page's Calendar part, in a scratch home (made-up events only; never the owner's).

  1. its door gives the gathered events of every calendar, oldest first, timed ones to the minute and all-day ones by date
     (the end the day after, as calendars keep it), each with its calendar, place and description; and the calendars' names;
  2. the door and EventCalendar's two files (the pinned release, as its makers ship it) answer only a signed-in browser;
  3. a new event: refused in plain words when something is missing; saved through the calendar connection's own add_event (Google
     stood in), stored at once from Google's reply, and only by a press with the page's check; the connection's add_event itself
     posts to Google's events address for that calendar with the calendar sign-in's token (the network call stood in).

    python tests\calendar_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


INSIDE = r'''
import datetime as dt, hashlib, json, os, secrets, socket, sys, time, urllib.request, urllib.error
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[1]), "live_page"))
import common, db, calendar_view
from connections import _store
db.init_schema()
sk = socket.socket(); sk.bind(("127.0.0.1", 0)); free = sk.getsockname()[1]; sk.close()
common.write_json(common.SETTINGS, {"page_port": free})
out = {}
d = dt.datetime(2030, 3, 4)
_store.calendar_events([("e2", "Family", "Dinner with Pat", d + dt.timedelta(hours=18), d + dt.timedelta(hours=20), False, "Pat's house", "Bring dessert.", d),
                        ("e1", "Work", "Site walk", d + dt.timedelta(hours=9), d + dt.timedelta(hours=10, minutes=30), False, "12 Elm Street", "", d),
                        ("e3", "Family", "Weekend trip", d + dt.timedelta(days=5), d + dt.timedelta(days=7), True, "", "", d)], prune=False)
got = calendar_view.events()
out["events"] = [got["ok"], got["calendars"], [[e["id"], e["calendar"], e["title"], e["start"], e["end"], e["all_day"], e["location"], e["description"]] for e in got["events"]]]
import local_site
srv = local_site.start(); port = srv.server_address[1]
tok, csrf = secrets.token_urlsafe(48), secrets.token_hex(32)
local_site._save("sessions", {hashlib.sha256(tok.encode()).hexdigest(): {"made": int(time.time()), "seen": int(time.time()), "exp": int(time.time()) + 3600, "len": 3600, "csrf": csrf}})
def get(path, signed):
    h = {"Host": f"127.0.0.1:{port}"}
    if signed: h["Cookie"] = f"{local_site.cookie_name()}={tok}"
    try:
        with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/{path}", headers=h), timeout=30) as r:
            return r.status, r.headers.get("Content-Type", ""), len(r.read())
    except urllib.error.HTTPError as e:
        return e.code, "", 0
out["door"] = [get("api/calendar/events", True)[:2], get("api/calendar/events", False)[0]]
out["files"] = [get("s/ec/event-calendar.min.js", True), get("s/ec/event-calendar.min.css", True), list(get("s/ec/event-calendar.min.js", False)[:2])]
import connections
from connections import _http
real_listed = connections.listed
connections.listed = lambda kind=None, *a, **k: [{"id": "c9", "type": "google_calendar", "kind": "calendar", "address": "o@example.com"}] if kind == "calendar" else real_listed(kind, *a, **k)
gc = connections.module("google_calendar")
real_add = gc.add_event
gc.writable = lambda conn: [("work@example.com", "Work"), ("pat@example.com", "Family")]
sent = []
gc.add_event = lambda conn, cid, ev: (sent.append([cid, ev]), dict(ev, id="g1", updated="2030-03-01T10:00:00.000Z"))[1]
calendar_view._W["at"] = 0
ok_body = {"title": "Crew  meeting", "calendar": "Work", "day": "2030-03-05", "all_day": False, "start": "07:30", "end": "08:30", "place": "Shop", "notes": "Bring the plans"}
out["refused in plain words"] = [calendar_view.add(dict(ok_body, title=""))["error"], calendar_view.add(dict(ok_body, end="07:00"))["error"][:30],
                                 calendar_view.add(dict(ok_body, calendar="Nobody"))["error"], len(sent)]
r = calendar_view.add(ok_body)
out["saved through the connection, stored at once"] = [r["ok"], r["event"]["calendar"], r["event"]["start"], r["event"]["title"], sent[0][0], sent[0][1]["summary"],
    "dateTime" in sent[0][1]["start"], [e["id"] for e in calendar_view.events()["events"] if e["id"] == "g1"], calendar_view.events()["writable"]]
r2 = calendar_view.add(dict(ok_body, all_day=True, title="Trip"))
out["all day"] = [sent[1][1]["start"], sent[1][1]["end"], r2["event"]["all_day"]]
def boom(conn, cid, ev): raise _http.Refused(403, "forbidden")
gc.add_event = boom
out["Google's no, said plainly"] = calendar_view.add(ok_body)["error"][:40]
def post(body, check=True):
    h = {"Host": f"127.0.0.1:{port}", "Cookie": f"{local_site.cookie_name()}={tok}", "Content-Type": "application/json"}
    if check: h["X-Brief-Csrf"] = csrf; h["Origin"] = f"http://127.0.0.1:{port}"
    rq = urllib.request.Request(f"http://127.0.0.1:{port}/api/calendar/add", data=json.dumps(body).encode(), method="POST", headers=h)
    try:
        with urllib.request.urlopen(rq, timeout=30) as r9:
            return r9.status, json.loads(r9.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
gc.add_event = lambda conn, cid, ev: dict(ev, id="g9")
out["the add door: a press with the page's check only"] = [post(ok_body)[0], post(ok_body)[1].get("ok"), post(ok_body, check=False)[0]]
calls = []
_http.call_json = lambda method, url, token, obj=None, **k: (calls.append([method, url, token, obj["summary"]]), (200, dict(obj, id="x")))[1]
gc._mail = lambda: type("M", (), {"token_for": staticmethod(lambda conn: "calendar-token")})
got = real_add({"id": "c9"}, "work@example.com", {"summary": "S", "start": {"date": "2030-03-05"}, "end": {"date": "2030-03-06"}})
out["the connection's add_event posts to Google with the calendar sign-in"] = [calls, got["id"]]
srv.shutdown()
print(json.dumps(out))
'''

WANT = {
    "events": [True, ["Family", "Work"], [
        ["e1", "Work", "Site walk", "2030-03-04T09:00", "2030-03-04T10:30", False, "12 Elm Street", ""],
        ["e2", "Family", "Dinner with Pat", "2030-03-04T18:00", "2030-03-04T20:00", False, "Pat's house", "Bring dessert."],
        ["e3", "Family", "Weekend trip", "2030-03-09", "2030-03-11", True, "", ""]]],
    "door": [[200, "application/json; charset=utf-8"], 401],
    "refused in plain words": ["Give the event a title.", "Choose a start and an end time", "Choose one of your calendars you can add to.", 0],
    "saved through the connection, stored at once": [True, "Work", "2030-03-05T07:30", "Crew meeting", "work@example.com", "Crew meeting", True, ["g1"], ["Family", "Work"]],
    "all day": [{"date": "2030-03-05"}, {"date": "2030-03-06"}, True],
    "Google's no, said plainly": "Google did not let me add to that calend",
    "the add door: a press with the page's check only": [200, True, 403],
    "the connection's add_event posts to Google with the calendar sign-in": [[["POST", "https://www.googleapis.com/calendar/v3/calendars/work%40example.com/events", "calendar-token", "S"]], "x"],
    "files": [[200, "text/javascript; charset=utf-8", 136808], [200, "text/css; charset=utf-8", 14673], [200, "text/html; charset=utf-8"]],      # signed out: the sign-in page, never the file
}


def engine_part():
    tmp = tempfile.mkdtemp(prefix="cal-")
    live = os.path.join(PKG, "engine", "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=120, encoding="utf-8")
    import _cleanup
    _cleanup.remove(tmp)
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        check("the engine checks ran", r.stderr.strip()[-1500:], "")
        return
    for k, v in WANT.items():
        check(k, got.get(k), v)


engine_part()
for name, ok, got, want in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n   got  {got}\n   want {want}"))
print(f"{sum(1 for r in results if r[1])}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
