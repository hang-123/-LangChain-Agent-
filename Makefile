# BettaFish Docker 常用命令

.PHONY: help up down build restart logs status clean

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:     ## 启动全部服务
	docker compose up -d

down:   ## 停止全部服务
	docker compose down

build:  ## 重新构建镜像
	docker compose build --pull

restart:  ## 重启 app 服务
	docker compose restart app

logs:   ## 查看 app 日志 (跟随模式)
	docker compose logs -f app

logs-all:  ## 查看全部日志
	docker compose logs -f

status:  ## 查看服务状态
	docker compose ps

shell:  ## 进入 app 容器
	docker compose exec app bash

db-shell:  ## 进入 PostgreSQL
	docker compose exec postgres psql -U bettafish -d bettafish

clean:  ## 停止并删除所有数据 (危险!)
	docker compose down -v
	@echo "所有数据和卷已删除"
