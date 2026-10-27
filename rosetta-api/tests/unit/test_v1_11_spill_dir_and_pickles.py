"""V1-11: the API keeps job files only in a private directory of its own and unpickles only files
it wrote; pickle loading appears only where the API, the prep worker and the runner scaffolding
read their own data."""
import os
import pickle
import re
import stat
from pathlib import Path

import pytest

from services import job_store

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def spill(tmp_path, monkeypatch):
    path = tmp_path / "spill"
    monkeypatch.setattr(job_store, "SPILL_DIR", str(path))
    return path


class _Planted:
    def __init__(self, marker):
        self.marker = marker

    def __reduce__(self):
        return os.mkdir, (self.marker,)


def test_v1_11_a_directory_of_another_user_or_a_link_is_refused(spill, tmp_path, monkeypatch):
    spill.mkdir()
    (spill / "planted.pickle").write_bytes(pickle.dumps(_Planted(str(tmp_path / "ran"))))
    monkeypatch.setattr(job_store.os, "geteuid", lambda: os.getuid() + 1)
    with pytest.raises(job_store.SpillDirRefused):
        job_store.reset_spill_dir()
    monkeypatch.undo()
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "link"))
    os.symlink(spill, tmp_path / "link")
    with pytest.raises(job_store.SpillDirRefused):
        job_store.reset_spill_dir()
    assert (spill / "planted.pickle").exists() and not (tmp_path / "ran").exists()


def test_v1_11_an_own_directory_is_emptied_and_made_private(spill, tmp_path):
    spill.mkdir()
    os.chmod(spill, 0o777)
    (spill / "old.pickle").write_bytes(b"x")
    job_store.reset_spill_dir()
    assert os.listdir(spill) == []
    assert stat.S_IMODE(os.lstat(spill).st_mode) == 0o700


def test_v1_11_only_files_this_process_wrote_are_unpickled(spill, tmp_path):
    job_store.reset_spill_dir()
    mine = job_store.spill_task_report("job-a", 0, {"task_name": "bell"})
    assert isinstance(mine, job_store.SpilledReport) and mine.load() == {"task_name": "bell"}
    planted = spill / "job-b" / "task-00000.pickle"
    planted.parent.mkdir()
    planted.write_bytes(pickle.dumps(_Planted(str(tmp_path / "ran"))))
    with pytest.raises(job_store.ForeignSpillFile):
        job_store.SpilledReport(str(planted)).load()
    assert not (tmp_path / "ran").exists()
    job_store.remove_job_files("job-a")
    with pytest.raises((job_store.ForeignSpillFile, FileNotFoundError)):
        mine.load()


_LOADS = re.compile(r"\bpickle\.(load|loads)\b|\bUnpickler\b")
_ALLOWED = {"rosetta-api/services/job_store.py", "rosetta-api/services/prep_worker.py",
            "shared/qrosetta_commons/helpers.py"}


def test_v1_11_pickle_is_loaded_only_in_the_three_known_places():
    found = set()
    for top in ("rosetta-api", "shared", "runners", "compilers", "qrosetta_cli"):
        for path in (ROOT / top).rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if "/tests/" in rel or "/.venv/" in rel or "/build/" in rel:
                continue
            if _LOADS.search(path.read_text(encoding="utf-8", errors="replace")):
                found.add(rel)
    assert found <= _ALLOWED, sorted(found - _ALLOWED)
