"""Turn staged files into text in the database.

    python extract_text.py                 # process everything staged
    python extract_text.py --limit 200
    python extract_text.py --dry-run

The extracted text is what survives: staged files expire.
Text already present is read (PDF text layer, spreadsheet cells, HTML). A
photo or a scanned page with no text layer is marked 'needs_vision' for the
session to describe. Every file gets a document row and at least
one page row, so "looked and found nothing" differs from "never looked".
"""

import argparse
import datetime as dt
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
import db  # noqa: E402

TEXT_EXT = {".txt", ".csv", ".log", ".md"}
HTML_EXT = {".htm", ".html"}
SHEET_EXT = {".xlsx", ".xlsm"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
# formats nothing here can read; recorded honestly rather than pretended
OPAQUE_EXT = {".dwg", ".fab", ".zip", ".msg", ".doc", ".docx", ".rar", ".7z",
              ".cad", ".mp4", ".mov", ".exe", ".dll"}

MIN_MEANINGFUL_CHARS = 20

# A first page longer than 17 inches, or carrying plan words, is a drawing set:
# only its first sheet (title block and sheet index) is read.
LARGE_FORMAT_INCHES = 17
POINTS_PER_INCH = 72

# Plan words in the first page settle a set with a letter-size cover.
PLAN_WORDS = ("scale:", "sheet no", "sheet number", "drawn by", "title block",
              "north arrow", "detail no", "as-built", "revision block",
              "floor plan")


def plan_words():
    """The general drawing words plus the owner's own (personal "plan_words"): the words of their
    trade that mark a drawing set. None in the starter set."""
    try:
        import paths
        mine = [" ".join(str(w).lower().split()) for w in paths.personal().get("plan_words") or []]
    except Exception:  # noqa: BLE001  a list that cannot be read never stops a paper being read
        mine = []
    return PLAN_WORDS + tuple(w for w in mine if len(w) >= 3)

# Long documents: read the front and the back, and say so.
MAX_PAGES_FULL = 25
TAIL_PAGES = 3


def strip_html(raw: str) -> str:
    import re
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = (raw.replace("&nbsp;", " ").replace("&amp;", "&")
              .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'"))
    return re.sub(r"\s+", " ", raw).strip()


def extract_pdf(path):
    """Returns (pages, method). A page with no text layer yields ''.

    Text is read per page, so a PDF mixing typed and scanned pages queues only
    the scanned ones for vision."""
    import fitz
    # damaged files are data, not crashes: keep MuPDF's complaints off stderr
    fitz.TOOLS.mupdf_display_errors(False)
    out = []
    with fitz.open(path) as doc:
        n = len(doc)
        if n:
            first = doc[0]
            longest_in = max(first.rect.width, first.rect.height) / POINTS_PER_INCH
            head = first.get_text("text").strip()
            looks_like_plan = (longest_in > LARGE_FORMAT_INCHES
                               or any(w in head.lower() for w in plan_words()))
            if looks_like_plan:
                # keep the title block and the sheet index; skip the drawings
                dims = (f"{first.rect.width/POINTS_PER_INCH:.0f}x"
                        f"{first.rect.height/POINTS_PER_INCH:.0f} in")
                if n == 1:
                    note = f"[drawing, single sheet at {dims}.]"
                else:
                    note = (f"[drawing set: {n} sheets at {dims}. Only the first "
                            f"sheet is read; the other {n-1} are drawings.]")
                return [f"{note}\n{head}"], "drawing_first_sheet_only"

        want = (range(n) if n <= MAX_PAGES_FULL
                else list(range(MAX_PAGES_FULL - TAIL_PAGES)) + list(range(n - TAIL_PAGES, n)))
        for i in want:
            try:
                out.append(doc[i].get_text("text").strip())
            except Exception as e:  # noqa: BLE001
                out.append(f"[page unreadable: {type(e).__name__}]")
        if n > MAX_PAGES_FULL:
            out.insert(
                MAX_PAGES_FULL - TAIL_PAGES,
                f"[{n - MAX_PAGES_FULL} pages skipped: long document, first "
                f"{MAX_PAGES_FULL - TAIL_PAGES} and last {TAIL_PAGES} pages read]")
    if not out:
        # a zero-page or unopenable PDF still gets one row saying so, because
        # "looked and found nothing" must be distinguishable from "never looked"
        return [""], "needs_vision"
    # the document-level label is only a summary; page_methods() is the truth
    has_text = any(len(p) >= MIN_MEANINGFUL_CHARS for p in out)
    return out, ("native_text" if has_text else "needs_vision")


def page_methods(pages, doc_method, can_see=True):
    """Per-page method. Only a page that actually yielded text counts as read; only a picture or a PDF page (can_see) is ever
    sent to be read by eye: a spreadsheet's nearly empty sheet is read as it is, never queued for vision."""
    if doc_method in ("unreadable_format", "listing_only", "failed",
                      "drawing_first_sheet_only"):
        # a drawing is deliberately not read further; it must never be queued
        # for vision, which would be the expensive mistake twice over
        return [doc_method] * len(pages)
    return ["native_text" if len(p or "") >= MIN_MEANINGFUL_CHARS or not can_see else "needs_vision"
            for p in pages]


MAX_SHEET_ROWS = 500


def extract_sheet(path):
    """Read enough of a spreadsheet to know what it is; cap the rest."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    pages = []
    for ws in wb.worksheets:
        lines, taken, total = [], 0, 0
        for row in ws.iter_rows(values_only=True):
            total += 1
            if taken >= MAX_SHEET_ROWS:
                continue
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append("\t".join(cells))
                taken += 1
        head = f"[sheet: {ws.title}"
        if total > taken:
            head += f", {total} rows, first {taken} read"
        pages.append(head + "]\n" + "\n".join(lines))
    wb.close()
    return pages or [""], "native_text"


def extract(path, ext):
    """-> (list_of_page_texts, method). Never raises: failure is data."""
    try:
        if ext == ".pdf":
            return extract_pdf(path)
        if ext in TEXT_EXT:
            with open(path, encoding="utf-8", errors="replace") as f:
                return [f.read()], "native_text"
        if ext in HTML_EXT:
            with open(path, encoding="utf-8", errors="replace") as f:
                return [strip_html(f.read())], "native_text"
        if ext in SHEET_EXT:
            return extract_sheet(path)
        if ext in IMAGE_EXT:
            return [""], "needs_vision"
        if ext in OPAQUE_EXT:
            if ext == ".zip":
                with zipfile.ZipFile(path) as z:
                    listing = "\n".join(i.filename for i in z.infolist()[:200])
                return [f"[zip archive containing]\n{listing}"], "listing_only"
            return [""], "unreadable_format"
        return [""], "unreadable_format"
    except Exception as e:  # noqa: BLE001
        return [f"[extraction failed: {type(e).__name__}: {e}]"], "failed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--batch", type=int, default=200,
                    help="rows written per connection; keeps the DB lock brief")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run-id")
    args = ap.parse_args()

    rows = db.query("""
        SELECT a.id, a.message_id, a.saved_filename, a.saved_path,
               coalesce(a.original_filename, a.saved_filename), m.ts
        FROM attachments a LEFT JOIN messages m ON m.id = a.message_id
        WHERE a.state = 'staged'
        ORDER BY coalesce(m.ts, a.saved_at) DESC
        LIMIT ?""", (args.limit,))

    stats = {"native_text": 0, "needs_vision": 0, "unreadable_format": 0,
             "listing_only": 0, "failed": 0, "missing_file": 0}
    chars = 0
    batch = []

    def flush(pending):
        """Write one batch and close the connection, so the lock is held only
        while a batch is written."""
        if not pending or args.dry_run:
            return
        con = db.connect()
        try:
            for att_id, msg_id, ts, pages, method, can_see in pending:
                doc_id = con.execute(
                    "INSERT INTO documents (message_id, attachment_id, doc_type,"
                    " doc_date, created_at)"
                    " VALUES (?,?,?,?,?) RETURNING id",
                    (msg_id, att_id, "attachment",
                     ts.date() if ts else None, dt.datetime.now())).fetchone()[0]
                per_page = page_methods(pages, method, can_see)
                con.executemany(
                    "INSERT INTO pages (document_id, page_no, method, text,"
                    " extracted_at) VALUES (?,?,?,?,?)",
                    [(doc_id, i, pm, text, dt.datetime.now())
                     for i, (text, pm) in enumerate(zip(pages, per_page), start=1)])
                # 'processed' means the text is captured and the seven-day clock
                # starts; 'staged' still means nobody has looked at it
                con.execute("UPDATE attachments SET state='processed' WHERE id=?",
                            (att_id,))
        finally:
            con.close()

    for done, (att_id, msg_id, saved, path, original, ts) in enumerate(rows, start=1):
        if not path or not os.path.exists(path):
            stats["missing_file"] += 1
            continue
        ext = os.path.splitext(original or saved or "")[1].lower()
        pages, method = extract(path, ext)
        if not pages:                # belt and braces: never an empty insert
            pages = [""]
        stats[method] = stats.get(method, 0) + 1
        chars += sum(len(p) for p in pages)
        batch.append((att_id, msg_id, ts, pages, method, ext in IMAGE_EXT or ext == ".pdf"))

        if len(batch) >= args.batch:
            flush(batch)
            batch = []
            # progress on a long job, so a silent log cannot be mistaken for a hang
            print(f"   ...{done}/{len(rows)} files, {chars:,} chars", flush=True)

    flush(batch)

    if not args.dry_run:
        db.record_source_status(
            args.run_id, "extract", "ok",
            f"{len(rows)} files, {stats['needs_vision']} need vision")

    print(f"extract: {len(rows)} staged files"
          + ("  (dry run)" if args.dry_run else ""))
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        if v:
            print(f"   {k}: {v}")
    print(f"   {chars:,} characters of text captured")
    if stats["needs_vision"]:
        print(f"   {stats['needs_vision']} files hold no text layer and await"
              " a vision description by the session")
    return 0


if __name__ == "__main__":
    sys.exit(main())
