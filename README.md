# VPN Host Installer v2.0

Автоматический установщик VPN-инфраструктуры с методом обхода блокировок **XHTTP packet-up** через shared-хостинг REG.RU.

## ⚡ Быстрый старт

Установка одной командой на чистый Ubuntu/Debian сервер:

```bash
curl -fsSL https://raw.githubusercontent.com/gondor2012-maker/vpn-host-installer/main/install.sh | bash
```

С параметрами:
```bash
curl -fsSL https://raw.githubusercontent.com/gondor2012-maker/vpn-host-installer/main/install.sh | bash -s -- --mode 1 --panel xui --domain example.com
```

## 📋 Требования

- **OS:** Ubuntu 20.04+ / Debian 11+
- **Права:** root
- **Домен:** зарегистрированный домен (для панели и фронта)
- **Shared-хостинг:** аккаунт на REG.RU (или другой поддерживаемый CDN)

## 🔧 Параметры

| Параметр | Описание | Значение по умолчанию |
|----------|----------|----------------------|
| `--mode` | Режим: `1`=панель+нода, `2`=панель+удалённая нода, `3`=только нода | `1` |
| `--panel` | Панель: `xui` или `remnawave` | `xui` |
| `--domain` | Базовый домен | из `config.yaml` |
| `--front-domain` | Фронт-домен (REG.RU) | из `config.yaml` |
| `--rollback` | Откатить установку | — |

## 📦 Ручная установка

```bash
git clone https://github.com/gondor2012-maker/vpn-host-installer.git /opt/vpn-host-installer
cd /opt/vpn-host-installer
apt-get update && apt-get install -y python3-pip
pip3 install -r requirements.txt
nano config.yaml
python3 install.py
```

## 🏗️ Архитектура

```
Клиент → CDN/REG.RU (443) → Nginx (443) → Xray (127.0.0.1:2053) → Интернет
                              ↓
                         Панель (3x-ui / Remnawave)
```

## ✨ Возможности

- **XHTTP packet-up** — обход DPI через shared-хостинг
- **3x-ui v3.6.0** и **Remnawave 3.2.3** — поддержка двух панелей
- **Idempotency** — можно перезапускать установку
- **Rollback** — полный откат: `python3 install.py --rollback`
- **Нет vendor lock-in** — нет зависимости от внешних серверов лицензий
- **Каскад** — двухсерверная архитектура relay → exit

## 📄 Лицензия

MIT — используйте на свой страх и риск.
