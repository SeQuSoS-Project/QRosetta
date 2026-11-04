// Plain wording for the codes a report records (agreement labels, shot-noise assessments,
// marginal results, run statuses, timing caveats, compile refusals, not-comparable reasons). The code itself
// stays visible next to the wording. Leaf module: no imports.

/** @type {Record<string, { short: string, definition: string, anchor: string }>} */
export const LABELS = {
    agree_directly: { short: 'Agree', anchor: 'taxonomy',
        definition: 'The two statevectors match within the fidelity tolerance, as returned.' },
    agree_up_to_global_phase: { short: 'Agree up to a global phase', anchor: 'taxonomy',
        definition: 'The statevectors match after removing a global phase, which no measurement can see.' },
    agree_after_bit_reversal: { short: 'Agree after bit reversal', anchor: 'bitorder',
        definition: 'The statevectors match after the bit reversal implied by the two declared qubit orderings (qubit 0 rightmost in one, leftmost in the other). Counted as agreement.' },
    agree_after_qubit_permutation: { short: 'Match only after an undeclared qubit permutation', anchor: 'taxonomy',
        definition: 'The outputs match only after reordering qubits in a way neither backend declares. Counted as a disagreement.' },
    agree_after_normalization: { short: 'Agree after normalisation', anchor: 'taxonomy',
        definition: 'A statevector\'s norm differs from 1 by more than the norm tolerance; the pair agrees once both are normalised.' },
    residual_disagreement: { short: 'Disagree', anchor: 'taxonomy',
        definition: 'No registered transform (global phase, declared bit reversal, normalisation) explains the difference.' },
    not_comparable: { short: 'Not comparable', anchor: 'taxonomy',
        definition: 'The two outputs could not be compared; the reason is recorded with the pair.' },
    distance_within_threshold: { short: 'Within the JS/Hellinger thresholds', anchor: 'stat',
        definition: 'Descriptive: the distance between the count distributions is within the JS and Hellinger thresholds. Agreement is decided by the shot-noise test.' },
    distance_exceeds_threshold: { short: 'Above the JS/Hellinger thresholds', anchor: 'stat',
        definition: 'Descriptive: the distance is above the JS or Hellinger threshold, which at low shot counts can be shot noise. Agreement is decided by the shot-noise test.' },
    consistent_within_shot_noise: { short: 'Consistent within shot noise', anchor: 'stat',
        definition: 'No difference beyond shot noise, with enough power to detect a total-variation gap of the stated size. Not a proof of equality.' },
    inconclusive_low_shots: { short: 'Inconclusive', anchor: 'stat',
        definition: 'No difference found, but the test lacks power at this shot count or too many outcomes are rare.' },
    ambiguous: { short: 'Inconclusive: the two tests disagree', anchor: 'stat',
        definition: 'One of the chi-square and G-tests is significant and the other is not.' },
    distinguishable: { short: 'Distinguishable beyond shot noise', anchor: 'stat',
        definition: 'Both the chi-square and the G-test are significant after the multiple-testing correction.' },
    marginal_distinguishable: { short: 'A single-bit marginal differs', anchor: 'stat',
        definition: 'For at least one classical bit, the frequency of 1 differs beyond chance, so the distributions differ.' },
    no_marginal_difference_detected: { short: 'No single-bit marginal differs', anchor: 'stat',
        definition: 'No classical bit\'s frequency differs significantly. Not a proof of equality.' },
    low_power: { short: 'Test power too low', anchor: 'stat',
        definition: 'The test could not reliably detect a gap of the stated size at this shot count.' },
    low_expected_counts: { short: 'Too few counts per outcome', anchor: 'stat',
        definition: 'Expected counts are below 5 in too many outcomes for the test, even after pooling rare outcomes.' },
    ok: { short: 'OK', anchor: 'reading', definition: 'The backend returned a result.' },
    error: { short: 'Error', anchor: 'reading', definition: 'The backend rejected the circuit or crashed.' },
    timeout: { short: 'Timeout', anchor: 'reading', definition: 'The backend did not finish within its time budget.' },
    offline: { short: 'Offline', anchor: 'reading', definition: 'The backend could not be reached.' },
    shared_dispatch: { short: 'Shared dispatch', anchor: 'timing-caveats',
        definition: 'Dispatched beside other runs of the same job, sharing the host\'s cores and memory bandwidth.' },
    overlapping_runs: { short: 'Runs of this job overlapped', anchor: 'timing-caveats',
        definition: 'Other runs of this job were executing while this run executed.' },
    server_overlapping_runs: { short: 'Other jobs ran on the server', anchor: 'timing-caveats',
        definition: 'Runs of other jobs on this server were executing while this run executed.' },
    host_load: { short: 'Host load from qrosetta', anchor: 'timing-caveats',
        definition: 'qrosetta started, stopped, built, pulled or probed containers on this host during the run.' },
    throttled: { short: 'Throttled by the CPU quota', anchor: 'timing-caveats',
        definition: 'The CPU quota held the runner for at least 1% of the simulation window; that wait is part of simulation_time_sec.' },
    compilation_throttled: { short: 'Compilation throttled by the CPU quota', anchor: 'timing-caveats',
        definition: 'The CPU quota held the runner for at least 1% of the compilation window; that wait is part of compilation_time_sec.' },
    unstable_repeats: { short: 'Unstable timed runs', anchor: 'timing-caveats',
        definition: 'The timed runs spread by more than 1.3x between the fastest and the slowest simulation time.' },
    mixed_cores: { short: 'Mixed core speeds', anchor: 'timing-caveats',
        definition: 'The timed runs of this backend ran on CPUs of different speed classes (maximum frequencies more than 10% apart).' },
    outside_process: { short: 'Work outside the measured process', anchor: 'timing-caveats',
        definition: 'The container used at least 5 ms and 10% more CPU than the simulating process during the simulation window; that work is not in the process fields.' },
    single_timed_run: { short: 'One timed run (n=1)', anchor: 'timing-caveats',
        definition: 'One timed run (timing_repeats = 1): run-to-run variation is not measured.' },
    no_cpu_quota: { short: 'No CPU quota', anchor: 'timing-caveats',
        definition: 'No CPU quota applied; the runner\'s CPU share depended on other load on the host.' },
    virtualised_host: { short: 'Ran in a virtual machine', anchor: 'timing-caveats',
        definition: 'The host CPU reports the hypervisor flag: the runner ran in a virtual machine.' },
    emulated_cpu: { short: 'Emulated CPU', anchor: 'timing-caveats',
        definition: 'The runner saw an emulated CPU model; timings do not describe native execution.' },
    emulated_image: { short: 'Image emulated on this host', anchor: 'timing-caveats',
        definition: 'The image targets another architecture and ran under emulation; timings do not describe native execution.' },
    non_x86_64: { short: 'Not x86_64', anchor: 'timing-caveats',
        definition: 'The runner reported a machine architecture other than x86_64.' },
    cross_backend_core_speeds: { short: 'Backends on CPUs of different speeds', anchor: 'timing-caveats',
        definition: 'The simulation windows of these backends ran on CPUs of different speed classes (maximum frequencies more than 10% apart).' },
    cross_backend_cpu_quota: { short: 'Backends under different CPU quotas', anchor: 'timing-caveats',
        definition: 'Backends ran under different CPU quotas.' },
    cross_backend_image_commits: { short: 'Backends from images of different commits', anchor: 'timing-caveats',
        definition: 'Backend images were built from different commits; the measurement code may differ.' },
    input: { short: 'Refused: input', anchor: 'compilers', definition: 'The compiler cannot compile this input correctly and did not run.' },
    output_check: { short: 'Refused: output check failed', anchor: 'compilers', definition: 'The compiled circuit failed its equivalence or layout check.' },
    missing_statevector: { short: 'No statevector', anchor: 'taxonomy', definition: 'One run returned no statevector.' },
    statevector_parse_error: { short: 'Statevector unreadable', anchor: 'taxonomy', definition: 'A returned statevector could not be decoded.' },
    empty_statevector: { short: 'Empty statevector', anchor: 'taxonomy', definition: 'A returned statevector has no amplitudes.' },
    nonfinite_statevector: { short: 'Non-finite amplitudes', anchor: 'taxonomy', definition: 'A statevector contains NaN or infinite amplitudes.' },
    zero_norm_statevector: { short: 'Zero-norm statevector', anchor: 'taxonomy', definition: 'A statevector has norm 0.' },
    shape_mismatch: { short: 'Different lengths', anchor: 'taxonomy', definition: 'The two statevectors have different lengths.' },
    comparison_error: { short: 'Comparison failed', anchor: 'taxonomy', definition: 'The comparison raised an error.' },
    missing_counts: { short: 'No counts', anchor: 'taxonomy', definition: 'One run returned no counts.' },
    empty_counts: { short: 'Empty counts', anchor: 'taxonomy', definition: 'A count histogram has no entries.' },
    invalid_bitstring_key: { short: 'Invalid outcome key', anchor: 'taxonomy', definition: 'A counts key is not a bitstring.' },
    non_numeric_counts: { short: 'Non-numeric counts', anchor: 'taxonomy', definition: 'A count is not a number.' },
    nonfinite_counts: { short: 'Non-finite counts', anchor: 'taxonomy', definition: 'A count is NaN or infinite.' },
    negative_counts: { short: 'Negative counts', anchor: 'taxonomy', definition: 'A count is negative.' },
    zero_total_counts: { short: 'Zero shots', anchor: 'taxonomy', definition: 'The counts add up to 0.' },
    nonfinite_metric: { short: 'Non-finite distance', anchor: 'taxonomy', definition: 'A distance came out NaN or infinite.' },
    inconsistent_bitstring_lengths: { short: 'Outcome keys of different lengths', anchor: 'taxonomy', definition: 'The two backends report outcomes with different numbers of bits.' },
};

/** Plain wording for a code, or the code itself when it has none. */
export function labelText(code) {
    return LABELS[code]?.short ?? String(code ?? '');
}

/** Definition of a code, or ''. */
export function labelDefinition(code) {
    return LABELS[code]?.definition ?? '';
}

/** A link to the manual section that explains `code`, opening in a new tab; null when the
 * code has none. */
export function docsLink(code, text = 'How this is decided') {
    const anchor = LABELS[code]?.anchor;
    if (!anchor) return null;
    const a = document.createElement('a');
    a.href = `docs.html#${anchor}`;
    a.target = '_blank';
    a.rel = 'noopener';
    a.className = 'text-xs font-normal underline hover:no-underline';
    a.textContent = text;
    return a;
}

/** How pairs are judged, by mode. */
export const PLAIN_MEANING = {
    statevector: 'A pair agrees when its states match within the fidelity tolerance: directly, up to a global phase, '
        + 'or after the bit reversal the two declared qubit orderings imply. A differing pair does not identify which backend is wrong.',
    measured: 'Each pair is tested for a difference beyond shot noise. Inconclusive pairs need more shots; '
        + 'a distinguishable pair or a differing single-bit marginal means at least one of the two backends is wrong.',
};

/** One line on how pairs of a report in `mode` ('statevector' or 'measured') are judged. */
export function plainMeaningNote(mode) {
    const p = document.createElement('p');
    p.className = 'text-xs text-gray-600 mb-4';
    p.textContent = PLAIN_MEANING[mode === 'measured' ? 'measured' : 'statevector'];
    return p;
}
