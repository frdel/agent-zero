# -*- coding: utf-8 -*-

import sys
import pytest

from boltons.dictutils import OMD, OneToOne, ManyToMany, FrozenDict, subdict, FrozenHashError


_ITEMSETS = [[],
             [('a', 1), ('b', 2), ('c', 3)],
             [('A', 'One'), ('A', 'One'), ('A', 'One')],
             [('Z', -1), ('Y', -2), ('Y', -2)],
             [('a', 1), ('b', 2), ('a', 3), ('c', 4)]]


def test_dict_init():
    d = dict(_ITEMSETS[1])
    omd = OMD(d)

    assert omd['a'] == 1
    assert omd['b'] == 2
    assert omd['c'] == 3

    assert len(omd) == 3
    assert omd.getlist('a') == [1]
    assert omd == d


def test_todict():
    omd = OMD(_ITEMSETS[2])
    assert len(omd) == 1
    assert omd['A'] == 'One'

    d = omd.todict(multi=True)
    assert len(d) == 1
    assert d['A'] == ['One', 'One', 'One']

    flat = omd.todict()
    assert flat['A'] == 'One'

    for itemset in _ITEMSETS:
        omd = OMD(itemset)
        d = dict(itemset)

        flat = omd.todict()
        assert flat == d
    return


def test_eq():
    omd = OMD(_ITEMSETS[3])
    assert omd == omd
    assert not (omd != omd)

    omd2 = OMD(_ITEMSETS[3])
    assert omd == omd2
    assert omd2 == omd
    assert not (omd != omd2)

    d = dict(_ITEMSETS[3])
    assert d == omd
    omd3 = OMD(d)
    assert omd != omd3


def test_copy():
    for itemset in _ITEMSETS:
        omd = OMD(itemset)
        omd_c = omd.copy()
        assert omd == omd_c
        if omd_c:
            omd_c.pop(itemset[0][0])
            assert omd != omd_c
    return


def test_clear():
    for itemset in _ITEMSETS:
        omd = OMD(itemset)
        omd.clear()
        assert len(omd) == 0
        assert not omd
        omd.clear()
        assert not omd
        omd['a'] = 22
        assert omd
        omd.clear()
        assert not omd


def test_types():
    try:
        from collections.abc import MutableMapping
    except ImportError:
        from collections import MutableMapping

    omd = OMD()
    assert isinstance(omd, dict)
    assert isinstance(omd, MutableMapping)


def test_multi_correctness():
    size = 100
    redun = 5

    _rng = range(size)
    _rng_redun = list(range(size//redun)) * redun
    _pairs = zip(_rng_redun, _rng)

    omd = OMD(_pairs)
    for multi in (True, False):
        vals = [x[1] for x in omd.iteritems(multi=multi)]
        strictly_ascending = all([x < y for x, y in zip(vals, vals[1:])])
        assert strictly_ascending
    return


def test_kv_consistency():
    for itemset in _ITEMSETS:
        omd = OMD(itemset)

        for multi in (True, False):
            items = omd.items(multi=multi)
            keys = omd.keys(multi=multi)
            values = omd.values(multi=multi)

            assert keys == [x[0] for x in items]
            assert values == [x[1] for x in items]
    return


def test_update_basic():
    omd = OMD(_ITEMSETS[1])
    omd2 = OMD({'a': 10})
    omd.update(omd2)
    assert omd['a'] == 10
    assert omd.getlist('a') == [10]

    omd2_c = omd2.copy()
    omd2_c.pop('a')
    assert omd2 != omd2_c


def test_update():
    for first, second in zip(_ITEMSETS, _ITEMSETS[1:]):
        omd1 = OMD(first)
        omd2 = OMD(second)
        ref1 = dict(first)
        ref2 = dict(second)

        omd1.update(omd2)
        ref1.update(ref2)
        assert omd1.todict() == ref1

        omd1_repr = repr(omd1)
        omd1.update(omd1)
        assert omd1_repr == repr(omd1)


def test_update_extend():
    for first, second in zip(_ITEMSETS, _ITEMSETS[1:] + [[]]):
        omd1 = OMD(first)
        omd2 = OMD(second)
        ref = dict(first)
        orig_keys = set(omd1)

        ref.update(second)
        omd1.update_extend(omd2)
        for k in omd2:
            assert len(omd1.getlist(k)) >= len(omd2.getlist(k))

        assert omd1.todict() == ref
        assert orig_keys <= set(omd1)


def test_invert():
    for items in _ITEMSETS:
        omd = OMD(items)
        iomd = omd.inverted()
        # first, test all items made the jump
        assert len(omd.items(multi=True)) == len(iomd.items(multi=True))

        for val in omd.values():
            assert val in iomd  # all values present as keys


def test_poplast():
    for items in _ITEMSETS[1:]:
        omd = OMD(items)
        assert omd.poplast() == items[-1][-1]


def test_pop():
    omd = OMD()
    omd.add('even', 0)
    omd.add('odd', 1)
    omd.add('even', 2)

    assert omd.pop('odd') == 1
    assert omd.pop('odd', 99) == 99
    try:
        omd.pop('odd')
        assert False
    except KeyError:
        pass

    assert len(omd) == 1
    assert len(omd.items(multi=True)) == 2


def test_addlist():
    omd = OMD()
    omd.addlist('a', [1, 2, 3])
    omd.addlist('b', [4, 5])

    assert omd.keys() == ['a', 'b']
    assert len(list(omd.iteritems(multi=True))) == 5

    e_omd = OMD()
    e_omd.addlist('a', [])
    assert e_omd.keys() == []
    assert len(list(e_omd.iteritems(multi=True))) == 0


def test_pop_all():
    omd = OMD()
    omd.add('even', 0)
    omd.add('odd', 1)
    omd.add('even', 2)

    assert omd.popall('odd') == [1]
    assert len(omd) == 1
    try:
        omd.popall('odd')
        assert False
    except KeyError:
        pass
    assert omd.popall('odd', None) is None

    assert omd.popall('even') == [0, 2]
    assert len(omd) == 0
    assert omd.popall('nope', None) is None

    assert OMD().popall('', None) is None


def test_reversed():
    try:
        from collections import OrderedDict
    except:
        # skip on python 2.6
        return
    for items in _ITEMSETS:
        omd = OMD(items)
        od = OrderedDict(items)
        for ik, ok in zip(reversed(od), reversed(omd)):
            assert ik == ok

    r100 = range(100)
    omd = OMD(zip(r100, r100))
    for i in r100:
        omd.add(i, i)
    r100 = list(reversed(r100))
    assert list(reversed(omd)) == r100

    omd = OMD()
    assert list(reversed(omd)) == list(reversed(omd.keys()))
    for i in range(20):
        for j in range(i):
            omd.add(i, i)
    assert list(reversed(omd)) == list(reversed(omd.keys()))


def test_setdefault():
    omd = OMD()
    empty_list = []
    x = omd.setdefault('1', empty_list)
    assert x is empty_list
    y = omd.setdefault('2')
    assert y is None
    assert omd.setdefault('1', None) is empty_list

    e_omd = OMD()
    e_omd.addlist(1, [])
    assert e_omd.popall(1, None) is None
    assert len(e_omd) == 0

## END OMD TESTS

import string

def test_subdict():
    cap_map = dict([(x, x.upper()) for x in string.hexdigits])
    assert len(cap_map) == 22
    assert len(subdict(cap_map, drop=['a'])) == 21
    assert 'a' not in subdict(cap_map, drop=['a'])

    assert len(subdict(cap_map, keep=['a', 'b'])) == 2


def test_subdict_keep_type():
    omd = OMD({'a': 'A'})
    assert subdict(omd) == omd
    assert type(subdict(omd)) is OMD


def test_one_to_one():
    e = OneToOne({1:2})
    def ck(val, inv):
        assert (e, e.inv) == (val, inv)
    ck({1:2}, {2:1})
    e[2] = 3
    ck({1:2, 2:3}, {3:2, 2:1})
    e.clear()
    ck({}, {})
    e[1] = 1
    ck({1:1}, {1:1})
    e[1] = 2
    ck({1:2}, {2:1})
    e[3] = 2
    ck({3:2}, {2:3})
    del e[3]
    ck({}, {})
    e[1] = 2
    e.inv[2] = 3
    ck({3:2}, {2:3})
    del e.inv[2]
    ck({}, {})
    assert OneToOne({1:2, 3:4}).copy().inv == {2:1, 4:3}
    e[1] = 2
    e.pop(1)
    ck({}, {})
    e[1] = 2
    e.inv.pop(2)
    ck({}, {})
    e[1] = 2
    e.popitem()
    ck({}, {})
    e.setdefault(1)
    ck({1: None}, {None: 1})
    e.inv.setdefault(2)
    ck({1: None, None: 2}, {None: 1, 2: None})
    e.clear()
    e.update({1:2}, cat="dog")
    ck({1:2, "cat":"dog"}, {2:1, "dog":"cat"})

    # try various overlapping values
    oto = OneToOne({'a': 0, 'b': 0})
    assert len(oto) == len(oto.inv) == 1

    oto['c'] = 0
    assert len(oto) == len(oto.inv) == 1
    assert oto.inv[0] == 'c'

    oto.update({'z': 0, 'y': 0})
    assert len(oto) == len(oto.inv) == 1

    # test out unique classmethod
    with pytest.raises(ValueError):
        OneToOne.unique({'a': 0, 'b': 0})

    return


def test_many_to_many():
    m2m = ManyToMany()
    assert len(m2m) == 0
    assert not m2m
    m2m.add(1, 'a')
    assert m2m
    m2m.add(1, 'b')
    assert len(m2m) == 1
    assert m2m[1] == frozenset(['a', 'b'])
    assert m2m.inv['a'] == frozenset([1])
    del m2m.inv['a']
    assert m2m[1] == frozenset(['b'])
    assert 1 in m2m
    del m2m.inv['b']
    assert 1 not in m2m
    m2m[1] = ('a', 'b')
    assert set(m2m.iteritems()) == set([(1, 'a'), (1, 'b')])
    m2m.remove(1, 'a')
    m2m.remove(1, 'b')
    assert 1 not in m2m
    m2m.update([(1, 'a'), (2, 'b')])
    assert m2m.get(2) == frozenset(('b',))
    assert m2m.get(3) == frozenset(())
    assert ManyToMany(['ab', 'cd']) == ManyToMany(['ba', 'dc']).inv
    assert ManyToMany(ManyToMany(['ab', 'cd'])) == ManyToMany(['ab', 'cd'])

    m2m = ManyToMany({'a': 'b'})
    m2m.replace('a', 'B')
    # also test the repr while we're at it
    assert repr(m2m) == repr(ManyToMany([("B", "b")]))
    assert repr(m2m).startswith('ManyToMany(') and 'B' in repr(m2m)


def test_frozendict():
    efd = FrozenDict()
    assert isinstance(efd, dict)
    assert len(efd) == 0
    assert not efd
    assert repr(efd) == "FrozenDict({})"

    data = {'a': 'A', 'b': 'B'}
    fd = FrozenDict(data)

    assert bool(fd)
    assert len(fd) == 2
    assert fd['a'] == 'A'
    assert fd['b'] == 'B'
    assert sorted(fd.keys()) == ['a', 'b']
    assert sorted(fd.values()) == ['A', 'B']
    assert sorted(fd.items()) == [('a', 'A'), ('b', 'B')]
    assert 'a' in fd
    assert 'c' not in fd

    assert hash(fd)
    fd_map = {'fd': fd}
    assert fd_map['fd'] is fd

    with pytest.raises(TypeError):
        fd['c'] = 'C'
    with pytest.raises(TypeError):
        del fd['a']
    with pytest.raises(TypeError):
        fd.update(x='X')
    with pytest.raises(TypeError):
        fd.setdefault('x', [])
    with pytest.raises(TypeError):
        fd.pop('c')
    with pytest.raises(TypeError):
        fd.popitem()
    with pytest.raises(TypeError):
        fd.clear()


    import pickle
    fkfd = FrozenDict.fromkeys([2, 4, 6], value=0)
    assert pickle.loads(pickle.dumps(fkfd)) == fkfd

    assert sorted(fkfd.updated({8: 0}).keys()) == [2, 4, 6, 8]

    # try something with an unhashable value
    unfd = FrozenDict({'a': ['A']})
    with pytest.raises(TypeError) as excinfo:
        {unfd: 'val'}
    assert excinfo.type is FrozenHashError
    with pytest.raises(TypeError) as excinfo2:
        {unfd: 'val'}
    assert excinfo.value is excinfo2.value  # test cached exception

    return


@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires python3.9 or higher")
def test_frozendict_ior():
    data = {'a': 'A', 'b': 'B'}
    fd = FrozenDict(data)

    with pytest.raises(TypeError, match=".*FrozenDict.*immutable.*"):
        fd |= fd


def test_frozendict_api():
    # all the read-only methods that are fine
    through_methods = ['__class__',
                       '__cmp__',
                       '__contains__',
                       '__delattr__',
                       '__dir__',
                       '__eq__',
                       '__format__',
                       '__ge__',
                       '__getattribute__',
                       '__getstate__',
                       '__getitem__',
                       '__getstate__',
                       '__gt__',
                       '__init__',
                       '__iter__',
                       '__le__',
                       '__len__',
                       '__lt__',
                       '__ne__',
                       '__new__',
                       '__or__',
                       '__reduce__',
                       '__reversed__',
                       '__ror__',
                       '__setattr__',
                       '__sizeof__',
                       '__str__',
                       'copy',
                       'get',
                       'has_key',
                       'items',
                       'iteritems',
                       'iterkeys',
                       'itervalues',
                       'keys',
                       'values',
                       'viewitems',
                       'viewkeys',
                       'viewvalues']

    fd = FrozenDict()
    ret = []
    for attrname in dir(fd):
        if attrname == '_hash':  # in the dir, even before it's set
            continue
        attr = getattr(fd, attrname)
        if not callable(attr):
            continue

        if getattr(FrozenDict, attrname) == getattr(dict, attrname, None) and attrname not in through_methods:
            assert attrname == False
            ret.append(attrname)

    import copy
    assert copy.copy(fd) is fd
