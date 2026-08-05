"""Cau hinh tap trung cho pipeline multi-agent EC_POLICY_V2."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logging"

TRACE_PATH = LOG_DIR / "trace.jsonl"
METADATA_PATH = LOG_DIR / "metadata.json"

# Model duoc khai bao ro trong source code theo yeu cau de bai (<= 10B params).
LLM_PROVIDER = "groq"
LLM_MODEL = "llama-3.1-8b-instant"
LLM_PARAM_SIZE_B = 8
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 900
LLM_TIMEOUT_S = 60
LLM_MAX_RETRIES = 3

POLICY_VERSION = "EC_POLICY_V2"
CURRENCY = "BRL"

# Nguong doi soat payment theo de bai.
RECONCILE_TOLERANCE_BRL = 0.10

TS_FORMAT = "%Y-%m-%d %H:%M:%S"

# Gioi han array trong output schema.
LIMITS = {
    "order_ids": 5,
    "item_ids": 5,
    "seller_ids": 3,
    "payment_ids": 5,
    "related_order_ids": 5,
    "product_ids": 5,
    "category_names": 5,
    "ranked_causes": 3,
    "responsible_parties": 3,
    "evidence_ids": 20,
    "resolution_actions": 5,
}
