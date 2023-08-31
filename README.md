# polarIFy: Simplifying conditional Polars Expressions with Python 🐍 🐻‍❄️

![License][license-badge]
[![Build Status][build-badge]][build]
[![conda-forge][conda-forge-badge]][conda-forge]
[![pypi-version][pypi-badge]][pypi]
[![python-version][python-version-badge]][pypi]

[license-badge]: https://img.shields.io/github/license/quantco/polarify?style=flat-square
[build-badge]: https://img.shields.io/github/actions/workflow/status/quantco/polarify/ci.yml?style=flat-square&branch=main
[build]: https://github.com/quantco/polarify/actions/
[conda-forge]: https://prefix.dev/channels/conda-forge/packages/polarify
[conda-forge-badge]: https://img.shields.io/conda/pn/conda-forge/polarify?style=flat-square&logoColor=white&logo=conda-forge
[pypi]: https://pypi.org/project/polarify
[pypi-badge]: https://img.shields.io/pypi/v/polarify.svg?style=flat-square&logo=pypi&logoColor=white
[python-version-badge]: https://img.shields.io/pypi/pyversions/polarify?style=flat-square&logoColor=white&logo=python

Welcome to **polarIFy**, a Python function decorator that simplifies the way you write logical statements for Polars. With polarIFy, you can use Python's language structures like `if / elif / else` statements and transform them into `pl.when(..).then(..).otherwise(..)` statements. This makes your code more readable and less cumbersome to write. 🎉

## 🎯 Usage

polarIFy can automatically transform Python functions using `if / elif / else` statements into Polars expressions.

### Basic Transformation

Here's an example:

```python
@polarify
def signum(x: pl.Expr) -> pl.Expr:
    s = 0
    if x > 0:
        s = 1
    elif x < 0:
        s = -1
    return s
```

This gets transformed into:

```python
def signum(x: pl.Expr) -> pl.Expr:
    return pl.when(x > 0).then(1).otherwise(pl.when(x < 0).then(-1).otherwise(0))
```

### Handling Multiple Statements

polarIFy can also handle multiple statements like:

```python
@polarify
def multiple_if_statement(x: pl.Expr) -> pl.Expr:
    a = 1 if x > 0 else 5
    b = 2 if x < 0 else 2
    return a + b
```

which becomes:

```python
def multiple_if_statement(x):
    return pl.when(x > 0).then(1).otherwise(5) + pl.when(x < 0).then(2).otherwise(2)
```

### Handling Nested Statements

Additionally, it can handle nested statements:

```python
@polarify
def nested_if_else(x: pl.Expr) -> pl.Expr:
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
```

which becomes:

```python
def nested_if_else(x: pl.Expr) -> pl.Expr:
    return pl.when(x > 0).then(pl.when(x > 1).then(2).otherwise(1)).otherwise(pl.when(x < 0).then(-1).otherwise(0))
```

So you can still write readable row-wise python code while the `@polarify` decorator transforms it into a function that works with efficient polars expressions.

### Using a `polarify`d function

```python
import polars as pl
from polarify import polarify

@polarify
def complicated_operation(x: pl.Expr) -> pl.Expr:
    k = 0
    c = 2
    if x > 0:
        k = 1
        c = 0
        if x < 10:
            c = 1
    elif x < 0:
        k = -1
    return k * c


df = pl.DataFrame({"x": [-1, 1, 5, 10]})
result = df.select(pl.col("x"), complicated_operation(pl.col("x")))
print(result)
# shape: (4, 2)
# ┌─────┬─────────┐
# │ x   ┆ literal │
# │ --- ┆ ---     │
# │ i64 ┆ i32     │
# ╞═════╪═════════╡
# │ -1  ┆ -2      │
# │ 1   ┆ 1       │
# │ 5   ┆ 1       │
# │ 10  ┆ 0       │
# └─────┴─────────┘
```

### Displaying the transpiled polars expression

You can also display the transpiled polars expression by calling the `transform_func_to_new_source` method:

```python
from polarify import transform_func_to_new_source

def signum(x):
    s = 0
    if x > 0:
        s = 1
    elif x < 0:
        s = -1
    return s


print(f"Original function:\n{inspect.getsource(signum)}")
# Original function:
# def signum(x):
#     s = 0
#     if x > 0:
#         s = 1
#     elif x < 0:
#         s = -1
#     return s
print(f"Transformed function:\n{transform_func_to_new_source(signum)}")
# Transformed function:
# def signum_polarified(x):
#     import polars as pl
#     return pl.when(x > 0).then(1).otherwise(pl.when(x < 0).then(-1).otherwise(0))
```

TODO: complicated example with nested functions

## ⚙️ How It Works

polarIFy achieves this by parsing the AST (Abstract Syntax Tree) of the function and transforming the body into a Polars expression by inlining the different branches.
To get a more detailed understanding of what's happening under the hood, check out our [blog post](https://tech.quantco.com/2023/08/25/polarify.html) explaining how polarify works!

## 💿 Installation

### conda

```bash
conda install -c conda-forge polarify
# or micromamba
micromamba install -c conda-forge polarify
# or pixi
pixi add polarify
```

### pip

```bash
pip install polarify
```

## ⚠️ Limitations

polarIFy is still in an early stage of development and doesn't support the full Python language. Here's a list of the currently supported and unsupported operations:

### Supported operations

- `if / else / elif` statements
- binary operations (like `+`, `==`, `>`, `&`, `|`, ...)
- unary operations (like `~`, `-`, `not`, ...) (TODO)
- assignments (like `x = 1`)
- polars expressions (like `pl.col("x")`, TODO)
- side-effect free functions that return a polars expression (can be generated by `@polarify`) (TODO)

### Unsupported operations

- `for` loops
- `while` loops
- `break` statements
- `:=` walrus operator
- `match ... case` statements (TODO)
- functions with side-effects (`print`, `pl.write_csv`, ...)

## 🚀 Benchmarks

TODO: Add some benchmarks

## 📥 Development installation

```bash
pixi install
pixi run postinstall
pixi run test
```
