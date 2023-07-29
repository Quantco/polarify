import ast
from copy import copy
from typing import Dict


def inline_all(expr, assignments):
    if isinstance(expr, ast.Name):
        if expr.id not in assignments:
            raise ValueError(f"Variable {expr.id} not defined")
        return inline_all(assignments[expr.id], assignments)
    elif isinstance(expr, ast.BinOp):
        expr.left = inline_all(expr.left, assignments)
        expr.right = inline_all(expr.right, assignments)
        return expr
    else:
        print("leaf", ast.unparse(expr), type(expr))
        return expr

def is_returning_if_body(expr: ast.If) -> bool:

    if len(expr.orelse) == 0:
        return False
    elif isinstance(expr.body[-1], ast.Return) and isinstance(expr.orelse[-1], ast.Return):
        return True
    else:
        return False

def parse_body(body: list[ast.stmt], assignments={}):
    assert len(body) > 0
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            # Handle assignments
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    assignments[t.id] = stmt.value
                elif isinstance(t, ast.Tuple):
                    for sub_t, sub_v in zip(t.elts, stmt.value.elts):
                        if isinstance(sub_t, ast.Name):
                            assignments[sub_t.id] = sub_v
                        else:
                            raise ValueError(
                                f"Unsupported expression type inside of tuple: {type(e)}"
                            )
                else:
                    raise ValueError(f"Unsupported expression type: {type(t)}")
        elif isinstance(stmt, ast.If):
            # Handle if statements
            body = parse_body(stmt.body, assignments=copy(assignments))

            if len(stmt.orelse) == 0:
                raise ValueError(f"Missing else statement:\n{ast.unparse(stmt)}")
            
            orelse = parse_body(stmt.orelse, assignments=copy(assignments))
            test = inline_all(stmt.test, assignments)

            # Translate if statements into pl.when(test).then(body).otherwise(orelse)
            # Constructing new ast.Call nodes for 'pl.when', 'then' and 'otherwise' methods
            when_node = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="pl", ctx=ast.Load()), attr="when", ctx=ast.Load()
                ),
                args=[test],
                keywords=[],
            )
            then_node = ast.Call(
                func=ast.Attribute(value=when_node, attr="then", ctx=ast.Load()),
                args=[body],
                keywords=[],
            )
            final_node = ast.Call(
                func=ast.Attribute(value=then_node, attr="otherwise", ctx=ast.Load()),
                args=[orelse],
                keywords=[],
            )
            return final_node

        elif isinstance(stmt, ast.Return):
            # Handle return statements
            return inline_all(stmt.value, assignments)
        else:
            raise ValueError(f"Unsupported statement type: {type(stmt)}")


# code = """
# c = d = 2
# x, y = pl.col("x") * c, pl.col("y") * d
# z = x + y

# if z > 0:
#     if z > 1:
#         return z
#     elif z > 0.5:
#         return 1
#     else:
#         return 0.5
# else:
#     return 0
# """

code = """
tmp1 = 1
if z > 0:
    tmp1 = 2
else:
    tmp1 = 3
return tmp1 * 2
"""

tree = ast.parse(code)
transformed = parse_body(tree.body)
unparsed = ast.unparse(transformed)

print(ast.dump(transformed))
print(unparsed)
