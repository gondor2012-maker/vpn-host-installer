#!/usr/bin/env python3
"""
VPN Host Installer v2.1 — CDN Edition
Убран REG.RU shared hosting (отключили mod_proxy).
Теперь только CDN: Cloudflare, VK Cloud, Yandex Cloud, Timeweb, CDNvideo.
"""
import os
import sys
import yaml
import argparse
from pathlib import Path

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
from front.cloudflare import CloudflareFront
from front.vkcdn import VKCDNFront
from front.yandexcdn import YandexCDNFront
from front.timeweb import TimewebCDNFront
from front.cdnvideo import CDNvideoFront


def load_config(path: str = "config.yaml") -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def step(n: int, text: str) -> None:
    print(f"\n{'='*50}")
    print(f"  [{n}] {text}")
    print(f"{'='*50}")


def choose_cdn(cfg: dict) -> str:
    if cfg.get("cdn"):
        return cfg["cdn"]

    print("""
  Выбери CDN-провайдер для фронта:

  [1] Cloudflare (рекомендуется — бесплатно, надёжно)
  [2] VK Cloud CDN
  [3] Yandex Cloud CDN
  [4] Timeweb CDN
  [5] CDNvideo (Beeline)
  [6] REG.RU shared hosting [DEPRECATED — скорее всего не работает]
""")
    choice = input("  > ").strip()
    cdn_map = {"1": "cloudflare", "2": "vk", "3": "yandex", "4": "timeweb", "5": "cdnvideo", "6": "regru"}
    return cdn_map.get(choice, "cloudflare")


def get_front_class(cdn: str):
    mapping = {
        "cloudflare": CloudflareFront,
        "vk": VKCDNFront,
        "yandex": YandexCDNFront,
        "timeweb": TimewebCDNFront,
        "cdnvideo": CDNvideoFront,
        "regru": None,  # imported dynamically if needed
    }
    return mapping.get(cdn, CloudflareFront)


def main():
    parser = argparse.ArgumentParser(description="VPN Host Installer v2.1 CDN")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--mode", choices=["1", "2", "3"])
    parser.add_argument("--panel", choices=["remnawave", "xui"])
    parser.add_argument("--domain")
    parser.add_argument("--front-domain")
    parser.add_argument("--cdn", choices=["cloudflare", "vk", "yandex", "timeweb", "cdnvideo", "regru"])
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()

    if args.rollback:
        RollbackManager().rollback()
        return

    if os.geteuid() != 0:
        print("ОШИБКА: Запусти от root!")
        sys.exit(1)

    cfg = load_config(args.config)
    cfg["mode"] = args.mode or cfg.get("mode", "1")
    cfg["panel_type"] = args.panel or cfg.get("panel_type", "xui")
    cfg["domain"] = args.domain or cfg.get("domain")
    cfg["front_domain"] = args.front_domain or cfg.get("front_domain")
    cfg["cdn"] = args.cdn or cfg.get("cdn")

    if not cfg["domain"]:
        cfg["domain"] = input("  Домен (без http://): ").strip()
    cfg["domain"] = sanitize_domain(cfg["domain"])

    if not validate_domain(cfg["domain"]):
        print("  ❌ Невалидный домен")
        sys.exit(1)

    server_ip = get_public_ip()
    print(f"\n{'='*50}")
    print(f"   VPN Host Installer v2.1 — CDN Edition")
    print(f"   Server IP: {server_ip}")
    print(f"{'='*50}")

    state = InstallState.load()
    state.set_config("domain", cfg["domain"])
    state.set_config("server_ip", server_ip)

    # CDN selection
    cfg["cdn"] = choose_cdn(cfg)
    print(f"  CDN: {cfg['cdn']}")

    # Generate subdomains
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

    # === STEP 1: System ===
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

    # === STEP 2: SSL & Nginx ===
    step(2, "SSL и Nginx")
    if not state.has_step("nginx:base"):
        cert, key = ssl_mgr.ensure_self_signed(cfg["origin_domain"], state)
        ngx.setup(state)
        state.add_step("nginx:base")
    else:
        cert, key = ssl_mgr.ensure_self_signed(cfg["origin_domain"])

    # Try Let's Encrypt for origin domain (needed for CDN with strict SSL)
    if not state.has_step("ssl:le:origin"):
        le_cert, le_key = ssl_mgr.get_le_cert(cfg["origin_domain"], state)
        if le_cert:
            cert, key = le_cert, le_key
            state.add_step("ssl:le:origin")

    # === STEP 3: Panel ===
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

        if not state.has_step("nginx:panel"):
            ngx.reload(state)
            state.add_step("nginx:panel")

    # === STEP 4: Node ===
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

    # === STEP 5: Panel inbound ===
    sub_url = None
    if panel and not state.has_step("panel:inbound"):
        step(5, "Создание inbound в панели")
        sub_url = panel.create_inbound(node_ip, xray_port, xhttp_path, cfg["client_uuid"])
        state.add_step("panel:inbound")

    # === STEP 6: CDN Front ===
    step(6, f"Настройка CDN фронта ({cfg['cdn']})")
    front_cfg = {
        "front_domain": cfg["front_domain"],
        "node_ip": node_ip,
        "path": xhttp_path
    }

    FrontClass = get_front_class(cfg["cdn"])
    if cfg["cdn"] == "regru":
        from front.regru import RegruFront
        FrontClass = RegruFront

    front = FrontClass(front_cfg)

    if not front.setup():
        print(front.instructions())
        input("  Нажми ENTER когда CDN настроен...")

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

  CDN:    {cfg['cdn']}
  Origin: {cfg['origin_domain']} -> {node_ip}
  Front:  {cfg['front_domain']} (CDN)

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
