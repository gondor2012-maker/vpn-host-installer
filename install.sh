#!/bin/bash
# VPN Host Installer v2.1 — CDN Edition Bootstrap
# Usage: curl -fsSL https://raw.githubusercontent.com/gondor2012-maker/vpn-host-installer/main/install.sh | bash

set -e

REPO_URL="https://github.com/gondor2012-maker/vpn-host-installer/archive/refs/heads/main.zip"
INSTALL_DIR="/opt/vpn-host-installer"

echo "=========================================="
echo "  VPN Host Installer v2.1 — CDN Edition"
echo "=========================================="

if [ "$EUID" -ne 0 ]; then
    echo "ОШИБКА: Запусти от root!"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "  Установка python3..."
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip curl unzip
fi

echo "  Скачивание..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd /tmp
curl -fsSL -o vhi.zip "$REPO_URL" 2>/dev/null || {
    echo "  Пробую git clone..."
    apt-get install -y -qq git
    git clone --depth 1 "https://github.com/gondor2012-maker/vpn-host-installer" "$INSTALL_DIR"
}

if [ -f vhi.zip ]; then
    unzip -q vhi.zip -d /tmp/vhi_extract
    mv /tmp/vhi_extract/*/src "$INSTALL_DIR/"
    mv /tmp/vhi_extract/*/templates "$INSTALL_DIR/"
    mv /tmp/vhi_extract/*/install.py "$INSTALL_DIR/"
    mv /tmp/vhi_extract/*/config.yaml "$INSTALL_DIR/"
    mv /tmp/vhi_extract/*/requirements.txt "$INSTALL_DIR/"
    rm -rf /tmp/vhi_extract vhi.zip
fi

echo "  Установка зависимостей..."
cd "$INSTALL_DIR"
pip3 install -q -r requirements.txt 2>/dev/null || pip3 install -q pyyaml jinja2 cryptography 2>/dev/null

echo "  Запуск установщика..."
python3 "$INSTALL_DIR/install.py" "$@"
