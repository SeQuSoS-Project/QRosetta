# Peers whose last X-Forwarded-For entry names the client (QROSETTA_TRUSTED_PROXIES).

import ipaddress
import socket
import threading
import time

ANY_PEER = "*"
DEFAULTS = {"local": "nginx", "kubernetes": ANY_PEER}
RESOLVE_EVERY_SEC = 5.0
RESOLVE_WAIT_SEC = 0.5


def default_spec(execution_mode: str) -> str:
    """The list used when QROSETTA_TRUSTED_PROXIES is unset: the compose service name of nginx in
    local mode; any peer in Kubernetes mode, where the router's addresses are not fixed."""
    return DEFAULTS.get(execution_mode, "")


def peer_address(peer):
    """``peer`` as an address (an IPv4-mapped IPv6 address as IPv4, a zone index dropped), or
    None when it is not an IP address."""
    if not peer:
        return None
    try:
        address = ipaddress.ip_address(str(peer).split("%", 1)[0])
    except ValueError:
        return None
    mapped = getattr(address, "ipv4_mapped", None)
    return mapped or address


def resolve_host(host: str) -> frozenset:
    """Addresses ``host`` resolves to; empty when it does not resolve."""
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return frozenset()
    found = (peer_address(info[4][0]) for info in infos)
    return frozenset(a for a in found if a is not None)


class TrustedProxies:
    """Comma-separated entries: ``*`` (any peer), an IP address, a CIDR network or a host name.
    Host names are resolved when a peer outside the list sends X-Forwarded-For, at most once per
    RESOLVE_EVERY_SEC, in a thread the caller waits for at most RESOLVE_WAIT_SEC; a proxy whose
    address changed (a recreated nginx container) is trusted again from the next resolution."""

    def __init__(self, spec: str, resolve=resolve_host):
        self.any_peer = False
        self.networks = []
        self.hosts = []
        for raw in (spec or "").split(","):
            entry = raw.strip()
            if not entry:
                continue
            if entry == ANY_PEER:
                self.any_peer = True
                continue
            try:
                self.networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                self.hosts.append(entry)
        self._resolve = resolve
        self._resolved = frozenset()
        self._attempted_at = None
        self._lock = threading.Lock()

    def trusts(self, peer) -> bool:
        if self.any_peer:
            return True
        address = peer_address(peer)
        if address is None:
            return False
        if any(address in network for network in self.networks):
            return True
        if not self.hosts:
            return False
        if address not in self._resolved:
            self._refresh()
        return address in self._resolved

    def _refresh(self) -> None:
        now = time.monotonic()
        with self._lock:
            if self._attempted_at is not None and now - self._attempted_at < RESOLVE_EVERY_SEC:
                return
            self._attempted_at = now
        done = threading.Event()

        def work():
            found = set()
            for host in self.hosts:
                found |= self._resolve(host)
            self._resolved = frozenset(found)
            done.set()

        threading.Thread(target=work, name="trusted-proxies", daemon=True).start()
        done.wait(RESOLVE_WAIT_SEC)
