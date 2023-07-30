import ast
import inspect
from functools import wraps

from .main import parse_body


def transform_func_to_new_source(func) -> str:
    source = inspect.getsource(func)
    tree = ast.parse(source)
    func_def: ast.FunctionDef = tree.body[0]  # type: ignore
    expr = parse_body(func_def.body)

    # Replace the body of the function with the parsed expr
    # Also import polars as pl since this is used in the generated code
    # We don't want to rely on the user having imported polars as pl
    func_def.body = [
        ast.Import(names=[ast.alias(name="polars", asname="pl")]),
        ast.Return(value=expr),
    ]
    # TODO: make this prettier
    func_def.decorator_list = []
    func_def.name += "_polarified"

    # Unparse the modified AST back into source code
    return ast.unparse(tree)


def polarify(func):
    new_func_code = transform_func_to_new_source(func)
    # Execute the new function code in the original function's globals
    exec_globals = func.__globals__
    exec(new_func_code, exec_globals)

    # Get the new function from the globals
    new_func = exec_globals[func.__name__ + "_polarified"]

    @wraps(func)
    def wrapper(*args, **kwargs):
        return new_func(*args, **kwargs)

    return wrapper
