import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class TestFail(Exception):
    message: str
    __test__ = False            # tell pytest not to treat this as a test case
    context: Optional[str] = None
    line: Optional[int] = None

    def __str__(self):
        return self.message

# pylint: disable=too-many-locals
def _numbered_context(text: str, match_span=None, lines_before=3, lines_after=3):
    lines = text.splitlines()
    if match_span is None:
        start = 0
        end = min(len(lines), lines_before + lines_after + 1)
        return "\n".join(f"{i+1:5d}  {lines[i]}" for i in range(start, end))

    start_idx, _ = match_span
    # Find the line number of start_idx
    char_count = 0
    line_no = 0
    for i, line in enumerate(lines):
        if char_count + len(line) + 1 > start_idx:
            line_no = i
            break
        char_count += len(line) + 1

    s = max(0, line_no - lines_before)
    e = min(len(lines), line_no + 1 + lines_after)
    out = []
    for i in range(s, e):
        prefix = ">>" if i == line_no else "  "
        out.append(f"{i+1:5d}{prefix} {lines[i]}")
    return "\n".join(out)

def assert_contains(content, m, context=3):
    text = _coerce_text(content)
    snippet = text[0:40]
    if isinstance(m,re.Pattern):
        rx = m            # pattern is a regular expression
        m = rx.search(text)
        if not m:
            snippet = _numbered_context(text, None, context, context)
            raise TestFail(f"Expected pattern not found: {rx.pattern}", context=snippet)
    else:
        if content not in text:
            snippet = _numbered_context(text, None, context, context)
            raise TestFail(f"Expected text '{m}' not found", context=snippet)


def assert_not_contains(content, pattern, flags=0, context=3):
    text = _coerce_text(content)
    rx = pattern if hasattr(pattern, "search") else re.compile(pattern, flags)
    m = rx.search(text)
    if m:
        snippet = _numbered_context(text, (m.start(), m.end()), context, context)
        raise TestFail(f"Forbidden pattern present: {rx.pattern}", context=snippet)

def assert_len_between(content, min_len=None, max_len=None):
    text = _coerce_text(content)
    n = len(text)
    if min_len is not None and n < min_len:
        raise TestFail(f"Content too short: {n} < {min_len}", context=text[:512])
    if max_len is not None and n > max_len:
        raise TestFail(f"Content too long: {n} > {max_len}", context=text[:1024])

def _coerce_text(content):
    if hasattr(content, "text"):   # content object from primitives
        return content.text
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return str(content)
