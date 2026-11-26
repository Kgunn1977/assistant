r"""The replay's readers: one day of each source, read straight from the source and stored by the shared writers.

Each reader takes one day's window, [start, end) as moments in time (the day's midnight to the next midnight in the owner's
zone, worked out by replay.py), and stores only what falls in it, through connections._store, so the usual rules decide what
is already held. They only read: the replay's guard (replay_guard) refuses any change at a service below them.

    mail_day(conn, start, end)      Gmail (after:/before: in seconds) or Microsoft Graph (receivedDateTime ge/lt), sent and
                                    received, with attachments
    calendar_day(conn, start, end)  events whose start falls on the day, as each event is today

An added connection type (a chat app, say) reads its own day with replay_day in its own module (CONNECTIONS.md); replay.py
calls it, and this file names none.

Texts never come from phone backups: that source is gone (the owner's ruling). Texts reach the assistant only through the
Google Messages link.
"""
import datetime as dt
import os

import common
from connections import _store

FOLDER = os.path.join(common.paths.STATE, "replay")


def _epoch(when):
    return when.timestamp()


def _local(when):
    """A moment as the stored times are written: this computer's wall clock, no zone."""
    return when.astimezone().replace(tzinfo=None)


class _DayWriter(_store.MailWriter):
    """The usual mail writer, keeping only the day: a provider's search edges are a little loose, the day's are exact."""

    def __init__(self, account, start, end):
        super().__init__(account)
        self.lo, self.hi = _local(start), _local(end)
        self.outside = 0

    def add(self, provider_id, ts, *a, **k):
        if not (self.lo <= ts < self.hi):
            self.outside += 1
            return
        super().add(provider_id, ts, *a, **k)


# --- mail -------------------------------------------------------------------------------------------------------------
def mail_day(conn, start, end):
    """Messages stored for one mailbox and one day."""
    import connections
    mod = connections.module(conn["type"])
    if conn["type"] == "google_mail":
        return _gmail_day(mod, conn, start, end)
    if conn["type"] == "microsoft_mail":
        return _graph_day(mod, conn, start, end)
    raise RuntimeError(f"the replay has no day reader for {conn['type']}")


def gmail_query(start, end):
    """Gmail's search for the day, a minute wide at each edge (the writer keeps the exact day)."""
    return f"after:{int(_epoch(start)) - 60} before:{int(_epoch(end)) + 60}"


def _gmail_day(gm, conn, start, end):
    account = conn["address"]
    token = gm.token_for(conn)
    names = gm._label_names(token)
    held = _store.held_ids(account)
    writer = _DayWriter(account, start, end)
    ids = [i for i in gm._ids(token, gmail_query(start, end), gm.LIST_MOST) if i not in held]
    for mid in ids[::-1]:                       # the listing is newest first: store from the oldest
        gm._one(token, mid, account, writer, names)
    return writer.commit()


def graph_url(start, end, select):
    s, e = start.astimezone(dt.timezone.utc), end.astimezone(dt.timezone.utc)
    return (f"https://graph.microsoft.com/v1.0/me/messages?$filter=receivedDateTime ge {s:%Y-%m-%dT%H:%M:%SZ}"
            f" and receivedDateTime lt {e:%Y-%m-%dT%H:%M:%SZ}&$select={select}&$orderby=receivedDateTime asc&$top=50").replace(" ", "%20")


def _graph_day(ms, conn, start, end):
    account = conn["address"]
    token = ms._token(conn)
    folders = ms._kinds(conn, token)
    held = _store.held_ids(account)
    writer = _DayWriter(account, start, end)
    url = graph_url(start, end, ms.SELECT)
    while url:
        page = ms._get(url, token)
        for m in page.get("value", []):
            if m.get("isDraft") or m["id"] in held:     # every folder, sent mail too; a draft is not mail yet
                continue
            ms._one(token, m, account, writer, folders)
        url = page.get("@odata.nextLink")
    return writer.commit()


# --- calendar ---------------------------------------------------------------------------------------------------------
def calendar_day(conn, start, end):
    """Events whose start falls on the day, each as the calendar has it now. Returns how many."""
    import urllib.parse
    import connections
    gc = connections.module("google_calendar")
    token = gc._mail().token_for(conn)
    lo, hi = _local(start), _local(end)
    cals = gc._http.get_json(f"{gc.API}/users/me/calendarList", token).get("items", [])
    rows = []
    for cal in cals:
        name, page = cal.get("summary") or cal["id"], None
        while True:
            got = gc._http.get_json(f"{gc.API}/calendars/{urllib.parse.quote(cal['id'], safe='')}/events", token,
                                    {"timeMin": start.isoformat(), "timeMax": end.isoformat(), "singleEvents": "true",
                                     "orderBy": "startTime", "maxResults": 250, "pageToken": page})
            for e in got.get("items", []):
                row = None if e.get("status") == "cancelled" else gc.row_of(e, name)
                if row and lo <= row[3] < hi:
                    rows.append(row)
            page = got.get("nextPageToken")
            if not page:
                break
    _store.calendar_events(rows, prune=False)       # earlier days stay: never the rolling window's pruning
    return len(rows)
