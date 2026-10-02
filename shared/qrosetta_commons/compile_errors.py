"""Failures a compile-only adapter raises on purpose; their messages describe the circuit or
the check, never the server, so a run's share link may show them."""


class CompileRefused(ValueError):
    """The adapter refuses the input before compiling it."""


class OutputRejected(ValueError):
    """The compiler's output failed the adapter's check and is not reported."""
