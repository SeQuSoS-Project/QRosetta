"""Service lookup for the requalification harness: kind, directory and optimisation levels of a
canonical runner or compiler id, read from rosetta-api/config.py with the stdlib parser (the
directory is the host name of the registry's base_url, as CLAUDE.md §9.1 prescribes)."""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_FUNCTIONS = {"get_runner_services": "runner", "get_compiler_services": "compiler"}


def _url_defaults(tree):
    urls = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            urls[node.target.id] = node.value.value
    return urls


def services(repo=REPO):
    """{canonical id: {kind, dir, levels, enabled}} for every runner and compiler."""
    tree = ast.parse((Path(repo) / "rosetta-api" / "config.py").read_text())
    urls = _url_defaults(tree)
    found = {}
    for func in ast.walk(tree):
        if not (isinstance(func, ast.FunctionDef) and func.name in _FUNCTIONS):
            continue
        kind = _FUNCTIONS[func.name]
        for ret in ast.walk(func):
            if not (isinstance(ret, ast.Return) and isinstance(ret.value, ast.Dict)):
                continue
            for key, value in zip(ret.value.keys, ret.value.values, strict=True):
                if not (isinstance(key, ast.Constant) and isinstance(value, ast.Dict)):
                    continue
                entry = {k.value: v for k, v in zip(value.keys, value.values, strict=True)
                         if isinstance(k, ast.Constant)}
                base = entry["base_url"]
                url = urls[base.attr] if isinstance(base, ast.Attribute) else ast.literal_eval(base)
                host = re.match(r"https?://([^:/]+)", url).group(1)
                levels = sorted(ast.literal_eval(k) for k in entry["optimization_levels"].keys)
                found[key.value] = {
                    "kind": kind,
                    "dir": f"{kind}s/{host}",
                    "levels": levels,
                    "enabled": ast.literal_eval(entry["enabled"]) if "enabled" in entry else True,
                }
    return found


def sdk_packages(main_py_text):
    """Distribution names a service declares with ``declare_sdk_packages(...)``."""
    names = []
    for call in re.finditer(r"declare_sdk_packages\((.*?)\)", main_py_text, re.S):
        names += re.findall(r"""["']([^"']+)["']""", call.group(1))
    return names
