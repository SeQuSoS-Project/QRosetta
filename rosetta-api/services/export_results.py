"""results.json of an RO-Crate export: the report with statevectors kept or replaced by a
digest, the circuit texts the crate stores as files removed, and ``report_source`` set by the
export route. Written as the text ``json.dumps(..., indent=2, ensure_ascii=False)`` gives, in
chunks, holding one batch task's report at a time when the tasks are read from disk."""

import copy
import hashlib
import json
from typing import Any, Callable, Iterable, Iterator, Optional

from services.experiment_artifacts import sha256 as _json_sha256
from services.export_compiled import strip_compiled_text
from services.report_filters import (
    OMITTED_FOR_DISPLAY,
    fingerprint_statevectors,
    is_display_placeholder,
    remove_statevectors,
)

ENCODER = json.JSONEncoder(indent=2, ensure_ascii=False)
_TASK_INDENT = "\n    "


def _fingerprint(report: dict) -> None:
    fingerprint_statevectors(report, _json_sha256)


def _clean(report: dict) -> None:
    for r in report.get("raw_results", []) or []:
        if not isinstance(r, dict):
            continue
        r.pop("transpiled_qasm", None)
        if "statevector" in r and is_display_placeholder(r):
            r["statevector"] = None
            r[OMITTED_FOR_DISPLAY] = True
    for record in report.get("dispatched_circuits", []) or []:
        if isinstance(record, dict):
            record.pop("qasm", None)
    strip_compiled_text(report)


def results_data(results: dict, include_statevectors: bool, report_source: str) -> dict:
    """results.json content of a whole report: statevectors per ``include_statevectors``
    (else a sha256 and length per result), display placeholders nulled and flagged, circuit
    texts written as separate files removed, and ``report_source`` set."""
    data = copy.deepcopy(results)
    if not include_statevectors:
        _fingerprint(data)
        for task_result in data.get("benchmark_summary", []) or []:
            if isinstance(task_result, dict):
                _fingerprint(task_result)
        data = remove_statevectors(data)
    _clean(data)
    for task_result in data.get("benchmark_summary", []) or []:
        if isinstance(task_result, dict):
            _clean(task_result)
            task_result.pop("report_source", None)
    data["report_source"] = report_source
    return data


def results_task(task: Any, include_statevectors: bool) -> Any:
    """The results.json copy of one ``benchmark_summary`` entry, as ``results_data`` makes it."""
    data = copy.deepcopy(task)
    if not include_statevectors:
        if isinstance(data, dict):
            _fingerprint(data)
        data = remove_statevectors(data)
    if isinstance(data, dict):
        _clean(data)
        data.pop("report_source", None)
    return data


def _batch_chunks(results: dict, include_statevectors: bool, report_source: str,
                  load_task: Callable[[int], Any]) -> Iterator[str]:
    """results.json text of a batch report whose task ``i`` is ``load_task(i)``."""
    count = len(results["benchmark_summary"])
    top = results_data({**results, "benchmark_summary": []}, include_statevectors, report_source)
    yield "{"
    for i, (key, value) in enumerate(top.items()):
        item = ENCODER.encode({key: value})[1:-2]
        if i:
            yield ","
        if key != "benchmark_summary" or not count:
            yield item
            continue
        yield item[:-2] + "["
        for j in range(count):
            yield _TASK_INDENT if j == 0 else "," + _TASK_INDENT
            task = results_task(load_task(j), include_statevectors)
            for chunk in ENCODER.iterencode(task):
                yield chunk.replace("\n", _TASK_INDENT)
            del task
        yield "\n  ]"
    yield "\n}"


def results_json_source(results: dict, include_statevectors: bool, report_source: str,
                        load_task: Optional[Callable[[int], Any]] = None
                        ) -> Callable[[], Iterator[str]]:
    """A function returning the results.json text in chunks, each call from the start. With
    ``load_task``, ``results['benchmark_summary']`` (a list) stands for the tasks
    ``load_task(i)`` returns, read again on each call; otherwise the content is built once."""
    if load_task is not None and isinstance(results.get("benchmark_summary"), list):
        return lambda: _batch_chunks(results, include_statevectors, report_source, load_task)
    data = results_data(results, include_statevectors, report_source)
    return lambda: ENCODER.iterencode(data)


def encoded(chunks: Iterable[str], size: int = 1 << 20) -> Iterator[bytes]:
    """UTF-8 bytes of the text ``chunks``, joined into pieces of at least ``size`` characters
    (the last one shorter)."""
    buf, n = [], 0
    for chunk in chunks:
        buf.append(chunk)
        n += len(chunk)
        if n >= size:
            yield "".join(buf).encode("utf-8")
            buf, n = [], 0
    if buf:
        yield "".join(buf).encode("utf-8")


def digest(pieces: Iterable[bytes]) -> tuple:
    """(sha256 hex, total length) of the byte ``pieces``."""
    h, n = hashlib.sha256(), 0
    for piece in pieces:
        h.update(piece)
        n += len(piece)
    return h.hexdigest(), n
