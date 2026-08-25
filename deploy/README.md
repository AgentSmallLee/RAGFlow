# 阿里云服务器部署指南

## 系统兼容性

一键部署脚本支持以下系统：

| 系统 | 包管理器 | 状态 |
|-----|---------|------|
| **Ubuntu 22.04 / 24.04** | apt | ✅ 完美支持 |
| **Alibaba Cloud Linux 2 / 3** | yum/dnf | ✅ 完美支持 |
| **CentOS 7 / 8** | yum/dnf | ✅ 完美支持 |
| **Rocky Linux / AlmaLinux** | yum/dnf | ✅ 完美支持 |
| Debian 11/12 | apt | ✅ 应该没问题 |

脚本会自动检测系统类型并使用对应的包管理器。

> 💡 **说明**：阿里云服务器默认推荐的 **Alibaba Cloud Linux** 是 CentOS 兼容的，完全没问题，
> 用 `yum` 或 `dnf` 安装软件，和 CentOS 操作基本一样。

## 目录

- [一、准备工作（阿里云控制台操作）](#一准备工作阿里云控制台操作)
- [二、连接服务器](#二连接服务器)
- [三、一键部署（推荐）](#三一键部署推荐)
- [四、手动部署（一步步来）](#四手动部署一步步来)
- [五、上传你的文档](#五上传你的文档)
- [六、绑定域名（可选）](#六绑定域名可选)
- [七、配置 HTTPS（可选）](#七配置-https可选)
- [八、常用运维命令](#八常用运维命令)
- [九、常见问题排查](#九常见问题排查)

---

## 一、准备工作（阿里云控制台操作）

### 1. 服务器配置

在阿里云买了服务器之后，先确认几件事：

| 项目 | 推荐配置 | 说明 |
|-----|---------|------|
| **实例规格** | 2核4G（如 ecs.s6.large） | 最低 2核2G 也能跑，推荐 2核4G |
| **操作系统** | Ubuntu 22.04 64位 | 最稳定，教程最多 |
| **系统盘** | 40G 高效云盘 | 足够用 |
| **带宽** | 3M 按流量计费 / 固定带宽 | 用户少的话按流量计费更便宜 |

### 2. 设置 root 密码

刚买的服务器需要先设置 root 密码（或者用密钥登录）：

1. 进入 **ECS 控制台** → 找到你的实例
2. 点右侧 **"更多"** → **密码/密钥** → **重置实例密码**
3. 设置一个强密码，提交后点 **重启实例** 生效

### 3. 配置安全组（重要！）

安全组相当于防火墙，不放行端口就访问不了：

1. ECS 控制台 → 左侧菜单 **"网络与安全"** → **"安全组"**
2. 找到你实例绑定的安全组，点 **"配置规则"**
3. 点 **"手动添加"**，加入以下规则：

| 授权策略 | 协议类型 | 端口范围 | 授权对象 | 说明 |
|---------|---------|---------|---------|------|
| 允许 | SSH (22) | 22 | 0.0.0.0/0 | 远程登录（可选，建议只放行你的 IP） |
| 允许 | HTTP (80) | 80 | 0.0.0.0/0 | 网站访问，必须 |
| 允许 | HTTPS (443) | 443 | 0.0.0.0/0 | HTTPS 访问，推荐 |

### 4. 记录公网 IP

在 ECS 控制台实例列表里，找到 **"公网 IP 地址"**，记下来，后面要用。

---

## 二、连接服务器

### Windows 用户

用 **PuTTY** 或 **PowerShell**：

```powershell
# PowerShell 里直接输入
ssh root@你的公网IP
```

### Mac 用户

打开 **终端**（Terminal）：

```bash
ssh root@你的公网IP
```

输入刚才设置的 root 密码（输入时不显示字符，正常输入就行）。

连接成功后你会看到类似的提示符：
```
root@iZxxxxxx:~#
```

---

## 三、一键部署（推荐）

全程大概 5-10 分钟，跟着复制粘贴就行。

### 第 1 步：下载代码

```bash
# 进入项目目录
mkdir -p /var/www
cd /var/www

# 从 GitHub 克隆（推荐，方便以后更新）
git clone https://github.com/AgentSmallLee/RAGFlow.git ragflow
cd ragflow
```

> 如果你的服务器访问 GitHub 慢，可以用 Gitee 镜像，或者本地上传。
>
> **本地上传方式**（Mac 终端里执行，不是服务器上）：
> ```bash
> scp -r /你的本地路径/RAGFlow root@你的公网IP:/var/www/ragflow
> ```

### 第 2 步：运行部署脚本

```bash
cd /var/www/ragflow
bash deploy/setup.sh
```

脚本会自动完成以下事情（不用管，等着就行）：
- 安装 Python、Nginx、Git 等系统依赖
- 创建 Python 虚拟环境
- 安装项目所有依赖
- 配置 systemd 开机自启动
- 配置 Nginx 反向代理
- 配置防火墙

看到 `✅ 基础环境部署完成！` 就说明成功了。

### 第 3 步：配置 API Key

```bash
cd /var/www/ragflow
cp .env.example .env
nano .env
```

打开编辑器后，填入你的 API Key：

```env
# LLM 配置（按你实际用的填）
LLM_API_KEY=sk-xxxxxxxxxxxx
LLM_BASE_URL=
LLM_MODEL=qwen-plus

# Embedding 配置
EMBEDDING_API_KEY=sk-xxxxxxxxxxxx
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=text-embedding-v3
```

**操作说明：**
- 用方向键移动光标
- 改完后按 `Ctrl + O`（字母O，不是零），回车保存
- 按 `Ctrl + X` 退出编辑器

### 第 4 步：启动服务

```bash
systemctl start ragflow
systemctl status ragflow
```

看到 `active (running)` 就说明启动成功了。

### 第 5 步：访问验证

浏览器打开 `http://你的公网IP`，应该能看到 RAGFlow 的界面了！

---

## 四、手动部署（一步步来）

如果一键脚本出问题，可以按下面的步骤手动来。

### 1. 系统更新 + 安装依赖

```bash
apt update -y
apt upgrade -y
apt install -y python3 python3-pip python3-venv python3-dev \
    nginx git curl wget build-essential pkg-config
```

### 2. 准备项目代码

```bash
mkdir -p /var/www/ragflow
cd /var/www/ragflow
# 把代码放进来（git clone 或 scp 上传）
```

### 3. 创建虚拟环境 + 安装依赖

```bash
cd /var/www/ragflow
python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-gradio.txt
```

### 4. 配置 .env

```bash
cp .env.example .env
nano .env
# 填入 API Key 等配置
```

### 5. 创建 www-data 用户和设置权限

```bash
# 确保 www-data 用户存在
id -u www-data &>/dev/null || useradd -r -s /bin/false www-data

# 设置文件权限
chown -R www-data:www-data /var/www/ragflow
chmod -R 755 /var/www/ragflow
```

### 6. 建库（如果有文档）

```bash
sudo -u www-data .venv/bin/python build_index.py
```

### 7. 配置 systemd 服务

```bash
cp deploy/ragflow.service /etc/systemd/system/ragflow.service
systemctl daemon-reload
systemctl enable ragflow   # 设为开机自启
systemctl start ragflow    # 启动
systemctl status ragflow   # 确认状态
```

### 8. 配置 Nginx

```bash
cp deploy/nginx.conf /etc/nginx/sites-available/ragflow
ln -sf /etc/nginx/sites-available/ragflow /etc/nginx/sites-enabled/ragflow
rm -f /etc/nginx/sites-enabled/default

# 测试配置
nginx -t
# 如果显示 test is successful，就重载
systemctl reload nginx
```

### 9. 配置防火墙（阿里云的话主要在安全组里配）

```bash
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

---

## 五、上传你的文档

### 方式 A：通过 Web 界面上传（推荐）

直接在浏览器里打开网站，切换到 **"文档管理"** 标签页，拖拽上传就行。

上传的文档会保存在 `/var/www/ragflow/data/uploads/` 目录。

### 方式 B：服务器上直接放

```bash
# 在你本地电脑上执行，把文档传到服务器
scp -r /你的文档目录/* root@你的公网IP:/var/www/ragflow/data/documents/

# 然后在服务器上建库
cd /var/www/ragflow
sudo -u www-data .venv/bin/python build_index.py
```

---

## 六、绑定域名（可选）

如果有自己的域名，可以绑定上去，用域名访问比 IP 好看。

### 1. 域名解析

1. 登录你的域名服务商控制台（阿里云域名、腾讯云 DNSPod 等）
2. 找到域名，添加 **A 记录**：
   - 主机记录：`@`（主域名）或 `rag`（子域名，如 rag.example.com）
   - 记录类型：`A`
   - 记录值：你的服务器公网 IP
   - TTL：10 分钟

### 2. 修改 Nginx 配置

```bash
nano /etc/nginx/sites-available/ragflow
```

把 `server_name your-domain.com;` 改成你的域名，比如：
```nginx
server_name rag.example.com;
```

保存后重载 Nginx：
```bash
nginx -t && systemctl reload nginx
```

等几分钟 DNS 生效，用域名访问试试。

---

## 七、配置 HTTPS（可选）

有域名的话强烈建议配 HTTPS，免费的，一键搞定：

```bash
# 安装 certbot
apt install -y certbot python3-certbot-nginx

# 一键申请证书并自动配置
certbot --nginx -d 你的域名
```

过程中会问你邮箱和是否同意协议，按提示操作就行。

证书有效期 90 天，**会自动续期**，不用管。

配好之后访问 `https://你的域名`，浏览器地址栏左边会有个小锁 🔒。

---

## 八、常用运维命令

```bash
# ====== 服务管理 ======
systemctl start ragflow      # 启动
systemctl stop ragflow       # 停止
systemctl restart ragflow    # 重启
systemctl status ragflow     # 查看状态
systemctl enable ragflow     # 设为开机自启
systemctl disable ragflow    # 取消开机自启

# ====== 查看日志 ======
journalctl -u ragflow -f              # 实时日志（Ctrl+C 退出）
journalctl -u ragflow -n 100          # 最后100行
journalctl -u ragflow --since "1 hour ago"  # 最近1小时

# ====== 更新代码 ======
cd /var/www/ragflow
git pull
systemctl restart ragflow

# ====== Nginx ======
nginx -t                     # 测试配置是否正确
nginx -s reload              # 平滑重载（不中断服务）
systemctl restart nginx      # 完全重启

# ====== 磁盘空间 ======
df -h                        # 查看磁盘使用情况
du -sh /var/www/ragflow/data/vector_db/  # 向量库大小
```

---

## 九、常见问题排查

### ❌ 浏览器访问不了，一直转圈

**大概率是安全组没放行 80 端口。**
去阿里云安全组里确认加了 HTTP(80) 规则。

也可以在服务器上测试：
```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:7860
# 返回 200 说明服务正常，是外部访问的问题
```

### ❌ 502 Bad Gateway

Nginx 转发了，但后端服务没启动。

```bash
systemctl status ragflow     # 看服务状态
journalctl -u ragflow -n 50  # 看最近的错误日志
```

常见原因：
- `.env` 没配置或配置错了
- 依赖没装全
- 端口被占用了

### ❌ 500 Internal Server Error

服务内部报错，看日志：
```bash
journalctl -u ragflow -n 100 --no-pager
```

### ❌ 上传文件提示 413 Request Entity Too Large

Nginx 限制了上传大小。`deploy/nginx.conf` 里默认配了 100M，要是还不够就改大：

```bash
nano /etc/nginx/sites-available/ragflow
# 找到 client_max_body_size 100M; 改成 500M 或更大
nginx -t && systemctl reload nginx
```

### ❌ 页面能打开但点发送没反应 / 报错

看浏览器控制台（F12 → Console），同时看服务器日志：
```bash
journalctl -u ragflow -f
```

### ❌ 想换 API Key 或模型

```bash
cd /var/www/ragflow
nano .env
# 修改完保存
systemctl restart ragflow
```

### ❌ Alibaba Cloud Linux 和 Ubuntu 操作有什么不一样？

大部分操作一样，主要区别在这几个地方：

| 操作 | Ubuntu | Alibaba Cloud Linux / CentOS |
|-----|--------|------------------------------|
| 安装软件 | `apt install` | `yum install` 或 `dnf install` |
| 运行用户 | `www-data` | `nginx` |
| Nginx 配置目录 | `/etc/nginx/sites-available/` | `/etc/nginx/conf.d/` |
| 防火墙 | `ufw` | `firewall-cmd` |
| 编辑器 | 自带 nano | 可能没有 nano，用 `vi` |

💡 一键脚本已经自动处理了这些差异，直接跑就行。

### ❌ 提示 `bash: nano: command not found` 怎么办？

Alibaba Cloud Linux 默认可能没装 nano，两个选择：

**方案 A：装 nano**
```bash
yum install -y nano
```

**方案 B：用 vi（系统自带）**
- 打开文件：`vi 文件名`
- 按 `i` 进入编辑模式（左下角出现 -- INSERT --）
- 编辑完按 `Esc` 退出编辑模式
- 输入 `:wq` 回车（保存并退出）
- 不想保存就输入 `:q!` 回车（强制退出不保存）

---

## 文件目录结构（部署后）

```
/var/www/ragflow/
├── .env                     # 配置文件（密钥等，不提交 git）
├── .env.example             # 配置模板
├── app.py                   # Web 启动入口
├── build_index.py           # 建库脚本
├── chat.py                  # 命令行问答
├── requirements.txt         # 基础依赖
├── requirements-gradio.txt  # Gradio 额外依赖
├── config/                  # 配置模块
├── src/                     # 源代码
├── web/                     # Web 前端
├── deploy/                  # 部署相关文件
├── data/
│   ├── documents/           # 原始文档（离线建库用）
│   ├── uploads/             # Web 界面上传的文档
│   └── vector_db/           # 向量数据库
└── .venv/                   # Python 虚拟环境
```
