import pytest
import frozendict as cool
from frozendict import frozendict
from collections import OrderedDict
from collections.abc import MutableSequence, Sequence
from array import array
from types import MappingProxyType
from frozendict import FreezeError, FreezeWarning


class A:
    def __init__(self, x):
        self.x = x


class BaseSeq(Sequence):

    def __init__(self, seq):
        self._items = list(seq)
        
    def __getitem__(self, i):
        return self._items[i]
    
    def __len__(self):
        return len(self._items)    


class FrozenSeqA(BaseSeq):
    pass


class FrozenSeqB(BaseSeq):
    pass


class MutableSeq(BaseSeq, MutableSequence):
    
    def __delitem__(self, i):
        del self._items[i]
    
    def __setitem__(self, i, v):
        self._items[i] = v
        
    def insert(self, index, value):
        self._items.insert(index, value)


def custom_a_converter(a):
    return frozendict(**a.__dict__, y="mbuti")


def custom_inverse_converter(o):
    return dict(**o, y="mbuti")


@pytest.fixture
def before_cure_inverse():
    return [frozendict(a={1: 2})]


@pytest.fixture
def after_cure_inverse():
    return (frozendict(a=frozendict({1: 2}), y="mbuti"), )


@pytest.fixture
def a():
    a = A(3)
    
    return a


@pytest.fixture
def before_cure(a):
    return {"x": [
        5, 
        frozendict(y = {5, "b", memoryview(b"b")}), 
        array("B", (0, 1, 2)), 
        OrderedDict(a=bytearray(b"a")),
        MappingProxyType({2: []}),
        a
    ]}
    

@pytest.fixture
def after_cure():
    return frozendict(x = (
        5, 
        frozendict(y = frozenset({5, "b", memoryview(b"b")})), 
        (0, 1, 2), 
        frozendict(a = b'a'),
        MappingProxyType({2: ()}),
        frozendict(x = 3),
    ))


@pytest.fixture
def after_cure_a(a):
    return custom_a_converter(a)


def test_deepfreeze(before_cure, after_cure):
    assert cool.deepfreeze(before_cure) == after_cure


def test_register_bad_to_convert():
    with pytest.raises(ValueError):
        cool.register(5, 7)


def test_register_bad_converter():
    with pytest.raises(ValueError):
        cool.register(frozendict, 7)


def test_unregister_not_present():
    with pytest.raises(FreezeError):
        cool.unregister(frozendict)


def test_deepfreeze_bad_custom_converters_key(before_cure):
    with pytest.raises(ValueError):
        cool.deepfreeze(before_cure, custom_converters={7: 7})


def test_deepfreeze_bad_custom_converters_val(before_cure):
    with pytest.raises(ValueError):
        cool.deepfreeze(before_cure, custom_converters={frozendict: 7})


def test_deepfreeze_bad_custom_inverse_converters_key(before_cure):
    with pytest.raises(ValueError):
        cool.deepfreeze(before_cure, custom_inverse_converters={7: 7})


def test_deepfreeze_bad_custom_inverse_converters_val(before_cure):
    with pytest.raises(ValueError):
        cool.deepfreeze(
            before_cure,
            custom_inverse_converters = {frozendict: 7}
        )


def test_register_custom(a):
    cool.register(A, custom_a_converter)
    assert cool.deepfreeze(a) == custom_a_converter(a)
    cool.unregister(A)
    assert cool.deepfreeze(a) == frozendict(a.__dict__)
    
    
def test_deepfreeze_custom(a):
    assert cool.deepfreeze(
        a,
        custom_converters={A: custom_a_converter}
    ) == custom_a_converter(a)


def test_deepfreeze_inverse(before_cure_inverse, after_cure_inverse):
    assert cool.deepfreeze(
        before_cure_inverse,
        custom_inverse_converters={frozendict: custom_inverse_converter}
    ) == after_cure_inverse


def test_register_inverse(before_cure_inverse, after_cure_inverse):
    with pytest.warns(FreezeWarning):
        cool.register(
            frozendict,
            custom_inverse_converter,
            inverse=True
        )
    
    assert cool.deepfreeze(before_cure_inverse) == after_cure_inverse


def test_prefer_forward():
    assert isinstance(
        cool.deepfreeze(
            [FrozenSeqA((0, 1, 2))],
            custom_converters={FrozenSeqA: FrozenSeqB},
            custom_inverse_converters={FrozenSeqA: MutableSeq}
            )[0],
        FrozenSeqB
        )

def test_original_immutate():
    unfrozen = {
        "int": 1,
        "nested": {"int": 1},
    }

    frozen = cool.deepfreeze(unfrozen)
    
    assert type(unfrozen["nested"]) is dict
