# -*- coding: utf-8 -*-

import sys

from boltons.listutils import SplayList, BarrelList


def test_splay_list():
    splay = SplayList(range(10))
    splay.swap(0, 9)
    assert splay[0] == 9
    assert splay[-1] == 0

    splay.shift(-2)
    assert splay[0] == 8
    assert splay[-1] == 0
    assert len(splay) == 10


def test_barrel_list():
    bl = BarrelList()
    bl.insert(0, 0)
    assert bl[0] == 0
    assert len(bl) == 1
    bl.insert(1, 1)
    assert list(bl) == [0, 1]
    bl.insert(0, -1)
    assert list(bl) == [-1, 0, 1]
    bl.extend((range(int(1e5))))
    assert len(bl) == (1e5 + 3)
    bl._balance_list(0)
    assert len(bl) == (1e5 + 3)
    bl.pop(50000)
    assert len(bl) == (1e5 + 3 - 1)

    bl2 = BarrelList(TEST_INTS)
    bl2.sort()
    assert list(bl2[:5]) == [0, 74, 80, 96, 150]
    assert list(bl2[:-5:-1]) == [50508, 46607, 46428, 43442]

    # a hundred thousand integers
    bl3 = BarrelList(range(int(1e5)))
    for i in range(10000):
        # move the middle ten thou to the beginning
        bl3.insert(0, bl3.pop(len(bl3) // 2))
    assert len(bl3) == 1e5  # length didn't change
    assert bl3[0] == 40001  # first value changed as expected
    assert bl3[-1] == sorted(bl3)[-1]  # last value didn't change

    del bl3[10:5000]
    assert bl3[0] == 40001
    assert len(bl3) == 1e5 - (5000 - 10)  # length stayed co
    bl3[:20:2] = range(0, -10, -1)
    assert bl3[6] == -3  # some truly tricky stepping/slicing works

# roughly increasing random integers
# [ord(i) * x for i, x in zip(os.urandom(1024), range(1024))]
TEST_INTS = [0, 74, 96, 183, 456, 150, 1098, 665, 1752, 1053, 190,
             561, 2244, 2964, 2534, 750, 80, 612, 3780, 2698, 1320,
             4935, 5324, 3220, 672, 2925, 6474, 6507, 3892, 4814,
             1470, 6913, 6112, 6072, 7854, 8540, 4212, 7770, 8702,
             1404, 2240, 902, 5250, 10320, 9680, 8775, 2392, 11327,
             10368, 8085, 7750, 9333, 8008, 11395, 6858, 8690, 14112,
             5358, 13572, 3304, 9000, 11712, 1426, 12033, 11136,
             10270, 10626, 11189, 7208, 966, 9380, 16614, 10368,
             11680, 8214, 16350, 4712, 5082, 13572, 15879, 6800, 8667,
             17548, 9628, 3360, 19550, 1634, 20619, 1232, 17978,
             22950, 10829, 5612, 22692, 10058, 21375, 19680, 5626,
             15582, 18216, 2200, 20402, 24174, 3090, 19864, 2520,
             15794, 18511, 4212, 18530, 8470, 7992, 5152, 4294, 456,
             6095, 26564, 9477, 14042, 7259, 14520, 28677, 9394, 5289,
             7812, 1625, 17514, 7493, 24704, 903, 33150, 1834, 11352,
             20615, 32562, 540, 6256, 12878, 276, 17236, 6300, 25380,
             9088, 27742, 4752, 33930, 7008, 22491, 7992, 2831, 34200,
             18271, 22648, 6426, 15862, 26660, 29484, 2826, 14378,
             26553, 16000, 18998, 28998, 16626, 19024, 22275, 18426,
             21042, 29064, 30927, 26010, 14193, 9976, 30621, 12354,
             33600, 40832, 20178, 20292, 12709, 26640, 29865, 23660,
             20862, 34592, 28305, 24180, 38709, 18800, 11907, 28120,
             34189, 4992, 8106, 14938, 6435, 12936, 31914, 1782, 995,
             9800, 28542, 22018, 27608, 30396, 28700, 26986, 50508,
             5616, 46607, 2310, 41356, 26712, 8733, 43442, 33755,
             21384, 40145, 26160, 46428, 30360]


test_barrel_list()

if __name__ == '__main__':
    _TUNE_SETUP = """\
from boltons.listutils import BarrelList
bl = BarrelList()
bl._size_factor = %s
bl.extend(range(int(%s)))
"""

    def tune():
        from collections import defaultdict
        import gc
        from timeit import timeit
        data_size = 1e5
        old_size_factor = size_factor = 512
        all_times = defaultdict(list)
        min_times = {}
        step = 512
        while abs(step) > 4:
            gc.collect()
            for x in range(3):
                tottime = timeit('bl.insert(0, bl.pop(len(bl)//2))',
                                 _TUNE_SETUP % (size_factor, data_size),
                                 number=10000)
                all_times[size_factor].append(tottime)
            min_time = round(min(all_times[size_factor]), 3)
            min_times[size_factor] = min_time
            print(size_factor, min_time, step)
            if min_time > (min_times[old_size_factor] + 0.002):
                step = -step // 2
            old_size_factor = size_factor
            size_factor += step
        print(tottime)

    try:
        tune()  # main()
    except Exception as e:
        import pdb;pdb.post_mortem()
        raise
