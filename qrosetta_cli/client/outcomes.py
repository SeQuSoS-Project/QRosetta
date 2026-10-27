"""--fail-on (spec Q4): outcome names as the server's summaries publish them (GET /config
summary_outcomes), each mapped to an exit code by the role the server gives it; the CLI holds
no list of names and applies no rule of its own."""

from qrosetta_cli.errors import CliError, Exit, usage, worst

ROLE_EXIT = {
    "difference": Exit.DISAGREEMENT,
    "not_established": Exit.NOT_ESTABLISHED,
    "runs_without_output": Exit.RUNS_WITHOUT_OUTPUT,
}


def parse(values):
    """Names from repeated or comma-separated values, kebab or snake spelling; [] for none."""
    names = []
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip().lower().replace("-", "_")
            if part and part not in names:
                names.append(part)
    if names == ["none"]:
        return []
    if "none" in names:
        raise usage(
            "--fail-on none cannot be combined with outcome names.", hint="qrosetta run --help", reason="fail_on"
        )
    return names


def catalog(config):
    """The server's {name: role} map, or None when it publishes none."""
    block = (config or {}).get("summary_outcomes")
    roles = block.get("roles") if isinstance(block, dict) else None
    return roles if isinstance(roles, dict) and roles else None


def rule_version(config, summary=None):
    if isinstance(summary, dict) and summary.get("analysis_version"):
        return summary["analysis_version"]
    block = (config or {}).get("summary_outcomes") or {}
    return block.get("analysis_version") or ((config or {}).get("server") or {}).get("analysis_version")


def resolve(names, config):
    """The names --fail-on matches against: `any` is every name whose role is not agreement.
    A name the server does not list is exit 12; an agreement name is a usage error."""
    if not names:
        return []
    roles = catalog(config)
    if roles is None:
        raise CliError(
            "This server publishes no outcome names, so --fail-on cannot be checked.",
            Exit.INCOMPATIBLE,
            "feature_missing",
            hint="drop --fail-on, or upgrade the server to one with the summary feature",
        )
    out = []
    for name in names:
        if name == "any":
            out += [n for n, role in roles.items() if role in ROLE_EXIT and n not in out]
            continue
        if name not in roles:
            listed = ", ".join(n for n, role in roles.items() if role in ROLE_EXIT)
            raise CliError(
                f"--fail-on {name}: this server lists no such outcome. It lists {listed}.",
                Exit.INCOMPATIBLE,
                "unknown_outcome",
                hint="qrosetta run --help",
            )
        if roles[name] not in ROLE_EXIT:
            raise usage(
                f"--fail-on {name}: that outcome is an agreement ({roles[name]}); --fail-on takes outcomes "
                "that are not.",
                hint="qrosetta run --help",
                reason="fail_on",
            )
        if name not in out:
            out.append(name)
    return out


def evaluate(names, summary, config):
    """(exit code, matched names) of one job's summary."""
    if not names or not isinstance(summary, dict):
        return Exit.OK, []
    counts = summary.get("outcomes") or {}
    roles = summary.get("outcome_roles") or catalog(config) or {}
    matched = [n for n in names if (counts.get(n) or 0) > 0]
    codes = [ROLE_EXIT[roles[n]] for n in matched if roles.get(n) in ROLE_EXIT]
    return worst(codes) if codes else Exit.OK, matched


def block(names, matched, version):
    """The envelope's `outcome` object."""
    return {"rule_version": version, "fail_on": list(names), "matched": list(matched)}
