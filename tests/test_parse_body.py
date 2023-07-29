import polars as pl
from polarify import polarify
from polars.testing.parametric import dataframes, column
from polars.testing import assert_frame_equal
from hypothesis import given


@polarify
def transformed_signum(x: pl.Expr) -> pl.Expr:
    s = 0
    if x > 0:
        s = 1
    elif x < 0:
        s = -1
    return s


def literal_signum(x: int) -> int:
    s = 0
    if x > 0:
        s = 1
    elif x < 0:
        s = -1
    return s

@given(df=dataframes(column("x", dtype=pl.Int8), min_size=1))
def test_transform_signum(df: pl.DataFrame):
    x = pl.col("x")
    assert_frame_equal(
        df.select(transformed_signum(x).alias("apply")),
        df.apply(lambda r: literal_signum(r[0])),
        check_dtype=False,
    )


@polarify
def transformed_early_return(x: pl.Expr) -> pl.Expr:
    if x > 0:
        return 1
    return 0

def literal_early_return(x: int) -> int:
    if x > 0:
        return 1
    return 0

@given(df=dataframes(column("x", dtype=pl.Int8), min_size=1))
def test_transform_early_return(df: pl.DataFrame):
    x = pl.col("x")
    assert_frame_equal(
        df.select(transformed_early_return(x).alias("apply")),
        df.apply(lambda r: literal_early_return(r[0])),
        check_dtype=False,
    )

@polarify
def transformed_assign_both_branches(x: pl.Expr) -> pl.Expr:
    if x > 0:
        s = 1
    else:
        s = -1
    return s

def literal_assign_both_branches(x: int) -> int:
    if x > 0:
        s = 1
    else:
        s = -1
    return s

@given(df=dataframes(column("x", dtype=pl.Int8), min_size=1))
def test_transform_assign_both_branches(df: pl.DataFrame):
    x = pl.col("x")
    assert_frame_equal(
        df.select(transformed_assign_both_branches(x).alias("apply")),
        df.apply(lambda r: literal_assign_both_branches(r[0])),
        check_dtype=False,
    )

@polarify
def transformed_multiple_if_else(x: pl.Expr) -> pl.Expr:
    if x > 0:
        s = 1
    elif x < 0:
        s = -1
    else:
        s = 0
    return s

def literal_multiple_if_else(x: int) -> int:
    if x > 0:
        s = 1
    elif x < 0:
        s = -1
    else:
        s = 0
    return s

@given(df=dataframes(column("x", dtype=pl.Int8), min_size=1))
def test_transform_multiple_if_else(df: pl.DataFrame):
    x = pl.col("x")
    assert_frame_equal(
        df.select(transformed_multiple_if_else(x).alias("apply")),
        df.apply(lambda r: literal_multiple_if_else(r[0])),
        check_dtype=False,
    )

@polarify
def transformed_nested_if_else(x: pl.Expr) -> pl.Expr:
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

def literal_nested_if_else(x: int) -> int:
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

@given(df=dataframes(column("x", dtype=pl.Int8), min_size=1))
def test_transform_nested_if_else(df: pl.DataFrame):
    x = pl.col("x")
    assert_frame_equal(
        df.select(transformed_nested_if_else(x).alias("apply")),
        df.apply(lambda r: literal_nested_if_else(r[0])),
        check_dtype=False,
    )

@polarify
def transform_assignments_inside_branch(x: pl.Expr) -> pl.Expr:
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

def literal_assignments_inside_branch(x: int) -> int:
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

@given(df=dataframes(column("x", dtype=pl.Int8), min_size=1))
def test_transform_assignments_inside_branch(df: pl.DataFrame):
    x = pl.col("x")
    assert_frame_equal(
        df.select(transform_assignments_inside_branch(x).alias("apply")),
        df.apply(lambda r: literal_assignments_inside_branch(r[0])),
        check_dtype=False,
    )

@polarify
def transform_override_default(x: pl.Expr) -> pl.Expr:
    s = 0
    if x > 0:
        s = 10
    return x * s

def literal_override_default(x: int) -> int:
    s = 0
    if x > 0:
        s = 10
    return x * s

@given(df=dataframes(column("x", dtype=pl.Int8), min_size=1))
def test_transform_override_default(df: pl.DataFrame):
    x = pl.col("x")
    assert_frame_equal(
        df.select(transform_override_default(x).alias("apply")),
        df.apply(lambda r: literal_override_default(r[0])),
        check_dtype=False,
    )

@polarify
def transform_no_if_else(x: pl.Expr) -> pl.Expr:
    s = x * 10
    k = x - 3
    k = k * 2
    return s * k

def literal_no_if_else(x: int) -> int:
    s = x * 10
    k = x - 3
    k = k * 2
    return s * k

@given(df=dataframes(column("x", dtype=pl.Int8), min_size=1))
def test_transform_no_if_else(df: pl.DataFrame):
    x = pl.col("x")
    assert_frame_equal(
        df.select(transform_no_if_else(x).alias("apply")),
        df.apply(lambda r: literal_no_if_else(r[0])),
        check_dtype=False,
    )