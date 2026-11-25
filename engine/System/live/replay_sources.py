r"""The replay's readers: one day of each source, read straight from the source and stored by the shared writers.

Each reader takes one day's window, [start, end) as moments in time (the day's midnight to the next midnight in the owner's
zone, worked out by replay.py), and stores only what falls in it, through connections._store, so the usual rules decide what
is already held. They only read: the replay's guard (replay_guard) refuses any change at a service below them.

    mail_day(conn, start, end)      Gmail (after:/before: in seconds) or Microsoft Graph (receivedDateTime ge/lt), sent and
                                    received, with attachments
    calendar_day(conn, start, end)  events whose start falls on the day, as each event is today
    texts_day(day)                  the day's texts from the phone backups, as sorted out by spool_texts()
    spool_texts(folder, first_day, last_day, say)   read every phone backup once, streaming, and file each text under its day

An added connection type (a chat app, say) reads its own day with replay_day in its own module (CONNECTIONS.md); replay.py
calls it, and this file names none.

The phone backup reading is the phone_texts connection's own (an older connection type; its reader is kept here for the
replay): the same rows, the same ids, the same pictures. For the replay its routine limits are lifted (no size limit, no
3-day lookback), and the big full backup is streamed, never loaded whole.
"""
import base64
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import xml.etree.ElementTree as ET

import common
from connections import _store

FOLDER = os.path.join(common.paths.STATE, "replay")
TEXTS = os.path.join(FOLDER, "texts")                   # one file of rows per day, and what was read


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


# --- texts from the phone's backups -------------------------------------------------------------------------------------
FROM, TO = "137", "151"
RCS_BANNER = re.compile(r"^RCS chat with\b", re.I)
EXT = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/gif": ".gif",
       "image/bmp": ".bmp", "image/webp": ".webp", "image/heic": ".heic", "image/heif": ".heif",
       "application/pdf": ".pdf"}
DESCRIBABLE = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/bmp", "image/webp"}
CONVERT_TO_JPEG = {"image/heic", "image/heif"}


def backups(folder):
    """(the full backup, [the hourly ones]): the biggest sms-*.xml is the full one."""
    found = sorted(glob.glob(os.path.join(folder or "", "sms-*.xml")))
    if not found:
        return None, []
    full = max(found, key=os.path.getsize)
    return full, [p for p in found if p != full]


def _to_jpeg(data):
    import pillow_heif
    from PIL import Image
    pillow_heif.register_heif_opener()
    out = io.BytesIO()
    Image.open(io.BytesIO(data)).convert("RGB").save(out, "JPEG", quality=90)
    return out.getvalue()


def _clean(value):
    value = (value or "").strip()
    return "" if value in ("null", "(Unknown)") else value


def _ms(el):
    try:
        return int(el.get("date", "0"))
    except ValueError:
        return 0


def _row(thread, ms, direction, key, name, text, media):
    pid = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:12]
    return {"provider_id": f"bk:{thread}:{ms}:{direction}:{pid}", "thread": thread, "ms": ms, "direction": direction,
            "key": key, "name": name, "text": text, "media": media}


def _sms(el, ms):
    direction = {"1": "in", "2": "out"}.get(el.get("type"))
    text = _clean(el.get("body"))
    if not direction or not text or RCS_BANNER.match(text):
        return None
    address = _clean(el.get("address"))
    return _row(address, ms, direction, _store.phone_key(address) if address else None, _clean(el.get("contact_name")), text, [])


def _mms(el, ms):
    direction = {"1": "in", "2": "out"}.get(el.get("msg_box"))
    if not direction:
        return None
    text, media = [], []
    for part in el.iterfind("parts/part"):
        kind = (part.get("ct") or "").lower()
        if kind.startswith("text/plain"):
            piece = _clean(part.get("text"))
            if piece:
                text.append(piece)
        elif kind in EXT and part.get("data"):
            data = base64.b64decode(part.get("data"))
            if kind in CONVERT_TO_JPEG:
                try:
                    data, kind = _to_jpeg(data), "image/jpeg"
                except Exception:  # noqa: BLE001  kept as it came; it just cannot be described
                    pass
            media.append([EXT[kind], _clean(part.get("cl")), base64.b64encode(data).decode("ascii"), kind in DESCRIBABLE])
    text = " ".join(text).strip()
    if not (text or media) or RCS_BANNER.match(text):
        return None
    wanted = FROM if direction == "in" else TO
    people = [a.get("address") for a in el.iterfind("addrs/addr") if a.get("type") == wanted]
    person = _clean(people[0]) if people else ""
    group = ("~" in (el.get("address") or "")) or len(people) > 1
    return _row(_clean(el.get("address")), ms, direction, _store.phone_key(person) if person else None,
                "" if group else _clean(el.get("contact_name")), text or _store.NO_TEXT, media)


def read_backup(path, lo_ms, hi_ms):
    """Every text in [lo_ms, hi_ms) from one backup file, streamed: each element is let go once read, and the whole tree is
    cleared after each message, so a file of any size is read in little memory."""
    root = None
    for event, el in ET.iterparse(path, events=("start", "end")):
        if event == "start":
            if root is None:
                root = el
            continue
        if el.tag not in ("sms", "mms"):
            continue
        ms = _ms(el)
        row = None
        if lo_ms <= ms < hi_ms:
            row = _sms(el, ms) if el.tag == "sms" else _mms(el, ms)
        el.clear()
        root.clear()
        if row:
            yield row


def _day_of(ms, zone):
    return dt.datetime.fromtimestamp(ms / 1000, zone).date()


def spool_texts(folder, first_day, last_day, zone, say=print):
    """File every text from first_day to last_day (whole days in `zone`) under its day, reading each backup only once.
    Returns (backups read now, texts filed now)."""
    os.makedirs(os.path.join(TEXTS, "days"), exist_ok=True)
    done_path, seen_path = os.path.join(TEXTS, "read.json"), os.path.join(TEXTS, "seen.txt")
    done = common.read_json(done_path, {}) or {}
    try:
        with open(seen_path, encoding="utf-8") as f:
            seen = {ln.strip() for ln in f if ln.strip()}
    except OSError:
        seen = set()
    lo_ms = int(dt.datetime.combine(first_day, dt.time(), zone).timestamp() * 1000)
    hi_ms = int(dt.datetime.combine(last_day + dt.timedelta(days=1), dt.time(), zone).timestamp() * 1000)
    full, hourly = backups(folder)
    files, filed = 0, 0
    for path in ([full] if full else []) + hourly:
        name, size = os.path.basename(path), os.path.getsize(path)
        if (done.get(name) or {}).get("size") == size:
            continue
        if size > 200_000_000:
            say(f"  reading the full phone backup {name} ({size / 1e9:.1f} GB) once; this takes several minutes")
        n, held = 0, 0
        by_day = {}
        try:
            for row in read_backup(path, lo_ms, hi_ms):
                if row["provider_id"] in seen:
                    continue
                seen.add(row["provider_id"])
                by_day.setdefault(_day_of(row["ms"], zone), []).append(row)
                n += 1
                held += 200 + sum(len(m[2]) for m in row["media"])
                if held > 50_000_000:       # filed as it goes, by size: a big file never holds its pictures in memory
                    _flush(by_day, seen_path)
                    held = 0
        except (ET.ParseError, OSError) as e:       # still being written by the drive: read on a later run
            say(f"  {name} could not be read yet ({e})")
            _flush(by_day, seen_path)
            continue
        _flush(by_day, seen_path)
        done[name] = {"size": size, "texts": n}
        common.write_json(done_path, done)
        files, filed = files + 1, filed + n
    return files, filed


def _flush(by_day, seen_path):
    for day, rows in by_day.items():
        with open(os.path.join(TEXTS, "days", f"{day}.jsonl"), "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        with open(seen_path, "a", encoding="utf-8") as f:
            f.write("".join(r["provider_id"] + "\n" for r in rows))
    by_day.clear()


def texts_day(day):
    """Store the day's texts (and their pictures) the usual way. Returns how many were new."""
    rows = []
    try:
        with open(os.path.join(TEXTS, "days", f"{day}.jsonl"), encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                r["ts"] = dt.datetime.fromtimestamp(r.pop("ms") / 1000)        # stored as this computer's wall clock, as before
                r["media"] = [(m[0], m[1], base64.b64decode(m[2]), bool(m[3])) for m in r.get("media") or []]
                rows.append(r)
    except OSError:
        return 0
    if not rows:
        return 0
    written, _held, _queued = _store.text_messages(rows)
    return written
