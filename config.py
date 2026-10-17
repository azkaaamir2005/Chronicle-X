import os
from pathlib import Path

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent

# Directory Paths
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
ARCHIVES_DIR = DATA_DIR / "archives"
OUTPUTS_DIR = BASE_DIR / "outputs"
ASSETS_DIR = BASE_DIR / "assets"

# Ensure necessary directories exist
for directory in [PROFILES_DIR, ARCHIVES_DIR, OUTPUTS_DIR, ASSETS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# API Configurations (Loaded from environment variables)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Model Settings (Using Groq's high-speed inference models)
DEFAULT_LLM_MODEL = "openai/gpt-oss-120b"  # Exceptional for synthesis, reasoning, and editorial writing
# Alternative fast model: "openai/gpt-oss-20b"

# Newspaper Layout & Styling Configuration
NEWSPAPER_NAME = "CHRONICLEX"
NEWSPAPER_TAGLINE = "The Dialectic Broadsheet & Cognitive Mirror"
DEFAULT_PAGE_SIZE = "A4"
PDF_MARGIN_MM = 15

# Default Interest Categories & Serendipity Parameters
DEFAULT_CATEGORIES = [
    "Artificial Intelligence & Autonomous Systems",
    "Global Economics & Geopolitics",
    "Deep Tech & Engineering",
    "Ethics, Philosophy & Society",
    "Serendipity / Wildcard Breakthroughs"
]

SERENDIPITY_RATIO = 0.15  # 15% wildcard injection to prevent echo chambers