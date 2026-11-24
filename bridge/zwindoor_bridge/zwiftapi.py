"""The few Zwift web calls the Companion link needs, plus the launcher sign-in for the Windows shell.

Undocumented endpoints, as used by Sauce for Zwift and RoadCaptain (protocol facts, see
docs/architecture.md). Using them contradicts Zwift's terms of service; the Companion link is therefore
opt-in and private.

Tretlager brings its own sign-in (core/login.py) and only hands the access token in.
"""

from __future__ import annotations

import json
import secrets
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://us-or-rly101.zwift.com"
REALM = "https://secure.zwift.com/auth/realms/zwift/protocol/openid-connect"
CLIENT_ID = "Game_Launcher"
REDIRECT = "https://launcher.zwift.com/launcher"
HEADERS = {"Source": "Game Client", "User-Agent": "Zwindoor"}
TIMEOUT = 15


class ZwiftApiError(Exception):
    pass


def _request(method: str, url: str, token: str | None = None, body: dict | None = None,
             form: dict | None = None, opener=urllib.request.urlopen) -> bytes:
    headers = dict(HEADERS, Accept="application/json")
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener(req, timeout=TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise ZwiftApiError(f"{method} {urllib.parse.urlparse(url).path}: HTTP {e.code}") from None
    except (urllib.error.URLError, OSError) as e:
        raise ZwiftApiError(f"{method} {urllib.parse.urlparse(url).path}: {e}") from None


def athlete_id(token: str, opener=urllib.request.urlopen) -> int:
    profile = json.loads(_request("GET", f"{API}/api/profiles/me", token, opener=opener))
    return int(profile["id"])


def register_phone(token: str, address: str, port: int, opener=urllib.request.urlopen) -> None:
    """Tell Zwift where "the phone" listens; the running game then connects to it (plain TCP).
    Replaces the address of the real Companion app – only one phone per account."""
    _request("PUT", f"{API}/relay/profiles/me/phone", token,
             body={"phoneAddress": address, "port": port, "protocol": "TCP"}, opener=opener)


def lan_address() -> str:
    """IPv4 address of the interface with the default route (no packet is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("1.1.1.1", 53))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# --- Launcher sign-in (Windows shell) ---------------------------------------------

def new_state() -> str:
    return secrets.token_hex(16)


def auth_url(state: str) -> str:
    q = urllib.parse.urlencode({"response_type": "code", "client_id": CLIENT_ID, "redirect_uri": REDIRECT,
                                "scope": "openid", "login": "true", "state": state})
    return f"{REALM}/auth?{q}"


def parse_redirect(url: str, expected_state: str | None = None) -> str:
    """Authorization code from the address Zwift redirects to after the sign-in."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url.strip()).query)
    if "error" in q:
        raise ZwiftApiError(q.get("error_description", q["error"])[0])
    if expected_state and q.get("state", [""])[0] != expected_state:
        raise ZwiftApiError("sign-in address belongs to another attempt")
    code = q.get("code", [""])[0]
    if not code:
        raise ZwiftApiError("no sign-in code in the address")
    return code


def _token(form: dict, opener=urllib.request.urlopen) -> dict:
    token = json.loads(_request("POST", f"{REALM}/token", form=form, opener=opener))
    if "access_token" not in token:
        raise ZwiftApiError("no access token in the answer")
    token["obtained_at"] = int(time.time())
    return token


def exchange_code(code: str, opener=urllib.request.urlopen) -> dict:
    return _token({"client_id": CLIENT_ID, "redirect_uri": REDIRECT, "code": code,
                   "grant_type": "authorization_code"}, opener)


def refresh(token: dict, opener=urllib.request.urlopen) -> dict:
    return _token({"client_id": CLIENT_ID, "grant_type": "refresh_token",
                   "refresh_token": token["refresh_token"]}, opener)


def access_left(token: dict, now: float | None = None) -> int:
    now = time.time() if now is None else now
    return int(token.get("obtained_at", 0) + token.get("expires_in", 0) - now)


def refresh_left(token: dict, now: float | None = None) -> int:
    now = time.time() if now is None else now
    return int(token.get("obtained_at", 0) + token.get("refresh_expires_in", 0) - now)
