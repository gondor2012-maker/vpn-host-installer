"""
REG.RU shared hosting frontend via .htaccess mod_proxy.
"""
import ftplib
import time
from io import BytesIO
from ..utils.shell import run
from .base import Front


class RegruFront(Front):
    def setup(self) -> bool:
        print("\n  === НАСТРОЙКА REG.RU ФРОНТА ===")
        print("  Фронт-домен:", self.cfg["front_domain"])
        print("  Нода (backend):", self.cfg["node_ip"])
        print("  Путь:", self.cfg.get("path", "/p"))

        # Try FTP auto-upload
        auto = input("\n  Автоматически залить .htaccess через FTP? (y/n): ").strip().lower()
        if auto in ("y", "yes", "д", "да"):
            return self._upload_via_ftp()
        return False

    def _upload_via_ftp(self) -> bool:
        try:
            host = input("  FTP IP (напр. 31.31.197.4): ").strip()
            user = input("  FTP логин: ").strip()
            pw = input("  FTP пароль: ").strip()
            if not all([host, user, pw]):
                return False

            ftp = ftplib.FTP()
            ftp.connect(host, 21, timeout=30)
            ftp.login(user, pw)
            ftp.set_pasv(True)
            print(f"  ✅ Подключено к FTP")

            # Find site dir
            paths = [f"/data/www/{self.cfg['front_domain']}", f"/var/www/{user}/data/www/{self.cfg['front_domain']}"]
            site_dir = None
            for p in paths:
                try:
                    ftp.cwd(p)
                    site_dir = p
                    break
                except:
                    pass

            if not site_dir:
                manual = input("  Путь к папке сайта: ").strip()
                if manual:
                    ftp.cwd(manual)
                    site_dir = manual
                else:
                    return False

            # Backup old .htaccess
            files = ftp.nlst()
            if ".htaccess" in files:
                backup = f".htaccess.backup.{int(time.time())}"
                try:
                    ftp.rename(".htaccess", backup)
                    print(f"  ✅ Бэкап создан: {backup}")
                except:
                    print("  ⚠️ Перезаписываю старый .htaccess")

            pattern = self.cfg.get("path", "p").lstrip("/")
            target = self.cfg.get("path", "/p")
            content = f"RewriteEngine On\nRewriteRule ^{pattern}$ http://{self.cfg['node_ip']}{target} [P]\n"

            ftp.storbinary("STOR .htaccess", BytesIO(content.encode("utf-8")))
            ftp.quit()
            print("  ✅ .htaccess загружен")
            return True

        except Exception as e:
            print(f"  ❌ Ошибка FTP: {e}")
            return False

    def verify(self) -> bool:
        domain = self.cfg["front_domain"]
        path = self.cfg.get("path", "p")
        r = run(f"curl -sk https://{domain}/{path} -o /dev/null -w '%{http_code}'", check=False, timeout=15)
        code = r.stdout.strip()
        if code == "400":
            print(f"  ✅ Фронт работает (400 от xray)")
            return True
        print(f"  ⚠️ Фронт вернул {code}, ожидалось 400")
        return False

    def instructions(self) -> str:
        return f"""
  ============================================
  НАСТРОЙКА ФРОНТА (шаред-хостинг REG.RU)
  ============================================
  Фронт-домен: {self.cfg['front_domain']}
  Нода: {self.cfg['node_ip']}

  1. ispmanager -> Сайты -> Создать сайт:
     - Имя: {self.cfg['front_domain']}
     - Псевдонимы: убрать www
     - SSL: пока ВЫКЛ, перенаправление HTTP->HTTPS: ВЫКЛ

  2. DNS: A-запись {self.cfg['front_domain']} -> IP хостинга

  3. SSL-сертификаты -> Let's Encrypt -> привязать к сайту

  4. .htaccess в корне сайта:
     RewriteEngine On
     RewriteRule ^{self.cfg.get('path','p').lstrip('/')}$ http://{self.cfg['node_ip']}{self.cfg.get('path','/p')} [P]

  5. Проверка: curl https://{self.cfg['front_domain']}/{self.cfg.get('path','p')} -> 400 (xray)
"""
