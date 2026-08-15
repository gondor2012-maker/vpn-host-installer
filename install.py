#!/usr/bin/env python3
"""
VPN Host Installer v2.0
Улучшенный установщик VPN-инфраструктуры с XHTTP packet-up.

Улучшения по сравнению с v1.1:
- Модульная архитектура (легко расширять)
- Idempotency (можно перезапускать без дублей)
- Состояние установки в /opt/vpn-host-installer/state.json
- Чистый rollback
- Нет vendor lock-in (нет внешнего сервера лицензий)
- Конфигурация через YAML
- Улучшенная обработка ошибок
- Поддержка каскада из коробки
"""
import os
import sys
import yaml
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utils.shell import run, get_public_ip, is_installed
from utils.crypto import generate_uuid, generate_subdomain, generate_password
from utils.validators import validate_domain, sanitize_domain
from core.state import InstallState
from core.rollback import RollbackManager
from system import packages, sysctl, docker
from network import nginx as ngx, ssl as ssl_mgr, firewall
from node import xray, remnanode
from panels.xui import XUIPanel
from panels.remnawave import RemnawavePanel
from front.regru import RegruFront


def load_config(path: str = "config.yaml") -> dict:
    if not os.path.exists(path):
        print(f"  Файл {path} не найден, использую defaults")
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def step(n: int, text: str) -> None:
    print(f"\n{'='*50}")
    print(f"  [{n}] {text}")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="VPN Host Installer v2.0")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--mode", choices=["1", "2", "3"], help="1=panel+node, 2=panel+remote-node, 3=node-only")
    parser.add_argument("--panel", choices=["remnawave", "xui"], help="Panel type")
    parser.add_argument("--domain", help="Base domain")
    parser.add_argument("--front-domain", help="Front domain (for REG.RU)")
    parser.add_argument("--rollback", action="store_true", help="Rollback installation")
    args = parser.parse_args()

    # Rollback mode
    if args.rollback:
        RollbackManager().rollback()
        return

    # Check root
    if os.geteuid() != 0:
        print("ОШИБКА: Запусти от root!")
        sys.exit(1)

    # Load config
    cfg = load_config(args.config)
    cfg["mode"] = args.mode or cfg.get("mode", "1")
    cfg["panel_type"] = args.panel or cfg.get("panel_type", "xui")
    cfg["domain"] = args.domain or cfg.get("domain")
    cfg["front_domain"] = args.front_domain or cfg.get("front_domain")

    if not cfg["domain"]:
        cfg["domain"] = input("  Домен (без http://): ").strip()
    cfg["domain"] = sanitize_domain(cfg["domain"])

    if not validate_domain(cfg["domain"]):
        print("  ❌ Невалидный домен")
        sys.exit(1)

    server_ip = get_public_ip()
    print(f"\n{'='*50}")
    print(f"   VPN Host Installer v2.0")
    print(f"   Server IP: {server_ip}")
    print(f"{'='*50}")

    state = InstallState.load()
    state.set_config("domain", cfg["domain"])
    state.set_config("server_ip", server_ip)

    # Generate subdomains if not set
    if not cfg.get("origin_sub"):
        cfg["origin_sub"] = generate_subdomain()
    if not cfg.get("front_domain"):
        cfg["front_sub"] = cfg.get("front_sub") or generate_subdomain()
        cfg["front_domain"] = f"{cfg['front_sub']}.{cfg['domain']}"
    if not cfg.get("panel_sub"):
        cfg["panel_sub"] = generate_subdomain()

    cfg["origin_domain"] = f"{cfg['origin_sub']}.{cfg['domain']}"
    cfg["panel_domain"] = f"{cfg['panel_sub']}.{cfg['domain']}"
    cfg["client_uuid"] = cfg.get("client_uuid") or generate_uuid()
    cfg["sub_id"] = cfg.get("sub_id") or generate_password(16)

    print(f"  Origin: {cfg['origin_domain']}")
    print(f"  Front:  {cfg['front_domain']}")
    print(f"  Panel:  {cfg['panel_domain']}")

    # === STEP 1: System preparation ===
    step(1, "Подготовка системы")
    if not state.has_step("system:prepared"):
        packages.check_os()
        packages.install("nginx openssl curl sqlite3 ca-certificates gnupg sshpass certbot iptables-persistent", state)
        sysctl.tune(state)
        sysctl.setup_swap(state)
        docker.install(state)
        docker.setup_mirror(state)
        docker.ensure_compose(state)
        state.add_step("system:prepared")
    else:
        print("  ℹ️ Система уже подготовлена")

    # === STEP 2: SSL & Nginx base ===
    step(2, "SSL и Nginx")
    if not state.has_step("nginx:base"):
        cert, key = ssl_mgr.ensure_self_signed(cfg["origin_domain"], state)
        ngx.setup(state)
        state.add_step("nginx:base")
    else:
        cert, key = ssl_mgr.ensure_self_signed(cfg["origin_domain"])

    # === STEP 3: Panel installation (modes 1 & 2) ===
    panel = None
    if cfg["mode"] in ("1", "2"):
        step(3, f"Установка панели {cfg['panel_type']}")

        if cfg["panel_type"] == "xui":
            panel = XUIPanel(cfg, state)
        else:
            panel = RemnawavePanel(cfg, state)

        if not state.has_step(f"panel:{cfg['panel_type']}:installed"):
            panel.install()
            panel.setup_ssl(cfg["panel_domain"])
            state.add_step(f"panel:{cfg['panel_type']}:installed")

        # Panel nginx
        if not state.has_step("nginx:panel"):
            ngx.reload(state)
            state.add_step("nginx:panel")

    # === STEP 4: Node setup ===
    step(4, "Установка ноды")
    node_ip = server_ip if cfg["mode"] in ("1", "3") else cfg.get("node_ip", server_ip)
    xray_port = cfg.get("xray_port", 2053)
    xhttp_path = cfg.get("xhttp_path", "/p")

    if not state.has_step("xray:installed"):
        xray.install(state)

    inbound = xray.build_xhttp_inbound(
        port=xray_port, path=xhttp_path,
        client_uuid=cfg["client_uuid"],
        mode=cfg.get("xhttp_mode", "packet-up"),
        method=cfg.get("xhttp_method", "DELETE"),
        padding_key=cfg.get("padding_key", "q")
    )

    outbounds, rules = xray.build_outbound(cfg.get("cascade"))
    config = xray.build_config(inbound, outbounds, rules)
    xray.write_config(config, state)
    xray.ensure_service(state)

    # Nginx CDN origin
    if not state.has_step("nginx:cdn"):
        ipv6 = os.path.exists("/proc/sys/net/ipv6")
        nginx_conf = ngx.render_cdn_origin(
            xray_port=xray_port, xhttp_path=xhttp_path,
            ssl_cert=cert, ssl_key=key, ipv6=ipv6,
            panel_path=getattr(panel, "panel_path", None) if panel else None,
            panel_port=getattr(panel, "panel_port", None) if panel else None
        )
        ngx.write_site("cdn-origin.conf", nginx_conf, state)
        ngx.reload(state)
        state.add_step("nginx:cdn")

    # Firewall
    firewall.open_port(80, "tcp", state)
    firewall.open_port(443, "tcp", state)
    if panel:
        pport = getattr(panel, "panel_port", 2222)
        firewall.restrict_port(pport, server_ip, "tcp", state)
    firewall.save(state)

    # === STEP 5: Panel inbound creation ===
    sub_url = None
    if panel and not state.has_step("panel:inbound"):
        step(5, "Создание inbound в панели")
        sub_url = panel.create_inbound(node_ip, xray_port, xhttp_path, cfg["client_uuid"])
        state.add_step("panel:inbound")

    # === STEP 6: Front setup ===
    step(6, "Настройка фронта")
    front_cfg = {
        "front_domain": cfg["front_domain"],
        "node_ip": node_ip,
        "path": xhttp_path
    }
    front = RegruFront(front_cfg)

    if not front.setup():
        print(front.instructions())
        input("  Нажми ENTER когда фронт настроен...")

    front.verify()

    # === STEP 7: Final ===
    step(7, "Установка завершена")

    vless_link = (
        f"vless://{cfg['client_uuid']}@{cfg['front_domain']}:443"
        f"?type=xhttp&security=tls&sni={cfg['front_domain']}"
        f"&fp=firefox&alpn=h2&path={xhttp_path}"
        f"&host={cfg['front_domain']}&mode=packet-up&encryption=none"
        f"#user1-host"
    )

    print(f"""
  ============================================
  УСТАНОВКА ЗАВЕРШЕНА
  ============================================

  Origin: {cfg['origin_domain']} -> {node_ip}
  Front:  {cfg['front_domain']} (REG.RU shared hosting)

  Xray port: {xray_port}
  Path: {xhttp_path}
  UUID: {cfg['client_uuid']}

  VLESS Link:
  {vless_link}
  """)

    if sub_url:
        print(f"  Подписка: {sub_url}")

    if panel:
        creds = panel.get_credentials()
        print(f"""
  Панель: {creds['url']}
  Логин:  {creds['username']}
  Пароль: {creds['password']}
        """)

    print(f"""
  Rollback: python3 install.py --rollback
  ============================================
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Установка прервана.")
        sys.exit(1)
    except Exception as e:
        print(f"\n  ❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
