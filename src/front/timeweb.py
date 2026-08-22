"""
Timeweb Cloud CDN frontend.
"""
from ..utils.shell import run
from .base import Front


class TimewebCDNFront(Front):
    def setup(self) -> bool:
        print("\n  === НАСТРОЙКA TIMEWEB CDN ===")
        print(f"""
  1. https://timeweb.cloud/ → CDN → Создать
  2. Источник: {self.cfg['node_ip']}
  3. Домен: {self.cfg['front_domain']}
  4. Включи SSL
  5. Настрой CNAME
""")
        ready = input("  Настроил Timeweb CDN? (y/n): ").strip().lower()
        return ready in ("y", "yes", "д", "да")

    def verify(self) -> bool:
        domain = self.cfg["front_domain"]
        r = run(f"curl -sk https://{domain}/{self.cfg.get('path','p')} -o /dev/null -w '%{{http_code}}'", check=False, timeout=15)
        return r.stdout.strip() == "400"

    def instructions(self) -> str:
        return f"""
  Timeweb CDN: https://timeweb.cloud/
  Origin: {self.cfg['node_ip']}
  Домен: {self.cfg['front_domain']}
"""
