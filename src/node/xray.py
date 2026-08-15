"""
Xray standalone node management.
"""
import json
import os
from ..utils.shell import run, is_installed
from ..utils.crypto import generate_x25519_keys
from ..core.state import InstallState


def install(state: InstallState) -> None:
    if is_installed("xray"):
        r = run("xray version", check=False)
        print(f"  ℹ️ Xray уже установлен: {r.stdout.strip()[:50]}")
        return

    print("  Установка Xray...")
    r = run('bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install', check=False, timeout=120)
    if not r.ok:
        raise RuntimeError("Xray не установился")
    state.add_step("xray:installed")
    print("  ✅ Xray установлен")


def write_config(config: dict, state: InstallState) -> None:
    ensure_dir = lambda p: os.makedirs(p, exist_ok=True)
    ensure_dir("/usr/local/etc/xray")
    with open("/usr/local/etc/xray/config.json", "w") as f:
        json.dump(config, f, indent=2)
    state.add_file("/usr/local/etc/xray/config.json")


def ensure_service(state: InstallState) -> None:
    service = """[Unit]
Description=Xray Service
After=network.target nss-lookup.target

[Service]
User=nobody
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
Restart=on-failure
RestartPreventExitStatus=23
LimitNPROC=10000
LimitNOFILE=1000000

[Install]
WantedBy=multi-user.target
"""
    run("systemctl unmask xray 2>/dev/null", check=False)

    r = run("systemctl cat xray >/dev/null 2>&1 && echo yes", check=False)
    if "yes" not in r.stdout:
        with open("/etc/systemd/system/xray.service", "w") as f:
            f.write(service)
        run("systemctl daemon-reload", check=False)
        state.add_file("/etc/systemd/system/xray.service")
        state.add_systemd("xray")

    run("systemctl enable xray 2>/dev/null", check=False)
    run("systemctl restart xray", check=False)
    state.add_step("xray:service")
    print("  ✅ Xray service запущен")


def build_xhttp_inbound(port: int, path: str, client_uuid: str, mode: str = "packet-up",
                        method: str = "DELETE", padding_key: str = "q") -> dict:
    return {
        "tag": "xhttp-in",
        "port": port,
        "listen": "127.0.0.1",
        "protocol": "vless",
        "settings": {
            "clients": [{"id": client_uuid, "email": "user1"}],
            "decryption": "none"
        },
        "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
        "streamSettings": {
            "network": "xhttp",
            "security": "none",
            "xhttpSettings": {
                "mode": mode,
                "path": path,
                "uplinkHTTPMethod": method,
                "xPaddingKey": padding_key,
                "xPaddingMethod": "tokenish",
                "xPaddingPlacement": "query",
                "xPaddingBytes": "48-256",
                "xPaddingObfsMode": True,
                "sessionIDKey": "sid",
                "sessionIDPlacement": "query",
                "seqKey": "offset",
                "seqPlacement": "query",
                "scMaxEachPostBytes": "262144-786432",
                "scMinPostsIntervalMs": "0"
            }
        }
    }


def build_outbound(cascade: dict = None) -> list:
    outbounds = [
        {"protocol": "freedom", "tag": "direct", "settings": {"domainStrategy": "UseIPv4"}},
        {"protocol": "blackhole", "tag": "block"}
    ]
    rules = [
        {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
        {"type": "field", "protocol": ["bittorrent"], "outboundTag": "block"}
    ]

    if cascade:
        outbounds.append({
            "tag": "CASCADE",
            "protocol": "vless",
            "settings": {"vnext": [{"address": cascade["ip"], "port": 9999,
                "users": [{"id": cascade["uuid"], "encryption": "none"}]}]},
            "streamSettings": {"network": "tcp", "security": "none"}
        })
        rules.insert(0, {"type": "field", "inboundTag": ["xhttp-in"], "outboundTag": "CASCADE"})

    return outbounds, rules


def build_config(inbound: dict, outbounds: list, rules: list) -> dict:
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [inbound],
        "outbounds": outbounds,
        "routing": {"rules": rules}
    }
