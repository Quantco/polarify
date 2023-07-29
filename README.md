# polarIFy: Simplifying conditional Polars Expressions with Python 🐍

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

## ⚙️ How It Works

polarIFy achieves this by parsing the AST (Abstract Syntax Tree) of the function and transforming the body into a Polars expression by inlining the different branches.

## ⚠️ Limitations

Currently, support for walrus operators (`:=`) is missing. We're actively working on adding this feature. Stay tuned for updates!

## 📥 Devlopement

You can drop into a development environment by:

```bash
$ pixi install
$ pixi run pip install --no-deps --disable-pip-version-check --no-build-isolation -e .
```
