import os
from dotenv import load_dotenv

load_dotenv()

# Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# PostgreSQL
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mes_wms_ai")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# API URLs — kelganda .env da o'zgartiring
MES_API_URL = os.getenv("MES_API_URL", "http://localhost:8001")
MES_API_KEY = os.getenv("MES_API_KEY", "")

# Real WMS API (tenzorsoft) — login orqali JWT token olinadi
WMS_API_URL = os.getenv("WMS_API_URL", "https://api-wms.tenzorsoft.uz")
WMS_USERNAME = os.getenv("WMS_USERNAME", "")
WMS_PASSWORD = os.getenv("WMS_PASSWORD", "")

# Mock rejim
USE_MOCK = os.getenv("USE_MOCK", "True").lower() == "true"

# Modellar
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:32b")
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "qwen3:8b")
LLM_HEAVY_MODEL = os.getenv("LLM_HEAVY_MODEL", "qwen3.6:35b")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen3-vl:8b")
VISION_HEAVY_MODEL = os.getenv("VISION_HEAVY_MODEL", "qwen3-vl:30b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
SQL_MODEL = os.getenv("SQL_MODEL", "omnisql-32b-q6:latest")
