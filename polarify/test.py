# ruff: noqa: PLR2004

import polars as pl

from polarify import polarify

code = """
c = d = 2
x, y = pl.col("x") * c, pl.col("y") * d
z = x + y

if z > 0:
    if z > 1:
        return z
    elif z > 0.5:
        return 1
    else:
        return 0.5
else:
    return 0
"""

code = """
k = 0
if x > 0:
    return k
else:
    k = 1

if x > 1:
    k = 2
else:
    return k

if x >= 3:
    return 15

return k * 2
"""

code = """
k = 0
if x > 0:
    k = 1
else:
    k = -1
return k
"""

code = """
k = 0
if x > 0:
    k = 1
elif x < 0:
    k = -1
return k
"""

code = """
k = 0
c = 2
if x > 0:
    k = 1
    c = 0
return k * c
"""

code = """
k = 0
c = 2
if x > 0:
    k = 1
    c = 0
elif x < 0:
    k = -1
return k * c
"""


code = """
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
"""


@polarify
def f(x: pl.Expr) -> pl.Expr:
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


a = f(pl.col("x"))
print(type(a))


# tree = ast.parse(code)
# transformed = parse_body(tree.body)
# unparsed = ast.unparse(transformed)

# print(unparsed)
