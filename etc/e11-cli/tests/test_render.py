"""Tests for e11.e11core.render module."""
from unittest.mock import MagicMock

import pytest

from e11.e11core.render import print_summary


@pytest.fixture
def basic_summary():
    """Basic summary with passes only."""
    return {
        "lab": "lab0",
        "score": 5.0,
        "passes": ["test_one"],
        "fails": [],
        "tests": [{"status": "pass", "name": "test_one", "message": "Passed"}],
        "ctx": {"public_ip": "1.2.3.4"},
    }


@pytest.fixture
def summary_with_failures():
    """Summary with both passes and failures."""
    return {
        "lab": "lab0",
        "score": 2.5,
        "passes": ["test_one"],
        "fails": ["test_two"],
        "tests": [
            {"status": "pass", "name": "test_one", "message": "Passed"},
            {
                "status": "fail",
                "name": "test_two",
                "message": "Failed",
                "context": "Error details",
            },
        ],
        "ctx": {"public_ip": "1.2.3.4"},
    }


@pytest.fixture
def empty_summary():
    """Summary with no tests."""
    return {
        "lab": "lab0",
        "score": 0.0,
        "passes": [],
        "fails": [],
        "tests": [],
        "ctx": {"public_ip": "1.2.3.4"},
    }


class TestPrintSummary:
    """Test cases for print_summary function."""

    def test_basic_output_with_passes(self, capsys, basic_summary):
        """Test basic summary output with passing tests."""
        print_summary(basic_summary, verbose=False)
        captured = capsys.readouterr()
        
        assert "=== lab0 Results ===" in captured.out
        assert "Testing public ip address: 1.2.3.4" in captured.out
        assert "Score: 5.0 / 5.0" in captured.out
        assert "-- PASSES --" in captured.out
        assert "test_one" in captured.out
        assert "-- FAILURES --" not in captured.out

    def test_output_with_failures(self, capsys, summary_with_failures):
        """Test summary output with failing tests."""
        print_summary(summary_with_failures, verbose=False)
        captured = capsys.readouterr()
        
        assert "=== lab0 Results ===" in captured.out
        assert "Score: 2.5 / 5.0" in captured.out
        assert "-- PASSES --" in captured.out
        assert "-- FAILURES --" in captured.out
        assert "test_one" in captured.out
        assert "test_two" in captured.out
        assert "Error details" in captured.out
        assert "----- context -----" in captured.out

    def test_output_with_no_tests(self, capsys, empty_summary):
        """Test summary with no passing or failing tests."""
        print_summary(empty_summary, verbose=False)
        captured = capsys.readouterr()
        
        assert "-- PASSES --" not in captured.out
        assert "-- FAILURES --" not in captured.out
        assert "Score: 0.0 / 5.0" in captured.out

    @pytest.mark.parametrize(
        "ctx_input,expected_ip",
        [
            ({"public_ip": "1.2.3.4"}, "1.2.3.4"),
            ({}, "unknown"),
        ],
    )
    def test_public_ip_handling(self, capsys, basic_summary, ctx_input, expected_ip):
        """Test various public_ip contexts."""
        basic_summary["ctx"] = ctx_input
        print_summary(basic_summary, verbose=False)
        captured = capsys.readouterr()
        assert f"Testing public ip address: {expected_ip}" in captured.out

    def test_context_as_object(self, capsys, basic_summary):
        """Test summary with ctx as object with public_ip attribute."""
        ctx_obj = MagicMock()
        ctx_obj.public_ip = "9.10.11.12"
        basic_summary["ctx"] = ctx_obj
        
        print_summary(basic_summary, verbose=False)
        captured = capsys.readouterr()
        assert "Testing public ip address: 9.10.11.12" in captured.out

    @pytest.mark.parametrize(
        "test_data,expected_present,expected_absent",
        [
            (
                {"status": "fail", "message": "Failed"},
                ["test_two", "Failed"],
                ["----- context -----"],
            ),
            (
                {"status": "fail", "message": "Failed", "context": ""},
                ["test_two", "Failed"],
                ["----- context -----"],
            ),
        ],
    )
    def test_failure_context_handling(
        self, capsys, test_data, expected_present, expected_absent
    ):
        """Test failure output with various context scenarios."""
        summary = {
            "lab": "lab0",
            "score": 4.0,
            "passes": ["test_one"],
            "fails": ["test_two"],
            "tests": [
                {"status": "pass", "name": "test_one", "message": "Passed"},
                {"name": "test_two", **test_data},
            ],
            "ctx": {"public_ip": "1.2.3.4"},
        }
        
        print_summary(summary, verbose=False)
        captured = capsys.readouterr()
        
        for expected in expected_present:
            assert expected in captured.out
        for expected in expected_absent:
            assert expected not in captured.out

    @pytest.mark.parametrize(
        "test_data",
        [
            {"status": "pass", "message": ""},
            {"status": "pass"},
        ],
    )
    def test_pass_message_handling(self, capsys, test_data):
        """Test pass output with empty or missing messages."""
        summary = {
            "lab": "lab0",
            "score": 5.0,
            "passes": ["test_one"],
            "fails": [],
            "tests": [{"name": "test_one", **test_data}],
            "ctx": {"public_ip": "1.2.3.4"},
        }
        
        print_summary(summary, verbose=False)
        captured = capsys.readouterr()
        assert "test_one" in captured.out

    def test_verbose_mode_json_output(self, capsys, basic_summary):
        """Test verbose mode outputs JSON."""
        print_summary(basic_summary, verbose=True)
        captured = capsys.readouterr()
        
        assert captured.out.strip().startswith("{")
        assert '"lab"' in captured.out
        assert '"score"' in captured.out
        assert "=== lab0 Results ===" in captured.out

    def test_verbose_mode_with_pass_artifacts(self, capsys, basic_summary):
        """Test verbose mode shows pass artifacts with context."""
        basic_summary["tests"][0]["context"] = "Some artifact data"
        
        print_summary(basic_summary, verbose=True)
        captured = capsys.readouterr()
        
        assert "-- PASS ARTIFACTS (verbose) --" in captured.out
        assert "test_one" in captured.out
        assert "Some artifact data" in captured.out

    def test_verbose_mode_artifacts_header_without_context(self, capsys, basic_summary):
        """Test verbose mode shows artifacts header even when no context."""
        print_summary(basic_summary, verbose=True)
        captured = capsys.readouterr()
        
        # Header prints if there are passes (even if no context)
        assert "-- PASS ARTIFACTS (verbose) --" in captured.out
        assert "-- PASSES --" in captured.out
        assert "test_one" in captured.out

    def test_verbose_mode_no_artifacts_when_no_passes(self, capsys, empty_summary):
        """Test verbose mode doesn't show artifacts when there are no passes."""
        empty_summary["fails"] = ["test_one"]
        empty_summary["tests"] = [
            {"status": "fail", "name": "test_one", "message": "Failed"}
        ]
        
        print_summary(empty_summary, verbose=True)
        captured = capsys.readouterr()
        
        assert "-- PASS ARTIFACTS (verbose) --" not in captured.out

    def test_multiple_passes(self, capsys):
        """Test output with multiple passing tests."""
        summary = {
            "lab": "lab0",
            "score": 5.0,
            "passes": ["test_one", "test_two", "test_three"],
            "fails": [],
            "tests": [
                {"status": "pass", "name": "test_one", "message": "Pass 1"},
                {"status": "pass", "name": "test_two", "message": "Pass 2"},
                {"status": "pass", "name": "test_three", "message": "Pass 3"},
            ],
            "ctx": {"public_ip": "1.2.3.4"},
        }
        
        print_summary(summary, verbose=False)
        captured = capsys.readouterr()
        
        assert "test_one" in captured.out
        assert "test_two" in captured.out
        assert "test_three" in captured.out
