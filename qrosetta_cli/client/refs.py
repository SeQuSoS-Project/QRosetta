"""Circuit references (spec §5): algorithm:ALGO:QUBITS[,seed=S], example:NAME, mqt:ALGO:QUBITS,
qasmbench:NAME, - (stdin) and file paths, each turned into the editor's text or a playlist item
through the server's own routes."""

import os
import re
from dataclasses import dataclass, field

from qrosetta_cli.errors import CliError, Exit, usage

SCHEME = re.compile(r"^([a-z][a-z0-9+.-]*):")
DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
KINDS = ("algorithm", "example", "mqt", "qasmbench")
ALGORITHM_KEYS = ("seed",)


@dataclass
class CircuitRef:
    kind: str
    token: str
    name: str = ""
    qubits: int = None
    params: dict = field(default_factory=dict)


def _int(text, token, what):
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise usage(
            f"{token}: {what} must be a whole number, not {text!r}.", hint="qrosetta run --help", reason="bad_reference"
        ) from None
    return value


def parse(token):
    """A CircuitRef for one command-line token."""
    if token == "-":
        return CircuitRef("stdin", token, name="stdin")
    m = SCHEME.match(token)
    if not m or DRIVE.match(token):
        base = os.path.basename(token)
        return CircuitRef("file", token, name=os.path.splitext(base)[0] or base)
    kind, rest = m.group(1), token[m.end() :]
    if kind not in KINDS:
        raise usage(
            f"unknown reference type {kind!r}; write ./{token} for a file.",
            hint="qrosetta run --help",
            reason="unknown_reference",
        )
    if kind in ("example", "qasmbench"):
        if not rest:
            raise usage(
                f"{token}: name the {kind} after the colon.", hint="qrosetta run --help", reason="bad_reference"
            )
        name = rest[:-5] if kind == "example" and rest.endswith(".qasm") else rest
        return CircuitRef(kind, token, name=name)
    head, _, tail = rest.partition(",")
    algo, sep, qubits = head.rpartition(":")
    if not sep or not algo:
        raise usage(f"{token}: write {kind}:NAME:QUBITS.", hint="qrosetta run --help", reason="bad_reference")
    ref = CircuitRef(kind, token, name=algo, qubits=_int(qubits, token, "the qubit count"))
    if tail:
        if kind != "algorithm":
            raise usage(
                f"{token}: only algorithm: references take KEY=VALUE settings.",
                hint="qrosetta run --help",
                reason="bad_reference",
            )
        for pair in tail.split(","):
            key, sep, value = pair.rpartition("=")
            if not sep or key not in ALGORITHM_KEYS:
                raise usage(
                    f"{token}: unknown setting {pair!r}; algorithm references take "
                    f"{', '.join(k + '=N' for k in ALGORITHM_KEYS)}.",
                    hint="qrosetta run --help",
                    reason="bad_reference",
                )
            ref.params[key] = _int(value, token, key)
    return ref


def _read_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise CliError(
            f"Cannot read {path}: {exc.strerror}.",
            Exit.NOT_FOUND,
            "input_missing",
            hint="qrosetta run FILE, with FILE a readable OpenQASM 2.0 file",
        ) from None
    except UnicodeDecodeError:
        raise CliError(
            f"{path} is not UTF-8 text.",
            Exit.REFUSED,
            "input_not_text",
            hint="qrosetta run FILE, with FILE an OpenQASM 2.0 text file",
        ) from None


def text(conn, ref, stdin):
    """(name, QASM text) of a reference, fetched as the page's editor fetches it."""
    if ref.kind == "file":
        return ref.name, _read_file(ref.token)
    if ref.kind == "stdin":
        data = stdin.read()
        return ref.name, data.decode("utf-8") if isinstance(data, bytes) else data
    if ref.kind == "example":
        body = conn.get(f"/examples/{ref.name}.qasm", what=f"example {ref.name!r}", hint="qrosetta api GET /examples")
        return ref.name, body["qasm"]
    if ref.kind == "algorithm":
        payload = {"algorithm": ref.name, "qubits": ref.qubits, **ref.params}
        body = conn.post(
            "/generate_circuit", payload, what=f"algorithm {ref.name!r}", hint="qrosetta api GET /algorithms"
        )
        suffix = f"-seed{ref.params['seed']}" if "seed" in ref.params else ""
        return f"{ref.name}-{ref.qubits}q{suffix}", body["qasm"]
    if ref.kind == "mqt":
        body = conn.get(
            "/benchmarks/mqt",
            query={"algorithm": ref.name, "qubits": ref.qubits},
            what=f"MQT Bench {ref.name!r}",
            hint="qrosetta api GET /benchmarks/mqt/list",
        )
        return f"{ref.name}-{ref.qubits}q", body["qasm"]
    body = conn.get(
        "/benchmarks/qasmbench",
        query={"circuit": ref.name},
        what=f"QASMBench {ref.name!r}",
        hint="qrosetta api GET /benchmarks/qasmbench/list",
    )
    return ref.name, body["qasm"]


def playlist_item(conn, ref, stdin):
    """A playlist item in the page's format: algorithm, mqt and qasmbench references stay
    references the server resolves (a seeded algorithm becomes its text); the rest are
    literal circuits."""
    if ref.kind == "algorithm" and not ref.params:
        return {"algorithm": ref.name, "qubits": ref.qubits, "name": ref.name, "qasm_string": None}
    if ref.kind == "mqt":
        return {"source": "mqt", "algorithm": ref.name, "qubits": ref.qubits, "name": ref.name, "qasm_string": None}
    if ref.kind == "qasmbench":
        return {"source": "qasmbench", "algorithm": ref.name, "name": ref.name, "qasm_string": None}
    name, qasm = text(conn, ref, stdin)
    return {"algorithm": name, "name": name, "qasm_string": qasm}
