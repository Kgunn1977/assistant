r"""Acceptance: every module.name the engine uses on one of its own modules exists in that module (a call to a function
that was renamed or removed is caught here, not by the owner pressing a button). Reads the code only; runs nothing.

For each engine file, a name bound by an import of an engine module (import answers, from connections import _http,
import x as y) and then used as name.attr must find attr defined at the top level of that module: a def, a class, an
assignment, an import, or a name set by `global`. A module with its own __getattr__ is skipped. Names a file sets on a
module itself (mod.attr = ..., as a test stand-in or a cache) count as defined.

    python tests\engine_names_acceptance.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "engine", "System")
SKIP_DIRS = {"__pycache__", "site", "node_modules"}


def engine_files():
    for d, dirs, files in os.walk(ENGINE):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(d, f)


def module_index(files):
    """Module name -> file. A bare name may live in several folders (they are put on the path separately); all kept."""
    idx = {}
    for p in files:
        name = os.path.splitext(os.path.basename(p))[0]
        if name == "__init__":
            name = os.path.basename(os.path.dirname(p))
        idx.setdefault(name, []).append(p)
    return idx


def defined(path, _cache={}):
    """Top-level names of a module, or None when it answers any name (__getattr__)."""
    if path in _cache:
        return _cache[path]
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            names.update(node.names)
    for node in tree.body:
        for n in ([node] + (list(ast.walk(node)) if isinstance(node, (ast.If, ast.Try, ast.With)) else [])):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(n.name)
            elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name):
                            names.add(x.id)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    names.add((a.asname or a.name).split(".")[0])
    if os.path.basename(path) == "__init__.py":     # a package's own modules are its names too
        folder = os.path.dirname(path)
        names.update(os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith(".py"))
    _cache[path] = None if "__getattr__" in names else names
    return _cache[path]


def _locals(fn):
    """Names a function binds itself other than by import (its arguments, assignments, loop and with targets):
    inside it such a name is that value, not a module."""
    out = set()
    args = fn.args
    for a in args.args + args.kwonlyargs + getattr(args, "posonlyargs", []) + [x for x in (args.vararg, args.kwarg) if x]:
        out.add(a.arg)
    for n in ast.walk(fn):
        if n is not fn and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
    return out


def uses(tree):
    """(node, names shadowed where it stands) for every node, the shadowed names being those of the functions around it."""
    def walk(node, shadow):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            shadow = shadow | _locals(node)
        yield node, shadow
        for c in ast.iter_child_nodes(node):
            yield from walk(c, shadow)
    top = {n.id for st in tree.body if isinstance(st, (ast.Assign, ast.AnnAssign, ast.For, ast.With))
           for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    yield from walk(tree, frozenset(top))


def problems():
    files = list(engine_files())
    idx = module_index(files)
    set_on = {}                                     # module -> names files set on it (mod.x = ...)
    found = []
    trees = {p: ast.parse(open(p, encoding="utf-8").read(), p) for p in files}
    bound_by_file = {}
    for p, tree in trees.items():
        bound = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if "." not in a.name and a.name in idx:
                        bound[a.asname or a.name] = a.name
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if a.name in idx and (node.module in (None, "connections", "core") or node.level):
                        bound[a.asname or a.name] = a.name
        bound_by_file[p] = bound
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in bound:
                        set_on.setdefault(bound[t.value.id], set()).add(t.attr)
    for p, tree in trees.items():
        bound = bound_by_file[p]
        for node, shadow in uses(tree):
            if not (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in bound)                     or node.value.id in shadow:
                continue
            mod = bound[node.value.id]
            homes = [defined(h) for h in idx[mod]]
            if any(h is None or node.attr in h for h in homes) or node.attr in set_on.get(mod, ()):
                continue
            found.append(f"{os.path.relpath(p, ENGINE)}:{node.lineno} {node.value.id}.{node.attr} (no {node.attr} in {mod})")
    return sorted(set(found))


def main():
    got = problems()
    for g in got:
        print("FAIL " + g)
    print(("PASS every engine module.name reference resolves" if not got else f"{len(got)} unresolved"))
    return 0 if not got else 1


if __name__ == "__main__":
    sys.exit(main())
