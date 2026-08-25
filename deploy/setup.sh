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

# ---------- 1. 系统依赖 + Python ----------
echo ""
echo "[1/9] 安装系统依赖..."

# 检查 Python 版本，要求 >= 3.10
PYTHON_BIN="python3"
PYTHON_VERSION=$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo "当前 Python 版本: $PYTHON_VERSION"

# 需要 Python >= 3.10
NEED_INSTALL_PYTHON=false
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo "⚠️  Python 版本过低，需要安装 Python 3.11+"
    NEED_INSTALL_PYTHON=true
fi

if [ "$PKG_MANAGER" = "apt" ]; then
    apt update -y
    apt install -y python3 python3-pip python3-venv python3-dev \
        nginx git curl wget build-essential pkg-config

    if [ "$NEED_INSTALL_PYTHON" = true ]; then
        # Ubuntu 上加 deadsnakes PPA
        apt install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa
        apt update -y
        apt install -y python3.11 python3.11-venv python3.11-dev
        PYTHON_BIN="python3.11"
    fi

elif [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
    $PKG_MANAGER update -y
    $PKG_MANAGER install -y nginx git curl wget gcc gcc-c++ make pkgconfig

    if [ "$NEED_INSTALL_PYTHON" = true ]; then
        echo "正在安装 Python 3.11..."

        # 尝试从官方源安装（Alibaba Cloud Linux 3 / CentOS 8）
        if command -v dnf &>/dev/null; then
            # 先试试能不能直接装 python3.11
            if dnf list available python3.11 &>/dev/null; then
                dnf install -y python3.11 python3.11-devel python3.11-pip
            else
                # 装 EPEL 源再试
                dnf install -y epel-release 2>/dev/null || true
                if dnf list available python3.11 &>/dev/null; then
                    dnf install -y python3.11 python3.11-devel python3.11-pip
                else
                    # 用源码编译安装（兜底方案）
                    echo "官方源没有 Python 3.11，正在从源码编译安装（约 5-10 分钟）..."
                    $PKG_MANAGER install -y openssl-devel bzip2-devel libffi-devel zlib-devel xz-devel sqlite-devel readline-devel
                    cd /tmp
                    wget -q https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz
                    tar xf Python-3.11.9.tgz
                    cd Python-3.11.9
                    ./configure --prefix=/usr/local --enable-optimizations --with-ensurepip=install > /dev/null
                    make -j$(nproc) > /dev/null
                    make altinstall > /dev/null
                    cd /
                    rm -rf /tmp/Python-3.11.9*
                fi
            fi
            PYTHON_BIN="python3.11"
        else
            # yum (CentOS 7) - 源码安装
            echo "正在从源码编译 Python 3.11（约 10-15 分钟）..."
            $PKG_MANAGER install -y openssl-devel bzip2-devel libffi-devel zlib-devel xz-devel sqlite-devel readline-devel
            cd /tmp
            wget -q https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz
            tar xf Python-3.11.9.tgz
            cd Python-3.11.9
            ./configure --prefix=/usr/local --enable-optimizations --with-ensurepip=install > /dev/null
            make -j$(nproc) > /dev/null
            make altinstall > /dev/null
            cd /
            rm -rf /tmp/Python-3.11.9*
            PYTHON_BIN="python3.11"
        fi
    else
        # 系统自带 Python 3.10+，装开发包
        $PKG_MANAGER install -y python3 python3-pip python3-devel
    fi
fi

# 确保 python3.11 可用
if [ "$NEED_INSTALL_PYTHON" = true ]; then
    if ! command -v $PYTHON_BIN &>/dev/null; then
        echo "❌ Python 安装失败，请手动安装 Python 3.10+"
        exit 1
    fi
    echo "Python 安装完成: $($PYTHON_BIN --version)"
fi

# ---------- 2. 创建项目目录和用户 ----------
echo ""
echo "[2/9] 创建项目目录和用户..."
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
echo "[3/9] 创建 Python 虚拟环境..."
cd /var/www/ragflow
if [ ! -d ".venv" ]; then
    $PYTHON_BIN -m venv .venv
fi
chown -R $RUN_USER:$RUN_USER .venv

# ---------- 4. 安装项目依赖 ----------
echo ""
echo "[4/9] 安装 Python 依赖..."
cd /var/www/ragflow
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-gradio.txt

# ---------- 5. 配置 systemd 服务 ----------
echo ""
echo "[5/9] 配置 systemd 服务..."
# 替换服务文件中的运行用户
sed "s/User=www-data/User=$RUN_USER/g; s/Group=www-data/Group=$RUN_USER/g" \
    /var/www/ragflow/deploy/ragflow.service \
    > /etc/systemd/system/ragflow.service
systemctl daemon-reload
systemctl enable ragflow

# ---------- 6. 配置 Nginx ----------
echo ""
echo "[6/9] 配置 Nginx..."
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
echo "[7/9] 配置防火墙..."
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

# ---------- 8. 环境变量：记录使用的 Python ----------
echo ""
echo "[8/9] 写入环境变量配置..."

# 把 Python 路径写到 .env 里的注释里，方便排查
if [ ! -f /var/www/ragflow/.env ]; then
    touch /var/www/ragflow/.env
fi
chown -R $RUN_USER:$RUN_USER /var/www/ragflow/.env

# ---------- 9. 完成 ----------
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
