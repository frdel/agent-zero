# -*- coding: utf-8 -*-

from boltons.queueutils import SortedPriorityQueue, HeapPriorityQueue


def _test_priority_queue(queue_type):
    pq = queue_type()
    item1 = 'a'
    item2 = 'b'
    item3 = 'c'
    pq.add(item1)
    pq.remove(item1)

    # integer priorities
    pq.add(item1, 2)
    pq.add(item2, 9)
    pq.add(item3, 7)
    assert len(pq) == 3
    assert item2 == pq.pop()
    assert len(pq) == 2
    assert item3 == pq.pop()
    assert len(pq) == 1
    assert item1 == pq.pop()
    assert len(pq) == 0

    # float priorities
    pq.add(item1, 0.2)
    pq.add(item2, 0.9)
    pq.add(item3, 0.7)
    assert len(pq) == 3
    assert item2 == pq.pop()
    assert len(pq) == 2
    assert item3 == pq.pop()
    assert len(pq) == 1
    assert item1 == pq.pop()
    assert len(pq) == 0

    try:
        pq.pop()
    except IndexError:
        pass
    else:
        assert False, 'priority queue should be empty'
    return


def test_heap_queue():
    _test_priority_queue(HeapPriorityQueue)


def test_sorted_queue():
    _test_priority_queue(SortedPriorityQueue)
