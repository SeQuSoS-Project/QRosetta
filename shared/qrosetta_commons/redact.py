"""Removal of absolute file-system paths from error text that leaves the server."""

import re

PATH_PLACEHOLDER = "<path>"

_ABSOLUTE_PATH = re.compile(r"(?<![\w.:/~-])/(?:[\w.@+~-]+/)+[\w.@+~-]*")


def strip_absolute_paths(text: str) -> str:
    """``text`` with every absolute POSIX path of two or more components (``/a/b``) replaced by
    ``<path>``. URLs, ratios such as ``pi/2`` and relative paths are kept."""
    return _ABSOLUTE_PATH.sub(PATH_PLACEHOLDER, str(text))
