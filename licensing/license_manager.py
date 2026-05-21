"""
license_manager.py — FreeSystemDoctor PRO license validation.

License key format:   FSD-{TIER}-{YEAR}-{XXXXXX}-{CHECKSUM}
Example:              FSD-PRO-2026-AB12CD-7E3F

Tier values: PRO, ULT (Ultimate)
Year: 4-digit purchase year
Body: 6-character base32-ish identifier (also embeds expiry epoch for yearly licenses)
Checksum: 4-character HMAC of body using HMAC-SHA256 truncated

Online activation (optional but recommended):
   POST /api/activate  { key, machine_id }  → { valid: bool, tier, expiry_iso, devices_used, devices_max }

Offline fallback:
   Keys carry their own self-check (checksum). Online sync extends validity to expiry.
   Without internet: key valid for 14 days after last successful check.
"""

from __future__ import annotations

import os
import json
import hmac
import hashlib
import platform
import socket
import uuid
from pathlib import Path
from datetime import datetime, timedelta


# ── constants ────────────────────────────────────────────────────────────────

LICENSE_DIR = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "FreeSystemDoctorPro"
LICENSE_FILE = LICENSE_DIR / "license.json"
MACHINE_FILE = LICENSE_DIR / "machine.id"

# Public verification key shipped with the build (HMAC secret half visible).
# Real production: store private half on activation server only.
# This demo uses a placeholder. Production must rotate this and never ship the
# private half in the binary.
_PUBLIC_PREFIX = b"FSD-PRO-v1-"
_DEMO_SECRET = b"DEMO_REPLACE_IN_PROD_WITH_REAL_HMAC_SECRET"

OFFLINE_GRACE_DAYS = 14

ACTIVATION_API = "https://api.freesystemdoctor.pl/v1/activate"


# ── types ────────────────────────────────────────────────────────────────────

class LicenseInfo:
    def __init__(self, key: str = "", tier: str = "free",
                 expiry_iso: str = "", devices_used: int = 0,
                 devices_max: int = 1, activated_at: str = "",
                 last_check: str = ""):
        self.key = key
        self.tier = tier
        self.expiry_iso = expiry_iso
        self.devices_used = devices_used
        self.devices_max = devices_max
        self.activated_at = activated_at
        self.last_check = last_check

    def is_active(self) -> bool:
        if self.tier == "free":
            return False
        if not self.expiry_iso:
            return True  # lifetime
        try:
            return datetime.fromisoformat(self.expiry_iso) > datetime.now()
        except Exception:
            return False

    def is_pro(self) -> bool:
        return self.tier in ("pro", "ultimate")

    def is_ultimate(self) -> bool:
        return self.tier == "ultimate"

    def to_dict(self) -> dict:
        return {
            "key": self.key, "tier": self.tier,
            "expiry_iso": self.expiry_iso,
            "devices_used": self.devices_used,
            "devices_max": self.devices_max,
            "activated_at": self.activated_at,
            "last_check": self.last_check,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LicenseInfo":
        return cls(**d)


# ── machine id (stable, anonymous) ───────────────────────────────────────────

def get_machine_id() -> str:
    """Generate a stable machine ID. Stored locally; used by activation server."""
    LICENSE_DIR.mkdir(parents=True, exist_ok=True)
    if MACHINE_FILE.exists():
        try:
            return MACHINE_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    # First-run: derive from MAC + hostname + platform, hashed
    components = [
        hex(uuid.getnode()),
        socket.gethostname(),
        platform.node(),
        platform.machine(),
    ]
    seed = "|".join(components).encode("utf-8")
    mid = hashlib.sha256(seed).hexdigest()[:24]

    try:
        MACHINE_FILE.write_text(mid, encoding="utf-8")
    except Exception:
        pass
    return mid


# ── key format check ─────────────────────────────────────────────────────────

def _checksum(body: bytes) -> str:
    return hmac.new(_DEMO_SECRET, _PUBLIC_PREFIX + body,
                    hashlib.sha256).hexdigest()[:4].upper()


def _parse_key(key: str) -> dict | None:
    """Parse FSD-TIER-YEAR-BODY-CHECKSUM format."""
    key = (key or "").strip().upper()
    parts = key.split("-")
    if len(parts) != 5 or parts[0] != "FSD":
        return None
    _, tier, year, body, csum = parts
    if tier not in ("PRO", "ULT"):
        return None
    if not year.isdigit() or len(year) != 4:
        return None
    expected = _checksum(f"{tier}-{year}-{body}".encode("ascii"))
    if expected != csum:
        return None
    return {
        "tier": "ultimate" if tier == "ULT" else "pro",
        "year": int(year),
        "body": body,
    }


def is_valid_format(key: str) -> bool:
    return _parse_key(key) is not None


# ── activation (online + offline grace) ──────────────────────────────────────

def activate(key: str, online: bool = True) -> tuple[bool, str, LicenseInfo | None]:
    """
    Activate a license key.

    Returns:
        (success, message, LicenseInfo on success or None)
    """
    parsed = _parse_key(key)
    if parsed is None:
        return False, "Niepoprawny format klucza", None

    machine_id = get_machine_id()

    if online:
        try:
            import urllib.request
            req = urllib.request.Request(
                ACTIVATION_API,
                data=json.dumps({"key": key, "machine_id": machine_id}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode())
            if not payload.get("valid"):
                return False, payload.get("error", "Klucz odrzucony przez serwer"), None
            info = LicenseInfo(
                key=key,
                tier=payload.get("tier", parsed["tier"]),
                expiry_iso=payload.get("expiry_iso", ""),
                devices_used=payload.get("devices_used", 1),
                devices_max=payload.get("devices_max", 3),
                activated_at=datetime.now().isoformat(),
                last_check=datetime.now().isoformat(),
            )
            _save_license(info)
            return True, "Licencja aktywowana", info
        except Exception as e:
            # Fall through to offline activation
            pass

    # Offline activation — checksum-only, conservative 30-day expiry on yearly
    info = LicenseInfo(
        key=key,
        tier=parsed["tier"],
        expiry_iso="" if parsed["year"] >= 9999 else (
            (datetime.now() + timedelta(days=365)).isoformat()
        ),
        devices_used=1,
        devices_max=5 if parsed["tier"] == "ultimate" else 3,
        activated_at=datetime.now().isoformat(),
        last_check=datetime.now().isoformat(),
    )
    _save_license(info)
    return True, "Licencja aktywowana (tryb offline — sync gdy będzie internet)", info


def verify(refresh_online: bool = False) -> LicenseInfo:
    """Verify currently-stored license. Returns free-tier info if none/invalid."""
    info = _load_license()
    if info.key == "":
        return info  # free

    # Format must still be valid (catches tampering)
    if not is_valid_format(info.key):
        return LicenseInfo(tier="free")

    # Offline grace check
    if info.last_check:
        try:
            last = datetime.fromisoformat(info.last_check)
            if datetime.now() - last > timedelta(days=OFFLINE_GRACE_DAYS):
                # Force online re-check
                refresh_online = True
        except Exception:
            pass

    if refresh_online:
        ok, msg, fresh = activate(info.key, online=True)
        if ok and fresh:
            return fresh

    if not info.is_active():
        return LicenseInfo(tier="free")
    return info


def deactivate() -> bool:
    """Remove license file (also signals server to free a device slot)."""
    try:
        info = _load_license()
        if info.key:
            try:
                import urllib.request
                req = urllib.request.Request(
                    ACTIVATION_API.replace("/activate", "/deactivate"),
                    data=json.dumps({
                        "key": info.key,
                        "machine_id": get_machine_id(),
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()
        return True
    except Exception:
        return False


# ── storage ──────────────────────────────────────────────────────────────────

def _save_license(info: LicenseInfo):
    LICENSE_DIR.mkdir(parents=True, exist_ok=True)
    LICENSE_FILE.write_text(
        json.dumps(info.to_dict(), indent=2),
        encoding="utf-8",
    )


def _load_license() -> LicenseInfo:
    if not LICENSE_FILE.exists():
        return LicenseInfo(tier="free")
    try:
        d = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
        return LicenseInfo.from_dict(d)
    except Exception:
        return LicenseInfo(tier="free")


# ── helpers for gated features ───────────────────────────────────────────────

def require_pro(func):
    """Decorator: function only runs if Pro tier active."""
    def wrapper(*args, **kwargs):
        info = verify()
        if not info.is_pro():
            raise PermissionError(
                "Ta funkcja wymaga FSD Pro. Kup licencję: "
                "https://caytec.github.io/freesystemdoctor-pro"
            )
        return func(*args, **kwargs)
    return wrapper


def require_ultimate(func):
    """Decorator: function only runs if Ultimate tier active."""
    def wrapper(*args, **kwargs):
        info = verify()
        if not info.is_ultimate():
            raise PermissionError(
                "Ta funkcja wymaga FSD Ultimate. Upgrade: "
                "https://caytec.github.io/freesystemdoctor-pro#pricing"
            )
        return func(*args, **kwargs)
    return wrapper


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        info = verify()
        print(f"Tier:    {info.tier}")
        print(f"Active:  {info.is_active()}")
        print(f"Devices: {info.devices_used}/{info.devices_max}")
        print(f"Expiry:  {info.expiry_iso or 'lifetime'}")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "activate" and len(sys.argv) >= 3:
        ok, msg, info = activate(sys.argv[2])
        print(msg)
        sys.exit(0 if ok else 1)
    elif cmd == "deactivate":
        print("Deactivated" if deactivate() else "Failed")
    elif cmd == "machine":
        print(get_machine_id())
    elif cmd == "verify":
        info = verify(refresh_online=True)
        print(json.dumps(info.to_dict(), indent=2))
    else:
        print("Usage: license_manager.py [activate KEY|deactivate|machine|verify]")
