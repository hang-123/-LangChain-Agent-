import os
from dotenv import load_dotenv
from pathlib import Path

from openai import OpenAI

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent


# 加载 .env 文件（放在项目根目录）
load_dotenv(BASE_DIR / ".env")

#llm
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME")

# 本地文档路径
LOCAL_DOCS_DIR = BASE_DIR / "data" / "docs"

if not LOCAL_DOCS_DIR.exists():
    LOCAL_DOCS_DIR.mkdir(parents=True, exist_ok=True)

# pgdb配置

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "bettafish")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
PG_COLLECTION_NAME = os.getenv("PG_COLLECTION_NAME", "insight_docs")
