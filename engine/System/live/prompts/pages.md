Read pages that arrived as pictures or image-only files for {OWNER}'s assistant and write down what each one says.

The list below is JSON. Each entry is one page with no readable text: `page_id`, the `file` it is in, the `page_no` inside that file (1 is the first page), and who sent it with what subject.

{PAGES_JSON}

For each entry, open the file with the Read tool (for a PDF, read only that page) and write what the page says for someone who cannot see it and has to act on it:

- Copy every piece of text that matters exactly: codes and numbers of any kind, quantities, sizes, names, dates, amounts, reference numbers, handwritten notes. For a list or table, one line per row.
- Say what kind of page it is in the first line (a hand-written list, a form, a receipt, a letter, a photo of an object, and so on).
- What you cannot read, say is unreadable. Never guess a number or a word.
- {OWNER} may read this on a card: around the copied text, use short whole sentences in plain words, never your own file names or ids.
- A logo, signature banner or decoration with no content: write exactly `no content: ` followed by what it is.
- If a file will not open, leave that page out.

Write one JSON file, exactly this shape, and nothing else:

{"pages": [{"page_id": 123, "text": "what the page says"}]}
