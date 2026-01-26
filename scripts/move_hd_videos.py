import os
import shutil
import asyncio
import concurrent.futures
import subprocess
from pathlib import Path

def get_video_duration(video_path):
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=duration", "-of", "csv=p=0",
            video_path
        ], capture_output=True, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        return None

def move_video(video_path, destination_folder, dry_run, log_lines):
    try:
        destination_path = Path(destination_folder) / Path(video_path).name
        if Path(video_path).parent == Path(destination_folder):
            log_lines.append(f"[Skipped] Already in correct folder: {video_path}")
            return "skipped"

        if dry_run:
            log_lines.append(f"[Dry Run] Would move: {video_path} -> {destination_path}")
            return "dry_run"

        shutil.move(video_path, destination_path)
        log_lines.append(f"Moved: {video_path} -> {destination_path}")
        return "moved"
    except Exception as e:
        log_lines.append(f"Error moving {video_path}: {e}")
        return "error"

async def process_video(video_path, destination_folder, dry_run, executor, log_lines):
    loop = asyncio.get_running_loop()
    
    # Check size first (faster than ffprobe)
    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    
    if size_mb <= 70:
        log_lines.append(f"[Skipped] Video too small: {video_path} ({size_mb:.2f}MB)")
        return "skipped"

    duration = await loop.run_in_executor(executor, get_video_duration, video_path)

    if duration is None:
        log_lines.append(f"[Error] Could not get duration: {video_path}")
        return "error"
    elif duration < 600: # Less than 10 mins
        return await loop.run_in_executor(executor, move_video, video_path, destination_folder, dry_run, log_lines)
    else:
        log_lines.append(f"[Skipped] Video too long: {video_path} ({duration:.2f}s)")
        return "skipped"

async def find_and_move_hd_videos(source_folder, dry_run=False, log_path=None):
    current_folder_name = os.path.basename(source_folder.rstrip(os.sep))
    destination_folder = os.path.join(source_folder, f"hd_vids_{current_folder_name}")

    os.makedirs(destination_folder, exist_ok=True)

    # Support common video extensions
    extensions = ("*.mp4", "*.mkv", "*.avi", "*.mov", "*.flv", "*.wmv")
    video_files = []
    for ext in extensions:
        video_files.extend([str(file) for file in Path(source_folder).glob(ext)])
        
    log_lines = []
    log_lines.append(f"Source Folder: {source_folder}")
    log_lines.append(f"Target Folder: {destination_folder}")
    log_lines.append(f"Criteria: Size > 100MB and Duration < 10 mins\n")

    if not video_files:
        log_lines.append("No video files found.")
    
    executor = concurrent.futures.ThreadPoolExecutor()

    tasks = [
        process_video(video, destination_folder, dry_run, executor, log_lines)
        for video in video_files
    ]
    results = await asyncio.gather(*tasks)
    executor.shutdown()

    moved_count = results.count("moved")
    skipped_count = results.count("skipped")
    error_count = results.count("error")
    dry_run_count = results.count("dry_run")

    log_lines.append(f"\nSummary:")
    log_lines.append(f"Total videos moved: {moved_count}")
    log_lines.append(f"Total videos skipped: {skipped_count}")
    log_lines.append(f"Total errors: {error_count}")
    if dry_run:
        log_lines.append(f"Total would-be moved (Dry Run): {dry_run_count}")

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
    
    return {
        "moved_total": moved_count if not dry_run else dry_run_count,
        "skipped_total": skipped_count
    }
