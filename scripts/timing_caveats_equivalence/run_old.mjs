// Reads {reports: [[result, ...], ...]} on stdin; prints, per report, the reference JS tag booleans
// per result and its "Before comparing times" phrases (old_rules.mjs, written by compare.py).
import { throttleText, outsideProcessText, mixedCoresText, unstableText, _timingCaveats } from './old_rules.mjs';

let input = '';
process.stdin.on('data', d => { input += d; });
process.stdin.on('end', () => {
    const { reports } = JSON.parse(input);
    const out = reports.map(raws => ({
        tags: raws.map(r => ({
            throttled: throttleText(r) !== null,
            outside: outsideProcessText(r) !== null,
            mixed: mixedCoresText(r) !== null,
            unstable: unstableText(r) !== null,
        })),
        phrases: _timingCaveats(raws),
    }));
    process.stdout.write(JSON.stringify(out));
});
