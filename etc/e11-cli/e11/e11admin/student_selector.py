"""Shared student selection and display helpers for e11admin."""

import json
import sys
from typing import Any, Dict

from boto3.dynamodb.conditions import Key
from tabulate import tabulate

from e11.e11_common import (
    A,
    User,
    get_user_from_user_id,
    queryscan_table,
    users_table,
)


def student_user(args):
    """Resolve exactly one student selector from --email/positional email or --user-id."""
    email, user_id = getattr(args, "email", None), getattr(args, "user_id", None)
    if email and user_id:
        print("Specify either --email or --user-id, not both.", file=sys.stderr)
        sys.exit(2)
    if user_id:
        return get_user_from_user_id(user_id)
    if email:
        return _student_user_by_email(email)
    print("Specify --email or --user-id.", file=sys.stderr)
    sys.exit(2)


def _student_user_by_email(email: str):
    if "@" not in email:
        print(
            f"--email requires a full email address; got {email!r}. "
            "Use --user-id for a user_id.",
            file=sys.stderr,
        )
        sys.exit(2)
    matches = [
        User(**item)
        for item in queryscan_table(users_table.scan, {"FilterExpression": Key(A.SK).eq(A.SK_USER)})
        if _user_record_matches_email(item, email)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Multiple users match {email}; use --user-id.", file=sys.stderr)
        sys.exit(2)
    print(f"Student {email} is not registered", file=sys.stderr)
    sys.exit(1)


def _user_record_matches_email(item: Dict[str, Any], email: str) -> bool:
    claims = item.get(A.CLAIMS) or {}
    candidates = {item.get(A.EMAIL), item.get("alt_email"), claims.get(A.EMAIL), claims.get("preferred_username")}
    return email in {candidate for candidate in candidates if candidate}


def _student_name(user) -> str:
    claims = getattr(user, "claims", None) or {}
    return str(claims.get("name") or getattr(user, "preferred_name", None) or "")


def _display_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, default=str)
    return "" if value is None else str(value)


def print_student_header(user):
    rows = [["Name", _student_name(user)], ["Email", getattr(user, "email", None) or ""], ["user_id", user.user_id]]
    claims = getattr(user, "claims", None) or {}
    rows.extend([f"claims.{key}", _display_value(claims[key])] for key in sorted(claims))
    print("Student:")
    print(tabulate(rows, tablefmt="plain", disable_numparse=True))
    print("")
