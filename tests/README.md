# Tests

    pip install -r ../requirements.txt pytest
    pytest tests/ -q

## What is here

- **`test_security.py`** — the password and token layer. Needs only `cryptography`, so it
  runs anywhere the backend runs, with or without pytest:
  `python3 tests/test_security.py`. **Verified passing** (15 checks).
- **`test_api.py`** — role boundaries, ownership isolation, CSRF enforcement, sign-in rate
  limiting and secret leakage, driven in-process through FastAPI's `TestClient` against a
  throwaway database. Needs `fastapi` and `pytest`.
  **Not yet executed** — written in an environment with no access to the package index, so
  the assertions are reasoned from the source rather than observed. Run it once and fix any
  fixture mismatches before trusting a green result.
- **`smoke_test.py`** — read-only checks against an already-running server:
  `python3 tests/smoke_test.py http://127.0.0.1:8765`.

## Why these tests exist

`test_api.py` covers the properties that would be expensive to get wrong and easy to break
silently: a family account reaching staff or management data, one family seeing another's
swimmers, a state-changing request succeeding without a CSRF token, credentials appearing
in an API payload. Two different agents take turns editing this repo. Keep these green.
