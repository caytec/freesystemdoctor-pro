"""
HMAC-signed license key generation and validation.

Key format:  FSD-{TIER}-{YEAR}-{BODY6}-{CSUM4}
Example:     FSD-PRO-2026-AB12CD-7E3F

BODY6: 6-char base32 random (~30 bits entropy, sufficient for our scale)
CSUM4: first 4 hex chars of HMAC-SHA256 of "TIER-YEAR-BODY" with secret key
"""

import os
import hmac
import hashlib
import secrets
import string


_PUBLIC_PREFIX = b"FSD-PRO-v1-"
_SECRET = os.environ.get("LICENSE_HMAC_SECRET", "DEMO_REPLACE_IN_PROD").encode()

_BASE32_ALPHA = string.ascii_uppercase + "23456789"   # 32 chars, no 0/1/O/I


def _checksum(body: str) -> str:
    return hmac.new(
        _SECRET, _PUBLIC_PREFIX + body.encode("ascii"), hashlib.sha256
    ).hexdigest()[:4].upper()


def generate_key(*, tier: str, year: int) -> str:
    """Generate a new license key for the given tier and year."""
    tier_code = "ULT" if tier == "ultimate" else "PRO"
    body = "".join(secrets.choice(_BASE32_ALPHA) for _ in range(6))
    payload = f"{tier_code}-{year}-{body}"
    csum = _checksum(payload)
    return f"FSD-{payload}-{csum}"


def validate_key_format(key: str) -> bool:
    parsed = parse_key(key)
    return parsed is not None


def parse_key(key: str) -> dict | None:
    key = (key or "").strip().upper()
    parts = key.split("-")
    if len(parts) != 5 or parts[0] != "FSD":
        return None
    _, tier, year, body, csum = parts
    if tier not in ("PRO", "ULT"):
        return None
    if not year.isdigit() or len(year) != 4:
        return None
    if len(body) != 6 or len(csum) != 4:
        return None
    expected = _checksum(f"{tier}-{year}-{body}")
    if not hmac.compare_digest(expected, csum):
        return None
    return {
        "tier": "ultimate" if tier == "ULT" else "pro",
        "year": int(year),
        "body": body,
    }
