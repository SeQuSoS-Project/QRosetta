# The cached benchmark-list helpers return an independent copy on each call.

from services import benchmark_library as bl


def test_list_qasmbench_is_cached_and_returns_independent_copies():
    bl._qasmbench_names.cache_clear()
    a = bl.list_qasmbench()
    b = bl.list_qasmbench()
    assert a == b
    assert a is not b                       # fresh copy each call
    a.append("__mutation__")                # mutating the result must not leak
    assert "__mutation__" not in bl.list_qasmbench()
    assert bl._qasmbench_names.cache_info().hits >= 1   # later calls hit the cache


def test_list_mqt_is_cached_and_returns_independent_copies():
    bl._mqt_index.cache_clear()
    a = bl.list_mqt()
    b = bl.list_mqt()
    assert a == b
    assert a is not b
    for algo in a:                          # inner size lists are copies too
        assert a[algo] is not b[algo]
    assert bl._mqt_index.cache_info().hits >= 1


def test_invalid_upstream_files_are_not_listed_and_fetch_is_422():
    import pytest
    from fastapi import HTTPException
    from services import benchmark_library as bl
    names = bl.list_qasmbench()
    for bad in ("sat_n11", "vqe_uccsd_n4", "vqe_uccsd_n6"):
        assert bad not in names
        with pytest.raises(HTTPException) as exc:
            bl.get_qasmbench_circuit(bad)
        assert exc.value.status_code == 422 and "as distributed upstream" in exc.value.detail
    assert "adder_n4" in names
