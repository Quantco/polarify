import inspect

import polars
import pytest
from hypothesis import given
from hypothesis.strategies import integers
from packaging.version import Version
from polars import __version__ as _pl_version
from polars.testing import assert_frame_equal
from polars.testing.parametric import column, dataframes

from polarify import polarify, transform_func_to_new_source

from .functions import functions, xfail_functions

pl_version = Version(_pl_version)


@pytest.fixture(
    scope="module",
    params=functions
    + [pytest.param(f, marks=pytest.mark.xfail(reason="not implemented")) for f in xfail_functions],
)
def funcs(request):
    original_func = request.param
    transformed_func = polarify(original_func)
    original_func_unparsed = inspect.getsource(original_func)
    # build ast from transformed function as format as string
    transformed_func_unparsed = transform_func_to_new_source(original_func)
    print(f"Original:\n{original_func_unparsed}\nTransformed:\n{transformed_func_unparsed}")
    return transformed_func, original_func


# chunking + apply is broken for polars < 0.18.1
# https://github.com/pola-rs/polars/pull/9211
# only relevant for our test setup, not for the library itself
@given(
    df=dataframes(
        column("x", dtype=polars.Int64, strategy=integers(-100, 100)),
        min_size=1,
        chunked=False if pl_version < Version("0.18.1") else None,
    )
)
def test_transform_function(df: polars.DataFrame, funcs):
    x = polars.col("x")
    transformed_func, original_func = funcs

    if pl_version < Version("0.19.0"):
        df_with_transformed_func = df.select(transformed_func(x).alias("apply"))
        df_with_applied_func = df.apply(lambda r: original_func(r[0]))
    else:
        df_with_transformed_func = df.select(transformed_func(x).alias("map"))
        df_with_applied_func = df.map_rows(lambda r: original_func(r[0]))

    assert_frame_equal(
        df_with_transformed_func,
        df_with_applied_func,
        check_dtype=False,
    )
