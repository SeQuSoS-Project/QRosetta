"""The lifecycle commands: start, stop, remove, status, logs, build, profiles, doctor."""

import os
import platform
import subprocess

from qrosetta_cli import mode as modes, output
from qrosetta_cli.context import Result
from qrosetta_cli.errors import CliError, Exit
from qrosetta_cli.output import progress, result
from qrosetta_cli.stack import actions, guard, hostload, installed, profiles, serve
from qrosetta_cli.stack import ownership as own
from qrosetta_cli.stack import project as st
from qrosetta_cli.stack.engine import Engine, choose_engine


def open_stack(ctx):
    """(mode, engine, stack) for the checkout's compose project, or in installed mode for the
    compose file generated from the release manifest."""
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
    engine.check_compose()
    stack = st.load_stack(engine)
    stack.release = release
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
        raise CliError(f"This host is {system} {machine}; Quantum Rosetta images are linux/amd64 only.", Exit.ENGINE,
                       "wrong_architecture", hint="qrosetta start --allow-emulation")
    output.warn(f"starting on {system} {machine} under emulation; results do not record it until release 2.0.0, "
                "so their timings are not comparable with linux/amd64 runs.", "emulation")


def cmd_start(ctx):
    args = ctx.args
    check_host(args.allow_emulation)
    if modes.detect(ctx.opt("project_dir"), ctx.env, ctx.checkout).name == "installed":
        installed.require_published()
    hostload.ensure_token(ctx.env)
    _, engine, stack = open_stack(ctx)
    if ctx.cfg.get("lifecycle", "cpu_quota") is False:
        output.warn("[lifecycle] cpu_quota = false is not applied by this version (the --no-cpu-quota override "
                    "arrives with release 2.0.0); the stack starts with its CPU quotas.", "cpu_quota_ignored")
    bind = _bind(ctx)
    if bind:
        engine.env["QROSETTA_HTTP_BIND"] = bind
    found = own.scan(engine, stack)
    serve.check_startable(engine, found)
    requested = serve.requested_services(stack, args.services, args.profile, ctx.cfg)
    services, missing, compose_env = serve.plan_start(engine, stack, requested, ctx.env)
    if missing:
        names = ", ".join(stack.services[s].id for s in missing)
        if stack.release:
            progress(f"Not started (no image): {names}. "
                     + "; ".join(f"`{engine.name} pull {stack.image_for(s)}`" for s in missing) + ".")
        else:
            keys = " ".join(stack.services[s].id for s in missing)
            progress(f"Not started (no image): {names}. `qrosetta build {keys}` builds them.")
    running = {c.service for c in found.containers if c.running}
    adding = bool(running)
    to_start = [s for s in services if s not in running]
    url = serve.stack_url(engine, stack) if adding else None
    if adding:
        guard.refuse_if_busy(ctx, url, "start", "--yes", args.yes,
                             "starting services now adds load beside their timed windows")
    engine.env.update(compose_env)
    ids = [stack.services[s].id for s in to_start]
    if args.detach:
        with hostload.notice(ctx, url if to_start else None, "start", ids):
            if to_start:
                progress(f"Starting {len(to_start)} services" + (" beside the running ones" if adding else "") + "...")
                with guard.engine_lock(ctx.env, "start"):
                    serve.up(engine, to_start, adding, bind)
            else:
                progress("Every requested service is already running.")
            ready = serve.wait_ready(ctx, engine, stack, services)
        url = serve.announce_running(engine, stack)
        progress("`qrosetta stop` puts it on standby; `qrosetta remove` removes it.")
        return Result(0, {"url": url, "started": [stack.services[s].id for s in to_start],
                          "not_started": [stack.services[s].id for s in missing], "ready": ready})
    if adding:
        progress("Quantum Rosetta is already running; this terminal now controls it.")
    action = serve.exit_action(args.on_exit, ctx.env, ctx.tty, ctx.cfg.get("lifecycle", "on_exit"))
    server = serve.Server(engine, stack, action, to_start, {}, tty=ctx.tty, adding=adding,
                          lock=serve.lock_for(ctx.env), bind=bind, notice=_notices(ctx, engine, stack))
    return Result(server.run(), None)


def _notices(ctx, engine, stack):
    """A factory of host-load notices for the stack's server, found when each one begins."""
    return lambda kind, services=None, gone=False: hostload.notice(
        ctx, serve.stack_url(engine, stack), kind, services, expect_server_gone=gone)


def cmd_stop(ctx):
    _, engine, stack = open_stack(ctx)
    found = own.scan(engine, stack)
    url = None
    if any(c.running for c in found.containers):
        url = serve.stack_url(engine, stack)
        guard.refuse_if_busy(ctx, url, "stop", "--force", ctx.args.force,
                             "stopping now ends them, and their runs report a lost connection")
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
        guard.refuse_if_busy(ctx, url, "remove", "--force", args.force,
                             "removing now ends them, and their runs report a lost connection")
    with guard.engine_lock(ctx.env, "remove"), hostload.notice(ctx, url, "remove", expect_server_gone=True):
        actions.remove_stack(engine, stack, images=args.images, data=args.data, confirm=args.confirm,
                             tty=ctx.tty, ask=lambda q: output.prompt(q, stdin=ctx.stdin))
    return Result(0, {"images": args.images, "data": args.data})


def cmd_status(ctx):
    mode, engine, stack = open_stack(ctx)
    from qrosetta_cli.stack.status import status
    return Result(0, status(ctx, engine, stack, mode))


def cmd_logs(ctx):
    _, engine, stack = open_stack(ctx)
    args = ctx.args
    extra = ([] if args.no_follow else ["-f"]) + ([stack.resolve_service(args.service)] if args.service else [])
    try:
        code = engine.spawn(["logs", "--tail", str(args.tail), *extra], own_session=False).wait()
    except KeyboardInterrupt:
        return Result(int(Exit.SIGINT), None)
    if code != 0:
        raise CliError(f"`{engine.name} compose logs` exited with {code}.", Exit.ENGINE, "engine_error",
                       hint="qrosetta status")
    return Result(0, None)


def cmd_build(ctx):
    args = ctx.args
    _, engine, stack = open_stack(ctx)
    script = os.path.join(stack.project_dir, "scripts", "safe_boot.sh")
    if not os.path.isfile(script):
        raise CliError(f"Building needs a source checkout with scripts/safe_boot.sh; {stack.project_dir} has none.",
                       Exit.ENGINE, "no_build_script", hint="qrosetta --project-dir DIR build, with DIR a checkout")
    requested = serve.requested_services(stack, args.services, args.profile, ctx.cfg) or []
    if args.profile:
        requested += [c for c in stack.core_services() if c not in requested]
    found = own.scan(engine, stack)
    url = None
    if any(c.running for c in found.containers):
        url = serve.stack_url(engine, stack)
        guard.refuse_if_busy(ctx, url, "build", "--yes", args.yes,
                             "a build now loads the host beside their timed windows")
    env = dict(engine.env, QR_BUILD_ONLY="1", QR_ENGINE=engine.name, QR_BUILD_SERVICES=" ".join(requested),
               COMPOSE_PROJECT_NAME=engine.project, COMPOSE_FILE=os.pathsep.join(engine.files))
    try:
        with guard.engine_lock(ctx.env, "build"), hostload.notice(
                ctx, url, "build", [stack.services[s].id for s in requested]):
            code = subprocess.call(["bash", script], env=env, cwd=stack.project_dir)
    except KeyboardInterrupt:
        progress("qrosetta: interrupted. `qrosetta status` shows what is running.")
        return Result(int(Exit.SIGINT), None)
    if code != 0:
        raise CliError(f"scripts/safe_boot.sh exited with {code}.", Exit.ENGINE, "build_failed",
                       hint="qrosetta doctor")
    built = requested or [s for s in stack.services
                          if s in stack.core_services() or "full" in stack.services[s].profiles]
    images = st.find_images(engine, [stack.image_for(s) for s in built])
    unknown = [stack.services[s].id for s in built if stack.image_for(s) in images
               and images[stack.image_for(s)].git_sha == "unknown"]
    if unknown:
        raise CliError(f"Built images without a baked commit: {', '.join(unknown)}. The engine reused cached "
                       "layers built without QROSETTA_GIT_SHA.", Exit.ENGINE, "build_commit_unknown",
                       hint=f"{engine.name} rmi {' '.join(stack.image_for(stack.resolve_service(k)) for k in unknown)} "
                       f"&& qrosetta build {' '.join(unknown)}")
    for s in built:
        img = images.get(stack.image_for(s))
        if img and img.git_sha.endswith("-dirty"):
            output.warn(f"{stack.services[s].id} was built from {img.git_sha}: source not identifiable.", "dirty_build")
    return Result(0, {"built": [stack.services[s].id for s in built if stack.image_for(s) in images]})


def _server_profiles(ctx):
    """Profiles from the server's /runners and /compilers `profiles` fields (S7)."""
    transport = ctx.transport()
    names = {}
    for path in ("/runners", "/compilers"):
        resp = transport.request("GET", path, timeout=30)
        data = resp.json()
        if resp.status != 200 or not isinstance(data, list):
            raise CliError(f"GET {path} answered HTTP {resp.status}.", Exit.INCOMPATIBLE, "not_quantum_rosetta",
                           hint="qrosetta config show", http_status=resp.status)
        for entry in data:
            if not isinstance(entry, dict) or "profiles" not in entry:
                raise CliError(f"{transport.url} does not publish profiles in GET {path}; it needs platform 2.0.0.",
                               Exit.INCOMPATIBLE, "feature_missing",
                               hint="qrosetta profiles (in a checkout, from its compose labels)")
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
