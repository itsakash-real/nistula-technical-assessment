"""
Centralised configuration loader.

All environment variables are read exactly once, here.
No other file imports os or reads .env directly.
This ensures configuration is predictable and easy to audit.
"""

import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY is not set in environment variables.")