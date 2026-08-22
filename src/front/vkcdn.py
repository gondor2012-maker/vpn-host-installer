"""
VK Cloud CDN frontend.
"""
from ..utils.shell import run
from .base import Front


class VKCDNFront(Front):
    def setup(self) -> bool:
        print("\n  === НАСТРОЙКА VK CLOUD CDN ===")
        print(f"""
  1. https://mcs.mail.ru/ → CDN → Создать ресурс
  2. Источник: {self.cfg['node_ip']}
  3. Порт источника: 443
  4. Протокол взаимодействия с источником: HTTPS
  5. Добавь домен: {self.cfg['front_domain']}
  6. SSL: выпусти Let's Encrypt через VK CDN
  7. CNAME: направь {self.cfg['front_domain']} на адрес, выданный VK CDN
""")
        ready = input("  Настроил VK CDN? (y/n): ").strip().lower()
        return ready in ("y", "yes", "д", "да")

    def verify(self) -> bool:
        domain = self.cfg["front_domain"]
        r = run(f"curl -sk https://{domain}/{self.cfg.get('path','p')} -o /dev/null -w '%{{http_code}}'", check=False, timeout=15)
        return r.stdout.strip() == "400"

    def instructions(self) -> str:
        return f"""
  VK Cloud CDN: https://mcs.mail.ru/
  Origin: {self.cfg['node_ip']}:443
  Домен: {self.cfg['front_domain']}
"""
