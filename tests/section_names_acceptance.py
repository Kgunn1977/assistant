r"""Acceptance (quick): a section's name is never something a browser filled in by itself. Made-up owner, scratch folder.

- Saving a section name that is the owner's own name (whole or one part, any case), an email address, a phone number or a
  street address is refused with a plain reason; an ordinary name is saved.
- Every free-text box on the page that is not an address box says autocomplete="off", and the section-name box has a
  name that is not personal.

    python tests\section_names_acceptance.py
"""
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
PAGE = os.path.join(os.path.dirname(HERE), "engine", "System", "live_page", "page.html")
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="secnames-")
    os.environ["ASSISTANT_LIVE_HOME"] = tmp
    sys.path.insert(0, LIVE)
    sys.path.insert(0, os.path.join(LIVE, "core"))
    try:
        import common
        os.makedirs(os.path.dirname(common.PERSONAL_JSON), exist_ok=True)
        json.dump({"owner": "Robin Example"}, open(common.PERSONAL_JSON, "w", encoding="utf-8"))
        import settings_page

        def save(title):
            ok, said = settings_page.save({"settings": {"group": "page", "values": {"titles": {"feed": title}}}})
            return ok, said
        title = lambda: (settings_page._part("page").get("titles") or {}).get("feed", "")    # noqa: E731
        kept = {}
        for t in ("robin", "Robin Example", "EXAMPLE", "robin@home.example", "(555) 555-0142", "12 Elm Street"):
            ok, said = save(t)
            kept[t] = (ok, title(), "left as it was" in said and "browser filling in the box" in said)
        check("a newly typed name that is the owner's own, an email address, a phone number or a street address is not taken; "
              "the save still goes through and says why", kept, {t: (True, "", True) for t in kept})
        ok, said = save("Kept off the page")
        check("an ordinary section name is saved", (ok, title()), (True, "Kept off the page"))
        # a personal name already stored (from before this guard) never stops another setting from saving
        st = json.load(open(common.SETTINGS, encoding="utf-8"))
        st.setdefault("page", {})["titles"] = {"feed": "robin"}
        json.dump(st, open(common.SETTINGS, "w", encoding="utf-8"))
        ok, said = settings_page.save({"settings": {"group": "page", "values": {"titles": {"feed": "robin"}, "look": "workshop"}}})
        check("with a personal name already stored, saving the look goes through (the stored name is not a reason to refuse)",
              (ok, settings_page._part("page").get("look")), (True, "workshop"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    src = open(PAGE, encoding="utf-8").read()
    boxes = []
    for m in re.finditer(r'<(input type="(?:text|search)"|textarea)', src):
        boxes.append(src[m.start():src.find(">", m.end())])
    check("every free-text box on the page sets autocomplete", [b[:60] for b in boxes if "autocomplete" not in b], [])
    lay = [b for b in boxes if "lay-title" in b]
    check("the section-name box: autocomplete off and a name that is not personal",
          [('autocomplete="off"' in b, 'name="section-name"' in b) for b in lay], [(True, True)])
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
