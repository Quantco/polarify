import polars as pl
import pytest
from hypothesis import given
from polars.testing import assert_frame_equal
from polars.testing.parametric import column, dataframes

from polarify import polarify


def signum(x):
    s = 0
    if x > 0:
        s = 1
    elif x < 0:
        s = -1
    return s


def early_return(x):
    if x > 0:
        return 1
    return 0


def assign_both_branches(x):
    s = 1 if x > 0 else -1
    return s


def multiple_if_else(x):
    if x > 0:
        s = 1
    elif x < 0:
        s = -1
    else:
        s = 0
    return s


def nested_if_else(x):
    if x > 0:
        s = 2 if x > 1 else 1
    elif x < 0:
        s = -1
    else:
        s = 0
    return s


def assignments_inside_branch(x):
    if x > 0:
        s = 1
        s = s + 1
        s = x * s
    elif x < 0:
        s = -1
        s = s - 1
        s = x
    else:
        s = 0
    return s


def override_default(x):
    s = 0
    if x > 0:
        s = 10
    return x * s


def no_if_else(x):
    s = x * 10
    k = x - 3
    # k = k * 2
    return s * k


functions = [
    # signum,
    # early_return,
    # assign_both_branches,
    # multiple_if_else,
    # nested_if_else,
    # assignments_inside_branch,
    # override_default,
    no_if_else,
]


@pytest.fixture(scope="module", params=functions)
def test_funcs(request):
    return polarify(request.param), request.param


@given(df=dataframes(column("x", dtype=pl.Int8), min_size=1))
def test_transform_function(df: pl.DataFrame, test_funcs):
    x = pl.col("x")
    transformed_func, original_func = test_funcs
    assert_frame_equal(
        df.select(transformed_func(x).alias("apply")),
        df.apply(lambda r: original_func(r[0])),
        check_dtype=False,
    )
