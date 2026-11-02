"""Access tokens (RFC 8725): only HS256 tokens signed by this server with exp, iat and sub are
accepted; header fields are not read; sign-out and a password change refuse every token issued
before them on every route that requires a sign-in; a sign-in for an unknown email costs the same
bcrypt check as a wrong password."""
import base64
import hashlib
import hmac
import json
import time
from datetime import timedelta

import jwt
import pytest
from fastapi.routing import APIRoute

import services.accounts as accounts
import services.security as security
from routers.errors import _depends_on
from tests.unit.authz_world import PASSWORD, world


@pytest.fixture
def w(tmp_path, monkeypatch):
    with world(tmp_path, monkeypatch) as built:
        yield built


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _forge(header: dict, claims: dict, key: bytes = None, digest=hashlib.sha256) -> str:
    """A JWT with any header; signed with HMAC over ``key`` (empty signature without a key)."""
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
    signature = hmac.new(key, signing_input.encode(), digest).digest() if key is not None else b""
    return f"{signing_input}.{_b64(signature)}"


def _claims(w, user_id, **over):
    user = w.get_user(user_id)
    now = int(time.time())
    claims = {"sub": user.email, "uid": user_id, "iat": now - 5, "exp": now + 600, "aud": security.TOKEN_AUDIENCE}
    claims.update(over)
    return {k: v for k, v in claims.items() if v is not None}


def _me(w, token):
    return w.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def _login(w, email, password=PASSWORD):
    return w.client.post("/auth/token", data={"username": email, "password": password})


_KEY = security.SECRET_KEY.encode()


def test_a_token_this_server_signed_is_accepted(w):
    uid = w.user()
    assert _me(w, _forge({"alg": "HS256", "typ": "JWT"}, _claims(w, uid), _KEY)).status_code == 200


@pytest.mark.parametrize("case", [
    "alg_none", "alg_none_upper", "hs512_same_key", "hs384_same_key", "rs256_header", "es256_header",
    "other_key", "missing_exp", "missing_iat", "missing_sub", "expired", "expired_one_second",
    "iat_in_future", "iat_string", "exp_string", "sub_number", "uid_other_account", "no_signature",
])
def test_rfc8725_negative_tokens_are_refused(w, case):
    uid, other = w.user(), w.user()
    now = int(time.time())
    hs256 = {"alg": "HS256", "typ": "JWT"}
    tokens = {
        "alg_none": lambda: _forge({"alg": "none", "typ": "JWT"}, _claims(w, uid)),
        "alg_none_upper": lambda: _forge({"alg": "None"}, _claims(w, uid)),
        "hs512_same_key": lambda: _forge({"alg": "HS512"}, _claims(w, uid), _KEY, hashlib.sha512),
        "hs384_same_key": lambda: _forge({"alg": "HS384"}, _claims(w, uid), _KEY, hashlib.sha384),
        "rs256_header": lambda: _forge({"alg": "RS256"}, _claims(w, uid), _KEY),
        "es256_header": lambda: _forge({"alg": "ES256"}, _claims(w, uid), _KEY),
        "other_key": lambda: _forge(hs256, _claims(w, uid), b"not the server key" * 4),
        "missing_exp": lambda: _forge(hs256, _claims(w, uid, exp=None), _KEY),
        "missing_iat": lambda: _forge(hs256, _claims(w, uid, iat=None), _KEY),
        "missing_sub": lambda: _forge(hs256, _claims(w, uid, sub=None), _KEY),
        "expired": lambda: _forge(hs256, _claims(w, uid, exp=now - 60), _KEY),
        "expired_one_second": lambda: _forge(hs256, _claims(w, uid, exp=now - 1), _KEY),
        "iat_in_future": lambda: _forge(hs256, _claims(w, uid, iat=now + 60), _KEY),
        "iat_string": lambda: _forge(hs256, _claims(w, uid, iat="yesterday"), _KEY),
        "exp_string": lambda: _forge(hs256, _claims(w, uid, exp="tomorrow"), _KEY),
        "sub_number": lambda: _forge(hs256, _claims(w, uid, sub=12345), _KEY),
        "uid_other_account": lambda: _forge(hs256, _claims(w, uid, uid=other), _KEY),
        "no_signature": lambda: _forge(hs256, _claims(w, uid)),
    }
    response = _me(w, tokens[case]())
    assert response.status_code == 401, (case, response.text)
    assert response.headers["www-authenticate"] == "Bearer"


def test_header_fields_naming_keys_are_not_read(w, monkeypatch):
    uid = w.user()
    fetched = []
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: fetched.append(a) or None)
    header = {"alg": "HS256", "kid": "../../../../etc/passwd", "jku": "https://evil.example/jwks.json",
              "x5u": "https://evil.example/cert.pem", "jwk": {"kty": "oct", "k": _b64(b"attacker")}}
    assert _me(w, _forge(header, _claims(w, uid), _KEY)).status_code == 200
    assert _me(w, _forge(header, _claims(w, uid), b"attacker")).status_code == 401
    assert fetched == []


def test_the_decoder_requires_exp_iat_sub_and_this_audience():
    assert security.REQUIRED_CLAIMS == ("exp", "iat", "sub", "aud")
    token = jwt.encode({"sub": "a@example.org", "iat": int(time.time()), "aud": security.TOKEN_AUDIENCE},
                       security.SECRET_KEY, algorithm="HS256")
    with pytest.raises(jwt.MissingRequiredClaimError):
        security.decode_access_token(token)
    now = int(time.time())
    for aud in (None, "another-service", ["another-service"]):
        claims = {"sub": "a@example.org", "iat": now, "exp": now + 60, "aud": aud}
        token = jwt.encode({k: v for k, v in claims.items() if v is not None}, security.SECRET_KEY, algorithm="HS256")
        with pytest.raises(jwt.PyJWTError):
            security.decode_access_token(token)


def test_deleted_and_deactivated_accounts_are_refused(w):
    gone, off = w.user(), w.user()
    gone_token, off_token = w.token(gone), w.token(off)
    with w.session() as db:
        accounts.delete_account(db, db.get(accounts.models.User, gone))
    w.set_active(off, False)
    assert _me(w, gone_token).status_code == 401
    refused = _me(w, off_token)
    assert refused.status_code == 403 and refused.json()["detail"] == "This account has been deactivated"


def test_sign_out_refuses_every_earlier_token_of_the_account_only(w):
    uid, other = w.user(), w.user()
    first, second, others = w.token(uid), w.token(uid), w.token(other)
    out = w.client.post("/auth/logout", headers={"Authorization": f"Bearer {first}"})
    assert out.status_code == 204 and out.content == b""
    assert _me(w, first).status_code == 401
    assert _me(w, second).status_code == 401
    assert _me(w, others).status_code == 200
    assert w.client.post("/auth/logout", headers={"Authorization": f"Bearer {first}"}).status_code == 401
    assert w.get_user(uid).tokens_valid_after is not None and w.get_user(other).tokens_valid_after is None


def test_signing_in_right_after_signing_out_gives_a_working_token(w):
    uid = w.user()
    email = w.get_user(uid).email
    for _ in range(3):
        token = _login(w, email).json()["access_token"]
        assert _me(w, token).status_code == 200
        assert w.client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 204
        assert _me(w, token).status_code == 401
    assert _me(w, _login(w, email).json()["access_token"]).status_code == 200


def test_tokens_issued_before_the_cutoff_are_refused_and_at_it_accepted(w):
    uid = w.user()
    with w.session() as db:
        user = db.get(accounts.models.User, uid)
        cutoff = security.revoke_tokens(user).timestamp()
        db.commit()
    assert cutoff == int(cutoff) and cutoff > time.time()
    before = _forge({"alg": "HS256"}, _claims(w, uid, iat=int(cutoff) - 1), _KEY)
    assert _me(w, before).status_code == 401
    time.sleep(max(0.0, cutoff - time.time()))
    at = _forge({"alg": "HS256"}, _claims(w, uid, iat=int(cutoff)), _KEY)
    assert _me(w, at).status_code == 200


def test_a_signed_out_token_is_refused_by_every_route_that_requires_a_sign_in(w):
    import main
    from services.security import get_current_user
    uid = w.user()
    token = w.token(uid)
    assert w.client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 204
    routes = [(m, r.path) for r in main.app.routes if isinstance(r, APIRoute)
              and _depends_on(r.dependant, get_current_user) for m in sorted(r.methods)]
    assert len(routes) >= 19
    for method, path in routes:
        url = path.replace("{", "").replace("}", "")
        for name in ("circuit_id", "run_id", "job_id", "link_id"):
            url = url.replace(name, "00000000-0000-4000-8000-000000000000")
        response = w.client.request(method, url, json={}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401, (method, path, response.status_code, response.text)


def test_a_signed_out_token_makes_a_request_anonymous_where_a_sign_in_is_optional(w):
    uid = w.user()
    token = w.token(uid)
    with w.session() as db:
        assert security.get_optional_user(token, db).id == uid
        assert w.client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 204
        assert security.get_optional_user(token, db) is None


def test_changing_the_password_refuses_earlier_tokens_and_returns_a_new_one(w):
    uid = w.user()
    email = w.get_user(uid).email
    old = w.token(uid)
    answer = w.client.post("/auth/password", headers={"Authorization": f"Bearer {old}"},
                           json={"current_password": PASSWORD, "new_password": "a new long password"})
    assert answer.status_code == 200, answer.text
    assert answer.json()["token_type"] == "bearer" and answer.json()["expires_in"] > 0
    assert _me(w, old).status_code == 401
    assert _me(w, answer.json()["access_token"]).status_code == 200
    assert _login(w, email).status_code == 401
    assert _login(w, email, "a new long password").status_code == 200


@pytest.mark.parametrize("body, status", [
    ({"current_password": "wrong password", "new_password": "a new long password"}, 403),
    ({"current_password": PASSWORD, "new_password": "short"}, 422),
    ({"current_password": PASSWORD, "new_password": "x" * 73}, 422),
    ({"current_password": PASSWORD}, 422),
    ({"current_password": PASSWORD, "new_password": "a new long password", "extra": 1}, 422),
])
def test_a_refused_password_change_changes_nothing(w, body, status):
    uid = w.user()
    token = w.token(uid)
    before = w.get_user(uid).hashed_password
    answer = w.client.post("/auth/password", headers={"Authorization": f"Bearer {token}"}, json=body)
    assert answer.status_code == status, answer.text
    assert w.get_user(uid).hashed_password == before and w.get_user(uid).tokens_valid_after is None
    assert _me(w, token).status_code == 200


def test_sign_out_and_password_change_are_rate_limited_per_account(w):
    from routers import auth
    from routers.rate_limit import is_rate_limited
    assert is_rate_limited(auth.logout) and is_rate_limited(auth.change_password)


def test_sign_in_for_an_unknown_email_costs_one_bcrypt_check(w, monkeypatch):
    known = w.get_user(w.user()).email
    calls = []
    real = security.bcrypt.checkpw
    monkeypatch.setattr(security.bcrypt, "checkpw", lambda pw, h: calls.append(h) or real(pw, h))
    accounts._unknown_account_hash()
    unknown = _login(w, "nobody-here@example.org")
    wrong = _login(w, known, "not the password")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json() == {"detail": "Incorrect email or password"}
    assert len(calls) == 2


def test_the_server_offers_logout_to_clients():
    from services.server_info import FEATURES
    assert FEATURES["logout"] == 1


def test_the_signature_key_is_at_least_256_bits():
    assert len(security.SECRET_KEY.encode()) >= 32


def test_tokens_last_the_configured_time():
    from config import settings
    token = security.create_access_token({"sub": "a@example.org"}, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    claims = security.decode_access_token(token)
    assert claims["aud"] == security.TOKEN_AUDIENCE
    assert claims["exp"] - claims["iat"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
