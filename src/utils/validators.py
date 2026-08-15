"""
Input validation utilities.
"""
import re
import ipaddress
from typing import Optional


def validate_domain(domain: str) -> bool:
    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$"
    return bool(re.match(pattern, domain)) and len(domain) <= 253


def validate_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def validate_port(port: int) -> bool:
    return 1 <= port <= 65535


def sanitize_domain(domain: str) -> str:
    return domain.replace("https://", "").replace("http://", "").strip("/").strip()
