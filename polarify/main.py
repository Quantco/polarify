import ast
from copy import copy
from typing import Union

# TODO: make walrus throw ValueError
# TODO: Switch

Assignments = dict[str, ast.expr]


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


# ruff: noqa: N802
class InlineTransformer(ast.NodeTransformer):
    def __init__(self, assignments: Assignments):
        self.assignments = assignments

    @classmethod
    def inline_expr(cls, expr: ast.expr, assignments: Assignments) -> ast.expr:
        return cls(assignments).visit(expr)

    def visit_Name(self, node):
        if node.id in self.assignments:
            return self.visit(self.assignments[node.id])
        else:
            return node

    def visit_BinOp(self, node):
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        return node

    def visit_UnaryOp(self, node):
        node.operand = self.visit(node.operand)
        return node

    def visit_Call(self, node):
        node.args = [self.visit(arg) for arg in node.args]
        node.keywords = [
            ast.keyword(arg=k.arg, value=self.visit(k.value)) for k in node.keywords
        ]
        return node

    def visit_IfExp(self, node):
        test = self.visit(node.test)
        body = self.visit(node.body)
        orelse = self.visit(node.orelse)
        return build_polars_when_then_otherwise(test, body, orelse)

    def visit_Constant(self, node):
        return node

    def visit_Compare(self, node):
        if len(node.comparators) > 1:
            raise ValueError("Polars can't handle chained comparisons")
        node.left = self.visit(node.left)
        node.comparators = [self.visit(c) for c in node.comparators]
        return node

    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression type: {type(node)}")


def is_returning_body(stmts: list[ast.stmt]) -> bool:
    for s in stmts:
        if isinstance(s, ast.Return):
            return True
        elif isinstance(s, ast.If):
            if is_returning_body(s.body) and is_returning_body(s.orelse):
                return True
            elif is_returning_body(s.body) ^ is_returning_body(s.orelse):
                # TODO: investigate
                raise ValueError(
                    "All branches of a If statement must either return or not for now"
                )
    return False


def handle_assign(stmt: ast.Assign, assignments: Assignments) -> Assignments:
    assignments = copy(assignments)
    diff_assignments = {}

    for t in stmt.targets:
        if isinstance(t, ast.Name):
            new_value = InlineTransformer.inline_expr(stmt.value, assignments)
            assignments[t.id] = new_value
            diff_assignments[t.id] = new_value
        elif isinstance(t, (ast.List, ast.Tuple)):
            assert (
                isinstance(stmt.value, ast.Tuple)
                or isinstance(stmt.value, ast.List)
                and len(t.elts) == len(stmt.value.elts)
            )
            for sub_t, sub_v in zip(t.elts, stmt.value.elts):
                diff = handle_assign(
                    ast.Assign(targets=[sub_t], value=sub_v), assignments
                )
                assignments.update(diff)
                diff_assignments.update(diff)
        else:
            raise ValueError(
                f"Unsupported expression type inside assignment target: {type(t)}"
            )
    return diff_assignments


def handle_non_returning_if(stmt: ast.If, assignments: Assignments) -> Assignments:
    assignments = copy(assignments)
    assert not is_returning_body(stmt.orelse) and not is_returning_body(stmt.body)
    test = InlineTransformer.inline_expr(stmt.test, assignments)

    diff_assignments = {}
    all_vars_changed_in_body = get_all_vars_changed_in_body(stmt.body, assignments)
    all_vars_changed_in_orelse = get_all_vars_changed_in_body(stmt.orelse, assignments)

    def updated_or_default_assignments(var: str, diff: Assignments) -> ast.expr:
        if var in diff:
            return diff[var]
        elif var in assignments:
            return assignments[var]
        else:
            raise ValueError(
                f"Variable {var} has to be either defined in"
                " all branches or have a previous defintion"
            )

    for var in all_vars_changed_in_body | all_vars_changed_in_orelse:
        expr = build_polars_when_then_otherwise(
            test,
            updated_or_default_assignments(var, all_vars_changed_in_body),
            updated_or_default_assignments(var, all_vars_changed_in_orelse),
        )
        assignments[var] = expr
        diff_assignments[var] = expr
    return diff_assignments


def get_all_vars_changed_in_body(
    body: list[ast.stmt], assignments: Assignments
) -> Assignments:
    assignments = copy(assignments)
    diff_assignments = {}

    for s in body:
        if isinstance(s, ast.Assign):
            diff = handle_assign(s, assignments)
            assignments.update(diff)
            diff_assignments.update(diff)
        elif isinstance(s, ast.If):
            if_diff = handle_non_returning_if(s, assignments)
            assignments.update(if_diff)
            diff_assignments.update(if_diff)
        elif isinstance(s, ast.Return):
            raise ValueError("This should not happen.")
        else:
            raise ValueError(f"Unsupported statement type: {type(s)}")

    return diff_assignments


def parse_body(
    full_body: list[ast.stmt], assignments: Union[Assignments, None] = None
) -> ast.expr:
    if assignments is None:
        assignments = {}
    assignments = copy(assignments)
    assert len(full_body) > 0
    for i, stmt in enumerate(full_body):
        if isinstance(stmt, ast.Assign):
            # update assignments
            assignments.update(handle_assign(stmt, assignments))
        elif isinstance(stmt, ast.If):
            if is_returning_body(stmt.body) and is_returning_body(stmt.orelse):
                test = InlineTransformer.inline_expr(stmt.test, assignments)
                body = parse_body(stmt.body, assignments)
                orelse = parse_body(stmt.orelse, assignments)
                return build_polars_when_then_otherwise(test, body, orelse)
            elif is_returning_body(stmt.body):
                test = InlineTransformer.inline_expr(stmt.test, assignments)
                body = parse_body(stmt.body, assignments)
                orelse_everything = parse_body(
                    stmt.orelse + full_body[i + 1 :], assignments
                )
                return build_polars_when_then_otherwise(test, body, orelse_everything)
            elif is_returning_body(stmt.orelse):
                test = ast.Call(
                    func=ast.Attribute(
                        value=InlineTransformer.inline_expr(stmt.test, assignments),
                        attr="not",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[],
                )
                orelse = parse_body(stmt.orelse, assignments)
                body_everything = parse_body(
                    stmt.body + full_body[i + 1 :], assignments
                )
                return build_polars_when_then_otherwise(test, orelse, body_everything)
            else:
                diff = handle_non_returning_if(stmt, assignments)
                assignments.update(diff)

        elif isinstance(stmt, ast.Return):
            if stmt.value is None:
                raise ValueError("return needs a value")
            # Handle return statements
            return InlineTransformer.inline_expr(stmt.value, assignments)
        else:
            raise ValueError(f"Unsupported statement type: {type(stmt)}")
    raise ValueError("Missing return statement")
