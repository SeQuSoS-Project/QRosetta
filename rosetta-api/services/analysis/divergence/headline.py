"""Headline model of a report's per-backend counts: which backends the Summary headline names as
differing, built from the pairs that differ (BY-only pairs left out). Inconclusive and
not-comparable pairs count as neither agreement nor difference.

``kind`` is one of:
- 'none': no pair differs;
- 'named': one smallest set of at most MAX_NAMED backends, fewer than half, appears in every
  pair that differs; ``named`` lists it as groups of members that agree with each other, each
  with ``differs_from`` (backends outside it a member differs from) and ``compared_outside``;
  ``rest`` are the other backends, among which no pair differs;
- 'camps': with the backends that differ from none (``neutral``) set aside, the others split into
  2 to MAX_GROUPS groups, at least two of them with two or more members, with no differing pair
  inside a group and every compared pair between groups differing; ``camps`` lists them,
  ``largest`` is the unique largest group or null;
- 'pairs': at most MAX_NAMED pairs differ and none of the above applies; ``pairs`` lists them;
- 'spread': anything else; the backends that differ from more than half of those they were
  compared with are split into groups that agree with each other, ranked by the size of their
  difference from the other backends (lowest fidelity, or median total variation), then by the
  share of pairs that differ; ``named`` lists the first groups up to MAX_NAMED backends (at least
  one group) and ``unnamed`` the rest of these backends. With no such backend, ``named`` lists
  the MAX_NAMED backends that differ most, one per group. ``rest`` are the other backends and
  ``pairs`` the differing pairs among ``rest``.

``flagged`` are the backends the headline names as differing; ``reference`` are the backends a
named backend or group is sized against ('named' and 'spread': ``rest``; otherwise empty);
``chance`` are the named single backends of a measured report that differ from fewer than half
of the backends they were compared with and are consistent with all the others, a pattern one
unusual sample can produce; ``by_only_hub`` is the backend in every BY-only pair when there are
two or more such pairs. Names are ordered as the page orders them: runner keys by the root
collation order of their characters (``-`` and ``~`` before digits before letters)."""

import math
from functools import cmp_to_key

MAX_NAMED = 4
MAX_GROUPS = 4

_COLLATION = {c: i for i, c in enumerate("-~0123456789abcdefghijklmnopqrstuvwxyz")}


def _collation_key(key: str) -> list:
    return [_COLLATION.get(c, len(_COLLATION) + ord(c)) for c in key]


def _sign(x) -> int:
    return (x > 0) - (x < 0)


def _key_order(x: str, y: str) -> int:
    a, b = _collation_key(x), _collation_key(y)
    return (a > b) - (a < b)


def minimum_covers(edges: list, limit: int = MAX_NAMED) -> list:
    """Every vertex cover of the smallest size up to ``limit`` of the graph with these edges, or []."""
    for k in range(1, limit + 1):
        found = {}

        def search(chosen: frozenset, depth: int):
            open_edge = next((e for e in edges if e[0] not in chosen and e[1] not in chosen), None)
            if open_edge is None:
                cover = sorted(chosen)
                found["\0".join(cover)] = cover
                return
            if depth == k:
                return
            for x in open_edge:
                search(chosen | {x}, depth + 1)

        search(frozenset(), 0)
        if found:
            return [c for c in found.values() if len(c) == k]
    return []


def _components(keys: list, linked) -> list:
    """Connected components of ``keys`` under the symmetric relation ``linked``, largest first."""
    seen, groups = set(), []
    for start in keys:
        if start in seen:
            continue
        members, stack = [], [start]
        seen.add(start)
        while stack:
            k = stack.pop()
            members.append(k)
            for n in keys:
                if n not in seen and linked(k, n):
                    seen.add(n)
                    stack.append(n)
        groups.append(sorted(members))
    return sorted(groups, key=cmp_to_key(lambda x, y: (len(y) - len(x)) or _key_order(x[0], y[0])))


def median(xs: list) -> float:
    """Median of a non-empty list of numbers."""
    s = sorted(xs)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def sizes_between(verdicts: dict, members: list, others: list) -> list:
    """Recorded sizes (total variation or fidelity) of the compared pairs between ``members`` and ``others``."""
    by_key = {b["key"]: b for b in verdicts["backends"]}
    out = []
    for k in members:
        b = by_key.get(k)
        if not b:
            continue
        out += [b["size_with"][o] for o in others if o != k and o in b["size_with"]]
    return out


def headline_model(verdicts: dict) -> dict:
    """The headline model of ``backend_verdicts`` output (see the module description)."""
    failed = {"offline": [], "error": [], "timeout": []}
    for b in verdicts["backends"]:
        if b["status"] != "ok" and b["status"] in failed:
            failed[b["status"]].append(b["key"])
    ok = [b for b in verdicts["backends"] if b["status"] == "ok"]
    by_key = {b["key"]: b for b in ok}
    keys = sorted(b["key"] for b in ok)

    def differs(x, y):
        return y in by_key[x]["differs_with"]

    def agree(x, y):
        return y in by_key[x]["agrees_with"]

    def ratio(b):
        return len(b["differs_with"]) / max(1, b["compared"])

    differing = sorted((b for b in ok if b["differs_with"]), key=cmp_to_key(
        lambda x, y: _sign(ratio(y) - ratio(x)) or (len(y["differs_with"]) - len(x["differs_with"]))
        or _key_order(x["key"], y["key"])))
    edges = [[k, o] for k in keys for o in by_key[k]["differs_with"] if o in by_key and k < o]

    by_only = verdicts.get("by_only_pairs") or []
    hubs = []
    if len(by_only) >= 2:
        hubs = list(by_only[0])
        for pair in by_only:
            hubs = [k for k in hubs if k in pair]
    base = {"failed": failed, "ok": len(ok), "differing": [b["key"] for b in differing], "edges": edges,
            "by_only_hub": hubs[0] if len(hubs) == 1 else None, "named": [], "rest": [], "camps": [],
            "largest": None, "neutral": [], "pairs": [], "flagged": [], "unnamed": [], "reference": [],
            "chance": []}

    def chance(groups):
        if verdicts["mode"] != "measured":
            return []
        singles = [by_key[g["members"][0]] for g in groups if len(g["members"]) == 1]
        return [b["key"] for b in singles
                if len(b["differs_with"]) * 2 < b["compared"]
                and len(b["differs_with"]) + len(b["agrees_with"]) == b["compared"]]

    if not edges:
        return {**base, "kind": "none"}

    def describe(members):
        inside = set(members)
        differs_from, compared_outside = set(), set()
        for k in members:
            b = by_key[k]
            differs_from.update(o for o in b["differs_with"] if o not in inside)
            compared_outside.update(o for o in b["compared_with"] if o not in inside and o in by_key)
        return {"members": members, "differs_from": sorted(differs_from),
                "compared_outside": len(compared_outside),
                "differs_from_all": len(differs_from) > 0 and len(differs_from) == len(compared_outside)}

    covers = minimum_covers(edges)
    if len(covers) == 1 and len(covers[0]) * 2 < len(ok) and len(edges) > 1:
        cover = covers[0]
        named = sorted(map(describe, _components(cover, agree)), key=cmp_to_key(
            lambda x, y: (len(y["differs_from"]) - len(x["differs_from"]))
            or _key_order(x["members"][0], y["members"][0])))
        rest = [k for k in keys if k not in cover]
        return {**base, "kind": "named", "named": named, "rest": rest, "flagged": cover, "reference": rest,
                "chance": chance(named)}

    neutral = [k for k in keys if not by_key[k]["differs_with"]]
    active = [k for k in keys if k not in neutral]
    camps = _components(active, lambda x, y: not differs(x, y))
    consistent = all(not differs(x, y) for c in camps for x in c for y in c)
    if 2 <= len(camps) <= MAX_GROUPS and consistent and len(camps[1]) >= 2:
        largest = camps[0] if len(camps[0]) > len(camps[1]) else None
        return {**base, "kind": "camps", "camps": [describe(c) for c in camps], "largest": largest,
                "neutral": neutral, "flagged": [k for c in camps if c is not largest for k in c]}

    if len(edges) <= MAX_NAMED:
        return {**base, "kind": "pairs", "pairs": edges, "flagged": sorted({k for e in edges for k in e})}

    majority = [b["key"] for b in differing if len(b["differs_with"]) * 2 > b["compared"]]
    unnamed = []
    if majority:
        others = [k for k in keys if k not in majority]
        measured = verdicts["mode"] == "measured"

        def score(members):
            values = sizes_between(verdicts, members, others)
            if not values:
                return math.inf
            return -median(values) if measured else min(values)

        ranked = [{"m": m, "score": score(m), "share": max(ratio(by_key[k]) for k in m)}
                  for m in _components(majority, agree)]
        ranked.sort(key=cmp_to_key(
            lambda x, y: (0 if x["score"] == y["score"] else -1 if x["score"] < y["score"] else 1)
            or _sign(y["share"] - x["share"]) or (len(y["m"]) - len(x["m"])) or _key_order(x["m"][0], y["m"][0])))
        groups, count = [], 0
        for r in ranked:
            if not groups or count + len(r["m"]) <= MAX_NAMED:
                groups.append(describe(r["m"]))
                count += len(r["m"])
            else:
                unnamed += r["m"]
        unnamed.sort()
    else:
        groups = [describe([b["key"]]) for b in differing[:MAX_NAMED]]
    named = [k for g in groups for k in g["members"]]
    flagged = named + unnamed
    rest = [k for k in keys if k not in flagged]
    return {**base, "kind": "spread", "named": groups, "unnamed": unnamed, "rest": rest, "reference": rest,
            "chance": chance(groups), "pairs": [e for e in edges if e[0] not in flagged and e[1] not in flagged],
            "flagged": flagged}
