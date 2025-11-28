#!/usr/bin/env python3
"""
Scan all files in the git repository for trailing whitespace and fix them.

Only rewrites files that actually have trailing whitespace issues.
This helps maintain clean code without unnecessary file modifications.
"""

import os
import subprocess
import sys
from pathlib import Path


def get_git_tracked_files(repo_root):
    """Get all files tracked by git, excluding binary files."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    files = result.stdout.strip().split("\n")
    # Filter out binary files and common non-text files
    text_extensions = {
        ".py",
        ".js",
        ".html",
        ".css",
        ".json",
        ".md",
        ".rst",
        ".txt",
        ".yml",
        ".yaml",
        ".toml",
        ".ini",
        ".conf",
        ".sh",
        ".bash",
        ".makefile",
        "Makefile",
    }
    tracked = []
    for f in files:
        if not f:
            continue
        path = Path(f)
        # Include files with known text extensions or no extension (like Makefile)
        if path.suffix in text_extensions or not path.suffix:
            tracked.append(path)
    return tracked


def has_trailing_whitespace(filepath):
    """Check if file has trailing whitespace on any line."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                # Check if line has trailing whitespace (spaces or tabs before newline)
                if line.rstrip("\n\r") != line.rstrip():
                    return True, line_num
    except (UnicodeDecodeError, PermissionError,IsADirectoryError):
        # Skip binary files or files we can't read
        return False, None
    return False, None


def fix_trailing_whitespace(filepath):
    """Remove trailing whitespace from all lines in a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Remove trailing whitespace from each line, preserving newlines
        fixed_lines = []
        modified = False
        for line in lines:
            # Preserve the original line ending (could be \n, \r\n, or no newline at end)
            if line.endswith("\r\n"):
                stripped = line.rstrip(" \t\r\n")
                new_line = stripped + "\r\n"
            elif line.endswith("\n"):
                stripped = line.rstrip(" \t\n")
                new_line = stripped + "\n"
            else:
                # Last line might not have a newline
                new_line = line.rstrip(" \t")
                if new_line != line:
                    modified = True

            if new_line != line:
                modified = True
            fixed_lines.append(new_line)

        if modified:
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                f.writelines(fixed_lines)
            return True
    except (UnicodeDecodeError, PermissionError) as e:
        print(f"  Skipping {filepath}: {e}", file=sys.stderr)
        return False
    return False


def main():
    """Main entry point."""
    # Find repo root (directory containing .git)
    repo_root = Path(__file__).parent.parent.resolve()
    if not (repo_root / ".git").exists():
        print(f"Error: {repo_root} does not appear to be a git repository", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning git repository at {repo_root}")
    tracked_files = get_git_tracked_files(repo_root)

    files_with_issues = []
    for filepath in tracked_files:
        full_path = repo_root / filepath
        if not full_path.exists():
            continue
        has_issue, line_num = has_trailing_whitespace(full_path)
        if has_issue:
            files_with_issues.append((full_path, line_num))

    if not files_with_issues:
        print("No trailing whitespace found. All files are clean!")
        return 0

    print(f"\nFound {len(files_with_issues)} file(s) with trailing whitespace:")
    for filepath, line_num in files_with_issues:
        print(f"  {filepath} (line {line_num})")

    print("\nFixing trailing whitespace...")
    fixed_count = 0
    for filepath, _ in files_with_issues:
        if fix_trailing_whitespace(filepath):
            print(f"  Fixed: {filepath}")
            fixed_count += 1

    print(f"\nFixed {fixed_count} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
