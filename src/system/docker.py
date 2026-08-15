"""
Docker installation and configuration.
"""
from ..utils.shell import run, is_installed
from ..core.state import InstallState


def install(state: InstallState) -> None:
    if is_installed("docker"):
        r = run("docker --version", check=False)
        print(f"  ℹ️ Docker уже установлен: {r.stdout.strip()}")
        return

    print("  Установка Docker...")
    r = run("curl -fsSL https://get.docker.com | sh 2>&1 | tail -5", check=False, timeout=600)
    if not r.ok or not is_installed("docker"):
        print("  get.docker.com не сработал, пробую apt...")
        run("apt-get update -qq && apt-get install -y -qq docker.io docker-compose-plugin 2>&1 | tail -3", check=False, timeout=300)

    if not is_installed("docker"):
        raise RuntimeError("Docker не установился")

    r = run("docker --version", check=False)
    print(f"  ✅ Docker установлен: {r.stdout.strip()}")
    state.add_step("docker:installed")


def setup_mirror(state: InstallState) -> None:
    r = run("curl -s -m 5 -o /dev/null -w '%{http_code}' https://registry-1.docker.io/v2/", check=False, timeout=10)
    if r.stdout.strip() in ("200", "401"):
        return

    mirrors = '{"registry-mirrors":["https://huecker.io","https://dockerhub.timeweb.cloud","https://mirror.gcr.io"]}'
    run(f"mkdir -p /etc/docker && echo '{mirrors}' > /etc/docker/daemon.json && systemctl restart docker", check=False, timeout=30)
    state.add_step("docker:mirror")
    print("  ✅ Зеркало Docker Hub настроено")


def ensure_compose(state: InstallState) -> None:
    r = run("docker compose version 2>/dev/null", check=False)
    if r.ok:
        return

    run("apt-get install -y -qq docker-compose-plugin 2>/dev/null", check=False, timeout=120)
    state.add_step("docker:compose")
