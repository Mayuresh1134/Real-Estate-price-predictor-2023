"""Local user accounts.

Passwords are never stored. Each account keeps a random salt and a
PBKDF2-HMAC-SHA256 hash of the password, so reading the accounts file does not
reveal anyone's password.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path

ITERATIONS = 240_000
MIN_PASSWORD_LENGTH = 8
_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{2,29}$")


class AuthError(Exception):
    """A sign-in or sign-up problem, with a message that can be shown as is."""


def _hash(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


class UserStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    # -- file handling ----------------------------------------------------
    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Never overwrite a file we could not read: that would erase every account.
            raise AuthError(
                f"The accounts file could not be read ({self.path.name}). "
                "Fix or remove it, then try again."
            ) from exc
        return data if isinstance(data, dict) else {}

    def _save(self, users: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(users, indent=2), encoding="utf-8")
        os.replace(temp, self.path)   # atomic: the file is never half-written

    # -- public API -------------------------------------------------------
    def register(self, username: str, password: str, confirm: str) -> str:
        username = username.strip()
        if not _USERNAME.match(username):
            raise AuthError(
                "Choose a username of 3 to 30 characters: letters, numbers, "
                "spaces, dots, dashes or underscores."
            )
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AuthError(f"Use a password of at least {MIN_PASSWORD_LENGTH} characters.")
        if password != confirm:
            raise AuthError("The two passwords do not match.")
        users = self._load()
        if username.lower() in users:
            raise AuthError("That username is taken. Sign in, or pick another name.")
        salt = secrets.token_bytes(16)
        users[username.lower()] = {
            "name": username,
            "salt": salt.hex(),
            "hash": _hash(password, salt, ITERATIONS),
            "iterations": ITERATIONS,
        }
        self._save(users)
        return username

    def sign_in(self, username: str, password: str) -> str:
        """Return the account's display name, or raise AuthError."""
        record = self._load().get(username.strip().lower())
        # Same message for "no such user" and "wrong password" on purpose.
        failure = AuthError("That username and password do not match an account.")
        if not record:
            raise failure
        expected = record["hash"]
        actual = _hash(password, bytes.fromhex(record["salt"]), int(record["iterations"]))
        if not hmac.compare_digest(expected, actual):
            raise failure
        return record.get("name", username.strip())

    def has_accounts(self) -> bool:
        return bool(self._load())
