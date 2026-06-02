-- BettaFish 数据库初始化脚本
-- 在 postgres 容器首次启动时自动执行

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 如果需要在初始化时创建额外的表或索引，写在这里

