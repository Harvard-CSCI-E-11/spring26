ChatGPT notes:

How this works

* **Fake IdP**: Flask app serves discovery, /authorize (redirect back with code/state), /token (validates PKCE, signs an RS256 ID token), and /keys (JWKS).

* **No AWS**: Tests monkeypatch home._boto_secrets and home.table with in‑memory fakes; env vars are set so your code paths run unchanged.

* **End‑to‑end**: test_oidc_flow.py validates the stateless PKCE+state logic; test_home_handler.py hits your Lambda handler routes with synthetic API Gateway events.
