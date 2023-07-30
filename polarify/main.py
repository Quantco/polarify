from __future__ import annotations

import ast
from copy import copy, deepcopy
from dataclasses import dataclass

# TODO: make walrus throw ValueError
# TODO: Switch


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
    def __init__(self, assignments: dict[str, ast.expr]):
        self.assignments = assignments

    @classmethod
    def inline_expr(cls, expr: ast.expr, assignments: dict[str, ast.expr]) -> ast.expr:
        return cls(assignments).visit(deepcopy(expr))

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


@dataclass
class Assignments:
    assignments: dict[str, ast.expr]

    def handle_assign(self, stmt: ast.Assign):
        def _handle_assign(stmt: ast.Assign, assignments: dict[str, ast.expr]):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    new_value = InlineTransformer.inline_expr(stmt.value, assignments)
                    assignments[t.id] = new_value
                elif isinstance(t, (ast.List, ast.Tuple)):
                    assert (
                        isinstance(stmt.value, ast.Tuple)
                        or isinstance(stmt.value, ast.List)
                        and len(t.elts) == len(stmt.value.elts)
                    )
                    for sub_t, sub_v in zip(t.elts, stmt.value.elts):
                        diff = _handle_assign(
                            ast.Assign(targets=[sub_t], value=sub_v), assignments
                        )
                        assignments.update(diff)
                else:
                    raise ValueError(
                        f"Unsupported expression type inside assignment target: {type(t)}"
                    )

        _handle_assign(stmt, self.assignments)


@dataclass
class ReturnExpr:
    expr: ast.expr


@dataclass
class BranchState:
    state: Assignments | ReturnExpr


@dataclass
class Conditional:
    test: ast.expr
    then: Node
    orelse: Node


@dataclass
class Node:
    node: BranchState | Conditional

    def handle_assignment(self, expr: ast.Assign):
        if isinstance(self.node, BranchState):
            if isinstance(self.node.state, Assignments):
                self.node.state.handle_assign(expr)
        else:
            self.node.then.handle_assignment(expr)
            self.node.orelse.handle_assignment(expr)

    def handle_if(self, stmt: ast.If):
        if isinstance(self.node, BranchState):
            if isinstance(self.node.state, Assignments):
                self.node = Conditional(
                    test=InlineTransformer.inline_expr(
                        stmt.test, self.node.state.assignments
                    ),
                    then=parse_body(stmt.body, copy(self.node.state.assignments)),
                    orelse=parse_body(stmt.orelse, copy(self.node.state.assignments)),
                )
        else:
            self.node.then.handle_if(stmt)
            self.node.orelse.handle_if(stmt)

    def handle_return(self, value: ast.expr):
        if isinstance(self.node, BranchState):
            if isinstance(self.node.state, Assignments):
                self.node.state = ReturnExpr(
                    expr=InlineTransformer.inline_expr(
                        value, self.node.state.assignments
                    )
                )
        else:
            self.node.then.handle_return(value)
            self.node.orelse.handle_return(value)

    def check_all_branches_return(self):
        if isinstance(self.node, BranchState):
            return bool(isinstance(self.node.state, ReturnExpr))
        else:
            return (
                self.node.then.check_all_branches_return()
                and self.node.orelse.check_all_branches_return()
            )


def is_returning_body(stmts: list[ast.stmt]) -> bool:
    for s in stmts:
        if isinstance(s, ast.Return):
            return True
        elif isinstance(s, ast.If):
            return bool(is_returning_body(s.body) and is_returning_body(s.orelse))
    return False


def parse_body(
    full_body: list[ast.stmt], assignments: dict[str, ast.expr] | None = None
) -> Node:
    if assignments is None:
        assignments = {}
    state = Node(BranchState(Assignments(assignments)))
    for stmt in full_body:
        if isinstance(stmt, ast.Assign):
            state.handle_assignment(stmt)
        elif isinstance(stmt, ast.If):
            state.handle_if(stmt)
        elif isinstance(stmt, ast.Return):
            if stmt.value is None:
                raise ValueError("return needs a value")

            state.handle_return(stmt.value)
            break
        else:
            raise ValueError(f"Unsupported statement type: {type(stmt)}")
    return state


def transform_tree_into_expr(node: Node) -> ast.expr:
    if isinstance(node.node, BranchState):
        if isinstance(node.node.state, ReturnExpr):
            return node.node.state.expr
        else:
            raise ValueError("Not all branches return")
    else:
        return build_polars_when_then_otherwise(
            node.node.test,
            transform_tree_into_expr(node.node.then),
            transform_tree_into_expr(node.node.orelse),
        )
