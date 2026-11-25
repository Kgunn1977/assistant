r"""Keys for outside programs: typed by the owner into a box on their own computer, kept locked to their
Windows account, handed only to code that asks for one by name.

A key is never shown on the page, on a card, in a log or to an AI run. It is stored in the personal part
(keys.dat), locked by Windows to this user on this computer, so the file is useless anywhere else. Code
reads a key with `keys.get("name")`.

    pythonw keys.py --ask NAME --for "the outside program"     opens the box; exit 0 when a key was stored
    python  keys.py --names                                    the names that are stored, never the values
"""
import base64
import ctypes
import json
import os
import re
import sys
from ctypes import wintypes

import common

KEYS_FILE = os.path.join(common.PERSONAL, "keys.dat")
NAME = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


class _Blob(ctypes.Structure):
    _fields_ = [("n", wintypes.DWORD), ("p", ctypes.POINTER(ctypes.c_char))]


def _lock(data, lock):
    """Windows locks or unlocks bytes for this user on this computer."""
    buf = ctypes.create_string_buffer(data, len(data))
    src, out = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), _Blob()
    fn = ctypes.windll.crypt32.CryptProtectData if lock else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("Windows could not " + ("lock" if lock else "unlock") + " the key")
    try:
        return ctypes.string_at(out.p, out.n)
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free(ctypes.cast(out.p, ctypes.c_void_p))


def _load():
    try:
        with open(KEYS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def names():
    return sorted(_load())


def has(name):
    return name in _load()


def get(name):
    """The key stored under this name, or None when the owner has not entered it."""
    blob = _load().get(name)
    if not blob:
        return None
    try:
        return _lock(base64.b64decode(blob), False).decode("utf-8")
    except (OSError, ValueError):
        return None


def set_(name, value):
    if not NAME.match(name or "") or not value:
        raise ValueError("a key needs a plain name and a value")
    d = _load()
    d[name] = base64.b64encode(_lock(value.encode("utf-8"), True)).decode("ascii")
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    common.write_json(KEYS_FILE, d)


def forget(name):
    d = _load()
    if d.pop(name, None) is not None:
        common.write_json(KEYS_FILE, d)


def scrub(text):
    """The same text with every stored key's value taken out. Used on anything about to be logged or shown."""
    if not text:
        return text
    for n in names():
        v = get(n)
        if v and len(v) >= 4 and v in text:
            text = text.replace(v, "[key]")
    return text


def _box(name, program, what="", _type=None):
    """The box on the owner's computer. Returns what was typed, or None when it was closed."""
    import tkinter as tk
    root = tk.Tk()
    root.title("I need a key")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    got = {"v": None}
    tk.Label(root, justify="left", wraplength=420, padx=16, pady=12,
             text=f"I need a key to connect to {program}.\n\n"
                  + (what.strip() + "\n\n" if what.strip() else "")
                  + "Type or paste the key below. It stays on this computer, locked to your Windows account, "
                    "and is never shown on your page.").pack()
    entry = tk.Entry(root, show="•", width=52)
    entry.pack(padx=16)
    row = tk.Frame(root)
    row.pack(pady=12)

    def ok(_e=None):
        got["v"] = entry.get().strip() or None
        root.destroy()

    save = tk.Button(row, text="Save", width=10, command=ok)
    save.pack(side="left", padx=6)
    tk.Button(row, text="Not now", width=10, command=root.destroy).pack(side="left", padx=6)
    entry.bind("<Return>", ok)
    entry.focus_force()
    root.update_idletasks()
    root.geometry(f"+{(root.winfo_screenwidth() - root.winfo_width()) // 2}+{(root.winfo_screenheight() - root.winfo_height()) // 3}")
    if _type:
        root.after(400, lambda: _type(entry, save))
    root.mainloop()
    return got["v"]


def ask(name, program, what=""):
    """Open the box and store what the owner typed. True when a key was stored."""
    if not NAME.match(name or ""):
        return False
    v = _box(name, program, what)
    if not v:
        return False
    set_(name, v)
    return True


def main():
    a = sys.argv[1:]
    if "--names" in a:
        print(", ".join(names()) or "none")
        return 0
    if "--ask" in a:
        opt = lambda k: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else ""
        return 0 if ask(opt("--ask"), opt("--for") or "an outside program", opt("--what")) else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
