from pathlib import Path
from dotenv import load_dotenv
import os
import json

load_dotenv()

JOB_FEED_URLS = json.loads(os.getenv("JOB_FEED_URLS", "[]"))

if not isinstance(JOB_FEED_URLS, list):
    raise TypeError(
        f"JOB_FEED_URLS must be a list, got {type(JOB_FEED_URLS).__name__}: {JOB_FEED_URLS!r}"
    )

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_JOBS_DIR = DATA_DIR / "raw_jobs"
PROCESSED_DIR = DATA_DIR / "processed"
VECTOR_DIR = DATA_DIR / "vector_store"

for path in [DATA_DIR, RAW_JOBS_DIR, PROCESSED_DIR, VECTOR_DIR]:
    path.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DATABASE_PATH = os.getenv("DATABASE_PATH", str(PROCESSED_DIR / "jobs.db"))
CHROMA_DIR = os.getenv("CHROMA_DIR", str(VECTOR_DIR))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "job_agent_docs")

MATCH_THRESHOLD = int(os.getenv("MATCH_THRESHOLD", "70"))
TOP_K = int(os.getenv("TOP_K", "4"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "4000"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

print("JOB_FEED_URLS type:", type(JOB_FEED_URLS))
print("JOB_FEED_URLS sample:", JOB_FEED_URLS[:2] if isinstance(JOB_FEED_URLS, list) else repr(JOB_FEED_URLS))