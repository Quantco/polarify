import pytest

from polarify import polarify

from .functions import unsupported_functions

@pytest.mark.parametrize("func_match", unsupported_functions)
def test_unsupported_functions(func_match):
    func, match = func_match
    with pytest.raises(ValueError, match=match):
        polarify(func)
