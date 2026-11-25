r"""Acceptance (quick): only a picture or a PDF page is ever sent to be read by eye. A spreadsheet whose second sheet is nearly
empty is read as it is (it was queued for vision, which can never read it, so it failed every pass), and the reading step
passes over any other file queued by mistake. Made-up files in a scratch folder.

    python tests\page_vision_acceptance.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="pagevision-")
    os.environ["ASSISTANT_LIVE_HOME"] = tmp
    try:
        import openpyxl
        import extract_text
        import think
        book = os.path.join(tmp, "parts list.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Parts"
        for i in range(12):
            ws.append([f"Part {i}", "pendent K5.6", i * 3])
        wb.create_sheet("Notes")
        wb.save(book)
        pages, method = extract_text.extract(book, ".xlsx")
        check("a spreadsheet with a nearly empty second sheet: every page read as it is, none sent to be read by eye",
              extract_text.page_methods(pages, method, can_see=False), ["native_text", "native_text"])
        check("a scanned PDF page with no text layer is still sent to be read by eye",
              extract_text.page_methods([""], "needs_vision", can_see=True), ["needs_vision"])
        check("the reading step reads pictures and PDFs only",
              ([p.endswith(think.SEEABLE) for p in ("a.xlsx", "b.PDF".lower(), "c.png", "d.docx")]), [False, True, True, False])
        # a page the reader answers nothing for: tried three passes, then passed over and said, not failed every pass
        import types
        import db
        import gather
        db.init_schema()
        pdf = os.path.join(tmp, "blank.pdf")
        open(pdf, "wb").write(b"%PDF-1.4 made up")
        os.makedirs(os.path.dirname(gather.GATHER_STATE), exist_ok=True)
        gather.pending_pages = lambda: [p for p in [(901, 1, 1, pdf, None)] if 901 not in (gather.state().get("pages_skipped") or [])]
        think.ai_steps.agent = lambda *a, **k: types.SimpleNamespace(ok=True)
        said = [think.read_pages() for _ in range(4)]
        check("a page left unread is tried three passes, then passed over and said once",
              [x[0] for x in said], [False, False, True, True])
        check("its line says why", "passed over after 3 tries" in said[2][1], True)
        # a scanned PDF (a page that is only a picture): the reader is handed that page drawn as a picture, never the PDF,
        # since Claude's Read tool opens one page of a PDF only through pdftoppm, which the computer may not have
        import fitz
        import json
        scan = os.path.join(tmp, "scan.pdf")
        pic = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 260), 0)
        pic.clear_with(200)
        doc = fitz.open()
        for _ in range(2):
            doc.new_page(width=612, height=792).insert_image(fitz.Rect(36, 36, 576, 756), pixmap=pic)
        doc.save(scan)
        doc.close()
        con = db.connect()
        con.execute("INSERT INTO documents (id, doc_type, created_at) VALUES (2, 'attachment', now())")
        for pid, no in ((911, 1), (912, 2)):
            con.execute("INSERT INTO pages (id, document_id, page_no, method, text) VALUES (?, 2, ?, 'needs_vision', '')", (pid, no))
        con.close()
        gather.pending_pages = lambda: [(911, 2, 1, scan, None), (912, 2, 2, scan, None)]
        handed = []

        def reader(prompt, model, out, timeout):
            got = json.loads(prompt[prompt.index("["):prompt.index("]", prompt.index("[")) + 1])
            handed.extend([(e["file"].lower().endswith(".png"), e["page_no"], os.path.exists(e["file"]), e["file"]) for e in got])
            json.dump({"pages": [{"page_id": e["page_id"], "text": "A stock sales order, made up, page " + str(e["page_id"])} for e in got]},
                      open(out, "w", encoding="utf-8"))
            return types.SimpleNamespace(ok=True)
        think.ai_steps.agent = reader
        ok, line = think.read_pages()
        check("a scanned PDF's pages reach the reader as pictures of each page, drawn before it runs",
              [h[:3] for h in handed], [(True, 1, True), (True, 1, True)])
        check("... both pages are read and stored", (ok, line, sorted(r[0] for r in db.query("SELECT method FROM pages WHERE id IN (911, 912)"))),
              (True, "2 page(s) read", ["vision", "vision"]))
        check("... and the pictures are removed once read", [os.path.exists(h[3]) for h in handed], [False, False])
        # pages passed over while the reader could not open a PDF page come back once; nothing else does
        con = db.connect()
        for aid, doc, pid, path in ((31, 3, 921, scan), (32, 4, 931, os.path.join(tmp, "gone.pdf")), (33, 5, 941, os.path.join(tmp, "logo.png"))):
            con.execute("INSERT INTO attachments (id, saved_filename, saved_path) VALUES (?, ?, ?)", (aid, os.path.basename(path), path))
            con.execute("INSERT INTO documents (id, attachment_id, doc_type, created_at) VALUES (?, ?, 'attachment', now())", (doc, aid))
            con.execute("INSERT INTO pages (id, document_id, page_no, method, text) VALUES (?, ?, 1, 'needs_vision', '')", (pid, doc))
        con.close()
        open(os.path.join(tmp, "logo.png"), "wb").write(b"png")
        st = gather.state()
        st["pages_skipped"], st["pages_tries"] = [921, 931, 941], {"912": 2, "921": 2}
        st.pop("pdf_pages_back_at", None)
        import common
        common.write_json(gather.GATHER_STATE, st)
        first, again = think.pdf_pages_back(), think.pdf_pages_back()
        st = gather.state()
        check("a PDF page given up while PDF pages could not be opened is back in line, its tries cleared; a missing file and a picture stay passed over",
              (first, again, sorted(st["pages_skipped"]), st["pages_tries"]), (1, 0, [931, 941], {"912": 2}))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
