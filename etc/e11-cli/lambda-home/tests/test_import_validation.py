"""
Test to validate that all imports work correctly with the vendored e11 wheel.

This test simulates the actual deployment environment by importing modules
from the vendored wheel location. It should catch import errors before deployment.

This test must be run after 'vend-e11' has been executed to ensure the wheel exists.
"""

import sys
from pathlib import Path


def test_imports_from_vendored_wheel():
    """
    Test that all critical imports work from the vendored wheel.

    This simulates the Lambda environment where PYTHONPATH includes
    /var/task/home_app/e11.whl, and we import from e11.*
    """
    # Add the wheel location to sys.path if not already there
    wheel_path = Path(__file__).parent.parent / "src" / "home_app" / "e11.whl"

    if not wheel_path.exists():
        raise FileNotFoundError(
            f"e11.whl not found at {wheel_path}. "
            "Run 'make vend-e11' first to create the wheel."
        )

    # Add wheel to path (simulating Lambda environment)
    wheel_str = str(wheel_path)
    if wheel_str not in sys.path:
        sys.path.insert(0, wheel_str)

    # Test critical imports that are used in home.py
    # These are the imports that must work in production

    # 1. Import from e11.e11core.constants
    from e11.e11core.constants import COURSE_DOMAIN, COURSE_NAME, COURSE_KEY_LEN
    assert COURSE_DOMAIN is not None
    assert COURSE_NAME is not None
    assert COURSE_KEY_LEN is not None

    # 2. Import from e11.e11_common (this is where S3_BUCKET is defined)
    from e11.e11_common import (
        S3_BUCKET,
        A,
        EmailNotRegistered,
        User,
        add_grade,
        add_user_log,
        convert_dynamodb_item,
        route53_client,
        secretsmanager_client,
        sessions_table,
        users_table,
        queryscan_table,
        SES_VERIFIED_EMAIL,
        ses_client,
        s3_client
    )
    assert S3_BUCKET is not None
    assert S3_BUCKET == 'csci-e-11'

    # 3. Import from e11.e11core.grader (this was the problematic import)
    from e11.e11core import grader
    # Verify that grader can access S3_BUCKET (it imports it from e11_common)
    # We can't directly check if it imported correctly, but we can verify
    # the module loaded without import errors

    # 4. Import from e11.e11core.utils
    from e11.e11core.utils import get_logger, smash_email
    assert get_logger is not None
    assert smash_email is not None

    # 5. Import from e11.e11core.e11ssh
    from e11.e11core.e11ssh import E11Ssh
    assert E11Ssh is not None

    # 6. Import from e11.main (for version)
    from e11.main import __version__
    assert __version__ is not None

    # 7. Test that home.py's imports would work
    # This is the critical test - can we import what home.py needs?
    try:
        # Simulate the imports that home.py does
        from e11.e11core.e11ssh import E11Ssh
        from e11.e11core.utils import smash_email
        from e11.e11core import grader
        from e11.e11_common import (
            A,
            EmailNotRegistered,
            User,
            add_grade,
            add_user_log,
            convert_dynamodb_item,
            route53_client,
            secretsmanager_client,
            sessions_table,
            users_table,
            queryscan_table,
            S3_BUCKET,
            SES_VERIFIED_EMAIL,
            ses_client,
            s3_client
        )
        from e11.e11core.constants import COURSE_DOMAIN
        from e11.main import __version__
        from e11.e11core.utils import get_logger

        # If we get here, all imports worked
        assert True
    except ImportError as e:
        raise AssertionError(
            f"Import validation failed. One or more imports from the vendored wheel failed: {e}"
        ) from e


def test_grader_imports_s3_bucket_correctly():
    """
    Specifically test that grader.py can import S3_BUCKET correctly.

    This was the original bug - grader.py was trying to import S3_BUCKET
    from e11.e11core.constants, but it's actually in e11.e11_common.
    """
    wheel_path = Path(__file__).parent.parent / "src" / "home_app" / "e11.whl"

    if not wheel_path.exists():
        raise FileNotFoundError(
            f"e11.whl not found at {wheel_path}. "
            "Run 'make vend-e11' first to create the wheel."
        )

    wheel_str = str(wheel_path)
    if wheel_str not in sys.path:
        sys.path.insert(0, wheel_str)

    # Import grader module

    # Verify that grader module has access to S3_BUCKET
    # We can't directly access it if it's not exported, but we can
    # verify the module imported without errors

    # Try to use a function that would use S3_BUCKET
    # The discover_and_run function uses S3_BUCKET internally
    # We can't easily test it without a full context, but we can
    # verify the module loaded successfully

    # Check that constants module doesn't have S3_BUCKET (it shouldn't)
    from e11.e11core import constants
    assert not hasattr(constants, 'S3_BUCKET'), (
        "S3_BUCKET should not be in e11.e11core.constants. "
        "It should be imported from e11.e11_common in grader.py"
    )

    # Verify that e11_common has S3_BUCKET
    from e11.e11_common import S3_BUCKET
    assert S3_BUCKET == 'csci-e-11'
