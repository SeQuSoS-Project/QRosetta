#!/usr/bin/env bash
# Harness 1 long run: one validator_atheris.py process per CPU given, each pinned to its CPU
# at nice 10 with its own -max_len (FUZZ_MAX_LENS, cycled; default 1024 4096 16384 65536),
# sharing one corpus, seeded with the bundled circuits.
# Findings go to WORKDIR/findings, logs and /usr/bin/time -v reports to WORKDIR/log-N.txt
# and WORKDIR/time-N.txt.
# Usage: scripts/fuzz/run_validator.sh PYTHON WORKDIR SECONDS CPU [CPU...]
set -euo pipefail

cd "$(dirname "$0")/../.."
python=$1 workdir=$2 seconds=$3
shift 3
mkdir -p "$workdir/seeds" "$workdir/corpus" "$workdir/findings" "$workdir/crashes"
while IFS= read -r -d '' file; do
    cp "$file" "$workdir/seeds/$(printf '%s' "$file" | sha1sum | cut -c1-12).qasm"
done < <(find rosetta-api/benchmarks rosetta-api/circuits -name '*.qasm' -print0)

read -r -a lengths <<< "${FUZZ_MAX_LENS:-1024 4096 16384 65536}"
i=0
pids=()
for cpu in "$@"; do
    FUZZ_FINDINGS_DIR="$workdir/findings" TMPDIR="${TMPDIR:-$HOME/.tmp}" \
        /usr/bin/time -v -o "$workdir/time-$i.txt" \
        taskset -c "$cpu" nice -n 10 "$python" scripts/fuzz/validator_atheris.py \
        -max_total_time="$seconds" -timeout=30 -rss_limit_mb=1024 \
        -max_len="${lengths[$((i % ${#lengths[@]}))]}" -dict=scripts/fuzz/qasm.dict \
        -artifact_prefix="$workdir/crashes/" -print_final_stats=1 \
        "$workdir/corpus" "$workdir/seeds" > "$workdir/log-$i.txt" 2>&1 &
    pids+=($!)
    i=$((i + 1))
done
status=0
for pid in "${pids[@]}"; do
    wait "$pid" || status=1
done
grep -h "Elapsed\|User time\|System time\|Maximum resident" "$workdir"/time-*.txt
ls "$workdir/findings"
exit "$status"
