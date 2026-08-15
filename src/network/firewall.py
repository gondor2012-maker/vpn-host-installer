"""
Firewall management (iptables + ufw).
"""
from ..utils.shell import run
from ..core.state import InstallState


def open_port(port: int, proto: str = "tcp", state: InstallState = None) -> None:
    run(f"ufw allow {port}/{proto} >/dev/null 2>&1", check=False)
    run(f"iptables -C INPUT -p {proto} --dport {port} -j ACCEPT 2>/dev/null || iptables -I INPUT -p {proto} --dport {port} -j ACCEPT", check=False)
    if state:
        state.add_port(port)
        state.add_iptables(f"INPUT -p {proto} --dport {port} -j ACCEPT")


def restrict_port(port: int, allowed_ip: str, proto: str = "tcp", state: InstallState = None) -> None:
    run(f"iptables -I INPUT -p {proto} --dport {port} -s {allowed_ip} -j ACCEPT", check=False)
    run(f"iptables -A INPUT -p {proto} --dport {port} -j DROP", check=False)
    if state:
        state.add_iptables(f"INPUT -p {proto} --dport {port} -s {allowed_ip} -j ACCEPT")
        state.add_iptables(f"INPUT -p {proto} --dport {port} -j DROP")


def save(state: InstallState = None) -> None:
    run("netfilter-persistent save 2>/dev/null || iptables-save > /etc/iptables/rules.v4 2>/dev/null || true", check=False)
    if state:
        state.add_step("firewall:saved")
