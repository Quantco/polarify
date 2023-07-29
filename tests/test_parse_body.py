# ruff: noqa

import inspect
import polars as pl
import pytest
from hypothesis import given
from polars.testing import assert_frame_equal
from polars.testing.parametric import column, dataframes
from hypothesis.strategies import integers

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
    if x > 0:
        s = 1
    else:
        s = -1
    return s


def unary_expr(x):
    s = -x
    return s


def call_target_identity(x):
    return x


def call_expr(x):
    k = x * 2
    s = call_target_identity(k + 3)
    return s


def if_expr(x):
    s = 1 if x > 0 else -1
    return s


def if_expr2(x):
    s = 1 + (x if x > 0 else -1)
    return s


def if_expr3(x):
    s = 1 + ((3 if x < 10 else 5) if x > 0 else -1)
    return s


def compare_expr(x):
    if (0 < x) & (x < 10):
        s = 1
    else:
        s = 2
    return s


def chained_compare_expr(x):
    if 0 < x < 10:
        s = 1
    else:
        s = 2
    return s


def test_chained_compare_fail():
    with pytest.raises(ValueError):
        polarify(chained_compare_expr)


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
        if x > 1:
            s = 2
        else:
            s = 1
    elif x < 0:
        s = -1
    else:
        s = 0
    return s


def nested_if_else_expr(x):
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
    k = k * 2
    return s * k


def two_if_expr(x):
    a = 1 if x > 0 else 5
    b = 2 if x < 0 else 2
    return a + b


functions = [
    signum,
    early_return,
    assign_both_branches,
    unary_expr,
    call_expr,
    if_expr,
    if_expr2,
    if_expr3,
    compare_expr,
    multiple_if_else,
    nested_if_else,
    nested_if_else_expr,
    assignments_inside_branch,
    override_default,
    no_if_else,
    two_if_expr,
]


@pytest.fixture(scope="module", params=functions)
def test_funcs(request):
    original_func = request.param
    transformed_func = polarify(original_func)
    original_func_unparsed = inspect.getsource(original_func)
    transformed_func_unparsed = inspect.getsource(transformed_func)
    print(
        (
            f"Original:\n{original_func_unparsed}\n"
            f"Transformed:\n{transformed_func_unparsed}"
        )
    )
    return transformed_func, original_func


@given(
    df=dataframes(column("x", dtype=pl.Int64, strategy=integers(-100, 100)), min_size=1)
)
def test_transform_function(df: pl.DataFrame, test_funcs):
    x = pl.col("x")
    transformed_func, original_func = test_funcs
    assert_frame_equal(
        df.select(transformed_func(x).alias("apply")),
        df.apply(lambda r: original_func(r[0])),
        check_dtype=False,
    )
