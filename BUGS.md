# Known Issues & Upstream Limitations

## 1. Pytket-Cirq Barrier Incompatibility
* **Component:** `pytket-cirq-runner`
* **Error:** `Cannot convert tket Op to Cirq gate: Barrier`
* **Context:** The `barrier` instruction is valid in OPENQASM and Pytket, but the `tk_to_cirq` converter does not handle it natively during translation.
* **Workaround:** We explicitly apply `Transform.RemoveBarriers()` in the runner before conversion.

## 2. Pytket-Braket Gate Predicate Failure
* **Component:** `pytket-braket-runner`
* **Error:** `Circuit with index 0 ... does not satisfy GateSetPredicate ... { ... SWAP ... }`
* **Context:** The local Braket backend via Pytket seems to reject Barriers and occasionally complex gates when passed raw QASM without a compilation pass.
* **Workaround:** We apply `Transform.RemoveBarriers()` in the runner.

## 3. ProjectQ SWAP Gate Missing
* **Component:** `pytket-projectq-runner`
* **Error:** `Cannot convert op SWAP q[0], q[4]; to projectq`
* **Context:** The ProjectQ backend interface in Pytket does not have a mapping for the `SWAP` gate, even though ProjectQ likely supports it natively.
* **Workaround:** We apply `Transform.DecomposeSWAPtoCX()` in the runner to convert SWAPs into 3 CNOTs.

## 4. Braket Statevector Memory Explosion
* **Component:** `pytket-braket-runner`
* **Error:** `Unable to allocate 16.0 TiB ...`
* **Context:** When running large (20+ qubit) statevector simulations, the backend attempts to allocate the full Unitary Matrix instead of the Statevector.
* **Status:** Unresolved. This is a valid benchmark failure for the simulator in this configuration.
