"""Tests for license key generation and validation."""

import os
os.environ["LICENSE_HMAC_SECRET"] = "test_secret_for_unit_tests"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.keys import generate_key, parse_key, validate_key_format


def test_generates_valid_pro_key():
    key = generate_key(tier="pro", year=2026)
    assert key.startswith("FSD-PRO-2026-")
    assert validate_key_format(key)
    parsed = parse_key(key)
    assert parsed["tier"] == "pro"
    assert parsed["year"] == 2026


def test_generates_valid_ultimate_key():
    key = generate_key(tier="ultimate", year=2026)
    assert key.startswith("FSD-ULT-2026-")
    assert validate_key_format(key)
    assert parse_key(key)["tier"] == "ultimate"


def test_rejects_tampered_checksum():
    key = generate_key(tier="pro", year=2026)
    # Flip the last char of checksum
    tampered = key[:-1] + ("A" if key[-1] != "A" else "B")
    assert not validate_key_format(tampered)


def test_rejects_invalid_tier():
    assert not validate_key_format("FSD-LOL-2026-AB12CD-7E3F")


def test_rejects_invalid_year():
    assert not validate_key_format("FSD-PRO-XYZW-AB12CD-7E3F")


def test_rejects_garbage():
    assert not validate_key_format("garbage")
    assert not validate_key_format("")
    assert not validate_key_format("FSD")


def test_keys_are_unique():
    keys = {generate_key(tier="pro", year=2026) for _ in range(100)}
    assert len(keys) == 100  # all unique


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
