"""The CLI's retention wording and crate deferral read limits.job_ttl_sec and, when the server
publishes them, limits.job_max_kept and limits.job_evictable_after_sec: a finished job is kept
for up to the TTL, and certainly only until the eviction age when the server bounds the count."""
import time

import pytest

import tests.unit._qrosetta_fake  # noqa: F401  (puts the repository root on sys.path)

from qrosetta_cli.client import reads, run, save


class _Conn:
    def __init__(self, **limits):
        self.config = {"limits": limits}

    def limit(self, name, default=None):
        return self.config["limits"].get(name, default)


LOCAL = {"job_ttl_sec": 86400, "job_max_kept": 200, "job_evictable_after_sec": 1800}


@pytest.mark.parametrize("limits, kept", [
    (LOCAL, 1800),
    ({"job_ttl_sec": 86400, "job_evictable_after_sec": 1800}, 86400),
    ({"job_ttl_sec": 600, "job_max_kept": 200, "job_evictable_after_sec": 1800}, 600),
    ({}, 1800),
    ({"job_ttl_sec": "x", "job_max_kept": 200, "job_evictable_after_sec": None}, 1800),
])
def test_the_crate_deferral_ends_before_the_server_may_delete_the_job(limits, kept):
    assert save.kept_for(_Conn(**limits)) == kept


def test_kept_text_names_the_count_bound_only_when_it_shortens_the_retention():
    assert run.kept_text(_Conn(**LOCAL)) == (
        "it keeps finished jobs for up to 24 h, and deletes the oldest from 30 min on while it holds more than 200")
    assert run.kept_text(_Conn(job_ttl_sec=1800, job_max_kept=200, job_evictable_after_sec=1800)) == (
        "it keeps finished jobs for up to 30 min")
    assert run.kept_text(_Conn(job_ttl_sec=86400)) == "it keeps finished jobs for up to 24 h"
    assert run.kept_text(_Conn()) == "it keeps finished jobs for a while"


def test_info_row_and_retention_text_say_at_the_latest():
    assert reads._jobs_kept(LOCAL) == "up to 24 h after they finish; over 200 finished, the oldest go from 30 min on"
    assert reads._jobs_kept({"job_ttl_sec": 1800}) == "up to 30 min after they finish"
    now = time.mktime((2026, 11, 5, 9, 0, 0, 0, 0, -1))
    assert run.retention_text(86400, now) == "for up to 24 h, until 09:00 tomorrow at the latest"


def test_a_deferred_crate_line_names_the_earliest_deletion_minus_the_margin():
    since = time.mktime((2026, 11, 5, 9, 0, 0, 0, 0, -1))
    info = {"crate": "deferred", "status": "completed",
            "record": {"crate_deferred_since": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(since))}}
    assert "(up to 09:20)" in run.crate_line(_Conn(**LOCAL), "abcdef0123", info)
