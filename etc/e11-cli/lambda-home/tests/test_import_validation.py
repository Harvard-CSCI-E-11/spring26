"""
Test to validate that the Lambda handler can be imported correctly with the vendored e11 wheel.

This test simulates the actual deployment environment by importing the Lambda handler
module the way AWS Lambda does: `home_app.home.lambda_handler`

This test must be run after 'vend-e11' has been executed to ensure the wheel exists.
"""

import sys
from pathlib import Path


def _setup_wheel_path():
    """Add the vendored wheel to sys.path to simulate Lambda environment."""
    wheel_path = Path(__file__).parent.parent / "src" / "home_app" / "e11.whl"

    if not wheel_path.exists():
        raise FileNotFoundError(
            f"e11.whl not found at {wheel_path}. "
            "Run 'make vend-e11' first to create the wheel."
        )

    wheel_str = str(wheel_path)
    if wheel_str not in sys.path:
        sys.path.insert(0, wheel_str)


def test_lambda_handler_imports():
    """
    Test that the Lambda handler module can be imported the way AWS Lambda does.

    AWS Lambda imports: home_app.home.lambda_handler
    This will fail if any imports in home.py are broken (e.g., the S3_BUCKET import issue).
    """
    _setup_wheel_path()

    # Import the Lambda handler module the way AWS Lambda does
    # This will trigger all imports in home.py, including the problematic grader import
    import home_app.home  # pylint: disable=import-outside-toplevel

    # Verify the lambda_handler function exists
    assert hasattr(home_app.home, 'lambda_handler')
    assert callable(home_app.home.lambda_handler)


def test_grader_imports_s3_bucket_correctly():
    """
    Specifically test that grader.py can import S3_BUCKET correctly.

    This was the original bug - grader.py was trying to import S3_BUCKET
    from e11.e11core.constants, but it's actually in e11.e11_common.
    """
    _setup_wheel_path()

    # Import grader module - this will fail if S3_BUCKET import is broken
    from e11.e11core import grader  # pylint: disable=import-outside-toplevel
    assert grader is not None

    # Verify that constants module doesn't have S3_BUCKET (it shouldn't)
    from e11.e11core import constants  # pylint: disable=import-outside-toplevel
    assert not hasattr(constants, 'S3_BUCKET'), (
        "S3_BUCKET should not be in e11.e11core.constants. "
        "It should be imported from e11.e11_common in grader.py"
    )

    # Verify that e11_common has S3_BUCKET and compare to the constant
    import e11.e11_common as e11_common_module  # pylint: disable=import-outside-toplevel
    from e11.e11_common import S3_BUCKET  # pylint: disable=import-outside-toplevel
    # Compare imported value to the constant from the module (avoiding hard-coded strings)
    assert S3_BUCKET is not None
    assert S3_BUCKET == e11_common_module.S3_BUCKET

