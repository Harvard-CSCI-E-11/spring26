"""
Test staging environment detection and cookie domain handling
"""

import pytest

import home_app.home as home
import home_app.common as common
from e11.e11core.constants import COURSE_DOMAIN

def test_is_staging_environment():
    """Test staging environment detection"""

    # Production event (no stage or prod stage)
    prod_event = {
        "requestContext": {
            "stage": "prod"
        }
    }
    assert not common.is_staging_environment(prod_event)

    # Production event (no stage field)
    prod_event_no_stage = {
        "requestContext": {}
    }
    assert not common.is_staging_environment(prod_event_no_stage)

    # Staging event
    stage_event = {
        "requestContext": {
            "stage": "stage"
        }
    }
    assert common.is_staging_environment(stage_event)


def test_get_cookie_domain():
    """Test cookie domain selection based on environment"""

    # Production should use configured domain
    prod_event = {
        "requestContext": {
            "stage": "prod"
        }
    }
    assert home.get_cookie_domain(prod_event) == COURSE_DOMAIN

    # Staging should use production domain for session sharing
    stage_event = {
        "requestContext": {
            "stage": "stage"
        }
    }
    assert home.get_cookie_domain(stage_event) == COURSE_DOMAIN


def test_make_cookie_with_dynamic_domain():
    """Test that make_cookie uses the correct domain"""

    # Test production cookie
    prod_event = {
        "requestContext": {
            "stage": "prod"
        }
    }
    cookie = common.make_cookie("test", "value", domain=home.get_cookie_domain(prod_event))
    assert f"Domain={COURSE_DOMAIN}" in cookie

    # Test staging cookie (should use same domain)
    stage_event = {
        "requestContext": {
            "stage": "stage"
        }
    }
    cookie = common.make_cookie("test", "value", domain=home.get_cookie_domain(stage_event))
    assert f"Domain={COURSE_DOMAIN}" in cookie


def test_environment_detection_integration():
    """Test that environment detection works with real event structure"""

    # Simulate a real API Gateway event for staging
    stage_event = {
        "version": "2.0",
        "routeKey": "GET /",
        "rawPath": "/",
        "requestContext": {
            "stage": "stage",
            "http": {
                "method": "GET",
                "sourceIp": "127.0.0.1"
            }
        },
        "cookies": ["AuthSid=test-session-id"]
    }

    assert common.is_staging_environment(stage_event)
    assert home.get_cookie_domain(stage_event) == COURSE_DOMAIN

    # Simulate a real API Gateway event for production
    prod_event = {
        "version": "2.0",
        "routeKey": "GET /",
        "rawPath": "/",
        "requestContext": {
            "stage": "prod",
            "http": {
                "method": "GET",
                "sourceIp": "127.0.0.1"
            }
        },
        "cookies": ["AuthSid=test-session-id"]
    }

    assert not common.is_staging_environment(prod_event)
    assert home.get_cookie_domain(prod_event) == COURSE_DOMAIN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
