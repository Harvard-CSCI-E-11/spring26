"""
Test staging environment detection and cookie domain handling
"""

import pytest
from unittest.mock import Mock

import home_app.home as home


def test_is_staging_environment():
    """Test staging environment detection"""
    
    # Production event (no stage or prod stage)
    prod_event = {
        "requestContext": {
            "stage": "prod"
        }
    }
    assert not home.is_staging_environment(prod_event)
    
    # Production event (no stage field)
    prod_event_no_stage = {
        "requestContext": {}
    }
    assert not home.is_staging_environment(prod_event_no_stage)
    
    # Staging event
    stage_event = {
        "requestContext": {
            "stage": "stage"
        }
    }
    assert home.is_staging_environment(stage_event)


def test_get_cookie_domain():
    """Test cookie domain selection based on environment"""
    
    # Production should use configured domain
    prod_event = {
        "requestContext": {
            "stage": "prod"
        }
    }
    assert home.get_cookie_domain(prod_event) == "csci-e-11.org"
    
    # Staging should use production domain for session sharing
    stage_event = {
        "requestContext": {
            "stage": "stage"
        }
    }
    assert home.get_cookie_domain(stage_event) == "csci-e-11.org"


def test_make_cookie_with_dynamic_domain():
    """Test that make_cookie uses the correct domain"""
    
    # Test production cookie
    prod_event = {
        "requestContext": {
            "stage": "prod"
        }
    }
    cookie = home.make_cookie("test", "value", domain=home.get_cookie_domain(prod_event))
    assert "Domain=csci-e-11.org" in cookie
    
    # Test staging cookie (should use same domain)
    stage_event = {
        "requestContext": {
            "stage": "stage"
        }
    }
    cookie = home.make_cookie("test", "value", domain=home.get_cookie_domain(stage_event))
    assert "Domain=csci-e-11.org" in cookie


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
    
    assert home.is_staging_environment(stage_event)
    assert home.get_cookie_domain(stage_event) == "csci-e-11.org"
    
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
    
    assert not home.is_staging_environment(prod_event)
    assert home.get_cookie_domain(prod_event) == "csci-e-11.org"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
