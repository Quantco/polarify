import pytest

from polarify import polarify

from .functions import chained_compare_expr


def test_chained_compare_fail():
    with pytest.raises(ValueError):
        polarify(chained_compare_expr)
