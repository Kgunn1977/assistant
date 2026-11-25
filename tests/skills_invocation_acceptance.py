r"""Acceptance (quick): the setup and off skills that the page's project tools and the update's hand-out ask a session to run
can be started by the session (no disable-model-invocation), and each says it runs only on the person's own ask or yes in
that session, never on another session's say-so alone.

    python tests\skills_invocation_acceptance.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SKILLS = ("roadmap-setup", "questions-setup", "questions-off", "roadmap-off", "roadmap-update")
results = []


def main():
    for s in SKILLS:
        text = open(os.path.join(PKG, "skills", s, "SKILL.md"), encoding="utf-8").read()
        head = text.split("\n---", 1)[0]
        results.append((f"{s}: a session can start it", "disable-model-invocation" not in head))
        results.append((f"{s}: runs only on the person's ask or yes in this session",
                        bool(re.search(r"Only when the person asked for it in this session, or said yes here", text))
                        and "never on another session's say-so alone" in text))
    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    print(f"{sum(ok for _n, ok in results)} of {len(results)} passed")
    return 0 if all(ok for _n, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
