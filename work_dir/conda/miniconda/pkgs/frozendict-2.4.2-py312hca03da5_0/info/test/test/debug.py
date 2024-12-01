#!/usr/bin/env python3

import frozendict

assert frozendict.c_ext

from frozendict import frozendict
from uuid import uuid4
import pickle
from copy import copy, deepcopy
from collections.abc import MutableMapping
import tracemalloc
import gc
import sys


def getUuid():
    return str(uuid4())


class F(frozendict):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)


class FMissing(frozendict):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)
    
    def __missing__(self, key):
        return key


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


def print_info(klass, iterations, func):
    try:
        name = func.__name__
    except AttributeError:
        name = func
    
    print(
        (
            f"Class = {klass.__name__} - Loops: {iterations} - " +
            f"Evaluating: {name}"
        ),
        flush=True
    )


def print_sep():
    print("-" * 72, flush=True)


def trace(iterations = 100, mult = 10.0):
    def decorator(func):
        def wrapper():
            header = (
                f"Loops: {iterations} - Multiplier: {mult} " +
                f"Evaluating: {func.__name__}"
            )
            
            print(header,  flush=True)
            
            tracemalloc.start()

            snapshot1 = tracemalloc.take_snapshot().filter_traces(
                (tracemalloc.Filter(True, __file__), )
            )

            for i in range(iterations):
                func()
            
            gc.collect()

            snapshot2 = tracemalloc.take_snapshot().filter_traces(
                (tracemalloc.Filter(True, __file__), )
            )

            top_stats = snapshot2.compare_to(snapshot1, 'lineno')
            tracemalloc.stop()
            
            for stat in top_stats:
                if stat.count_diff * mult > iterations:
                    header = (
                        f"Error. count diff: {stat.count_diff}, " +
                        f"stat: {stat}"
                    )
                    
                    print(header, flush=True)
                    
                    sys.exit(1)
        
        return wrapper
         
    return decorator


key_in = getUuid()
dict_1 = {key_in: 0}
dict_tmp = {getUuid(): i for i in range(1, 1000)}
dict_1.update(dict_tmp)
generator_1 = ((key, val) for key, val in dict_1.items())
key_notin = getUuid()
dict_2 = {getUuid(): i for i in range(1000)}
dict_3 = {i: i for i in range(1000)}
dict_hole = dict_1.copy()
del dict_hole[key_in]
dict_unashable = dict_1.copy()
dict_unashable.update({getUuid(): []})
dict_1_items = tuple(dict_1.items())
dict_1_keys = tuple(dict_1.keys())
dict_1_keys_set = set(dict_1_keys)

functions = []


@trace(iterations = 300, mult = 1.5)
def func_1():
    pickle.loads(pickle.dumps(fd_1))


functions.append(func_1)


@trace(iterations = 200, mult = 1.5)
def func_2():
    pickle.loads(pickle.dumps(iter(fd_1.keys())))


functions.append(func_2)


@trace(iterations = 300, mult = 1.5)
def func_3():
    pickle.loads(pickle.dumps(iter(fd_1.items())))


functions.append(func_3)


@trace(iterations = 400, mult = 1.5)
def func_4():
    pickle.loads(pickle.dumps(iter(fd_1.values())))


functions.append(func_4)


@trace()
def func_5():
    frozendict_class({})


functions.append(func_5)


@trace()
def func_7():
    frozendict_class([])


functions.append(func_7)


@trace()
def func_8():
    frozendict_class({}, **{})


functions.append(func_8)


@trace()
def func_9():
    frozendict_class(**dict_1)


functions.append(func_9)


@trace()
def func_10():
    frozendict_class(dict_1, **dict_2)


functions.append(func_10)


@trace()
def func_11():
    frozendict_class(fd_1)


functions.append(func_11)


@trace()
def func_12():
    frozendict_class(generator_1)


functions.append(func_12)


@trace()
def func_13():
    frozendict_class(dict_hole)


functions.append(func_13)


@trace()
def func_14():
    fd_1.copy()


functions.append(func_14)


@trace()
def func_15():
    fd_1 == dict_1


functions.append(func_15)


@trace()
def func_16():
    fd_1 == fd_1


functions.append(func_16)


@trace()
def func_17():
    fd_1 != dict_hole


functions.append(func_17)


@trace()
def func_18():
    fd_1 != dict_2


functions.append(func_18)


@trace()
def func_19():
    fd_1 == dict_hole


functions.append(func_19)


@trace()
def func_20():
    fd_1 == dict_2


functions.append(func_20)


@trace()
def func_21():
    frozendict_class(dict_1)


functions.append(func_21)


@trace()
def func_22():
    frozendict_class(dict_1_items)


functions.append(func_22)


@trace()
def func_23():
    tuple(fd_1.keys())


functions.append(func_23)


@trace()
def func_24():
    tuple(fd_1.values())


functions.append(func_24)


@trace()
def func_25():
    tuple(fd_1.items())


functions.append(func_25)


@trace()
def func_26():
    frozendict_class.fromkeys(dict_1)


functions.append(func_26)


@trace()
def func_27():
    frozendict_class.fromkeys(dict_1, 1)


functions.append(func_27)


@trace()
def func_28():
    frozendict_class.fromkeys(dict_1_keys)


functions.append(func_28)


@trace()
def func_29():
    frozendict_class.fromkeys(dict_1_keys, 1)


functions.append(func_29)


@trace()
def func_30():
    frozendict_class.fromkeys(dict_1_keys_set)


functions.append(func_30)


@trace()
def func_31():
    frozendict_class.fromkeys(dict_1_keys_set, 1)


functions.append(func_31)


@trace()
def func_32():
    repr(fd_1)


functions.append(func_32)


@trace()
def func_33():
    fd_1 | dict_2


functions.append(func_33)


@trace()
def func_34():
    hash(fd_1)


functions.append(func_34)


@trace()
def func_35():
    frozendict_class() == frozendict_class()


functions.append(func_35)


@trace()
def func_36():
    tuple(reversed(fd_1))


functions.append(func_36)


@trace()
def func_37():
    tuple(reversed(fd_1.keys()))


functions.append(func_37)


@trace()
def func_38():
    tuple(reversed(fd_1.items()))


functions.append(func_38)


@trace()
def func_39():
    tuple(reversed(fd_1.values()))


functions.append(func_39)


@trace()
def func_40():
    iter(fd_1).__length_hint__()
    

functions.append(func_40)


@trace()
def func_41():
    len(fd_1)


functions.append(func_41)


@trace()
def func_42():
    len(fd_1.keys())


functions.append(func_42)


@trace()
def func_43():
    len(fd_1.items())


functions.append(func_43)


@trace()
def func_44():
    len(fd_1.values())


functions.append(func_44)


@trace()
def func_45():
    fd_1.keys().mapping == fd_1


functions.append(func_45)


@trace()
def func_46():
    fd_1.items().mapping == fd_1


functions.append(func_46)


@trace()
def func_47():
    fd_1.values().mapping == fd_1


functions.append(func_47)


@trace()
def func_48():
    fd_1[key_in]


functions.append(func_48)


@trace()
def func_49():
    fd_1.get(key_in)


functions.append(func_49)


@trace()
def func_50():
    fd_1.get(key_notin)


functions.append(func_50)


@trace()
def func_51():
    fd_1.get(key_notin, 1)


functions.append(func_51)


@trace()
def func_52():
    key_in in fd_1


functions.append(func_52)


@trace()
def func_53():
    key_notin in fd_1


functions.append(func_53)


@trace()
def func_54():
    fd_1.copy()


functions.append(func_54)


@trace()
def func_55():
    copy(fd_1)


functions.append(func_55)


@trace()
def func_56():
    deepcopy(fd_1)


functions.append(func_56)


@trace()
def func_57():
    deepcopy(fd_unashable)


functions.append(func_57)


@trace()
def func_58():
    fd_1.keys() == dict_1.keys()


functions.append(func_58)


@trace()
def func_59():
    fd_1.items() == dict_1.items()


functions.append(func_59)


@trace()
def func_60():
    key_notin in fd_1.keys()


functions.append(func_60)


@trace()
def func_61():
    (key_notin, 0) in fd_1.items()


functions.append(func_61)


@trace()
def func_62():
    FMissing(fd_1)[0]


functions.append(func_62)


@trace()
def func_63():
    mp = Map(dict_1)
    frozendict_class(mp) == dict_1


functions.append(func_63)


@trace()
def func_64():
    fd_1.keys().isdisjoint(dict_3)


functions.append(func_64)


@trace()
def func_65():
    fd_1.keys().isdisjoint(fd_1)


functions.append(func_65)


@trace()
def func_66():
    fd_1.items().isdisjoint(dict_3.items())


functions.append(func_66)


@trace()
def func_67():
    fd_1.items().isdisjoint(fd_1.items())


functions.append(func_67)


@trace()
def func_68():
    fd_unashable.keys() - fd_1.keys()


functions.append(func_68)


@trace()
def func_69():
    fd_1.items() - frozendict_class(dict_hole).items()


functions.append(func_69)


@trace()
def func_70():
    fd_1.keys() & frozendict_class(dict_hole).keys()


functions.append(func_70)


@trace()
def func_71():
    fd_1.items() & frozendict_class(dict_hole).items()


functions.append(func_71)


@trace()
def func_72():
    fd_1.keys() | frozendict_class(dict_2).keys()


functions.append(func_72)


@trace()
def func_73():
    fd_1.items() | frozendict_class(dict_2).items()


functions.append(func_73)


@trace()
def func_74():
    fd_1.keys() ^ frozendict_class(dict_hole).keys()


functions.append(func_74)


@trace()
def func_75():
    fd_1.items() ^ frozendict_class(dict_hole).items()


functions.append(func_75)


@trace()
def func_76():
    frozendict_class(dict_unashable)


functions.append(func_76)


@trace()
def func_77():
    frozendict_class(dict_3)


functions.append(func_77)


@trace()
def func_78():
    frozendict_class()


functions.append(func_78)


@trace()
def func_79():
    frozendict_class(dict_hole).keys() < fd_1.keys()


functions.append(func_79)


@trace()
def func_80():
    frozendict_class(dict_hole).keys() <= fd_1.keys()


functions.append(func_80)


@trace()
def func_81():
    frozendict_class(dict_hole).items() < fd_1.items()


functions.append(func_81)


@trace()
def func_82():
    fd_1.keys() > frozendict_class(dict_hole).keys()


functions.append(func_82)


@trace()
def func_83():
    fd_1.keys() >= frozendict_class(dict_hole).keys()


functions.append(func_83)


@trace()
def func_84():
    fd_1.items() > frozendict_class(dict_hole).items()


functions.append(func_84)


@trace()
def func_85():
    fd_1.items() >= frozendict_class(dict_hole).items()


functions.append(func_85)


@trace()
def func_86():
    fd_1.set(key_in, 1000)


functions.append(func_86)


@trace()
def func_87():
    fd_1.set(key_notin, 1000)


functions.append(func_87)


@trace()
def func_88():
    fd_1.delete(key_in)


functions.append(func_88)


@trace()
def func_89():
    fd_1.setdefault(key_in)


functions.append(func_89)


@trace()
def func_90():
    fd_1.setdefault(key_notin)


functions.append(func_90)


@trace()
def func_91():
    fd_1.setdefault(key_notin, 1000)


functions.append(func_91)


@trace()
def func_92():
    fd_1.key()


functions.append(func_92)


@trace()
def func_93():
    fd_1.key(0)


functions.append(func_93)


@trace()
def func_94():
    fd_1.key(-1)


functions.append(func_94)


@trace()
def func_95():
    fd_1.value()


functions.append(func_95)


@trace()
def func_96():
    fd_1.value(0)


functions.append(func_96)


@trace()
def func_97():
    fd_1.value(-1)


functions.append(func_97)


@trace()
def func_98():
    fd_1.item()


functions.append(func_98)


@trace()
def func_99():
    fd_1.item(0)


functions.append(func_99)


@trace()
def func_100():
    fd_1.item(-1)


functions.append(func_100)


@trace()
def func_101():
    for _ in fd_1:
        pass


functions.append(func_101)


@trace()
def func_102():
    for _ in iter(fd_1):
        pass


functions.append(func_102)


@trace()
def func_103():
    for _ in fd_1.keys():
        pass


functions.append(func_103)


@trace()
def func_104():
    for _ in fd_1.values():
        pass


functions.append(func_104)


@trace()
def func_105():
    for _ in fd_1.items():
        pass


functions.append(func_105)


@trace()
def func_106():
    try:
        hash(fd_unashable)
    except TypeError:
        pass


functions.append(func_106)


@trace()
def func_107():
    try:
        fd_1[key_notin]
    except KeyError:
        pass


functions.append(func_107)


@trace()
def func_108():
    try:
        fd_1.key(len(fd_1))
    except IndexError:
        pass
    

functions.append(func_108)


@trace()
def func_109():
    try:
        fd_1.value(len(fd_1))
    except IndexError:
        pass


functions.append(func_109)


@trace()
def func_110():
    try:
        fd_1.item(len(fd_1))
    except IndexError:
        pass


functions.append(func_110)


print_sep()

for frozendict_class in (frozendict, F):
    print_info(
        frozendict_class, 
        1, 
        "frozendict_class(dict_1)"
    )
    
    fd_1 = frozendict_class(dict_1)
    print_sep()
    print_info(
        frozendict_class, 
        1, 
        "frozendict_class(dict_unashable)"
    )
    
    fd_unashable = frozendict_class(dict_unashable)
    print_sep()
    
    for function in functions:
        print(
            f"Class = {frozendict_class.__name__} - ", 
            flush = True,
            end = ""
        )
        
        function()
        
        print_sep()
