# VPN Host Installer v2.1 — CDN Edition

> ⚠️ **REG.RU shared hosting больше не работает** — отключили mod_proxy на shared-хостинге.  
> Теперь скрипт работает **только через CDN-провайдеров**.

Автоматический установщик VPN-инфраструктуры с методом обхода блокировок **XHTTP packet-up** через CDN.

## ⚡ Быстрый старт

```bash
curl -fsSL https://raw.githubusercontent.com/gondor2012-maker/vpn-host-installer/main/install.sh | bash
```

## 📋 Требования

- **OS:** Ubuntu 20.04+ / Debian 11+
- **Права:** root
- **Домен:** зарегистрированный домен с DNS-управлением
- **CDN-аккаунт:** Cloudflare (рекомендуется), VK Cloud, Yandex Cloud, Timeweb или CDNvideo

## 🌐 Поддерживаемые CDN

| CDN | Сложность | Надёжность | Примечание |
|-----|-----------|------------|------------|
| **Cloudflare** | ⭐ Легко | ⭐⭐⭐ Высокая | Бесплатный тариф, лучший выбор |
| VK Cloud | ⭐⭐ Средне | ⭐⭐⭐ Высокая | Нужен аккаунт VK Cloud |
| Yandex Cloud | ⭐⭐ Средне | ⭐⭐⭐ Высокая | Нужен аккаунт Yandex Cloud |
| Timeweb | ⭐⭐ Средне | ⭐⭐ Средняя | Российский провайдер |
| CDNvideo (Beeline) | ⭐⭐ Средне | ⭐⭐ Средняя | Дороже остальных |
| ~~REG.RU shared~~ | — | — | ❌ Не работает (отключили mod_proxy) |

## 🔧 Параметры

```
python3 install.py [опции]
  --config FILE       Путь к config.yaml
  --mode {1,2,3}      1=панель+нода, 2=панель+удалённая нода, 3=только нода
  --panel {xui,remnawave}
  --domain DOMAIN     Базовый домен
  --front-domain D    Фронт-домен (CDN)
  --cdn {cloudflare,vk,yandex,timeweb,cdnvideo}
  --rollback          Откатить установку
```

## 🏗️ Архитектура

```
Клиент → CDN (443, TLS) → Origin Server (твой VDS, 443) → Nginx → Xray (127.0.0.1:2053)
                                              ↓
                                         Панель (3x-ui / Remnawave)
```

**Важно:** CDN проксирует HTTPS-трафик на твой сервер. Xray работает за nginx, маскируясь под обычный веб-трафик.

## 📦 Ручная установка

```bash
git clone https://github.com/gondor2012-maker/vpn-host-installer.git /opt/vpn-host-installer
cd /opt/vpn-host-installer
apt-get update && apt-get install -y python3-pip
pip3 install -r requirements.txt
nano config.yaml   # заполни домен и CDN
python3 install.py
```

## 📄 Лицензия

MIT
