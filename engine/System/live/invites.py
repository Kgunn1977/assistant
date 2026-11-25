r"""Meeting invites in the Mail part: the bar at the top of an open email, and the owner's Accept / Maybe / Decline.

    show(message_id)        {ok, invite}: what, when (local time), where, organizer, what it clashes with on the calendar, and
                            the owner's current answer; invite is None when the email carries no meeting request. Asked of
                            the mail service (the invite is not stored), kept for a few minutes.
    respond(rec, got)       one press {"mail_invite": {"message", "answer": accept|tentative|decline, "note"}}: the answer goes
                            to the account's own calendar service, which tells the organizer and updates the calendar.
    parse_ics(text)         the first meeting request in an iCalendar text (Google style, or an Outlook .ics), or None
    from_event(message)     the same from a Microsoft eventMessage with its event

A mail connection type that can do this has invite_source(conn, provider_id) and invite_answer(conn, invite, answer, note).
"""
import datetime as dt
import json
import time

import common

ANSWERS = {"accept": "Accepted", "tentative": "Said maybe to", "decline": "Declined"}
KEEP = 300                      # seconds an invite is kept after it was read from the service
_CACHE = {}

# Windows time zone names (what Outlook writes in an .ics) -> IANA, for the common ones
WINDOWS_ZONES = {
    "Pacific Standard Time": "America/Los_Angeles", "Mountain Standard Time": "America/Denver",
    "US Mountain Standard Time": "America/Phoenix", "Central Standard Time": "America/Chicago",
    "Eastern Standard Time": "America/New_York", "Alaskan Standard Time": "America/Anchorage",
    "Hawaiian Standard Time": "Pacific/Honolulu", "UTC": "UTC", "GMT Standard Time": "Europe/London",
    "W. Europe Standard Time": "Europe/Berlin", "Central Europe Standard Time": "Europe/Budapest",
}


# --- reading an invite ------------------------------------------------------------------------------------------------
def _unfold(text):
    lines = []
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _unescape(v):
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _prop(line):
    head, _, value = line.partition(":")
    name, *params = head.split(";")
    p = {}
    for x in params:
        k, _, v = x.partition("=")
        p[k.upper()] = v.strip('"')
    return name.upper(), p, value


def _zone(name):
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(WINDOWS_ZONES.get(name, name))
    except Exception:  # noqa: BLE001 - no such zone or no zone data: the computer's own time stands in
        return None


def _local(naive, zone):
    """A naive wall-clock time in `zone` (None = this computer's zone), as a naive local time."""
    aware = naive.replace(tzinfo=zone) if zone else naive.astimezone()
    return aware.astimezone().replace(tzinfo=None)


def _ics_time(value, params):
    """(naive local datetime, all_day) from an iCalendar date or date-time."""
    value = value.strip()
    if params.get("VALUE") == "DATE" or (len(value) == 8 and value.isdigit()):
        return dt.datetime.strptime(value[:8], "%Y%m%d"), True
    if value.endswith("Z"):
        return _local(dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S"), dt.timezone.utc), False
    return _local(dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S"), _zone(params["TZID"]) if params.get("TZID") else None), False


def _mailto(v):
    return v[7:] if v.lower().startswith("mailto:") else v


def parse_ics(text):
    method, ev, inside, seen = "", {}, False, False
    for line in _unfold(text):
        up = line.strip().upper()
        if up == "BEGIN:VEVENT" and not seen:
            inside, ev = True, {"attendees": []}
        elif up == "END:VEVENT" and inside:
            inside, seen = False, True
        elif inside:
            name, p, v = _prop(line)
            if name in ("DTSTART", "DTEND"):
                try:
                    ev[name], ev["all_day"] = _ics_time(v, p)
                except ValueError:
                    return None
            elif name == "ORGANIZER":
                ev["organizer"], ev["organizer_email"] = p.get("CN", ""), _mailto(v)
            elif name == "ATTENDEE":
                ev["attendees"].append({"email": _mailto(v).lower(), "status": p.get("PARTSTAT", "").lower()})
            elif name in ("SUMMARY", "LOCATION", "UID", "DESCRIPTION"):
                ev[name.lower()] = _unescape(v)
        elif up.startswith("METHOD:"):
            method = up[7:].strip()
    if not seen or method not in ("REQUEST", "") or "DTSTART" not in ev:
        return None
    start = ev["DTSTART"]
    end = ev.get("DTEND") or (start + (dt.timedelta(days=1) if ev.get("all_day") else dt.timedelta(hours=1)))
    return {"what": ev.get("summary") or "(no title)", "start": start, "end": end, "all_day": bool(ev.get("all_day")),
            "where": ev.get("location", ""), "organizer": ev.get("organizer") or ev.get("organizer_email", ""),
            "organizer_email": ev.get("organizer_email", ""), "uid": ev.get("uid", ""), "attendees": ev["attendees"],
            "response": ""}


def _graph_time(node):
    raw = str((node or {}).get("dateTime") or "")[:19]
    zone = str((node or {}).get("timeZone") or "UTC")
    return _local(dt.datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S"), dt.timezone.utc if zone == "UTC" else _zone(zone))


def from_event(message):
    """From a Microsoft message read with its event: None unless it is a meeting request (not a cancellation or a reply)."""
    ev = (message or {}).get("event") or {}
    if str((message or {}).get("meetingMessageType") or "") != "meetingRequest" or not ev.get("id"):
        return None
    try:
        start, end = _graph_time(ev.get("start")), _graph_time(ev.get("end"))
    except ValueError:
        return None
    who = (ev.get("organizer") or {}).get("emailAddress") or {}
    return {"what": ev.get("subject") or "(no title)", "start": start, "end": end, "all_day": bool(ev.get("isAllDay")),
            "where": (ev.get("location") or {}).get("displayName") or "", "organizer": who.get("name") or who.get("address", ""),
            "organizer_email": who.get("address", ""), "event_id": ev["id"], "uid": ev.get("iCalUId") or "", "attendees": [],
            "response": {"accepted": "accept", "tentativelyAccepted": "tentative", "declined": "decline"}
            .get((ev.get("responseStatus") or {}).get("response"), "")}


# --- what it clashes with ---------------------------------------------------------------------------------------------
def clashes(inv):
    """The events already on the calendar that overlap the invite (all-day events do not count)."""
    import mail
    if inv["all_day"]:
        return []
    con = mail._read(1)
    try:
        got = con.execute("SELECT start_ts, end_ts, summary, calendar FROM calendar_events WHERE NOT all_day AND start_ts < ? AND end_ts > ?"
                          " ORDER BY start_ts", [inv["end"], inv["start"]]).fetchall()
    finally:
        con.close()
    out = []
    for s, e, summary, cal in got:
        if s == inv["start"] and e == inv["end"] and str(summary or "") == inv["what"]:
            continue            # the invite itself, once it is on the calendar
        out.append({"what": summary or "(no title)", "from": s.strftime("%H:%M"), "to": e.strftime("%H:%M"), "calendar": cal or ""})
    return out[:6]


def _when_text(inv):
    s, e = inv["start"], inv["end"]
    day = f"{s:%A} {s:%B} {s.day}"
    if inv["all_day"]:
        return day + ", all day"
    clock = lambda t: f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"  # noqa: E731
    return f"{day}, {clock(s)} to {clock(e)}" + ("" if s.date() == e.date() else f" ({e:%A %B} {e.day})")


def _public(inv):
    out = {k: inv[k] for k in ("what", "where", "organizer", "organizer_email", "response")}
    out.update(when=_when_text(inv), start=inv["start"].isoformat(timespec="minutes"), end=inv["end"].isoformat(timespec="minutes"),
               clashes=clashes(inv))
    return out


# --- the page's door and press ----------------------------------------------------------------------------------------
def _message(message_id):
    import mail
    con = mail._read(1)
    try:
        row = con.execute(mail.SELECT + " AND m.id = ?", [int(message_id)]).fetchone()
    finally:
        con.close()
    return mail._row(row) if row else None


def _service(r):
    import connections
    conn, mod = connections.mailbox(r["account"])
    return (conn, mod) if conn is not None and hasattr(mod, "invite_source") else (None, None)


def read(message_id):
    """(invite dict, None) or (None, reason): the invite as the service holds it, kept a few minutes."""
    hit = _CACHE.get(int(message_id))
    if hit and time.time() - hit[0] < KEEP:
        return hit[1], None
    r = _message(message_id)
    if not r:
        return None, "That email is not here any more."
    conn, mod = _service(r)
    if conn is None:
        return None, ""
    try:
        inv = mod.invite_source(conn, r["_pid"])
    except Exception as e:  # noqa: BLE001
        return None, f"The invite could not be read from {r['account']} ({type(e).__name__})."
    if inv:
        inv["account"] = r["account"]
    _CACHE[int(message_id)] = (time.time(), inv)
    return inv, None


def show(message_id):
    inv, why = read(message_id)
    if why:
        return {"ok": False, "error": why}
    return {"ok": True, "invite": _public(inv) if inv else None}


def respond(rec, got):
    """The press. Returns the act_on_answer result; a refusal says why in plain words and changes nothing."""
    import replay_guard
    replay_guard.refuse("an answer to a meeting invite")

    def no(words):
        return {"ok": True, "items": [], "result": "Not done: " + words}
    try:
        mid, answer, note = int(got["message"]), str(got["answer"]), str(got.get("note") or "").strip()[:500]
    except (KeyError, ValueError, TypeError):
        return {"ok": False, "error": "That press could not be read. Nothing was changed.", "items": []}
    if answer not in ANSWERS:
        return {"ok": False, "error": "That press could not be read. Nothing was changed.", "items": []}
    inv, why = read(mid)
    if why or not inv:
        return no(why or "that email carries no meeting invite. Nothing was changed.")
    r = _message(mid)
    conn, mod = _service(r)
    if conn is None or not hasattr(mod, "invite_answer"):
        return no(f"{r['account']} cannot answer invites from here. Nothing was changed.")
    try:
        mod.invite_answer(conn, inv, answer, note)
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ == "NotAllowed":
            return no(f"the sign-in for {r['account']} does not allow answering invites yet. To allow it, open Setup, "
                      "pick that account and press Sign in again.")
        if type(e).__name__ == "NotFound":
            return no(f"{r['account']}'s calendar does not hold this meeting (it may have been cancelled or moved). Nothing was changed.")
        return no(f"{r['account']} refused it ({type(e).__name__}). Nothing was changed.")
    _CACHE.pop(mid, None)
    common.log_line(common.os.path.join(common.LOGS, "mail.log"), f"{rec.get('id')} invite {answer} {mid} {r['account']}")
    return {"ok": True, "items": [], "result": f"{ANSWERS[answer]} \"{inv['what']}\". {inv['organizer'] or 'The organizer'} is told."}
