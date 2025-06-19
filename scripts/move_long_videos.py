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

async def process_video(video_path, destination_folder, faulty_folder, dry_run, executor, log_lines):
    loop = asyncio.get_running_loop()
    duration = await loop.run_in_executor(executor, get_video_duration, video_path)

    if duration is None:
        return await loop.run_in_executor(executor, move_video, video_path, faulty_folder, dry_run, log_lines)
    elif duration > 480:
        return await loop.run_in_executor(executor, move_video, video_path, destination_folder, dry_run, log_lines)
    else:
        log_lines.append(f"[Skipped] Video too short: {video_path} ({duration:.2f}s)")
        return "skipped"

async def find_and_move_long_videos(source_folder, dry_run=False, log_path=None):
    destination_folder = os.path.join(source_folder, "Long_Videos")
    faulty_folder = os.path.join(source_folder, "faulty_videos")

    os.makedirs(destination_folder, exist_ok=True)
    os.makedirs(faulty_folder, exist_ok=True)

    video_files = [str(file) for file in Path(source_folder).rglob("*.mp4")]
    log_lines = []
    executor = concurrent.futures.ThreadPoolExecutor()

    tasks = [
        process_video(video, destination_folder, faulty_folder, dry_run, executor, log_lines)
        for video in video_files
    ]
    results = await asyncio.gather(*tasks)
    executor.shutdown()

    moved_count = results.count("moved")
    skipped_count = results.count("skipped")

    log_lines.append(f"\nTotal videos moved: {moved_count}")
    log_lines.append(f"Total videos skipped: {skipped_count}")

    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))