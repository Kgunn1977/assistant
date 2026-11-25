r"""Acceptance: meeting invites (invites.py). One made-up Google-style invite (an .ics text) and one made-up Outlook-style
invite (a Microsoft eventMessage with its event) are read; the respond call to the account is a stand-in. Nothing outside
this process is touched.

    python tests\mail_invites_acceptance.py
"""
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine", "System", "live"))
import invites  # noqa: E402

fails = []


def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        fails.append(name)


GOOGLE = "\r\n".join(["BEGIN:VCALENDAR", "METHOD:REQUEST", "BEGIN:VEVENT", "UID:abc123@example.test",
                      "DTSTART:20301105T180000Z", "DTEND:20301105T190000Z", "SUMMARY:Planning\\, round two",
                      "LOCATION:Room 4", "ORGANIZER;CN=Sam Example:mailto:sam@example.test",
                      "ATTENDEE;PARTSTAT=NEEDS-ACTION:mailto:me@example.test", "END:VEVENT", "END:VCALENDAR"])
g = invites.parse_ics(GOOGLE)
utc = dt.datetime(2030, 11, 5, 18, 0, tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)
check("google: what", g and g["what"] == "Planning, round two")
check("google: start in local time", g and g["start"] == utc and g["end"] - g["start"] == dt.timedelta(hours=1))
check("google: where, organizer, uid", g and g["where"] == "Room 4" and g["organizer"] == "Sam Example" and g["uid"] == "abc123@example.test")
check("google: a cancellation is not an invite", invites.parse_ics(GOOGLE.replace("REQUEST", "CANCEL")) is None)
check("outlook .ics with a Windows zone", invites.parse_ics(GOOGLE.replace("DTSTART:20301105T180000Z", "DTSTART;TZID=Pacific Standard Time:20301105T100000")) is not None)

msg = {"meetingMessageType": "meetingRequest", "event": {
    "id": "EVT1", "subject": "Budget review", "isAllDay": False, "start": {"dateTime": "2030-11-06T17:00:00.0000000", "timeZone": "UTC"},
    "end": {"dateTime": "2030-11-06T17:30:00.0000000", "timeZone": "UTC"}, "location": {"displayName": "Teams"},
    "organizer": {"emailAddress": {"name": "Pat Example", "address": "pat@example.test"}}, "responseStatus": {"response": "tentativelyAccepted"}}}
o = invites.from_event(msg)
check("outlook: what, where, organizer", o and o["what"] == "Budget review" and o["where"] == "Teams" and o["organizer"] == "Pat Example")
check("outlook: local time and current answer", o and o["start"] == dt.datetime(2030, 11, 6, 17, 0, tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None) and o["response"] == "tentative")
check("outlook: a reply message is not an invite", invites.from_event(dict(msg, meetingMessageType="meetingAccepted")) is None)
check("when text", "Tuesday November 5" in invites._when_text(dict(g, start=dt.datetime(2030, 11, 5, 10), end=dt.datetime(2030, 11, 5, 11))))

# the respond press, with the service and the stored email stood in
sent = []
class Svc:
    @staticmethod
    def invite_source(conn, pid): return g
    @staticmethod
    def invite_answer(conn, inv, answer, note): sent.append((answer, note))
invites._message = lambda mid: {"account": "me@example.test", "_pid": "p1"}
invites._service = lambda r: ({"id": "c"}, Svc)
invites.common.log_line = lambda *a, **k: None
out = invites.respond({"id": "mail:1:1"}, {"message": 1, "answer": "tentative", "note": "Might be late"})
check("respond: sent once with the note", sent == [("tentative", "Might be late")] and out["result"].startswith("Said maybe to"))
check("respond: bad answer changes nothing", invites.respond({}, {"message": 1, "answer": "x"}).get("ok") is False and len(sent) == 1)
print("FAILED: " + ", ".join(fails) if fails else "all passed")
sys.exit(1 if fails else 0)
