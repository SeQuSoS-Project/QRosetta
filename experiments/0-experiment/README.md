# 0-experiment — QRosetta fleet-experiment harness

A small, dependency-free driver that runs a set of circuits across the QRosetta simulator
fleet and **freezes everything needed to replay and cite the run**. It is the reusable
harness; each actual run lives in a sibling folder (`experiment-1/`, `experiment-2/`, …).

## Why this exists

The reviewers asked us to run more circuits. Running the fleet over many circuits produces
**two distinct, honest outputs** that this harness keeps separate:

- **A — Conformance / robustness matrix** (`conformance_matrix.csv`): for every
  `circuit × simulator`, did it run? (`success` / `error` / `timeout` / `circuit_error`),
  with the raw error signature. This is the "run more circuits" evidence and the
  runner-conformance contribution.
- **B — Explained-disagreement prevalence** (`agreement_prevalence.csv`): over the pairs
  that ran successfully, the distribution of agreement classes
  (`agree_directly` → `bit_reversal` → `qubit_permutation` → `residual_disagreement`).

They are **never conflated**, and no research question is baked in.

## Integrity: triage before you call anything a "finding"

An error in the matrix is only a *finding* after a human classifies it into one of:

| Bucket | Meaning | Report it? |
|---|---|---|
| adapter | a QRosetta runner-adapter bug (cf. FIX-001) | ❌ fix it, don't report |
| sdk | a genuine bug inside the simulator SDK | ✅ once reproduced in-container |
| by-design | the SDK legitimately doesn't support that feature | ✅ as a capability limit |
| resource | OOM / timeout / environment | ⚠️ report as environmental |

The `triage` column starts as `untriaged`. `errors/<simulator>.log` groups signatures per
simulator to make this fast. **Do not** paste the matrix into the paper before triage.

## Reproducibility contract

Each `experiment-N/` folder is self-describing:

```
experiment-N/
  manifest.json            git SHA · effective seed(s) · executed SDK versions · config hash · timestamp
  inputs/*.qasm            the EXACT QASM executed (frozen; not "regenerate grover-5q" later)
  results/<axis>/*.json    per-circuit reports (statevectors stripped to a sha256 unless --keep-sv)
  conformance_matrix.csv   output A (+ triage column)
  agreement_prevalence.csv output B
  performance.csv          per circuit x simulator timings, memory and CPU context
  errors/<sim>.log         per-simulator error signatures
```

**Seed policy:** set `"seed"` in the config for an exact replay; leave it `null` and the API
generates one *and records it* in every report (`results/*/*.json` → `"seed"`, surfaced in
`manifest.json → effective_seeds_per_axis`). No run is ever un-seeded. Statevector mode is
exact/seedless. **Image digests** are pinned in the runner Dockerfiles (`@sha256`, FIX-014);
record the deployed digests in `manifest.json` before a citable release.

## Usage

```bash
# 1. Bring up the QRosetta stack (local containers), then:
python run_experiment.py --config config.example.json --out experiment-1

# override the API or keep full statevectors:
python run_experiment.py --config config.example.json --out experiment-1 \
    --base-url http://localhost:8000 --keep-sv
```

Only the Python standard library is required. `mode` may be `measured` or `statevector`;
`preprocessing_modes` may be `[true]`, `[false]`, or `[true, false]` to run both axes (note:
some SDKs — e.g. TorchQuantum — cannot run raw QASM without a basis-decomposition pass, so
`false` is not uniformly meaningful; the per-runner `preprocessing_applied` is recorded).

## Config fields

| field | meaning |
|---|---|
| `base_url` | QRosetta API root |
| `mode` | `measured` or `statevector` |
| `n_shots` | shots (measured mode); omitted = server default (8192) |
| `timing_repeats` | timed runs per backend after one warm-up (1–10); times are medians |
| `runner_phases` | runner id → phase number; phases run one after another, so backends in different phases do not compete for CPU |
| `seed` | fixed seed, or `null` → generated-and-recorded |
| `target_simulators` | `[]` = all enabled, else a subset |
| `optimization_level` | global opt level |
| `preprocessing_modes` | list of booleans (run each as an axis) |
| `thresholds` | optional agreement-threshold overrides, or `null` for defaults |
| `circuits` | list of `{algorithm, qubits}` (presets) and/or `{qasm_file, name}` |
