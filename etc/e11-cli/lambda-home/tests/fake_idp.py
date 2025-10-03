# Minimal Fake OIDC Provider (discovery, authorize, token, jwks)
import logging
import base64
import hashlib
import threading
import time
from flask import Flask, request, jsonify, redirect


def create_app(issuer, private_key_pem, jwk):
    app = Flask(__name__)
    app.issuer = issuer

    # auth_code -> {client_id, redirect_uri, state, nonce, code_challenge, method}
    CODES = {}

    @app.get("/.well-known/openid-configuration")
    def discovery():
        return jsonify({
            "issuer": app.issuer,
            "authorization_endpoint": f"{app.issuer}/oauth2/v1/authorize",
            "token_endpoint": f"{app.issuer}/oauth2/v1/token",
            "jwks_uri": f"{app.issuer}/oauth2/v1/keys",
            "id_token_signing_alg_values_supported": ["RS256"],
        })

    @app.get("/oauth2/v1/authorize")
    def authorize():
        # Simulate user consent → redirect back with code & original state
        q = request.args
        code = base64.urlsafe_b64encode(hashlib.sha256(
            f"{q.get('client_id')}|{q.get('nonce')}|{time.time()}".encode()
        ).digest())[:24].decode().rstrip("=")
        CODES[code] = {
            "client_id": q.get("client_id"),
            "redirect_uri": q.get("redirect_uri"),
            "state": q.get("state"),
            "nonce": q.get("nonce"),
            "code_challenge": q.get("code_challenge"),
            "method": q.get("code_challenge_method", "S256"),
            "scope": q.get("scope", ""),
        }
        redir = f"{q.get('redirect_uri')}?code={code}&state={q.get('state')}"
        return redirect(redir, code=302)

    @app.post("/oauth2/v1/token")
    def token():
        from jwt import encode
        data = request.form
        code = data.get("code")
        cv = data.get("code_verifier")
        client_id = data.get("client_id", request.authorization.username if request.authorization else None)
        logging.getLogger().debug("data=%s client_id=%s",data,client_id)

        if code not in CODES:
            return jsonify(error="invalid_grant", error_description="unknown code"), 400
        record = CODES.pop(code)
        logging.getLogger().debug("record=%s",record)

        # Verify client_id matches the one that initiated auth (basic check)
        if client_id != record["client_id"]:
            return jsonify(error="invalid_client", error_description=f"client_id mismatch received={client_id} expected={record['client_id']} record={record}"), 401

        # Verify PKCE
        if record["method"] == "S256":
            expected = base64.urlsafe_b64encode(hashlib.sha256(cv.encode()).digest()).decode().rstrip("=")
        else:
            expected = cv
        if expected != record["code_challenge"]:
            return jsonify(error="invalid_grant", error_description="pkce verification failed"), 400

        now = int(time.time())
        claims = {
            "iss": app.issuer,
            "aud": client_id,
            "sub": "test-sub-123",
            "iat": now,
            "exp": now + 3600,
            "nonce": record["nonce"],
            "email": "alice@example.edu",
            "email_verified": True,
            "name": "Alice Example",
            "given_name": "Alice",
            "family_name": "Example",
        }
        id_token = encode(claims, private_key_pem, algorithm="RS256", headers={"typ": "JWT", "alg": "RS256", "kid": jwk["kid"]})
        return jsonify({
            "access_token": "fake-access",
            "token_type": "Bearer",
            "expires_in": 3600,
            "id_token": id_token,
            "scope": record["scope"],
        })

    @app.get("/oauth2/v1/keys")
    def keys():
        return jsonify({"keys": [jwk]})

    return app

class ServerThread(threading.Thread):
    def __init__(self, app, host="127.0.0.1", port=0):
        super().__init__(daemon=True)
        from werkzeug.serving import make_server
        self.srv = make_server(host, port, app)
        self.port = self.srv.server_port
    def run(self):
        self.srv.serve_forever()
    def stop(self):
        self.srv.shutdown()
