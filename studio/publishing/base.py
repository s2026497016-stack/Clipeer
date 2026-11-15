"""Common publishing helpers.

Adapters deliberately return only after the platform has acknowledged a post.  A
network exception is never interpreted as a successful upload.
"""
import base64
import json
import os
import secrets
import time
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .. import config

TOKEN_FIELDS = {"access_token", "refresh_token", "token"}
_KEY_CACHE = None


class PublishingError(RuntimeError):
    """A platform rejected, or did not confirm, a publish operation."""


def _key() -> bytes:
    global _KEY_CACHE
    if _KEY_CACHE is not None:
        return _KEY_CACHE
    raw = config.env("CLIPEER_PUBLISHING_KEY", "").strip()
    path = config.env("CLIPEER_PUBLISHING_KEY_FILE", "").strip()
    if not raw and path and Path(path).exists():
        raw = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
    if not raw:
        path = config.DATA_DIR / "publishing.key"
        if path.exists():
            raw = path.read_text(encoding="utf-8", errors="ignore").strip()
        else:
            raw = secrets.token_urlsafe(32)
            path.write_text(raw + "\n", encoding="utf-8")
            try:
                path.chmod(0o600)
            except OSError:
                pass
    import hashlib
    _KEY_CACHE = hashlib.sha256(raw.encode("utf-8")).digest()
    return _KEY_CACHE


def encrypt_token(value: str) -> str:
    """Encrypt a token with an authenticated, versioned AES-GCM envelope."""
    if not value:
        return value
    nonce = secrets.token_bytes(12)
    body = nonce + AESGCM(_key()).encrypt(nonce, value.encode("utf-8"), b"weegloo")
    return "enc:v2:" + base64.urlsafe_b64encode(body).decode()


def decrypt_token(value: str) -> str:
    if not isinstance(value, str) or not value.startswith(("enc:v1:", "enc:v2:")):
        return value
    if value.startswith("enc:v1:"):
        raise PublishingError("Legacy publishing token format requires re-authentication.")
    try:
        blob = base64.urlsafe_b64decode(value[7:])
        nonce, cipher = blob[:12], blob[12:]
        return AESGCM(_key()).decrypt(nonce, cipher, b"weegloo").decode("utf-8")
    except Exception as exc:
        raise PublishingError("Stored publishing token cannot be decrypted.") from exc


def protect_account(account: dict) -> dict:
    out = dict(account)
    for field in TOKEN_FIELDS:
        if out.get(field) and not str(out[field]).startswith("enc:v2:"):
            out[field] = encrypt_token(str(out[field]))
    return out


def reveal_account(account: dict) -> dict:
    out = dict(account)
    for field in TOKEN_FIELDS:
        if out.get(field):
            out[field] = decrypt_token(out[field])
    return out


class Publisher:
    platform = ""

    def publish(self, account, path: Path, **kwargs):
        raise NotImplementedError

    def refresh(self, account):
        return account

    def disconnect(self, account):
        account.clear()


_PUBLISHERS = {}


def get_publisher(platform: str) -> Publisher:
    if platform not in _PUBLISHERS:
        from .instagram import InstagramPublisher
        from .tiktok import TikTokPublisher
        from .youtube import YouTubePublisher
        _PUBLISHERS.update(youtube=YouTubePublisher(), instagram=InstagramPublisher(), tiktok=TikTokPublisher())
    try:
        return _PUBLISHERS[platform]
    except KeyError as exc:
        raise PublishingError(f"Unsupported publishing platform: {platform}") from exc


class DurableState:
    """Small atomic JSON state helper for callers outside the legacy queue."""
    def __init__(self, path: Path):
        self.path = path

    def load(self):
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, (dict, list)) else {}
        except (OSError, ValueError):
            return {}

    def save(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(value, indent=1), encoding="utf-8")
        tmp.replace(self.path)

