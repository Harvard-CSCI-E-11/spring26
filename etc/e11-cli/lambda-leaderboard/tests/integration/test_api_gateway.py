"""
test_api_gateway.py

Integration tests for the leaderboard API Gateway Lambda handler.
Tests multiple routes to ensure the full integration works.

"""

import json
import pytest

from leaderboard_app.leaderboard import lambda_handler

#pylint: disable=line-too-long

class TestApiGateway:           # pylint: disable=missing-class-docstring
    @pytest.fixture()
    def apigw_event_base(self):
        """Base API Gateway event structure"""
        return {
            "version": "2.0",
            "routeKey": "GET /api/register",
            "rawPath": "/api/register",
            "rawQueryString": "",
            "requestContext": {
                "http": {
                    "method": "GET",
                    "path": "/api/register",
                    "protocol": "HTTP/1.1",
                    "sourceIp": "127.0.0.1",
                    "requestId": "test-request-id"
                },
                "stage": "prod"
            },
            "headers": {
                "Accept": "application/json",
                "User-Agent": "test-agent"
            },
            "isBase64Encoded": False
        }

    def test_api_register_get(self, apigw_event_base, dynamodb_local):
        """Test GET /api/register endpoint"""
        event = apigw_event_base.copy()
        ret = lambda_handler(event, None)

        assert ret["statusCode"] == 200
        data = json.loads(ret["body"])
        assert "name" in data
        assert "opaque" in data
        assert isinstance(data["name"], str)
        assert isinstance(data["opaque"], str)

    def test_api_ver(self, apigw_event_base):
        """Test GET /ver endpoint"""
        event = apigw_event_base.copy()
        event["routeKey"] = "GET /ver"
        event["rawPath"] = "/ver"
        event["requestContext"]["http"]["path"] = "/ver"

        ret = lambda_handler(event, None)

        assert ret["statusCode"] == 200
        # /ver returns just the version string, not JSON
        assert isinstance(ret["body"], str)
        assert len(ret["body"]) > 0

    def test_root_route(self, apigw_event_base):
        """Test GET / (root) endpoint"""
        event = apigw_event_base.copy()
        event["routeKey"] = "GET /"
        event["rawPath"] = "/"
        event["requestContext"]["http"]["path"] = "/"

        ret = lambda_handler(event, None)

        assert ret["statusCode"] == 200
        # Root route returns HTML - headers are lowercase in API Gateway v2
        content_type = ret.get("headers", {}).get("content-type", "").lower()
        assert "text/html" in content_type
        assert "<html" in ret["body"].lower() or "<!doctype" in ret["body"].lower()
