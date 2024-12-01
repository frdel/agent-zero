
from boltons.statsutils import Stats


# [round(random.normalvariate(10, 3), 3) for i in range(100)]
NORM_DATA = [12.975, 8.341, 12.27, 12.799, 15.443, 6.739, 10.572,
             14.863, 3.723, 9.825, 7.716, 12.218, 11.641, 9.02,
             13.037, 11.175, 13.156, 11.706, 8.184, 13.306, 9.845,
             11.665, 14.298, 12.021, 8.419, 10.209, 10.698, 6.559,
             10.346, 9.895, 11.742, 13.391, 10.587, 6.639, 10.23,
             8.841, 10.511, 6.033, 5.767, 8.482, 9.517, 9.039, 11.111,
             13.845, 4.331, 5.323, 14.486, 14.875, 10.005, 6.367,
             12.18, 11.69, 13.97, 4.14, 7.979, 11.114, 4.126, 10.028,
             9.295, 10.078, 14.615, 7.055, 7.641, 9.037, 9.933,
             10.077, 14.174, 14.645, 10.398, 10.238, 9.067, 4.841,
             13.159, 15.829, 8.464, 7.47, 11.858, 9.885, 11.978,
             5.418, 12.19, 8.206, 10.755, 6.455, 10.019, 11.594,
             9.082, 10.245, 12.321, 8.508, 9.711, 5.5, 15.001, 9.922,
             7.864, 7.794, 10.546, 9.203, 8.798, 9.853]


SIMPLE_RANGE_DATA = range(110)

LAYER_RANGE_DATA = (list(range(100))
                    + list(range(20, 80))
                    + list(range(40, 60)))

EMPTY_DATA = []

ALL_DATASETS = [EMPTY_DATA, LAYER_RANGE_DATA, SIMPLE_RANGE_DATA, NORM_DATA]


def test_check_sum():
    for data in ALL_DATASETS:
        for bin_size in [0, 1, 10, 99]:
            # bin_size=0 tests freedman
            stats = Stats(data)
            hist_counts = stats.get_histogram_counts()
            hist_counts_sum = sum([c for _, c in hist_counts])
            assert len(data) == hist_counts_sum
            if not data:
                continue

            assert min(data) >= hist_counts[0][0]
            assert max(data) >= hist_counts[-1][0]
    return


def test_norm_regression():
    stats = Stats(NORM_DATA)

    assert stats.format_histogram(width=80) == NORM_DATA_FREEDMAN_OUTPUT
    assert stats.format_histogram(10, width=80) == NORM_DATA_TEN_BIN_OUTPUT

    subpar_bin_out = stats.format_histogram([12.0], width=80)
    assert subpar_bin_out == NORM_DATA_SINGLE_SUBPAR_BIN_OUTPUT

    format_bin_out = stats.format_histogram(5,
                                            width=80,
                                            format_bin=lambda b: '%sms' % b)
    assert format_bin_out == NORM_DATA_FORMAT_BIN_OUTPUT


NORM_DATA_FREEDMAN_OUTPUT = """\
 3.7:  5 ################
 5.2: 10 ################################
 6.8:  9 #############################
 8.3: 21 ###################################################################
 9.9: 22 ######################################################################
11.4: 16 ###################################################
13.0: 10 ################################
14.5:  7 ######################"""

NORM_DATA_TEN_BIN_OUTPUT = """\
 3.7:  5 ##############
 4.9:  5 ##############
 6.1:  6 #################
 7.3: 12 ##################################
 8.5: 11 ###############################
 9.7: 25 ######################################################################
10.9: 12 ##################################
12.1: 12 ##################################
13.4:  5 ##############
14.6:  7 ####################"""

# make sure the minimum gets added
NORM_DATA_SINGLE_SUBPAR_BIN_OUTPUT = """\
 3.7: 75 ######################################################################
12.0: 25 #######################"""

NORM_DATA_FORMAT_BIN_OUTPUT = """\
 3.7ms: 10 ###################
 6.1ms: 18 ##################################
 8.5ms: 36 ####################################################################
10.9ms: 24 #############################################
13.4ms: 12 #######################"""


def main():
    print(Stats(NORM_DATA).format_histogram(10))


if __name__ == '__main__':
    main()
