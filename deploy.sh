#!/usr/bin/env bash
# ============================================================
# BettaFish 一键部署脚本
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; }
info() { echo -e "${BLUE}[i]${NC} $*"; }

# ───────────────────────────────────────
# 1. 前置检查
# ───────────────────────────────────────
echo ""
echo "=========================================="
echo "  BettaFish 生产部署"
echo "=========================================="
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    err "Docker 未安装。请先安装 Docker: https://docs.docker.com/engine/install/"
    exit 1
fi
log "Docker 已安装: $(docker --version)"

# 检查 Docker Compose
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
elif docker-compose version &> /dev/null; then
    COMPOSE="docker-compose"
else
    err "Docker Compose 未安装"
    exit 1
fi
log "Docker Compose 已安装"

# 检查 .env
if [ ! -f .env ]; then
    warn ".env 文件不存在，正在从 .env.production 创建..."
    if [ -f .env.production ]; then
        cp .env.production .env
        warn "请编辑 .env 填入真实 API Key 和密码后重新运行"
        exit 1
    else
        err ".env.production 也不存在，请手动创建 .env 文件"
        exit 1
    fi
fi
log ".env 文件已就绪"

# ───────────────────────────────────────
# 2. 构建 & 启动
# ───────────────────────────────────────
echo ""
info "正在构建镜像..."
$COMPOSE build --pull

echo ""
info "正在启动服务..."
$COMPOSE up -d

# ───────────────────────────────────────
# 3. 等待健康检查
# ───────────────────────────────────────
echo ""
info "等待服务就绪..."

# 等待 PostgreSQL
for i in $(seq 1 30); do
    if $COMPOSE exec postgres pg_isready -U bettafish -d bettafish &> /dev/null; then
        log "PostgreSQL 就绪"
        break
    fi
    if [ "$i" -eq 30 ]; then
        err "PostgreSQL 启动超时"
        $COMPOSE logs postgres --tail 20
        exit 1
    fi
    sleep 2
done

# 等待 App
for i in $(seq 1 30); do
    if curl -sf http://localhost:9000/api/health &> /dev/null; then
        log "Backend API 就绪"
        break
    fi
    if [ "$i" -eq 30 ]; then
        err "Backend 启动超时"
        $COMPOSE logs app --tail 20
        exit 1
    fi
    sleep 2
done

# 等待 Nginx
for i in $(seq 1 10); do
    if curl -sf http://localhost:80/health &> /dev/null; then
        log "Nginx 就绪"
        break
    fi
    if [ "$i" -eq 10 ]; then
        warn "Nginx 健康检查未通过（可能不影响使用）"
    fi
    sleep 1
done

# ───────────────────────────────────────
# 4. 部署信息
# ───────────────────────────────────────
echo ""
echo "=========================================="
echo "  🚀 部署完成！"
echo "=========================================="
echo ""
info "服务状态:"
$COMPOSE ps
echo ""

# 获取服务器 IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")
echo "  访问地址:"
echo "    前端:  http://${SERVER_IP}"
echo "    API:   http://${SERVER_IP}/api/health"
echo "    Docs:  http://${SERVER_IP}/api/docs"
echo ""
echo "  常用命令:"
echo "    查看日志:  $COMPOSE logs -f app"
echo "    查看状态:  $COMPOSE ps"
echo "    重启服务:  $COMPOSE restart app"
echo "    停止全部:  $COMPOSE down"
echo "    更新部署:  ./deploy.sh"
echo ""
