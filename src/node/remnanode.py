"""
Remnanode Docker management.
"""
import os
from ..utils.shell import run, ensure_dir
from ..core.state import InstallState


COMPOSE_TEMPLATE = """services:
  remnanode:
    container_name: remnanode
    hostname: remnanode
    image: ghcr.io/remnawave/node:latest
    network_mode: host
    restart: always
    cap_add:
      - NET_ADMIN
    ulimits:
      nofile:
        soft: 1048576
        hard: 1048576
    volumes:
      - /etc/nginx/ssl:/etc/nginx/ssl:ro
    env_file:
      - .env
"""


def deploy(secret_key: str, state: InstallState, project_dir: str = "/opt/remnanode") -> None:
    ensure_dir(project_dir)

    compose_path = os.path.join(project_dir, "docker-compose.yml")
    env_path = os.path.join(project_dir, ".env")

    with open(compose_path, "w") as f:
        f.write(COMPOSE_TEMPLATE)

    with open(env_path, "w") as f:
        f.write(f"NODE_PORT=2222\nSECRET_KEY={secret_key}\n")

    run(f"cd {project_dir} && docker compose pull", check=False, timeout=180)
    run(f"cd {project_dir} && docker compose up -d", check=False, timeout=60)

    state.add_dir(project_dir)
    state.add_file(compose_path)
    state.add_file(env_path)
    state.add_docker(project_dir)
    state.add_step("remnanode:deployed")
    print("  ✅ Remnanode запущен")


def restart(project_dir: str = "/opt/remnanode") -> None:
    run(f"cd {project_dir} && docker compose restart", check=False, timeout=30)


def logs(lines: int = 10) -> str:
    r = run(f"docker logs remnanode --tail={lines} 2>&1", check=False)
    return r.stdout
