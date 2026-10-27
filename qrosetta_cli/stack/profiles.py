"""Profiles (spec §6.9): built-in ones from the compose labels org.qrosetta.profiles (checkout
mode), user profiles from the config file (experimental). Core services are always added by
the commands that start or build a profile."""

from qrosetta_cli import output
from qrosetta_cli.config import RESERVED_PROFILES
from qrosetta_cli.errors import usage
from qrosetta_cli.stack import project as st

BUILT_IN = ("minimal", "cpu", "gpu", "compilers", "full")


def built_in(stack):
    """Profile name -> member compose services, from the compose labels."""
    names = []
    for svc in stack.services.values():
        names += [p for p in svc.profiles if p not in names]
    order = [n for n in BUILT_IN if n in names] + sorted(n for n in names if n not in BUILT_IN)
    return {name: st.profile_members(stack, name) for name in order}


def user_profiles(cfg):
    return (cfg.get("profiles") or {}) if cfg is not None else {}


def _user_members(stack, name, cfg, seen):
    if name in seen:
        raise usage(f"Profile {name!r} extends itself through {' -> '.join(seen)}.", hint=f"edit {cfg.path}",
                    reason="profile_cycle")
    table = user_profiles(cfg)[name]
    base = table.get("extends")
    chosen = members(stack, base, cfg, seen + [name]) if base else []
    for key in table.get("services") or []:
        service = stack.resolve_service(key)
        if service not in chosen:
            chosen.append(service)
    return chosen


def members(stack, name, cfg=None, seen=None):
    """Compose services of a built-in or user profile."""
    builtin = built_in(stack)
    if name in builtin:
        return list(builtin[name])
    if name in user_profiles(cfg) and name not in RESERVED_PROFILES:
        output.experimental("user profiles")
        return _user_members(stack, name, cfg, seen or [])
    known = list(builtin) + sorted(user_profiles(cfg))
    raise usage(f"Unknown profile {name!r}. Profiles: {', '.join(known) or 'none'}.", hint="qrosetta profiles",
                reason="unknown_profile")


def listing(stack, cfg):
    """[{name, source, services: [service keys]}] for the profiles command."""
    rows = [{"name": name, "source": "compose labels", "experimental": False,
             "services": sorted(stack.services[s].id for s in svcs)} for name, svcs in built_in(stack).items()]
    for name in sorted(user_profiles(cfg)):
        svcs = members(stack, name, cfg)
        rows.append({"name": name, "source": "config", "experimental": True,
                     "services": sorted(stack.services[s].id for s in svcs)})
    return rows
