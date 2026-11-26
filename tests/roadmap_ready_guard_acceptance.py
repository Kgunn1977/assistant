r"""Acceptance (quick): the roadmap's guard on Ready rows. A row written "Ready, waiting for your look" or "Ready, known fault"
must carry, in the same write, only checks the person alone can do (each with needs_person saying why) and a shown_working
line "Checked by Claude, <date>: ..."; any other Ready write is refused, single or in a batch or given as a file. Other
writes pass. The roadmap page shows each check's reason. Made-up rows; no roadmap page is called.

    python tests\roadmap_ready_guard_acceptance.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PKG, "hooks"))
import roadmap_blocks as rb  # noqa: E402

results = []
PAGE = "https://claude.ai/artifact/MadeUpRoadmap"
CFG = {"page_url": PAGE}
CHECKED = "Checked by Claude, 11/20: the code path and the page on test cards."
GOOD = [{"id": "c1", "text": "On your phone, open the page and see the new line.", "needs_person": "only your phone shows how it looks there"}]


def check(name, got, want):
    results.append((name, got == want, got, want))


def write(data, action="update", **extra):
    ti = dict({"action": action, "url": PAGE, "collection": "steps", "doc_id": "step-03", "data": data}, **extra)
    return rb.refuse_ready({"hook_event_name": "PreToolUse", "tool_name": "ArtifactData", "tool_input": ti}, CFG)


def main():
    ready = "Ready, waiting for your look"
    r = write({"status": ready, "checks": [{"id": "c1", "text": "Open the page and see the line."}], "shown_working": CHECKED})
    check("a check without needs_person is refused, with the plain words", r is not None and "Run this check yourself first" in r, True)
    r = write({"status": "Ready, known fault", "checks": GOOD, "shown_working": "Built the new line."})
    check("a Ready write without the Checked by Claude line is refused", r is not None and "Checked by Claude" in r, True)
    r = write({"status": ready, "shown_working": CHECKED})
    check("a Ready write without its checks in the same write is refused", r is not None, True)
    check("a Ready write with both is let through", write({"status": ready, "checks": GOOD, "shown_working": CHECKED}), None)
    check("other writes pass (Done, confirmed with the line; an update with no status)",
          [write({"status": "Done, confirmed", "shown_working": CHECKED}), write({"name": "Tiles"})], [None, None])
    def done(line):
        ti = {"action": "update", "url": PAGE, "collection": "steps", "doc_id": "step-05", "data": {"status": "Done, confirmed", "shown_working": line}}
        return rb.refuse_self_confirm({"hook_event_name": "PreToolUse", "tool_name": "ArtifactData", "tool_input": ti}, CFG)
    check("Claude can't confirm its own work: Done, confirmed on its own check is refused; on the person's checks or word it passes",
          [done(CHECKED) is not None and "can't judge your own work" in done(CHECKED), done(CHECKED + "\nYour checks, 11/21"),
           done("You confirmed it, 11/21")], [True, None, None])
    r = rb.refuse_ready({"hook_event_name": "PreToolUse", "tool_name": "ArtifactData", "tool_input": {
        "action": "batch", "url": PAGE, "writes": [
            {"op": "update", "collection": "steps", "doc_id": "step-01", "data": {"status": "Done, confirmed", "shown_working": CHECKED}},
            {"op": "update", "collection": "steps", "doc_id": "step-02", "data": {"status": ready, "checks": [{"id": "c2", "text": "x"}],
                                                                               "shown_working": CHECKED}}]}}, CFG)
    check("a batch holding one bad Ready row is refused", r is not None, True)
    tmp = tempfile.mkdtemp(prefix="readyguard-")
    f = os.path.join(tmp, "row.json")
    json.dump({"status": ready, "checks": GOOD, "shown_working": "no line"}, open(f, "w", encoding="utf-8"))
    r = rb.refuse_ready({"hook_event_name": "PreToolUse", "tool_name": "ArtifactData", "tool_input": {
        "action": "update", "url": PAGE, "collection": "steps", "doc_id": "step-04", "file_path": f}}, CFG)
    check("a Ready row given as a file is read and checked too", r is not None, True)
    other = rb.refuse_ready({"hook_event_name": "PreToolUse", "tool_name": "ArtifactData", "tool_input": {
        "action": "update", "url": "https://claude.ai/artifact/SomeOtherPage", "collection": "steps", "data": {"status": ready}}}, CFG)
    check("another page's writes are not this guard's", other, None)
    page = open(os.path.join(PKG, "page", "roadmap.html"), encoding="utf-8").read()
    check("the roadmap page shows each check's reason under it", "Why only you can check this: " in page and "c.needs_person" in page, True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
