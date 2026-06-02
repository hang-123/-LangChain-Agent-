# BettaFish 云服务器 Docker 部署指南

## 目录

1. [架构概览](#1-架构概览)
2. [服务器准备](#2-服务器准备)
3. [快速部署（5分钟）](#3-快速部署)
4. [配置详解](#4-配置详解)
5. [运维管理](#5-运维管理)
6. [HTTPS 配置](#6-https-配置可选)
7. [故障排查](#7-故障排查)

---

## 1. 架构概览

```
                    ┌─────────────────────────────────┐
  用户 → :80        │         Nginx (Docker)           │
                    │  • 静态前端 (React SPA)           │
                    │  • /api/* 反向代理                │
                    │  • SSE 流式支持                   │
                    └───────────┬─────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
   ┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
   │  App :9000        │ │ PostgreSQL   │ │  Redis       │
   │  FastAPI+LangGraph│ │ :5432        │ │  :6379       │
   │  (Docker)         │ │ + pgvector   │ │  (Docker)    │
   └──────────────────┘ └──────────────┘ └──────────────┘
```

**4 个容器：**
| 服务 | 镜像 | 端口 | 用途 |
|------|------|------|------|
| `nginx` | 自建 (Dockerfile.frontend) | 80 | 反向代理 + 前端静态文件 |
| `app` | 自建 (Dockerfile) | 9000 (内网) | FastAPI + LangGraph 后端 |
| `postgres` | pgvector/pgvector:pg16 | 5432 (仅本地) | 向量数据库 + 业务数据 |
| `redis` | redis:7-alpine | 6379 (仅本地) | 缓存 + 消息队列 |

---

## 2. 服务器准备

### 2.1 最低配置要求

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 磁盘 | 20 GB | 50 GB+ |
| 系统 | Ubuntu 22.04 / Debian 12 / CentOS 8+ |

> 阿里云 / 腾讯云 2核4G 的轻量应用服务器足够起步。

### 2.2 安装 Docker

```bash
# Ubuntu / Debian 一键安装
curl -fsSL https://get.docker.com | bash

# 将当前用户加入 docker 组 (免 sudo)
sudo usermod -aG docker $USER

# 重新登录生效，或执行:
newgrp docker

# 验证
docker --version
docker compose version
```

### 2.3 开放端口

在云服务器**安全组**中开放：
- `80` (HTTP)
- `443` (HTTPS，可选)
- `22` (SSH，应该已开)

> ⚠️ **不要**开放 5432、6379、9000 — 这些端口仅容器间通信，开放到公网会有安全风险。

---

## 3. 快速部署（5分钟）

### 3.1 上传代码到服务器

```bash
# 方式1: git clone (推荐)
git clone <你的仓库地址> bettafish
cd bettafish

# 方式2: scp 上传
scp -r ./bettafish_langchain user@你的服务器IP:/home/user/bettafish
```

### 3.2 配置环境变量

```bash
# 从模板创建
cp .env.production .env

# 编辑 .env，填入真实的 API Key 和密码
nano .env   # 或 vim .env
```

**必须修改的配置项：**

```ini
# LLM API Key (阿里云 DashScope 或其他 OpenAI 兼容)
QUERY_ENGINE_API_KEY=sk-你的真实key

# Tavily 搜索 API Key (https://tavily.com)
TAVILY_API_KEY=tvly-你的真实key

# Embedding API Key (SiliconFlow 或其他)
EMBEDDING_API_KEY=sk-你的真实key

# 数据库密码 (改为强密码!)
PG_PASSWORD=至少16位的强密码

# 数据库连接串 (密码要和上面一致)
RAG_DATABASE_URL=postgresql://bettafish:你的强密码@postgres:5432/bettafish
```

### 3.3 一键部署

```bash
# 赋予执行权限
chmod +x deploy.sh

# 部署
./deploy.sh
```

脚本会自动完成：构建镜像 → 启动所有容器 → 等待健康检查 → 显示访问地址。

### 3.4 验证

```bash
# 健康检查
curl http://localhost/api/health
# 预期: {"status":"ok","service":"career-research-assistant"}

# 查看服务状态
docker compose ps
# 预期: 4 个服务全部 healthy / running
```

打开浏览器访问 `http://你的服务器IP`，应该能看到前端页面。

---

## 4. 配置详解

### 4.1 环境变量速查

| 变量 | 必填 | 说明 |
|------|------|------|
| `QUERY_ENGINE_API_KEY` | ✅ | LLM API Key |
| `QUERY_ENGINE_BASE_URL` | ✅ | LLM API 地址 |
| `TAVILY_API_KEY` | ✅ | 搜索 API Key |
| `EMBEDDING_API_KEY` | ✅ | 嵌入模型 API Key |
| `PG_PASSWORD` | ✅ | PostgreSQL 密码 |
| `RAG_DATABASE_URL` | ✅ | DB 连接串 |
| `REDIS_URL` | ✅ | Redis 连接串 |
| `ENABLE_RAG` | 可选 | 启用 RAG (默认 1) |
| `RAG_TOP_K` | 可选 | 检索返回数 (默认 4) |
| `RAG_DENSE_WEIGHT` | 可选 | Dense 检索权重 (默认 0.7) |
| `RAG_SPARSE_WEIGHT` | 可选 | Sparse 检索权重 (默认 0.3) |

### 4.2 RAG 混合检索参数调优

在 `.env` 中可以调整 RAG 参数来适配你的场景：

```ini
# 平衡 Dense(语义) 和 Sparse(关键词) 的权重
# 总和应该为 1.0
RAG_DENSE_WEIGHT=0.7    # 语义检索权重
RAG_SPARSE_WEIGHT=0.3   # 关键词检索权重
RAG_TRUST_BONUS=0.5     # 自动回写的信任加成

# 召回数量 (增大可提升召回率但会增加 LLM 成本)
RAG_TOP_K=4

# 启用 Cross-Encoder 重排 (需要额外部署模型或调用 API)
ENABLE_RERANKER=0
```

---

## 5. 运维管理

### 5.1 常用命令

```bash
# ===== 服务管理 =====
docker compose up -d          # 启动全部
docker compose down           # 停止全部
docker compose restart app    # 重启后端
docker compose restart nginx  # 重启前端

# ===== 日志 =====
docker compose logs -f app       # 后端实时日志
docker compose logs -f nginx     # Nginx 日志
docker compose logs --tail=100   # 最近 100 行

# ===== 数据库 =====
docker compose exec postgres psql -U bettafish -d bettafish  # 进入数据库
docker compose exec app bash                                   # 进入后端容器

# ===== 状态 =====
docker compose ps                 # 服务状态
docker stats                      # 资源使用

# 或者用 Makefile
make help
make status
make logs
make restart
```

### 5.2 更新部署

```bash
git pull                        # 拉取最新代码
docker compose build --pull     # 重新构建 (拉取最新 base image)
docker compose up -d            # 重新创建容器
# 或一键:
./deploy.sh
```

### 5.3 备份数据库

```bash
# 导出
docker compose exec -T postgres pg_dump -U bettafish bettafish > backup_$(date +%Y%m%d).sql

# 恢复
docker compose exec -T postgres psql -U bettafish bettafish < backup_20250101.sql
```

**设置 crontab 自动备份：**
```bash
# 每天凌晨 3 点备份，保留 7 天
0 3 * * * cd /path/to/bettafish && docker compose exec -T postgres pg_dump -U bettafish bettafish > backups/backup_$(date +\%Y\%m\%d).sql && find backups/ -mtime +7 -delete
```

### 5.4 资源监控

```bash
# 实时监控
docker stats

# 磁盘使用
docker system df
docker system df -v   # 详细

# 定期清理 (谨慎使用)
docker system prune -a --volumes  # 删除所有未使用的镜像、容器、卷
```

---

## 6. HTTPS 配置（可选但推荐）

### 方式一：Nginx + Let's Encrypt (免费)

在你的**服务器上**（不是在容器里）安装 Certbot：

```bash
# 安装 certbot
sudo apt install certbot -y

# 先停止 nginx 容器，让 certbot 占用 80 端口
docker compose stop nginx

# 申请证书 (替换为你的域名)
sudo certbot certonly --standalone -d bettafish.yourdomain.com

# 证书路径:
# /etc/letsencrypt/live/bettafish.yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/bettafish.yourdomain.com/privkey.pem
```

然后修改 `nginx/default.conf` 添加 443 端口监听：

```nginx
server {
    listen 443 ssl;
    server_name bettafish.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/bettafish.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bettafish.yourdomain.com/privkey.pem;

    # ... 其余配置同上 ...
}

server {
    listen 80;
    server_name bettafish.yourdomain.com;
    return 301 https://$host$request_uri;  # HTTP 跳转 HTTPS
}
```

更新 `docker-compose.yml` 挂载证书：

```yaml
nginx:
  volumes:
    - /etc/letsencrypt:/etc/letsencrypt:ro
```

### 方式二：Cloudflare Tunnel (无需开放端口)

如果你的域名托管在 Cloudflare，可以用 Cloudflare Tunnel 零端口开放实现 HTTPS。略。

---

## 7. 故障排查

### 7.1 服务启动失败

```bash
# 查看具体哪个服务挂了
docker compose ps

# 查看日志
docker compose logs app      # 后端
docker compose logs postgres # 数据库
```

### 7.2 PostgreSQL 连接失败

```bash
# 确认 postgres 已健康
docker compose exec postgres pg_isready -U bettafish -d bettafish

# 检查 .env 中的 RAG_DATABASE_URL
# host 必须是 "postgres" (docker-compose 服务名)，不能是 "localhost"
```

### 7.3 前端页面 502

这通常是 nginx 无法连接后端：

```bash
# 检查 app 容器是否运行
docker compose ps app

# 检查 nginx 能否解析 app 主机名
docker compose exec nginx wget -qO- http://app:9000/api/health
```

### 7.4 镜像构建慢

```bash
# 使用国内镜像加速 (编辑 /etc/docker/daemon.json)
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
# 重启 docker: sudo systemctl restart docker
```

### 7.5 磁盘空间不足

```bash
# 查看是什么占了空间
docker system df

# 清理
docker builder prune    # 清理构建缓存
docker volume prune     # 清理未使用的卷 (⚠ 会删除数据!)
```

---

## 快速参考卡片

```bash
# 首次部署
cp .env.production .env && nano .env && ./deploy.sh

# 更新
git pull && docker compose up -d --build

# 看日志
docker compose logs -f app

# 重启
docker compose restart app

# 备份
docker compose exec -T postgres pg_dump -U bettafish bettafish > backup.sql

# 完全重置
docker compose down -v && docker compose up -d
```
