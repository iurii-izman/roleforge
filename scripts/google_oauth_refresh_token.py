#!/usr/bin/env python3
"""
One-time OAuth2 flow: read client_id and client_secret from keyring, open browser
for consent, then store refresh_token in keyring (domain=google, key=refresh_token).

Requires: client_id and client_secret already in keyring (scripts/roleforge-keyring.sh set google client_id/client_secret).
Run from repo root. Uses Gmail read scope for RoleForge intake.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Gmail read-only: list and get messages (intake).
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

REPO_ROOT = Path(__file__).resolve().parent.parent


def keyring_get(domain: str, key: str) -> str:
    """Read secret from roleforge keyring."""
    out = subprocess.run(
        [str(REPO_ROOT / "scripts" / "roleforge-keyring.sh"), "get", domain, key],
        check=True,
        text=True,
        capture_output=True,
    )
    return out.stdout.strip()


def keyring_set(domain: str, key: str, value: str) -> None:
    """Write secret to roleforge keyring via secret-tool (same attributes as keyring script)."""
    subprocess.run(
        [
            "secret-tool",
            "store",
            f"--label=RoleForge {domain} {key}",
            "service", "roleforge",
            "domain", domain,
            "key", key,
        ],
        check=True,
        input=value.encode(),
    )


def main() -> int:
    client_id = keyring_get("google", "client_id")
    client_secret = keyring_get("google", "client_secret")
    if not client_id or not client_secret:
        print("Missing google client_id or client_secret in keyring.", file=sys.stderr)
        return 1

    from google_auth_oauthlib.flow import InstalledAppFlow

    config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/"],
        }
    }
    flow = InstalledAppFlow.from_client_config(config, scopes=SCOPES)
    print("Opening browser for Google sign-in. Use the same account that will receive job alerts.")
    creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")
    refresh = getattr(creds, "refresh_token", None)
    if not refresh:
        print("No refresh_token in response (e.g. already consented). Revoke app access and run again, or use a new account.", file=sys.stderr)
        return 1
    keyring_set("google", "refresh_token", refresh)
    print("Stored refresh_token in keyring (google / refresh_token). You can close the browser.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
