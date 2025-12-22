import os
import sys
from pathlib import Path
import pytest

TEST_CONFIG="""
[student]
preferred_name=Preferred Name
email=test@example.org
smashedemail=testexampleorg
public_ip=127.0.0.1
course_key=key1234
"""

@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    # Fake HOME with a minimal ~/e11-config.ini
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))

    fake_home.mkdir()
    cfg = fake_home / "e11-config.ini"
    cfg.write_text(TEST_CONFIG, encoding="utf-8")

    # Redirect COURSE_ROOT to tmp to avoid touching the real FS
    from e11.e11core import constants
    monkeypatch.setattr(constants, "COURSE_ROOT", tmp_path / "course", raising=False)
    (tmp_path / "course").mkdir()

    yield

# Import fixtures from lambda-home for integration testing
# Add lambda-home tests to path
lambda_home_tests = Path(__file__).parent.parent / "lambda-home" / "tests"
if str(lambda_home_tests) not in sys.path:
    sys.path.insert(0, str(lambda_home_tests))

# Try to import fixtures from lambda-home conftest
try:
    # Import the conftest module and register its fixtures
    import importlib.util
    conftest_path = lambda_home_tests / "conftest.py"
    if conftest_path.exists():
        spec = importlib.util.spec_from_file_location("lambda_home_conftest", conftest_path)
        lambda_home_conftest = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lambda_home_conftest)

        # Register fixtures from lambda-home conftest
        # Pytest will automatically discover fixtures in imported modules
        # We just need to make sure the module is loaded
        globals().update({
            'fake_aws': lambda_home_conftest.fake_aws,
            'dynamodb_local': lambda_home_conftest.dynamodb_local,
            'clean_dynamodb': lambda_home_conftest.clean_dynamodb,
            'fake_idp_server': lambda_home_conftest.fake_idp_server,
        })
except (ImportError, AttributeError, FileNotFoundError):
    # If we can't import, create dummy fixtures that skip tests
    @pytest.fixture
    def fake_aws():
        pytest.skip("lambda-home fixtures not available - ensure lambda-home/tests/conftest.py exists")

    @pytest.fixture
    def dynamodb_local():
        pytest.skip("lambda-home fixtures not available - ensure lambda-home/tests/conftest.py exists")

    @pytest.fixture
    def clean_dynamodb():
        pytest.skip("lambda-home fixtures not available - ensure lambda-home/tests/conftest.py exists")

    @pytest.fixture
    def fake_idp_server():
        pytest.skip("lambda-home fixtures not available - ensure lambda-home/tests/conftest.py exists")
