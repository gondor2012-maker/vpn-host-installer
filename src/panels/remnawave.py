"""
Remnawave panel installer and API manager.
"""
import json
import time
import hmac
import hashlib
import base64
import urllib.request
import ssl as ssl_mod
from ..utils.shell import run, ensure_dir
from ..utils.crypto import generate_password, generate_token
from ..network import nginx as ngx
from ..network import ssl as ssl_mgr
from ..core.state import InstallState
from .base import Panel


class RemnawavePanel(Panel):
    def __init__(self, config: dict, state: InstallState):
        super().__init__(config, state)
        self.panel_user = "admin"
        self.panel_pass = generate_password(20) + "Aa1"
        self.jwt_auth = generate_token(32)
        self.jwt_api = generate_token(32)
        self.pg_pass = generate_password(24)
        self.api_token = None

    def install(self) -> None:
        if self.state.has_step("remnawave:installed"):
            print("  ℹ️ Remnawave уже установлен")
            return

        print("  Установка Remnawave 3.2.3...")
        ensure_dir("/opt/remnawave")

        compose = """services:
  remnawave-db:
    container_name: remnawave-db
    image: postgres:17
    restart: always
    shm_size: 256m
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: {pg_pass}
    volumes:
      - remnawave-db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 3s
      timeout: 3s
      retries: 10
    networks:
      - remnawave-network
  remnawave-redis:
    container_name: remnawave-redis
    image: valkey/valkey:8.1.1-alpine
    restart: always
    command: valkey-server --save 20 1
    volumes:
      - remnawave-redis:/data
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 3s
      timeout: 3s
      retries: 10
    networks:
      - remnawave-network
  remnawave:
    container_name: remnawave
    image: remnawave/backend:3.2.3
    restart: always
    ports:
      - "127.0.0.1:3000:3000"
    env_file:
      - .env
    depends_on:
      remnawave-db:
        condition: service_healthy
      remnawave-redis:
        condition: service_healthy
    networks:
      - remnawave-network
volumes:
  remnawave-db:
  remnawave-redis:
networks:
  remnawave-network:
    driver: bridge
""".format(pg_pass=self.pg_pass)

        env = f"""JWT_AUTH_SECRET={self.jwt_auth}
JWT_API_TOKENS_SECRET={self.jwt_api}
APP_SECRET={self.jwt_auth}
METRICS_USER=metrics
METRICS_PASS={generate_password(16)}
WEBHOOK_SECRET_HEADER={generate_token(32)}
POSTGRES_USER=postgres
POSTGRES_PASSWORD={self.pg_pass}
POSTGRES_DB=postgres
DATABASE_URL="postgresql://postgres:{self.pg_pass}@remnawave-db:5432/postgres"
REDIS_HOST=remnawave-redis
REDIS_PORT=6379
FRONT_END_DOMAIN={self.cfg["panel_domain"]}
PANEL_DOMAIN={self.cfg["panel_domain"]}
SUB_PUBLIC_DOMAIN={self.cfg["panel_domain"]}/api/sub
IS_PANEL_BEHIND_CLOUDFLARE=false
TRAFFIC_RESET_DAY=1
"""

        with open("/opt/remnawave/docker-compose.yml", "w") as f:
            f.write(compose)
        with open("/opt/remnawave/.env", "w") as f:
            f.write(env)

        run("cd /opt/remnawave && docker compose down 2>/dev/null", check=False, timeout=60)
        run("cd /opt/remnawave && docker compose pull", check=False, timeout=300)
        run("cd /opt/remnawave && docker compose up -d", check=False, timeout=180)

        # Wait for panel
        for _ in range(60):
            r = run("curl -s http://127.0.0.1:3000/api/auth/register -o /dev/null -w '%{http_code}'", check=False)
            if r.stdout.strip() in ("200", "201", "400", "405"):
                break
            time.sleep(5)
        else:
            raise RuntimeError("Remnawave не запустился")

        self.state.add_dir("/opt/remnawave")
        self.state.add_file("/opt/remnawave/docker-compose.yml")
        self.state.add_file("/opt/remnawave/.env")
        self.state.add_docker("/opt/remnawave")
        self.state.add_step("remnawave:installed")
        print("  ✅ Remnawave запущен")

        self._create_api_token()

    def _create_api_token(self) -> None:
        token_uuid = __import__('uuid').uuid4().hex
        header_b = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()).rstrip(b"=").decode()
        payload_obj = {"uuid": token_uuid, "username": None, "role": "API", "iat": int(time.time()), "exp": int(time.time()) + 86400 * 365 * 10}
        payload_b = base64.urlsafe_b64encode(json.dumps(payload_obj, separators=(",", ":")).encode()).rstrip(b"=").decode()
        sig_data = f"{header_b}.{payload_b}"
        sig = base64.urlsafe_b64encode(hmac.new(self.jwt_auth.encode(), sig_data.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        self.api_token = f"{sig_data}.{sig}"

        run(f"docker exec remnawave-db psql -U postgres -c "DELETE FROM api_tokens WHERE name='installer';"", check=False)
        run(f"docker exec remnawave-db psql -U postgres -c "INSERT INTO api_tokens (uuid, name, scopes, expire_at) VALUES ('{token_uuid}', 'installer', ARRAY['*'], NOW() + INTERVAL '3650 days');"", check=False)
        self.state.add_step("remnawave:api_token")

    def api_call(self, method: str, path: str, data: dict = None) -> dict:
        url = f"http://127.0.0.1:3000/api/{path}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1"
        }
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                return {"error": e.code, "message": e.read().decode()[:500]}
            except:
                return {"error": e.code}
        except Exception as e:
            return {"error": str(e)}

    def setup_ssl(self, domain: str) -> None:
        cert, key = ssl_mgr.get_le_cert(domain, self.state)
        if cert:
            print(f"  ✅ LE сертификат для панели получен")

        ipv6 = __import__('os').path.exists("/proc/sys/net/ipv6")
        v6 = "\n    listen [::]:443 ssl http2;" if ipv6 else ""
        conf = f"""server {{
    listen 80;
    server_name {domain};
    location /.well-known/acme-challenge/ {{ root /var/www/certbot; }}
    location / {{ return 301 https://$host$request_uri; }}
}}
server {{
    listen 443 ssl http2;{v6}
    server_name {domain};
    ssl_certificate {cert or '/etc/nginx/ssl/cdn.crt'};
    ssl_certificate_key {key or '/etc/nginx/ssl/cdn.key'};
    ssl_protocols TLSv1.2 TLSv1.3;
    location / {{
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}"""
        ngx.write_site("panel.conf", conf, self.state)
        ngx.reload(self.state)

    def create_inbound(self, node_ip: str, xray_port: int, path: str, client_uuid: str) -> str:
        # Simplified: create profile, node, host, user via API
        # In production, expand with full Remnawave API logic
        profile_name = f"host-profile-{__import__('secrets').token_hex(4)}"

        profile_config = {
            "log": {"loglevel": "warning"},
            "inbounds": [{
                "tag": "host-xhttp", "port": xray_port, "listen": "127.0.0.1",
                "protocol": "vless",
                "settings": {"clients": [], "decryption": "none"},
                "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
                "streamSettings": {
                    "network": "xhttp", "security": "none",
                    "xhttpSettings": {
                        "mode": "packet-up", "path": path,
                        "uplinkHTTPMethod": "DELETE",
                        "xPaddingKey": "q", "xPaddingMethod": "tokenish",
                        "xPaddingPlacement": "query", "xPaddingBytes": "48-256",
                        "xPaddingObfsMode": True
                    }
                }
            }],
            "outbounds": [
                {"protocol": "freedom", "tag": "direct"},
                {"protocol": "blackhole", "tag": "block"}
            ]
        }

        resp = self.api_call("POST", "config-profiles", {"name": profile_name, "config": profile_config})
        profile_uuid = resp.get("response", {}).get("uuid")
        inbound_uuid = None
        for ib in resp.get("response", {}).get("inbounds", []):
            if ib.get("tag") == "host-xhttp":
                inbound_uuid = ib.get("uuid")
                break

        # Create node
        node_data = {
            "name": f"node-{node_ip.replace('.', '-')}",
            "address": node_ip, "port": 2222,
            "countryCode": "XX", "isTrafficTrackingActive": True,
            "trafficLimitBytes": 0, "trafficResetDay": 1,
            "configProfile": {
                "activeConfigProfileUuid": profile_uuid,
                "activeInbounds": [inbound_uuid] if inbound_uuid else []
            }
        }
        resp = self.api_call("POST", "nodes", node_data)
        node_uuid = resp.get("response", {}).get("uuid")

        # Create host
        host_payload = {
            "inbound": {"configProfileUuid": profile_uuid, "configProfileInboundUuid": inbound_uuid},
            "remark": "HOST CDN", "address": self.cfg["front_domain"], "port": 443,
            "path": path, "sni": self.cfg["front_domain"], "host": self.cfg["front_domain"],
            "alpn": "h2", "fingerprint": "firefox", "isDisabled": False,
            "securityLayer": "TLS", "allowInsecure": False
        }
        resp = self.api_call("POST", "hosts", host_payload)
        host_uuid = resp.get("response", {}).get("uuid")

        if node_uuid and host_uuid:
            self.api_call("PATCH", "hosts", {"uuid": host_uuid, "nodes": [node_uuid]})

        # Create user
        user_resp = self.api_call("POST", "users", {
            "username": "user1",
            "expireAt": "2099-12-31T23:59:59.000Z",
            "trafficLimitBytes": 0, "trafficLimitStrategy": "NO_RESET",
            "hwidDeviceLimit": 0
        })
        short_uuid = user_resp.get("response", {}).get("shortUuid", "")

        self.state.add_step("remnawave:resources_created")
        return f"https://{self.cfg['panel_domain']}/api/sub/{short_uuid}"

    def get_credentials(self) -> dict:
        return {
            "username": self.panel_user,
            "password": self.panel_pass,
            "url": f"https://{self.cfg.get('panel_domain', 'localhost')}"
        }
