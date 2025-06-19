from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def generate_log_filename(prefix="operation"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.txt"

def write_log(log_path, lines):
    """Write a list of lines to a log file."""
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")
