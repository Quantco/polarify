import ast
import inspect
from functools import wraps

from main import parse_body


def polarify(func):
    source = inspect.getsource(func)
    print(source)
    tree = ast.parse(source)
    expr = parse_body(tree.body[0].body)

    # Replace the body of the function with the parsed expr
    tree.body[0].body = [ast.Return(expr)]
    # TODO: make this prettier
    tree.body[0].decorator_list = []

    # Unparse the modified AST back into source code
    new_func_code = ast.unparse(tree)

    # Execute the new function code in the original function's globals
    exec_globals = func.__globals__
    exec(new_func_code, exec_globals)

    # Get the new function from the globals
    new_func = exec_globals[func.__name__]

    @wraps(func)
    def wrapper(*args, **kwargs):
        return new_func(*args, **kwargs)

    return wrapper
