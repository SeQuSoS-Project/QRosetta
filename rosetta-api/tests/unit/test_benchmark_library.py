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
