"""Process-wide lock held around every pytket QASM parse or write (the round-trip and the
Quirk drawing in the preparation worker, the algorithm templates in the API process):
pytket's QASM reader keeps one parser and its gate table in a module global, so two threads
parsing at once read each other's gates."""

import threading

PYTKET_LOCK = threading.RLock()
