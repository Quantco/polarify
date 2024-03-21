from __future__ import annotations

import ast
import sys
from copy import copy, deepcopy
from dataclasses import dataclass
from typing import Sequence, Tuple


PY_39 = (sys.version_info <= (3, 9))

# TODO: make walrus throw ValueError

def build_polars_when_then_otherwise(body: Sequence[Tuple[ast.Expr, ast.Expr]], orelse: ast.expr) -> ast.Call:
    nodes = []
    for test, then in body:
        when_node = ast.Call(
            func=ast.Attribute(value=nodes[-1] if len(nodes) else ast.Name(id="pl", ctx=ast.Load()), attr="when", ctx=ast.Load()),
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
        return build_polars_when_then_otherwise([[test, body]], orelse)

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.Compare:
        if len(node.comparators) > 1:
            raise ValueError("Polars can't handle chained comparisons")
        node.left = self.visit(node.left)
        node.comparators = [self.visit(c) for c in node.comparators]
        return node

    def visit_List(self, node: ast.List) -> ast.List:
        node.elts = [self.visit(elt) for elt in node.elts]
        return node
    
    def visit_MatchValue(self, node: ast.MatchValue) -> ast.MatchValue:
        return node.value
    
    def visit_Subscript(self, node: ast.Subscript) -> ast.Any:
        node.value = self.visit(node.value)
        node.slice = self.visit(node.slice)
        return node
    
    def visit_Slice(self, node: ast.Slice) -> ast.Any:
        if (node.lower):
            node.lower = self.visit(node.lower)
        if(node.upper):
            node.upper = self.visit(node.upper)
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
    A conditional state, with a test expression and two branches.
    """

    body: Sequence[Tuple[ast.expr, State]]
    orelse: State


@dataclass
class State:
    """
    A state in the execution flow.
    Either unresolved assignments, a return statement, or a conditional state.
    """

    node: UnresolvedState | ReturnState | ConditionalState

    def translate_match(self, subj, stmt: ast.MatchValue | ast.MatchOr):              
        if isinstance(stmt, ast.MatchValue):
            return ast.Compare(
                left=ast.Name(id=subj, ctx=ast.Load()),
                ops=[ast.Eq()],
                comparators=[stmt.value],
            )
        elif isinstance(stmt, ast.MatchOr):
            return ast.BinOp(
                left=self.translate_match(subj, stmt.patterns[0]),
                op=ast.BitOr(),
                right=self.translate_match(subj, ast.MatchOr(patterns=stmt.patterns[1:])) if len(stmt.patterns) > 2 else self.translate_match(subj, stmt.patterns[1]),
            )
        elif isinstance(stmt, ast.MatchSequence):
            left = ast.Name(id=subj, ctx=ast.Load())
            if isinstance(stmt.patterns[-1], ast.MatchStar):
                raise ValueError("starred patterns are not supported")
                # self.node.assignments[stmt.patterns[-1].name] = ast.Subscript(value=ast.Name(id=subj, ctx=ast.Load()), slice=ast.Slice(lower=ast.Constant(value=len(stmt.patterns) - 1)))
                # left = ast.Subscript(value=ast.Name(id=subj, ctx=ast.Load()), slice=ast.Slice(upper=ast.Constant(value=len(stmt.patterns) - 1)))
            return ast.Compare(
                left=left,
                ops=[ast.Eq()],
                comparators=[ast.List(elts=[stmt.patterns[i] for i in range(len(stmt.patterns) - isinstance(stmt.patterns[-1], ast.MatchStar))])],
            )
        else:
            raise ValueError(f"Unsupported match type: {type(stmt)}")
        
    def handle_assign(self, expr: ast.Assign | ast.AnnAssign):
        if isinstance(expr, ast.AnnAssign):
            expr = ast.Assign(targets=[expr.target], value=expr.value)

        if isinstance(self.node, UnresolvedState):
            self.node.handle_assign(expr)
        elif isinstance(self.node, ConditionalState):
            for i in range(len(self.node.body)):
                self.node.body[i][1].handle_assign(expr)
            self.node.orelse.handle_assign(expr)

    def handle_if(self, stmt: ast.If):
        if isinstance(self.node, UnresolvedState):
            self.node = ConditionalState(
                body=[
                    [InlineTransformer.inline_expr(stmt.test, self.node.assignments),
                    parse_body(stmt.body, copy(self.node.assignments))]
                ],
                orelse=parse_body(stmt.orelse, copy(self.node.assignments)),
            )
        elif isinstance(self.node, ConditionalState):
            for i in range(len(self.node.body)):
                self.node.body[i][1].handle_if(stmt)
            self.node.orelse.handle_if(stmt)

    def handle_return(self, value: ast.expr):
        if isinstance(self.node, UnresolvedState):
            self.node = ReturnState(
                expr=InlineTransformer.inline_expr(value, self.node.assignments)
            )
        elif isinstance(self.node, ConditionalState):
            for i in range(len(self.node.body)):
                self.node.body[i][1].handle_return(value)
            self.node.orelse.handle_return(value)
    
    def handle_match(self, stmt: ast.Match):
        if isinstance(self.node, UnresolvedState):
            self.node = ConditionalState(
                body=[
                    [InlineTransformer.inline_expr(
                        self.translate_match(stmt.subject.id, stmt.cases[i].pattern), self.node.assignments),
                    parse_body([
                        stmt.cases[i].body[0]
                    ], copy(self.node.assignments))
                    ] 
                for i in range(len(stmt.cases))
                    if not isinstance(stmt.cases[i].pattern, ast.MatchAs)
                ],
                orelse=parse_body(
                    [
                        stmt.cases[i].body[0]
                    for i in range(len(stmt.cases)) if isinstance(stmt.cases[i].pattern, ast.MatchAs)
                    ]
                , copy(self.node.assignments)),
            )
        elif isinstance(self.node, ConditionalState):
            for i in range(len(self.node.body)):
                self.node.body[i][1].handle_match(stmt)
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
            if PY_39:
                raise ValueError("match statements are only supported in Python 3.9+")
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
                [node.node.body[i][0],
                transform_tree_into_expr(node.node.body[i][1])
            ] for i in range(len(node.node.body))
            ],
            transform_tree_into_expr(node.node.orelse),
        )
    else:
        raise ValueError("Not all branches return")
    return expr