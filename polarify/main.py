from __future__ import annotations

import ast
import sys
from collections.abc import Sequence
from copy import copy, deepcopy
from dataclasses import dataclass

PY_39 = sys.version_info <= (3, 9)

# TODO: make walrus throw ValueError


@dataclass
class UnresolvedCase:
    """
    An unresolved case in a conditional statement. (if, match, etc.)
    Each case consists of a test expression and a state.
    The value of the then State is not yet resolved.
    """

    test: ast.expr
    then: State

    def __init__(self, test: ast.expr, then: State):
        self.test = test
        self.then = then


@dataclass
class ResolvedCase:
    """
    A resolved case in a conditional statement. (if, match, etc.)
    Each case consists of a test expression and a state.
    The value of the then State is resolved.
    """

    test: ast.expr
    then: ast.expr

    def __init__(self, test: ast.expr, then: ast.expr):
        self.test = test
        self.then = then

    def __iter__(self):
        return iter([self.test, self.then])


def build_polars_when_then_otherwise(body: Sequence[ResolvedCase], orelse: ast.expr) -> ast.Call:
    nodes: list[ast.Call] = []

    if not body:
        raise ValueError("No cases provided")

    for test, then in body:
        when_node = ast.Call(
            func=ast.Attribute(
                value=nodes[-1] if nodes else ast.Name(id="pl", ctx=ast.Load()),
                attr="when",
                ctx=ast.Load(),
            ),
            args=[test],
            keywords=[],
        )
        then_node = ast.Call(
            func=ast.Attribute(value=when_node, attr="then", ctx=ast.Load()),
            args=[then],
            keywords=[],
        )
        nodes.append(then_node)
    final_node = ast.Call(
        func=ast.Attribute(value=nodes[-1], attr="otherwise", ctx=ast.Load()),
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
        expr = cls(assignments).visit(deepcopy(expr))
        assert isinstance(expr, ast.expr)
        return expr

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if node.id in self.assignments:
            return self.visit(self.assignments[node.id])
        else:
            return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.BinOp:
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.UnaryOp:
        node.operand = self.visit(node.operand)
        return node

    def visit_Call(self, node: ast.Call) -> ast.Call:
        node.args = [self.visit(arg) for arg in node.args]
        node.keywords = [ast.keyword(arg=k.arg, value=self.visit(k.value)) for k in node.keywords]
        return node

    def visit_IfExp(self, node: ast.IfExp) -> ast.Call:
        test = self.visit(node.test)
        body = self.visit(node.body)
        orelse = self.visit(node.orelse)
        return build_polars_when_then_otherwise([ResolvedCase(test, body)], orelse)

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.Compare:
        if len(node.comparators) > 1:
            raise ValueError("Polars can't handle chained comparisons")
        node.left = self.visit(node.left)
        node.comparators = [self.visit(c) for c in node.comparators]
        return node

    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression type: {type(node)}")


@dataclass
class UnresolvedState:
    """
    When an execution flow is not finished (i.e., not returned) in a function, we need to keep track
    of the assignments.
    """

    assignments: dict[str, ast.expr]

    def handle_assign(self, stmt: ast.Assign):
        def _handle_assign(stmt: ast.Assign, assignments: dict[str, ast.expr]):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    new_value = InlineTransformer.inline_expr(stmt.value, assignments)
                    assignments[t.id] = new_value
                elif isinstance(t, (ast.List, ast.Tuple)):
                    if not isinstance(stmt.value, (ast.List, ast.Tuple)):
                        raise ValueError(
                            f"Assignment target is {type(t)}, but value is {type(stmt.value)}"
                        )
                    assert len(t.elts) == len(stmt.value.elts)
                    for sub_t, sub_v in zip(t.elts, stmt.value.elts):
                        _handle_assign(ast.Assign(targets=[sub_t], value=sub_v), assignments)
                else:
                    raise ValueError(
                        f"Unsupported expression type inside assignment target: {type(t)}"
                    )

        _handle_assign(stmt, self.assignments)


@dataclass
class ReturnState:
    """
    The expression of a return statement.
    """

    expr: ast.expr


@dataclass
class ConditionalState:
    """
    A list of conditional states.
    Each case consists of a test expression and a state.
    """

    body: Sequence[UnresolvedCase]
    orelse: State


@dataclass
class State:
    """
    A state in the execution flow.
    Either unresolved assignments, a return statement, or a conditional state.
    """

    node: UnresolvedState | ReturnState | ConditionalState

    def translate_match(
        self,
        subj: ast.expr | Sequence[ast.expr] | ast.Tuple,
        stmt: ast.pattern,
        guard: ast.expr | None = None,
    ):
        if isinstance(stmt, ast.MatchValue) and isinstance(subj, ast.Name):
            if guard is not None:
                return ast.BinOp(
                    left=guard,
                    op=ast.BitAnd(),
                    right=ast.Compare(
                        left=ast.Name(id=subj.id, ctx=ast.Load()),
                        ops=[ast.Eq()],
                        comparators=[stmt.value],
                    ),
                )

            return ast.Compare(
                left=ast.Name(id=subj.id, ctx=ast.Load()),
                ops=[ast.Eq()],
                comparators=[stmt.value],
            )
        elif isinstance(stmt, ast.MatchAs) and isinstance(subj, ast.Name):
            if stmt.name is not None:
                self.handle_assign(
                    ast.Assign(
                        targets=[ast.Name(id=stmt.name, ctx=ast.Store())],
                        value=ast.Name(id=subj.id, ctx=ast.Load()),
                    )
                )
            return guard
        elif isinstance(stmt, ast.MatchOr):
            return ast.BinOp(
                left=self.translate_match(subj, stmt.patterns[0], guard),
                op=ast.BitOr(),
                right=(
                    self.translate_match(subj, ast.MatchOr(patterns=stmt.patterns[1:]))
                    if stmt.patterns[2:]
                    else self.translate_match(subj, stmt.patterns[1])
                ),
            )
        elif isinstance(stmt, ast.MatchSequence):
            if isinstance(stmt.patterns[-1], ast.MatchStar):
                raise ValueError("starred patterns are not supported.")

            if isinstance(subj, ast.Tuple):
                while len(subj.elts) > len(stmt.patterns):
                    stmt.patterns.append(ast.MatchValue(value=ast.Constant(value=None)))
                left = self.translate_match(subj.elts[0], stmt.patterns[0], guard)
                right = (
                    self.translate_match(
                        subj.elts[1:],
                        ast.MatchSequence(patterns=stmt.patterns[1:]),
                    )
                    if stmt.patterns[2:]
                    else self.translate_match(subj.elts[1], stmt.patterns[1])
                )

                if left is None or right is None:
                    return left or right
                return ast.BinOp(left=left, op=ast.BitAnd(), right=right)
            raise ValueError("Matching lists is not supported.")
        else:
            raise ValueError(
                f"Incompatible match and subject types: {type(stmt)} and {type(subj)}."
            )

    def handle_assign(self, expr: ast.Assign | ast.AnnAssign):
        if isinstance(expr, ast.AnnAssign):
            expr = ast.Assign(targets=[expr.target], value=expr.value)

        if isinstance(self.node, UnresolvedState):
            self.node.handle_assign(expr)
        elif isinstance(self.node, ConditionalState):
            for case in self.node.body:
                assert isinstance(case.then, State)
                case.then.handle_assign(expr)
            self.node.orelse.handle_assign(expr)

    def handle_if(self, stmt: ast.If):
        if isinstance(self.node, UnresolvedState):
            self.node = ConditionalState(
                body=[
                    UnresolvedCase(
                        InlineTransformer.inline_expr(stmt.test, self.node.assignments),
                        parse_body(stmt.body, copy(self.node.assignments)),
                    )
                ],
                orelse=parse_body(stmt.orelse, copy(self.node.assignments)),
            )
        elif isinstance(self.node, ConditionalState):
            for case in self.node.body:
                assert isinstance(case.then, State)
                case.then.handle_if(stmt)
            self.node.orelse.handle_if(stmt)

    def handle_return(self, value: ast.expr):
        if isinstance(self.node, UnresolvedState):
            self.node = ReturnState(
                expr=InlineTransformer.inline_expr(value, self.node.assignments)
            )
        elif isinstance(self.node, ConditionalState):
            for case in self.node.body:
                assert isinstance(case.then, State)
                case.then.handle_return(value)
            self.node.orelse.handle_return(value)

    def handle_match(self, stmt: ast.Match):
        if isinstance(self.node, UnresolvedState):
            orelse = next(
                iter(
                    [
                        case.body
                        for case in stmt.cases
                        if isinstance(case.pattern, ast.MatchAs) and case.pattern.name is None
                    ]
                ),
                [],
            )
            self.node = ConditionalState(
                body=[
                    UnresolvedCase(
                        InlineTransformer.inline_expr(
                            self.translate_match(stmt.subject, case.pattern, case.guard),
                            self.node.assignments,
                        ),
                        parse_body(case.body, copy(self.node.assignments)),
                    )
                    for case in stmt.cases
                    if not isinstance(case.pattern, ast.MatchAs) or case.pattern.name is not None
                ],
                orelse=parse_body(
                    orelse,
                    copy(self.node.assignments),
                ),
            )
        elif isinstance(self.node, ConditionalState):
            for case in self.node.body:
                assert isinstance(case.then, State)
                case.then.handle_match(stmt)
            self.node.orelse.handle_match(stmt)


def parse_body(full_body: list[ast.stmt], assignments: dict[str, ast.expr] | None = None) -> State:
    if assignments is None:
        assignments = {}
    state = State(UnresolvedState(assignments))
    for stmt in full_body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            state.handle_assign(stmt)
        elif isinstance(stmt, ast.If):
            state.handle_if(stmt)
        elif isinstance(stmt, ast.Return):
            if stmt.value is None:
                raise ValueError("return needs a value")
            state.handle_return(stmt.value)
            break
        elif isinstance(stmt, ast.Match):
            assert not PY_39
            state.handle_match(stmt)
        else:
            raise ValueError(f"Unsupported statement type: {type(stmt)}")
    return state


def transform_tree_into_expr(node: State) -> ast.expr:
    if isinstance(node.node, ReturnState):
        return node.node.expr
    elif isinstance(node.node, ConditionalState):
        return build_polars_when_then_otherwise(
            [
                ResolvedCase(case.test, transform_tree_into_expr(case.then))
                for case in node.node.body
            ],
            transform_tree_into_expr(node.node.orelse),
        )
    else:
        raise ValueError("Not all branches return")
