"""Exit codes (spec Q4), their priority, and CliError, the one way a command reports a problem."""

from enum import IntEnum


class Exit(IntEnum):
    OK = 0
    INTERNAL = 1
    USAGE = 2
    DISAGREEMENT = 3
    RUNS_WITHOUT_OUTPUT = 4
    JOB_FAILED = 5
    JOB_CANCELLED = 6
    WAIT_TIMEOUT = 7
    NOT_ESTABLISHED = 8
    SELFTEST_FAILED = 9
    REFUSED = 10
    UNREACHABLE = 11
    INCOMPATIBLE = 12
    AUTH = 13
    NOT_FOUND = 14
    BUSY = 15
    ENGINE = 16
    CHECKS_FAILED = 17
    SIGHUP = 129
    SIGINT = 130
    SIGPIPE = 141
    SIGTERM = 143


NAMES = {code: code.name.lower() for code in Exit}
NAMES.update({Exit.SIGHUP: "sighup", Exit.SIGINT: "sigint", Exit.SIGPIPE: "sigpipe", Exit.SIGTERM: "sigterm"})

PRIORITY = (
    Exit.INTERNAL,
    Exit.USAGE,
    Exit.INCOMPATIBLE,
    Exit.UNREACHABLE,
    Exit.AUTH,
    Exit.NOT_FOUND,
    Exit.REFUSED,
    Exit.BUSY,
    Exit.ENGINE,
    Exit.CHECKS_FAILED,
    Exit.SELFTEST_FAILED,
    Exit.JOB_FAILED,
    Exit.JOB_CANCELLED,
    Exit.WAIT_TIMEOUT,
    Exit.DISAGREEMENT,
    Exit.NOT_ESTABLISHED,
    Exit.RUNS_WITHOUT_OUTPUT,
    Exit.OK,
)
SIGNALS = (Exit.SIGHUP, Exit.SIGINT, Exit.SIGPIPE, Exit.SIGTERM)


def name(code):
    """The exit code's name; unknown codes in 10-63 are errors."""
    try:
        return NAMES[Exit(code)]
    except ValueError:
        return "error" if 10 <= code <= 63 else "unknown"


def worst(codes):
    """The code to exit with when several apply: signals first, then the Q4 priority order;
    an unlisted code ranks with the errors."""
    codes = list(codes) or [Exit.OK]
    for sig in SIGNALS:
        if sig in codes:
            return sig
    rank = {c: i for i, c in enumerate(PRIORITY)}
    return min(codes, key=lambda c: rank.get(c, PRIORITY.index(Exit.REFUSED) + 0.5))


class CliError(Exception):
    """A problem reported as one message, with the exit code, a snake_case reason and the
    command (or file to edit) printed last."""

    def __init__(self, message, code=Exit.ENGINE, reason=None, hint=None, http_status=None, detail=None, data=None):
        super().__init__(message)
        self.data = data
        self.message = message
        self.code = Exit(code)
        self.reason = reason or NAMES[self.code]
        self.hint = hint
        self.http_status = http_status
        self.detail = detail

    def as_dict(self):
        return {
            "code": name(self.code),
            "reason": self.reason,
            "message": self.message,
            "hint": self.hint,
            "http_status": self.http_status,
            "detail": self.detail,
        }


def usage(message, hint=None, reason="usage"):
    return CliError(message, Exit.USAGE, reason, hint)
