"""Commands that need neither half in particular: version and config."""

import os
import platform
import subprocess
import sys

from qrosetta_cli import __version__, config as cfgmod, jobstore, localstack, manifest, mode as modes, output
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit, usage
from qrosetta_cli.output import progress, result


def cmd_version(ctx):
    from qrosetta_cli.client import handshake

    mode = modes.detect(ctx.opt("project_dir"), ctx.env, ctx.checkout)
    server = ctx.server()
    block, state = None, "not answering"
    try:
        config = handshake.fetch_config(ctx.transport(timeout=3), timeout=3)
        block = handshake.server_block(config)
        ctx.note_handshake(block)
        state = handshake.describe(block)
    except CliError as exc:
        state = "not answering" if exc.code == Exit.UNREACHABLE else exc.message
    py = platform.python_version()
    block_manifest = {"release": None, "index": None}
    if mode.name == "installed":
        release = manifest.load()
        described = manifest.describe(release)
        block_manifest.update(
            release=(release or {}).get("platform_version"), images_published=manifest.images_published(release)
        )
    else:
        described = "none (images are built from the checkout; the manifest arrives with release 2.0.0)"
    rows = [
        ("Python", py),
        ("Mode", f"{mode.name} mode" + (f", {mode.project_dir}" if mode.project_dir else "")),
        ("CLI API levels", f"{handshake.CLI_API_LEVELS[0]}-{handshake.CLI_API_LEVELS[1]}"),
        ("Release manifest", described),
        ("Server", f"{server.url} ({server.source}): {state}"),
    ]
    width = max(len(k) for k, _ in rows)
    result(f"qrosetta {__version__}")
    result("")
    for key, value in rows:
        result(f"  {key:<{width}}  {value}")
    return Result(
        0,
        {
            "cli_version": __version__,
            "python": py,
            "mode": mode.name,
            "project_dir": mode.project_dir or None,
            "cli_api_levels": list(handshake.CLI_API_LEVELS),
            "manifest": block_manifest,
            "server": dict(ctx.server_block or {}, handshake=block, reachable=state != "not answering"),
        },
    )


def _effective(ctx):
    cfg, env = ctx.cfg, ctx.env
    rows = []

    def add(key, value, source):
        rows.append({"key": key, "value": value, "source": source})

    add("config file", cfg.path, "loaded" if cfg.loaded else "absent")
    server = ctx.server()
    add("server", f"{server.name} {server.url}" if server.name != server.url else server.url, server.source)
    value, source = cfgmod.env_or_config(env, "QROSETTA_ENGINE", cfg, "lifecycle", "engine")
    add("lifecycle.engine", value or "the first of docker and podman whose `info` answers", source)
    value, source = cfgmod.env_or_config(env, "QROSETTA_ON_EXIT", cfg, "lifecycle", "on_exit")
    add("lifecycle.on_exit", value or "ask on a terminal, else standby", source)
    bind = cfg.get("lifecycle", "bind")
    add(
        "lifecycle.bind",
        bind or "127.0.0.1:8080 (the compose default, QROSETTA_HTTP_BIND)",
        "config lifecycle.bind" if bind else "default",
    )
    quota, since, source = localstack.cpu_quota(env, cfg)
    add("lifecycle.cpu_quota", quota, f"{source}, since {since}" if since else source)
    jobs = jobstore.resolve(env, cfg)
    add("lifecycle.jobs_kept", jobs["jobs_kept"][0], jobs["jobs_kept"][1])
    add("lifecycle.job_storage", f"{jobs['job_storage'][0]} MiB", jobs["job_storage"][1])
    add("lifecycle.job_memory", f"{jobs['job_memory'][0]} MiB", jobs["job_memory"][1])
    add("lifecycle.job_retention", f"{jobs['job_retention'][0]} s", jobs["job_retention"][1])
    value, source = cfgmod.env_or_config(env, "QROSETTA_RESULTS_DIR", cfg, "results", "dir")
    add("results.dir", os.path.abspath(cfgmod.expand(value or "./qrosetta-results", env)), source)
    from qrosetta_cli.client import servers

    add(
        "auth.credentials",
        servers.credentials_path(cfg, env),
        "config auth.credentials" if cfg.get("auth", "credentials") else "default",
    )
    for key, default in (("color", "auto"), ("progress", "auto"), ("experimental_notice", True)):
        value = cfg.get("output", key)
        add(
            f"output.{key}", default if value is None else value, "default" if value is None else f"config output.{key}"
        )
    mode = modes.detect(ctx.opt("project_dir"), env, ctx.checkout)
    add("project directory", mode.project_dir or "none (installed mode)", mode.source)
    add(
        "project",
        env.get("QROSETTA_PROJECT") or "qsimulators",
        "env QROSETTA_PROJECT" if env.get("QROSETTA_PROJECT") else "default",
    )
    names = sorted((cfg.get("profiles") or {}).keys())
    if names:
        add("user profiles (experimental)", ", ".join(names), "config profiles")
    return rows


def cmd_config_path(ctx):
    result(ctx.cfg.path)
    return Result(0, {"path": ctx.cfg.path, "exists": os.path.isfile(ctx.cfg.path)})


def cmd_config_show(ctx):
    rows = _effective(ctx)
    width = max(len(r["key"]) for r in rows)
    for r in rows:
        value = str(r["value"]).lower() if isinstance(r["value"], bool) else r["value"]
        result(f"{r['key']:<{width}}  {value}  ({r['source']})")
    return Result(0, {"path": ctx.cfg.path, "loaded": ctx.cfg.loaded, "settings": rows})


def cmd_config_init(ctx):
    path = ctx.cfg.path
    if os.path.exists(path):
        raise usage(
            f"{path} already exists; config init does not overwrite it.", hint=f"edit {path}", reason="config_exists"
        )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(cfgmod.TEMPLATE)
    progress(f"Wrote {path}")
    result(path)
    return Result(0, {"path": path})


def cmd_config_edit(ctx):
    path = ctx.cfg.path
    editor = ctx.env.get("VISUAL") or ctx.env.get("EDITOR")
    if not editor:
        raise usage("Set VISUAL or EDITOR to edit the config file.", hint=f"edit {path}", reason="no_editor")
    if not os.path.exists(path):
        raise CliError(f"{path} does not exist.", Exit.NOT_FOUND, "config_missing", hint="qrosetta config init")
    code = subprocess.call([*editor.split(), path])
    if code != 0:
        raise CliError(f"{editor} exited with {code}.", Exit.USAGE, "editor_failed", hint=f"edit {path}")
    cfgmod.load(path, ctx.env)
    return Result(0, {"path": path})


def write_log(env, text):
    """Append a traceback to $XDG_STATE_HOME/qrosetta/cli.log; return the path or None."""
    path = os.path.join(cfgmod.qr_dir("state", env), "cli.log")
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"--- {output.utc_now()} qrosetta {__version__} {' '.join(sys.argv[1:2])}\n{text}\n")
        return path
    except OSError:
        return None
