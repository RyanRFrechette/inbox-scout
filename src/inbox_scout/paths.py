from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
TOKENS_DIR = PROJECT_ROOT / "tokens"

# Legacy primary-account token paths (kept at project root for backward compat)
_PRIMARY_TOKEN_FILES = {
    "readonly": PROJECT_ROOT / "token.json",
    "modify": PROJECT_ROOT / "token_modify.json",
    "settings": PROJECT_ROOT / "token_settings.json",
}


def get_token_path(account: str, mode: str) -> Path:
    if account == "primary":
        return _PRIMARY_TOKEN_FILES[mode]
    return TOKENS_DIR / f"{account}_{mode}.json"

RAW_DIR = DATA_DIR / "raw"
EXPORTS_DIR = DATA_DIR / "exports"
REPORTS_DIR = DATA_DIR / "reports"
HISTORY_DIR = DATA_DIR / "history"

PROTECTED_TERMS_FILE = CONFIG_DIR / "protected_terms.txt"
PROTECTED_SENDERS_FILE = CONFIG_DIR / "protected_senders.txt"
RULES_FILE = CONFIG_DIR / "rules.json"

LATEST_RESORT_PLAN = DATA_DIR / "plans" / "latest_resort_plan.json"


def verify_project_structure() -> dict:
    required_paths = [
        CREDENTIALS_DIR,
        CONFIG_DIR,
        DATA_DIR,
        RAW_DIR,
        EXPORTS_DIR,
        REPORTS_DIR,
        HISTORY_DIR,
        PROTECTED_TERMS_FILE,
        PROTECTED_SENDERS_FILE,
        RULES_FILE,
    ]

    results = {}

    for path in required_paths:
        results[str(path)] = path.exists()

    return results
