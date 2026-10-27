"""The version handshake (spec Q2): the `server` block of GET /config, the CLI's API levels, and
the checks a command needing a level or feature makes."""

from qrosetta_cli.errors import CliError, Exit

CLI_API_LEVELS = (1, 1)
UPGRADE_HINT = "pipx upgrade qrosetta, or upgrade the server to platform 2.0.0 or later"


def fetch_config(transport, timeout=10):
    """GET /config as JSON, or a CliError: unreachable (11), or an answer that is not the
    Quantum Rosetta config (12)."""
    resp = transport.request("GET", "/config", timeout=timeout)
    data = resp.json()
    if resp.status != 200 or not isinstance(data, dict) or "limits" not in data:
        raise CliError(f"{transport.url} answered GET /config with HTTP {resp.status}, not Quantum Rosetta's "
                       "configuration.", Exit.INCOMPATIBLE, "not_quantum_rosetta", hint="qrosetta config show",
                       http_status=resp.status)
    return data


def server_block(config):
    block = config.get("server") if isinstance(config, dict) else None
    return block if isinstance(block, dict) else None


def levels(block):
    raw = (block or {}).get("api_levels")
    if isinstance(raw, (list, tuple)) and len(raw) == 2 and all(isinstance(v, int) for v in raw):
        return tuple(raw)
    return None


def describe(block):
    """'platform 2.0.0, API levels 1-1', or a note that the server predates the handshake."""
    if not block:
        return "server predates the version handshake"
    lv = levels(block)
    text = f"platform {block.get('platform_version', '?')}"
    return text + (f", API levels {lv[0]}-{lv[1]}" if lv else "")


def check(config, features=()):
    """Raise exit 12 unless the server publishes the handshake, shares an API level with this
    CLI, and offers every feature in `features` (name or (name, minimum version))."""
    block = server_block(config)
    if block is None:
        raise CliError("This server predates the CLI; it needs platform 2.0.0 or later.", Exit.INCOMPATIBLE,
                       "server_too_old", hint=UPGRADE_HINT)
    lv = levels(block)
    if lv is None or lv[1] < CLI_API_LEVELS[0] or lv[0] > CLI_API_LEVELS[1]:
        raise CliError(f"This server serves API levels {lv}; this CLI speaks {CLI_API_LEVELS[0]}-"
                       f"{CLI_API_LEVELS[1]}.", Exit.INCOMPATIBLE, "api_levels", hint=UPGRADE_HINT)
    offered = block.get("features") or {}
    for feature in features:
        fname, minimum = feature if isinstance(feature, tuple) else (feature, 1)
        have = offered.get(fname)
        if not isinstance(have, int) or have < minimum:
            raise CliError(f"This server does not offer {fname}@{minimum}.", Exit.INCOMPATIBLE,
                           "feature_missing", hint=UPGRADE_HINT)
    return block
