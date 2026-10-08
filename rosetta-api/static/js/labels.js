// Plain wording for the codes a report records (agreement labels, shot-noise assessments,
// marginal results, run statuses, compile refusals, not-comparable reasons). The code itself
// stays visible next to the wording. Leaf module: no imports.

/** @type {Record<string, { short: string, definition: string, anchor: string }>} */
export const LABELS = {
    agree_directly: { short: 'Agree', anchor: 'taxonomy',
        definition: 'The two statevectors match within the fidelity tolerance, as returned.' },
    agree_up_to_global_phase: { short: 'Agree up to a global phase', anchor: 'taxonomy',
        definition: 'The statevectors match after removing a global phase, which no measurement can see.' },
    agree_after_bit_reversal: { short: 'Agree after bit reversal', anchor: 'bitorder',
        definition: 'The statevectors match after the bit reversal that the two backends\' declared qubit orderings imply: one backend writes qubit 0 as the rightmost bit of a basis state, the other as the leftmost, so the same state is written in reverse. This is agreement. A state that reads the same both ways (a Bell or GHZ state) is listed here too for every pair of one LSB and one MSB backend.' },
    agree_after_qubit_permutation: { short: 'Match only after an undeclared qubit permutation', anchor: 'taxonomy',
        definition: 'The outputs match only after reordering qubits in a way neither backend declares. Counted as a disagreement.' },
    agree_after_normalization: { short: 'Agree after normalisation', anchor: 'taxonomy',
        definition: 'A statevector\'s norm differs from 1 by more than the norm tolerance; the pair agrees once both are normalised.' },
    residual_disagreement: { short: 'Disagree', anchor: 'taxonomy',
        definition: 'No registered transform (global phase, declared bit reversal, normalisation) explains the difference.' },
    not_comparable: { short: 'Not comparable', anchor: 'taxonomy',
        definition: 'The two outputs could not be compared; the reason is recorded with the pair.' },
    distance_within_threshold: { short: 'Within the JS/Hellinger thresholds', anchor: 'stat',
        definition: 'Descriptive only: the distance between the two count distributions is within the JS and Hellinger thresholds. The shot-noise test decides agreement.' },
    distance_exceeds_threshold: { short: 'Above the JS/Hellinger thresholds', anchor: 'stat',
        definition: 'Descriptive only: the distance is above the JS or Hellinger threshold. At low shot counts this can be shot noise; the shot-noise test decides.' },
    consistent_within_shot_noise: { short: 'Consistent within shot noise', anchor: 'stat',
        definition: 'The tests found no difference beyond shot noise and had enough power to find a total-variation gap of the stated size. This does not show the distributions are equal.' },
    inconclusive_low_shots: { short: 'Inconclusive', anchor: 'stat',
        definition: 'No difference was found, but the test had too little power at this shot count, or too many outcomes were rare.' },
    ambiguous: { short: 'Inconclusive: the two tests disagree', anchor: 'stat',
        definition: 'One of the chi-square and G-tests is significant and the other is not.' },
    distinguishable: { short: 'Distinguishable beyond shot noise', anchor: 'stat',
        definition: 'Both the chi-square and the G-test are significant after the multiple-testing correction.' },
    marginal_distinguishable: { short: 'A single-bit marginal differs', anchor: 'stat',
        definition: 'For at least one classical bit, how often it reads 1 differs between the two backends by more than chance allows. The distributions are therefore not equal.' },
    no_marginal_difference_detected: { short: 'No single-bit marginal differs', anchor: 'stat',
        definition: 'No classical bit\'s frequency differs significantly. This does not show the distributions are equal.' },
    low_power: { short: 'Test power too low', anchor: 'stat',
        definition: 'The test could not reliably detect a gap of the stated size at this shot count.' },
    low_expected_counts: { short: 'Too few counts per outcome', anchor: 'stat',
        definition: 'Expected counts are below 5 in too many outcomes for the test, even after pooling rare outcomes.' },
    ok: { short: 'OK', anchor: 'reading', definition: 'The backend returned a result.' },
    error: { short: 'Error', anchor: 'reading', definition: 'The backend rejected the circuit or crashed.' },
    timeout: { short: 'Timeout', anchor: 'reading', definition: 'The backend did not finish within its time budget.' },
    offline: { short: 'Offline', anchor: 'reading', definition: 'The backend could not be reached.' },
    input: { short: 'Refused: input', anchor: 'compilers', definition: 'The compiler cannot compile this input correctly, so it did not try.' },
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

/** Simulator ids with a row in the manual's Known backend issues table (docs.html#known-issues). */
export const KNOWN_ISSUE_BACKENDS = ['pennylane-default', 'pennylane-lightning', 'qibo', 'qrisp', 'quimb'];

/** A link to the manual's Known backend issues section, opening in a new tab. */
export function knownIssuesLink(text = 'Known backend issues') {
    const a = document.createElement('a');
    a.href = 'docs.html#known-issues';
    a.target = '_blank';
    a.rel = 'noopener';
    a.className = 'underline';
    a.textContent = text;
    return a;
}

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
    a.className = 'text-xs font-normal underline opacity-80 hover:opacity-100';
    a.textContent = text;
    return a;
}

/** A plain-language reading of a report's Summary for a reader new to the comparison, by mode. */
export const PLAIN_MEANING = {
    statevector: 'Each backend computed the final quantum state of the circuit, and every pair of backends was compared. '
        + 'Two backends agree when their states match to within rounding. "Agree after bit reversal" is also agreement: the two backends '
        + 'write the qubits of a state in opposite order (qubit 0 rightmost or leftmost), and the states match once that is undone. '
        + 'A backend that differs from the others has produced a different state; the report shows which pairs differ, not which backend is right.',
    measured: 'Each backend simulated measuring the circuit many times (the shots) and counted the outcomes. Random sampling makes the counts '
        + 'of two correct backends differ a little, so each pair is tested for a difference larger than that noise. "Consistent within shot noise" '
        + 'means none was found; "Inconclusive" means more shots are needed to tell; "Distinguishable" or a differing single-bit marginal '
        + 'means a real difference, so at least one of the two backends is wrong.',
};

/** The "What this means" paragraph for a report in `mode` ('statevector' or 'measured'). */
export function plainMeaningNote(mode) {
    const text = PLAIN_MEANING[mode === 'measured' ? 'measured' : 'statevector'];
    const p = document.createElement('p');
    p.className = 'text-sm text-gray-700 mb-4';
    const b = document.createElement('span');
    b.className = 'font-medium';
    b.textContent = 'What this means: ';
    p.append(b, text);
    return p;
}
