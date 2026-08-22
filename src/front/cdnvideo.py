"""
CDNvideo (Beeline) frontend.
"""
from ..utils.shell import run
from .base import Front


class CDNvideoFront(Front):
    def setup(self) -> bool:
        print("\n  === НАСТРОЙКА CDNVIDEO (BEELINE) ===")
        print(f"""
  1. https://cdnvideo.ru/ → Личный кабинет
  2. Создать CDN-ресурс
  3. Origin: {self.cfg['node_ip']}
  4. Домен: {self.cfg['front_domain']}
  5. SSL + CNAME
""")
        ready = input("  Настроил CDNvideo? (y/n): ").strip().lower()
        return ready in ("y", "yes", "д", "да")

    def verify(self) -> bool:
        domain = self.cfg["front_domain"]
        r = run(f"curl -sk https://{domain}/{self.cfg.get('path','p')} -o /dev/null -w '%{{http_code}}'", check=False, timeout=15)
        return r.stdout.strip() == "400"

    def instructions(self) -> str:
        return f"""
  CDNvideo: https://cdnvideo.ru/
  Origin: {self.cfg['node_ip']}
  Домен: {self.cfg['front_domain']}
"""
