"""
OS package management with idempotency.
"""
import time
from ..utils.shell import run, is_installed
from ..core.state import InstallState


CRITICAL_PACKAGES = ["nginx", "openssl", "curl", "iptables-persistent"]


def check_os() -> None:
    r = run("which apt-get", check=False, timeout=10)
    if not r.ok:
        print("  ❌ Только Ubuntu/Debian поддерживаются")
        raise RuntimeError("Unsupported OS")


def install(packages: str, state: InstallState, remote_ip: str = None, remote_cred: dict = None, timeout: int = 180) -> None:
    pkg_list = packages.split()

    # Wait for apt locks
    for _ in range(30):
        r = run("fuser /var/lib/dpkg/lock-frontend 2>/dev/null", check=False, timeout=5)
        if not r.ok:
            break
        print("  Ожидание снятия блокировки apt...")
        time.sleep(2)

    run("dpkg --configure -a 2>/dev/null", check=False, timeout=60)
    run("apt-get update -qq", check=False, timeout=120)

    r = run(f"DEBIAN_FRONTEND=noninteractive apt-get install -y {packages}", check=False, timeout=timeout)
    if not r.ok:
        print(f"  apt ошибка, повторная попытка...")
        run("apt-get --fix-broken install -y 2>/dev/null", check=False, timeout=60)
        run("apt-get update --fix-missing", check=False, timeout=120)
        for pkg in pkg_list:
            run(f"DEBIAN_FRONTEND=noninteractive apt-get install -y {pkg}", check=False, timeout=120)

    # Verify critical packages
    missing = []
    for pkg in CRITICAL_PACKAGES:
        if pkg in pkg_list and not is_installed(pkg):
            missing.append(pkg)
    if missing:
        raise RuntimeError(f"Не удалось установить: {', '.join(missing)}")

    state.add_step(f"packages:{packages}")


def install_sshpass() -> None:
    if not is_installed("sshpass"):
        run("apt-get update -qq && apt-get install -y -qq sshpass 2>/dev/null", check=False, timeout=120)
