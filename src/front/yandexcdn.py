"""
Yandex Cloud CDN frontend.
"""
from ..utils.shell import run
from .base import Front


class YandexCDNFront(Front):
    def setup(self) -> bool:
        print("\n  === НАСТРОЙКА YANDEX CLOUD CDN ===")
        print(f"""
  1. https://cloud.yandex.ru/ → CDN → Создать ресурс
  2. Тип источника: Сервер
  3. IP источника: {self.cfg['node_ip']}
  4. Добавь домен: {self.cfg['front_domain']}
  5. Выпусти SSL-сертификат в панели Yandex Cloud
  6. Настрой CNAME в DNS-провайдере
""")
        ready = input("  Настроил Yandex CDN? (y/n): ").strip().lower()
        return ready in ("y", "yes", "д", "да")

    def verify(self) -> bool:
        domain = self.cfg["front_domain"]
        r = run(f"curl -sk https://{domain}/{self.cfg.get('path','p')} -o /dev/null -w '%{{http_code}}'", check=False, timeout=15)
        return r.stdout.strip() == "400"

    def instructions(self) -> str:
        return f"""
  Yandex Cloud CDN: https://cloud.yandex.ru/
  Origin: {self.cfg['node_ip']}
  Домен: {self.cfg['front_domain']}
"""
