"""Queue images for description, and save the descriptions that come back.

    python describe_images.py --list            # what is waiting, with paths
    python describe_images.py --commit d.json   # save the descriptions

Same three-part shape as judgment, for the same reason: looking at a photo and
saying what it shows is not something a script can do. The script prepares the
queue and commits the result; the session does the looking.

    text media fetch  ->  page(method='needs_vision', text='')
    session reads the file, writes a description
    describe_images.py --commit  ->  page(method='vision', text=<description>)

A description is written for someone who cannot see the picture and has to
act on it: what the thing is, any text in it, and the detail a decision turns
on. Most texted images are 600px on the long edge; what is unreadable is said
to be, never guessed.
"""

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
import db  # noqa: E402
import paths  # noqa: E402

MIN_DESCRIPTION = 15


def pending():
    import common
    skip, upto = common.describe_sql()
    # the sender's name as a scalar: joining contacts would repeat an image
    # once per contact key
    return db.query("""
        SELECT p.id, d.id, a.saved_path, m.id, m.ts, m.direction,
               coalesce((SELECT max(c.name) FROM contacts c
                          WHERE c.person_id = m.person_id AND c.name IS NOT NULL),
                        m.from_key, ?),
               m.subject, m.body
        FROM pages p
        JOIN documents d ON d.id = p.document_id
        JOIN attachments a ON a.id = d.attachment_id
        JOIN messages m ON m.id = d.message_id
        WHERE p.method = 'needs_vision' AND d.doc_type = 'image'
          AND m.channel = 'sms'""" + skip + """
        ORDER BY m.ts DESC""", (f"({paths.owner_name()})", *upto))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true",
                    help="emit the queue as JSON, split into agent batches")
    ap.add_argument("--batch-size", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="--json: only the newest this many pictures (0 = all)")
    ap.add_argument("--commit")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    rows = pending()
    if args.commit:
        with open(args.commit, encoding="utf-8") as f:
            payload = json.load(f)
        items = payload.get("descriptions", [])
        by_page = {r[0]: r for r in rows}

        problems = []
        seen = set()
        for it in items:
            pid = it.get("page_id")
            if pid not in by_page:
                problems.append(f"page {pid} is not waiting for a description")
            if pid in seen:
                problems.append(f"page {pid} described twice")
            seen.add(pid)
            text = (it.get("description") or "").strip()
            if len(text) < MIN_DESCRIPTION:
                problems.append(f"page {pid}: description too short to be real")
        missing = set(by_page) - seen
        if missing and not payload.get("partial"):
            problems.append(
                f"{len(missing)} queued image(s) left undescribed: "
                f"{sorted(missing)[:10]}. Set \"partial\": true to allow that.")
        if problems:
            print("COMMIT REFUSED\n")
            for p in problems:
                print(f"   {p}")
            return 1

        now = dt.datetime.now()
        con = db.connect()
        try:
            for it in items:
                con.execute(
                    "UPDATE pages SET text=?, method='vision', extracted_at=?"
                    " WHERE id=?",
                    (it["description"].strip(), now, it["page_id"]))
                # the file has served its purpose; the description is what
                # survives the retention sweep
                con.execute(
                    "UPDATE attachments SET state='processed' WHERE id ="
                    " (SELECT attachment_id FROM documents d"
                    "   JOIN pages p ON p.document_id = d.id WHERE p.id = ?)",
                    (it["page_id"],))
        finally:
            con.close()
        print(f"saved {len(items)} description(s)")
        left = len(pending())
        print(f"images still waiting: {left}")
        return 0

    if args.json:
        # batches for parallel description agents; each image is independent
        items = []
        for page_id, _doc, path, msg_id, ts, direction, who, thread, body in (rows[:args.limit] if args.limit else rows):
            nxt = db.query("""
                SELECT body FROM messages WHERE channel='sms'
                  AND thread_id=(SELECT thread_id FROM messages WHERE id=?)
                  AND ts > ? AND coalesce(body,'') <> '' ORDER BY ts LIMIT 1""",
                (msg_id, ts))
            items.append({
                "page_id": page_id, "message_id": msg_id, "file": path,
                "when": str(ts), "direction": direction, "from": who,
                "thread": thread,
                "text_sent_with_it": body if body and body not in
                ("[image]", "[media message, no text]") else None,
                "next_in_thread": nxt[0][0][:200] if nxt and nxt[0][0] else None,
                "exists": os.path.exists(path),
            })
        batches = [items[i:i + args.batch_size]
                   for i in range(0, len(items), args.batch_size)]
        print(json.dumps({"total": len(items), "batches": batches}, indent=1))
        return 0

    # --list, the default
    print(f"images waiting for a description: {len(rows)}\n")
    for page_id, _doc, path, msg_id, ts, direction, who, thread, body in rows:
        exists = os.path.exists(path)
        print(f"page {page_id}  message {msg_id}  {ts:%m/%d/%y %H:%M}  {direction}")
        print(f"   from: {who}")
        print(f"   thread: {thread!r}")
        if body and body not in ("[image]", "[media message, no text]"):
            print(f"   text with it: {body[:120]!r}")
        print(f"   file: {path}{'' if exists else '   MISSING FROM DISK'}")
        # the neighbouring message is often what the picture answers
        nxt = db.query("""
            SELECT body, direction FROM messages
            WHERE channel='sms' AND thread_id=(SELECT thread_id FROM messages WHERE id=?)
              AND ts > ? AND coalesce(body,'') <> '' ORDER BY ts LIMIT 1""",
            (msg_id, ts))
        if nxt and nxt[0][0]:
            print(f"   next in thread ({nxt[0][1]}): {nxt[0][0][:100]!r}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
