import ast
from copy import copy
from typing import Dict

# TODO: Walruss
# TODO: Switch

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

def is_returning_body(stmts: list[ast.stmt]) -> bool:
    for s in stmts:
        if isinstance(s, ast.Return):
            return True
        elif isinstance(s, ast.If):
            if is_returning_body(s.body) and is_returning_body(s.orelse):
                return True
            elif is_returning_body(s.body) ^ is_returning_body(s.orelse):
                raise ValueError("All branches of a If statement must either return or not for now")
    return False

def regularize_assign_statement(stmt: ast.Assign, assignments: dict[str, ast.expr]) -> dict[str, ast.expr]:
    assignments_updated = {}
    for t in stmt.targets:
        if isinstance(t, ast.Name):
            assignments_updated[t.id] = inline_all(stmt.value, copy(assignments))
        elif isinstance(t, ast.Tuple):
            for sub_t, sub_v in zip(t.elts, stmt.value.elts):
                if isinstance(sub_t, ast.Name):
                    assignments_updated[sub_t.id] = inline_all(sub_v, copy(assignments))
                else:
                    raise ValueError(
                        f"Unsupported expression type inside of tuple: {type(sub_t)}"
                    )
        else:
            raise ValueError(f"Unsupported expression type: {type(t)}")
    return assignments_updated

def get_all_vars_changed_in_body(body: list[ast.stmt], assignments: dict[str, ast.expr]) -> dict[str, ast.expr]:
    assignments = copy(assignments)
    diff_assignments = dict()

    for s in body:
        if isinstance(s, ast.Assign):
            diff = regularize_assign_statement(s, assignments)
            assignments.update(diff)
            diff_assignments.update(diff)
        elif isinstance(s, ast.If):
            raise NotImplementedError("If statements not supported yet")
        elif isinstance(s, ast.Return):
            raise ValueError("This should not happen.")
        else:
            raise ValueError(f"Unsupported statement type: {type(s)}")

    return diff_assignments

def build_polars_when_then_otherwise(test: ast.expr, then: ast.expr, orelse: ast.expr):
    when_node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="pl", ctx=ast.Load()), attr="when", ctx=ast.Load()
        ),
        args=[test],
        keywords=[],
    )
   
    then_node = ast.Call(
        func=ast.Attribute(value=when_node, attr="then", ctx=ast.Load()),
        args=[then],
        keywords=[],
    )
    final_node = ast.Call(
        func=ast.Attribute(value=then_node, attr="otherwise", ctx=ast.Load()),
        args=[orelse],
        keywords=[],
    )
    return final_node

def parse_body(full_body: list[ast.stmt], assignments={}):
    assert len(full_body) > 0
    for i, stmt in enumerate(full_body):
        if isinstance(stmt, ast.Assign):
            # update assignments
            assignments.update(regularize_assign_statement(stmt, assignments))
        elif isinstance(stmt, ast.If):
            # Handle if statements
            if is_returning_body(stmt.body) and is_returning_body(stmt.orelse):
                # TODO: refactor
                test = inline_all(stmt.test, copy(assignments))
                when_node = ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="pl", ctx=ast.Load()), attr="when", ctx=ast.Load()
                    ),
                    args=[test],
                    keywords=[],
                )
                body = parse_body(stmt.body, assignments=copy(assignments))
                then_node = ast.Call(
                    func=ast.Attribute(value=when_node, attr="then", ctx=ast.Load()),
                    args=[body],
                    keywords=[],
                )
                orelse = parse_body(stmt.orelse, assignments=copy(assignments))
                final_node = ast.Call(
                    func=ast.Attribute(value=then_node, attr="otherwise", ctx=ast.Load()),
                    args=[orelse],
                    keywords=[],
                )
                return final_node
            elif is_returning_body(stmt.body):
                test = inline_all(stmt.test, copy(assignments))
                body = parse_body(stmt.body, assignments=copy(assignments))
                orelse_everything = parse_body(stmt.orelse + full_body[i+1:], assignments=copy(assignments))
                return build_polars_when_then_otherwise(test, body, orelse_everything)
            elif is_returning_body(stmt.orelse):
                test = ast.Call(
                    func=ast.Attribute(
                        value=inline_all(stmt.test, copy(assignments)),
                        attr="not",
                        ctx=ast.Load()
                    ),
                    args=[],
                    keywords=[],
                )
                orelse = parse_body(stmt.orelse, assignments=copy(assignments))
                body_everything = parse_body(stmt.body + full_body[i+1:], assignments=copy(assignments))
                return build_polars_when_then_otherwise(test, orelse, body_everything)
            else:
                assert not is_returning_body(stmt.orelse) and not is_returning_body(stmt.body)
                test = inline_all(stmt.test, copy(assignments))
                # TODO: inconsequent when caller / callee copies assignments
                all_vars_changed_in_body = get_all_vars_changed_in_body(stmt.body, assignments)
                all_vars_changed_in_orelse = get_all_vars_changed_in_body(stmt.orelse, assignments)
                for var in (all_vars_changed_in_body | all_vars_changed_in_orelse).keys():
                    expr = build_polars_when_then_otherwise(
                        test,
                        all_vars_changed_in_body.get(var, assignments[var]),
                        all_vars_changed_in_orelse.get(var, assignments[var])
                    )
                    assignments[var] = expr

        elif isinstance(stmt, ast.Return):
            # Handle return statements
            return inline_all(stmt.value, assignments)
        else:
            raise ValueError(f"Unsupported statement type: {type(stmt)}")


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

# TODO
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
if x > 0:
    k = 1
else:
    k = -1
return k
"""


tree = ast.parse(code)
transformed = parse_body(tree.body)
unparsed = ast.unparse(transformed)

print(ast.dump(transformed))
print(unparsed)
