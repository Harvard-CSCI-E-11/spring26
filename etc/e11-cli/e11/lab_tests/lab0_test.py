"""
This test is for the pytest self-test.
It's called lab0_test.py.
"""

from pathlib import Path
from e11.e11core.decorators import timeout
from e11.e11core.assertions import assert_contains, assert_not_contains, assert_len_between, TestFail
from e11.e11core.testrunner import TestRunner

# Imported test functions are used by test discovery system (see grader.collect_tests_in_definition_order)
imported_tests = []  # lab0 has no imported tests

@timeout(5)
def test_cwd_is_labdir( _:TestRunner ):
    # Runner auto-chdirs to COURSE_ROOT/lab0 before executing tests
    assert Path.cwd().name.lower() == "lab0", f"cwd not lab0: {Path.cwd()}"

@timeout(5)
def test_run_command_echo( tr:TestRunner ):
    r = tr.run_command("echo hello")
    if r.exit_code != 0:
        raise TestFail("echo failed", context=r.stderr)
    assert_contains(r.text, "hello")

@timeout(5)
def test_assertions_basic( _:TestRunner ): # pylint: disable=unused-argument
    assert_contains("abc", r"b")
    assert_not_contains("abc", r"z")
    assert_len_between("abcdef", min_len=3, max_len=10)

@timeout(5)
def test_read_file_self( tr:TestRunner ):
    # Ensure read_file works and returns non-empty content
    txt = tr.read_file(__file__)
    assert_len_between(txt, min_len=50)
    assert_contains(txt, "lab0_test.py")

def test_fails( _:TestRunner ):
    # This test should fail
    assert_contains("This is a test", "fails")
