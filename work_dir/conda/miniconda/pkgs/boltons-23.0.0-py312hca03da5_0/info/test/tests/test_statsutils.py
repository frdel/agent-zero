# -*- coding: utf-8 -*-
from boltons.statsutils import Stats


def test_stats_basic():
    da = Stats(range(20))
    assert da.mean == 9.5
    assert round(da.std_dev, 2) == 5.77
    assert da.variance == 33.25
    assert da.skewness == 0
    assert round(da.kurtosis, 1) == 1.9
    assert da.median == 9.5


def _test_pearson():
    import random
    from statsutils import pearson_type

    def get_pt(dist):
        vals = [dist() for x in range(10000)]
        pt = pearson_type(vals)
        return pt

    for x in range(3):
        # pt = get_pt(dist=lambda: random.normalvariate(15, 5))  # expect 0, normal
        # pt = get_pt(dist=lambda: random.weibullvariate(2, 3))  # gets 1, beta, weibull not specifically supported
        # pt = get_pt(dist=lambda: random.gammavariate(2, 3))  # expect 3, gamma
        # pt = get_pt(dist=lambda: random.betavariate(2, 3))  # expect 1, beta
        # pt = get_pt(dist=lambda: random.expovariate(0.2))  # expect 3, beta
        pt = get_pt(dist=lambda: random.uniform(0.0, 10.0))  # gets 2
        print('pearson type:', pt)

        # import pdb;pdb.set_trace()
