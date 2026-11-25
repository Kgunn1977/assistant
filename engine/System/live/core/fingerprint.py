"""Content fingerprints, the second dedup key for email.

Migrated history carries older mailbox ids that no cloud API returns, so
provider_id alone cannot match it. The fingerprint hashes account, sender,
subject and body, and excludes the timestamp, so the same message fetched two
ways matches while the same message in two mailboxes stays two rows.
"""

import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
import db  # noqa: E402

# Keep only [a-z0-9]: Python's and DuckDB's whitespace classes differ on
# Unicode, and an explicit ASCII class cannot.
_KEEP = re.compile(r"[^a-z0-9]")
_RE_PREFIX = re.compile(r"^((re|fw|fwd)[ \t]*:[ \t]*)+", re.I)


def normalize_subject(subject: str) -> str:
    return _KEEP.sub("", _RE_PREFIX.sub("", (subject or "").lower()))


def normalize_body(body: str) -> str:
    return _KEEP.sub("", (body or "").lower())[:4000]


def fingerprint(account: str, from_addr: str, subject: str, body: str) -> str:
    payload = "|".join([
        (account or "").lower(),
        (from_addr or "").lower().strip(),
        normalize_subject(subject),
        normalize_body(body),
    ])
    return hashlib.md5(payload.encode("utf-8", "replace")).hexdigest()


# The SQL twin of fingerprint(); test_agreement() proves they match.
SQL_FINGERPRINT = r"""
md5(
  lower(coalesce(account,'')) || '|' ||
  lower(trim(coalesce(replace(from_key, 'email:', ''), ''))) || '|' ||
  regexp_replace(
      regexp_replace(lower(coalesce(subject,'')), '^((re|fw|fwd)[ \t]*:[ \t]*)+', '', 'g'),
      '[^a-z0-9]', '', 'g') || '|' ||
  substr(regexp_replace(lower(coalesce(body,'')), '[^a-z0-9]', '', 'g'), 1, 4000)
)
"""


def test_agreement(sample: int = 300):
    """Prove the Python and SQL fingerprints produce identical values."""
    rows = db.query(
        f"SELECT account, replace(coalesce(from_key,''),'email:',''), subject, body,"
        f" {SQL_FINGERPRINT} FROM messages WHERE channel='email'"
        f" USING SAMPLE {sample} ROWS"
    )
    bad = [r for r in rows if fingerprint(r[0], r[1], r[2], r[3]) != r[4]]
    return len(rows), bad


if __name__ == "__main__":
    checked, bad = test_agreement()
    print(f"python/SQL fingerprint agreement: {checked - len(bad)}/{checked} match")
    for acct, frm, subj, _body, sqlfp in bad[:3]:
        print(f"   MISMATCH {acct} {frm} {str(subj)[:40]!r}")
        print(f"     sql={sqlfp}  py={fingerprint(acct, frm, subj, _body)}")
    if bad:
        sys.exit(1)
