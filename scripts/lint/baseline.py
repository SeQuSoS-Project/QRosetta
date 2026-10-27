"""Compares shellcheck, hadolint or semgrep JSON output with a baseline of (file, code, count) lines.

Usage: shellcheck -f json1 FILES | python3 scripts/lint/baseline.py shellcheck scripts/lint/shellcheck.txt
       hadolint --no-fail -f json FILES | python3 scripts/lint/baseline.py hadolint scripts/lint/hadolint.txt
       semgrep scan --json ... | python3 scripts/lint/baseline.py semgrep scripts/lint/semgrep.txt
Exit 1 when a file has more findings of a code than its baseline line allows; prints those findings.
With --write, replaces the baseline with today's counts.
"""

import collections
import json
import sys


def findings(tool, text):
    """[(file, code, line, message)] from one tool's JSON output."""
    data = json.loads(text or "[]")
    if tool == "shellcheck":
        rows = data.get("comments", []) if isinstance(data, dict) else data
        return [(r["file"], f"SC{r['code']}", r["line"], r["message"]) for r in rows]
    if tool == "hadolint":
        return [(r["file"], r["code"], r["line"], r["message"]) for r in data]
    if tool == "semgrep":
        return [(r["path"], r["check_id"].rsplit(".", 1)[-1], r["start"]["line"], r["check_id"])
                for r in data.get("results", [])]
    raise ValueError(f"unknown tool {tool!r}")


def read_baseline(text):
    """{(file, code): count} from baseline lines `file code count`; # starts a comment."""
    counts = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            path, code, count = line.split()
            counts[(path, code)] = int(count)
    return counts


def format_baseline(tool, rows):
    counts = collections.Counter((path, code) for path, code, _, _ in rows)
    head = [f"# {tool} findings scripts/lint/check.sh accepts: file, code, count.",
            "# Lower or delete a line when you fix a finding; a count above its line fails the check."]
    return "\n".join(head + [f"{p} {c} {n}" for (p, c), n in sorted(counts.items())]) + "\n"


def compare(rows, baseline):
    """(new findings above the baseline, (file, code) pairs now below it)."""
    by_key = collections.defaultdict(list)
    for row in rows:
        by_key[(row[0], row[1])].append(row)
    new = []
    for key, items in sorted(by_key.items()):
        if len(items) > baseline.get(key, 0):
            new.extend(sorted(items, key=lambda r: r[2]))
    fewer = sorted(key for key, allowed in baseline.items() if len(by_key.get(key, ())) < allowed)
    return new, fewer


def main(argv):
    write = "--write" in argv
    args = [a for a in argv if a != "--write"]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    tool, path = args
    rows = findings(tool, sys.stdin.read())
    if write:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(format_baseline(tool, rows))
        print(f"{path}: {len(rows)} findings recorded")
        return 0
    with open(path, encoding="utf-8") as fh:
        baseline = read_baseline(fh.read())
    new, fewer = compare(rows, baseline)
    for file, code, line, message in new:
        print(f"{file}:{line}: {code} {message}")
    for file, code in fewer:
        print(f"{file} {code}: fewer findings than {path} allows; lower its count")
    if new:
        print(f"{tool}: {len(new)} findings in files or codes above {path}")
        return 1
    print(f"{tool}: {len(rows)} findings, none above {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
