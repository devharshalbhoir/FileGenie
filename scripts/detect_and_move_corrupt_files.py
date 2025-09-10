import os
import shutil
import subprocess
from pathlib import Path


def is_video_corrupt(file_path: Path) -> bool:
    """
    Check if a video file is corrupt using ffmpeg.
    Returns True if corrupt/unreadable, False otherwise.
    """
    try:
        cmd = [
            "ffmpeg", "-v", "error", "-i", str(file_path),
            "-f", "null", "-", "-y"
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # If ffmpeg writes anything to stderr, it's probably an error
        if result.stderr.strip():
            return True
        return False
    except Exception:
        return True  # treat as corrupt if ffmpeg itself fails


def move_corrupt_file(file_path: Path, corrupt_folder: Path, dry_run: bool, log_lines: list):
    target_file = corrupt_folder / file_path.name
    if dry_run:
        log_lines.append(f"[Dry Run] Would move corrupt: {file_path} -> {target_file}")
        return "detected"

    corrupt_folder.mkdir(parents=True, exist_ok=True)
    shutil.move(str(file_path), str(target_file))
    log_lines.append(f"Moved corrupt: {file_path} -> {target_file}")
    return "moved"


def detect_and_move_corrupt_files(folder: str, dry_run: bool = False, log_path: str = None):
    base_path = Path(folder).resolve()
    if not base_path.is_dir():
        raise Exception(f"❌ '{base_path}' is not a valid directory.")

    corrupt_folder = base_path / "Corrupt"
    video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv"}
    files = [f for f in base_path.iterdir() if f.suffix.lower() in video_extensions]

    log_lines = [f"Starting corrupt file detection in: {base_path}", f"Dry Run: {dry_run}"]
    moved, skipped = 0, 0

    for file in files:
        if is_video_corrupt(file):
            result = move_corrupt_file(file, corrupt_folder, dry_run, log_lines)
            if result == "moved":
                moved += 1
        else:
            skipped += 1
            log_lines.append(f"OK: {file.name}")

    log_lines.append(f"\n✅ Completed. Moved corrupt: {moved}, OK files: {skipped}")

    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))

    return {
        "moved_total": moved,
        "ok_total": skipped,
        "log_lines": log_lines
    }


if __name__ == "__main__":
    folder = input("Enter the folder path with videos: ").strip()
    try:
        result = detect_and_move_corrupt_files(folder, dry_run=False)
        for line in result["log_lines"]:
            print(line)
    except Exception as e:
        print("❌ Exception occurred:", e)
