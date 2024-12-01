import pytest
import pickle
from copy import deepcopy
import sys
from collections.abc import MutableMapping
from .base import FrozendictTestBase


pyversion = sys.version_info
pyversion_major = pyversion[0]
pyversion_minor = pyversion[1]


class Map(MutableMapping):
    def __init__(self, *args, **kwargs):
        self._dict = dict(*args, **kwargs)
    
    def __getitem__(self, key):
        return self._dict[key]
    
    def __setitem__(self, key, value):
        self._dict[key] = value
    
    def __delitem__(self, key):
        del self._dict[key]
    
    def __iter__(self):
        return iter(self._dict)
    
    def __len__(self):
        return len(self._dict)


class FrozendictCommonTest(FrozendictTestBase):
    @property
    def is_mapping_implemented(self):
        return self.c_ext or (
            pyversion_major > 3 or 
            (pyversion_major == 3 and pyversion_minor > 9)
        )
    
    @property
    def is_reversed_implemented(self):
        return self.c_ext or (
            pyversion_major > 3 or 
            (pyversion_major == 3 and pyversion_minor > 7)
        )
    
    ####################################################################
    # main tests

    def test_bool_false(self, fd_empty):
        assert not fd_empty

    def test_constructor_kwargs(self, fd2, fd_dict_2):
        assert self.FrozendictClass(**fd_dict_2) == fd2

    def test_constructor_self(self, fd):
        assert fd == self.FrozendictClass(fd, Guzzanti="Corrado")

    def test_constructor_generator(self, fd, generator_seq2):
        assert fd == self.FrozendictClass(
            generator_seq2,
            Guzzanti="Corrado"
        )

    def test_constructor_hole(self, fd_hole, fd_dict_hole):
        assert fd_hole == self.FrozendictClass(fd_dict_hole)

    def test_constructor_map(self, fd_dict):
        assert self.FrozendictClass(Map(fd_dict)) == fd_dict

    def test_normalget(self, fd):
        assert fd["Guzzanti"] == "Corrado"

    def test_keyerror(self, fd):
        with pytest.raises(KeyError):
            fd["Brignano"]

    def test_len(self, fd, fd_dict):
        assert len(fd) == len(fd_dict)

    def test_in_true(self, fd):
        assert "Guzzanti" in fd

    def test_not_in_false(self, fd):
        assert not ("Guzzanti" not in fd)

    def test_in_false(self, fd):
        assert not ("Brignano" in fd)

    def test_not_in_true(self, fd):
        assert "Brignano" not in fd

    def test_bool_true(self, fd):
        assert fd

    def test_deepcopy_unhashable(self, fd_unhashable):
        fd_copy = deepcopy(fd_unhashable)
        assert fd_copy == fd_unhashable
        assert fd_copy is not fd_unhashable

    def test_not_equal(self, fd, fd2, fd_sabina):
        assert fd != fd_sabina
        assert fd != fd2
        assert not (fd == fd_sabina)
        assert not (fd == fd2)

    def test_equals_dict(self, fd, fd_dict):
        assert fd == fd_dict

    @pytest.mark.parametrize(
            "protocol",
            range(pickle.HIGHEST_PROTOCOL + 1)
    )
    def test_pickle(self, fd, protocol):
        dump = pickle.dumps(fd, protocol=protocol)
        assert dump
        assert pickle.loads(dump) == fd

    def test_constructor_iterator(self, fd, fd_items):
        assert self.FrozendictClass(fd_items) == fd

    def test_todict(self, fd, fd_dict):
        assert dict(fd) == fd_dict

    def test_get(self, fd):
        assert fd.get("Guzzanti") == "Corrado"

    def test_get_fail(self, fd):
        default = object()
        assert fd.get("Brignano", default) is default

    def test_keys(self, fd, fd_dict):
        assert tuple(fd.keys()) == tuple(fd_dict.keys())

    def test_values(self, fd, fd_dict):
        assert tuple(fd.values()) == tuple(fd_dict.values())

    def test_items(self, fd, fd_dict):
        assert tuple(fd.items()) == tuple(fd_dict.items())

    def test_fromkeys(self, fd_sabina):
        keys = ["Corrado", "Sabina"]
        f = self.FrozendictClass.fromkeys(keys, "Guzzanti")
        assert f == fd_sabina

    def test_fromkeys_dict(self, fd_sabina, fd_dict_sabina):
        f = self.FrozendictClass.fromkeys(fd_dict_sabina, "Guzzanti")
        assert f == fd_sabina

    def test_fromkeys_set(self, fd_sabina, fd_dict_sabina):
        f = self.FrozendictClass.fromkeys(
            set(fd_dict_sabina),
            "Guzzanti"
        )
        
        assert f == fd_sabina

    def test_repr(self, fd, fd_dict, module_prefix):
        classname = self.FrozendictClass.__name__
        dict_repr = repr(fd_dict)
        assert repr(fd) == f"{module_prefix}{classname}({dict_repr})"

    def test_str(self, fd, fd_dict, module_prefix):
        classname = self.FrozendictClass.__name__
        assert str(fd) == f"{module_prefix}{classname}({repr(fd_dict)})"

    def test_format(self, fd, fd_dict, module_prefix):
        classname = self.FrozendictClass.__name__
        dict_repr = repr(fd_dict)
        assert format(fd) == f"{module_prefix}{classname}({dict_repr})"

    def test_iter(self, fd):
        items = []

        for x in iter(fd):
            items.append((x, fd[x]))

        assert tuple(items) == tuple(fd.items())

    def test_sum(self, fd, fd_dict, fd_dict_sabina):
        new_fd = fd | fd_dict_sabina
        assert type(new_fd) is self.FrozendictClass
        new_dict = dict(fd_dict)
        new_dict.update(fd_dict_sabina)
        assert new_fd == new_dict

    def test_union(self, fd_dict, fd_sabina):
        new_fd = self.FrozendictClass(fd_dict)
        id_fd = id(new_fd)
        new_fd |= fd_sabina
        assert type(new_fd) is self.FrozendictClass
        assert id_fd != id(new_fd)
        new_dict = dict(fd_dict)
        new_dict.update(fd_sabina)
        assert new_fd == new_dict

    def test_reversed(self, fd, fd_dict):
        assert (tuple(reversed(fd)) == tuple(reversed(tuple(fd_dict))))

    def test_iter_len(self, fd):
        assert iter(fd).__length_hint__() >= 0

    def test_keys_len(self, fd):
        assert len(fd.keys()) == len(fd)

    def test_items_len(self, fd):
        assert len(fd.items()) == len(fd)

    def test_values_len(self, fd):
        assert len(fd.values()) == len(fd)

    def test_equal_keys(self, fd, fd_dict):
        assert fd.keys() == fd_dict.keys()

    def test_equal_items(self, fd, fd_dict):
        assert fd.items() == fd_dict.items()

    def test_in_keys(self, fd):
        assert "Guzzanti" in fd.keys()

    def test_in_items(self, fd):
        assert ("Guzzanti", "Corrado") in fd.items()

    def test_disjoint_true_keys(self, fd, fd_sabina):
        assert fd.keys().isdisjoint(fd_sabina)

    def test_disjoint_true_items(self, fd, fd_sabina):
        assert fd.items().isdisjoint(fd_sabina.items())

    def test_disjoint_false_keys(self, fd):
        assert not fd.keys().isdisjoint(fd)

    def test_disjoint_false_items(self, fd):
        assert not fd.items().isdisjoint(fd.items())

    def test_sub_keys(self, fd, fd_dict, fd2, fd_dict_2):
        res = frozenset(fd_dict.keys()) - frozenset(fd_dict_2.keys())
        assert fd.keys() - fd2.keys() == res

    def test_sub_items(self, fd, fd_dict, fd2, fd_dict_2):
        res = frozenset(fd_dict.items()) - frozenset(fd_dict_2.items())
        assert fd.items() - fd2.items() == res

    def test_and_keys(self, fd, fd_dict, fd2, fd_dict_2):
        res = frozenset(fd_dict.keys()) & frozenset(fd_dict_2.keys())
        assert fd.keys() & fd2.keys() == res

    def test_and_items(self, fd, fd_dict, fd2, fd_dict_2):
        res = frozenset(fd_dict.items()) & frozenset(fd_dict_2.items())
        assert fd.items() & fd2.items() == res

    def test_or_keys(self, fd, fd_dict, fd2, fd_dict_2):
        res = frozenset(fd_dict.keys()) | frozenset(fd_dict_2.keys())
        assert fd.keys() | fd2.keys() == res

    def test_or_items(self, fd, fd_dict, fd2, fd_dict_2):
        res = frozenset(fd_dict.items()) | frozenset(fd_dict_2.items())
        assert fd.items() | fd2.items() == res

    def test_xor_keys(self, fd, fd_dict, fd2, fd_dict_2):
        res = frozenset(fd_dict.keys()) ^ frozenset(fd_dict_2.keys())
        assert fd.keys() ^ fd2.keys() == res

    def test_xor_items(self, fd, fd_dict, fd2, fd_dict_2):
        res = frozenset(fd_dict.items()) ^ frozenset(fd_dict_2.items())
        assert fd.items() ^ fd2.items() == res

    @pytest.mark.parametrize(
            "protocol",
            range(pickle.HIGHEST_PROTOCOL + 1)
    )
    def test_pickle_iter_key(self, fd, protocol):
        orig = iter(fd.keys())
        dump = pickle.dumps(orig, protocol=protocol)
        assert dump
        assert tuple(pickle.loads(dump)) == tuple(orig)

    @pytest.mark.parametrize(
            "protocol",
            range(pickle.HIGHEST_PROTOCOL + 1)
    )
    def test_pickle_iter_item(self, fd, protocol):
        orig = iter(fd.items())
        dump = pickle.dumps(orig, protocol=protocol)
        assert dump
        assert tuple(pickle.loads(dump)) == tuple(orig)

    @pytest.mark.parametrize(
            "protocol",
            range(pickle.HIGHEST_PROTOCOL + 1)
    )
    def test_pickle_iter_value(self, fd, protocol):
        orig = iter(fd.values())
        dump = pickle.dumps(orig, protocol=protocol)
        assert dump
        assert tuple(pickle.loads(dump)) == tuple(orig)

    def test_lt_key(self, fd, fd_hole):
        assert fd_hole.keys() < fd.keys()

    def test_gt_key(self, fd, fd_hole):
        assert fd.keys() > fd_hole.keys()

    def test_le_key(self, fd, fd_hole):
        assert fd_hole.keys() <= fd.keys()
        assert fd.keys() <= fd.keys()

    def test_ge_key(self, fd, fd_hole):
        assert fd.keys() >= fd_hole.keys()
        assert fd.keys() >= fd.keys()

    def test_lt_item(self, fd, fd_hole):
        assert fd_hole.items() < fd.items()

    def test_gt_item(self, fd, fd_hole):
        assert fd.items() > fd_hole.items()

    def test_le_item(self, fd, fd_hole):
        assert fd_hole.items() <= fd.items()
        assert fd.items() <= fd.items()

    def test_ge_item(self, fd, fd_hole):
        assert fd.items() >= fd_hole.items()
        assert fd.items() >= fd.items()
    
    def test_mapping_keys(self, fd):
        if not self.is_mapping_implemented:
            pytest.skip("mapping not implemented")
        
        assert fd.keys().mapping == fd
    
    def test_mapping_items(self, fd):
        if not self.is_mapping_implemented:
            pytest.skip("mapping not implemented")
        
        assert fd.items().mapping == fd
    
    def test_mapping_values(self, fd):
        if not self.is_mapping_implemented:
            pytest.skip("mapping not implemented")
        
        assert fd.values().mapping == fd

    def test_reversed_keys(self, fd, fd_dict):
        if not self.is_reversed_implemented:
            pytest.skip("reversed not implemented")
            
        fd_keys = tuple(reversed(fd.keys()))
        dict_keys = tuple(reversed(tuple(fd_dict.keys())))
        assert fd_keys == dict_keys

    def test_reversed_items(self, fd, fd_dict):
        if not self.is_reversed_implemented:
            pytest.skip("reversed not implemented")
            
        fd_items = tuple(reversed(fd.items()))
        dict_items = tuple(reversed(tuple(fd_dict.items())))
        assert fd_items == dict_items

    def test_reversed_values(self, fd, fd_dict):
        if not self.is_reversed_implemented:
            pytest.skip("reversed not implemented")
            
        fd_values = tuple(reversed(fd.values()))
        dict_values = tuple(reversed(tuple(fd_dict.values())))
        assert fd_values == dict_values

    ####################################################################
    # frozendict-only tests

    def test_hash(self, fd, fd_eq):
        assert hash(fd)
        assert hash(fd) == hash(fd_eq)

    def test_unhashable_value(self, fd_unhashable):
        with pytest.raises(TypeError):
            hash(fd_unhashable)

        # hash is cached
        with pytest.raises(TypeError):
            hash(fd_unhashable)

    def test_set_replace(self, fd_dict, generator_seq2):
        items = tuple(generator_seq2)
        d2 = dict(items)
        assert fd_dict != d2
        f2 = self.FrozendictClass(items)
        fd3 = f2.set("Guzzanti", "Corrado")
        assert fd3 == fd_dict

    def test_set_add(self, fd_dict):
        d2 = dict(fd_dict, a="b")
        assert fd_dict != d2
        f2 = self.FrozendictClass(fd_dict)
        fd3 = f2.set("a", "b")
        assert fd3 == d2

    def test_setdefault_notinsert(self, fd, fd_dict):
        assert fd.setdefault("Hicks") is fd

    def test_setdefault_insert_default(self, fd, fd_dict):
        fd_dict.setdefault("Allen")
        assert fd_dict == fd.setdefault("Allen")

    def test_setdefault_insert(self, fd, fd_dict):
        fd_dict.setdefault("Allen", "Woody")
        assert fd_dict == fd.setdefault("Allen", "Woody")

    def test_del(self, fd_dict):
        d2 = dict(fd_dict)
        d2["a"] = "b"
        f2 = self.FrozendictClass(d2)
        fd3 = f2.delete("a")
        assert fd3 == fd_dict

    def test_key(self, fd):
        assert fd.key() == fd.key(0) == "Guzzanti"
        assert fd.key(1) == fd.key(-2) == "Hicks"

    def test_key_out_of_range(self, fd):
        with pytest.raises(IndexError):
            fd.key(3)
        
        with pytest.raises(IndexError):
            fd.key(-4)

    def test_value(self, fd):
        assert fd.value() == fd.value(0) == "Corrado"
        assert fd.value(1) == fd.value(-2) == "Bill"

    def test_value_out_of_range(self, fd):
        with pytest.raises(IndexError):
            fd.value(3)
        
        with pytest.raises(IndexError):
            fd.value(-4)

    def test_item(self, fd):
        assert fd.item() == fd.item(0) == ("Guzzanti", "Corrado")
        assert fd.item(1) == fd.item(-2) == ("Hicks", "Bill")

    def test_item_out_of_range(self, fd):
        with pytest.raises(IndexError):
            fd.item(3)
        
        with pytest.raises(IndexError):
            fd.item(-4)

    ####################################################################
    # immutability tests

    def test_normalset(self, fd):
        with pytest.raises(TypeError):
            fd["Guzzanti"] = "Caterina"

    def test_del_error(self, fd):
        with pytest.raises(TypeError):
            del fd["Guzzanti"]

    def test_clear(self, fd):
        with pytest.raises(AttributeError):
            fd.clear()

    def test_pop(self, fd):
        with pytest.raises(AttributeError):
            fd.pop("Guzzanti")

    def test_popitem(self, fd):
        with pytest.raises(AttributeError):
            fd.popitem()

    def test_update(self, fd):
        with pytest.raises(AttributeError):
            fd.update({"Brignano": "Enrico"})

    def test_delattr(self, fd):
        with pytest.raises(AttributeError):
            del fd.items
