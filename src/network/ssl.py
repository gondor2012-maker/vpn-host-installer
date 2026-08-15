"""
SSL certificate management.
"""
import os
from ..utils.shell import run, ensure_dir
from ..core.state import InstallState


def ensure_self_signed(domain: str = "cdn-origin", state: InstallState = None) -> tuple:
    cert_dir = "/etc/nginx/ssl"
    cert = f"{cert_dir}/cdn.crt"
    key = f"{cert_dir}/cdn.key"

    if os.path.exists(cert) and os.path.exists(key):
        return cert, key

    ensure_dir(cert_dir)
    run(f"openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -subj '/CN={domain}' -keyout {key} -out {cert} 2>/dev/null", check=False)

    if state:
        state.add_file(cert)
        state.add_file(key)
        state.add_step("ssl:selfsigned")
    print("  ✅ Self-signed SSL создан")
    return cert, key


def get_le_cert(domain: str, state: InstallState = None) -> tuple:
    """Get Let's Encrypt certificate via certbot."""
    cert = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
    key = f"/etc/letsencrypt/live/{domain}/privkey.pem"

    if os.path.exists(cert) and os.path.exists(key):
        return cert, key

    ensure_dir("/var/www/certbot")
    r = run(f"certbot certonly --webroot -w /var/www/certbot -d {domain} --non-interactive --agree-tos --register-unsafely-without-email", check=False, timeout=120)

    if r.ok and os.path.exists(cert):
        if state:
            state.add_step(f"ssl:le:{domain}")
        print(f"  ✅ LE сертификат для {domain} получен")
        return cert, key

    print(f"  ⚠️ LE не сработал для {domain}")
    return None, None


def setup_acme_for_ip(ip: str, state: InstallState = None) -> tuple:
    """Issue LE cert for IP address (short-lived profile)."""
    run("curl -fsSL https://get.acme.sh | sh 2>/dev/null", check=False, timeout=120)
    run("systemctl stop nginx", check=False)

    r = run(f"~/.acme.sh/acme.sh --issue --server letsencrypt -d {ip} --standalone --httpport 80 --cert-profile shortlived --keylength ec-256 --days 3 --force", check=False, timeout=120)

    if r.ok:
        ensure_dir("/root/cert/ip")
        run(f"~/.acme.sh/acme.sh --install-cert -d {ip} --fullchain-file /root/cert/ip/fullchain.pem --key-file /root/cert/ip/privkey.pem", check=False)
        run("systemctl start nginx", check=False)
        if state:
            state.add_step(f"ssl:acme:{ip}")
        return "/root/cert/ip/fullchain.pem", "/root/cert/ip/privkey.pem"

    run("systemctl start nginx", check=False)
    return None, None
