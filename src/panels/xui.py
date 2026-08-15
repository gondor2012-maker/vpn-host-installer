"""
3x-ui panel installer and manager.
Uses direct SQLite manipulation (robust for v3.6.0).
"""
import json
import time
import os
from ..utils.shell import run, wait_for_port
from ..utils.crypto import generate_password, generate_subdomain
from ..network import nginx as ngx
from ..network import ssl as ssl_mgr
from ..core.state import InstallState
from .base import Panel


class XUIPanel(Panel):
    def __init__(self, config: dict, state: InstallState):
        super().__init__(config, state)
        self.panel_user = "admin"
        self.panel_pass = generate_password(16)
        self.panel_port = 47115 + (os.getpid() % 1000)
        self.panel_path = generate_subdomain(8)
        self.client_uuid = config.get("client_uuid")
        self.sub_id = config.get("sub_id")

    def install(self) -> None:
        if self.state.has_step("xui:installed"):
            print("  ℹ️ 3x-ui уже установлен")
            return

        print("  Установка 3x-ui v3.6.0...")
        run("curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh -o /tmp/3xui_install.sh", check=False, timeout=60)

        env = f"XUI_NONINTERACTIVE=1 XUI_DB_TYPE=sqlite XUI_USERNAME={self.panel_user} XUI_PASSWORD={self.panel_pass} XUI_PORT={self.panel_port} XUI_WEB_BASE_PATH={self.panel_path}"
        r = run(f"{env} bash /tmp/3xui_install.sh v3.6.0", check=False, timeout=300)

        # Wait for x-ui
        for _ in range(20):
            r = run("systemctl is-active x-ui", check=False)
            if "active" in r.stdout:
                break
            time.sleep(2)
        else:
            raise RuntimeError("x-ui не запустился")

        # Force settings
        run(f"/usr/local/x-ui/x-ui setting -username {self.panel_user} -password {self.panel_pass} -port {self.panel_port} -webBasePath /{self.panel_path}/", check=False)
        run("systemctl restart x-ui", check=False)
        time.sleep(3)

        self.state.add_systemd("x-ui")
        self.state.add_step("xui:installed")
        print(f"  ✅ 3x-ui: порт={self.panel_port}, путь=/{self.panel_path}/")

    def setup_ssl(self, domain: str) -> tuple:
        cert, key = ssl_mgr.get_le_cert(domain, self.state)
        if cert:
            run(f"/usr/local/x-ui/x-ui setting -certFile {cert} -keyFile {key}", check=False)
            run(f"/usr/local/x-ui/x-ui setting -subCertFile {cert} -subKeyFile {key}", check=False)
            run("systemctl restart x-ui", check=False)
            return cert, key
        return ssl_mgr.ensure_self_signed(domain, self.state)

    def create_inbound(self, node_ip: str, xray_port: int, path: str, client_uuid: str) -> str:
        tag = "host-cdn-xhttp"
        now_ms = int(time.time() * 1000)

        settings = {
            "clients": [{
                "id": client_uuid, "email": "user1", "enable": True,
                "expiryTime": 0, "limitIp": 0, "totalGB": 0,
                "subId": self.sub_id, "tgId": 0, "reset": 0,
                "created_at": now_ms, "updated_at": now_ms
            }],
            "decryption": "none", "fallbacks": []
        }

        stream = {
            "network": "xhttp", "security": "none",
            "externalProxy": [{"forceTls": "tls", "dest": self.cfg["front_domain"], "port": 443,
                               "sni": self.cfg["front_domain"], "fingerprint": "firefox", "alpn": "h2"}],
            "xhttpSettings": {
                "path": path, "mode": "packet-up", "uplinkHTTPMethod": "DELETE",
                "xPaddingKey": "q", "xPaddingMethod": "tokenish", "xPaddingPlacement": "query",
                "xPaddingBytes": "48-256", "xPaddingObfsMode": True,
                "sessionIDKey": "sid", "sessionIDPlacement": "query",
                "seqKey": "offset", "seqPlacement": "query",
                "scMaxEachPostBytes": "262144-786432", "scMinPostsIntervalMs": "0",
                "xmux": {"maxConcurrency": 0, "maxConnections": "16-32", "cMaxReuseTimes": 0,
                         "hMaxRequestTimes": "600-900", "hMaxReusableSecs": "120-240", "hKeepAlivePeriod": 20}
            }
        }

        sniffing = {"enabled": True, "destOverride": ["http", "tls", "quic"]}

        sj = json.dumps(settings).replace("'", "''")
        stj = json.dumps(stream).replace("'", "''")
        snj = json.dumps(sniffing).replace("'", "''")

        sql = f"""
DELETE FROM client_inbounds WHERE client_id IN (SELECT id FROM clients WHERE email='user1');
DELETE FROM client_traffics WHERE email='user1';
DELETE FROM clients WHERE email='user1';
DELETE FROM inbounds WHERE tag='{tag}';
INSERT INTO inbounds (user_id, up, down, total, remark, enable, expiry_time, listen, port, protocol, settings, stream_settings, tag, sniffing)
VALUES (1, 0, 0, 0, 'HOST-CDN', 1, 0, '127.0.0.1', {xray_port}, 'vless', '{sj}', '{stj}', '{tag}', '{snj}');
INSERT INTO clients (email, sub_id, uuid, limit_ip, total_gb, expiry_time, enable, tg_id, reset, created_at, updated_at)
VALUES ('user1', '{self.sub_id}', '{client_uuid}', 0, 0, 0, 1, 0, 0, {now_ms}, {now_ms});
"""
        with open("/tmp/xui_setup.sql", "w") as f:
            f.write(sql)
        run("sqlite3 /etc/x-ui/x-ui.db < /tmp/xui_setup.sql", check=False)

        # Link client to inbound
        cid = run("sqlite3 /etc/x-ui/x-ui.db 'SELECT id FROM clients WHERE email=\"user1\";'", check=False).stdout.strip()
        iid = run(f"sqlite3 /etc/x-ui/x-ui.db 'SELECT id FROM inbounds WHERE tag=\"{tag}\";'", check=False).stdout.strip()
        if cid and iid:
            run(f"sqlite3 /etc/x-ui/x-ui.db 'INSERT INTO client_inbounds (client_id, inbound_id, flow_override, created_at) VALUES ({cid}, {iid}, \"\", {now_ms});'", check=False)

        run("systemctl restart x-ui", check=False)
        self.state.add_step("xui:inbound_created")

        panel_domain = self.cfg.get("panel_domain", node_ip)
        return f"https://{panel_domain}/sub/{self.sub_id}"

    def get_credentials(self) -> dict:
        return {
            "username": self.panel_user,
            "password": self.panel_pass,
            "port": self.panel_port,
            "path": self.panel_path,
            "url": f"https://{self.cfg.get('panel_domain', 'localhost')}/{self.panel_path}/"
        }
