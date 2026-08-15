"""
Rollback system - undo all changes tracked by InstallState.
"""
import os
import shutil
from typing import Optional
from .state import InstallState
from ..utils.shell import run


class RollbackManager:
    def __init__(self, state: Optional[InstallState] = None):
        self.state = state or InstallState.load()

    def rollback(self, force: bool = False) -> None:
        print("\n  [ROLLBACK] Откат установки...")

        # 1. Docker compose down
        for project in reversed(self.state.docker_projects):
            print(f"    docker compose down: {project}")
            run(f"cd {project} && docker compose down -v 2>/dev/null", check=False, timeout=60)

        # 2. Stop systemd services
        for svc in reversed(self.state.systemd_services):
            print(f"    stopping systemd: {svc}")
            run(f"systemctl stop {svc} 2>/dev/null; systemctl disable {svc} 2>/dev/null", check=False, timeout=30)

        # 3. Remove nginx sites
        for site in reversed(self.state.nginx_sites):
            print(f"    removing nginx site: {site}")
            for p in [f"/etc/nginx/sites-enabled/{site}", f"/etc/nginx/sites-available/{site}"]:
                if os.path.exists(p):
                    os.remove(p)

        # 4. Remove iptables rules
        for rule in reversed(self.state.iptables_rules):
            spec = rule.strip()
            if spec.startswith("-"):
                spec = spec[1:].strip()
            print(f"    iptables -D {spec}")
            run(f"iptables -D {spec} 2>/dev/null", check=False, timeout=10)

        # 5. Remove files
        for path in reversed(self.state.created_files):
            if os.path.exists(path):
                print(f"    removing file: {path}")
                os.remove(path)

        # 6. Remove directories (only if empty or explicitly tracked)
        for path in reversed(self.state.created_dirs):
            if os.path.exists(path) and not os.listdir(path):
                print(f"    removing dir: {path}")
                os.rmdir(path)

        # Reload nginx
        run("nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null", check=False, timeout=15)
        run("netfilter-persistent save 2>/dev/null || iptables-save > /etc/iptables/rules.v4 2>/dev/null", check=False, timeout=15)

        # Reset state
        InstallState.reset()
        print("  [ROLLBACK] Завершён. Система очищена.")
