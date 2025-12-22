"""
Conftest to import fixtures from lambda-home for integration testing.
This allows e11-cli tests to use lambda-home fixtures like fake_aws, dynamodb_local, etc.
"""

import sys
from pathlib import Path

# Add lambda-home tests to path
lambda_home_tests = Path(__file__).parent.parent / "lambda-home" / "tests"
if str(lambda_home_tests) not in sys.path:
    sys.path.insert(0, str(lambda_home_tests))

# Import fixtures from lambda-home conftest
try:
    from conftest import fake_aws, dynamodb_local, clean_dynamodb, fake_idp_server
    __all__ = ['fake_aws', 'dynamodb_local', 'clean_dynamodb', 'fake_idp_server']
except ImportError:
    # If we can't import, create dummy fixtures that skip tests
    import pytest
    
    @pytest.fixture
    def fake_aws():
        pytest.skip("lambda-home fixtures not available")
    
    @pytest.fixture
    def dynamodb_local():
        pytest.skip("lambda-home fixtures not available")
    
    @pytest.fixture
    def clean_dynamodb():
        pytest.skip("lambda-home fixtures not available")
    
    @pytest.fixture
    def fake_idp_server():
        pytest.skip("lambda-home fixtures not available")

