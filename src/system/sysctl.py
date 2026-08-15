"""
Kernel tuning and system limits.
"""
from ..utils.shell import run, write_file
from ..core.state import InstallState


SYSCTL_CONFIG = """net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_mtu_probing = 1
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.core.netdev_max_backlog = 65536
net.ipv4.ip_local_port_range = 1024 65535
net.core.rmem_max = 67108864
net.core.wmem_max = 67108864
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864
net.ipv4.tcp_max_tw_buckets = 1440000
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_fin_timeout = 15
fs.file-max = 1048576
vm.swappiness = 10
"""

LIMITS_CONFIG = """* soft nofile 1048576
* hard nofile 1048576
root soft nofile 1048576
root hard nofile 1048576
"""


def tune(state: InstallState) -> None:
    write_file("/etc/sysctl.d/99-vpn-tuning.conf", SYSCTL_CONFIG)
    run("sysctl --system > /dev/null 2>&1", check=False)

    write_file("/etc/security/limits.d/99-nofile.conf", LIMITS_CONFIG)
    state.add_step("sysctl:tune")
    state.add_file("/etc/sysctl.d/99-vpn-tuning.conf")
    state.add_file("/etc/security/limits.d/99-nofile.conf")
    print("  ✅ TCP BBR + limits настроены")


def setup_swap(state: InstallState) -> None:
    r = run("swapon --show", check=False)
    if not r.stdout.strip():
        run("fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile", check=False)
        run("grep -q swapfile /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab", check=False)
        state.add_step("swap:created")
        print("  ✅ Swap 2G создан")
    else:
        print("  ℹ️ Swap уже есть")
