"""
Cloudflare CDN frontend.
Самый простой и надёжный вариант — проксирование через Cloudflare (бесплатный тариф).
"""
from ..utils.shell import run
from .base import Front


class CloudflareFront(Front):
    def setup(self) -> bool:
        print("\n  === НАСТРОЙКА CLOUDFLARE CDN ===")
        domain = self.cfg["front_domain"]
        origin_ip = self.cfg["node_ip"]

        print(f"""
  1. Зарегистрируйся/войди на https://dash.cloudflare.com

  2. Добавь сайт: {domain}
     → Cloudflare просканирует DNS-записи

  3. Создай A-запись:
     - Name: @ (или поддомен, например origin)
     - IPv4 address: {origin_ip}
     - Proxy status: ВКЛЮЧЕНО (оранжевая облачка)

  4. В настройках SSL/TLS:
     - Mode: Full (strict) — если на origin есть валидный LE сертификат
     - Mode: Full — если self-signed

  5. В настройках Network:
     - gRPC: ON (если используешь gRPC)
     - WebSockets: ON

  6. В Page Rules (опционально):
     - {domain}/p/* → Cache Level: Bypass
     (чтобы CDN не кешировал VPN-трафик)
""")

        ready = input("  Настроил Cloudflare? (y/n): ").strip().lower()
        return ready in ("y", "yes", "д", "да")

    def verify(self) -> bool:
        domain = self.cfg["front_domain"]
        path = self.cfg.get("path", "p")
        r = run(f"curl -sk https://{domain}/{path} -o /dev/null -w '%{{http_code}}'", check=False, timeout=15)
        code = r.stdout.strip()
        if code == "400":
            print(f"  ✅ Фронт работает (400 от xray)")
            return True
        print(f"  ⚠️ Фронт вернул {code}, ожидалось 400")
        return False

    def instructions(self) -> str:
        return f"""
  ============================================
  НАСТРОЙКА CLOUDFLARE
  ============================================
  Домен: {self.cfg['front_domain']}
  Origin IP: {self.cfg['node_ip']}

  1. dash.cloudflare.com → Add Site → {self.cfg['front_domain']}
  2. DNS → A-запись → {self.cfg['node_ip']} → Proxy: ON
  3. SSL/TLS → Full (или Full strict)
  4. Network → gRPC ON, WebSockets ON
  5. Page Rules → {self.cfg['front_domain']}/{self.cfg.get('path','p')}/* → Bypass Cache
"""
