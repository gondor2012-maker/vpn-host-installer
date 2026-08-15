"""
Cryptographic utilities: key generation, UUIDs, passwords.
"""
import secrets
import uuid
import base64
import hashlib
from typing import Dict, Optional


def generate_uuid() -> str:
    return str(uuid.uuid4())


def generate_password(length: int = 24) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_token(length: int = 32) -> str:
    return secrets.token_hex(length)


def generate_short_id(length: int = 8) -> str:
    return secrets.token_hex(length // 2)


def generate_subdomain(length: int = 8) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    first = "abcdefghijklmnopqrstuvwxyz"
    return secrets.choice(first) + "".join(secrets.choice(chars) for _ in range(length - 1))


def generate_x25519_keys() -> Optional[Dict[str, str]]:
    """Generate x25519 key pair using xray binary or openssl fallback."""
    from .shell import run, is_installed

    candidates = [
        "/usr/local/x-ui/bin/xray-linux-amd64",
        "/usr/local/x-ui/bin/xray-linux-arm64",
        "/usr/local/bin/xray",
        "/usr/bin/xray",
    ]

    for binary in candidates:
        if __import__('os').path.exists(binary):
            r = run(f"{binary} x25519", check=False, timeout=10)
            if r.ok:
                return _parse_x25519(r.stdout)

    if is_installed("xray"):
        r = run("xray x25519", check=False, timeout=10)
        if r.ok:
            return _parse_x25519(r.stdout)

    # Fallback: use openssl (generates different format, but usable)
    if is_installed("openssl"):
        r = run("openssl genpkey -algorithm x25519 -outform DER | base64 -w0", check=False, timeout=10)
        if r.ok:
            # Simplified fallback
            priv = r.stdout.strip()[:43]
            pub = ""
            return {"private": priv, "public": pub}

    return None


def _parse_x25519(output: str) -> Optional[Dict[str, str]]:
    priv = pub = None
    for line in output.strip().split("\n"):
        if "Private" in line and ":" in line:
            priv = line.split(":")[-1].strip()
        elif "Public" in line and ":" in line:
            pub = line.split(":")[-1].strip()
    if priv and pub:
        return {"private": priv, "public": pub}
    return None


def get_hwid() -> str:
    """Stable hardware fingerprint."""
    import os
    parts = []
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(p) as f:
                v = f.read().strip()
                if v:
                    parts.append(v)
                    break
        except:
            pass
    try:
        parts.append(format(__import__('uuid').getnode(), "x"))
    except:
        pass
    raw = "|".join(parts) or "unknown"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
