import os
import shutil
import asyncio
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

executor = ThreadPoolExecutor()

def get_video_resolution(path: Path) -> str | None:
    """Extract video resolution using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0", str(path)
        ]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        return output if output else None
    except Exception as e:
        return None

def ensure_folder_exists(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def move_file_to_resolution_folder(file_path: Path, resolution: str, base_path: Path, dry_run: bool, log_lines: list):
    if not resolution:
        resolution = "Unknown_Resolution"
    target_dir = base_path / resolution
    target_file = target_dir / file_path.name

    if file_path.parent.name == resolution:
        log_lines.append(f"Skipped (already in {resolution}): {file_path.name}")
        return 'skipped'

    if dry_run:
        log_lines.append(f"[Dry Run] Would move: {file_path.name} -> {target_dir}")
        return 'moved'

    ensure_folder_exists(target_dir)
    shutil.move(str(file_path), str(target_file))
    log_lines.append(f"Moved: {file_path.name} -> {target_dir}")
    return 'moved'

async def process_file(file_path: Path, base_path: Path, dry_run: bool, log_lines: list):
    loop = asyncio.get_event_loop()
    resolution = await loop.run_in_executor(executor, get_video_resolution, file_path)
    result = await loop.run_in_executor(
        executor, move_file_to_resolution_folder, file_path, resolution, base_path, dry_run, log_lines
    )
    return result

async def segregate_files_by_resolution(input_path: str, dry_run: bool = False, log_path: str = None):
    base_path = Path(input_path).resolve()
    if not base_path.is_dir():
        raise Exception(f"❌ '{base_path}' is not a valid directory.")

    files = [f for f in base_path.iterdir() if f.is_file()]
    log_lines = [f"Starting segregation by resolution in: {base_path}", f"Dry Run: {dry_run}"]

    tasks = [process_file(f, base_path, dry_run, log_lines) for f in files]
    results = await asyncio.gather(*tasks)

    moved = results.count('moved')
    skipped = results.count('skipped')

    log_lines.append(f"\n✅ Completed. Moved: {moved}, Skipped: {skipped}")

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))

    return {
        'moved_total': moved,
        'skipped_total': skipped,
        'log_lines': log_lines
    }

if __name__ == "__main__":
    user_input = input("Enter the full path to the directory: ").strip()
    try:
        asyncio.run(segregate_files_by_resolution(user_input, dry_run=True))
    except Exception as e:
        print("❌ Exception occurred:", e)
