import re
import pytest
from e11.e11core.assertions import assert_contains, assert_not_contains, assert_len_between, TestFail

def test_contains_and_not_contains():
    assert_contains("abc", r"b")
    assert_contains("AbC", re.compile("a", re.I))
    with pytest.raises(TestFail):
        assert_contains("abc", r"z")
    assert_not_contains("abc", r"z")
    with pytest.raises(TestFail):
        assert_not_contains("abc", r"a")

def test_len_between():
    assert_len_between("abcd", min_len=2, max_len=10)
    with pytest.raises(TestFail):
        assert_len_between("a", min_len=2)
    with pytest.raises(TestFail):
        assert_len_between("abcdef", max_len=3)
