r"""The page's Calendar part: the events the assistant already gathers (calendar_events), for the calendar view; and the changes
the owner makes to his calendars, from the part's New event form or by telling his assistant (chat.py, the calendar ACTION).

    events()      {"ok": True, "calendars": [names], "writable": [names], "events": [...]} or {"ok": False, "error": plain words, "busy": True}
    add(body)     a new event, from the owner's Save in the part's form or his words to the assistant: made on Google through the
                  calendar connection's own sign-in (google_calendar.add_event, the path invites already use), then stored from
                  Google's reply at once
    find(title, day)       the events on calendars he can change that match a title and/or a day (the stored window first, then
                           Google itself for a day outside it)
    change(body)  one event changed: the event named by title and/or day (exactly one must match), only the fields given
    delete(body)  one event taken off its calendar, named the same way
"""
import datetime as dt
import json
import re
import time

import db

# Kevin's rule for anything added to the calendar: a reminder one day ahead and one 2 hours ahead (spec 1.4)
REMINDERS = {"useDefault": False, "overrides": [{"method": "popup", "minutes": 24 * 60}, {"method": "popup", "minutes": 120}]}
WRITABLE_SECONDS = 600          # which calendars he can add to is asked of Google again after this long
_W = {"at": 0.0, "list": []}


def writable():
    """[{"conn", "id", "name", "own"}] of the calendars he can add events to, from every calendar connection that can add one."""
    if time.time() - _W["at"] < WRITABLE_SECONDS:
        return _W["list"]
    out = []
    try:
        import connections
        for c in connections.listed("calendar"):
            mod = connections.module(c["type"])
            if hasattr(mod, "add_event"):
                try:
                    out += [{"conn": c["id"], "id": cid, "name": nm, "own": str(cid).lower() == str(c.get("address") or "").lower()}
                            for cid, nm in mod.writable(c)]
                except Exception:  # noqa: BLE001  that account is not reachable now: its calendars are not offered
                    pass
    except Exception:  # noqa: BLE001
        pass
    _W.update(at=time.time(), list=out)
    return out


def default_calendar():
    """The calendar an event goes on when the owner names none: the only one he can add to, else his own account's main one."""
    w = writable()
    if len(w) == 1:
        return w[0]
    own = [c for c in w if c.get("own")]
    return own[0] if len(own) == 1 else None


def _shape(row):
    eid, cal, title, start, end, all_day, place, about = row[:8]
    end = end or start
    return {"id": str(eid), "calendar": str(cal), "title": title or "(no title)", "all_day": bool(all_day),
            "start": start.date().isoformat() if all_day else start.isoformat(timespec="minutes"),
            "end": end.date().isoformat() if all_day else end.isoformat(timespec="minutes"),
            "location": place or "", "description": (about or "")[:4000]}


def _when(d0, all_day, start, end):
    """Google's start and end for a day, all day or from start to end (HH:MM, his computer's own zone)."""
    if all_day:
        return {"start": {"date": d0.isoformat()}, "end": {"date": (d0 + dt.timedelta(days=1)).isoformat()}}
    at = lambda hm: dt.datetime.fromisoformat(f"{d0.isoformat()}T{hm}").astimezone().isoformat()      # noqa: E731
    return {"start": {"dateTime": at(start)}, "end": {"dateTime": at(end)}}


def _conn(cal):
    import connections
    conn = next((c for c in connections.listed("calendar") if c["id"] == cal["conn"]), None)
    return conn, (connections.module(conn["type"]) if conn else None)


def _google(call, verb, done):
    """(Google's answer, '') or (None, the plain reason nothing was done)."""
    from connections import _http
    try:
        return call(), ""
    except _http.Refused as e:
        if e.status in (401, 403):
            return None, (f"Google did not let me {verb} that calendar. If this keeps happening, sign in to "
                          "the calendar again with /assistant:change accounts.")
        return None, f"Google did not take the change (it answered {e.status}). Nothing was {done}."
    except Exception:  # noqa: BLE001  the network, a sign-in that cannot be renewed now
        return None, f"Google could not be reached, so nothing was {done}. Check the connection and try again."


LATE = "I made the change at Google, but my own copy is busy, so it will show at the next check."


def _later(out, stored):
    """The result, with the plain note when my own copy could not take the change now."""
    return out if stored else dict(out, late=True, note=LATE)


def _store_row(row):
    from connections import _store
    try:                # stored now, from Google's own reply: it shows here even while Sync is off; the next sync keeps it the same
        _store.calendar_events([row], prune=False)
        return True
    except Exception:  # noqa: BLE001  the database is held now: the next sync stores it
        return False


def add(body):
    """{"ok": True, "event": {...}} or {"ok": False, "error": plain words}. body: title, calendar, day (YYYY-MM-DD), all_day,
    start and end (HH:MM), place, notes; default_ok: the owner's main calendar when he named none (his words to the assistant)."""
    b = body if isinstance(body, dict) else {}
    title = " ".join(str(b.get("title") or "").split())[:300]
    day, all_day = str(b.get("day") or ""), bool(b.get("all_day"))
    start, end = str(b.get("start") or ""), str(b.get("end") or "")
    if not title:
        return {"ok": False, "error": "Give the event a title."}
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return {"ok": False, "error": "Choose the day."}
    if not all_day and not (re.fullmatch(r"\d{2}:\d{2}", start) and re.fullmatch(r"\d{2}:\d{2}", end) and end > start):
        return {"ok": False, "error": "Choose a start and an end time, the end after the start, or tick All day."}
    name = str(b.get("calendar") or "").strip()
    if name or not b.get("default_ok"):
        cal = next((w for w in writable() if w["name"].lower() == name.lower()), None)
    else:
        cal = default_calendar()
    if cal is None:
        names = ", ".join(w["name"] for w in writable())
        return {"ok": False, "error": "Choose one of your calendars you can add to" + (f": {names}." if names and b.get("default_ok") else ".")}
    try:
        d0 = dt.date.fromisoformat(day)
    except ValueError:
        return {"ok": False, "error": "Choose the day."}
    event = dict(_when(d0, all_day, start, end), summary=title, reminders=json.loads(json.dumps(REMINDERS)))
    if str(b.get("place") or "").strip():
        event["location"] = str(b["place"]).strip()[:300]
    if str(b.get("notes") or "").strip():
        event["description"] = str(b["notes"]).strip()[:4000]
    conn, mod = _conn(cal)
    if conn is None:
        return {"ok": False, "error": "That calendar's account is not connected any more."}
    got, why = _google(lambda: mod.add_event(conn, cal["id"], event), "add to", "added")
    if why:
        return {"ok": False, "error": why}
    row = mod.row_of(got, cal["name"]) if isinstance(got, dict) else None
    if row is None:
        return {"ok": False, "error": "Google took the event but did not say when it is; it shows here the next time I check for messages."}
    return _later({"ok": True, "event": _shape(row)}, _store_row(row))


# --- one event, found by its title and day, changed or taken off -------------------------------------------------------------
def find(title="", day=None):
    """[{"cal": writable entry, "event_id", "row"}] of the events on calendars he can change that match: the words of the title
    (every one, in any order) and/or the day. The stored window first; for a day outside it, Google itself."""
    words = [w for w in re.findall(r"[a-z0-9']+", str(title or "").lower()) if len(w) > 1]
    if not words and day is None:
        return []
    cals = {w["name"]: w for w in writable()}
    out = []
    con = None
    for _ in range(6):
        con = db.try_connect(read_only=True)
        if con is not None:
            break
        time.sleep(0.5)
    if con is not None:
        try:
            rows = con.execute("SELECT event_id, calendar, coalesce(summary, ''), start_ts, end_ts, coalesce(all_day, false), coalesce(location, ''), "
                               "coalesce(description, ''), updated_at FROM calendar_events WHERE start_ts IS NOT NULL ORDER BY start_ts").fetchall()
        finally:
            con.close()
        for r in rows:
            if r[1] in cals and (day is None or r[3].date() == day) and all(w in str(r[2]).lower() for w in words):
                out.append({"cal": cals[r[1]], "event_id": str(r[0]), "row": tuple(r)})
    if not out and day is not None:
        for cal in cals.values():
            conn, mod = _conn(cal)
            if conn is None or not hasattr(mod, "day_events"):
                continue
            try:
                got = mod.day_events(conn, cal["id"], day)
            except Exception:  # noqa: BLE001  that calendar is not reachable now
                continue
            for e in got:
                row = mod.row_of(e, cal["name"])
                if row and all(w in str(row[2] or "").lower() for w in words):
                    out.append({"cal": cal, "event_id": str(e["id"]), "row": row})
    return out


def _one(b):
    """(the one matching event, '') or (None, plain words saying none or which)."""
    day = None
    if b.get("on_day"):
        try:
            day = dt.date.fromisoformat(str(b["on_day"]))
        except ValueError:
            return None, "I could not read the day of the event you meant."
    hits = find(b.get("find") or "", day)
    if not hits:
        return None, "I found no event like that on a calendar you can change" + (f" on {day.month}/{day.day}" if day else "") + ", so nothing was changed."
    if len(hits) > 1:
        return None, ("More than one event matches, so nothing was changed: "
                      + "; ".join(f"{h['row'][2]} {_said_when(h['row'])} ({h['cal']['name']})" for h in hits[:5]) + ". Which one?")
    return hits[0], ""


def _said_when(row):
    start, all_day = row[3], row[5]
    day = f"{start.strftime('%a')} {start.month}/{start.day}"
    return f"{day}, all day" if all_day else f"{day} at {start.strftime('%I:%M %p').lstrip('0')}"


def change(body):
    """{"ok", "event", "was"} or {"ok": False, "error"}. body: find (words of its title) and/or on_day (YYYY-MM-DD) name the event;
    title, day, all_day, start, end, place, notes are the new values, only those given. A new start alone keeps its length."""
    b = {k: v for k, v in (body if isinstance(body, dict) else {}).items() if v not in (None, "")}     # empty or null: not given
    hit, why = _one(b)
    if hit is None:
        return {"ok": False, "error": why}
    row = hit["row"]
    fields = {}
    if str(b.get("title") or "").strip():
        fields["summary"] = " ".join(str(b["title"]).split())[:300]
    if str(b.get("place") or "").strip():
        fields["location"] = str(b["place"]).strip()[:300]
    if str(b.get("notes") or "").strip():
        fields["description"] = str(b["notes"]).strip()[:4000]
    if b.get("day") or b.get("start") or b.get("end") or ("all_day" in b and bool(b["all_day"]) != bool(row[5])):
        try:
            d0 = dt.date.fromisoformat(str(b.get("day"))) if b.get("day") else row[3].date()
        except ValueError:
            return {"ok": False, "error": "I could not read the new day, so nothing was changed."}
        all_day = bool(b["all_day"]) if "all_day" in b else (bool(row[5]) and not b.get("start"))
        if not all_day:
            old_len = (row[4] - row[3]) if row[4] and not row[5] else dt.timedelta(hours=1)
            start = str(b.get("start") or ("" if row[5] else row[3].strftime("%H:%M")))
            if not re.fullmatch(r"\d{2}:\d{2}", start):
                return {"ok": False, "error": "Say what time it starts, so nothing was changed."}
            end = str(b.get("end") or "")
            if not end:
                e = dt.datetime.combine(d0, dt.time.fromisoformat(start)) + old_len
                end = e.strftime("%H:%M") if e.date() == d0 else "23:59"
            if not (re.fullmatch(r"\d{2}:\d{2}", end) and end > start):
                return {"ok": False, "error": "The end must be after the start, so nothing was changed."}
            fields.update(_when(d0, False, start, end))
        else:       # all day: an event that was all day keeps how many days it spans
            days = max(1, (row[4].date() - row[3].date()).days) if row[5] and row[4] else 1
            fields.update({"start": {"date": d0.isoformat()}, "end": {"date": (d0 + dt.timedelta(days=days)).isoformat()}})
    if not fields:
        return {"ok": False, "error": "You did not say what to change, so nothing was changed."}
    conn, mod = _conn(hit["cal"])
    if conn is None or not hasattr(mod, "change_event"):
        return {"ok": False, "error": "That calendar's account is not connected any more."}
    got, why = _google(lambda: mod.change_event(conn, hit["cal"]["id"], hit["event_id"], fields), "change", "changed")
    if why:
        return {"ok": False, "error": why}
    new = mod.row_of(got, hit["cal"]["name"]) if isinstance(got, dict) and got.get("id") else None
    stored = _store_row(new) if new is not None else True
    return _later({"ok": True, "event": _shape(new) if new else None, "was": _shape(row)}, stored)


def delete(body):
    """{"ok", "was"} or {"ok": False, "error"}. body: find and/or on_day name the one event to take off its calendar."""
    b = body if isinstance(body, dict) else {}
    hit, why = _one(b)
    if hit is None:
        return {"ok": False, "error": why}
    conn, mod = _conn(hit["cal"])
    if conn is None or not hasattr(mod, "delete_event"):
        return {"ok": False, "error": "That calendar's account is not connected any more."}
    _got, why = _google(lambda: mod.delete_event(conn, hit["cal"]["id"], hit["event_id"]), "change", "removed")
    if why:
        return {"ok": False, "error": why}
    try:                # off the page now; otherwise the next sync agrees
        db.execute("DELETE FROM calendar_events WHERE event_id = ?", (hit["event_id"],))
        stored = True
    except Exception:  # noqa: BLE001  the database is held now: the next sync drops it
        stored = False
    return _later({"ok": True, "was": _shape(hit["row"])}, stored)


def said(out, do):
    line_ = _said(out, do)
    return line_ + " " + out["note"] if out.get("note") else line_


def _said(out, do):
    """One plain line for the reply: exactly what was done, on which calendar."""
    def line(e):
        if not e:
            return ""
        if e["all_day"]:
            d = dt.date.fromisoformat(e["start"])
            when = f"{d.strftime('%a')} {d.month}/{d.day}, all day"
        else:
            s, t = dt.datetime.fromisoformat(e["start"]), dt.datetime.fromisoformat(e["end"])
            when = f"{s.strftime('%a')} {s.month}/{s.day}, {s.strftime('%I:%M %p').lstrip('0')} to {t.strftime('%I:%M %p').lstrip('0')}"
        return f"\"{e['title']}\", {when}" + (f", at {e['location']}" if e.get("location") else "") + f", on your {e['calendar']} calendar"
    if not out.get("ok"):
        return str(out.get("error") or "That did not go through.")
    if do == "add":
        return f"Added to your calendar: {line(out['event'])}."
    if do == "change":
        return f"Changed {line(out['was'])}" + (f"; it is now {line(out['event'])}." if out.get("event") else ".")
    return f"Taken off your calendar: {line(out['was'])}. Google keeps it in that calendar's trash for 30 days."


def events():
    """Every gathered event (the gathering keeps a rolling window: a week back, two weeks ahead), oldest first."""
    con = None
    for _ in range(6):
        con = db.try_connect(read_only=True)
        if con is not None:
            break
        time.sleep(0.5)
    if con is None:
        return {"ok": False, "busy": True, "error": "Your calendar is being brought up to date. It shows in a moment."}
    try:
        rows = con.execute("SELECT event_id, calendar, coalesce(summary, ''), start_ts, end_ts, coalesce(all_day, false), coalesce(location, ''), "
                           "coalesce(description, '') FROM calendar_events WHERE start_ts IS NOT NULL ORDER BY start_ts").fetchall()
    finally:
        con.close()
    out = [_shape(r) for r in rows]
    can = [w["name"] for w in writable()]
    return {"ok": True, "calendars": sorted({e["calendar"] for e in out} | set(can)), "writable": sorted(set(can)), "events": out}
