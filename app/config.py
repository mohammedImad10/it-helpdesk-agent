from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent
SIMULATOR_ROOT = PROJECT_ROOT / "simulator"
KIT_ROOT = SIMULATOR_ROOT if SIMULATOR_ROOT.is_dir() else (
    REPOSITORY_ROOT / "Final-Mini-Project" / "scenario-2-it-helpdesk" / "kit"
)
DATASET_ROOT = KIT_ROOT / "dataset"
KB_ROOT = DATASET_ROOT / "knowledge_base"
INDEX_PATH = PROJECT_ROOT / "data" / "kb_index.json"
MEMORY_PATH = PROJECT_ROOT / "data" / "helpdesk.sqlite3"

HELPDESK_MCP_COMMAND = sys.executable
HELPDESK_MCP_ARGS = [str(KIT_ROOT / "services" / "helpdesk_mcp.py")]
HELPDESK_TIMEOUT_SECONDS = float(os.getenv("HELPDESK_TIMEOUT_S", "20"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "openai/gpt-4.1-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
