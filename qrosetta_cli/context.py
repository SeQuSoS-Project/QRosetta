"""What every command receives: parsed arguments, environment, config, terminal, and factories
for the engine and the transport that tests replace."""

import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Result:
    """A command's outcome: exit code, the envelope's data, its `outcome` block (the --fail-on
    rule version, names and matches of a run), and a payload schema other than the command's."""

    code: int = 0
    data: Any = None
    outcome: dict | None = None
    schema: str | None = None


@dataclass
class Context:
    args: Any
    env: dict
    cfg: Any
    checkout: str | None = None
    engine_factory: Any = None
    transport_factory: Any = None
    stdin: Any = None
    tty: bool | None = None
    server_block: dict | None = None
    _server: Any = field(default=None, repr=False)

    def __post_init__(self):
        if self.stdin is None:
            self.stdin = sys.stdin
        if self.tty is None:
            try:
                self.tty = bool(self.stdin.isatty())
            except (AttributeError, ValueError, OSError):
                self.tty = False

    def opt(self, name, default=None):
        return getattr(self.args, name, default)

    def server(self):
        from qrosetta_cli.client import servers

        if self._server is None:
            self._server = servers.select(self.opt("server"), self.env, self.cfg)
            self.server_block = self._server.block()
        return self._server

    def transport(self, with_token=False, timeout=None, server=None):
        from qrosetta_cli.client import servers

        server = server or self.server()
        token = servers.token_for(server, self.cfg, self.env) if with_token else None
        factory = self.transport_factory or servers.transport
        return factory(server, token, timeout)

    def note_handshake(self, block):
        """Record the server's version and levels in the envelope's server block."""
        if self._server is not None:
            self.server_block = self._server.block(block)
