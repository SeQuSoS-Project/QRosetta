# Experiments

`experiment-1/` (5 July 2026) and `experiment-2/` (27 July 2026) were produced by code from
before v2.0.0, at commits `3ef4cf1` and `50e0af8`. Those commits were in the history that was
rewritten on 21 October 2026 and are not in this repository's history, so the `git_sha` in each
`manifest.json` cannot be checked out from here.

Do not cite these results as results of v2.0.0. Since they were produced:

- the Qrisp adapter's all-zero output on a failed SDK call was fixed (5bb0574);
- several adapters' bit-order labels were corrected;
- the measured-mode tests, multiple-testing correction and power calculation changed (the
  `ANALYSIS_VERSION` history in `DESIGN_DECISIONS.md`);
- the timing windows were redrawn (conversion moved out of the simulation call, one CPU per
  runner).

They stay as the record of what was run at the time. `0-experiment/` holds the harness that
produced them; the page's Experiment sweep (`POST /experiments`) produces a bundle of the same
kind with the current code.
