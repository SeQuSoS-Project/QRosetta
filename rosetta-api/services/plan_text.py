"""Text rules the run planner shares with the page: printable names, circuit names without a
qubit-count suffix, integer reading of qubit counts, and the byte length of a request body as
a browser's JSON.stringify writes it."""

import json
import math
import re
import unicodedata

from schemas.benchmark import _BLANK_SYMBOLS, _INVISIBLE_ALLOWED, _REFUSED_IN_NAMES, _in_ranges

UNDEFINED = object()

_WS = "\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_WS_SET = frozenset("\t\n\v\f\r \u00a0\u1680\u2028\u2029\u202f\u205f\u3000\ufeff"
                    + "".join(chr(c) for c in range(0x2000, 0x200B)))
_QUBIT_SUFFIX = re.compile(rf"(?:[{_WS}]*\([0-9]+q\))+[{_WS}]*\Z")


def js_trim(text: str) -> str:
    """``text`` without leading and trailing whitespace as JavaScript's trim() sees it."""
    start, end = 0, len(text)
    while start < end and text[start] in _WS_SET:
        start += 1
    while end > start and text[end - 1] in _WS_SET:
        end -= 1
    return text[start:end]


def js_truthy(value) -> bool:
    if value is UNDEFINED or value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0 and not (isinstance(value, float) and math.isnan(value))
    if isinstance(value, str):
        return value != ""
    return True


def js_number_text(value) -> str:
    """A number as JavaScript's String() and JSON.stringify write it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and abs(value) < 2 ** 53:
        return str(value)
    value = float(value)
    if not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if value == 0:
        return "0"
    if value == int(value) and abs(value) < 2 ** 53:
        return str(int(value))
    sign = "-" if value < 0 else ""
    mantissa, _, exp = repr(abs(value)).partition("e")
    whole, _, frac = mantissa.partition(".")
    digits = whole + frac
    point = len(whole) + (int(exp) if exp else 0)
    lead = len(digits) - len(digits.lstrip("0"))
    digits, point = digits[lead:].rstrip("0"), point - lead
    k, n = len(digits), point
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    rest = "." + digits[1:] if k > 1 else ""
    return f"{sign}{digits[0]}{rest}e{'+' if e >= 0 else '-'}{abs(e)}"


def js_string(value) -> str:
    """``String(value)`` in JavaScript, for JSON values (and UNDEFINED)."""
    if value is UNDEFINED:
        return "undefined"
    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    if isinstance(value, (bool, int, float)):
        return js_number_text(value)
    if isinstance(value, list):
        return ",".join("" if v is None else js_string(v) for v in value)
    return "[object Object]"


def js_parse_int_or_zero(value) -> int:
    """``parseInt(value) || 0`` in JavaScript."""
    text = js_string(value)
    i = 0
    while i < len(text) and text[i] in _WS_SET:
        i += 1
    sign = 1
    if i < len(text) and text[i] in "+-":
        sign = -1 if text[i] == "-" else 1
        i += 1
    base, digits = 10, "0123456789"
    if text[i:i + 2] in ("0x", "0X"):
        base, digits, i = 16, "0123456789abcdefABCDEF", i + 2
    j = i
    while j < len(text) and text[j] in digits:
        j += 1
    if j == i:
        return 0
    return sign * int(text[i:j], base) or 0


def _refused(ch: str) -> bool:
    return _in_ranges(ord(ch), _REFUSED_IN_NAMES)


def is_blank_label(text: str) -> bool:
    """request_limits.js isBlankName."""
    return all(ch in _WS_SET or _in_ranges(ord(ch), _INVISIBLE_ALLOWED + _BLANK_SYMBOLS)
               or unicodedata.category(ch) in ("Mn", "Me", "Cf") for ch in text)


def printable_label(value, max_length: int) -> str:
    """request_limits.js printableLabel: refused characters removed, trimmed, cut to
    ``max_length`` characters; '' when nothing visible is left."""
    text = "" if value is UNDEFINED or value is None else js_string(value)
    clean = js_trim("".join(ch for ch in text if not _refused(ch)))
    if is_blank_label(clean):
        return ""
    return clean if len(clean) <= max_length else js_trim(clean[:max_length])


def bare_circuit_name(value) -> str:
    """run_plan.js bareCircuitName: the name without a trailing ' (4q)'."""
    text = "" if value is UNDEFINED or value is None else js_string(value)
    return js_trim(_QUBIT_SUFFIX.sub("", text, count=1))


_SURROGATE = re.compile("[\ud800-\udfff]")


def _json_string(text: str, out: list) -> None:
    if not _SURROGATE.search(text):
        out.append(json.dumps(text, ensure_ascii=False))
        return
    out.append('"')
    for ch in text:
        cp = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch in "\b\f\n\r\t":
            out.append({"\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch])
        elif cp < 0x20 or 0xD800 <= cp <= 0xDFFF:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(ch)
    out.append('"')


def _json(value, out: list) -> None:
    if value is None:
        out.append("null")
    elif isinstance(value, (bool, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            out.append("null")
        else:
            out.append(js_number_text(value))
    elif isinstance(value, str):
        _json_string(value, out)
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for i, item in enumerate(value):
            if i:
                out.append(",")
            _json(None if item is UNDEFINED else item, out)
        out.append("]")
    elif isinstance(value, dict):
        out.append("{")
        first = True
        for key, item in value.items():
            if item is UNDEFINED:
                continue
            if not first:
                out.append(",")
            first = False
            _json_string(str(key), out)
            out.append(":")
            _json(item, out)
        out.append("}")
    else:
        raise TypeError(f"not a JSON value: {type(value).__name__}")


def js_json(value) -> str:
    """``JSON.stringify(value)``."""
    out = []
    _json(value, out)
    return "".join(out)


def js_json_bytes(value) -> int:
    """UTF-8 bytes of ``JSON.stringify(value)``: request_limits.js jsonBytes."""
    return len(js_json(value).encode("utf-8"))
