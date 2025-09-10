import re
import os
import math
import datetime
from pathlib import Path
from imdbmovies import IMDB


# ---------------------------
# Cleaning function
# ---------------------------
def clean_movie_name(raw_name: str) -> str:
    """Clean a movie folder/file name to extract a probable title."""
    name = raw_name

    # Replace dots/underscores with spaces
    name = re.sub(r"[._]", " ", name)

    # If a year is present, keep everything before & including it
    year_match = re.search(r"\b(19|20)\d{2}\b", name)
    if year_match:
        year_end = year_match.end()
        name = name[:year_end]

    # Remove junk words/patterns (for cases without year or before year section)
    patterns = [
        r"\b(480p|720p|1080p|2160p|4k|10bit)\b",
        r"\b(BluRay|WEB[- ]DL|WEBRip|HDRip|DVDRip|BRRip|CAM|HDTS)\b",
        r"\b(x264|x265|h264|h265|HEVC|AV1)\b",
        r"\b(AAC|DDP\d\.\d|DTS|TrueHD|Atmos|MP3)\b",
        r"\b(YTS\d\.\d|YIFY|RARBG|NeoNoir|EVO|FGT|LOL|PSA|HDRush|Spidey|Asiimov|ION10|GalaxyRG|TGx|MkvCage|rmteam)\b",
        r"\b(Hindi|Urdu|Tamil|Telugu|Malayalam|Kannada|Bengali|Japanese)\b",
        r"\b(NF|ZEE5|Prime|Hotstar|Disney|AMZN|Netflix)\b",
        r"\b(TheMoviesBoss|Yo-Movies|yo-movies|4MovieRulz|TamilMV|b13)\b",
        r"\b(Hain|Mal|Sun|George|Watch|Online|Cleaned|HC|HQ|ESub|ESubs)\b",
        r"\b(www)\b",
        r"\b\d{3,4}MB\b",
        r"[\[\]\(\)«»]"
    ]

    for p in patterns:
        name = re.sub(p, "", name, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", name).strip()


# ---------------------------
# Helpers for size & date
# ---------------------------
def get_size(path: Path) -> int:
    """Return folder/file size in bytes."""
    if path.is_file():
        return path.stat().st_size
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def human_readable_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    return f"{size_bytes / p:.2f} {size_name[i]}"


# ---------------------------
# Safe rating parsing
# ---------------------------
def safe_parse_rating(rating):
    if isinstance(rating, (int, float, str)):
        try:
            return float(rating)
        except ValueError:
            return None
    elif isinstance(rating, dict):
        return safe_parse_rating(rating.get("ratingValue"))
    return None


# ---------------------------
# Verdict logic
# ---------------------------
VERDICT_MAP = [
    (9.0, "Excellent – must-watch"),
    (7.0, "Good – enjoyable"),
    (5.0, "Fair – maybe watch with family"),
    (0.0, "Poor – skip it"),
]


def get_verdict(rating: float) -> str:
    for threshold, verdict in VERDICT_MAP:
        if rating >= threshold:
            return verdict
    return "No verdict"


# ---------------------------
# Main processing function
# ---------------------------
def process_movies(parent_folder: str):
    base = Path(parent_folder).resolve()
    imdb = IMDB()
    video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"}

    log_path = base / "imdb_log.txt"
    results = []

    for sub in base.iterdir():
        if sub.is_dir():
            raw_name = sub.name
        elif sub.is_file() and sub.suffix.lower() in video_extensions:
            raw_name = sub.stem
        else:
            continue

        movie_name = clean_movie_name(raw_name)
        print(f"🔍 Searching IMDb for: '{movie_name}'...")

        try:
            res = imdb.get_by_name(movie_name, tv=False)
        except Exception as e:
            print(f"  ❌ Error searching '{movie_name}': {e}")
            continue

        info = res[0] if isinstance(res, list) and res else res
        if not info:
            print(f"  ⚠️ No IMDb result for '{movie_name}'")
            continue

        rating_val = safe_parse_rating(info.get("rating"))
        summary = info.get("description") or info.get("plot") or "No summary available."
        verdict = get_verdict(rating_val) if rating_val is not None else "Unknown"
        size_bytes = get_size(sub)
        size_hr = human_readable_size(size_bytes)

        results.append({
            "name": movie_name,
            "rating": rating_val,
            "summary": summary,
            "verdict": verdict,
            "size": size_bytes,
            "size_hr": size_hr
        })

    # Sorting priority:
    # 1. Highest rating
    # 2. Largest size
    # 3. Oldest modified date
    results.sort(key=lambda x: (
        -(x["rating"] or 0),
        -x["size"]
    ))

    log_lines = [f"🎬 IMDb Movie Report for: {base}\n{'=' * 60}\n"]

    for idx, r in enumerate(results, 1):
        indicator = "❌" if r["rating"] is not None and r["rating"] < 5.0 else "✅"
        suggestion = f"Priority #{idx}"

        entry = (
            f"{indicator} {r['name']}\n"
            f"IMDb Rating: {r['rating'] or 'N/A'}\n"
            f"Summary: {r['summary']}\n"
            f"Verdict: {r['verdict']}\n"
            f"Size: {r['size_hr']}\n"
            f"Suggestion: {suggestion}\n"
            f"{'-' * 60}\n"
        )
        log_lines.append(entry)

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"\n📄 IMDb report with size & priority saved at: {log_path}")


# ---------------------------
# Entry point
# ---------------------------
if __name__ == "__main__":
    folder = input("Enter the parent folder path: ").strip()
    process_movies(folder)
