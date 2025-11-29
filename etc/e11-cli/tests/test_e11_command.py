import pytest

import e11.main

def test_patched_config(_isolate_env):
    cp = e11.main.get_config()
    assert cp['student']['email'] == 'test@example.org' # from conftest.py
    assert cp['student']['smashedemail'] == 'testexampleorg' # from conftest.py
    assert cp['student']['public_ip'] == '127.0.0.1' # from conftest.py


class TestReportTests:
    """Test cases for do_report_tests command."""

    def test_report_tests_output_format(self, capsys):
        """Test that report tests generates markdown output with expected format."""
        e11.main.do_report_tests(None)
        captured = capsys.readouterr()

        # Check markdown header
        assert "# E11 Lab Tests Report" in captured.out
        assert "This document lists all available tests for each lab." in captured.out

        # Check for lab sections (at least lab0 should exist)
        assert "## LAB0" in captured.out

    def test_report_tests_includes_lab0(self, capsys):
        """Test that lab0 tests are included in the report."""
        e11.main.do_report_tests(None)
        captured = capsys.readouterr()

        # lab0 should be present
        assert "## LAB0" in captured.out
        # Check for some expected lab0 tests
        assert "test_cwd_is_labdir" in captured.out
        assert "test_run_command_echo" in captured.out

    def test_report_tests_includes_imported_tests(self, capsys):
        """Test that imported tests from lab_common are included."""
        e11.main.do_report_tests(None)
        captured = capsys.readouterr()

        # Check that imported tests appear in labs that use them
        # lab1 uses test_autograder_key_present
        if "## LAB1" in captured.out:
            assert "test_autograder_key_present" in captured.out

    def test_report_tests_markdown_structure(self, capsys):
        """Test that output follows proper markdown structure."""
        e11.main.do_report_tests(None)
        captured = capsys.readouterr()

        output = captured.out

        # Should have proper markdown headers
        assert output.strip().startswith("#")
        assert "##" in output  # At least one lab section

        # Test items should be formatted as markdown list items
        assert "- **test_" in output or "*No tests defined*" in output

    def test_report_tests_includes_docstrings(self, capsys):
        """Test that test docstrings are included in the output."""
        e11.main.do_report_tests(None)
        captured = capsys.readouterr()

        output = captured.out

        # Some tests have docstrings that should appear
        # The format is: - **test_name**: docstring
        # Look for the colon pattern that indicates a docstring is present
        assert ":" in output  # At least one test should have a docstring

    def test_report_tests_handles_missing_labs(self, capsys):
        """Test that missing lab modules are handled gracefully."""
        e11.main.do_report_tests(None)
        captured = capsys.readouterr()

        output = captured.out

        # Should not crash, should have some output
        assert len(output) > 0
        # Should not have error messages about missing modules
        assert "Traceback" not in output
        assert "ModuleNotFoundError" not in output
