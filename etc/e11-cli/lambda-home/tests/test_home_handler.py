import urllib.parse
import requests
import logging

import home_app.home as home
import home_app.sessions as sessions
import home_app.common as common
import home_app.oidc as oidc

def _api_event(path, *, qs=None, cookies=None, method='GET', body=None):
    return {
        "rawPath": path,
        "queryStringParameters": qs or {},
        "requestContext": {"http": {"method": method, "sourceIp": "203.0.113.9"}, "stage": ""},
        "isBase64Encoded": False,
        "body": body,
        "cookies" : cookies or {}
    }

def test_lambda_routes_without_aws(fake_idp_server, fake_aws, monkeypatch):
    # Set up mocked AWS services manually since the fixture doesn't seem to be working
    import json

    class FakeSecrets:
        def get_secret_value(self, SecretId):
            return {"SecretString": json.dumps({
                "oidc_discovery_endpoint": fake_idp_server["discovery"],
                "client_id": "client-123",
                "redirect_uri": "https://app.example.org/auth/callback",
                "hmac_secret": "super-secret-hmac",
                "secret_key": "client-secret-xyz",
            })}

    class FakeTable:
        def __init__(self):
            self.db = {}

        def put_item(self, Item):
            # Store the item in our fake database
            key = f"{Item.get('user_id', '')}#{Item.get('sk', '')}"
            self.db[key] = Item
            return {}

        def query(self, **kwargs):
            # Handle GSI queries
            if kwargs.get("IndexName") == "GSI_Email":
                key_condition = kwargs.get("KeyConditionExpression")
                if key_condition == "email = :e":
                    email = kwargs.get("ExpressionAttributeValues", {}).get(":e")
                    items = []
                    for item in self.db.values():
                        if item.get("email") == email:
                            items.append(item)
                    return {
                        "Items": items,
                        "Count": len(items),
                        "LastEvaluatedKey": None
                    }
            return {"Items": [], "Count": 0, "LastEvaluatedKey": None}

    class FakeSessionsTable:
        def __init__(self):
            self.db = {}

        def put_item(self, Item):
            key = Item.get("sid", "")
            self.db[key] = Item
            return {}

        def get_item(self, Key):
            return {"Item": self.db.get(Key["sid"])}

        def delete_item(self, Key):
            self.db.pop(Key["sid"], None)

    # Set up the mocked services
    fake_users = FakeTable()
    fake_sessions = FakeSessionsTable()

    monkeypatch.setattr(common, "secretsmanager_client", FakeSecrets())
    monkeypatch.setattr(home, "users_table", fake_users)
    monkeypatch.setattr(home, "sessions_table", fake_sessions)

    # Also need to monkeypatch the users_table in common.py since add_user_log uses it
    monkeypatch.setattr(common, "users_table", fake_users)
    monkeypatch.setattr(common, "sessions_table", fake_sessions)

    # Also need to monkeypatch the users_table in sessions.py since add_user_log uses it
    monkeypatch.setattr(sessions, "users_table", fake_users)
    monkeypatch.setattr(sessions, "sessions_table", fake_sessions)

    # Debug: Check if the monkeypatch worked
    # print(f"After monkeypatch:")
    # print(f"users_table type: {type(home.users_table)}")
    # print(f"sessions_table type: {type(home.sessions_table)}")
    print(f"**1 secretsmanager_client type: {type(common.secretsmanager_client)}")

    # 1) GET "/" should embed login URL
    resp = home.lambda_handler(_api_event("/"), None)
    assert resp["statusCode"] == 200
    assert "harvard_key" in resp["body"] or "http" in resp["body"]

    # 2) Simulate full OIDC redirect:
    # Build auth URL from the same config to get a valid state
    cfg = oidc.load_openid_config(fake_idp_server["discovery"], client_id="client-123",
                                  redirect_uri="https://app.example.org/auth/callback")
    cfg["hmac_secret"] = "super-secret-hmac"
    cfg["secret_key"]  = "client-secret-xyz"
    auth_url, _ = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)
    r = requests.get(auth_url, allow_redirects=False)
    qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.headers["Location"]).query))

    # 3) Call the Lambda callback with the returned code/state
    cb_event = _api_event("/auth/callback", qs=qs)
    cb_resp  = home.lambda_handler(cb_event, None)
    print("cb_resp=",cb_resp)

    assert cb_resp["statusCode"] == 302
    assert cb_resp["headers"]["Location"] == "/dashboard"
    # cookie should be set
    assert cb_resp["cookies"]

    # 4) Dashboard route without cookies
    dash_resp = home.lambda_handler(_api_event("/dashboard"), None)
    logging.getLogger().debug("dash_resp without cookies=%s",dash_resp)
    assert dash_resp["statusCode"] == 302 and dash_resp['headers']['Location']=='/'

    # 4) Dashboard route without cookies
    dash_resp = home.lambda_handler(_api_event("/dashboard",cookies=cb_resp['cookies']), None)
    logging.getLogger().debug("dash_resp with cookies (%s) = %s",cb_resp['cookies'],dash_resp)
    logging.getLogger().warning("Not validating dashboard loging. Requires mocking DynamodB")

    # 5) Logout route
    logout_resp = home.lambda_handler(_api_event("/logout"), None)
    logging.getLogger().debug("logout_resp=%s",logout_resp)
    assert logout_resp["statusCode"] == 200
    assert "Max-Age=0;" in logout_resp['cookies'][0] # validate that it logs the user out
    assert "You have been logged out" in logout_resp['body']

    # 6) Check point
    home.lambda_handler(_api_event('/api/v1',method='POST',body='{"action":"ping"}'), None)
