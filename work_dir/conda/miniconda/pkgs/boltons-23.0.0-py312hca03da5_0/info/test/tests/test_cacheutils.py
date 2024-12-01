# -*- coding: utf-8 -*-
import string
import sys
from abc import abstractmethod, ABCMeta

import pytest

from boltons.cacheutils import LRU, LRI, cached, cachedmethod, cachedproperty, MinIDMap, ThresholdCounter


class CountingCallable(object):
    def __init__(self):
        self.call_count = 0

    def __call__(self, *a, **kw):
        self.call_count += 1
        return self.call_count


def test_lru_add():
    cache = LRU(max_size=3)
    for i in range(4):
        cache[i] = i
    assert len(cache) == 3
    assert 0 not in cache


def test_lri():
    cache_size = 10
    bc = LRI(cache_size, on_miss=lambda k: k.upper())
    for idx, char in enumerate(string.ascii_letters):
        x = bc[char]
        assert x == char.upper()
        least_recent_insert_index = idx - cache_size
        if least_recent_insert_index >= 0:
            # least recently inserted object evicted
            assert len(bc) == cache_size
            for char in string.ascii_letters[least_recent_insert_index+1:idx]:
                assert char in bc

    # test that reinserting an existing key changes eviction behavior
    bc[string.ascii_letters[-cache_size+1]] = "new value"
    least_recently_inserted_key = string.ascii_letters[-cache_size+2]
    bc["unreferenced_key"] = "value"
    keys_in_cache = [
        string.ascii_letters[i]
        for i in range(-cache_size + 1, 0)
        if string.ascii_letters[i] != least_recently_inserted_key
    ]
    keys_in_cache.append("unreferenced_key")
    assert len(bc) == cache_size
    for k in keys_in_cache:
        assert k in bc


def test_lri_cache_eviction():
    """
    Regression test
    Original LRI implementation had a bug where the specified cache
    size only supported `max_size` number of inserts to the cache,
    rather than support `max_size` number of keys in the cache. This
    would result in some unintuitive behavior, where a key is evicted
    recently inserted value would be evicted from the cache if the key
    inserted was inserted `max_size` keys earlier.
    """
    test_cache = LRI(2)
    # dequeue: (key1); dict keys: (key1)
    test_cache["key1"] = "value1"
    # dequeue: (key1, key1); dict keys: (key1)
    test_cache["key1"] = "value1"
    # dequeue: (key1, key1, key2); dict keys: (key1, key2)
    test_cache["key2"] = "value2"
    # dequeue: (key1, key2, key3); dict keys: (key2, key3)
    test_cache["key3"] = "value3"
    # will error here since we evict key1 from the cache and it doesn't
    # exist in the dict anymore
    test_cache["key3"] = "value3"


def test_cache_sizes_on_repeat_insertions():
    """
    Regression test
    Original LRI implementation had an unbounded size of memory
    regardless of the value for its `max_size` parameter due to a naive
    insertion algorithm onto an underlying deque data structure. To
    prevent memory leaks, this test will assert that a cache does not
    grow past its max size given values of a uniform memory footprint
    """
    caches_to_test = (LRU, LRI)
    for cache_type in caches_to_test:
        test_cache = cache_type(2)
        # note strings are used to force allocation of memory
        test_cache["key1"] = "1"
        test_cache["key2"] = "1"
        initial_list_size = len(test_cache._get_flattened_ll())
        for k in test_cache:
            for __ in range(100):
                test_cache[k] = "1"
        list_size_after_inserts = len(test_cache._get_flattened_ll())
        assert initial_list_size == list_size_after_inserts


def test_lru_basic():
    lru = LRU(max_size=1)
    repr(lru)                   # sanity

    lru['hi'] = 0
    lru['bye'] = 1
    assert len(lru) == 1
    lru['bye']
    assert lru.get('hi') is None

    del lru['bye']
    assert 'bye' not in lru
    assert len(lru) == 0
    assert not lru

    try:
        lru.pop('bye')
    except KeyError:
        pass
    else:
        assert False

    default = object()
    assert lru.pop('bye', default) is default

    try:
        lru.popitem()
    except KeyError:
        pass
    else:
        assert False

    lru['another'] = 1
    assert lru.popitem() == ('another', 1)

    lru['yet_another'] = 2
    assert lru.pop('yet_another') == 2

    lru['yet_another'] = 3
    assert lru.pop('yet_another', default) == 3

    lru['yet_another'] = 4
    lru.clear()
    assert not lru

    lru['yet_another'] = 5
    second_lru = LRU(max_size=1)
    assert lru.copy() == lru

    second_lru['yet_another'] = 5
    assert second_lru == lru
    assert lru == second_lru

    lru.update(LRU(max_size=2, values=[('a', 1),
                                       ('b', 2)]))
    assert len(lru) == 1
    assert 'yet_another' not in lru

    lru.setdefault('x', 2)
    assert dict(lru) == {'x': 2}
    lru.setdefault('x', 3)
    assert dict(lru) == {'x': 2}

    assert lru != second_lru
    assert second_lru != lru


def test_lru_with_dupes():
    SIZE = 2
    lru = LRU(max_size=SIZE)
    for i in [0, 0, 1, 1, 2, 2]:
        lru[i] = i
        assert _test_linkage(lru._anchor, SIZE + 1), 'linked list invalid'


def test_lru_with_dupes_2():
    "From Issue #55, h/t github.com/mt"
    SIZE = 3
    lru = LRU(max_size=SIZE)
    keys = ['A', 'A', 'B', 'A', 'C', 'B', 'D', 'E']
    for i, k in enumerate(keys):
        lru[k] = 'HIT'
        assert _test_linkage(lru._anchor, SIZE + 1), 'linked list invalid'

    return


def _test_linkage(dll, max_count=10000, prev_idx=0, next_idx=1):
    """A function to test basic invariants of doubly-linked lists (with
    links made of Python lists).

    1. Test that the list is not longer than a certain length
    2. That the forward links (indicated by `next_idx`) correspond to
    the backward links (indicated by `prev_idx`).

    The `dll` parameter is the root/anchor link of the list.
    """
    start = cur = dll
    i = 0
    prev = None
    while 1:
        if i > max_count:
            raise Exception("did not return to anchor link after %r rounds"
                            % max_count)
        if prev is not None and cur is start:
            break
        prev = cur
        cur = cur[next_idx]
        if cur[prev_idx] is not prev:
            raise Exception('prev_idx does not point to prev at i = %r' % i)
        i += 1

    return True


def test_cached_dec():
    lru = LRU()
    inner_func = CountingCallable()
    func = cached(lru)(inner_func)

    assert inner_func.call_count == 0
    func()
    assert inner_func.call_count == 1
    func()
    assert inner_func.call_count == 1
    func('man door hand hook car door')
    assert inner_func.call_count == 2

    return


def test_unscoped_cached_dec():
    lru = LRU()
    inner_func = CountingCallable()
    func = cached(lru)(inner_func)

    other_inner_func = CountingCallable()
    other_func = cached(lru)(other_inner_func)

    assert inner_func.call_count == 0
    func('a')
    assert inner_func.call_count == 1
    func('a')

    other_func('a')
    assert other_inner_func.call_count == 0
    return


def test_callable_cached_dec():
    lru = LRU()
    get_lru = lambda: lru

    inner_func = CountingCallable()
    func = cached(get_lru)(inner_func)

    assert inner_func.call_count == 0
    func()
    assert inner_func.call_count == 1
    func()
    assert inner_func.call_count == 1

    lru.clear()

    func()
    assert inner_func.call_count == 2
    func()
    assert inner_func.call_count == 2

    print(repr(func))

    return


def test_cachedmethod():
    class Car(object):
        def __init__(self, cache=None):
            self.h_cache = LRI() if cache is None else cache
            self.door_count = 0
            self.hook_count = 0
            self.hand_count = 0

        @cachedmethod('h_cache')
        def hand(self, *a, **kw):
            self.hand_count += 1

        @cachedmethod(lambda obj: obj.h_cache)
        def hook(self, *a, **kw):
            self.hook_count += 1

        @cachedmethod('h_cache', scoped=False)
        def door(self, *a, **kw):
            self.door_count += 1

    car = Car()

    # attribute name-style
    assert car.hand_count == 0
    car.hand('h', a='nd')
    assert car.hand_count == 1
    car.hand('h', a='nd')
    assert car.hand_count == 1

    # callable-style
    assert car.hook_count == 0
    car.hook()
    assert car.hook_count == 1
    car.hook()
    assert car.hook_count == 1

    # Ensure that non-selfish caches share the cache nicely
    lru = LRU()
    car_one = Car(cache=lru)
    assert car_one.door_count == 0
    car_one.door('bob')
    assert car_one.door_count == 1
    car_one.door('bob')
    assert car_one.door_count == 1

    car_two = Car(cache=lru)
    assert car_two.door_count == 0
    car_two.door('bob')
    assert car_two.door_count == 0

    # try unbound for kicks
    Car.door(Car(), 'bob')

    # always check the repr
    print(repr(car_two.door))
    print(repr(Car.door))
    return


def test_cachedmethod_maintains_func_abstraction():
    ABC = ABCMeta('ABC', (object,), {})

    class Car(ABC):

        def __init__(self, cache=None):
            self.h_cache = LRI() if cache is None else cache
            self.hand_count = 0

        @cachedmethod('h_cache')
        @abstractmethod
        def hand(self, *a, **kw):
            self.hand_count += 1

    with pytest.raises(TypeError):
        Car()


def test_cachedproperty():
    class Proper(object):
        def __init__(self):
            self.expensive_func = CountingCallable()

        @cachedproperty
        def useful_attr(self):
            """Useful DocString"""
            return self.expensive_func()

    prop = Proper()

    assert prop.expensive_func.call_count == 0
    assert prop.useful_attr == 1
    assert prop.expensive_func.call_count == 1
    assert prop.useful_attr == 1
    assert prop.expensive_func.call_count == 1

    # Make sure original DocString is accessible
    assert Proper.useful_attr.__doc__ == "Useful DocString"

    prop.useful_attr += 1  # would not be possible with normal properties
    assert prop.useful_attr == 2

    delattr(prop, 'useful_attr')
    assert prop.expensive_func.call_count == 1
    assert prop.useful_attr
    assert prop.expensive_func.call_count == 2

    repr(Proper.useful_attr)


def test_cachedproperty_maintains_func_abstraction():
    ABC = ABCMeta('ABC', (object,), {})

    class AbstractExpensiveCalculator(ABC):

        @cachedproperty
        @abstractmethod
        def calculate(self):
            pass

    with pytest.raises(TypeError):
        AbstractExpensiveCalculator()


def test_min_id_map():
    import sys
    if '__pypy__' in sys.builtin_module_names:
        return  # TODO: pypy still needs some work

    midm = MinIDMap()

    class Foo(object):
        def __init__(self, val):
            self.val = val

    # use this circular array to have them periodically collected
    ref_wheel = [None, None, None]

    for i in range(1000):
        nxt = Foo(i)
        ref_wheel[i % len(ref_wheel)] = nxt
        assert midm.get(nxt) <= len(ref_wheel)
        if i % 10 == 0:
            midm.drop(nxt)

    # test __iter__
    assert sorted([f.val for f in list(midm)[:10]]) == list(range(1000 - len(ref_wheel), 1000))

    items = list(midm.iteritems())
    assert isinstance(items[0][0], Foo)
    assert sorted(item[1] for item in items) == list(range(0, len(ref_wheel)))


def test_threshold_counter():
    tc = ThresholdCounter(threshold=0.1)
    tc.add(1)

    assert tc.items() == [(1, 1)]

    tc.update([2] * 10)

    assert tc.get(1) == 0

    tc.add(5)
    assert 5 in tc

    assert len(list(tc.elements())) == 11

    assert tc.threshold == 0.1
    assert tc.get_common_count() == 11
    assert tc.get_uncommon_count() == 1  # bc the initial 1 was dropped
    assert round(tc.get_commonality(), 2) == 0.92
    assert tc.most_common(2) == [(2, 10), (5, 1)]
    assert list(tc.elements()) == ([2] * 10) + [5]

    assert tc[2] == 10
    assert len(tc) == 2
    assert sorted(tc.keys()) == [2, 5]
    assert sorted(tc.values()) == [1, 10]
    assert sorted(tc.items()) == [(2, 10), (5, 1)]
