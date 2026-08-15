"""
Installation state management for idempotency.
Tracks what was done so we can skip on re-run or rollback.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


STATE_FILE = "/opt/vpn-host-installer/state.json"


@dataclass
class InstallState:
    version: str = "2.0.0"
    started_at: str = ""
    completed_steps: List[str] = None
    created_files: List[str] = None
    created_dirs: List[str] = None
    systemd_services: List[str] = None
    docker_projects: List[str] = None
    nginx_sites: List[str] = None
    iptables_rules: List[str] = None
    firewall_ports: List[int] = None
    db_records: List[Dict[str, Any]] = None
    env_vars: Dict[str, str] = None
    config: Dict[str, Any] = None

    def __post_init__(self):
        if self.completed_steps is None:
            self.completed_steps = []
        if self.created_files is None:
            self.created_files = []
        if self.created_dirs is None:
            self.created_dirs = []
        if self.systemd_services is None:
            self.systemd_services = []
        if self.docker_projects is None:
            self.docker_projects = []
        if self.nginx_sites is None:
            self.nginx_sites = []
        if self.iptables_rules is None:
            self.iptables_rules = []
        if self.firewall_ports is None:
            self.firewall_ports = []
        if self.db_records is None:
            self.db_records = []
        if self.env_vars is None:
            self.env_vars = {}
        if self.config is None:
            self.config = {}
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat()

    def add_step(self, step: str) -> None:
        if step not in self.completed_steps:
            self.completed_steps.append(step)
            self.save()

    def has_step(self, step: str) -> bool:
        return step in self.completed_steps

    def add_file(self, path: str) -> None:
        if path not in self.created_files:
            self.created_files.append(path)
            self.save()

    def add_dir(self, path: str) -> None:
        if path not in self.created_dirs:
            self.created_dirs.append(path)
            self.save()

    def add_systemd(self, service: str) -> None:
        if service not in self.systemd_services:
            self.systemd_services.append(service)
            self.save()

    def add_docker(self, project_dir: str) -> None:
        if project_dir not in self.docker_projects:
            self.docker_projects.append(project_dir)
            self.save()

    def add_nginx(self, site: str) -> None:
        if site not in self.nginx_sites:
            self.nginx_sites.append(site)
            self.save()

    def add_iptables(self, rule: str) -> None:
        if rule not in self.iptables_rules:
            self.iptables_rules.append(rule)
            self.save()

    def add_port(self, port: int) -> None:
        if port not in self.firewall_ports:
            self.firewall_ports.append(port)
            self.save()

    def set_config(self, key: str, value: Any) -> None:
        self.config[key] = value
        self.save()

    def save(self) -> None:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls) -> "InstallState":
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE) as f:
                    data = json.load(f)
                return cls(**data)
            except:
                pass
        return cls()

    @classmethod
    def reset(cls) -> None:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
