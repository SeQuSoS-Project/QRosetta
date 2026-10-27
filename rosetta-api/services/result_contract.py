"""Checks on what a runner or compiler returns (HTTP body or S3 object) before the API uses it."""

import json
import numbers

from qrosetta_commons.helpers import UNMEASURED_METRICS, get_logger

logger = get_logger("rosetta-api")

MAX_RESULT_BYTES = 256 * 1024 * 1024
MAX_RESULT_DEPTH = 32

_NUMERIC_FIELDS = tuple(UNMEASURED_METRICS) + ("queue_wait_sec",)
_TEXT_FIELDS = ("simulator", "compiler", "transpiled_qasm", "refusal", "refusal_kind")
_REQUIRED = {"run": ("statevector", str), "run_measured": ("counts", dict),
             "compile": ("transpiled_qasm", str)}


class ResultContractError(ValueError):
    """A response that does not follow the result contract; the message names the rule, never
    the response's content."""


def _depth_exceeds(value, limit: int) -> bool:
    stack = [(value, 1)]
    while stack:
        node, level = stack.pop()
        if isinstance(node, (dict, list)):
            if level > limit:
                return True
            stack.extend((child, level + 1) for child in (node.values() if isinstance(node, dict) else node))
    return False


def _reject_constant(name):
    raise ResultContractError(f"it holds {name}, which JSON does not allow")


def _number_or_none(value) -> bool:
    return value is None or (isinstance(value, numbers.Real) and not isinstance(value, bool))


def check_result(result, endpoint: str | None = None) -> dict:
    """``result`` when it is a result object for ``endpoint`` (``run``, ``run_measured``,
    ``compile``; None checks only what every endpoint shares); else ResultContractError."""
    if not isinstance(result, dict):
        raise ResultContractError("it is not a JSON object")
    if _depth_exceeds(result, MAX_RESULT_DEPTH):
        raise ResultContractError(f"it nests more than {MAX_RESULT_DEPTH} levels deep")
    error = result.get("error")
    if error is not None and not isinstance(error, str):
        raise ResultContractError("its error field is not text")
    for field in _TEXT_FIELDS:
        if result.get(field) is not None and not isinstance(result[field], str):
            raise ResultContractError(f"its {field} field is not text")
    for field in _NUMERIC_FIELDS:
        if field in result and not _number_or_none(result[field]):
            raise ResultContractError(f"its {field} field is not a number")
    notes = result.get("preprocessing_applied")
    if notes is not None and not (isinstance(notes, list) and all(isinstance(n, str) for n in notes)):
        raise ResultContractError("its preprocessing_applied field is not a list of text")
    if error:
        return result
    required = _REQUIRED.get(endpoint)
    if required is not None:
        field, kind = required
        if not isinstance(result.get(field), kind):
            raise ResultContractError(f"it has neither an error nor a valid {field} field")
    counts = result.get("counts")
    if counts is not None and not (
            isinstance(counts, dict)
            and all(isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v >= 0
                    for k, v in counts.items())):
        raise ResultContractError("its counts field is not a map of bit strings to shot counts")
    return result


def parse_result(body: bytes, endpoint: str | None = None) -> dict:
    """Parse and check one response body; ResultContractError when it is too large, not JSON or
    not a result for ``endpoint``."""
    if len(body) > MAX_RESULT_BYTES:
        raise ResultContractError(f"it is larger than {MAX_RESULT_BYTES // (1024 * 1024)} MiB")
    try:
        value = json.loads(body, parse_constant=_reject_constant)
    except ResultContractError:
        raise
    except RecursionError:
        raise ResultContractError(f"it nests more than {MAX_RESULT_DEPTH} levels deep") from None
    except ValueError:
        raise ResultContractError("it is not valid JSON") from None
    return check_result(value, endpoint)


def endpoint_of(url: str) -> str | None:
    """``run``, ``run_measured`` or ``compile`` from a dispatch URL; None for anything else."""
    tail = str(url).rstrip("/").rsplit("/", 1)[-1]
    return tail if tail in _REQUIRED else None


def invalid_response_message(name: str, kind: str, reason: str) -> str:
    """The error recorded for a run whose response broke the contract."""
    return (f"INVALID RESPONSE: the {name} {kind} returned a response the API cannot use "
            f"({reason}). Server operators can see details in the API logs.")


def log_rejected(name: str, reason: str) -> None:
    """Log a rejected response with the job id it belongs to, when known."""
    from services.job_manager import JOB_ID
    logger.error(f"Response of {name} rejected (job {JOB_ID.get() or 'unknown'}): {reason}")
