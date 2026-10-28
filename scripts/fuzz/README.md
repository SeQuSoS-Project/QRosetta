# Fuzz harnesses

Four harnesses for the code that reads client text: the request validator, preparation, the
regular expressions, and client-supplied reports. `rosetta-api/tests/unit/test_fuzz_harnesses.py`
runs each for a few seconds on its seed inputs, so CI keeps them working; the long runs below are
run by hand. Saved findings go to `rosetta-api/tests/fuzz_corpus/`, each with a regression test
named after its defect id (`test_v6_fuzz_findings.py`), and every file there is replayed under
every request option by `test_saved_finding_replays_under_every_option`.

| File | Harness | Oracle |
|---|---|---|
| `validator_atheris.py`, `run_validator.sh` | 1: bytes into `validate_submission` (Atheris, coverage-guided), seeded with the bundled circuits, mode and options from the input's CRC32 | returns, or HTTPException 400/413 with a text detail; under 1 s; under 256 MiB (`tracemalloc` on replay, libFuzzer `-rss_limit_mb` while fuzzing) |
| `qasm_grammar.py`, `run_grammar.py` | 2: generated OpenQASM 2.0 (several registers, nested gate definitions with parameters, expressions, broadcasts, barriers, measure, reset, if) | a program the validator accepts prepares in both modes (pytket round-trip), parses in Qiskit (`QuantumCircuit.from_qasm_str`), has the expanded-gate count Qiskit's parse gives, and, when statevector-compatible and up to 8 qubits, prepares to the same state (fidelity at least 1 - 1e-9) |
| `redos.py` | 3: every literal regular expression in the API, `shared/`, the runners and the compilers, timed on 1 MB built from short repeated strings (generic QASM pieces and the pattern's own literals, with suffixes that make a match fail), with the methods the code calls | under 1 s |
| `report_fuzz.py` | 4: reports with odd values (1 MiB strings, 20,000-deep nesting, 50,000-key objects, huge numbers, bidi controls, formula-like cells) sent in process to POST /export, /summary, /publication/artifacts, /publication/render, /timing-caveats | no 5xx; under 10 s; crate member names without control, bidi or `..` parts; formula-like CSV cells counted (crates record values as they are; DESIGN_DECISIONS.md, "CSV cells in crates") |

`fuzz_targets.large_inputs()` gives 1 MB circuits of one repeated construct (blank lines, comments,
declarations, gate bodies, operand lists, expressions); `test_v6_06_every_large_input_shape_takes_under_a_second`
times the validator on each. `reduce.py FINDING.bin` shrinks a harness-1 finding by delta
debugging (lines, then characters) while it fails the same way.

## Setup

Atheris and Qiskit are not in the CI requirements. Use a separate venv (Python 3.12; atheris
3.0.0 ships a cp312 wheel; Qiskit 1.4.4 is the version the cuQuantum runner pins; pytket 1.33.0
is the API's pin), and keep `TMPDIR` off `/tmp`:

```bash
python3.12 -m venv ~/.tmp/fuzz-venv
~/.tmp/fuzz-venv/bin/pip install -r rosetta-api/requirements.txt \
    atheris==3.0.0 hypothesis==6.112.1 qiskit==1.4.4
```

On a machine that is also measuring, pin the fuzzers to cores the measurement does not use and
run them at nice 10 (`run_validator.sh` does both).

## Long runs

From the repository root:

```bash
# Harness 1: one process per CPU listed, 2 hours each, findings in WORKDIR/findings
TMPDIR=~/.tmp scripts/fuzz/run_validator.sh ~/.tmp/fuzz-venv/bin/python ~/.tmp/fuzz-v1 7200 16 17 18 19
~/.tmp/fuzz-venv/bin/python scripts/fuzz/reduce.py ~/.tmp/fuzz-v1/findings/<id>.bin

# Harness 2: 30 minutes
TMPDIR=~/.tmp PYTHONPATH=rosetta-api:shared ~/.tmp/fuzz-venv/bin/python scripts/fuzz/run_grammar.py 1800 ~/.tmp/fuzz-v2

# Harness 3: prints one line per pattern, exit status 1 when any is over the limit
TMPDIR=~/.tmp ~/.tmp/fuzz-venv/bin/python scripts/fuzz/redos.py --json ~/.tmp/redos.json

# Harness 4 (from rosetta-api/, which the app's static mount needs): 30 minutes, seed 1
cd rosetta-api && TMPDIR=~/.tmp PYTHONPATH=.:../shared DATABASE_URL=sqlite:///$HOME/.tmp/fuzz.db \
    ~/.tmp/fuzz-venv/bin/python ../scripts/fuzz/report_fuzz.py 1800 ~/.tmp/fuzz-v4 1
```

`run_validator.sh` writes `/usr/bin/time -v` output per process (`time-N.txt`); the user and
system times there are the CPU time spent.
