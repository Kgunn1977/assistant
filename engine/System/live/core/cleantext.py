"""Reduce a stored message body to the words a human actually wrote.

clean_body strips the HTML furniture (style blocks, Word markup, tracking
URLs) and keeps the sentences. new_text goes further for the judge: only the
words this message adds, without the HTML copy of its plain part, the quoted
reply history or a delimited signature.
"""

import html
import re

STYLE_BLOCK = re.compile(
    r"<(style|script|head|xml)\b.*?</\1>", re.I | re.S)
CONDITIONAL = re.compile(r"<!--\[if.*?<!\[endif\]-->", re.I | re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>", re.I)
BLOCK_END = re.compile(r"</(p|div|tr|table|h\d|li|blockquote)\s*>", re.I)
BREAK = re.compile(r"<br\s*/?>", re.I)
TAG = re.compile(r"<[^>]{0,4000}>", re.S)
# CSS that survives outside a <style> block, e.g. pasted inline rules
CSS_RULE = re.compile(r"[.@#]?[\w\\:.-]+\s*\{[^{}]{0,2000}\}", re.S)
MSO_LINE = re.compile(r"^\s*(mso-|panose-|@font-face|font-family:|@page|@list)"
                      r".*$", re.I | re.M)
LONG_URL = re.compile(r"<?https?://\S{60,}>?")
URL = re.compile(r"<?(https?://\S+)>?")
ZERO_WIDTH = re.compile(r"[​-‏⁠﻿ ᠎]")
MANY_BLANKS = re.compile(r"\n{3,}")
TRAILING_SPACE = re.compile(r"[ \t]+$", re.M)
SPACES = re.compile(r"[ \t]{2,}")
ANCHOR = re.compile(r"""<a\b[^>]*?\bhref\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a\s*>""", re.I | re.S)


def _anchor(m):
    """A link's words followed by its address, so a link given only as words
    (a shared folder, a portal) keeps where it points."""
    href, inner = html.unescape(m.group(1)).strip(), m.group(2)
    words = html.unescape(TAG.sub(" ", inner))
    bare = re.sub(r"^https?://", "", href, flags=re.I).rstrip("/").lower()
    if (not href.lower().startswith(("http://", "https://")) or len(href) >= 120
            or bare in words.lower()):
        return inner
    return f"{inner} {href.replace('://', HIDDEN, 1)} "


HIDDEN = "\x02"  # stands in for :// so the bare-URL passes leave a link's address alone
HIDDEN_URL = re.compile(r"(https?)\x02(\S+)")


def clean_body(body: str, limit: int = 1500, keep_links: int = 3) -> str:
    """Plain readable text, or '' for a body that was only markup."""
    if not body:
        return ""
    # some senders emit \r\r\n; normalise before the blank-line collapse
    t = body.replace("\r\n", "\n").replace("\r", "\n")
    t = DOCTYPE.sub(" ", t)
    t = CONDITIONAL.sub(" ", t)
    t = STYLE_BLOCK.sub(" ", t)
    t = COMMENT.sub(" ", t)
    t = ANCHOR.sub(_anchor, t)
    t = BREAK.sub("\n", t)
    t = BLOCK_END.sub("\n", t)
    t = TAG.sub(" ", t)
    t = html.unescape(t)
    t = CSS_RULE.sub(" ", t)
    t = MSO_LINE.sub("", t)

    # keep the first few links (a receipt or portal link can matter), drop the
    # rest: marketing mail is mostly tracking URLs and they carry no meaning
    links = []

    def _link(m):
        u = m.group(1)
        if len(links) < keep_links and len(u) < 120:
            links.append(u)
            return u
        return "[link]"

    t = LONG_URL.sub("[link]", t)
    t = URL.sub(_link, t)

    # a link given as words keeps its address, up to the same few; the rest
    # keep only their words
    shown = []

    def _shown(m):
        if len(shown) < keep_links:
            shown.append(m.group(2))
            return f"{m.group(1)}://{m.group(2)}"
        return ""

    t = HIDDEN_URL.sub(_shown, t)

    t = ZERO_WIDTH.sub(" ", t)
    t = TRAILING_SPACE.sub("", t)
    t = SPACES.sub(" ", t)
    # layout tables leave hundreds of lines holding a single stray character;
    # a line with no letter or digit carries nothing a reader would miss
    t = "\n".join(ln for ln in t.split("\n")
                  if not ln.strip() or re.search(r"[A-Za-z0-9]", ln))
    t = MANY_BLANKS.sub("\n\n", t)
    t = t.strip()

    return _clip(t, limit)


def _clip(t, limit):
    if len(t) > limit:
        cut = t.rfind("\n", 0, limit)
        t = t[:cut if cut > limit * 0.6 else limit].rstrip() + "\n[...]"
    return t


# Where an older message carried below begins.
FORWARD_START = re.compile(
    r"^\s*(-{5,}\s*Forwarded message\s*-{5,}|Begin forwarded message:)", re.I)
THREAD_START = [
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}", re.I),
    re.compile(r"^\s*On .{5,200} wrote:\s*$", re.I),
    re.compile(r"^\s*_{10,}\s*$"),
    FORWARD_START,
]
FROM_LINE = re.compile(r"^\s*From:\s*\S", re.I)
HEADER_NEAR = re.compile(r"^\s*(Sent|Date|To|Subject):", re.I)
SIGNATURE_START = re.compile(
    r"^\s*(--|sent from my \w+|get outlook for \w+)\s*$", re.I)
WORD = re.compile(r"[A-Za-z0-9]")


def thread_starts(lines):
    """Indexes (never 0) of lines where an older message begins."""
    for i, ln in enumerate(lines):
        if i == 0:
            continue
        if any(p.match(ln) for p in THREAD_START) or (
                FROM_LINE.match(ln) and any(
                    HEADER_NEAR.match(x) for x in lines[i + 1:i + 4])):
            yield i


def _flat(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().lower()


def dedupe_parts(text: str) -> str:
    """Mail stored as the plain part followed by the HTML part reads twice
    after cleaning. When the opening words come back again past the first
    third of the text, the second copy (the HTML part, better formatted)
    is kept and the first dropped."""
    lines = text.split("\n")
    head = _flat(text)[:50]
    if len(head) < 30:
        return text
    total = len(text)
    pos = 0
    for i, ln in enumerate(lines):
        if i and pos > total / 3 and _flat("\n".join(lines[i:])).startswith(head):
            return "\n".join(lines[i:])
        pos += len(ln) + 1
    return text


FORWARD_SUBJECT = re.compile(r"^\s*(fw|fwd)\s*:", re.I)


def new_text(body: str, limit: int = 1500, keep_links: int = 3,
             subject: str = "") -> str:
    """What this message itself says, for the judge: cleaned, '>' quoted lines
    dropped, cut at the first older message or signature, and the HTML copy
    of the plain part dropped. A forward is the message's substance, so
    nothing at or below one is cut; a subject starting FW or Fwd marks the
    first older-message header as that forward."""
    if not body:
        return ""
    forward = bool(FORWARD_SUBJECT.match(subject or ""))
    t = clean_body(body, limit=10**9, keep_links=keep_links)
    lines = [ln for ln in t.split("\n") if not ln.lstrip().startswith(">")]
    starts = set(thread_starts(lines))
    for i, ln in enumerate(lines):
        if FORWARD_START.match(ln) or (forward and i in starts):
            break
        pair = ln.strip() + " " + (lines[i + 1].strip() if i + 1 < len(lines) else "")
        if i and (SIGNATURE_START.match(ln) or THREAD_START[1].match(pair)
                  or i in starts):
            if any(WORD.search(x) for x in lines[:i]):
                lines = lines[:i]
            break
    return _clip(dedupe_parts("\n".join(lines)).strip(), limit)


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
    import db

    rows = db.query("""
        SELECT id, subject, body FROM messages
        WHERE body IS NOT NULL AND length(body) > 2000
        ORDER BY id DESC LIMIT 12""")
    total_before = total_after = 0
    for mid, subj, body in rows:
        c = clean_body(body)
        total_before += len(body)
        total_after += len(c)
        print(f"\n=== {mid} {(subj or '')[:60]!r}")
        print(f"    {len(body)} chars -> {len(c)}")
        print("    " + (c[:300].replace("\n", "\n    ") or "(nothing but markup)"))
    print(f"\ntotal {total_before} -> {total_after} chars "
          f"({100 - 100*total_after/max(total_before,1):.0f}% removed)")
