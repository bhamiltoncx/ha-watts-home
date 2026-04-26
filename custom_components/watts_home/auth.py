"""Azure AD B2C PKCE authentication for the Watts Home API."""
from __future__ import annotations

import base64
import hashlib
import json
import urllib.parse
from typing import Any

from curl_cffi.requests import AsyncSession

from .const import (
    AUTH_HOST,
    BROWSER_UA,
    CLIENT_ID,
    CODE_VERIFIER,
    POLICY,
    REDIRECT_URI,
    SCOPE,
    TENANT,
)


class WattsAuthError(Exception):
    """Base authentication exception."""


class WattsTokenExpiredError(WattsAuthError):
    """Raised when the refresh token is expired or rejected (4xx)."""


def code_challenge(verifier: str) -> str:
    """Return the S256 PKCE code challenge for *verifier*."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class WattsAuth:
    """Static-method namespace for Watts Home authentication helpers."""

    @staticmethod
    async def login(
        session: AsyncSession, username: str, password: str
    ) -> dict[str, Any]:
        """Authenticate with Azure AD B2C and return a token dict.

        Steps:
          1. GET the authorize URL to seed session cookies.
          2. POST credentials to the SelfAsserted endpoint.
          3. GET the confirmed URL (no redirect) to obtain the auth code.
          4. Exchange the auth code for tokens.
        """
        # ------------------------------------------------------------------
        # Step 1: GET authorize URL
        # ------------------------------------------------------------------
        challenge = code_challenge(CODE_VERIFIER)

        # Build query string manually so scope uses "+" not "%20" and we
        # never double-encode the "+" signs already in the scope string.
        scope_plus = SCOPE.replace(" ", "+")
        params = (
            f"scope={scope_plus}"
            f"&response_type=code"
            f"&client_id={CLIENT_ID}"
            f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
            f"&prompt=login"
            f"&code_challenge={challenge}"
            f"&code_challenge_method=S256"
            f"&client_info=1"
            f"&haschrome=1"
        )
        authorize_url = (
            f"{AUTH_HOST}/tfp/{TENANT}/{POLICY}/oauth2/v2.0/authorize?{params}"
        )

        resp = await session.get(authorize_url, headers={"User-Agent": BROWSER_UA})
        if resp.status_code != 200:
            raise WattsAuthError(
                f"Authorize GET failed: HTTP {resp.status_code}"
            )

        # ------------------------------------------------------------------
        # Extract csrf + transaction_cid from cookies
        # ------------------------------------------------------------------
        csrf: str | None = None
        transaction_cid: str | None = None

        for name, value in resp.cookies.items():
            if name == "x-ms-cpim-csrf":
                csrf = value
            elif name == "x-ms-cpim-trans":
                padded = value + "=" * (-len(value) % 4)
                decoded = json.loads(base64.b64decode(padded))
                transaction_cid = decoded["C_ID"]

        if not csrf:
            raise WattsAuthError("Missing x-ms-cpim-csrf cookie after authorize GET")
        if not transaction_cid:
            raise WattsAuthError(
                "Missing x-ms-cpim-trans cookie / C_ID after authorize GET"
            )

        # Build transactionEncoded (base64url WITH padding = Go's url.URLEncoding)
        tid_json = json.dumps({"TID": transaction_cid}, separators=(",", ":"))
        transaction_encoded = base64.urlsafe_b64encode(tid_json.encode()).decode()

        # ------------------------------------------------------------------
        # Step 2: POST credentials to SelfAsserted
        # ------------------------------------------------------------------
        self_asserted_url = (
            f"{AUTH_HOST}/{TENANT}/{POLICY}/SelfAsserted"
            f"?tx=StateProperties={transaction_encoded}"
            f"&p={POLICY}"
        )
        form_body = urllib.parse.urlencode(
            {
                "request_type": "RESPONSE",
                "signInName": username,
                "password": password,
            }
        )
        resp = await session.post(
            self_asserted_url,
            data=form_body.encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": BROWSER_UA,
                "X-CSRF-TOKEN": csrf,
                "Referer": authorize_url,
            },
        )
        if resp.status_code != 200:
            raise WattsAuthError(
                f"SelfAsserted POST failed: HTTP {resp.status_code}"
            )
        result = resp.json()
        if result.get("status") != "200":
            raise WattsAuthError(f"Credentials rejected: {resp.text}")

        # ------------------------------------------------------------------
        # Step 3: GET confirmed → 302 with auth code
        # ------------------------------------------------------------------
        confirm_url = (
            f"{AUTH_HOST}/{TENANT}/{POLICY}"
            f"/api/CombinedSigninAndSignup/confirmed"
            f"?rememberMe=true"
            f"&csrf_token={csrf}"
            f"&tx=StateProperties={transaction_encoded}"
        )
        resp = await session.get(
            confirm_url,
            allow_redirects=False,
            headers={
                "User-Agent": BROWSER_UA,
                "Referer": authorize_url,
            },
        )
        if resp.status_code != 302:
            raise WattsAuthError(
                f"Confirmed GET expected 302, got HTTP {resp.status_code}"
            )

        location = resp.headers.get("Location", "")
        parsed = urllib.parse.urlparse(location)
        qs = urllib.parse.parse_qs(parsed.query)
        if "code" not in qs:
            raise WattsAuthError(
                f"No 'code' param in redirect Location: {location!r}"
            )
        auth_code = qs["code"][0]

        # ------------------------------------------------------------------
        # Step 4: Exchange code for tokens
        # ------------------------------------------------------------------
        return await WattsAuth._exchange_code(session, auth_code)

    @staticmethod
    async def _exchange_code(
        session: AsyncSession, code: str
    ) -> dict[str, Any]:
        """POST the auth code to the token endpoint and return the token dict."""
        token_url = (
            f"{AUTH_HOST}/tfp/{TENANT}/{POLICY}/oauth2/v2.0/token?haschrome=1"
        )
        # Scope must use literal "+" separators in form bodies (not %20 / %2B).
        scope_encoded = SCOPE.replace(" ", "+")
        body = (
            f"client_id={CLIENT_ID}"
            f"&scope={scope_encoded}"
            f"&client_info=1"
            f"&grant_type=authorization_code"
            f"&code={urllib.parse.quote(code, safe='')}"
            f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
            f"&code_verifier={CODE_VERIFIER}"
        )
        resp = await session.post(
            token_url,
            data=body.encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": BROWSER_UA,
            },
        )
        if resp.status_code >= 400:
            raise WattsAuthError(
                f"Token exchange failed: HTTP {resp.status_code} — {resp.text}"
            )
        return resp.json()

    @staticmethod
    async def refresh(
        session: AsyncSession, refresh_token: str
    ) -> dict[str, Any]:
        """Use a refresh token to obtain new tokens.

        Raises WattsTokenExpiredError if the server returns 4xx.
        """
        token_url = (
            f"{AUTH_HOST}/tfp/{TENANT}/{POLICY}/oauth2/v2.0/token?haschrome=1"
        )
        scope_encoded = SCOPE.replace(" ", "+")
        body = (
            f"client_id={CLIENT_ID}"
            f"&scope={scope_encoded}"
            f"&client_info=1"
            f"&grant_type=refresh_token"
            f"&refresh_token={urllib.parse.quote(refresh_token, safe='')}"
            f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        )
        resp = await session.post(
            token_url,
            data=body.encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": BROWSER_UA,
            },
        )
        if resp.status_code >= 400:
            raise WattsTokenExpiredError(
                f"Refresh token rejected: HTTP {resp.status_code} — {resp.text}"
            )
        return resp.json()
