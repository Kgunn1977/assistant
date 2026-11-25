"""Contract validator: refuses a whole commit on any violation.

Coverage, id-reality, evidence and shape are checked here; a failure means
nothing is written and no watermark advances.

    v = Validator(run_id)
    v.check_coverage(payload_ids, judged_ids)
    v.check_ids_real('messages', cited_message_ids)
    v.check_close_evidence(closes)
    v.raise_if_failed()          # ContractViolation aborts the commit
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
import db  # noqa: E402


class ContractViolation(Exception):
    """Raised to abort a commit. Nothing is written; nothing advances."""


class Validator:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.failures: list[str] = []

    # --- checks --------------------------------------------------------
    def check_coverage(self, payload_ids, judged_ids):
        """Every message in the payload must carry a judgment."""
        missing = set(payload_ids) - set(judged_ids)
        if missing:
            sample = sorted(list(missing))[:10]
            self.failures.append(
                f"coverage: {len(missing)} of {len(payload_ids)} unjudged, e.g. {sample}"
            )

    def check_ids_real(self, table: str, ids, id_column: str = "id"):
        """Every cited id must exist in its source table (fabricated-evidence guard)."""
        ids = [i for i in ids if i is not None]
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        rows = db.query(
            f"SELECT {id_column} FROM {table} WHERE {id_column} IN ({placeholders})",
            tuple(ids),
        )
        real = {r[0] for r in rows}
        fake = [i for i in ids if i not in real]
        if fake:
            self.failures.append(f"id-reality: {table} ids do not exist: {fake[:10]}")

    def check_close_evidence(self, closes):
        """closes: iterable of (item_key, evidence_ref). A close with no
        deterministic evidence is refused (prove before close)."""
        for item_key, evidence in closes:
            if not evidence:
                self.failures.append(f"close-evidence: {item_key} closed with no evidence")

    def check_no_empty(self, label: str, rows, fields):
        """Required fields must be non-empty (renderer/loader silent-drop guard)."""
        for i, row in enumerate(rows):
            for f in fields:
                if row.get(f) in (None, "", []):
                    self.failures.append(f"{label}: row {i} missing {f}")
                    break

    # --- verdict -------------------------------------------------------
    @property
    def ok(self) -> bool:
        return not self.failures

    def raise_if_failed(self):
        if self.failures:
            raise ContractViolation(
                f"run {self.run_id}: commit refused, {len(self.failures)} violation(s):\n  "
                + "\n  ".join(self.failures)
            )


if __name__ == "__main__":
    # self-test: prove the validator actually refuses bad commits
    v = Validator("selftest")
    v.check_coverage([1, 2, 3], [1, 2])
    v.check_ids_real("messages", [999999])
    v.check_close_evidence([("system::thing", None)])
    assert not v.ok, "validator failed to catch violations"
    try:
        v.raise_if_failed()
        print("FAIL: did not raise")
    except ContractViolation as e:
        print("validator self-test OK, caught:")
        print(e)
    clean = Validator("selftest")
    clean.check_coverage([1, 2], [1, 2])
    clean.raise_if_failed()
    print("clean commit passes: OK")
