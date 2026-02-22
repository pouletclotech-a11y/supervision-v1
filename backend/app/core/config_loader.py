import yaml
from pathlib import Path

CONFIG_PATH = Path("/app/config.yml")

def load_config():
    if not CONFIG_PATH.exists():
        return {}
    
    with open(CONFIG_PATH, "r") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as exc:
            print(f"Error loading config.yml: {exc}")
            return {}

# Load once at import time
app_config = load_config()
