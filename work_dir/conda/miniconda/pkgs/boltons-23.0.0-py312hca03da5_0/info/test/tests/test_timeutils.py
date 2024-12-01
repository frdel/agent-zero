
from datetime import timedelta, date

import pytest

from boltons.timeutils import total_seconds, daterange


def test_float_total_seconds():
    """Check for floating point precision loss per
    http://bugs.python.org/issue8644 and tests in the corresponding
    diff, spurred by
    https://github.com/mahmoud/boltons/pull/13#issuecomment-93835612 .

    The funny thing is that floating point precision loss is
    definitely happening. With or without true division, in Python
    2.7's native timedelta.total_seconds() as well as
    dateutils.total_seconds. The constants in the tests below are from
    manual tests on Python 2.7.6 final. 2.6 does vary slightly, but it
    might just be a repr change.

    With these tests in mind, I'm not sure why the Python issue got
    created in the first place.

    """
    assert total_seconds(timedelta(microseconds=1)) == 1e-06
    assert total_seconds(timedelta(microseconds=-1)) == -1e-06
    assert total_seconds(timedelta(microseconds=-2)) == -2e-06
    assert total_seconds(timedelta(days=2 ** 29, microseconds=1)) == 46385646796800.0

    assert total_seconds(timedelta(seconds=123456.789012)) == 123456.789012
    assert total_seconds(timedelta(seconds=-123456.789012)) == -123456.789012


def test_daterange_years():
    new_year = date(2017, 1, 1)
    bit_rollover = date(2038, 1, 19)

    new_years_remaining = daterange(new_year, bit_rollover, step=(1, 0, 0))
    assert len(list(new_years_remaining)) == 22

    y2025 = date(2025, 1, 1)
    bakers_years_til_2025 = list(daterange(new_year, y2025, step=(1, 1, 0)))
    assert len(bakers_years_til_2025) == 8
    assert bakers_years_til_2025[-1] == date(2024, 8, 1)
    assert bakers_years_til_2025[-1] == date(2024, 8, 1)

    years_from_2025 = list(daterange(y2025, new_year, step=(-1, 0, 0),
                                     inclusive=True))

    assert years_from_2025[0] == date(2025, 1, 1)
    assert years_from_2025[-1] == date(2017, 1, 1)


def test_daterange_years_step():
    start_day = date(year=2012, month=12, day=25)
    end_day = date(year=2016, month=1, day=1)
    dates = list(daterange(start_day, end_day, step=(1, 0, 0), inclusive=False))
    expected = [date(year=2012, month=12, day=25), date(year=2013, month=12, day=25), date(year=2014, month=12, day=25), date(year=2015, month=12, day=25)]

    assert dates == expected

    dates = list(daterange(start_day, end_day, step=(0, 13, 0), inclusive=False))
    expected = [date(year=2012, month=12, day=25), date(year=2014, month=1, day=25), date(year=2015, month=2, day=25)]
    assert dates == expected
    
    
def test_daterange_infinite():
    today = date.today()
    infinite_dates = daterange(today, None)
    for i in range(10):
        assert next(infinite_dates) == today + timedelta(days=i)


def test_daterange_with_same_start_stop():
    today = date.today()

    date_range = daterange(today, today)
    with pytest.raises(StopIteration):
        next(date_range)

    date_range_inclusive = daterange(today, today, inclusive=True)
    assert next(date_range_inclusive) == today
    with pytest.raises(StopIteration):
        next(date_range_inclusive)
