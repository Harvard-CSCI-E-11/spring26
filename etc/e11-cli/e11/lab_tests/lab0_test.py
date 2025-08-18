#
# This test is for the pytest self-test
#

import os, sys, re
from pathlib import Path
from e11.e11core.decorators import timeout
from e11.e11core.primitives import run_command, read_file
from e11.e11core.assertions import assert_contains, assert_not_contains, assert_len_between, TestFail

@timeout(5)
def test_cwd_is_labdir():
    # Runner auto-chdirs to COURSE_ROOT/lab0 before executing tests
    assert Path.cwd().name.lower() == "lab0", f"cwd not lab0: {Path.cwd()}"

@timeout(5)
def test_run_command_echo():
    r = run_command("echo hello")
    if r.exit_code != 0:
        raise TestFail("echo failed", context=r.stderr)
    assert_contains(r.text, r"\bhello\b")

@timeout(5)
def test_assertions_basic():
    assert_contains("abc", r"b")
    assert_not_contains("abc", r"z")
    assert_len_between("abcdef", min_len=3, max_len=10)

@timeout(5)
def test_read_file_self():
    # Ensure read_file works and returns non-empty content
    txt = read_file(__file__)
    assert_len_between(txt, min_len=50)
    assert_contains(txt, r"lab0_test\.py")
