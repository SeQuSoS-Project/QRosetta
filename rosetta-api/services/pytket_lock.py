"""Process-wide lock held around every pytket QASM parse or write in the API process
(the round-trip and the algorithm templates): pytket's QASM reader keeps one parser and its
gate table in a module global, so two threads parsing at once read each other's gates."""

import threading

PYTKET_LOCK = threading.RLock()
