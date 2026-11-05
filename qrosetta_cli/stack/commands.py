"""The lifecycle commands: start, stop, remove, status, logs, build, profiles, doctor."""

import os
import platform
import subprocess

from qrosetta_cli import jobstore, layout, localstack, mode as modes, output
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import actions, guard, hostload, installed, preflight, profiles, quota, serve
from qrosetta_cli.stack import ownership as own
from qrosetta_cli.stack import project as st
from qrosetta_cli.stack.engine import TRANSFER_TIMEOUT_SEC, Engine, choose_engine, timed_out


def open_stack(ctx, cpu_quota=None):
    """(mode, engine, stack) for the checkout's compose project, or in installed mode for the
    compose file generated from the release manifest. With the CPU quota off (`cpu_quota`, else
    the recorded stack setting) compose also gets the override that removes the CPU limits."""
    mode = modes.detect(ctx.opt("project_dir"), ctx.env, ctx.checkout)
    release = None
    if mode.name == "checkout":
        project_dir = mode.project_dir
    else:
        project_dir, release = installed.prepare(ctx.env)
    if ctx.engine_factory:
        engine = ctx.engine_factory(project_dir)
    else:
        choice = choose_engine(ctx.env, ctx.cfg.get("lifecycle", "engine"))
        engine = Engine(choice.name, project_dir, env=ctx.env, info=choice.info, reason=choice.reason)
    engine.env.update(hostload.compose_env(ctx.env))
    if release:
        installed.localise(engine, release)
    engine.check_compose()
    stack = st.load_stack(engine)
    stack.release = release
    if cpu_quota is None:
        cpu_quota = localstack.cpu_quota(ctx.env, ctx.cfg, stack.name)[0]
    quota.apply(engine, stack, cpu_quota, ctx.env)
    return mode, engine, stack


def _bind(ctx):
    bind = ctx.opt("bind") or ctx.cfg.get("lifecycle", "bind")
    return serve.check_bind(bind) if bind else None


def check_host(allow_emulation, system=None, machine=None):
    """Refuse a host that is not Linux x86_64 unless --allow-emulation (spec §6.1)."""
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    if system == "Linux" and machine in ("x86_64", "amd64"):
        return
    if not allow_emulation:
        raise CliError(
            f"This host is {system} {machine}; Quantum Rosetta images are linux/amd64 only.",
            Exit.ENGINE,
            "wrong_architecture",
            hint="qrosetta start --allow-emulation",
            step="Start under emulation (results record it, and timings are not comparable):",
        )
    output.warn(
        f"starting on {system} {machine} under emulation; results of images built from this version on "
        "record it, and their timings are not comparable with linux/amd64 runs.",
        "emulation",
    )


def host_compose_env(system=None, machine=None, run=subprocess.run):
    """QROSETTA_HOST_OS and QROSETTA_HOST_ARCH for compose: this host's OS and native machine
    (an x86_64 Python under Rosetta reports arm64 here), which runners compare with their image's."""
    system = system or platform.system()
    machine = machine or platform.machine()
    if system == "Darwin" and machine.lower() == "x86_64":
        try:
            translated = run(
                ["sysctl", "-n", "sysctl.proc_translated"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            translated = ""
        if translated == "1":
            machine = "arm64"
    return {"QROSETTA_HOST_OS": system, "QROSETTA_HOST_ARCH": machine}


def set_up_env(ctx, engine, bind=None):
    """Put in the engine's environment the variables `start` gives compose besides the caller's:
    this host's OS and machine, the lifecycle token's path (start writes the token there), the
    bind address and the finished-job settings (`jobstore.resolve`). `status` sets them too, so
    `compose config --hash` gives there what it gives `start`; QROSETTA_GIT_SHA comes from
    `serve.git_sha_env`. Returns the finished-job settings."""
    jobs = jobstore.resolve(ctx.env, ctx.cfg)
    engine.env.update(jobstore.compose_env(jobs))
    engine.env.update(host_compose_env())
    engine.env[hostload.COMPOSE_VAR] = hostload.token_path(ctx.env)
    if bind:
        engine.env["QROSETTA_HTTP_BIND"] = bind
    return jobs


def _recreate_effect(stack, stale):
    """What recreating the running containers among `stale` does to runs in flight, or None."""
    replaced = [stack.services[s.service].id for s in stale if s.running]
    if not replaced:
        return None
    how = {frozenset({"image"}): " on new images", frozenset({"config"}): " with their new compose configuration"}
    kinds = frozenset(r for s in stale if s.running for r in s.reasons)
    return (
        f"recreating the containers of {', '.join(replaced)}{how.get(kinds, '')} stops them, and runs on them "
        "report a lost connection"
    )


def cmd_start(ctx):
    args = ctx.args
    check_host(args.allow_emulation)
    if modes.detect(ctx.opt("project_dir"), ctx.env, ctx.checkout).name == "installed":
        installed.require_published()
    cpu_quota, _ = quota.wanted(ctx)
    preflight.check(ctx, cpu_quota)
    hostload.ensure_token(ctx.env)
    _, engine, stack = open_stack(ctx, cpu_quota)
    quota.check_host(engine, cpu_quota)
    setting = quota.record(ctx.env, stack.name, cpu_quota, stack.cpu_override_sha256)
    if not cpu_quota:
        output.warn(quota.describe_off(setting.get("since")), "cpu_quota_off")
    bind = _bind(ctx)
    jobs = set_up_env(ctx, engine, bind)
    found = own.scan(engine, stack)
    serve.check_startable(engine, found)
    requested = serve.requested_services(stack, args.services, args.profile, ctx.cfg)
    services, missing, compose_env = serve.plan_start(engine, stack, requested, ctx.env)
    engine.env.update(compose_env)
    if missing:
        names = ", ".join(stack.services[s].id for s in missing)
        if stack.release:
            keys = " ".join(stack.services[s].id for s in missing)
            progress(
                f"Not started (no image): {names}. `qrosetta pull {keys}` pulls them; "
                "`qrosetta images load DIR` loads them from the release's image archives."
            )
        else:
            keys = " ".join(stack.services[s].id for s in missing)
            progress(f"Not started (no image): {names}. `qrosetta build {keys}` builds them.")
    running = {c.service for c in found.containers if c.running}
    adding = bool(running)
    to_start = [s for s in services if s not in running]
    hashes = serve.config_hashes(engine) if any(c.config_hash for c in found.containers) else None
    stale = serve.stale_containers(engine, stack, found, services, hashes)
    recreated = [s.service for s in stale]
    fresh_start = [s for s in to_start if s not in recreated]
    url = serve.stack_url(engine, stack) if adding else None
    if adding:
        effect = _recreate_effect(stack, stale) or "starting services now adds load beside their timed windows"
        guard.refuse_if_busy(ctx, url, "start", "--yes", args.yes, effect)
    if stale:
        progress("\n".join(serve.describe_stale(stack, stale)))
    ids = [stack.services[s].id for s in fresh_start]
    if args.detach:
        if stale:
            kind, stale_ids, gone = serve.stale_notice(stack, stale)
            with (
                hostload.notice(ctx, url, kind, stale_ids, expect_server_gone=gone),
                guard.engine_lock(ctx.env, "start"),
            ):
                serve.up(engine, recreated, adding, bind, recreate=True, stack=stack)
        with hostload.notice(ctx, url if fresh_start else None, "start", ids):
            if fresh_start:
                progress(
                    f"Starting {len(fresh_start)} services" + (" beside the running ones" if adding else "") + "..."
                )
                with guard.engine_lock(ctx.env, "start"):
                    serve.up(engine, fresh_start, adding, bind, stack=stack)
            elif not stale:
                progress("Every requested service is already running.")
            ready = serve.wait_ready(ctx, engine, stack, services)
        url = serve.announce_running(engine, stack)
        progress(jobstore.line(jobs))
        progress("`qrosetta stop` puts it on standby; `qrosetta remove` removes it.")
        result(layout.next_step("qrosetta selftest"))
        return Result(
            0,
            {
                "url": url,
                "started": [stack.services[s].id for s in to_start],
                "recreated": [stack.services[s].id for s in recreated],
                "recreations": [{"id": stack.services[s.service].id, "reasons": s.reasons} for s in stale],
                "not_started": [stack.services[s].id for s in missing],
                "ready": ready,
                "cpu_quota": quota.block(stack, ctx.env),
                "finished_jobs": jobstore.block(jobs),
            },
        )
    if adding:
        progress("Quantum Rosetta is already running; this terminal now controls it.")
    action = serve.exit_action(args.on_exit, ctx.env, ctx.tty, ctx.cfg.get("lifecycle", "on_exit"))
    server = serve.Server(
        engine,
        stack,
        action,
        fresh_start,
        {},
        tty=ctx.tty,
        adding=adding,
        lock=serve.lock_for(ctx.env),
        bind=bind,
        notice=_notices(ctx, engine, stack),
        stale=stale,
        jobs_line=jobstore.line(jobs),
    )
    return Result(server.run(), None)


def _notices(ctx, engine, stack):
    """A factory of host-load notices for the stack's server, found when each one begins."""
    return lambda kind, services=None, gone=False: hostload.notice(
        ctx, serve.stack_url(engine, stack), kind, services, expect_server_gone=gone
    )


def cmd_stop(ctx):
    _, engine, stack = open_stack(ctx)
    found = own.scan(engine, stack)
    url = None
    if any(c.running for c in found.containers):
        url = serve.stack_url(engine, stack)
        guard.refuse_if_busy(
            ctx,
            url,
            "stop",
            "--force",
            ctx.args.force,
            "stopping now ends them, and their runs report a lost connection",
        )
    with guard.engine_lock(ctx.env, "stop"), hostload.notice(ctx, url, "stop", expect_server_gone=True):
        left = actions.stop_stack(engine, stack)
    actions.report_left(left)
    return Result(0, {"stopped": True})


def cmd_remove(ctx):
    args = ctx.args
    _, engine, stack = open_stack(ctx)
    found = own.scan(engine, stack)
    url = None
    if any(c.running for c in found.containers):
        url = serve.stack_url(engine, stack)
        guard.refuse_if_busy(
            ctx, url, "remove", "--force", args.force, "removing now ends them, and their runs report a lost connection"
        )
    everything = bool(getattr(args, "all", False))
    with guard.engine_lock(ctx.env, "remove"), hostload.notice(ctx, url, "remove", expect_server_gone=True):
        removed = actions.remove_stack(
            engine,
            stack,
            images=args.images,
            data=args.data,
            confirm=args.confirm,
            tty=ctx.tty,
            ask=lambda q: output.prompt(q, stdin=ctx.stdin),
            everything=everything,
        )
    return Result(
        0, {"images": args.images or everything, "data": args.data or everything, "all": everything, "removed": removed}
    )


def cmd_status(ctx):
    mode, engine, stack = open_stack(ctx)
    jobs = set_up_env(ctx, engine, ctx.cfg.get("lifecycle", "bind"))
    from qrosetta_cli.stack.status import status

    return Result(0, status(ctx, engine, stack, mode, jobs))


def cmd_logs(ctx):
    _, engine, stack = open_stack(ctx)
    args = ctx.args
    extra = ([] if args.no_follow else ["-f"]) + ([stack.resolve_service(args.service)] if args.service else [])
    try:
        code = engine.spawn(["logs", "--tail", str(args.tail), *extra], own_session=False).wait()
    except KeyboardInterrupt:
        return Result(int(Exit.SIGINT), None)
    if code != 0:
        raise CliError(
            f"`{engine.name} compose logs` exited with {code}.", Exit.ENGINE, "engine_error", hint="qrosetta status"
        )
    return Result(0, None)


def cmd_build(ctx):
    args = ctx.args
    _, engine, stack = open_stack(ctx)
    script = os.path.join(stack.project_dir, "scripts", "safe_boot.sh")
    if not os.path.isfile(script):
        raise CliError(
            f"Building needs a source checkout with scripts/safe_boot.sh; {stack.project_dir} has none.",
            Exit.ENGINE,
            "no_build_script",
            hint="qrosetta --project-dir DIR build, with DIR a checkout",
        )
    requested = serve.requested_services(stack, args.services, args.profile, ctx.cfg) or []
    if args.profile:
        requested += [c for c in stack.core_services() if c not in requested]
    found = own.scan(engine, stack)
    url = None
    if any(c.running for c in found.containers):
        url = serve.stack_url(engine, stack)
        guard.refuse_if_busy(
            ctx, url, "build", "--yes", args.yes, "a build now loads the host beside their timed windows"
        )
    env = dict(
        engine.env,
        QR_BUILD_ONLY="1",
        QR_ENGINE=engine.name,
        QR_BUILD_SERVICES=" ".join(requested),
        COMPOSE_PROJECT_NAME=engine.project,
        COMPOSE_FILE=os.pathsep.join(engine.files),
    )
    try:
        with (
            guard.engine_lock(ctx.env, "build"),
            hostload.notice(ctx, url, "build", [stack.services[s].id for s in requested]),
        ):
            code = subprocess.call(["bash", script], env=env, cwd=stack.project_dir, timeout=TRANSFER_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        raise timed_out(["bash", script], TRANSFER_TIMEOUT_SEC) from None
    except KeyboardInterrupt:
        progress("qrosetta: interrupted. `qrosetta status` shows what is running.")
        return Result(int(Exit.SIGINT), None)
    if code != 0:
        raise CliError(f"scripts/safe_boot.sh exited with {code}.", Exit.ENGINE, "build_failed", hint="qrosetta doctor")
    built = requested or [
        s for s in stack.services if s in stack.core_services() or "full" in stack.services[s].profiles
    ]
    images = st.find_images(engine, [stack.image_for(s) for s in built])
    unknown = [
        stack.services[s].id
        for s in built
        if stack.image_for(s) in images and images[stack.image_for(s)].git_sha == "unknown"
    ]
    if unknown:
        raise CliError(
            f"Built images without a baked commit: {', '.join(unknown)}. The engine reused cached "
            "layers built without QROSETTA_GIT_SHA.",
            Exit.ENGINE,
            "build_commit_unknown",
            hint=f"{engine.name} rmi {' '.join(stack.image_for(stack.resolve_service(k)) for k in unknown)} "
            f"&& qrosetta build {' '.join(unknown)}",
        )
    for s in built:
        img = images.get(stack.image_for(s))
        if img and img.git_sha.endswith("-dirty"):
            output.warn(f"{stack.services[s].id} was built from {img.git_sha}: source not identifiable.", "dirty_build")
    return Result(0, {"built": [stack.services[s].id for s in built if stack.image_for(s) in images]})


def _server_profiles(ctx):
    """Profiles from the server's /runners and /compilers `profiles` fields (S7)."""
    transport = ctx.transport()
    names: dict = {}
    for path in ("/runners", "/compilers"):
        resp = transport.request("GET", path, timeout=30)
        data = resp.json()
        if resp.status != 200 or not isinstance(data, list):
            raise CliError(
                f"GET {path} answered HTTP {resp.status}.",
                Exit.INCOMPATIBLE,
                "not_quantum_rosetta",
                hint="qrosetta config show",
                http_status=resp.status,
            )
        for entry in data:
            if not isinstance(entry, dict) or "profiles" not in entry:
                raise CliError(
                    f"{transport.url} does not publish profiles in GET {path}; it needs platform 2.0.0.",
                    Exit.INCOMPATIBLE,
                    "feature_missing",
                    hint="qrosetta profiles (in a checkout, from its compose labels)",
                )
            for name in entry.get("profiles") or []:
                names.setdefault(name, []).append(entry["id"])
    return [{"name": n, "source": "server", "experimental": False, "services": ids} for n, ids in names.items()]


def cmd_profiles(ctx):
    mode = modes.detect(ctx.opt("project_dir"), ctx.env, ctx.checkout)
    if ctx.opt("server") or mode.name != "checkout":
        rows = _server_profiles(ctx)
    else:
        _, engine, stack = open_stack(ctx)
        rows = profiles.listing(stack, ctx.cfg)
    width = max([len(r["name"]) for r in rows] + [7])
    result(f"{'PROFILE':<{width}}  SOURCE          SERVICES (core nginx and api always added)")
    for r in rows:
        tag = " (experimental)" if r["experimental"] else ""
        result(f"{r['name']:<{width}}  {r['source']:<14}  {', '.join(r['services']) or '-'}{tag}")
    if not rows:
        progress("The compose file carries no org.qrosetta.profiles labels.")
    return Result(0, {"profiles": rows})


def cmd_doctor(ctx):
    from qrosetta_cli.stack.doctor import cmd_doctor as run

    return run(ctx)
