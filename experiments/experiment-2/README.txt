QRosetta reproducible-experiment bundle
=======================================

This folder freezes one fleet run so it can be replayed and cited:
  inputs/                  - the exact OpenQASM executed
  results/<axis>/*.json    - per-circuit reports (statevectors stripped to a sha256 by
                             default; metrics, labels and provenance kept in full)
  conformance_matrix.csv   - per (circuit x simulator) run status + error signature
  agreement_prevalence.csv - agreement-class counts over the pairs that ran
  errors/*.log             - per-simulator error signatures
  manifest.json            - config + git SHA + timestamp + effective seed + SDK versions

Reading the CSVs:
  * The conformance matrix and the prevalence table are separate outputs: a cell
    that failed to run carries no agreement information.
  * Each error row records a raw signature with triage='untriaged'. Classify each
    error as adapter / SDK / by-design / resource and update the column before
    reporting it as a result.
  * Each agreement label carries its registered transform and numerical effect in
    the per-pair records under results/.
  * The exhaustive qubit-permutation search is bounded; larger pairs report
    attempted=false with a reason. Disclose this bound in any prevalence analysis.
