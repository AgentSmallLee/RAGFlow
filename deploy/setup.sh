#!/bin/bash
# ============================================================
# RAGFlow 云服务器一键部署脚本
# 支持系统：
#   - Ubuntu 22.04 / 24.04 (apt)
#   - CentOS 7/8 / Alibaba Cloud Linux 2/3 (yum/dnf)
#   - Rocky Linux / AlmaLinux (yum/dnf)
# 使用方式：bash deploy/setup.sh
# ============================================================

set -e

echo "=========================================="
echo " RAGFlow 云服务器部署脚本"
echo "=========================================="

# ---------- 0. 检查 root 权限 ----------
if [ "$EUID" -ne 0 ]; then
    echo "请使用 root 权限运行: sudo bash deploy/setup.sh"
    exit 1
fi

# ---------- 0.5 检测系统类型 ----------
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    OS_VERSION=$VERSION_ID
else
    echo "无法检测系统类型，请手动部署"
    exit 1
fi

echo "检测到系统: $OS $OS_VERSION"

# 判断包管理器
if command -v apt &>/dev/null; then
    PKG_MANAGER="apt"
    echo "使用 apt 包管理器（Debian/Ubuntu 系）"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    echo "使用 dnf 包管理器（RHEL/CentOS 8+ 系）"
elif command -v yum &>/dev/null; then
    PKG_MANAGER="yum"
    echo "使用 yum 包管理器（RHEL/CentOS 7 系）"
else
    echo "不支持的包管理器，请手动部署"
    exit 1
fi

# ---------- 1. 系统依赖 ----------
echo ""
echo "[1/8] 安装系统依赖..."

if [ "$PKG_MANAGER" = "apt" ]; then
    apt update -y
    apt install -y python3 python3-pip python3-venv python3-dev \
        nginx git curl wget build-essential pkg-config
elif [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
    $PKG_MANAGER update -y
    $PKG_MANAGER install -y python3 python3-pip python3-devel \
        nginx git curl wget gcc gcc-c++ make pkgconfig
    # CentOS/Alibaba Cloud Linux 可能没有 python3-venv 单独包
    # 确保 python3 包含 venv 模块
fi

# ---------- 2. 创建项目目录和用户 ----------
echo ""
echo "[2/8] 创建项目目录和用户..."
mkdir -p /var/www/ragflow
if ! id -u nginx >/dev/null 2>&1; then
    # 有些系统 nginx 运行用户是 www-data，有些是 nginx
    if id -u www-data >/dev/null 2>&1; then
        RUN_USER="www-data"
    else
        useradd -r -s /bin/false nginx 2>/dev/null || true
        RUN_USER="nginx"
    fi
else
    RUN_USER="nginx"
fi
echo "运行用户: $RUN_USER"
chown -R $RUN_USER:$RUN_USER /var/www/ragflow

# ---------- 3. 创建 Python 虚拟环境 ----------
echo ""
echo "[3/8] 创建 Python 虚拟环境..."
cd /var/www/ragflow
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
chown -R $RUN_USER:$RUN_USER .venv

# ---------- 4. 安装项目依赖 ----------
echo ""
echo "[4/8] 安装 Python 依赖..."
cd /var/www/ragflow
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-gradio.txt

# ---------- 5. 配置 systemd 服务 ----------
echo ""
echo "[5/8] 配置 systemd 服务..."
# 替换服务文件中的运行用户
sed "s/User=www-data/User=$RUN_USER/g; s/Group=www-data/Group=$RUN_USER/g" \
    /var/www/ragflow/deploy/ragflow.service \
    > /etc/systemd/system/ragflow.service
systemctl daemon-reload
systemctl enable ragflow

# ---------- 6. 配置 Nginx ----------
echo ""
echo "[6/8] 配置 Nginx..."
# 不同系统 nginx 配置目录不一样
if [ -d /etc/nginx/sites-available ]; then
    # Debian/Ubuntu 风格
    cp /var/www/ragflow/deploy/nginx.conf /etc/nginx/sites-available/ragflow
    if [ ! -f /etc/nginx/sites-enabled/ragflow ]; then
        ln -s /etc/nginx/sites-available/ragflow /etc/nginx/sites-enabled/ragflow
    fi
    rm -f /etc/nginx/sites-enabled/default
else
    # CentOS/RHEL 风格，配置放在 conf.d 目录
    cp /var/www/ragflow/deploy/nginx.conf /etc/nginx/conf.d/ragflow.conf
    # 注释掉默认 server
    if [ -f /etc/nginx/nginx.conf ]; then
        sed -i 's/listen\s*80 default_server;/# listen 80 default_server;/g' /etc/nginx/nginx.conf 2>/dev/null || true
        sed -i 's/server_name\s*_;/# server_name _;/g' /etc/nginx/nginx.conf 2>/dev/null || true
    fi
fi

nginx -t && systemctl enable nginx && systemctl reload nginx

# ---------- 7. 配置防火墙 ----------
echo ""
echo "[7/8] 配置防火墙..."
if command -v firewall-cmd &>/dev/null; then
    # CentOS/RHEL 用 firewalld
    firewall-cmd --permanent --add-service=http 2>/dev/null || true
    firewall-cmd --permanent --add-service=https 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
elif command -v ufw &>/dev/null; then
    # Ubuntu 用 ufw
    ufw allow 80/tcp 2>/dev/null || true
    ufw allow 443/tcp 2>/dev/null || true
fi
echo "⚠️  如果是阿里云/腾讯云服务器，记得在控制台安全组放行 80/443 端口"

# ---------- 8. 完成 ----------
echo ""
echo "=========================================="
echo " ✅ 基础环境部署完成！"
echo "=========================================="
echo ""
echo "运行用户: $RUN_USER"
echo ""
echo "下一步操作："
echo "  1. 复制 .env.example 为 .env，填入 API Key"
echo "     cd /var/www/ragflow"
echo "     cp .env.example .env"
echo "     vi .env"
echo ""
echo "  2. 建库（如果有文档）:"
echo "     sudo -u $RUN_USER .venv/bin/python build_index.py"
echo ""
echo "  3. 启动服务:"
echo "     systemctl start ragflow"
echo "     systemctl status ragflow"
echo ""
echo "  4. 浏览器访问服务器 IP 即可"
echo ""
echo "常用命令："
echo "  启动:   systemctl start ragflow"
echo "  停止:   systemctl stop ragflow"
echo "  重启:   systemctl restart ragflow"
echo "  状态:   systemctl status ragflow"
echo "  日志:   journalctl -u ragflow -f"
echo ""
