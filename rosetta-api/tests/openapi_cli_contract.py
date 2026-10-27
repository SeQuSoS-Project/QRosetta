"""The OpenAPI contract of the routes the stable qrosetta commands read (CLI spec S16): a
normalised extract of /openapi.json committed as `tests/openapi_cli_baseline.json`, and the
check that the current app still serves every older CLI that was built against it.

Refused (breaking): a route or method removed; a parameter or request field removed, newly
required, or accepting fewer types or enum values; a request body or success status or media
type changed; a response field removed, no longer always present, or returning a type it did
not. Allowed (additive): new routes, optional parameters and request fields, response
fields, enum values in responses, and wider request or narrower response types. A breaking
change passes only when `API_LEVELS` in `services/server_info.py` raises its maximum above the
baseline's, and the previous level stays served for 12 months.

Refresh the baseline deliberately, from rosetta-api/ (it refuses a breaking change whose
API level was not raised):

    PYTHONPATH=.:../shared python -m tests.openapi_cli_contract --write

`--check` prints the differences and exits 1 on a refused one.
"""

import argparse
import json
import os
import sys

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openapi_cli_baseline.json")

CLI_ROUTES = (
    "GET /config",
    "GET /runners",
    "GET /compilers",
    "GET /algorithms",
    "GET /examples",
    "GET /examples/{name}",
    "GET /benchmarks/mqt/list",
    "GET /benchmarks/qasmbench/list",
    "GET /benchmarks/mqt",
    "GET /benchmarks/qasmbench",
    "POST /generate_circuit",
    "POST /auth/token",
    "GET /auth/me",
    "POST /plan",
    "POST /compare",
    "POST /compare_measured",
    "POST /run_batch_suite",
    "GET /jobs/{job_id}",
    "GET /jobs/{job_id}/report",
    "GET /jobs/{job_id}/summary",
    "POST /summary",
    "POST /jobs/{job_id}/export",
    "POST /export",
    "GET /selftest",
    "GET /jobs/{job_id}/selftest-result",
)

EXPERIMENTAL_ROUTES = (
    "POST /experiments",
    "GET /experiments/{job_id}/bundle",
    "GET /jobs/{job_id}/circuit-texts",
    "GET /openapi.json",
)

_SIMPLE_KEYS = ("type", "properties", "required", "items", "additionalProperties", "enum")


def _resolve(schema, components, seen):
    while isinstance(schema, dict) and "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        if name in seen:
            return {"recursive": name}, seen
        seen = seen | {name}
        schema = components.get(name, {})
    return schema, seen


def _merge(nodes):
    """One node for a union: the types of every member, and the shape of the members that
    have one (an object, array or enum member keeps its own)."""
    out = {"type": sorted({t for n in nodes for t in n.get("type", ["any"])})}
    shaped = [n for n in nodes if set(n) - {"type"}]
    if len(shaped) == 1:
        out.update({k: v for k, v in shaped[0].items() if k != "type"})
    elif shaped:
        out["anyOf"] = sorted(shaped, key=lambda n: json.dumps(n, sort_keys=True))
    if "enum" in out and any("enum" not in n and n.get("type") != ["null"] for n in nodes):
        del out["enum"]
    return out


def normalise(schema, components, seen=frozenset()):
    """A schema reduced to what an older client depends on: types (refs inlined, unions
    merged, null as a type), properties, required, items, additionalProperties and enum.
    Titles, descriptions, defaults, formats and numeric bounds are dropped."""
    schema, seen = _resolve(schema, components, seen)
    if not isinstance(schema, dict):
        return {"type": ["any"]}
    if "recursive" in schema:
        return schema
    members = schema.get("anyOf") or schema.get("oneOf")
    if members:
        return _merge([normalise(m, components, seen) for m in members])
    if schema.get("allOf"):
        parts = [normalise(m, components, seen) for m in schema["allOf"]]
        if len(parts) == 1:
            return parts[0]
        node = {"type": ["object"], "properties": {}, "required": []}
        for part in parts:
            node["properties"].update(part.get("properties", {}))
            node["required"] = sorted(set(node["required"]) | set(part.get("required", [])))
        return node
    node = {}
    types = schema.get("type")
    if types is None and "const" in schema:
        node["enum"] = [schema["const"]]
    if isinstance(types, str):
        types = [types]
    if "enum" in schema:
        node["enum"] = sorted(schema["enum"], key=lambda v: json.dumps(v, sort_keys=True))
    if types is None and "properties" in schema:
        types = ["object"]
    node["type"] = sorted(set(types)) if types else ["any"]
    if "properties" in schema:
        node["properties"] = {k: normalise(v, components, seen) for k, v in schema["properties"].items()}
        node["required"] = sorted(schema.get("required", []))
    if "items" in schema:
        node["items"] = normalise(schema["items"], components, seen)
    extra = schema.get("additionalProperties")
    if isinstance(extra, dict):
        node["additionalProperties"] = normalise(extra, components, seen)
    elif extra is False:
        node["additionalProperties"] = False
    return node


def _operation(op, components):
    params = {}
    for p in op.get("parameters", []):
        p, _ = _resolve(p, components, frozenset())
        params[f"{p['in']}:{p['name']}"] = {"required": bool(p.get("required")),
                                            "schema": normalise(p.get("schema", {}), components)}
    body = None
    if op.get("requestBody"):
        rb, _ = _resolve(op["requestBody"], components, frozenset())
        (media, content), = sorted(rb.get("content", {}).items())[:1]
        body = {"media": media, "required": bool(rb.get("required")),
                "schema": normalise(content.get("schema", {}), components)}
    success = sorted(code for code in op.get("responses", {}) if code.startswith("2"))
    response = None
    if success:
        entry = op["responses"][success[0]]
        content = entry.get("content") or {}
        json_schema = (content.get("application/json") or {}).get("schema")
        response = {"status": int(success[0]), "media": sorted(content),
                    "schema": normalise(json_schema, components) if json_schema is not None else None}
    return {"parameters": params, "request": body, "response": response}


def extract(doc, routes=CLI_ROUTES):
    """{"METHOD /path": operation} for `routes`; a route the document lacks is left out."""
    components = (doc.get("components") or {}).get("schemas") or {}
    out = {}
    for route in routes:
        method, path = route.split(" ", 1)
        op = ((doc.get("paths") or {}).get(path) or {}).get(method.lower())
        if op is not None:
            out[route] = _operation(op, components)
    return out


def _types(node):
    types = set(node.get("type", ["any"]))
    if "number" in types:
        types.add("integer")
    return types


def _compare(base, cur, where, direction, found):
    """Append (breaking, where, message) for each difference between two normalised schemas;
    `direction` is "request" (the client sends it) or "response" (the client reads it)."""
    if "recursive" in base or "recursive" in cur:
        return
    tb, tc = _types(base), _types(cur)
    if direction == "request":
        if "any" not in tc and not ("any" not in tb and tb <= tc):
            found.append((True, where, f"accepts {sorted(tc)}, not {sorted(tb)}"))
        elif tb != tc:
            found.append((False, where, f"accepts {sorted(tc)} (was {sorted(tb)})"))
        if "enum" in cur and ("enum" not in base or set(map(json.dumps, base["enum"])) - set(map(json.dumps, cur["enum"]))):
            found.append((True, where, f"accepts only {cur['enum']} (was {base.get('enum', 'any value')})"))
        elif base.get("enum") != cur.get("enum"):
            found.append((False, where, f"accepts {cur.get('enum', 'any value')} (was {base['enum']})"))
    else:
        if "any" not in tb and ("any" in tc or not tc <= tb):
            found.append((True, where, f"may return {sorted(tc)}, not only {sorted(tb)}"))
        elif tb != tc:
            found.append((False, where, f"returns {sorted(tc)} (was {sorted(tb)})"))
        if base.get("enum") != cur.get("enum"):
            found.append((False, where, f"values {cur.get('enum', 'any')} (was {base.get('enum', 'any')})"))
    bprops, cprops = base.get("properties"), cur.get("properties")
    if bprops is not None or cprops is not None:
        bprops, cprops = bprops or {}, cprops or {}
        breq, creq = set(base.get("required", [])), set(cur.get("required", []))
        for name in sorted(set(bprops) | set(cprops)):
            here = f"{where}.{name}"
            if name not in cprops:
                found.append((True, here, "removed"))
                continue
            if name not in bprops:
                newly_required = direction == "request" and name in creq
                found.append((newly_required, here, "added, required" if newly_required else "added"))
                continue
            if direction == "request" and name in creq and name not in breq:
                found.append((True, here, "now required"))
            if direction == "response" and name in breq and name not in creq:
                found.append((True, here, "no longer always present"))
            _compare(bprops[name], cprops[name], here, direction, found)
    for key, label in (("items", "[]"), ("additionalProperties", "{*}")):
        b, c = base.get(key), cur.get(key)
        if isinstance(b, dict) and isinstance(c, dict):
            _compare(b, c, where + label, direction, found)
        elif b is False and c is not False and direction == "response":
            found.append((True, where + label, "may now carry fields it did not"))
        elif direction == "request" and c is False and b is not False:
            found.append((True, where + label, "no longer accepts extra fields"))


def compare(base_routes, cur_routes):
    """[(breaking, where, message)] for the routes of the baseline against the current ones."""
    found = []
    for route in sorted(set(base_routes) | set(cur_routes)):
        if route not in cur_routes:
            found.append((True, route, "removed"))
            continue
        if route not in base_routes:
            found.append((False, route, "not in the baseline"))
            continue
        b, c = base_routes[route], cur_routes[route]
        for name in sorted(set(b["parameters"]) | set(c["parameters"])):
            here = f"{route} parameter {name}"
            bp, cp = b["parameters"].get(name), c["parameters"].get(name)
            if cp is None:
                found.append((True, here, "removed"))
            elif bp is None:
                found.append((cp["required"], here, "added, required" if cp["required"] else "added"))
            else:
                if cp["required"] and not bp["required"]:
                    found.append((True, here, "now required"))
                _compare(bp["schema"], cp["schema"], here, "request", found)
        bb, cb = b["request"], c["request"]
        if bb is None and cb is not None:
            found.append((cb["required"], f"{route} body", "added, required" if cb["required"] else "added"))
        elif bb is not None and cb is None:
            found.append((True, f"{route} body", "removed"))
        elif bb is not None:
            if bb["media"] != cb["media"]:
                found.append((True, f"{route} body", f"media type {cb['media']} (was {bb['media']})"))
            else:
                _compare(bb["schema"], cb["schema"], f"{route} body", "request", found)
        br, cr = b["response"], c["response"]
        if br is None or cr is None:
            if br != cr:
                found.append((br is not None, f"{route} response", "removed" if cr is None else "added"))
            continue
        if br["status"] != cr["status"]:
            found.append((True, f"{route} response", f"status {cr['status']} (was {br['status']})"))
        missing = sorted(set(br["media"]) - set(cr["media"]))
        if missing:
            found.append((True, f"{route} response", f"no longer {missing}"))
        if br["schema"] is not None and cr["schema"] is None:
            found.append((True, f"{route} response", "schema removed"))
        elif br["schema"] is not None:
            _compare(br["schema"], cr["schema"], f"{route} response", "response", found)
        elif cr["schema"] is not None:
            found.append((False, f"{route} response", "schema documented"))
    return found


def current(app=None):
    """The normalised routes of the app in this checkout, and its API levels."""
    if app is None:
        from main import app
    from services.server_info import API_LEVELS
    app.openapi_schema = None
    return {"api_levels": list(API_LEVELS), "routes": extract(app.openapi())}


def load_baseline(path=BASELINE):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def verdict(baseline, now):
    """(refused, notes): the breaking differences the API levels do not cover, and every
    other difference as text."""
    found = compare(baseline["routes"], now["routes"])
    raised = now["api_levels"][1] > baseline["api_levels"][1]
    refused = [f"{where}: {msg}" for breaking, where, msg in found if breaking and not raised]
    notes = [f"{'breaking, covered by API level ' + str(now['api_levels'][1]) if breaking else 'additive'}: "
             f"{where}: {msg}" for breaking, where, msg in found if not (breaking and not raised)]
    return refused, notes


def dumps(doc):
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="refresh the baseline (refuses an uncovered break)")
    parser.add_argument("--check", action="store_true", help="print the differences; exit 1 on a refused one")
    args = parser.parse_args(argv)
    now = current()
    refused, notes = verdict(load_baseline(), now) if os.path.exists(BASELINE) else ([], ["no baseline yet"])
    for line in notes:
        print(line)
    for line in refused:
        print(f"REFUSED: {line}")
    if refused:
        print("A breaking change for older CLIs: keep the old field or route, or raise the maximum of "
              "API_LEVELS in services/server_info.py (and keep serving the previous level for 12 months), "
              "then refresh the baseline.", file=sys.stderr)
        return 1
    if args.write:
        with open(BASELINE, "w", encoding="utf-8") as fh:
            fh.write(dumps(now))
        print(f"wrote {BASELINE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
