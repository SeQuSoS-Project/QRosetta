"""ReDoS check: every regular expression in the API, the shared package, the runners and the
compilers, timed on 1 MB adversarial inputs.

The inventory comes from the source (``re.compile``/``re.sub``/... calls with a literal
pattern, and the methods each compiled pattern is called with). Each pattern is run with
``findall`` (the cost of ``search``, ``finditer``, ``sub`` and ``split`` over a whole text)
and ``match`` on inputs built by repeating short strings to 1 MB: generic QASM pumps and the
literal pieces of the pattern itself, each also with a suffix that makes a match fail. A
run is killed after ``--kill-sec``.

Usage: python scripts/fuzz/redos.py [--size BYTES] [--limit-sec 1.0] [--json OUT]
"""

import argparse
import ast
import json
import multiprocessing as mp
import re
import sys
import time
from pathlib import Path

try:
    import re._parser as sre_parse
except ImportError:
    import sre_parse

REPO = Path(__file__).resolve().parents[2]
SCOPES = {
    "api": ["rosetta-api/services", "rosetta-api/routers", "rosetta-api/schemas",
            "rosetta-api/main.py", "rosetta-api/config.py", "rosetta-api/db"],
    "shared": ["shared/qrosetta_commons"],
    "runner": ["runners"],
    "compiler": ["compilers"],
}
RE_FUNCS = {"compile", "sub", "subn", "search", "match", "fullmatch", "findall", "finditer",
            "split"}
FLAG_NAMES = {"M": re.M, "MULTILINE": re.M, "S": re.S, "DOTALL": re.S, "I": re.I,
              "IGNORECASE": re.I, "X": re.X, "VERBOSE": re.X, "A": re.A, "ASCII": re.A}
GENERIC_PUMPS = [
    "\n", " ", "\t", "\r\n", " \n", "\n ", "a", "0", "1.", "1e", ".", "(", ")", "[", "]", "{",
    "}", ";", ",", "/", "*", "//", "/*", "-", "+", "_", "\"", "=", "==", "->", "~", "x ", "q",
    "a0", "a ", "a[", "a[0", "q[0]", "q[0],", "(a", "a(", "a)", "if(", "if (", "gate ",
    "gate a ", "gate a(", "qreg ", "creg ", "qreg a[", "measure ", "measure a ", "barrier ",
    "OPENQASM ", "pi", "pi*", "1e1", "sin(", "~opt", "~opt0~run", "u3(", "c4x ", "barrier;",
    "tdg ", "\\", "%", "\x00",
]
SUFFIXES = ["", "!", "\x00", "{", ";"]


def _const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(value.value)
            else:
                parts.append("NAME")
        return "".join(parts)
    return None


def _flags(node) -> int:
    if node is None:
        return 0
    if isinstance(node, ast.Attribute) and node.attr in FLAG_NAMES:
        return FLAG_NAMES[node.attr]
    if isinstance(node, ast.BinOp):
        return _flags(node.left) | _flags(node.right)
    return 0


def inventory() -> list:
    """Every regex call with a literal pattern: scope, file, line, function, pattern, flags,
    and for a compiled pattern assigned to a name the attributes used on that name in the file
    (``match``, ``sub``, ...)."""
    out = []
    for scope, roots in SCOPES.items():
        files = []
        for root in roots:
            path = REPO / root
            files += [path] if path.is_file() else sorted(path.rglob("*.py"))
        for path in files:
            if "/tests/" in str(path) or not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            assigned = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            assigned[id(node.value)] = target.id
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == "re"
                        and node.func.attr in RE_FUNCS and node.args):
                    continue
                pattern = _const_str(node.args[0])
                if pattern is None:
                    continue
                flags_node = next((k.value for k in node.keywords if k.arg == "flags"), None)
                if flags_node is None:
                    index = {"compile": 1, "search": 2, "match": 2, "fullmatch": 2,
                             "findall": 2, "finditer": 2, "split": 3, "sub": 4,
                             "subn": 4}[node.func.attr]
                    flags_node = node.args[index] if len(node.args) > index else None
                name = assigned.get(id(node))
                methods = [node.func.attr] if node.func.attr != "compile" else []
                if name:
                    methods = sorted(set(re.findall(rf"\b{re.escape(name)}\.(\w+)\b", source)))
                out.append({
                    "scope": scope, "file": str(path.relative_to(REPO)), "line": node.lineno,
                    "name": name, "call": node.func.attr, "methods": methods,
                    "pattern": pattern, "flags": _flags(flags_node),
                })
    return out


def _literals(pattern: str, flags: int) -> list:
    """Literal runs in a pattern (``gate``, ``qreg``, ``[``), used as pumps."""
    found, current = [], []

    def walk(items):
        for op, arg in items:
            name = str(op)
            if name == "LITERAL":
                current.append(chr(arg))
                continue
            if current:
                found.append("".join(current))
                current.clear()
            if name in ("SUBPATTERN",):
                walk(arg[-1])
            elif name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
                walk(arg[2])
            elif name == "BRANCH":
                for branch in arg[1]:
                    walk(branch)
                    if current:
                        found.append("".join(current))
                        current.clear()
            elif name in ("ASSERT", "ASSERT_NOT"):
                walk(arg[1])
            elif name == "IN":
                for kind, value in arg:
                    if str(kind) == "LITERAL":
                        found.append(chr(value))
                        break
    try:
        walk(sre_parse.parse(pattern, flags))
    except Exception:
        return []
    if current:
        found.append("".join(current))
    return sorted(set(found))[:40]


def pumps_for(pattern: str, flags: int) -> list:
    lits = _literals(pattern, flags)
    out = list(GENERIC_PUMPS)
    out += lits
    out += [lit + " " for lit in lits] + [lit + "\n" for lit in lits]
    out += [lit + "a" for lit in lits] + [lit + "0" for lit in lits]
    return list(dict.fromkeys(p for p in out if p))


def _time_one(pattern, flags, method, text, conn):
    rx = re.compile(pattern, flags)
    start = time.perf_counter()
    if method == "findall":
        rx.findall(text)
    else:
        rx.match(text)
    conn.send(time.perf_counter() - start)


def _timed(pattern, flags, method, text, kill_sec):
    parent, child = mp.Pipe(duplex=False)
    proc = mp.Process(target=_time_one, args=(pattern, flags, method, text, child))
    proc.start()
    proc.join(kill_sec)
    if proc.is_alive():
        proc.kill()
        proc.join()
        return None
    return parent.recv() if parent.poll() else None


ANCHORED = {"match", "fullmatch"}
COMPILED_METHODS = ANCHORED | {"search", "findall", "finditer", "sub", "subn", "split"}


def methods_to_time(entry) -> list:
    """``match`` alone for a pattern the code only calls ``match``/``fullmatch`` on, else
    ``findall`` and ``match``."""
    used = set(entry["methods"]) & COMPILED_METHODS
    if used and used <= ANCHORED:
        return ["match"]
    return ["findall", "match"]


def _check_pattern(entry, size, kill_sec, quick_sec=0.0039):
    """Worst time over the pumps. Each input is first timed at 1/16 of ``size`` in process;
    one under ``quick_sec`` there stays under 1 s at full size even if the pattern is
    quadratic (256 x), and is reported as 16 x its time. The others are rerun at full size in
    a child that is killed at ``kill_sec``."""
    pattern, flags = entry["pattern"], entry["flags"]
    rx = re.compile(pattern, flags)
    worst = {"sec": 0.0, "pump": None, "method": None, "killed": False}
    small = max(1, size // 16)
    methods = methods_to_time(entry)
    for pump in pumps_for(pattern, flags):
        for suffix in SUFFIXES:
            body = (pump * (small // len(pump) + 1))[:small - len(suffix)] + suffix
            for method in methods:
                start = time.perf_counter()
                (rx.findall if method == "findall" else rx.match)(body)
                quick = time.perf_counter() - start
                if quick < quick_sec:
                    estimate = quick * 16
                    if estimate > worst["sec"]:
                        worst.update(sec=estimate, pump=pump + suffix, method=method,
                                     killed=False, measured="scaled")
                    continue
                full = (pump * (size // len(pump) + 1))[:size - len(suffix)] + suffix
                sec = _timed(pattern, flags, method, full, kill_sec)
                if sec is None:
                    worst.update(sec=kill_sec, pump=pump + suffix, method=method, killed=True,
                                 measured="full")
                    return worst
                if sec > worst["sec"]:
                    worst.update(sec=sec, pump=pump + suffix, method=method, killed=False,
                                 measured="full")
    return worst


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--size", type=int, default=1_000_000)
    parser.add_argument("--limit-sec", type=float, default=1.0)
    parser.add_argument("--kill-sec", type=float, default=10.0)
    parser.add_argument("--json")
    parser.add_argument("--scope", action="append")
    args = parser.parse_args(argv)
    entries = [e for e in inventory() if not args.scope or e["scope"] in args.scope]
    over = 0
    for entry in entries:
        entry["worst"] = _check_pattern(entry, args.size, args.kill_sec)
        flag = "OVER" if entry["worst"]["sec"] > args.limit_sec else "ok"
        over += flag == "OVER"
        print(f"{flag:4} {entry['worst']['sec']:8.3f}s {entry['scope']:8} {entry['file']}:"
              f"{entry['line']} {entry['pattern']!r} pump={entry['worst']['pump']!r} "
              f"{entry['worst']['method']}", flush=True)
    print(f"{len(entries)} patterns, {over} over {args.limit_sec} s on {args.size} bytes")
    if args.json:
        Path(args.json).write_text(json.dumps(entries, indent=2))
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
