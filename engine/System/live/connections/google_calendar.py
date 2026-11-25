r"""Google Calendar: every calendar one Google account can see, read; and the changes the owner makes from his page's Calendar
part or by telling his assistant (a new event, a changed one, one taken off), through the same sign-in invites already answer
with (calendar.events)."""
import datetime as dt
import urllib.parse

from connections import _http
import connections

TYPE = "google_calendar"
NAME = "Google Calendar"
KIND = "calendar"
CAN_SEND = False
APP = "google"
ASKS = []


def _mail():                    # the Google sign-in and its registration questions live with Google mail
    return connections.module("google_mail")


SETUP = """\
WHAT THIS CONNECTS
The calendars one Google account can see: your own, and any shared with you (a family
calendar, a room calendar at work). I read them, and add, change or remove an
event only when you ask me to. It shows today's events on
your page from the calendars you choose, and uses the rest to know when you are busy.

WHAT YOU NEED
- The one-time Google registration from "Gmail or Google Workspace mail", steps 1 to 9. If you
  already connected a Google mailbox, that is done. If not, open that connection's steps and
  do 1 to 9 first (step 3 there already turns on the calendar).

CONNECTING
1. In the setup window press "Sign in". Your browser opens Google's own sign-in page.
2. Pick the account whose calendars you want. On "Google hasn't verified this app" click
   "Advanced", then "Go to My assistant (unsafe)". It is your own app.
3. Tick the box to see your calendars and click "Continue".
4. The browser says "Signed in." Close that tab.
5. Back in the setup window, on the "Your calendar" step, tick the calendars whose events
   should show under Today on your page.

IF SOMETHING GOES WRONG
- A calendar you expected is missing: in Google Calendar on the web, check it is listed under
  "My calendars" or "Other calendars" for that same account. Only listed calendars are read.
"""

API = "https://www.googleapis.com/calendar/v3"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly",
          "https://www.googleapis.com/auth/calendar.events"]   # events: answering meeting invites (invites.py)
PAST_DAYS, FUTURE_DAYS = 7, 14


def connect(conn, say=print, answers=None):
    answer = _mail().sign_in(conn, SCOPES, say)
    cals = _http.get_json(f"{API}/users/me/calendarList", answer["access_token"]).get("items", [])
    primary = [c["id"] for c in cals if c.get("primary")]
    conn["address"] = (primary[0] if primary else "").lower()
    conn["label"] = conn["address"] or "Google Calendar"
    return conn


def calendars(conn):
    """[(calendar name, True when it is the account's own)] for the "which calendar shows" choice."""
    cals = _http.get_json(f"{API}/users/me/calendarList", _mail().token_for(conn)).get("items", [])
    return [(c.get("summary") or c["id"], bool(c.get("primary"))) for c in cals]


def check(conn):
    return f"{conn.get('label')}: reachable, {len(calendars(conn))} calendars"


def writable(conn):
    """[(calendar id, name)] of the calendars this account may add events to: its own, and those shared with it to change."""
    cals = _http.get_json(f"{API}/users/me/calendarList", _mail().token_for(conn)).get("items", [])
    return [(c["id"], c.get("summary") or c["id"]) for c in cals if c.get("accessRole") in ("owner", "writer")]


def add_event(conn, cal_id, event):
    """One new event on one of this account's calendars, made by the owner's own Save on his page. Google's copy of it."""
    return _http.call_json("POST", f"{API}/calendars/{urllib.parse.quote(cal_id, safe='')}/events", _mail().token_for(conn), event)[1]


def change_event(conn, cal_id, event_id, fields):
    """One event changed (only the fields given: summary, start, end, location, description), on the owner's own words. Google's copy."""
    return _http.call_json("PATCH", f"{API}/calendars/{urllib.parse.quote(cal_id, safe='')}/events/{urllib.parse.quote(event_id, safe='')}",
                           _mail().token_for(conn), fields)[1]


def delete_event(conn, cal_id, event_id):
    """One event taken off the calendar, on the owner's own words. Google keeps it in the calendar's trash for 30 days."""
    _http.call_json("DELETE", f"{API}/calendars/{urllib.parse.quote(cal_id, safe='')}/events/{urllib.parse.quote(event_id, safe='')}",
                    _mail().token_for(conn), ok=(200, 204, 410))


def day_events(conn, cal_id, day):
    """The events of one calendar on one day (a date), for an event outside the gathered window."""
    start = dt.datetime.combine(day, dt.time()).astimezone()
    got = _http.get_json(f"{API}/calendars/{urllib.parse.quote(cal_id, safe='')}/events", _mail().token_for(conn),
                         {"timeMin": start.isoformat(), "timeMax": (start + dt.timedelta(days=1)).isoformat(), "singleEvents": "true",
                          "orderBy": "startTime", "maxResults": 100})
    return [e for e in got.get("items", []) if e.get("status") != "cancelled"]


def row_of(e, name):
    """One Google event as the gathering stores it (calendar_events), or None for one with no start."""
    start, all_day = _when(e.get("start"))
    end, _ = _when(e.get("end"))
    if start is None:
        return None
    updated = dt.datetime.fromisoformat(e["updated"].replace("Z", "")) if e.get("updated") else None
    me = next((a for a in e.get("attendees") or [] if isinstance(a, dict) and a.get("self")), None)
    return (e["id"], name, e.get("summary"), start, end, all_day, e.get("location"), e.get("description"), updated,
            (me or {}).get("responseStatus"))      # his own answer to an invitation; None on his own events


def _when(node):
    """Google gives dateTime for timed events, date for all-day ones."""
    if not node:
        return None, False
    if node.get("dateTime"):
        return dt.datetime.fromisoformat(node["dateTime"]).astimezone().replace(tzinfo=None), False
    if node.get("date"):
        return dt.datetime.fromisoformat(node["date"]), True
    return None, False


def gather(conn, ctx):
    """Adds this account's events to ctx.events; the caller stores the whole window at once."""
    token = _mail().token_for(conn)
    now = dt.datetime.now().astimezone()
    window = {"timeMin": (now - dt.timedelta(days=PAST_DAYS)).isoformat(),
              "timeMax": (now + dt.timedelta(days=FUTURE_DAYS)).isoformat()}
    cals = _http.get_json(f"{API}/users/me/calendarList", token).get("items", [])
    n = 0
    for cal in cals:
        name = cal.get("summary") or cal["id"]
        page = None
        while True:
            got = _http.get_json(f"{API}/calendars/{urllib.parse.quote(cal['id'], safe='')}/events", token,
                                 {**window, "singleEvents": "true", "orderBy": "startTime", "maxResults": 250,
                                  "pageToken": page})
            for e in got.get("items", []):
                if e.get("status") == "cancelled":
                    continue
                row = row_of(e, name)
                if row is None:
                    continue
                ctx.events.append(row)
                n += 1
            page = got.get("nextPageToken")
            if not page:
                break
    return f"{n} events across {len(cals)} calendars"
