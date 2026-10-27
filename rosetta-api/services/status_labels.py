"""GET /config status_labels: the word and tooltip shown for each live status of a run
(``runner_statuses``), of a playlist circuit (``progress.tasks[].status``, plus
``analysing`` while the job's phase is analysing) and of a job (``phase``)."""

_QUEUED = {"label": "QUEUED", "hint": "Not started yet. Its time starts when it does."}
_DONE = {"label": "DONE", "hint": None}
_ERROR = {"label": "ERROR", "hint": None}
_ANALYSING = {"label": "ANALYSING",
              "hint": "Every backend has returned; the server is comparing the results. Measured "
                      "runs with many outcomes can take tens of seconds here."}

STATUS_LABELS = {
    "runs": {
        "queued": _QUEUED,
        "spawning": {"label": "SPAWNING", "hint": None},
        "running": {"label": "SENT",
                    "hint": "Sent to the backend. Each backend runs one request at a time, so this "
                            "includes any wait behind another job; the wait is recorded as "
                            "queue_wait_sec."},
        "done": _DONE,
        "error": _ERROR,
        "timeout": {"label": "TIMEOUT", "hint": None},
        "offline": {"label": "OFFLINE", "hint": "The backend could not be reached."},
    },
    "tasks": {
        "queued": _QUEUED,
        "running": {"label": "RUNNING", "hint": None},
        "analysing": _ANALYSING,
        "done": _DONE,
        "error": _ERROR,
    },
    "phases": {
        "queued": {"label": "QUEUED", "hint": "Accepted; the server has not started it."},
        "dispatching": {"label": "RUNNING",
                        "hint": "Preparing circuits, waiting for the run gate, and the runs and "
                                "compiles."},
        "analysing": _ANALYSING,
        "exporting": {"label": "EXPORTING",
                      "hint": "Writing the job's results to the server's job store."},
        "done": _DONE,
    },
}


def status_labels() -> dict:
    """A copy of STATUS_LABELS."""
    return {kind: {status: dict(entry) for status, entry in entries.items()}
            for kind, entries in STATUS_LABELS.items()}
